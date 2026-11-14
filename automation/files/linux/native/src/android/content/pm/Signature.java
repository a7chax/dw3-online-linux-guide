package android.content.pm;

public final class Signature {
    private final byte[] certificate;

    public Signature(byte[] certificate) {
        this.certificate = certificate.clone();
    }

    public byte[] toByteArray() {
        return certificate.clone();
    }
}
