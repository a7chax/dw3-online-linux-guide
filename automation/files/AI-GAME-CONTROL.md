# Control the Game from Live State

This local controller uses the Linux Java game client. It reads the game's actual GPS route and sends normal movement input. It does not change movement speed.

Use [README-AUTOPLAY.md](README-AUTOPLAY.md) for the short start/stop procedure. Install the locked Python environment from this directory with `uv sync --locked`; run Python commands through `uv run --locked`. The lock pins Pillow 12.1.1. Java and the existing X11 desktop tools are still required by the game and window controls.


## Automatic inn recovery

`uv run --locked automation.py` also watches the complete party, including reserves. If any Digimon has HP zero, recovery takes priority over quest walking after active battles have been handled. Unknown party telemetry waits. The controller selects the nearest estimated reachable inn from bundled world-map hints and collision paths; it does not choose the cheapest inn. Locked or unusable routes can pause recovery.

At the inn it advances a catalog-matched innkeeper greeting, waits for the genuine inn offer, checks the server-provided BIT price against the wallet, and confirms the selected stay option once with normal Space. Insufficient BIT or an unconfirmed revival pauses instead of repeating purchases. Quest control resumes only after every party member has HP above zero, the inn UI has closed, and world movement is ready. No revival item, cash purchase or direct HP write is used. Inspect `inn-recovery.json` and the supervisor state/events for progress and pause reasons.

A live Forest Inn stay was verified: the server charged 1,520 BIT (52,435 → 50,915; Cash remained zero), Agumon, Palmon and Renamon ended at HP 2,462, 1,202 and 2,002 respectively, and quest control resumed. The initial innkeeper approach was assisted after a distance/facing loop; subsequent greeting pages, genuine offer, payment and revival ran through automation. The approach now uses the client's exact interaction/facing predicate with regression fixtures. A complete unassisted travel-to-revival loop has not yet been verified.


## Start everything with one command

After installing the current source kit beside the original game files, run:

```bash
uv run --locked automation.py
```

The entry point builds a missing/stale native bridge and missing executable/runtime outputs, logs in or reuses the monitored world, checks game-only input capabilities, and starts persistent control. It can restart a stale monitored bridge to load the current classes. It enables tactical battle skills/items, HP/DS supplies, known-popup dismissal, and bounded Codex repair. It detects an existing session controller rather than starting duplicate input.

The original game/APK, Linux build/desktop dependencies, and one-time private credentials are still required. Configure `.env` from `.env.example` locally. Codex must be installed/authenticated for source repair; add `--no-codex-repair` to disable it. Add `--no-battle-space` to wait through ongoing combat, or `--max-cycles 3` for a finite check. Normal movement and interaction run without AI calls. This command supervises supported states; unknown objectives and story choices can pause it. Legacy bridges also pause on lost focus.

Inspect or stop without setup, login or game input:

```bash
uv run --locked automation.py --status
uv run --locked automation.py --stop
```

## Continue while minimized

Use the same one-command entry. With `native_background_input: true` and `native_capture: true`, input and screenshots stay inside the game without focus or desktop activation. `autoplay-state.json` reports `background_input_enabled: true`; the client keeps updating while minimized. The entry upgrades an older bridge with a rebuild and one monitored restart/login using the private credential setup. Verify those loaded capabilities before relying on background operation.

You may minimize the game or use another application. Keep the desktop session, game process and OpenGL context running. This is background desktop operation, not a headless client; logout, suspend and a lost graphics context are not covered. PID/map/session/modal checks, controller ownership and bounded actions remain enforced. Legacy bridges keep their focus guard and X11 capture behavior until reloaded.

Verified live: a four-cycle run stayed minimized and unfocused before and after, made four actions with three progress events, closed the known popup, and moved the character. Its 834×615 native screenshot changed during the run, confirming fresh rendering rather than a static image. This verifies the observed background workflow, not every quest or operation after logout/suspend.

## Start and log in manually

