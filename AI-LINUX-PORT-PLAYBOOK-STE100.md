# AI Replication Instructions: Native Linux Port of DW3 Online

## 1. How to Use This Document

Give this complete document to the other AI.
Supply the original Windows package and the original APK.
The AI does not need the previous conversation or the existing port files.
Appendix A contains the source files that the AI must create.

This document uses ASD-STE100 Issue 9 style.
Technical names and code retain their exact forms.
No automated STE dictionary check was available.

## 2. Task for the AI

Act as the engineer who must reproduce this native Linux port.
Start with the original Windows package and `DW3-Online.apk`.
Use REA to examine the supplied artifacts.
Use the desktop Java client for the final application.
Use the matching native library from the APK.
Create a Linux executable with an included Java runtime.

Do not use Wine, Proton, Waydroid, or an Android emulator for the final application.
Do not change the original Windows files or the APK.
Do not extract private keys or change the certificate checks.
Do not claim gameplay success from a successful startup test.

Continue through the build and the verification steps.
Report a specific missing prerequisite if a step cannot proceed.
Do not stop after an investigation when the required tools and files are available.

## 3. Required Inputs and Environment

Use the following inputs.

| Input | Requirement |
| --- | --- |
| Windows package | DW3 Online desktop client version 0.1.95. |
| APK | DW3 Online version 0.1.95, version code 10095. |
| Host | Linux x86_64 with glibc and a graphical desktop. |
| Java build tools | JDK 21 with `java`, `javac`, `jar`, and `jlink`. |
| Other build tools | Python 3, Bash, GCC, and standard ELF inspection tools. |
| Android tools | Android SDK Build Tools with `aapt` and `apksigner`. |
| REA | APK archive inspection and native analysis through Hopper. |

The tested host was Ubuntu 26.04.1 LTS.
Other hosts require their own verification.
Android Studio and an Android system image are not build requirements.

Use these identities for the supplied version.

| Artifact | SHA-256 |
| --- | --- |
| `DW3-Online.apk` | `e1865b79e6af7d6fde18568221d15edddaf419a6d137e0f77ec01e1eca685baa` |
| `app/client.jar` | `7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe` |
| APK `lib/x86_64/libdwcofre.so` | `62b7987c1568999053618cf26a8f5f564a6aadd1f746d97ccf61817fe1a0e120` |
| Public signer certificate | `5335bc451e542043cea6996de0baf8a882e6c165aa2004fce248bb8de8410d85` |

If an input hash differs, examine that version before use.
Do not replace the expected hashes merely to force a build.

## 4. Procedure for the AI

### Step 1. Prepare a Separate Workspace

1. Extract the Windows package into a writable game directory.
2. Put `DW3-Online.apk` in that directory.
3. Record the original file hashes.
4. Read the applicable `AGENTS.md` instructions.
5. Confirm the host architecture.
6. Confirm the available tools.

Use the following commands as inspection examples.

```bash
uname -m
java -version
javac -version
jlink --version
command -v gcc python3 readelf nm
sha256sum DW3-Online.apk app/client.jar
cat "app/DW3 Online.cfg"
cat runtime/release
```

The original entry point is `dw.client.ClientMain`.
The original Windows Java runtime is not suitable for Linux.

### Step 2. Reproduce the Original Linux Failure

1. Create a separate Java home directory inside the workspace.
2. Start the desktop client with Linux Java.
3. Record the complete error output.

```bash
mkdir -p .linux-home
java -Duser.home="$PWD/.linux-home" -XX:+DisableAttachMechanism \
    -cp 'app/*' dw.client.ClientMain
```

The inspected package first failed because `liblwjgl.so` was absent.
This is evidence of missing Linux native dependencies.
A display failure can also occur inside a restricted execution environment.
Use the permitted graphical session for the graphical test.
Do not treat a sandbox display restriction as a defect in the game.

### Step 3. Inspect the APK with REA

