"""Download private Dragon Ball inputs and verify them using the pinned engine."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

TITLE = 0x010035F022078000
EXTENSIONS = {".nsp", ".nsz", ".xci", ".xcz"}


def download(label, target):
    url = os.environ.get(f"{label}_URL", "").strip()
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        raise SystemExit(f"{label}_URL must contain an HTTPS download URL")
    result = subprocess.run(
        ["curl", "--location", "--fail", "--silent", "--retry", "3",
         "--proto", "=https", "--output", str(target), "--url", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode or not target.is_file() or not target.stat().st_size:
        raise SystemExit(f"Download failed for {label}. Verify the private direct download URL.")


def stage(label, work, packages):
    source = work / f"{label}.download"
    download(label, source)
    with source.open("rb") as stream:
        header = stream.read(8)
        stream.seek(0x100)
        cartridge = stream.read(4)
    if header.startswith((b"Rar!\x1a\x07", b"PK\x03\x04")):
        extracted = work / label
        extracted.mkdir()
        subprocess.run(["unar", "-q", "-D", "-o", str(extracted), str(source)], check=True)
        wanted = sorted(p for p in extracted.rglob("*") if p.is_file() and not p.is_symlink()
                        and p.suffix.lower() in EXTENSIONS)
        for index, path in enumerate(wanted):
            path.rename(packages / f"{label}-{index}{path.suffix.lower()}")
        source.unlink()
    elif header.startswith(b"PFS0") or cartridge == b"HEAD":
        suffix = Path(urlsplit(os.environ[f"{label}_URL"]).path).suffix.lower()
        if suffix not in EXTENSIONS:
            suffix = ".nsp" if header.startswith(b"PFS0") else ".xci"
        source.rename(packages / f"{label}-0{suffix}")
        wanted = [source]
    else:
        raise SystemExit(f"{label} is not a supported package or archive. Use a file download URL, not a share page.")
    expected = 12 if label == "DLC" else 1
    if len(wanted) != expected:
        raise SystemExit(f"{label}: expected {expected} package(s), got {len(wanted)}")


def verify(engine, work):
    packages = work / "packages"
    packages.mkdir(parents=True)
    keys = work / "prod.keys"
    download("KEYS", keys)
    keys.chmod(0o600)
    for label in ("GAME", "UPDATE", "DLC"):
        stage(label, work, packages)

    sys.path.insert(0, str(engine / "scripts"))
    import build_ipa_from_nsp as builder
    import nacp

    env = dict(os.environ)
    for label in ("GAME", "UPDATE", "DLC", "KEYS"):
        env.pop(f"{label}_URL", None)
    with builder.package_reader(engine, keys, env) as reader:
        _, family = builder.scan_nsps(packages, reader.contents, TITLE)
        reader.check_keys(family)
    if (len(family["updates"]) != 1 or len(family["dlc"]) != 12
            or len({tid for tid, _, _ in family["dlc"]}) != 12
            or not family["base"].name.startswith("GAME-")
            or not family["updates"][0][1].name.startswith("UPDATE-")
            or any(not path.name.startswith("DLC-") for _, _, path in family["dlc"])):
        raise SystemExit("Expected one Dragon Ball base, one update, and 12 distinct DLC titles in their respective inputs.")

    with TemporaryDirectory(dir=work) as temp:
        validation = Path(temp)
        family = builder.decompress_nsz(packages, TITLE, family, keys, env, validation)
        version, update = family["updates"][0]
        extractor = builder.find_nx_extract(engine, env)
        manifest = validation / "manifest"
        subprocess.run([str(extractor), str(keys), str(family["base"]), str(update),
                        str(manifest), "--manifest", "--app", f"{TITLE:016X}"],
                       check=True, env=env, stdout=subprocess.DEVNULL)
        display = nacp.display_version(manifest / "control.nacp")
        if display != "2.0.74":
            raise SystemExit(f"Expected update 2.0.74, got {display or 'no display version'} (CNMT v{version}).")
    print(f"Verified game {TITLE:016X}, update {display} (CNMT v{version}), and 12 distinct DLC titles.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    verify(args.engine.resolve(), args.work.resolve())
