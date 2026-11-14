package android.app;

/** Supplies the application object requested by the original JNI library. */
public final class ActivityThread {
    private static final Application APPLICATION = new Application();

    private ActivityThread() {}

    public static Application currentApplication() {
        return APPLICATION;
    }
}
