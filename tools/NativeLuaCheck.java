import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Uses reflection so a host JDK can compile against its own standard library.
 * Execution uses the installed game's Java runtime and its actual Kahlua compiler. */
public final class NativeLuaCheck {
    static Object env, thread;
    static Method compile, call;

    static void execute(String source, String name) throws Exception {
        Object closure = compile.invoke(null, source, name, env);
        Object[] result = (Object[]) call.invoke(thread, closure, new Object[0]);
        if (!Boolean.TRUE.equals(result[0])) {
            var match = java.util.regex.Pattern.compile(":(\\d+)").matcher(Arrays.toString(result));
            if (match.find()) {
                int line = Integer.parseInt(match.group(1));
                var lines = source.lines().toList();
                for (int i=Math.max(0,line-3); i<Math.min(lines.size(),line+2); i++)
                    System.err.println((i+1) + ": " + lines.get(i));
            }
            throw new AssertionError(name + ": " + Arrays.toString(result));
        }
    }

    static void method(String type, String name, Class<?>... parameters) throws Exception {
        Class.forName(type).getMethod(name, parameters);
    }

    public static void main(String[] args) throws Exception {
        Path root = Paths.get(args[0]);
        Path lua = root.resolve("Contents/mods/BSCCraftFromContainers/42/media/lua");
        Class<?> platformType = Class.forName("se.krka.kahlua.vm.Platform");
        Class<?> tableType = Class.forName("se.krka.kahlua.vm.KahluaTable");
        Class<?> platformClass = Class.forName("se.krka.kahlua.j2se.J2SEPlatform");
        Object platform = platformClass.getMethod("getInstance").invoke(null);
        env = platformClass.getMethod("newEnvironment").invoke(platform);
        Class<?> threadClass = Class.forName("se.krka.kahlua.vm.KahluaThread");
        thread = threadClass.getConstructor(platformType, tableType).newInstance(platform, env);
        threadClass.getField("debugOwnerThread").set(thread, Thread.currentThread());
        compile = Class.forName("se.krka.kahlua.luaj.compiler.LuaCompiler")
            .getMethod("loadstring", String.class, String.class, tableType);
        call = threadClass.getMethod("pcall", Object.class, Object[].class);

        StringBuilder preload = new StringBuilder("local modules,cache={},{}\nfunction require(n) if cache[n]~=nil then return cache[n] end assert(modules[n], n); cache[n]=modules[n](); return cache[n] end\n");
        int files = 0;
        try (var stream = Files.walk(lua)) {
            for (Path path : stream.filter(p -> p.toString().endsWith(".lua")).sorted().toList()) {
                String source = Files.readString(path, StandardCharsets.UTF_8);
                compile.invoke(null, source, path.toString(), env);
                String relative = lua.relativize(path).toString().replace('\\', '/');
                String module = relative.substring(relative.indexOf('/') + 1).replaceAll("\\.lua$", "");
                preload.append("modules[\"").append(module).append("\"]=function()\n").append(source).append("\nend\n");
                files++;
            }
        }
        System.out.println("Native Kahlua compilation: " + files + " Lua files OK");
        String fixture = Files.readString(root.resolve("tests/fixtures.lua"), StandardCharsets.UTF_8);
        int tests = 0;
        try (var stream = Files.list(Paths.get(args[1]))) {
            for (Path test : stream.filter(p -> p.toString().endsWith(".lua")).sorted().toList()) {
                // Each test gets a fresh environment and module cache.
                env = platformClass.getMethod("newEnvironment").invoke(platform);
                thread = threadClass.getConstructor(platformType, tableType).newInstance(platform, env);
                threadClass.getField("debugOwnerThread").set(thread, Thread.currentThread());
                execute(preload + fixture + "\n" + Files.readString(test, StandardCharsets.UTF_8), test.getFileName().toString());
                System.out.println("PASS " + test.getFileName());
                tests++;
            }
        }
        // Verify the exact local signatures the mod calls; online Javadocs lag behind Build 42.
        Class<?> character = Class.forName("zombie.characters.IsoGameCharacter");
        Class<?> player = Class.forName("zombie.characters.IsoPlayer");
        Class<?> square = Class.forName("zombie.iso.IsoGridSquare");
        method("zombie.iso.IsoCell", "getChunkForGridSquare", int.class, int.class, int.class);
        method("zombie.iso.IsoCell", "getGridSquare", int.class, int.class, int.class);
        for (String name : List.of("getLoadID", "getMinLevel", "getMaxLevel")) method("zombie.iso.IsoChunk", name);
        method("zombie.iso.IsoChunk", "getGridSquare", int.class, int.class, int.class);
        for (String name : List.of("getObjects", "getBuilding", "getX", "getY", "getZ")) method("zombie.iso.IsoGridSquare", name);
        for (String name : List.of("getSquare", "getObjectIndex", "getContainerCount")) method("zombie.iso.IsoObject", name);
        method("zombie.iso.IsoObject", "getContainerByIndex", int.class);
        Class<?> container = Class.forName("zombie.inventory.ItemContainer");
        Class<?> item = Class.forName("zombie.inventory.InventoryItem");
        for (String name : List.of("isExplored", "getParent", "getOutermostContainer", "getType"))
            method("zombie.inventory.ItemContainer", name);
        method("zombie.inventory.ItemContainer", "getItemWithID", int.class);
        method("zombie.inventory.ItemContainer", "containsID", int.class);
        method("zombie.inventory.ItemContainer", "Remove", item);
        method("zombie.inventory.ItemContainer", "AddItem", item);
        method("zombie.inventory.ItemContainer", "isItemAllowed", item);
        method("zombie.inventory.ItemContainer", "hasRoomFor", character, item);
        method("zombie.inventory.ItemContainer", "hasRoomFor", character, float.class);
        for (String name : List.of("getID", "getContainer", "isFavorite", "getUnequippedWeight")) method("zombie.inventory.InventoryItem", name);
        method("zombie.iso.IsoObject", "getContainerIndex", container);
        method("zombie.iso.objects.IsoThumpable", "isLockedToCharacter", character);
        method("zombie.iso.areas.SafeHouse", "getSafeHouse", square);
        method("zombie.iso.areas.SafeHouse", "playerAllowed", player);
        method("zombie.iso.areas.SafeHouse", "isSafehouseAllowLoot", square, player);
        method("zombie.characters.IsoGameCharacter", "setHaloNote", String.class, int.class, int.class, int.class, float.class);
        method("zombie.characters.IsoGameCharacter", "getCurrentSquare");
        method("zombie.characters.IsoGameCharacter", "getInventory");
        method("zombie.characters.IsoGameCharacter", "isEquipped", item);
        method("zombie.characters.IsoGameCharacter", "hasTrait", Class.forName("zombie.scripting.objects.CharacterTrait"));
        Class<?> logic = Class.forName("zombie.entity.components.crafting.recipe.HandcraftLogic");
        logic.getConstructor(character, Class.forName("zombie.entity.components.crafting.CraftBench"), Class.forName("zombie.iso.IsoObject"));
        logic.getMethod("setContainers", ArrayList.class);
        logic.getMethod("setRecipe", Class.forName("zombie.scripting.entity.components.crafting.CraftRecipe"));
        logic.getMethod("setTargetVariableInputRatio", float.class);
        logic.getMethod("canPerformCurrentRecipe");
        logic.getMethod("getRecipeData");
        method("zombie.entity.components.crafting.recipe.CraftRecipeData", "getAllInputItems");
        method("zombie.Lua.LuaManager$GlobalObject", "getChunkSizeInSquares");
        method("zombie.Lua.LuaManager$GlobalObject", "sendServerCommand", player, String.class, String.class, tableType);
        method("zombie.Lua.LuaManager$GlobalObject", "sendClientCommand", player, String.class, String.class, tableType);
        method("zombie.Lua.LuaManager$GlobalObject", "sendAddItemToContainer", container, item);
        method("zombie.Lua.LuaManager$GlobalObject", "sendRemoveItemFromContainer", container, item);
        System.out.println("Local API signatures OK; " + tests + " native Kahlua logic tests passed.");
    }
}
