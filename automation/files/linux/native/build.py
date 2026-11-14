#!/usr/bin/env python3
"""Adapt the known APK's x86_64 JNI library for the existing desktop client.

Only ELF dynamic-linker metadata changes. Native instructions, asset handling,
certificate validation, and cryptographic operations remain in the original code.
"""
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
APK_SHA256 = "e1865b79e6af7d6fde18568221d15edddaf419a6d137e0f77ec01e1eca685baa"
LIB_SHA256 = "62b7987c1568999053618cf26a8f5f564a6aadd1f746d97ccf61817fe1a0e120"
CERT_SHA256 = "5335bc451e542043cea6996de0baf8a882e6c165aa2004fce248bb8de8410d85"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def length_prefixed(blob, position=0):
    require(position + 4 <= len(blob), "Truncated APK signing block.")
    size = struct.unpack_from("<I", blob, position)[0]
    end = position + 4 + size
    require(end <= len(blob), "Invalid APK signing block length.")
    return blob[position + 4:end], end


def signer_certificate(apk):
    eocd = apk.rfind(b"PK\x05\x06")
    require(eocd >= 0, "APK ZIP directory not found.")
    directory = struct.unpack_from("<I", apk, eocd + 16)[0]
    require(apk[directory - 16:directory] == b"APK Sig Block 42", "APK signing block not found.")
    size = struct.unpack_from("<Q", apk, directory - 24)[0]
    position = directory - size
    while position < directory - 24:
        pair_size, identity = struct.unpack_from("<QI", apk, position)
        require(pair_size >= 4 and position + 8 + pair_size <= directory - 24,
                "Invalid APK signing block pair.")
        if identity == 0x7109871A:
            signers, _ = length_prefixed(apk[position + 12:position + 8 + pair_size])
            signer, end = length_prefixed(signers)
            require(end == len(signers), "Expected exactly one APK signer.")
            signed_data, _ = length_prefixed(signer)
            _, offset = length_prefixed(signed_data)
            certificates, _ = length_prefixed(signed_data, offset)
            certificate, _ = length_prefixed(certificates)
            return certificate
        position += 8 + pair_size
    raise SystemExit("APK v2 signature not found.")


def adapt_library(original):
    require(original[:6] == b"\x7fELF\x02\x01", "Expected little-endian ELF64.")
    require(struct.unpack_from("<H", original, 18)[0] == 62, "Expected x86_64 library.")
    data = bytearray(original)
    headers = struct.unpack_from("<Q", data, 32)[0]
    entry_size, count = struct.unpack_from("<HH", data, 54)
    for index in range(count):
        header = headers + index * entry_size
        if struct.unpack_from("<I", data, header)[0] == 2:  # PT_DYNAMIC
            start = struct.unpack_from("<Q", data, header + 8)[0]
            size = struct.unpack_from("<Q", data, header + 32)[0]
            break
    else:
        raise SystemExit("ELF dynamic section not found.")
    entries = []
    removed = []
    for offset in range(start, start + size, 16):
        tag, value = struct.unpack_from("<QQ", data, offset)
        if tag == 0:
            break
        # libc is already loaded by the JVM. These Android library names and
        # LIBC symbol-version requests do not exist in desktop glibc.
        if tag in (1, 0x6FFFFFF0, 0x6FFFFFFE, 0x6FFFFFFF):
            removed.append(tag)
        else:
            entries.append((tag, value))
    require(removed.count(1) == 2, "Unexpected native dependency list.")
    encoded = b"".join(struct.pack("<QQ", *entry) for entry in entries)
    data[start:start + size] = encoded + b"\0" * (size - len(encoded))
    require(data[:start] == original[:start] and data[start + size:] == original[start + size:],
            "Unexpected change outside ELF dynamic metadata.")
    return bytes(data)


def main():
    apk_path = ROOT / "DW3-Online.apk"
    require(apk_path.is_file(), "Place DW3-Online.apk in the game directory.")
    apk = apk_path.read_bytes()
    require(hashlib.sha256(apk).hexdigest() == APK_SHA256,
            "This adapter supports only the inspected APK version 0.1.95 (10095).")
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))
    apksigner = shutil.which("apksigner")
    if not apksigner:
        candidates = sorted((sdk / "build-tools").glob("*/apksigner"))
        require(candidates, "Install Android SDK Build Tools to verify the original APK signature.")
        apksigner = str(candidates[-1])
    subprocess.run([apksigner, "verify", str(apk_path)], check=True)
    certificate = signer_certificate(apk)
    require(hashlib.sha256(certificate).hexdigest() == CERT_SHA256,
            "Unexpected APK signer certificate.")
    with zipfile.ZipFile(apk_path) as archive:
        original = archive.read("lib/x86_64/libdwcofre.so")
    require(hashlib.sha256(original).hexdigest() == LIB_SHA256,
            "Unexpected APK native library.")
    adapted = adapt_library(original)
    output = ROOT / "linux/lib"
    output.mkdir(parents=True, exist_ok=True)
    sources = sorted((Path(__file__).parent / "src").rglob("*.java"))
    # Publish new files atomically so an existing game can keep its mapped files.
    with tempfile.TemporaryDirectory(prefix=".dw3-linux-build-", dir=output) as temporary:
        classes = Path(temporary) / "classes"
        classes.mkdir()
        subprocess.run(["javac", "--release", "17", "-cp", str(ROOT / "app/gson-2.11.0.jar"), "-d", str(classes),
                        *map(str, sources)], check=True)
        (classes / "dw3-apk-signer.der").write_bytes(certificate)
        bridge = Path(temporary) / "dw3-android-bridge.jar"
        subprocess.run(["jar", "--create", "--file", str(bridge),
                        "-C", str(classes), "."], check=True)
        native = Path(temporary) / "libdwcofre.so"
        native.write_bytes(adapted)
        os.replace(native, output / "libdwcofre.so")
        os.replace(bridge, output / "dw3-android-bridge.jar")
    print("Built native Linux adapter; original native machine code is unchanged.")
    print("APK signature verified; original signer certificate bundled in Java bridge.")


if __name__ == "__main__":
    main()
