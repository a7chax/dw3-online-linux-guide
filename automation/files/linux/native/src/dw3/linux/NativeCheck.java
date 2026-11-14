package dw3.linux;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.Charset;

/** Runs the game's own library initialization, including signature validation. */
public final class NativeCheck {
    private NativeCheck() {}

    public static void main(String[] args) throws Throwable {
        // The game uses this legacy Korean encoding when loading later assets.
        // It is supplied by jdk.charsets on the Linux JDK.
        Charset.forName("x-windows-949");
        Class<?> cofre = Class.forName("dw.client.pak.Cofre");
        Method initialize = cofre.getDeclaredMethod("a");
        initialize.setAccessible(true);
        try {
            initialize.invoke(null);
        } catch (InvocationTargetException error) {
            throw error.getCause();
        }
        System.out.println("Native library loaded; original APK signature validation passed.");
    }
}
