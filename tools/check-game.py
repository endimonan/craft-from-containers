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

# The vanilla Lua the mod wraps or calls. A game update that renames or moves one of these turns
# the matching part of the mod off; this names it.
VANILLA = {
    "client/Entity/ISUI/CraftRecipe/ISHandCraftPanel.lua": ["function ISHandCraftPanel:updateContainers("],
    "client/Entity/ISUI/CraftRecipe/ISWidgetHandCraftControl.lua": ["function ISWidgetHandCraftControl:startHandcraft("],
    "client/Entity/ISUI/Components/Crafting/ISCraftBenchPanel.lua": ["ISXuiSkin.build(self.xuiSkin, nil, ISHandCraftPanel,"],
    "client/ISUI/ISCraftingUI.lua": ["function ISCraftingUI.ReturnItemsToOriginalContainer(playerObj, items)"],
    "client/ISUI/ISInventoryPaneContextMenu.lua": [
        "ISInventoryPaneContextMenu.getContainers = function(character)",
        "function ISInventoryPaneContextMenu.transferIfNeeded(playerObj, item",
        "ISInventoryPaneContextMenu.addNewCraftingDynamicalContextMenu = function(",
        "ISInventoryPaneContextMenu.OnNewCraft = function(",
        "function ISInventoryPaneContextMenu.doEvorecipeMenu(context, items, player, evorecipe, baseItem, containerList)",
        "ISInventoryPaneContextMenu.onAddItemInEvoRecipe = function(recipe, baseItem, usedItem, player)",
    ],
    "client/TimedActions/ISTimedActionQueue.lua": ["ISTimedActionQueue.add = function(action)"],
    "shared/TimedActions/ISInventoryTransferUtil.lua": [
        "function ISInventoryTransferUtil.newInventoryTransferAction(character, item, srcContainer, destContainer, time)",
    ],
    "shared/Entity/TimedActions/ISHandcraftAction.lua": [
        "function ISHandcraftAction:start()", "function ISHandcraftAction:perform()", "function ISHandcraftAction:stop()",
        "function ISHandcraftAction:new(character, craftRecipe, containers, isoObject, craftBench, manualInputs, items, recipeItem, variableInputRatio, eatPercentage)",
    ],
    "shared/TimedActions/ISAddItemInRecipe.lua": [
        "function ISAddItemInRecipe:isValidStart()", "function ISAddItemInRecipe:start()",
        "function ISAddItemInRecipe:perform()", "function ISAddItemInRecipe:stop()",
        "function ISAddItemInRecipe:new(character, recipe, baseItem, usedItem)",
    ],
}
for relative, snippets in VANILLA.items():
    source = (game / "media/lua" / relative).read_text(encoding="utf-8", errors="replace")
    for snippet in snippets:
        if snippet not in source:
            raise SystemExit(f"Vanilla Lua changed: {relative} lacks {snippet!r}")
print(f"Vanilla Lua entry points OK ({sum(map(len, VANILLA.values()))} definitions)")
