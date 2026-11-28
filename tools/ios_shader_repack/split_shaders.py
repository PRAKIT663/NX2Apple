"""Repack a slim NxNative IPA's shader images as separate files."""
import argparse
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from romfs import Image

SHADER = re.compile(r"Payload/[^/]+\.app/msl/(?:p\d+/)?b-[^/]+\.img")
APP_INFO = re.compile(r"Payload/[^/]+\.app/Info\.plist")


def unpack_shaders(archive, entry, output, names, temp):
    image_path = temp / "shader.img"
    with archive.open(entry) as source, image_path.open("wb") as target:
        shutil.copyfileobj(source, target, 1024 * 1024)
    image = Image(image_path)
    files = image.children(0)
    if not any(name.endswith(".metallib") for name, _ in files):
        raise ValueError("Shader image contains no Metal libraries")
    with image_path.open("rb") as source:
        for name, index in files:
            offset, size, _, _, kind, _ = image.entry(index)
            destination = entry.filename[:-4] + "/" + name
            if kind != 1 or "\\" in name or destination in names:
                raise ValueError(f"Unexpected shader entry: {name}")
            member = zipfile.ZipInfo(destination, entry.date_time)
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            member.file_size = size
            source.seek(offset)
            with output.open(member, "w") as target:
                while size:
                    chunk = source.read(min(size, 1024 * 1024))
                    if not chunk:
                        raise ValueError("Incomplete shader image")
                    target.write(chunk)
                    size -= len(chunk)
            names.add(destination)
    image_path.unlink()
    print(f"Split {entry.filename} into {len(files):,} files.", flush=True)


def split_ipa(source, output, separate_romfs=False):
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    with zipfile.ZipFile(source) as archive, tempfile.TemporaryDirectory(dir=output.parent) as directory:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        if len(names) != len(entries) or sum(bool(APP_INFO.fullmatch(n)) for n in names) != 1:
            raise ValueError("Expected a ZIP containing one Payload/<name>.app/Info.plist")
        romfs = {n for n in names if re.fullmatch(r"Payload/[^/]+\.app/romfs(?:\.img|/.*)", n, re.I)}
        if romfs and not separate_romfs:
            raise ValueError("Use the slim IPA after separating romfs.img.")
        shaders = [entry for entry in entries if SHADER.fullmatch(entry.filename)]
        if not shaders:
            raise ValueError("No packed NxNative shader image found")
        work = Path(directory)
        temporary = work / "output.ipa"
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for entry in entries:
                if entry.filename in romfs:
                    continue
                if SHADER.fullmatch(entry.filename):
                    unpack_shaders(archive, entry, target, names, work)
                else:
                    with archive.open(entry) as incoming, target.open(entry, "w") as outgoing:
                        shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        temporary.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--separate-romfs", action="store_true", help="leave bundled RomFS out of the new IPA")
    arguments = parser.parse_args()
    destination = arguments.ipa.with_name(arguments.ipa.stem + "-ShaderFiles.ipa")
    try:
        split_ipa(arguments.ipa, destination, arguments.separate_romfs)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Created: {destination}")
