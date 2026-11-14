# DW3 Online: Linux Port and Operating Instructions

| Item | Value |
| --- | --- |
| Document date | 2026-11-14 |
| Game version | 0.1.95 |
| APK version code | 10095 |
| Target system | Linux x86_64 with glibc |
| Test system | Ubuntu 26.04.1 LTS |
| Included Java runtime | OpenJDK 21.0.2 |
| Writing basis | ASD-STE100 Issue 9 style |

## 1. Purpose

This document explains the Linux port.
It also gives instructions to start the game.

The port uses the desktop Java client and the native library from the APK.
A small Java bridge connects the native library to the desktop client.
The game runs in a Linux Java process.

The port does not use Wine, Waydroid, or an Android emulator.
The APK alone cannot run this desktop port.

## 2. Technical Terms

| Term | Meaning in this document |
| --- | --- |
| APK | The Android application package, `DW3-Online.apk`. |
| Desktop client | The Java game program in `app/client.jar`. |
| Native library | Compiled code that the processor executes directly. |
| Adapter | The native library with changes to its loader metadata. |
| Java bridge | Java classes that supply the required Android package information. |
| JNI | The Java Native Interface between Java and the native library. |
| ELF | The executable file format that this Linux port uses. |
| Java runtime | The software that executes the Java client. |
| Public certificate | The public identity certificate of the APK signer. |
| REA | The analysis tool used to examine the APK and its native library. |
| Hopper | The disassembler that REA used for native code analysis. |

## 3. Required Files

Keep these items in the game directory.

```text
DW3 Online/
├── DW3-Online-Linux
├── DW3 Online Linux.desktop
├── play-linux.sh
├── app/
│   ├── client.jar
│   └── other Java libraries
├── data/
│   └── data.pak
└── linux/
    ├── lib/
    │   ├── libdwcofre.so
    │   ├── dw3-android-bridge.jar
    │   └── Linux LWJGL native JAR files
    ├── runtime/
    │   └── bin/java
    └── native/
        ├── build.py
        ├── build-executable.sh
        ├── launcher.c
        └── src/
```

The executable requires the adjacent files and directories.
It is not a complete application in one file.
The included Java runtime removes the requirement for a separate Java installation.

The APK supplies the native library and its public certificate during the build.
The completed port does not read the APK during normal operation.

## 4. Start the Game

### 4.1 Use the Applications Menu

1. Open the Applications menu.
2. Select **DW3 Online (Linux)**.
3. Wait for the login screen.
4. Enter your account name in the **Name** field.
5. Enter your password in the **Password** field.
6. Select **LOG IN**.

The shortcut is installed for the current user.
Its target is the executable in `/path/to/DW3 Online`.

### 4.2 Use a Terminal

1. Open a terminal.
2. Change to the game directory.

   ```bash
   cd "/path/to/DW3 Online"
   ```

3. Start the Linux executable.

   ```bash
   ./DW3-Online-Linux
   ```

4. Wait for the login screen.

### 4.3 Use the File Manager

1. Open the game directory.
2. Open `DW3-Online-Linux`.
3. Wait for the login screen.

If the file manager does not execute the file, use the terminal procedure in section 4.2.

## 5. Check the Native Adapter

1. Open a terminal.
2. Change to the game directory.

   ```bash
   cd "/path/to/DW3 Online"
   ```

3. Execute the native check.

   ```bash
   ./DW3-Online-Linux --check
   ```

4. Compare the result with this message.

   ```text
   Native library loaded; original APK signature validation passed.
   ```

This check loads the native library through the Java runtime.
It also executes the original certificate check in the native library.
It does not test account access or gameplay.

## 6. Confirm Native Linux Operation

Use this procedure with one game window open.

1. Open a terminal.
2. Get the process identifier of the game.

   ```bash
   pid=$(pgrep -n -u "$(id -u)" -f 'dw[.]client[.]ClientMain')
   ```

3. Show the path of the process executable.

   ```bash
   readlink -f "/proc/$pid/exe"
   ```

4. Compare the path with the included Java executable.

   ```text
   /path/to/DW3 Online/linux/runtime/bin/java
   ```

5. Show the related libraries in the process memory map.

   ```bash
   awk '/libdwcofre[.]so|libjvm[.]so|liblwjgl[.]so/ {print substr($0, index($0, "/"))}' "/proc/$pid/maps" | sort -u
   ```

The results include the Linux JVM, the adapter, and the Linux LWJGL library.
These paths identify the code that the process loaded.

6. Change to the game directory.

   ```bash
   cd "/path/to/DW3 Online"
   ```

7. Examine the executable formats.

   ```bash
   file DW3-Online-Linux linux/runtime/bin/java linux/lib/libdwcofre.so
   ```

The results identify ELF files for the x86_64 processor.
The adapter retains its original Android build note.
That note does not identify an active Android runtime.

The saved process evidence is in [native-runtime-proof.txt](linux/diagnostics/native-runtime-proof.txt).
The executable test image is in [native-executable-check.png](linux/native-executable-check.png).

## 7. How the Port Works

### 7.1 Original Failure

The Windows package contains a Java client and Windows native libraries.
The first Linux test could not find `liblwjgl.so`.
The added Linux LWJGL libraries corrected that failure.

The next test reached the game window.
The client then failed when it tried to load `dwcofre`.
The Windows package contains only `dwcofre.dll`.
Linux Java cannot load that Windows library.