If the window opens but the character does not move, check `uv run --locked automation.py --status` and `autoplay-events.jsonl`. With a current background-capable bridge, minimized/unfocused input uses the private game connection. On a legacy bridge, restore/focus the intended game for `window_unavailable` or `focus_lost`; a window pause does not request Codex repair. Legacy X11 screenshots query actual geometry and trap errors locally. Previously a cached 1280×720 size against an actual 834×615 window caused an XGetImage error that could terminate Python.

The local planner also handles a valid foot pixel that lies outside its extra body-clearance margin. It permits only a bounded 50–175-ms escape through clear foot pixels, including a 17-ms release guard, when both normal and guard landings restore full padded clearance. This is a recovery from a conservative margin, not permission to cross blocked terrain. `local_route_unavailable` is a normal bounded navigation result. A blocked cached endpoint gets a 60-second retry backoff, avoiding rapid repeated path searches. Keep dynamic obstacles and unknown exits as unresolved when no route is found.

1. Open a terminal in this game directory.
2. Run:

   ```bash
   uv run --locked python ai-game.py login
   ```

3. Credentials are read from the private `.env` when configured. If no password is configured, enter it at the hidden prompt.
4. Wait for `Selected character` and the world position.

The script reuses an existing monitored world. Use `--restart` only when you need to load a rebuilt bridge. Each new game session requires login. The script replaces login fields exactly, selects the Asia server, and selects the requested character.

Your local `.env` stores `DW3_USERNAME`, `DW3_PASSWORD`, `DW3_SERVER`, and `DW3_CHARACTER`. It has mode `0600` and is ignored by Git. Share `.env.example`, which contains placeholders, instead. Explicit command arguments override process environment, which overrides `.env`. The parser reads literal values without executing shell expressions. With `.env` configured, `uv run --locked python ai-game.py login` performs login without another password prompt.

## Load game-only keyboard and mouse input

The former host XTest keyboard path could trigger GNOME's Remote Desktop permission dialog during battle input. The current controller sends allowlisted keys (`space`, `enter`, `g`, `x`) through the game's private bridge to its own GLFW callback. Popup clicks go directly to the game's input processor in window-local coordinates. These operations do not inject desktop keys/mouse events, move the host pointer, or request desktop sharing. Window discovery and legacy focus/capture use local X11; current bridge capture reads the game framebuffer without activating the window.

The running bridge must report `native_key_input` and `native_click_input: true`. An older JVM fails with a rebuild/restart message instead of falling back to host input. After installing the current sources, stop the supervisor and rebuild/restart the monitored game deliberately:

```bash
uv run --locked autoplay.py --stop
uv sync --locked
uv run --locked python linux/native/build.py
uv run --locked python ai-game.py login --restart
uv run --locked python ai-game.py status
```

The restart closes the monitored game and logs in again using the private credential setup. Recheck the capability fields, world state and intended PID before resuming autoplay. Normal input retains world/PID/map guards and the legacy focus guard when background capability is absent and guaranteed key/button release cleanup, including after a caller timeout. The new path has isolated fixtures; verify its observable behavior on the rebuilt client before claiming a live result.

## Direct supervisor commands (advanced)

For the supported navigation and interaction loop, start the persistent supervisor:

The one-command entry point above handles setup/login first. Use the direct commands below when an appropriate monitored world is already running.

```bash
uv run --locked autoplay.py --resume --battle-space --repair-with-codex
```

It has no default deadline and stays running until stopped. It reuses the monitored logged-in game. `--resume` clears an earlier stop request; it does not log in or restart the game.

Normal navigation and interaction run in Python without an AI service. `--repair-with-codex` optionally enables a Codex source-repair worker after repeated controller failures; omit that flag to keep repairs manual. See the repair section below for its limits.

To leave it running in the background after this terminal command returns:

```bash
nohup uv run --locked python -u -B autoplay.py --resume --battle-space --repair-with-codex > linux/ai-sessions/latest/autoplay.log 2>&1 < /dev/null &
```

Inspect or stop it without loading game controls or sending game input:

