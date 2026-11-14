package dw3.linux;

import java.io.InputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Objects;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/** Opt-in, read-only state output for the inspected desktop client. */
public final class StatePrinter implements AutoCloseable {
    private static final String CLIENT_SHA256 =
            "7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe";
    private final ScheduledExecutorService worker;
    private final AtomicBoolean pending = new AtomicBoolean();
    private final AtomicReference<Snapshot> latest = new AtomicReference<>();
    private final AtomicReference<Exception> failure = new AtomicReference<>();
    private final Reader reader = new Reader();
    private final Path stateFile;
    private final Path historyFile;
    private Snapshot last;
    private volatile boolean closed;

    private StatePrinter() throws IOException {
        String configured = System.getenv("DW3_STATE_FILE");
        stateFile = (configured == null || configured.isBlank()
                ? Path.of(System.getProperty("user.home"), "game-state.json")
                : Path.of(configured)).toAbsolutePath().normalize();
        Files.createDirectories(stateFile.getParent());
        historyFile = stateFile.resolveSibling("state-events.jsonl");
        worker = Executors.newSingleThreadScheduledExecutor(task -> {
            Thread thread = new Thread(task, "dw3-state-printer");
            thread.setDaemon(true);
            return thread;
        });
        worker.scheduleWithFixedDelay(this::scheduleSample, 0, 100, TimeUnit.MILLISECONDS);
    }