1. Discover the available REA tools and their input schemas.
2. Open the APK with `open_binary`.
3. Examine its archive inventory with `inspect_artifact`.
4. Find `lib/x86_64/libdwcofre.so` in that inventory.
5. Save the evidence identifier and the artifact hash.

Use absolute paths in REA calls.
The following examples show the intended operations.
Use the exact schemas advertised by the connected server.

```json
{"tool":"open_binary","arguments":{"path":"/absolute/path/DW3-Online.apk"}}
{"tool":"inspect_artifact","arguments":{}}
```

6. Read the APK manifest with `inspect_android_package`, if that capability is available.
7. If JADX is unavailable, use Android SDK `aapt` for manifest inspection.
8. Record the package name, version, processor types, and launch activity.

```bash
"$ANDROID_HOME/build-tools/37.0.0/aapt" dump badging DW3-Online.apk
```

Replace the build-tools version with an installed version.
The inspected package name is `br.com.digitalna.dw3`.
Its APK includes an x86_64 native library.
Do not substitute its ARM libraries on an x86_64 host.

### Step 4. Inspect the Native Boundary with REA

1. Extract the original x86_64 library into an analysis directory.
2. Close the APK target before the native analysis.
3. Open the extracted library with REA.
4. Inspect its exported JNI functions.
5. Trace the initialization function into its Android API calls.
6. Record all external C imports.

Use the following commands to supplement REA evidence.

```bash
mkdir -p linux/apk
python3 - <<'EXTRACT'
from pathlib import Path
from zipfile import ZipFile
with ZipFile('DW3-Online.apk') as apk:
    Path('linux/apk/libdwcofre.so').write_bytes(apk.read('lib/x86_64/libdwcofre.so'))
EXTRACT
readelf -d linux/apk/libdwcofre.so
readelf --version-info linux/apk/libdwcofre.so
nm -D linux/apk/libdwcofre.so
```

Use `procedure_pseudo_code` or `analyze_function` through REA.
For this exact library, `pronto` starts at `0x59d0`.
It calls the initialization routine at `0x59e0`.
Other builds can use different addresses.

The inspected library exports these functions.

```text
Java_dw_client_pak_Cofre_pronto
Java_dw_client_pak_Cofre_servidor
Java_dw_client_pak_Cofre_chave
Java_dw_client_pak_Cofre_abrir
Java_dw_client_pak_Cofre_soltar
```

The inspected library requires `libc.so`, `libdl.so`, and Android `LIBC` symbol versions.
Its initialization also requests Android package information through JNI.
The desktop JVM does not provide those Android classes.

Proceed only after the imported functions have compatible desktop implementations.
This metadata adaptation is specific to the inspected library.
It is not a general conversion method for Android libraries.

### Step 5. Add the Linux LWJGL Libraries

1. Create `linux/lib/`.
2. Download the Linux x86_64 native JARs for LWJGL 3.3.3.
3. Verify each download against its Maven Central SHA-256 file.
4. Save the verified checksums in `linux/SHA256SUMS`.

Use this complete download procedure.

```python
from pathlib import Path
from urllib.request import urlopen
import hashlib
import io
import zipfile

modules = [
    'lwjgl', 'lwjgl-glfw', 'lwjgl-jemalloc', 'lwjgl-openal',
    'lwjgl-opengl', 'lwjgl-opengles', 'lwjgl-stb',
]
output = Path('linux/lib')
output.mkdir(parents=True, exist_ok=True)
checksums = []
for module in modules:
    name = f'{module}-3.3.3-natives-linux.jar'
    url = f'https://repo.maven.apache.org/maven2/org/lwjgl/{module}/3.3.3/{name}'
    data = urlopen(url, timeout=30).read()
    expected = urlopen(url + '.sha256', timeout=30).read().decode().split()[0]
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise RuntimeError(f'Checksum mismatch: {name}')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f'Invalid JAR: {name}')
    (output / name).write_bytes(data)
    checksums.append(f'{actual}  {name}\n')
Path('linux/SHA256SUMS').write_text(''.join(checksums))
```

The original libGDX and FreeType desktop native JARs already include Linux libraries.
The launcher must exclude the Windows LWJGL native JARs.