```bash
uv run --locked autoplay.py --status
uv run --locked autoplay.py --stop
```

The process pins the resolved session directory when it starts. If `latest` later points to a new game session, use `--session` with the old resolved directory for that supervisor's status or stop command. Optional `--pid` binds it to a particular game process. A second supervisor for the same session is rejected. For a finite verification run, use `--max-cycles 3`; omit that flag for persistent operation.

The supervisor reads fresh world and quest state before choosing each action. It follows usable GPS routes, can try the local collision atlas after a stalled GPS segment, advances ordinary reported dialogue, and sends one normal Space input when complete story/battle-result telemetry says it is ready. Ready story/result pages keep their normal input pacing even when the character and quest coordinates stay unchanged. Empty enabled GPS routes get a delayed refresh attempt and retry backoff. With the default settings, ongoing combat waits unless a reported result is ready to close.

The command above enables `--battle-space`, which now selects enabled affordable skills and useful battle items on a bridge advertising `native_battle_control`. It uses guarded original menu selection/target/confirm handlers, unique menu-generation tokens and a 10% maximum-DS reserve for ordinary skill use. A known affordable finisher may use that reserve when needed. Normal-attack estimates are checked before spending DS or opening items; routine healing follows battle, and emergency active healing cannot replace consecutive offensive turns. The inspected client exposes DS cost and animation/range metadata, not a verified damage formula; skill comparisons use explicitly non-causal observed HP-loss samples. Normal Space acknowledges ready results. A legacy direct supervisor without this capability retains selected-option Space. Omit the flag to wait through ongoing combat. Check `tactical_battle_enabled` and `battle-decisions.json`.

`automation.py` also enables guarded normal inventory HP/DS use and bounded BIT restocking; see [README-AUTOPLAY.md](README-AUTOPLAY.md). Runtime prices, quantity, wallet reserve and inventory/resource confirmations are mandatory. Inspect `supplies-recovery.json` for failures and backoff. No cash, permanent-stat purchases or HP/DS/currency writes are part of this policy.

When an observed battle ends with an enabled but empty GPS route and `has_reply: false`, the updated supervisor requests one immediate GPS refresh instead of waiting the usual ten seconds. It then allows two seconds for the reply. If the reply remains absent, it can recover toward a previously observed endpoint through the collision atlas, provided the game PID, map, quest chapter/step and target map are unchanged. It validates the local path before movement, stops short of a cached NPC target for facing/talking, and retains bounded crossing at an exit. The validated cache is stored in the pinned session as `autoplay-route-cache.json`, so a supervisor restart can retain the same-context route and pending-battle marker. It cannot invent a route when none was observed. Modal/session guards still apply; the legacy focus guard applies without background capability. Inspect `post_battle_recovery`, `cached_route_available`, and reasons such as `post_battle_gps_refresh`, `post_battle_cached_route`, or `cached_route_blocked` in the saved state/events.

For nearby type-2 NPC/terminal targets, arrival includes facing. Within 24 world units, the supervisor makes one 50-millisecond alignment move when farther than 16 units or facing away from the endpoint, then attempts talking when aligned. It avoids another push when already within 16 units and correctly facing. If collision prevents at least two units of movement but the character is correctly facing the same endpoint, a 30-second boundary fallback permits the normal interaction within 24 units. Repeated identical failed alignment attempts are suppressed for 30 seconds, with the usual no-progress backoff. The new alignment path has fixture coverage; the Station terminal was opened in the live check using a deliberate manual alignment, so that observation is not proof of the new automatic alignment path.

Local and cached NPC recovery now select a validated clear approach strictly within 24 world units using a bounded search, rather than planning into the NPC's blocked center. They preserve the actual `interaction_target`, use `cross_map: false`, and stop based on distance to that NPC instead of the generic eight-unit waypoint tolerance. Nearby interaction uses measured distance even when the GPS step count is stale. Missing approaches return `NoRouteError` and bounded navigation/backoff rather than triggering Codex repair. The earlier blocked-center failure did start a worker; its accepted change made blocked goals an expected no-route result, but verification was interrupted, so a complete automatic repair/restart remains unverified.

