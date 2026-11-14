# DW3 Online: Native Linux Port Guide

Reproduce a native Linux Java port with an AI coding agent and REA.
Start with the original Windows package and the matching Android APK.

The [AI replication playbook](AI-LINUX-PORT-PLAYBOOK-STE100.md) gives the complete procedure.
It includes all 13 source and test files for the adapter, Java bridge, and Linux launcher.

## What This Repository Contains

- `AI-LINUX-PORT-PLAYBOOK-STE100.md`: the procedure and complete source code for the receiving AI.
- `README.md`: the input requirements, operating instructions, and explanation of the original failure.
- `AI-SETUP.md`: the skills and REA setup for Claude Code and Codex.

This repository does not contain the game download, APK, game assets, or prepared executables.
Supply your own original game files.

The instructions use ASD-STE100 Issue 9 style.
No automated STE dictionary check was available.

## Download the Original Game

Use the [official DW3 Online website](https://digitalna.com.br/).
Its [download page](https://digitalna.com.br/baixar) provides the Windows package and Android APK.

1. Open the official download page.
2. Download the Windows 64-bit ZIP package.
3. Extract the complete Windows package.
4. Download the Android APK from the same page.
5. Check the version and hashes against the playbook.

The Windows package includes `DW3 Online.exe`, `app/`, `data/`, and its Windows runtime.
The `.exe` alone is insufficient for this port.
Keep the full package and the matching APK.

The official site can offer a newer version than the inspected version.
Do not apply the pinned adaptation to different files without a new analysis.

## Claude Code and Codex Skills

Read [AI-SETUP.md](AI-SETUP.md) before the replication procedure.
It gives separate REA setup commands for Claude Code and Codex.

Use these skills:

- `reverse-engineer-anything`: the main REA workflow for this task.
- `systematic-debugging`: recommended for failure analysis.
- `verification-before-completion`: recommended for evidence-based completion checks.
- `test-driven-development`: optional when you change the supplied code.
- `requesting-code-review`: optional for an implementation review.

REA also needs a connected MCP server and a native analysis engine.
Installing the skill instructions alone does not provide those tools.
The completed game does not require the AI agent or its skills.

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

2. Complete the Claude Code or Codex setup in `AI-SETUP.md`.
3. Extract the original Windows game into a separate workspace.
4. Put the matching `DW3-Online.apk` in that workspace.
5. Give the AI access to this repository and both original inputs.
6. Replace the example paths in this prompt.
7. Give the completed prompt to the AI.

```text
Read AI-SETUP.md and AI-LINUX-PORT-PLAYBOOK-STE100.md in full.

Use the reverse-engineer-anything skill for REA analysis.
Use systematic-debugging and verification-before-completion when available.
Report which skills and REA tools are actually available.

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

## Open Multiple Game Windows

Start `DW3-Online-Linux` again while the first window remains open.
The same executable can open more than one client.

```bash
./DW3-Online-Linux &
./DW3-Online-Linux &
```

Each client uses a separate persistent Java home.
The first available client uses `.linux-home/`.
Additional clients use `.linux-home/instances/instance-2/`, `instance-3/`, and subsequent slots.
Each home has its own settings, logs, and native game lock.
The installed client libraries and game assets remain shared.

The bootstrap reserves a profile until its game window closes.
A later launch can reuse the released slot and its saved settings.
Profile slots are not named accounts.
The bootstrap also detects the native lock of an already-running older client.
It does not change the game's lock code.

Run the regression checks after a build:

```bash
python3 linux/native/tests/test_instances.py
```

The three checks cover concurrent profile selection, released profile reuse, and an existing older client.
Two actual game windows also displayed their login screens together during the graphical test.
The user subsequently confirmed that multiple windows work.

## Native Linux Java Application

The Linux executable starts the included OpenJDK runtime.
The desktop game logic runs as Java bytecode in that Linux JVM.
Graphics, audio, and the adapted asset library use native Linux code.
This is a native Linux Java application, rather than a fully compiled standalone game binary.
No Wine or Android emulator is involved.

## Verified Results and Limits

The original implementation reached the fully rendered login screen on Linux.
Its process used Linux Java, Linux LWJGL libraries, and the adapted native library.
Its original native certificate check passed.

A separate test extracted the source files from the Markdown playbook into a fresh directory.
That test rebuilt the adapter, bridge, executable, and included Java runtime.
The rebuilt native initialization and certificate check passed.
It did not reuse those outputs from the existing port.

The user subsequently tested account login and gameplay successfully.
Those results are user-reported verification.
The agent independently verified native startup and the rendered login screen.
The multi-window launcher passed all three regression checks.
The user also confirmed successful operation of multiple windows.
The receiving AI must verify its own build on the target computer.