### Step 6. Create the Adapter and Bridge Source

1. Create every file in Appendix A at its specified relative path.
2. Keep the original `app/` and `data/` directories.
3. Keep the APK at the workspace root.
4. Set `ANDROID_HOME` to the installed SDK directory, if necessary.
5. Put the JDK 21 tools on `PATH`.
6. Build the native adapter and Java bridge.

```bash
python3 linux/native/build.py
```

The builder verifies the original APK signature with `apksigner`.
It also checks the fixed artifact hashes.
It extracts the public certificate from the APK v2 signing block.
It does not extract a private signing key.

The builder removes these tags from the ELF dynamic table.

| Dynamic tag | Value |
| --- | --- |
| `DT_NEEDED` | `1` |
| `DT_VERSYM` | `0x6ffffff0` |
| `DT_VERNEED` | `0x6ffffffe` |
| `DT_VERNEEDNUM` | `0x6fffffff` |

The desktop JVM already has the standard C library in its process.
That library resolves the compatible C imports after the Android requests are removed.
The builder preserves every byte outside the dynamic table.
It does not change native instructions or certificate checks.

The Java bridge supplies these exact Android API elements.

| Class | Required API |
| --- | --- |
| `android.app.ActivityThread` | Static `currentApplication()` returning `android.app.Application`. |
| `android.app.Application` | `getPackageName()` and `getPackageManager()`. |
| `android.os.Build$VERSION` | Static integer field `SDK_INT`, value `26`. |
| `android.content.pm.PackageManager` | `getPackageInfo(String, int)` returning `PackageInfo`. |
| `android.content.pm.PackageInfo` | Public `Signature[] signatures` field. |
| `android.content.pm.Signature` | `toByteArray()` returning the original public certificate. |

The bridge uses API level 26 to select the inspected signature API path.
It does not provide a complete Android runtime.

### Step 7. Test the Native Adapter

1. Make `play-linux.sh` executable.
2. Run its native check.

```bash
chmod +x play-linux.sh
./play-linux.sh --check
```

Require this actual output.

```text
Native library loaded; original APK signature validation passed.
```

Do not print that message without the native initialization call.
If the check fails, inspect the actual exception before any further change.
Do not replace the native check with a fixed success result.

### Step 8. Build the Executable and Included Java Runtime

1. Make the executable builder available.
2. Run the executable builder.

```bash
chmod +x linux/native/build-executable.sh
./linux/native/build-executable.sh
```

The builder compiles `launcher.c` with GCC.
It creates a reduced Java 21 runtime with `jlink`.
The executable selects that runtime from its own directory.
It forwards the user arguments to `play-linux.sh`.

3. Examine the output formats.

```bash
file DW3-Online-Linux linux/runtime/bin/java
./DW3-Online-Linux --check
```

Require an ELF executable for Linux x86_64.
Require successful native initialization with the included runtime.

### Step 9. Test the Graphical Application

1. Start the new executable in a permitted Linux graphical session.

```bash
./DW3-Online-Linux
```

2. Wait for the login screen.
3. Capture the game window.
4. Examine the image for complete graphics and visible input fields.
5. Check for new game error reports.
6. Save the image and test output in the workspace.

The visible window alone is not sufficient evidence.
The game must load the assets and display the login interface.
Use an isolated test instance if a user already operates the game.
Do not close the user's active game to perform a test.

7. Test a launch from another working directory.
8. Test the included runtime with an invalid external `JAVA_HOME`.

Use a separate temporary copy of the launcher for an isolated test.
Keep its settings separate from the user's settings.

```bash
JAVA_HOME=/does-not-exist /absolute/path/to/DW3-Online-Linux --check
```

The executable must still select its included runtime.

### Step 10. Prove Native Linux Execution

1. Get the process identifier from the actual launch.
2. Read `/proc/<PID>/exe`.
3. Read `/proc/<PID>/maps`.
4. Save the relevant paths.

Require the following evidence.

