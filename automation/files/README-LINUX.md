# DW3 Online: native Linux desktop port

See the [AI setup guide](AI-SETUP.md) for Claude Code and Codex skills and REA setup.

Use [the AI replication playbook](AI-LINUX-PORT-PLAYBOOK-STE100.md) to reproduce the port from the original downloads.
Use [the operating guide](LINUX-PORT-GUIDE-STE100.md) to run and check the prepared game.

## Run

Open **DW3 Online (Linux)** from your Applications menu, double-click
`DW3-Online-Linux`, or run:

```bash
cd "/path/to/DW3 Online"
./DW3-Online-Linux
```

This is a Linux x86_64 ELF executable with a bundled OpenJDK 21.0.2 runtime.
Keep it beside `play-linux.sh`, `app/`, `data/`, and `linux/`. No separate
Java installation, Wine, Waydroid, Android SDK or Android emulator is needed
for launching the prepared game. `DW3 Online Linux.desktop` is also provided.
The desktop shortcut contains this installation's absolute path; regenerate or
edit it if you move the game folder. The executable itself works after moving
the whole folder.

`./play-linux.sh` also works and uses `JAVA_HOME` or Java on your PATH instead
of forcing the bundled runtime. Both launchers keep the primary settings and logs in `.linux-home/`.
Additional clients use separate homes under `.linux-home/instances/`. Do not run the game as root.

## What is combined

- The existing desktop Java client `app/client.jar`, version 0.1.95, and its
  original game data `data/data.pak`.
- The original x86_64 JNI library from `DW3-Online.apk`, adapted for the Linux
  JVM by changing only its ELF dynamic-linker metadata.
- `linux/lib/dw3-android-bridge.jar`, a small Java bridge for the Android
  package-signature API calls used by that native library.
- Matching Linux x86_64 LWJGL 3.3.3 native JARs and the existing libGDX JARs.

This uses the existing desktop renderer and controls. It does not run Android.
The APK alone is not sufficient for this desktop port. The APK is needed to
rebuild the adapter, but is not opened when launching the prepared game.
The original Windows runtime, executable and DLL are not used.

## Verification and current limits

The Linux executable was also tested from a different directory with an invalid
external JAVA_HOME: it used its bundled runtime and displayed the login screen.
Runtime evidence is saved in `linux/diagnostics/native-runtime-proof.txt` and
`linux/native-executable-check.png`.

The final Java bridge and native library passed the game's original native
initialization and APK certificate validation. The desktop client loaded its
game assets and displayed the fully rendered login screen; see
`linux/native-desktop.png`. The user subsequently reported successful account login and gameplay.
Historical errors in `.linux-home/DW3-erro.txt` and
`.linux-home/.dw3online/erro.log` are from the earlier failed launch before
this APK adapter was built.

Run the native check without opening a window:

```bash
./DW3-Online-Linux --check
```

Expected output:

```text
Native library loaded; original APK signature validation passed.
```

To confirm native Linux execution while the game is open:

```bash
pid=$(pgrep -u "$(id -u)" -f 'dw[.]client[.]ClientMain' | head -n1)
readlink -f "/proc/$pid/exe"
awk '/libdwcofre[.]so|libjvm[.]so|liblwjgl[.]so/ {print substr($0, index($0, "/"))}' "/proc/$pid/maps" | sort -u
file DW3-Online-Linux linux/runtime/bin/java linux/lib/libdwcofre.so
```

The process executable should be `linux/runtime/bin/java` when started with
`DW3-Online-Linux`. Its memory maps should include `linux/lib/libdwcofre.so`,
`linux/runtime/lib/server/libjvm.so`, and Linux LWJGL libraries. `file` reports
ELF x86_64 binaries. The adapted native library retains its original Android
build note; this note does not mean an Android runtime is being used.

## How REA was used

