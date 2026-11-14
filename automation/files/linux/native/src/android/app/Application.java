package android.app;

import android.content.pm.PackageManager;

public final class Application {
    private final PackageManager packageManager = new PackageManager();

    public String getPackageName() {
        return "br.com.digitalna.dw3";
    }

    public PackageManager getPackageManager() {
        return packageManager;
    }
}