| Item | Required observation |
| --- | --- |
| Process executable | The included `linux/runtime/bin/java`. |
| Main class | `dw.client.ClientMain`. |
| JVM library | The included `linux/runtime/lib/server/libjvm.so`. |
| Game library | The adapted `linux/lib/libdwcofre.so`. |
| Graphics libraries | Linux `liblwjgl.so` and `libglfw.so`. |

Preserve complete paths with spaces when you parse the memory map.
Do not use the last whitespace field as the file path.
The original Android build note can remain in the adapted ELF file.
That note does not indicate an active Android runtime.

### Step 11. Create the Desktop Shortcut

1. Generate a `.desktop` file for the actual installation directory.
2. Set `Exec` to the new Linux executable.
3. Set `Path` to the game directory.
4. Set `Terminal=false`.
5. Set `StartupWMClass=DW3 Online`.
6. Validate the file with `desktop-file-validate`, if available.
7. Install the shortcut for the user when that action is authorized.

Use the following structure.
Replace each absolute path with the actual installation path.

```ini
[Desktop Entry]
Type=Application
Name=DW3 Online (Linux)
Comment=Native Linux Java desktop client
Exec="/absolute/game/path/DW3-Online-Linux"
Path=/absolute/game/path
Icon=/absolute/game/path/DW3 Online.ico
Terminal=false
Categories=Game;RolePlaying;
StartupWMClass=DW3 Online
```

### Step 12. Complete the Handoff

1. Verify that the original game files remain unchanged.
2. Verify that the original APK remains unchanged.
3. Record the successful checks.
4. Record all untested functions.
5. Give the user the executable path.
6. Give the user the command to start the game.
7. Explain that the adjacent directories are required.

Use this final operating instruction.

```bash
cd "/absolute/game/path"
./DW3-Online-Linux
```

The prepared game does not require the APK during normal operation.
The APK is required for an adapter rebuild.
The executable requires `app/`, `data/`, `linux/`, and `play-linux.sh`.

## 5. Acceptance Criteria

Do not declare the port complete until these checks pass.

- The inputs match the inspected artifact identities.
- The APK signature verifies with `apksigner`.
- The adapter changes only ELF dynamic metadata.
- The original native certificate check passes.
- The original native asset code loads the game assets.
- The Linux executable uses the included Java runtime.
- The login interface renders correctly.
- The process evidence identifies native Linux Java and Linux libraries.
- The original Windows files and APK remain unchanged.
- The handoff gives the exact start command and required directories.

Report account login and gameplay as untested unless you test those functions.
Let the user enter private account credentials directly.

## 6. Scope and Limits

This procedure reproduces the inspected DW3 Online 0.1.95 port.
It does not convert an arbitrary APK into a desktop application.
The existing desktop Java client is an essential input.
Another game version can require a different bridge or native adaptation.

REA supplies inspection evidence.
Python, Java build tools, GCC, and `jlink` produce the runnable port.
The resulting executable is a directory-based application, not a single-file bundle.

## Appendix A. Complete Source Files

Create the following files before the build steps.
Paths are relative to the extracted game directory.
These files do not depend on the previous conversation.

### A.1. `play-linux.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

game_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd -- "$game_dir"

fail() { printf '%s\n' "$*" >&2; exit 1; }

[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] ||
    fail 'This launcher includes native libraries for Linux x86_64 only.'

java_bin=java
if [[ -n ${JAVA_HOME:-} ]]; then
    java_bin="$JAVA_HOME/bin/java"
fi
command -v "$java_bin" >/dev/null 2>&1 ||
    fail 'Install a Linux Java 17 or newer runtime, or set JAVA_HOME.'
java_version=$("$java_bin" -version 2>&1) || fail 'Java could not start.'
java_major=$(sed -nE 's/.*version "([0-9]+).*/\1/p' <<< "$java_version" | head -n1)
[[ $java_major =~ ^[0-9]+$ ]] && ((java_major >= 17)) ||
    fail 'This game requires Linux Java 17 or newer.'

[[ -f app/client.jar && -f data/data.pak ]] ||
    fail 'Keep this launcher beside the original app/ and data/ directories.'

