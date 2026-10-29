import java.lang.reflect.*;
import java.util.*;

/** Read-only use of the installed game's own uploader validator. */
public final class NativeWorkshopCheck {
    public static void main(String[] args) throws Exception {
        // Initialize path roots only; do not start the game, scan assets or load saves.
        Class<?> fsType = Class.forName("zombie.ZomboidFileSystem");
        Object fs = fsType.getField("instance").get(null);
        Object base = fsType.getField("base").get(fs);
        base.getClass().getMethod("set", java.io.File.class).invoke(base, new java.io.File("."));
        // The uploader only accepts folders under the cache folder: use the one holding the staged copy.
        fsType.getMethod("setCacheDir", String.class).invoke(fs, args[2]);
        Class<?> type = Class.forName("zombie.core.znet.SteamWorkshopItem");
        Object item = type.getConstructor(String.class).newInstance(args[0]);
        if (!Boolean.TRUE.equals(type.getMethod("readWorkshopTxt").invoke(item)))
            throw new IllegalStateException("Could not read workshop.txt");
        Object error = type.getMethod("validateContents").invoke(item);
        if (error != null) throw new IllegalStateException("Native validator: " + error);
        for (String field : new String[] {"ID", "Title", "Visibility", "Tags", "PreviewImage", "ContentFolder"})
            System.out.println(field + ": " + type.getMethod("get" + field).invoke(item));
        String description = (String)type.getMethod("getDescription").invoke(item);
        if (!description.contains("craft with what's in your base") || description.contains("Português brasileiro"))
            throw new IllegalStateException("Expected the English-only presentation");
        if (!description.contains("3823984685"))
            throw new IllegalStateException("The description must name the Base Stock Counter requirement");
        String expectedID = args[1].isEmpty() ? null : args[1];
        if (!Objects.equals(type.getMethod("getID").invoke(item), expectedID))
            throw new IllegalStateException("Unexpected Workshop ID; do not create or overwrite another item");
        System.out.println("PASS: native Workshop content and PNG validation; English description and expected item ID.");
    }
}
