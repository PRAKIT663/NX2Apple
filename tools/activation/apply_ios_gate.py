"""Apply the Dragon Ball activation gate to the pinned experimental iOS engine."""

import argparse
from pathlib import Path
import shutil
import subprocess

PIN = "634829096267587aed7a578cdcc2ea72ed77ecd8"
INCLUDE = '#import "DragonBallActivation.h"\n'
ENTRY = "    self.window.rootViewController = front_ios_root();\n"
GATE = """    DragonBallActivation *activation = [DragonBallActivation new];
    __weak SceneDelegate *sceneDelegate = self;
    activation.onAllowed = ^{
        SceneDelegate *delegate = sceneDelegate;
        if (!delegate) return;
        delegate.window.rootViewController = front_ios_root();
        front_ios_focus_event(UIApplication.sharedApplication.applicationState == UIApplicationStateActive ? 3 : 0);
    };
    self.window.rootViewController = activation;
"""


def apply(engine: Path) -> None:
    head = subprocess.check_output(
        ["git", "-C", str(engine), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != PIN:
        raise SystemExit(f"Unexpected iOS engine revision: {head}")

    main = engine / "dm/ios/Sources/main.m"
    source = main.read_text(encoding="utf-8")
    marker = "@interface SceneDelegate : UIResponder <UIWindowSceneDelegate>"
    if source.count(marker) != 1:
        raise SystemExit("Could not identify the iOS scene delegate")

    if INCLUDE in source:
        if source.count(INCLUDE) != 1 or source.count(GATE) != 1 or ENTRY in source:
            raise SystemExit("Existing activation gate does not match")
    else:
        if source.count(ENTRY) != 1:
            raise SystemExit("Could not identify the game root controller")
        source = source.replace(marker, INCLUDE + "\n" + marker).replace(ENTRY, GATE)

    shutil.copyfile(Path(__file__).with_name("DragonBallActivation.h"), main.with_name("DragonBallActivation.h"))
    main.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    apply(parser.parse_args().engine)