The original corner now passes a real-atlas movement simulation; that is separate from live replay of the old NPC position. A later four-cycle live run crossed `s255` → `s237` → `s202`, and resumed unlimited automation advanced chapter 9 from step 2 to step 3. These observations verify the observed recovery/progression, not every NPC or quest.

When `native_background_input: true` is loaded, the supervisor sends game-local input without focusing or activating the window, including while minimized. Stale/missing state, login/loading screens, a different PID/session, story choices, incomplete telemetry and unsupported objectives still pause it. Older bridges acquire focus once and pause when focus is lost; refocus that same game to clear the legacy pause. The supervisor does not repeatedly reclaim focus. A changed session/PID needs a deliberate new supervisor binding. A running or paused process is not proof that a quest is progressing. `progress_events` counts changes in a broader position/map/dialogue state fingerprint, not completed quest steps.

Use the current session's `autoplay-state.json` to see the PID, mode, reason, action, quest, and counters. `autoplay-events.jsonl` records state changes; `autoplay-actions.log` records bounded action output. `autoplay.stop` is the stop flag and `autoplay.lock` prevents duplicate supervisors. Stop requests are checked between short input actions. This is persistent supervision of supported states, not a guarantee of completing every quest or handling every battle.

`--scene-target CHAPTER:STEP:MAP` explicitly permits the bounded manual scene macro for a particular unhooked `enter`/`zone` objective. Space can confirm choices. Prefer complete read-only story telemetry; use that override only for an inspected scene within the requested action.

Live verification on 14 November 2026 moved from `s445` into `s440` during a deliberate three-cycle supervisor test. A separate persistent run stayed alive through 116 cycles and six actions, paused on lost focus, and resumed after focus returned. A stop request produced `active: false` and `reason: stop_requested`. A previously displayed Victory result was closed with normal Space before walking resumed; these historical checks did not exercise the new combat-Space mode. These checks verify the observed supported loop, not completion of every objective.

## Optional Codex repair

With `--repair-with-codex`, three observations of the same eligible controller failure can start one repair worker. Eligible reasons are `action_failed`, `unknown_action`, and `local_recovery_failed`. Lost focus, ongoing combat, story choices, and ordinary waiting do not trigger a repair. The parent pauses input while the worker uses an allowlisted diagnostic context to fix the narrow Python problem and add regression coverage. The worker must not control the game, read credentials, alter Java/native components, or publish changes.

Codex must already be installed and authenticated. Its worker uses workspace-write sandboxing and on-request approvals with automatic approval review; an approval requirement can leave it waiting. A worker's successful exit alone is insufficient: source changes must pass the full locked regression suite before the supervisor restarts with the same pinned session and game PID. This restarts the Python supervisor, not the game. Failed repairs remain reported for inspection. Limits are one attempt per failure fingerprint, at most three workers per session, and ten minutes between workers.

Read `repair-state.json` for status and `repairs/NNN-*/` for `context.json`, `report.md`, `worker.log`, and `verification.log`. The context excludes `.env`, dialogue, exception messages, and raw session logs; do not manually add secrets. A stop request also interrupts a running worker. The repair policy has fixture coverage; a genuine live failure followed by a successful autonomous repair has not yet been demonstrated.

A real repair worker later proposed `NoRouteError` handling, which was reviewed and accepted for bounded `local_route_unavailable` results. A stop request interrupted verification, so that run does not establish the complete automatic repair/test/restart chain. Such a stop is recorded as `repair_interrupted`, even when the worker process exited successfully.

## Close a visible popup

Persistent mode checks for the known close icon before movement on its first cycle and at most once every two seconds afterward. With a local `linux/ui/popup-close.png` template, it sends a guarded game-only click and captures `after-popup-close.png`; disappearance of the marker resets navigation backoff. An absent template skips automatic detection. This recognizes that exact local icon, not arbitrary dialogs or choices. The public source kit does not distribute the game-derived template.

