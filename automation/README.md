# Native Linux automation source kit

This directory contains source code and tests for the inspected DW3 Online 0.1.95 Linux port and its local Python controller. It does not contain the game, APK, Java runtime, native libraries, map exports, dialogue exports, screenshots, credentials, or saved sessions. Obtain your own original game files and matching APK. See the [port playbook](../AI-LINUX-PORT-PLAYBOOK-STE100.md) for those prerequisites and the Linux LWJGL dependencies.

`files/` mirrors the **game installation root**. Install it beside your own `app/` and `data/`; running these scripts directly inside this repository would give them the wrong game path. The current files under `files/linux/native/` supersede the historical source appendix in the port playbook.

## Install the sources

From the repository directory, inspect the dry-run first:

```bash
uv run --no-project automation/install.py --game-dir "/path/to/DW3 Online"
```

Apply that source-only plan:

```bash
uv run --no-project automation/install.py --game-dir "/path/to/DW3 Online" --apply
```

The installer uses standard-library Python through `uv`. It requires an existing `app/client.jar`, checks the source manifest hashes and safe relative paths, creates the relative `game_control.py -> game-control.py` import alias, and merges `.gitignore`. Changed source/configuration files are backed up under `linux/automation-backups/TIMESTAMP/`. It never reads, copies, backs up, or overwrites your private `.env`. Its `.env.example` contains placeholders only.

The installer does **not** download, build, launch, log in, or move your game. Installing updated Java source does not update an already-running client. Build and restart deliberately after stopping existing controllers. Match the pinned game/APK versions before building.

## Prepare and run in your game directory

After supplying the original inputs/dependencies and configuring private credentials once, start the complete supported workflow with one command:

```bash
cd "/path/to/DW3 Online"
uv run --locked automation.py
```

The entry point builds a missing/stale native bridge and missing executable/runtime outputs, logs in or reuses the monitored game, validates/reloads the game-only input bridge, and starts persistent control. It enables selected-option combat Space, known-popup checks and bounded Codex repair. It detects an existing session controller rather than creating duplicate input. Normal control runs in Python without AI calls; source repair needs an installed, authenticated Codex CLI. Use `--no-codex-repair` or `--no-battle-space` to disable those respective modes, and `--max-cycles 3` for a finite check. This does not download original game inputs, install system build tools, or supply private credentials.

Inspect or stop without setup/login/input:

```bash
uv run --locked automation.py --status
uv run --locked automation.py --stop
```

The explicit build steps below remain available for diagnosis or a manual setup:

```bash
cd "/path/to/DW3 Online"
uv sync --locked
uv run --locked python linux/native/build.py
bash linux/native/build-executable.sh
./DW3-Online-Linux --check
```

The Python lock supplies Pillow. Build/runtime dependencies remain separate: Linux x86_64, JDK 21 tools, GCC, Android SDK `apksigner`, the matching original APK, Linux LWJGL native JARs, and your graphical X11 desktop. Window lookup, focus and screenshots require `xwininfo`, `xprop`, and libX11. Routine keys and popup clicks use private game callbacks; libXtst and desktop keyboard/mouse injection are not required. See the port playbook for Linux-port preparation; the original Windows runtime cannot run on Linux.

The former host XTest path could trigger GNOME's Remote Desktop permission dialog during battle input. The maintained controller sends allowlisted keys through the game's GLFW callback and clicks through its input processor in window-local coordinates. It does not move the host pointer or request desktop sharing for those actions. `status` must report `native_key_input` and `native_click_input: true`; an older loaded bridge fails instead of falling back to host input.

After updating sources on an existing installation, stop the supervisor, build, and restart the monitored game to load the new bridge:

```bash
uv run --locked autoplay.py --stop
uv sync --locked
uv run --locked python linux/native/build.py
uv run --locked python ai-game.py login --restart
uv run --locked python ai-game.py status
```

Run these commands in the installed game directory. The restart closes that monitored game and logs in again; configure private credentials first. Verify the capability fields and intended PID before resuming. Focus, map/session and modal guards still apply.

Configure credentials privately, or use the hidden prompt:

```bash
cp -n .env.example .env
chmod 600 .env
# Edit .env locally; do not publish its contents.
uv run --locked python ai-game.py login
```

For an already prepared monitored world, start the advanced direct supervisor without AI repairs:

```bash
uv run --locked python autoplay.py --resume
```

To additionally confirm the currently selected combat option with normal Space, explicitly add `--battle-space`. This does not choose items or tactics. Optional `--repair-with-codex` requires a separately installed, authenticated Codex CLI; normal control does not require an AI service. Both capabilities and their limits are described in [README-AUTOPLAY.md](files/README-AUTOPLAY.md) and [AI-GAME-CONTROL.md](files/AI-GAME-CONTROL.md).

```bash
uv run --locked python autoplay.py --resume --battle-space
uv run --locked python autoplay.py --status
uv run --locked python autoplay.py --stop
```

There is no default time limit. `--max-cycles 3` gives a bounded run. Focus loss, invalid state, unsupported objectives, incomplete telemetry, and story choices can pause the controller. A running process does not prove quest progress or guarantee completion of every quest. Stop commands act on the monitored session; specify `--session /original/session/path` if `latest` has changed.

If startup opens the game but movement stops, inspect `uv run --locked automation.py --status`. Resized-window captures now refresh geometry and trap X11 errors as a recoverable `window_unavailable` pause; restore/focus the same window. The planner can make a short clear-foot escape from its extra collision margin only when it lands back in full padded clearance. Missing routes remain bounded stops, and blocked cached routes back off for 60 seconds. These changes recovered the recorded startup case without weakening normal terrain checks.

Map and quest exports must be generated locally, after login, when wanted:

```bash
uv run --locked python ai-game.py export-world
uv run --locked python quest_catalog.py export
```

Exported `linux/world/` and `linux/quest-catalog/` files contain data from your original game and are intentionally absent from the repository. Local guides mention historical diagnostics and screenshots that are also intentionally excluded. The optional popup-close template is not distributed; exact template matching requires a locally supplied template, otherwise the existing dismissal command uses its documented fallback.

The supervisor checks a locally supplied close template before movement and at most once every two seconds, sends a guarded game-only click, and verifies marker disappearance before clearing navigation backoff. Missing templates skip automatic detection. Unknown dialogs and story choices are not automatically recognized.

## Tests

Installer tests run without game files or a desktop:

```bash
uv run --no-project python -B -m unittest discover -s automation/tests -v
```

After installing into your own prepared game, building the adapter/runtime, and exporting the local map/NPC metadata, run its complete suite there:

```bash
uv run --locked python -B -m unittest discover -s linux/native/tests -p 'test_*.py' -q
```

The complete suite includes original-client and built-Java integration checks. A source-only checkout cannot satisfy those inputs. Synthetic policy, movement, and UI fixtures do not send game input. The startup recovery revision passed 162 local automation tests and 8 installer tests. A two-cycle live check moved from map `s205` to `s330`; an intentionally invalid X11 capture was caught, and the next capture succeeded. Live results belong to the original inspected installation; verify your own setup separately.

## Maintainers

Refresh only the reviewed sources from an explicit workspace, then rerun installer tests and inspect the diff:

```bash
uv run --no-project python -B automation/refresh_payload.py --workspace "/path/to/DW3 Online"
uv run --no-project python -B -m unittest discover -s automation/tests -v
```

The generator takes the public root `AI-SETUP.md` and playbook copies from this repository, preserves the game-relative source layout, and regenerates `manifest.json`. It does not commit, push, build, or control the game.