    static StatePrinter startIfRequested() {
        if (!"1".equals(System.getenv("DW3_PRINT_STATE"))) return null;
        try {
            Class<?> client = Class.forName("dw.client.ClientMain", false,
                    StatePrinter.class.getClassLoader());
            Path jar = Path.of(client.getProtectionDomain().getCodeSource().getLocation().toURI());
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = Files.newInputStream(jar)) {
                byte[] buffer = new byte[65536];
                int count;
                while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
            }
            if (!CLIENT_SHA256.equals(HexFormat.of().formatHex(digest.digest()))) {
                throw new IllegalStateException("Unsupported client version; expected the inspected 0.1.95 JAR.");
            }
            return new StatePrinter();
        } catch (Exception error) {
            System.err.println("DW3_STATE_ERROR: " + error.getMessage());
            return null;
        }
    }

    private void scheduleSample() {
        if (closed) return;
        Exception error = failure.getAndSet(null);
        if (error != null) {
            reportFailure(error);
            return;
        }
        Snapshot state = latest.getAndSet(null);
        if (state != null) {
            try {
                emit(state);
            } catch (IOException outputError) {
                reportFailure(outputError);
                return;
            }
        }
        if (closed || !pending.compareAndSet(false, true)) return;
        try {
            Class<?> gdx = Class.forName("com.badlogic.gdx.Gdx");
            Object application = gdx.getField("app").get(null);
            if (application == null) {
                latest.set(reader.readScreen(null));
                pending.set(false);
                return;
            }
            // LibGDX executes this callback on its render thread. No game fields
            // are inspected from the scheduler thread, and only one request queues.
            application.getClass().getMethod("postRunnable", Runnable.class).invoke(application,
                    (Runnable) () -> {
                        try {
                            if (closed) return;
                            Object listener = application.getClass().getMethod("getApplicationListener")
                                    .invoke(application);
                            Object screen = listener == null ? null
                                    : listener.getClass().getMethod("getScreen").invoke(listener);
                            // Only this bounded handoff runs on the render thread.
                            // Terminal output can block the worker, never the game.
                            latest.set(reader.readScreen(screen));
                        } catch (Exception readError) {
                            failure.set(readError);
                        } finally {
                            pending.set(false);
                        }
                    });
        } catch (Exception sampleError) {
            pending.set(false);
            failure.set(sampleError);
        }
    }

    private synchronized void emit(Snapshot state) throws IOException {
        if (closed) return;
        String json = state.toJson();
        Path temporary = Files.createTempFile(stateFile.getParent(), ".state-", ".tmp");
        try {
            Files.writeString(temporary, json + "\n");
            Files.move(temporary, stateFile, StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
        } finally {
            Files.deleteIfExists(temporary);
        }
        if (!state.equals(last)) {
            Files.writeString(historyFile, json + "\n", StandardOpenOption.CREATE,
                    StandardOpenOption.APPEND);
            System.out.println("DW3_STATE " + json);
            last = state;
        }
    }

    private void reportFailure(Exception error) {
        System.err.println("DW3_STATE_ERROR: Cannot read this client state: "
                + error.getClass().getSimpleName() + ": " + error.getMessage());
        close();
    }

    @Override
    public void close() {
        closed = true;
        worker.shutdownNow();
    }

    static final class Reader {
        private Object previousScreen;
        private String previousMap;
        private float previousX;
        private float previousY;

        Snapshot readScreen(Object screen) throws Exception {
            String name = screen == null ? null : screen.getClass().getName();
            if (!"aj".equals(name)) {
                previousScreen = null;
                String phase = name == null ? "starting" : switch (name) {
                    case "a" -> "login";
                    case "r" -> "character_selection";
                    default -> "other_screen";
                };
                return Snapshot.withoutPosition(phase, name);
            }
            Object mapObject = field(screen, "av");
            if (mapObject == null) {
                previousScreen = null;
                return Snapshot.withoutPosition("loading_map", name);
            }
            Method mapIdentifier = mapObject.getClass().getDeclaredMethod("a");
            mapIdentifier.setAccessible(true);
            String map = (String) mapIdentifier.invoke(mapObject);
            float x = (Float) field(screen, "ax");
            float y = (Float) field(screen, "ay");
            int facing = (Integer) field(screen, "az");
            if (!Float.isFinite(x) || !Float.isFinite(y)) {
                throw new IllegalStateException("Non-finite player coordinates.");
            }
            Boolean moving = previousScreen == screen && Objects.equals(previousMap, map)
                    ? Math.abs(x - previousX) > 0.0001f || Math.abs(y - previousY) > 0.0001f
                    : null;
            previousScreen = screen;
            previousMap = map;
            previousX = x;
            previousY = y;
            return new Snapshot("world", name, map, x, y,
                    (int) Math.floor(x), (int) Math.floor(y), moving, facing,
                    trace(field(screen, "cG"), x, y),quest(field(screen,"cG")));
        }

        private static String quest(Object gps) throws Exception {
            Object progress=field(gps,"f");
            if(progress==null)return null;
            // Exact accessors of the inspected bI.bG progress packet. The
            // objective text comes from the same formatter used by the HUD.
            return "{\"chapter\":"+call(progress,"a",new Class<?>[0])
                    +",\"chapter_count\":"+call(progress,"b",new Class<?>[0])
                    +",\"target_map\":"+Snapshot.json(call(progress,"c",new Class<?>[0]))
                    +",\"action_code\":"+call(progress,"d",new Class<?>[0])
                    +",\"progress_value_f\":"+call(progress,"f",new Class<?>[0])
                    +",\"step\":"+call(progress,"g",new Class<?>[0])
                    +",\"step_count\":"+call(progress,"h",new Class<?>[0])
                    +",\"objective_text\":"+Snapshot.json(call(gps,"x",new Class<?>[0]))+"}";
        }

        // These inspected GPS accessors only read the current server route.
        // Never call al.a(x,y,e): that method advances the game's auto-walk cursor.
        private static String trace(Object gps, float x, float y) throws Exception {
            boolean enabled = (Boolean) call(gps, "a", new Class<?>[0]);
            boolean automatic = (Boolean) call(gps, "b", new Class<?>[0]);
            int type = (Integer) call(gps, "f", new Class<?>[0]);
            int steps = (Integer) call(gps, "b", new Class<?>[]{float.class,float.class}, x,y);
            float[] points = (float[]) call(gps, "c", new Class<?>[]{float.class,float.class,float.class}, x,y,7f);
            StringBuilder json = new StringBuilder("{\"enabled\":"+enabled
                    +",\"auto_walk\":"+automatic+",\"route_type\":"+type
                    +",\"steps_remaining\":"+steps+",\"points\":[");
            for (int index=0; index+1<Math.min(points.length,4096); index+=2) {
                if (!Float.isFinite(points[index]) || !Float.isFinite(points[index+1]))
                    throw new IllegalStateException("Non-finite GPS coordinates");
                if(index>0)json.append(',');
                json.append('[').append(points[index]).append(',').append(points[index+1]).append(']');
            }
            return json.append("]}").toString();
        }

        private static Object call(Object target,String name,Class<?>[] types,Object...args) throws Exception {
            Method method=target.getClass().getDeclaredMethod(name,types);
            method.setAccessible(true);return method.invoke(target,args);
        }

        private static Object field(Object object, String name) throws Exception {
            Field field = object.getClass().getDeclaredField(name);
            field.setAccessible(true);
            return field.get(object);
        }
    }

    record Snapshot(String phase, String screen, String map, Float x, Float y,
                    Integer tileX, Integer tileY, Boolean moving, Integer facing, String trace, String mainQuest) {
        static Snapshot withoutPosition(String phase, String screen) {
            return new Snapshot(phase, screen, null, null, null, null, null, null, null, null, null);
        }

        String toJson() {
            return "{\"time\":" + json(Instant.now().toString())
                    + ",\"pid\":" + ProcessHandle.current().pid()
                    + ",\"profile\":" + json(System.getProperty("user.home"))
                    + ",\"phase\":" + json(phase) + ",\"screen\":" + json(screen)
                    + ",\"map\":" + json(map) + ",\"x\":" + json(x) + ",\"y\":" + json(y)
                    + ",\"tile_x\":" + json(tileX) + ",\"tile_y\":" + json(tileY)
                    + ",\"moving\":" + json(moving) + ",\"facing\":" + json(facing)
                    + ",\"trace\":" + (trace == null ? "null" : trace)
                    + ",\"main_quest\":" + (mainQuest == null ? "null" : mainQuest)+ "}";
        }

        private static String json(Object value) {
            if (value == null) return "null";
            if (value instanceof Number || value instanceof Boolean) return value.toString();
            StringBuilder output = new StringBuilder("\"");
            for (char character : value.toString().toCharArray()) {
                switch (character) {
                    case '"' -> output.append("\\\"");
                    case '\\' -> output.append("\\\\");
                    case '\n' -> output.append("\\n");
                    case '\r' -> output.append("\\r");
                    case '\t' -> output.append("\\t");
                    default -> {
                        if (character < 32) output.append(String.format("\\u%04x", (int) character));
                        else output.append(character);
                    }
                }
            }
            return output.append('"').toString();
        }
    }
}