Capture can take longer than a state sample remains fresh. After capture, the controller polls again and validates PID/map/quest context before a popup click or subsequent following. A slow image must not authorize input against the old sampled state. Native capture with lost capabilities, stale status or an invalid reply pauses with `WindowUnavailable`; it does not switch to host capture or activate the window.

If a popup covers the world, run:

```bash
uv run --locked python ai-game.py dismiss
```

This captures the screen, detects the known popup-close icon and clicks its visible X. If that icon is absent, it tries the game's X key. It saves `linux/ai-sessions/latest/after-dismiss.png`; inspect that image to confirm closure. Unknown or scaled popups may require inspection.

## Follow the GPS trace

Ensure GPS is enabled and its dotted route is visible. Then run:

```bash
uv run --locked python ai-game.py follow --seconds 10
```

Add `--continuous` to continue after map changes. Nearby NPC interaction targets stop with `interaction_required`.

For local navigation without GPS dots, and reading the main quest, see [WORLD-ATLAS.md](WORLD-ATLAS.md).

With `native_background_input: true`, following does not activate the game and can continue unfocused/minimized. Older bridges require focus and stop on focus loss. Use the stop command or Ctrl+C in the controlling terminal to stop background-capable following. Each movement lasts at most 175 milliseconds. The controller reads the next position and route after each movement, usually several times a second. It stops on its time limit, map/screen changes or stale state, and on focus loss only for a legacy bridge.

A point within eight world units counts as reached. At a GPS endpoint, the controller aims toward the remaining endpoint vector (or the final route segment when already at the point), then keeps that heading for a bounded crossing attempt in 100-millisecond bursts for up to two seconds. It checks for a new map after each burst. If the route is missing, it first waits up to 2.5 seconds for route data, then makes the same bounded forward attempt if no route arrives. With no usable route, the fallback follows the character's current heading; neither attempt proves an exit exists in that direction. Diagonal facing uses native diagonal input when the loaded bridge advertises it, otherwise alternating cardinal movements. A successful crossing reports `reason: map_changed`; the `before.map` and `current.map` fields identify the maps. It stops after that crossing. Run the follow command again to follow the route on the new map.

The movement watcher detects tiny bumps, insufficient progress along the requested direction, and short back-and-forth loops. It remembers failed directions for six seconds near the same position, then lets collision-aware steering choose a different clear direction. This avoids immediately repeating the same blocked burst. With terrain data it uses a short 50-ms recovery pause; the legacy fallback waits longer for route refresh. It keeps polling while waiting. No useful movement for six seconds stops with `unable_to_advance`; a GPS segment with no clear steering candidate can hand off to local-atlas recovery sooner. A forward attempt without a map transfer stops after two seconds with `no_map_exit_detected`. If a popup appears, stop, inspect the screenshot, dismiss it, and continue.

An updated bridge advertises eight `movement_directions`, including native diagonals such as `down_right`. With the exported atlas available, the controller checks each normal burst against collision pixels and allows 17 milliseconds for frame/release timing. It can back away from a corner before turning. Local navigation also replans after two failed bursts. Older bridges retain the original cardinal fallback until reloaded.

The local planner reuses grid/collision work instead of checking every long candidate segment repeatedly. In one 294-point route benchmark, planning fell from approximately 1.95–2.19 seconds and 35,022 clearance checks to 1.1 milliseconds and three checks. This measures that fixture, not every route. Inspect `blocked_directions`, `redirects`, and `planner_ms` in `follow-state.json`; the last field measures the latest steering calculation, while `local-path.json` records the initial full-path planning time.

Live recovery on `s465` was verified from the recorded stuck bridge position: a left backoff exposed a clear diagonal path, and the controller reached Shaman House (`s475`) without another `unable_to_advance` stop. A real blocked door or temporary obstacle can still require inspection; recovery preserves the bounds and capability-appropriate guards.

For one short movement:

```bash
uv run --locked python ai-game.py move right --milliseconds 150
```

