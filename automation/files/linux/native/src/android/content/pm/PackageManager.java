package android.content.pm;

import java.io.IOException;
import java.io.InputStream;

/** Provides the actual signer certificate extracted from the verified APK. */
public final class PackageManager {
    public PackageInfo getPackageInfo(String name, int flags) throws IOException {
        if (!"br.com.digitalna.dw3".equals(name)) {
            throw new IllegalArgumentException("Unknown package: " + name);
        }
        try (InputStream certificate = PackageManager.class.getResourceAsStream("/dw3-apk-signer.der")) {
            if (certificate == null) {
                throw new IOException("The original APK signer certificate is missing from the bridge.");
            }
            PackageInfo info = new PackageInfo();
            info.signatures = new Signature[] {new Signature(certificate.readAllBytes())};
            return info;
        }
    }
}
