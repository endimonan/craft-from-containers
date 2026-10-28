"""Compile/test with the installed game's Kahlua; uses hidden child processes."""
import ast
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
game = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid")
javac = shutil.which("javac")
if not javac:
    # Same installed toolchain as javap/java on PATH.
    java = shutil.which("java")
    javac = str(Path(java).with_name("javac.exe")) if java else None
if not javac or not Path(javac).is_file():
    raise SystemExit("A host JDK with javac is required.")

with tempfile.TemporaryDirectory(prefix="bscc-kahlua-", dir=ROOT) as temp:
    destination = Path(temp)
    assert destination.resolve().parent == ROOT.resolve()
    tree = ast.parse((ROOT / "tests/run.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_") and node.name != "test_lua51_syntax_and_translations":
            snippets = []
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "check":
                    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
                        snippets.append(call.args[0].value)
            if snippets:
                (destination / f"{node.name}.lua").write_text("\n".join(snippets), encoding="utf-8")
    def run(command, cwd=ROOT):
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print(result.stdout, end="")
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            raise SystemExit(result.returncode)
    run([javac, "-d", temp, str(ROOT / "tools/NativeLuaCheck.java")])
    run([str(game / "jre64/bin/java.exe"), "-Djava.awt.headless=true", "-cp", str(game / "projectzomboid.jar") + ";" + temp, "NativeLuaCheck", str(ROOT), temp], cwd=game)
