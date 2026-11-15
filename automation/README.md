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

The entry point builds a missing/stale native bridge and missing executable/runtime outputs, logs in or reuses the monitored game, validates/reloads the game-only input bridge, and starts persistent control. It enables tactical skills, HP/DS supplies, known-popup checks and bounded Codex repair. It detects an existing session controller rather than creating duplicate input. Normal control runs in Python without AI calls; source repair needs an installed, authenticated Codex CLI. Use `--no-codex-repair` or `--no-battle-space` to disable those respective modes, and `--max-cycles 3` for a finite check. This does not download original game inputs, install system build tools, or supply private credentials.

Inspect or stop without setup/login/input:

```bash
uv run --locked automation.py --status
uv run --locked automation.py --stop
```

For background/minimized operation, the same entry loads a bridge with `native_background_input: true` and `native_capture: true`; status reports `background_input_enabled: true`. Input and framebuffer screenshots do not activate the game. An older installation needs one rebuild/restart/login, handled by the entry when private credentials and build tools are ready. Keep the desktop session, game process and OpenGL context running. This is not a headless mode, and logout/suspend operation is not promised. Legacy bridges retain focus/capture guards until reloaded.

A live four-cycle check stayed minimized/unfocused, closed the known local popup and moved with changing native screenshots (four actions, three progress events). Capture is followed by fresh PID/map/quest validation before click or movement. This verifies that observed background workflow, not every objective; the game-derived close template and private session proof are excluded from this source kit.

The explicit build steps below remain available for diagnosis or a manual setup:

```bash
cd "/path/to/DW3 Online"
uv sync --locked
uv run --locked python linux/native/build.py
bash linux/native/build-executable.sh
./DW3-Online-Linux --check
```

The Python lock supplies Pillow. Build/runtime dependencies remain separate: Linux x86_64, JDK 21 tools, GCC, Android SDK `apksigner`, the matching original APK, Linux LWJGL native JARs, and a running graphical desktop/OpenGL context. Legacy window lookup/focus/capture requires `xwininfo`, `xprop`, and libX11; the current native input/capture path does not open an X11 control connection. Routine keys and popup clicks use private game callbacks; libXtst and desktop keyboard/mouse injection are not required. See the port playbook for Linux-port preparation; the original Windows runtime cannot run on Linux.

The former host XTest path could trigger GNOME's Remote Desktop permission dialog during battle input. The maintained controller sends allowlisted keys through the game's GLFW callback and clicks through its input processor in window-local coordinates. It does not move the host pointer or request desktop sharing for those actions. `status` must report `native_key_input` and `native_click_input: true`; an older loaded bridge fails instead of falling back to host input.

After updating sources on an existing installation, stop the supervisor, build, and restart the monitored game to load the new bridge:

```bash
uv run --locked autoplay.py --stop
uv sync --locked
uv run --locked python linux/native/build.py
uv run --locked python ai-game.py login --restart
uv run --locked python ai-game.py status
```

Run these commands in the installed game directory. The restart closes that monitored game and logs in again; configure private credentials first. Verify the capability fields and intended PID before resuming. Map/session and modal guards remain; legacy bridges retain the focus guard.

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

To enable active-combat skill/item decisions with the current native bridge, explicitly add `--battle-space`. This flag retains its historical name; old direct supervisors without the tactical capability retain selected-option Space compatibility. Optional `--repair-with-codex` requires a separately installed, authenticated Codex CLI; normal control does not require an AI service. Both capabilities and their limits are described in [README-AUTOPLAY.md](files/README-AUTOPLAY.md) and [AI-GAME-CONTROL.md](files/AI-GAME-CONTROL.md).

```bash
uv run --locked python autoplay.py --resume --battle-space
uv run --locked python autoplay.py --status
uv run --locked python autoplay.py --stop
```

There is no default time limit. `--max-cycles 3` gives a bounded run. Invalid state, unsupported objectives, incomplete telemetry and story choices can pause the controller; legacy bridges also pause on focus loss. A running process does not prove quest progress or guarantee completion of every quest. Stop commands act on the monitored session; specify `--session /original/session/path` if `latest` has changed.

If startup opens the game but movement stops, inspect `uv run --locked automation.py --status`. Resized-window captures now refresh geometry and trap X11 errors as a recoverable `window_unavailable` pause; restore/focus that window when using the legacy capture path. The planner can make a short clear-foot escape from its extra collision margin only when it lands back in full padded clearance. Missing routes remain bounded stops, and blocked cached routes back off for 60 seconds. These changes recovered the recorded startup case without weakening normal terrain checks.

NPC recovery selects a validated clear approach within interaction range instead of routing into a blocked NPC center. It retains facing/actual-distance checks, rejects stale GPS counts as arrival evidence, and backs off expected no-route cases without a code-repair worker. The old corner passed a real-atlas simulation; later live automation crossed maps and advanced chapter 9 step 2→3. This does not guarantee every objective will proceed without a pause.

Map and quest exports must be generated locally, after login, when wanted:

```bash
uv run --locked python ai-game.py export-world
uv run --locked python quest_catalog.py export
```

Exported `linux/world/` and `linux/quest-catalog/` files contain data from your original game and are intentionally absent from the repository. Local guides mention historical diagnostics and screenshots that are also intentionally excluded. The optional popup-close template is not distributed; exact template matching requires a locally supplied template, otherwise the existing dismissal command uses its documented fallback.

The supervisor checks a locally supplied close template before movement and at most once every two seconds, sends a guarded game-only click, and verifies marker disappearance before clearing navigation backoff. Missing templates skip automatic detection. Unknown dialogs and story choices are not automatically recognized.


## Automatic inn recovery