## Advance an interaction or story scene

Inspect the current screen, then use one normal Space interaction:

```bash
uv run --locked python ai-game.py interact
```

For ordinary NPC dialogue, use `uv run --locked python ai-game.py talk --seconds 30 --max-pages 12`. It waits for the reported page to finish typing before pressing Space.

Story scenes use a separate client system and may not appear in the ordinary dialogue state. For a scene you have inspected and want to advance, run:

```bash
uv run --locked python ai-game.py scene --seconds 60 --max-presses 30
```

This explicit macro presses normal Space at most once per second. It requires fresh world and quest state. Background-capable bridges do not activate the window; legacy bridges focus once and stop on focus loss. It also stops on quest progress, map/session changes, invalid state, or its time/press limit. Space can confirm choices; the macro does not detect scenes or choices. Inspect the screen before using it. It saves `before-scene.png`, `after-scene.png`, and `scene-state.json` in the current session. Check the before/current quest chapter and step to verify completion.

Live verification reached Shaman House and advanced its story with 18 normal Space presses: chapter 5 changed from step 2 to step 3, targeting Protocol Ruins (`s375`). That run used a bounded prototype macro; the reusable `scene` command has separate fixture coverage and has not been used to advance another objective. Evidence is saved locally under `linux/diagnostics/next-quest-step/`.

## Read the files

| File under `linux/ai-sessions/latest/` | Contents |
| --- | --- |
| `state.json` | Latest position, movement state, and GPS route; refreshed about every 100 ms. |
| `state-events.jsonl` | Position and route changes over time. |
| `follow-state.json` | Latest follow run: starting state, current state, burst count, active flag, movement mode and stop reason. |
| `last-move.json` | Before/after state for the latest movement. |
| `scene-state.json` | Bounded Space run: before/current state, press count, screenshots, and stop reason. |
| `autoplay-state.json` | Persistent supervisor PID, action, quest, mode, pause reason and counters. |
| `autoplay-events.jsonl` | Changes in the persistent supervisor state. |
| `autoplay-actions.log` | Output from the supervisor's bounded actions. |
| `autoplay-route-cache.json` | Validated same-context endpoint and pending-battle marker for route recovery. |
| `repair-state.json` | Optional Codex worker status, attempts and verification result. |
| `repairs/NNN-*/` | Allowlisted repair context, worker report/log and regression output. |
| `control.sock` | Private local command socket. |

The `trace` object in a world state contains:

- `enabled`: whether GPS is enabled.
- `auto_walk`: whether the game's own auto-walk mode is active.
- `route_type`: the client's numeric route type. Types 0 and 4 are not usable for this controller.
- `steps_remaining`: the game's GPS step count.
- `points`: remaining GPS dots as `[x, y]` pairs in world coordinates, sampled seven units apart.

The observer calls only the inspected read-only GPS accessors. It does not advance the game's auto-walk cursor. The controller uses the dots to choose short arrow-key bursts, then checks the resulting coordinates. It does not enable or bypass the game's built-in auto-walk eligibility rules.

## Instructions for Codex or Claude Code

1. Read this file and `GAME-STATE-PRINTING.md`.
2. Run `uv run --locked python ai-game.py status`. Confirm `phase` is `world` and the timestamp is fresh.
3. Inspect a screenshot before moving. Use `uv run --locked python game-control.py screenshot /tmp/dw3-screen.png`.
4. If a popup is visible, run `uv run --locked python ai-game.py dismiss` and inspect `after-dismiss.png`.
5. Check `trace.enabled`, `trace.points`, and `trace.steps_remaining`.
6. Run a bounded follow command, such as `uv run --locked python ai-game.py follow --seconds 5`.
7. Read `follow-state.json`. Compare the starting and current positions and GPS counts. Inspect another screenshot when the map changes, movement stops, or the route becomes unavailable.
8. State what actually happened. A pressed key alone is not proof of movement, and fewer steps do not prove quest completion.