### 7.2 APK Analysis with REA

REA examined the supplied APK archive.
The archive contains an x86_64 copy of `libdwcofre.so`.
Hopper examined its initialization code through REA.

The analysis identified the required JNI entry points.
It also identified calls to Android package APIs.
Those calls obtain the public certificate of the APK signer.

The separate JADX component was not available in REA.
Android SDK `aapt` supplied the package version and application information.

### 7.3 Native Library Adaptation

The original APK library uses Android library names and Android symbol versions.
The desktop Linux loader cannot resolve those requests directly.

The build script changes only the ELF dynamic table.
It removes the Android dependency requests and symbol-version requests.
The Linux JVM has already loaded the desktop C library.
That C library supplies the standard C functions that the adapter requires.

The build script does not change native machine instructions.
The original code still opens the game assets.
The original code still checks the public certificate.

### 7.4 Java Bridge

The desktop JVM does not contain Android application classes.
The bridge supplies the small set of classes that the native library requires.

The bridge supplies the original package name.
It also supplies the original public certificate from the verified APK.
The native library compares that certificate with its expected value.

The bridge is in `linux/lib/dw3-android-bridge.jar`.
Its source files are in `linux/native/src/`.

### 7.5 Linux Executable

GCC compiles `linux/native/launcher.c` into `DW3-Online-Linux`.
The executable finds the game directory from its own location.
It selects the Java runtime in `linux/runtime/`.
It then executes `play-linux.sh` with that runtime.

The script selects the Java libraries and Linux native libraries.
It starts `dw.client.ClientMain`.
The client uses the existing desktop graphics and controls.

The `jlink` tool creates the included Java runtime.
Its module list matches the module list in the original Windows Java runtime.

## 8. Rebuild the Port

This procedure is optional for normal operation.
It rebuilds the existing adapter and executable.
It does not download the game files or the LWJGL libraries.

### 8.1 Build Requirements

| Item | Requirement |
| --- | --- |
| Game files | The existing `app/` and `data/` directories. |
| APK | The inspected `DW3-Online.apk`, version 0.1.95. |
| Java tools | JDK 21 with `javac`, `jar`, and `jlink`. |
| C compiler | GCC. |
| Script tools | Python 3 and Bash. |
| Signature tool | Android SDK Build Tools with `apksigner`. |
| Linux dependencies | The existing files in `linux/lib/`. |

The build script verifies the APK signature before it creates the adapter.
It also checks the APK hash, native library hash, and public certificate hash.
The script accepts only the inspected APK version.

### 8.2 Build Procedure

1. Open a terminal.
2. Change to the game directory.

   ```bash
   cd "/path/to/DW3 Online"
   ```

3. If the SDK uses a different directory, set `ANDROID_HOME` to that directory.

   ```bash
   export ANDROID_HOME="/path/to/Android/Sdk"
   ```

   The default SDK directory is `~/Android/Sdk`.

4. Build the adapter and Java bridge.

   ```bash
   python3 linux/native/build.py
   ```

5. Build the Linux executable.

   ```bash
   bash linux/native/build-executable.sh
   ```

   The script creates the Java runtime if no runtime exists.
   It keeps an existing executable runtime.

6. Execute the native check.

   ```bash
   ./DW3-Online-Linux --check
   ```

7. Start the game.

   ```bash
   ./DW3-Online-Linux
   ```

## 9. Correct Common Problems

| Symptom | Cause or check | Corrective action |
| --- | --- | --- |
| Permission denied | The executable permission is absent. | Execute `chmod +x DW3-Online-Linux play-linux.sh`. |
| Missing adapter message | The adapter or bridge file is absent. | Repeat section 8.2 with the required build tools. |
| Missing Linux dependency | A required LWJGL JAR file is absent. | Restore the named file in `linux/lib/`. |
| Incomplete runtime message | The runtime directory lacks an executable `bin/java`. | Move the incomplete runtime directory before a rebuild. |
| Shortcut fails after a move | The shortcut contains the previous directory path. | Start the executable from the new directory. |
| Game does not open | Another game process can hold the instance lock. | Close the existing game window. |
| Login fails | Account access and server availability require separate checks. | Check the account details and the server status. |

The game stores its settings and logs in `.linux-home/`.
The old error reports record the failures before the adapter build.
The time in each report identifies its test.

## 10. Test Results and Limits

| Check | Result |
| --- | --- |
| APK signature verification | Passed. |
| Native library initialization | Passed. |
| Original public certificate check | Passed. |
| Game asset access | Passed during startup. |
| Login screen display | Passed. |
| Included runtime selection | Passed with an invalid external `JAVA_HOME`. |
| Start from another directory | Passed. |
| Original Windows files | All 195 files remained unchanged. |
| Original APK | The file remained unchanged. |
| Account login | Passed, as reported by the user. |
| Gameplay | Passed, as reported by the user. |

The tests apply to this computer and the inspected game version.
A different APK version requires a new compatibility check.

## 11. References

- [Technical details and source locations](README-LINUX.md).
- [ASD-STE100 Issue 9, official specification](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf).
- [ASD-STE100 official website](https://www.asd-ste100.org/).

This guide uses short sentences, direct instructions, and consistent technical terms.
No automated STE dictionary check was available for this document.
