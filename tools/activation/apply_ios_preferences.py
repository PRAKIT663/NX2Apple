"""Apply the Dragon Ball iPhone touch artwork and launcher defaults."""
import argparse
from pathlib import Path
import subprocess


def apply(engine):
    patch = Path(__file__).resolve().with_name("combat-touch-icons.patch")
    settings = engine / "dm/games/settings.tsv"
    rows = settings.read_text(encoding="utf-8").splitlines(keepends=True)
    matches = [i for i, row in enumerate(rows) if row.startswith("DM_FPS_TARGET\t")]
    if len(matches) != 1:
        raise SystemExit("Expected one Frame rate setting")
    index = matches[0]
    fields = rows[index].split("\t")
    if fields[3] not in ("DM_GAME_FPS_TARGET", "30|DM_GAME_FPS_TARGET"):
        raise SystemExit("Unexpected Frame rate default")
    fields[3] = "30|DM_GAME_FPS_TARGET"
    rows[index] = "\t".join(fields)

    command = ["git", "-C", str(engine), "apply"]
    already_applied = subprocess.run(
        [*command, "--reverse", "--check", str(patch)], capture_output=True
    ).returncode == 0
    if not already_applied:
        subprocess.run([*command, "--check", str(patch)], check=True)
        subprocess.run([*command, str(patch)], check=True)
    settings.write_text("".join(rows), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    apply(parser.parse_args().engine)
