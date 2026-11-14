package dw3.linux;

import java.io.IOException;
import java.lang.reflect.InvocationTargetException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** Keeps concurrent clients in separate persistent homes without changing game code. */
public final class DesktopLauncher {
    private DesktopLauncher() {}

    public static void main(String[] args) throws Throwable {
        Path primaryHome = Path.of(System.getProperty("user.home")).toAbsolutePath().normalize();
        try (ProfileLease profile = acquireProfile(primaryHome)) {
            System.setProperty("user.home", profile.home.toString());
            try (StatePrinter printer = StatePrinter.startIfRequested();
                 ControlBridge control = ControlBridge.startIfRequested()) {
                Class<?> client = Class.forName("dw.client.ClientMain");
                try {
                    client.getMethod("main", String[].class).invoke(null, (Object) args);
                } catch (InvocationTargetException error) {
                    throw error.getCause();
                }
            }
        }
    }

    private static ProfileLease acquireProfile(Path primaryHome) throws IOException {
        for (int slot = 1; slot < Integer.MAX_VALUE; slot++) {
            Path home = slot == 1 ? primaryHome
                    : primaryHome.resolve("instances").resolve("instance-" + slot);
            ProfileLease lease = tryAcquire(home);
            if (lease != null) return lease;
        }
        throw new IOException("No free game profile is available.");
    }

    private static ProfileLease tryAcquire(Path home) throws IOException {
        Files.createDirectories(home);
        FileChannel channel = FileChannel.open(home.resolve(".linux-launcher.lock"),
                StandardOpenOption.CREATE, StandardOpenOption.WRITE);
        FileLock lock = null;
        boolean retained = false;
        try {
            lock = channel.tryLock();
            if (lock == null || !gameLockAvailable(home)) return null;
            ProfileLease lease = new ProfileLease(home, channel, lock);
            retained = true;
            return lease;
        } catch (OverlappingFileLockException busy) {
            return null;
        } finally {
            if (!retained) {
                try {
                    if (lock != null) lock.release();
                } finally {
                    channel.close();
                }
            }
        }
    }

    private static boolean gameLockAvailable(Path home) throws IOException {
        Path gameLock = home.resolve(".dw3online").resolve("aberto.lock");
        if (!Files.exists(gameLock)) return true;
        // Older launcher processes hold only this game lock, not our reservation.
        try (FileChannel channel = FileChannel.open(gameLock, StandardOpenOption.WRITE);
             FileLock lock = channel.tryLock()) {
            return lock != null;
        } catch (OverlappingFileLockException busy) {
            return false;
        }
    }

    private static final class ProfileLease implements AutoCloseable {
        private final Path home;
        private final FileChannel channel;
        private final FileLock lock;

        private ProfileLease(Path home, FileChannel channel, FileLock lock) {
            this.home = home;
            this.channel = channel;
            this.lock = lock;
        }

        @Override
        public void close() throws IOException {
            try {
                lock.release();
            } finally {
                channel.close();
            }
        }
    }
}
