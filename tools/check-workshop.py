"""Validate staged upload with installed game classes; does not contact Steam."""
from pathlib import Path
import shutil
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
game = Path(r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid")
folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Zomboid/Workshop/BSCCraftFromContainers"
# The game only reads Workshop folders under its cache folder (normally ~/Zomboid). A dry-run
# folder like .runtime/Zomboid/Workshop/BSCCraftFromContainers avoids a second copy of the mod
# in the real Zomboid folder next to a local test install.
zomboid = next((p for p in folder.resolve().parents if p.name == "Zomboid"), None)
if not zomboid:
    raise SystemExit("Stage the folder under a Zomboid folder, like <dir>/Zomboid/Workshop/BSCCraftFromContainers")
metadata = (ROOT / "workshop.txt").read_text(encoding="utf-8")
identifier = re.search(r"^id=(\d+)\s*$", metadata, re.MULTILINE)
expected_id = identifier.group(1) if identifier else ""
javac = shutil.which("javac")
if not javac:
    raise SystemExit("A host JDK with javac is required.")

def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)

with tempfile.TemporaryDirectory(prefix="bscc-workshop-", dir=ROOT) as temp:
    assert Path(temp).resolve().parent == ROOT.resolve()
    run([javac, "-encoding", "UTF-8", "-d", temp, str(ROOT / "tools/NativeWorkshopCheck.java")], ROOT)
    run([str(game / "jre64/bin/java.exe"), "-Djava.awt.headless=true", "-Dfile.encoding=UTF-8",
         "-cp", str(game / "projectzomboid.jar") + ";" + temp,
         "NativeWorkshopCheck", str(folder.resolve()), expected_id, str(zomboid)], game)