Use the REA reverse-engineering skill when adapting the observer to a different client version. Use systematic debugging and verification before completion for fixes. Ordinary use needs the locked uv Python environment and existing X11 desktop tools. REA is needed for adapter/version analysis; an AI service is used only when the optional Codex repair path is enabled and triggered.

## Verification

A live eight-second run on 14 November 2026 followed the Bulk Bridge trace on map `s450`. The GPS count decreased from 68 to 21, and position changed from `(846.5, 587.5)` to approximately `(989.34, 262.50)`. The popup was closed before walking. These observations demonstrate route progress, not completion of the entire quest.

The final build was then tested from `(989.5, 262.5)`. It made 19 short movements, reduced the GPS count from 20 to 1, and stopped at approximately `(839.42, 137.27)`, within eight world units of the endpoint `(834, 134)`.

After the recovery and map-crossing update, a live run started at `(962.27, 474.57)` on `s450` (Bulk Bridge). It made 52 movements around the bank, crossed to `s465` (Tranquil Swamp) at `(1180.5, 582.5)`, and stopped with `map_changed`. The saved state confirmed the map ID change. Endpoint forward movement and transition timing races are also covered by regression fixtures.

Run the regression checks:

```bash
uv run --locked python -m unittest discover -s linux/native/tests -p 'test_*.py' -v
```

The delayed key-release check binds an isolated local Unix socket. Restricted environments must allow that local socket operation. The tests cover the runtime charset, concurrent profiles, live-state output, GPS fields, stale states, bends, nearby endpoints and delayed release after a render timeout.

The earlier locked uv suite passed **127 tests in 25.791 seconds**. A two-cycle live run moved through the `s400` corridor and stopped movement correctly when battle began (`09-fast-uv-live-check.json`); a bounded normal Space check then closed the battle (`10-battle-space-live-check.json`). The requested persistent uv launch with both opt-in flags is recorded in `11-uv-persistent-launch.json`, under `linux/diagnostics/autoplay/`.

That persistent process then handled a new random battle without additional AI/operator game input: following stopped at `battle_active`, cycles 3–6 sent guarded normal combat Space, cycles 7–8 acknowledged ready results, and following resumed to approximately `(337.8, 324.7)` on `s400`. `13-autonomous-random-battle-proof.json` records the process-specific events and resulting state; `12-final-uv-enabled-state.json` confirms both opt-in flags. This verifies the observed selected-option combat flow, not tactical play or every encounter. A later non-interactive repair completed worker execution, full parent verification and automatic reload, with observed movement from s650 to s655; see the runtime guide for that separate evidence.

This controller supports only the inspected client version 0.1.95. Its files remain local; publishing the new controller is a separate step.

Publication verification: the post-battle recovery update passed **133 controller tests** under uv. The exact source-kit payload was installed into an isolated temporary game layout and passed the same 133 tests using local original inputs. Its separate source installer passed **eight tests**. No credentials, original game binaries, map/dialogue exports, screenshots, or private sessions are included in the public kit.

Game-local input verification: the corrected popup command removed the visible Halloween panel; its close marker disappeared in the saved after image. The new key operation changed live GPS from enabled to disabled and back to enabled. The Python input helper no longer invokes XTest, and legacy login uses the local control bridge. These checks validate game-local input; an already-open GNOME sharing dialog can be cancelled instead of granting desktop sharing.

Integrated entry-point verification: `uv run --locked automation.py --max-cycles 2 --no-codex-repair` reused the logged-in world, moved into the quest target map, and aligned at its NPC. The full suite at that stage passed **148 tests** under uv, including automatic known-popup checks before navigation and the one-command setup fixtures. The standalone source installer has eight separate passing tests.

The later startup fix was checked live with a deliberately oversized X11 capture: the error was trapped, then a subsequent capture succeeded. The one-command entry then completed two cycles from the stuck `s205` position `(776.5, 297.6646)` to `s330` near `(1209, 472.75)`, recording two actions and two progress events without AI game input. This verifies that observed capture/clearance-margin recovery; it does not establish every map connection or quest.
