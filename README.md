# DW3 Online: Native Linux Port Guide

Reproduce a native Linux Java port with an AI coding agent and REA.
Start with the original Windows package and the matching Android APK.

The [AI replication playbook](AI-LINUX-PORT-PLAYBOOK-STE100.md) gives the complete procedure.
It includes all 11 source files for the adapter, Java bridge, and Linux launcher.

## What This Repository Contains

- `AI-LINUX-PORT-PLAYBOOK-STE100.md`: the procedure and complete source code for the receiving AI.
- `README.md`: the input requirements, operating instructions, and explanation of the original failure.

This repository does not contain the game download, APK, game assets, or prepared executables.
Supply your own original game files.

The instructions use ASD-STE100 Issue 9 style.
No automated STE dictionary check was available.

## Supported Inputs

| Item | Required version or environment |
| --- | --- |
| Desktop package | DW3 Online 0.1.95, including `app/client.jar` and `data/data.pak`. |
| Android package | `DW3-Online.apk`, version 0.1.95, version code 10095. |
| Host | Linux x86_64 with glibc and a graphical desktop. |
| Java build tools | JDK 21 with `java`, `javac`, `jar`, and `jlink`. |
| Other build tools | Python 3, Bash, GCC, and standard ELF tools. |
| Android tools | SDK Build Tools with `aapt` and `apksigner`. |
| Analysis tools | REA with APK archive inspection and native analysis through Hopper. |

The tested host was Ubuntu 26.04.1 LTS.
The playbook records the exact input hashes.
A different game version requires a new analysis.

## Give the Task to Another AI

1. Clone this repository.

   ```bash
   git clone https://github.com/a7chax/dw3-online-linux-guide.git
   cd dw3-online-linux-guide
   ```

2. Extract the original Windows game into a separate workspace.
3. Put the matching `DW3-Online.apk` in that workspace.
4. Give the AI access to the playbook and both original inputs.
5. Replace the example paths in this prompt.
6. Give the completed prompt to the AI.

```text
Read AI-LINUX-PORT-PLAYBOOK-STE100.md in full.

Reproduce the native Linux Java port described in that document.

Original Windows game directory: /absolute/path/to/DW3 Online
Original APK: /absolute/path/to/DW3-Online.apk
Writable output directory: /absolute/path/to/linux-port-workspace

Use REA to inspect the actual APK and native library.
Verify the input hashes before you use the supplied adaptation.
Create the source files from Appendix A.
Build the adapter, Java bridge, Linux executable, and included Java runtime.

Use the existing desktop Java client and game data.
Do not use Wine, Proton, Waydroid, or an Android emulator for the final application.
Keep the original downloads unchanged.
Preserve the original certificate check and native asset code.

Run the checks in the playbook.
Verify the rendered login screen and the actual Linux process libraries.
Give me the executable path, start command, test evidence, and remaining limits.
Do not claim account login or gameplay success unless those functions were tested.
Let me enter private account credentials directly.

Complete the implementation and verification when the required tools are available.
Report the specific blocker if a required step cannot proceed.
```

The receiving AI does not need the original conversation.
Appendix A contains the source files that it must create.
The AI must still verify its environment and the supplied game version.

## Why the Windows-Only Attempt Failed

The desktop client is Java, but the Windows download includes platform-specific components.
Its `.exe` launcher and included Java runtime are Windows programs.
Linux cannot execute those components directly.

The first Linux Java test could not find `liblwjgl.so`.
The package contained Windows LWJGL native libraries instead of Linux LWJGL native libraries.
The matching Linux libraries corrected that failure.

The next test opened a game window but failed during asset initialization.
The Java client requires the custom JNI library `dwcofre`.
The Windows package contains only `app/dwcofre.dll`.
The Linux JVM requires a compatible Linux shared library.

That test reported:

```text
java.lang.UnsatisfiedLinkError: no dwcofre in java.library.path
```

Renaming the DLL does not change its binary format or its Windows API dependencies.
Replacing the Java runtime alone does not supply the missing library.
This explains the failure of the original Windows-only approach.
It does not mean that Java applications cannot run on Linux.

## Why the Combined Port Works

The matching APK contains `lib/x86_64/libdwcofre.so`.
REA and Hopper identified its native interface and its Android package API calls.

The port combines these components:

| Component | Source or purpose |
| --- | --- |
| Desktop client and game data | The original Windows package. |
| Native asset library | The matching x86_64 library from the APK. |
| Loader metadata adaptation | Resolves the inspected library's standard C imports through the desktop JVM process. |
| Java bridge | Supplies the required Android package name and original public certificate. |
| Linux graphics and audio libraries | Matching LWJGL 3.3.3 native JAR files. |
| Linux executable and Java runtime | GCC launcher and an included OpenJDK 21 runtime. |

The adaptation changes ELF dynamic-linker metadata.
It does not change native machine instructions, asset routines, or certificate-check instructions.
The builder verifies the APK signature before it extracts the public certificate.

The result runs the desktop Java client directly on Linux.
It does not run an Android operating system.

This method applies to the inspected game and library.
It is not a general method to convert arbitrary Windows programs or APKs.

## Run the Completed Port

These commands apply after the AI has completed the playbook.
The repository itself is a guide, not a ready-to-run game.

1. Change to the completed game directory.

   ```bash
   cd "/absolute/path/to/linux-port-workspace"
   ```

2. Start the Linux executable.

   ```bash
   ./DW3-Online-Linux
   ```

3. Wait for the login screen.

The executable includes its Java runtime.
Keep these items together:

```text
DW3-Online-Linux
play-linux.sh
app/
data/
linux/
```

The executable is not a complete application in one file.
The APK is required for an adapter rebuild, but not for normal operation of the completed port.

To check native initialization without a game window, execute:

```bash
./DW3-Online-Linux --check
```

Expected output:

```text
Native library loaded; original APK signature validation passed.
```

## Verified Results and Limits

The original implementation reached the fully rendered login screen on Linux.
Its process used Linux Java, Linux LWJGL libraries, and the adapted native library.
Its original native certificate check passed.

A separate test extracted the source files from the Markdown playbook into a fresh directory.
That test rebuilt the adapter, bridge, executable, and included Java runtime.
The rebuilt native initialization and certificate check passed.
It did not reuse those outputs from the existing port.

Account login and gameplay were not tested.
The receiving AI must repeat the graphical verification on the target computer.