REA inventoried the APK and Hopper analyzed the native library's initialization.
That established the x86_64 JNI entry points and the required Android signature
API calls. REA's JADX package inspection was unavailable because its separate
JADX component was not configured; Android SDK `aapt` supplied manifest details.

The APK signature was verified with Android SDK `apksigner` before extracting
its public signing certificate. The Java bridge supplies this original
certificate to the library's existing verification code. No native instructions,
asset encryption routines or signature-checking instructions were changed.
Only the Android `DT_NEEDED` and symbol-version requests were removed from the
ELF dynamic table so the already-loaded desktop C library can supply the same
standard C functions.

Inspected APK SHA-256:

```text
e1865b79e6af7d6fde18568221d15edddaf419a6d137e0f77ec01e1eca685baa
```

Original APK x86_64 library SHA-256:

```text
62b7987c1568999053618cf26a8f5f564a6aadd1f746d97ccf61817fe1a0e120
```

Public signing certificate SHA-256:

```text
5335bc451e542043cea6996de0baf8a882e6c165aa2004fce248bb8de8410d85
```

REA APK inventory evidence:
`ev_5ea82dd7f647e6561df91bb3c8e55bd385b0d8bdef0fe1dff79db3a3b156a325`.
REA native initialization evidence:
`ev_ba4379303d22a51de685b15d28bb94b8926bf3f6f483e26eb7d2f5fb5a1ad2d0`.
These are static findings. The launch, screenshot and process memory maps are
separate runtime verification.

## Rebuild

Rebuilding needs Python 3, JDK 21 with `javac`, `jar` and `jlink`, GCC, the original
APK and Android SDK Build Tools containing `apksigner`. Set `ANDROID_HOME` if
that SDK is outside `~/Android/Sdk`. The adapter is pinned to the inspected
APK version 0.1.95 (10095); a newer APK requires a new compatibility review.

```bash
python3 linux/native/build.py
bash linux/native/build-executable.sh
./DW3-Online-Linux --check
```

The native source is `linux/native/launcher.c`; the bridge source is under
`linux/native/src/`. The runtime includes the original module list plus `jdk.charsets`.
The game requires `x-windows-949` when it loads later assets. Its license notices are retained under
`linux/runtime/legal/`.

Added LWJGL dependencies come from Maven Central using this pattern:

```text
https://repo.maven.apache.org/maven2/org/lwjgl/<module>/3.3.3/<module>-3.3.3-natives-linux.jar
```

They were checked against Maven Central's SHA-256 files. Verify them locally:

```bash
(cd linux/lib && sha256sum -c ../SHA256SUMS)
```

The original Windows files and APK remain unchanged.

## Multiple game windows

Open `DW3-Online-Linux` again while the first window remains open.
Each client receives its own persistent profile.
The first free profile uses `.linux-home/`.
Additional profiles use `.linux-home/instances/instance-2/` and subsequent slots.
Closing a window makes its profile available for reuse.

```bash
./DW3-Online-Linux &
./DW3-Online-Linux &
```

The bootstrap is `dw3.linux.DesktopLauncher`; it invokes the original game entry point.
Three regression checks and two simultaneous rendered login windows passed.
The user also confirmed successful multi-window operation.

```bash
python3 linux/native/tests/test_instances.py
```

## Game state output

See [Game state output](GAME-STATE-PRINTING.md) for the opt-in `print-game-state.sh` launcher.
It opens a new monitored window and prints player coordinates and movement changes.
It does not attach to an existing window.

## Missing legacy text encoding

The crash `UnsupportedCharsetException: x-windows-949` requires `jdk.charsets` in the bundled runtime.
The executable builder now detects an older runtime without that module and rebuilds it.
The previous runtime remains in a `linux/runtime.previous-*` directory.
The replacement is atomic, so an existing game is not interrupted during installation.
Restart the affected game window to use the updated runtime.

```bash
python3 linux/native/tests/test_runtime.py
./DW3-Online-Linux --check
```