classpath=''
for jar in "$game_dir"/app/*.jar; do
    case "$jar" in *-natives-windows*.jar) continue ;; esac
    classpath+="${classpath:+:}$jar"
done
for module in lwjgl lwjgl-glfw lwjgl-jemalloc lwjgl-openal lwjgl-opengl lwjgl-opengles lwjgl-stb; do
    jar="$game_dir/linux/lib/$module-3.3.3-natives-linux.jar"
    [[ -f $jar ]] || fail "Missing Linux dependency: $jar"
    classpath+=":$jar"
done

[[ -f linux/lib/libdwcofre.so && -f linux/lib/dw3-android-bridge.jar ]] || fail \
'The APK native adapter is missing. Rebuild it with:
    python3 linux/native/build.py
See README-LINUX.md for requirements.'
classpath="$game_dir/linux/lib/dw3-android-bridge.jar:$classpath"

if [[ ${1:-} == --check ]]; then
    exec "$java_bin" "-Djava.library.path=$game_dir/linux/lib" \
        -cp "$classpath" dw3.linux.NativeCheck
fi

[[ -n ${DISPLAY:-} || -n ${WAYLAND_DISPLAY:-} ]] ||
    fail 'Launch this game from a graphical Linux desktop.'

# Keep settings, logs and the single-instance lock inside the game folder.
mkdir -p "$game_dir/.linux-home"
exec "$java_bin" \
    "-Duser.home=$game_dir/.linux-home" \
    "-Djava.library.path=$game_dir/linux/lib:$game_dir/app" \
    -Djpackage.app-version=1.0.0 \
    -XX:+DisableAttachMechanism \
    -cp "$classpath" dw.client.ClientMain "$@"
```

### A.2. `linux/native/build.py`

```python
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
    with tempfile.TemporaryDirectory(prefix="dw3-linux-build-") as temporary:
        classes = Path(temporary) / "classes"
        classes.mkdir()
        subprocess.run(["javac", "--release", "17", "-d", str(classes),
                        *map(str, sources)], check=True)
        (classes / "dw3-apk-signer.der").write_bytes(certificate)
        subprocess.run(["jar", "--create", "--file", str(output / "dw3-android-bridge.jar"),
                        "-C", str(classes), "."], check=True)
    (output / "libdwcofre.so").write_bytes(adapted)
    print("Built native Linux adapter; original native machine code is unchanged.")
    print("APK signature verified; original signer certificate bundled in Java bridge.")


if __name__ == "__main__":
    main()
```

### A.3. `linux/native/build-executable.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

game_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd -- "$game_dir"

gcc -O2 -Wall -Wextra -Werror -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
    -o DW3-Online-Linux linux/native/launcher.c

if [[ ! -x linux/runtime/bin/java ]]; then
    if [[ -e linux/runtime ]]; then
        printf '%s\n' 'linux/runtime exists but has no executable bin/java. Move that incomplete directory aside, then rebuild.' >&2
        exit 1
    fi
    if [[ $(jlink --version) != 21.* ]]; then
        printf '%s\n' 'Use a JDK 21 jlink on PATH to build the bundled Java 21 runtime.' >&2
        exit 1
    fi
    runtime_build=$(mktemp -d "$game_dir/linux/.runtime-build.XXXXXX")
    trap 'rm -rf -- "$runtime_build"' EXIT
    jlink --add-modules \
        java.base,java.datatransfer,java.xml,java.prefs,java.desktop,java.logging,java.management,java.net.http,java.transaction.xa,java.sql,jdk.crypto.ec,jdk.unsupported \
        --strip-debug --no-header-files --no-man-pages --compress=zip-6 \
        --output "$runtime_build/runtime"
    mv -- "$runtime_build/runtime" linux/runtime
fi

./DW3-Online-Linux --check
printf 'Built DW3-Online-Linux with a bundled Linux Java runtime.\n'
```

### A.4. `linux/native/launcher.c`

```c
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Resolve relative to the ELF executable, including launches from a file manager. */
int main(int argc, char **argv) {
    char executable[PATH_MAX];
    ssize_t length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
    if (length < 0 || (size_t)length >= sizeof(executable) - 1) {
        fprintf(stderr, "Cannot locate the game executable.\n");
        return 1;
    }
    executable[length] = '\0';
    char *separator = strrchr(executable, '/');
    if (separator == NULL) return 1;
    *separator = '\0';

    char runtime[PATH_MAX], script[PATH_MAX], java[PATH_MAX];
    int runtime_length = snprintf(runtime, sizeof(runtime), "%s/linux/runtime", executable);
    int script_length = snprintf(script, sizeof(script), "%s/play-linux.sh", executable);
    int java_length = snprintf(java, sizeof(java), "%s/bin/java", runtime);
    if (runtime_length < 0 || (size_t)runtime_length >= sizeof(runtime) ||
        script_length < 0 || (size_t)script_length >= sizeof(script) ||
        java_length < 0 || (size_t)java_length >= sizeof(java)) {
        fprintf(stderr, "Game directory path is too long.\n");
        return 1;
    }
    if (access(java, X_OK) != 0 || access(script, X_OK) != 0) {
        fprintf(stderr, "Keep DW3-Online-Linux beside play-linux.sh and the linux/ directory.\n");
        return 1;
    }
    if (setenv("JAVA_HOME", runtime, 1) != 0) {
        perror("Cannot select bundled Java");
        return 1;
    }
    char **arguments = calloc((size_t)argc + 1, sizeof(*arguments));
    if (arguments == NULL) {
        perror("Cannot allocate launcher arguments");
        return 1;
    }
    arguments[0] = script;
    for (int index = 1; index < argc; index++) arguments[index] = argv[index];
    execv(script, arguments);
    fprintf(stderr, "Could not launch the game: %s\n", strerror(errno));
    free(arguments);
    return 1;
}
```

### A.5. `linux/native/src/android/os/Build.java`

```java
package android.os;

