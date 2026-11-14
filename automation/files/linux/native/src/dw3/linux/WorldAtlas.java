package dw3.linux;

import com.google.gson.*;
import java.lang.reflect.Method;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;

/** Read map metadata through the original client's already-unlocked asset reader. */
public final class WorldAtlas {
    private static final Gson JSON=new GsonBuilder().setPrettyPrinting().create();
    private WorldAtlas() {}

    public static JsonObject export(Object assets,Path output)throws Exception {
        Object directory=call(assets,"child",new Class<?>[]{String.class},"maps");
        Object[] entries=(Object[])call(directory,"list",new Class<?>[0]);
        if(entries.length==0)throw new IllegalStateException("No unlocked map assets; log in first");
        Files.createDirectories(output);
        JsonObject atlas=new JsonObject();atlas.addProperty("schema",1);
        atlas.addProperty("exported_at",Instant.now().toString());
        atlas.addProperty("client_version","0.1.95");
        atlas.addProperty("source","original logged-in client asset reader");
        atlas.addProperty("coordinate_system","per-map world pixels; origin top-left; x right; y down");
        JsonArray maps=new JsonArray(),failures=new JsonArray();
        Arrays.sort(entries,Comparator.comparing(entry->{try{return (String)call(entry,"name",new Class<?>[0]);}catch(Exception e){throw new IllegalStateException(e);}}));
        int directories=0;
        for(Object entry:entries) {
            String id=(String)call(entry,"name",new Class<?>[0]);
            if(!(Boolean)call(entry,"isDirectory",new Class<?>[0]))continue;
            directories++;
            if(!id.matches("[A-Za-z0-9_-]+")){failures.add("Invalid map identifier");continue;}
            try {
                Object metadata=call(entry,"child",new Class<?>[]{String.class},"map.json");
                JsonObject raw=JsonParser.parseString((String)call(metadata,"readString",new Class<?>[0])).getAsJsonObject();
                int width=raw.get("width").getAsInt(),height=raw.get("height").getAsInt();
                if(width<=0 || height<=0)throw new IllegalArgumentException("Invalid map dimensions");
                Path mapDir=output.resolve("maps").resolve(id);Files.createDirectories(mapDir);
                String prefix="maps/"+id+"/";
                write(mapDir.resolve("metadata.json"),JSON.toJson(raw).getBytes(StandardCharsets.UTF_8));
                JsonObject map=new JsonObject();map.addProperty("id",id);
                map.addProperty("name",raw.has("room")?raw.get("room").getAsString():id);
                map.addProperty("width",width);map.addProperty("height",height);
                map.addProperty("metadata",prefix+"metadata.json");
                if(raw.has("place"))map.add("place",raw.get("place"));
                if(raw.has("collision") && !raw.get("collision").isJsonNull()) {
                    Object collision=call(entry,"child",new Class<?>[]{String.class},raw.get("collision").getAsString());
                    byte[] bytes=(byte[])call(collision,"readBytes",new Class<?>[0]);
                    write(mapDir.resolve("collision.png"),bytes);
                    map.addProperty("collision",prefix+"collision.png");
                    map.addProperty("collision_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
                }
                maps.add(map);
            } catch(Exception error) {failures.add(id+": "+error.getClass().getSimpleName());}
        }
        atlas.addProperty("map_directories",directories);atlas.add("maps",maps);atlas.add("failures",failures);
        atlas.addProperty("coverage",failures.isEmpty()?"all map directories visible to this client":"partial");
        atlas.addProperty("exit_connections","not inferred from map metadata; server transitions need separate evidence");
        JsonObject auxiliary=new JsonObject();
        for(String name:new String[]{"npcs.json","worldmap/world.json"}) {
            Object resource=call(assets,"child",new Class<?>[]{String.class},name);
            if((Boolean)call(resource,"exists",new Class<?>[0])) {
                Path destination=output.resolve("auxiliary").resolve(name);
                Files.createDirectories(destination.getParent());
                write(destination,(byte[])call(resource,"readBytes",new Class<?>[0]));
                auxiliary.addProperty(name,"auxiliary/"+name);
            }
        }
        atlas.add("auxiliary",auxiliary);
        write(output.resolve("atlas.json"),JSON.toJson(atlas).getBytes(StandardCharsets.UTF_8));
        JsonObject result=new JsonObject();result.addProperty("path",output.resolve("atlas.json").toAbsolutePath().toString());
        result.addProperty("maps",maps.size());result.addProperty("failures",failures.size());return result;
    }

    private static Object call(Object target,String name,Class<?>[] types,Object...args)throws Exception {
        Method method=target.getClass().getMethod(name,types);method.setAccessible(true);return method.invoke(target,args);
    }
    private static void write(Path path,byte[] bytes)throws Exception {
        Path temporary=Files.createTempFile(path.getParent(),".atlas-",".tmp");
        try {Files.write(temporary,bytes);Files.move(temporary,path,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
        finally {Files.deleteIfExists(temporary);}
    }
}
