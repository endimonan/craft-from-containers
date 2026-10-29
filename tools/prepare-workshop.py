"""Stage only upload files; never publish or overwrite an existing Workshop item."""
from pathlib import Path
import hashlib
import os
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MOD = "BSCCraftFromContainers"
version = re.search(r"^modversion=(\S+)$", (ROOT / f"Contents/mods/{MOD}/42/mod.info").read_text(encoding="utf-8"), re.MULTILINE).group(1)
zomboid = Path.home() / "Zomboid"
destination = Path(sys.argv[1]) if len(sys.argv) > 1 else zomboid / "Workshop" / MOD
if destination.exists():
    raise SystemExit(f"Destination already exists; preserve its Workshop ID and local edits: {destination}")
# The game loads mods from both folders; two copies of one mod id break the mod list.
if (zomboid / "Workshop") in destination.resolve().parents and (zomboid / "mods" / MOD).exists():
    raise SystemExit(f"Remove the local test copy first: {zomboid / 'mods' / MOD}")
files = sorted(p for p in (ROOT / "Contents").rglob("*") if p.is_file())
files += [ROOT / "preview.png", ROOT / "workshop.txt"]
expected = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
destination.mkdir(parents=True, exist_ok=False)
for source in files:
    target = destination / source.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
actual = {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in destination.rglob("*") if p.is_file()}
assert actual == expected, "Staged files differ from source"
output = ROOT / f"dist/{MOD}-{version}-workshop.zip"
output.parent.mkdir(exist_ok=True)
temporary = output.with_suffix(".zip.tmp")
with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(expected):
        archive.write(destination / name, f"{MOD}/" + name)
with zipfile.ZipFile(temporary) as archive:
    assert archive.testzip() is None
    packed = {name.removeprefix(f"{MOD}/"): hashlib.sha256(archive.read(name)).hexdigest()
              for name in archive.namelist()}
    assert packed == expected, "ZIP contents differ from staged files"
os.replace(temporary, output)
print(f"Workshop folder: {destination}")
print(f"Verified {len(expected)} files, source = folder = ZIP")
print(f"ZIP: {output}")
print(f"ZIP SHA256: {hashlib.sha256(output.read_bytes()).hexdigest()}")