/** API level for the small Android package-signature compatibility surface. */
public final class Build {
    private Build() {}

    public static final class VERSION {
        public static final int SDK_INT = 26;
        private VERSION() {}
    }
}
```

### A.6. `linux/native/src/android/app/ActivityThread.java`

```java
package android.app;

/** Supplies the application object requested by the original JNI library. */
public final class ActivityThread {
    private static final Application APPLICATION = new Application();

    private ActivityThread() {}

    public static Application currentApplication() {
        return APPLICATION;
    }
}
```

### A.7. `linux/native/src/android/app/Application.java`

```java
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
```

### A.8. `linux/native/src/android/content/pm/Signature.java`

```java
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
```

### A.9. `linux/native/src/android/content/pm/PackageInfo.java`

```java
package android.content.pm;

public final class PackageInfo {
    public Signature[] signatures;
}
```

### A.10. `linux/native/src/android/content/pm/PackageManager.java`

```java
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
```

### A.11. `linux/native/src/dw3/linux/NativeCheck.java`

```java
package dw3.linux;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/** Runs the game's own library initialization, including signature validation. */
public final class NativeCheck {
    private NativeCheck() {}

    public static void main(String[] args) throws Throwable {
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
```

## Appendix B. Document Verification

The source files were extracted from this Markdown document into a new temporary directory.
The test used the original APK, original desktop files, and verified LWJGL dependency JARs.
It rebuilt the adapter, Java bridge, Linux executable, and included Java runtime.
It did not reuse those outputs from the existing port.
The rebuilt native initialization and certificate check passed.

This document test did not repeat the graphical test.
The receiving AI must perform the graphical checks in its own environment.

## Appendix C. Source References

- [ASD-STE100 official website](https://www.asd-ste100.org/).
- [Official LWJGL source](https://github.com/LWJGL/lwjgl3).
- [Maven Central](https://repo.maven.apache.org/maven2/org/lwjgl/).

The source files in Appendix A implement the tested adaptation.
The receiving AI must still verify the new environment and the actual runtime behavior.