`uv run --locked automation.py` also watches the complete party, including reserves. If any Digimon has HP zero, recovery takes priority over quest walking after active battles have been handled. Unknown party telemetry waits. The controller selects the nearest estimated reachable inn from bundled world-map hints and collision paths; it does not choose the cheapest inn. Locked or unusable routes can pause recovery.

At the inn it advances a catalog-matched innkeeper greeting, waits for the genuine inn offer, checks the server-provided BIT price against the wallet, and confirms the selected stay option once with normal Space. Insufficient BIT or an unconfirmed revival pauses instead of repeating purchases. Quest control resumes only after every party member has HP above zero, the inn UI has closed, and world movement is ready. No revival item, cash purchase or direct HP write is used. Inspect `inn-recovery.json` and the supervisor state/events for progress and pause reasons.

A live Forest Inn stay was verified: the server charged 1,520 BIT (52,435 → 50,915; Cash remained zero), Agumon, Palmon and Renamon ended at HP 2,462, 1,202 and 2,002 respectively, and quest control resumed. The initial innkeeper approach was assisted after a distance/facing loop; subsequent greeting pages, genuine offer, payment and revival ran through automation. The approach now uses the client's exact interaction/facing predicate with regression fixtures. A complete unassisted travel-to-revival loop has not yet been verified.


## Tests

The default no-progress watchdog can launch non-interactive `codex exec` after repeated navigation or modal-guard failures (60 seconds without progress), or an eligible idle story (180 seconds). Its prompt arrives on stdin; the worker reads a bounded credential-filtered game-state log, adds a regression and must pass the full suite before reload. It never launches the interactive Codex terminal UI. Normal combat, typing, choices, loading and insufficient funds do not qualify. Worker runtime and repair attempt/cooldown limits remain bounded.

The repair worker uses this command shape automatically, with the generated prompt file connected to stdin:

```bash
codex --sandbox workspace-write --ask-for-approval on-request \
  -c approvals_reviewer=auto_review exec --skip-git-repo-check \
  --cd "$GAME_ROOT" -o "$REPAIR_DIR/report.md" - < "$REPAIR_DIR/prompt.txt"
```

Run `uv run --locked automation.py` from the installed game directory to use the complete controller. No interactive Codex terminal input is needed. Inspect `repair-state.json` for worker and verification results. Queued modal repairs are dropped when the modal closes or changes. Saturated movement backoff cannot prevent a rejected-route refresh; the 30-second GPS rate limit and 60-second local-recovery exclusion remain enforced.

Installer tests run without game files or a desktop:

```bash
uv run --no-project python -B -m unittest discover -s automation/tests -v
```

After installing into your own prepared game, building the adapter/runtime, and exporting the local map/NPC metadata, run its complete suite there:

```bash
uv run --locked python -B -m unittest discover -s linux/native/tests -p 'test_*.py' -q
```

The complete suite includes original-client and built-Java integration checks. A source-only checkout cannot satisfy those inputs. Synthetic policy, movement, and UI fixtures do not send game input. A live navigation repair used non-interactive Codex with 96 filtered snapshots and a stdin prompt. The worker exited zero, parent verification passed 251 tests and automation reloaded; fresh game state then confirmed movement from s650 to s655. A second worker fixed the corresponding NPC-route case, passed 258 parent verification tests and reached the NPC story interaction on s655. These observations establish both automatic repair cycles. Installer checks include a strict allowlist for reviewed JSON replay fixtures. A completed background story no longer blocks active combat; unfinished stories and choices retain their input guards. The live inn stay above verified the normal BIT fee, full party revival and resumed quest control; its first innkeeper interaction was assisted before correcting the approach predicate. Live results belong to the original inspected installation; verify your own setup separately.

## Maintainers

Refresh only the reviewed sources from an explicit workspace, then rerun installer tests and inspect the diff:

```bash
uv run --no-project python -B automation/refresh_payload.py --workspace "/path/to/DW3 Online"
uv run --no-project python -B -m unittest discover -s automation/tests -v
```

The generator takes the public root `AI-SETUP.md` and playbook copies from this repository, preserves the game-relative source layout, and regenerates `manifest.json`. It does not commit, push, build, or control the game.

## Tactical skills and supplies

The current one-command entry upgrades the monitored bridge to expose verified battle options and HP/DS inventory/shop telemetry. The Python planner selects enabled affordable skills, useful battle items and living reserves for forced switches. It learns bounded observed enemy HP-loss comparisons, which can include other combatants or status effects. Skill animation/range values are not damage power; the inspected client does not establish a server damage formula.

World recovery uses owned HP/DS items before restocking. It targets three recovery items of each type, purchases at most five at once, and caps each restock at min(10% starting BIT, 5,000 BIT, wallet minus a 5,000 BIT reserve). Every step rechecks the live shop price, wallet and menu token. Purchases require confirmed stock gain and BIT loss; item use requires inventory loss and HP/DS gain. Unconfirmed operations back off rather than repeating purchases. Cash and permanent-stat items are excluded.

See [the runtime guide](files/README-AUTOPLAY.md), [battle evidence](files/docs/battle-research.md), and [item/shop evidence](files/docs/item-shop-research.md). Native snapshots and normal menu handlers are tested with isolated fixtures; live evidence is recorded separately in the runtime guide. These controls still depend on the original prepared game and an active desktop/OpenGL session.

The combat-efficiency correction prefers a conservative normal-attack finisher, establishes a basic baseline before skill exploration and separates terminal kill bounds from uncensored HP-loss samples. Routine party HP/DS recovery happens after combat; only useful active-fighter emergency healing can occur during battle, with an accepted offensive command required before another item. The guard survives restart and incomplete menu telemetry.

The [AI battle model draft](files/docs/AI-BATTLE-MODEL-DRAFT.md) is a proposal only. No new AI model or training process is enabled.
