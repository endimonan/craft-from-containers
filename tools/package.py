"""Prepare a review archive. No Steam/GitHub publication or game installation."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MOD = "BSCCraftFromContainers"
version = re.search(r"^modversion=(\S+)$", (ROOT / f"Contents/mods/{MOD}/42/mod.info").read_text(encoding="utf-8"), re.MULTILINE).group(1)
files = sorted(p for p in (ROOT / "Contents").rglob("*") if p.is_file())
files += [ROOT / name for name in ("preview.png", "workshop.txt", "README.md", "LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md")]
files += sorted(p for p in (ROOT / "docs").rglob("*") if p.is_file())
for file in files:
    if not file.is_file():
        raise SystemExit(f"Missing package file: {file}")
manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
destination = ROOT / "dist"
destination.mkdir(exist_ok=True)
output = destination / f"{MOD}-{version}-review.zip"
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for file in files:
        archive.write(file, f"{MOD}/" + file.relative_to(ROOT).as_posix())
    archive.writestr(f"{MOD}/SHA256.json", json.dumps(manifest, indent=2) + "\n")
print(output)
print(f"{len(files)} files; {output.stat().st_size} bytes; SHA256 {hashlib.sha256(output.read_bytes()).hexdigest()}")
