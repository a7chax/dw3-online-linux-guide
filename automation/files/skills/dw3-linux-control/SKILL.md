---
name: dw3-linux-control
description: Operate the DW3 Online native Linux Java client through its local state and control scripts, inspect main-quest progress, and navigate exported map coordinates. Use for this game's existing Linux port and automation workflow.
---

# DW3 Linux Control

Run commands from the game directory containing `ai-game.py`, `world_map.py`, and `linux/`. Reuse the existing scripts and inspected client adapter; routine operation does not need another reverse-engineering pass. This is a Linux Java client, not Wine or an Android emulator.

Use `uv sync --locked` to install the project environment and `uv run --locked` for every Python command. Keep dependency changes in `pyproject.toml` and `uv.lock`; do not install into system Python. For a restricted environment with an unwritable uv cache, select a writable `UV_CACHE_DIR` without changing project dependencies.

## Look up quests without progressing the game

For all main quests, future steps, or a request explicitly excluding progression, use the offline catalog instead of interacting with the game:

```bash
uv run --locked python quest_catalog.py list
uv run --locked python quest_catalog.py chapter 5
uv run --locked python quest_catalog.py export
```

`--json` works with `list` and `chapter`. Export writes `linux/quest-catalog/main-quests.json` and `main-quests.md`. The inspected definitions contain **36 chapters and 113 ordered steps**: 55 `talk`, 17 `enter`, 40 `zone`, and 1 `drop`. These are bundled requirements, not proof of completion or a complete server quest implementation. Preserve unknown titles, exact triggers, rewards, prerequisites, and battle targets/counts as unknown. Do not start live gameplay, autoplay, navigation or dialogue commands merely to look up the catalog.

If English names are missing, `uv run --locked python scripts/export-quest-text.py` reads exactly `text/en/places.json` and `talk0.json` through `talk10.json` using the original standalone asset reader. This was verified offline with all 12 files present, without credentials, login, or attaching to the game. Regenerate the catalog afterward. See the reference for source/provenance details.

## Inspect before acting

1. Run `uv run --locked python ai-game.py status`. Confirm a fresh timestamp, the intended PID/profile, and `phase: world` before movement. When supplied, `movement_ready: false` blocks movement even though the world screen is active. The live session is `linux/ai-sessions/latest/`; resolve that symlink again after a restart.
2. Run `uv run --locked python ai-game.py quest` when the task concerns the main quest. Read its objective and next action before choosing a destination or interaction.
3. Inspect a current screenshot when a popup, dialogue, or unexpected stop affects input:

   ```bash
   uv run --locked python game-control.py screenshot /tmp/dw3-screen.png
   ```

With current native capture/background capabilities, screenshots and input do not activate the window; a legacy screenshot path may require focus. Coordinate with an existing controller instead of taking focus during its run. Do not start a second controller to investigate the first.

Check `status.native_key_input` for `space`, `enter`, `g`, and `x`, and `native_click_input: true` before UI actions. Current keys/clicks use game-only bridge callbacks; host XTest injection previously caused GNOME Remote Desktop permission dialogs. Do not restore host-input fallbacks or approve desktop sharing as a workaround. Window selection and legacy focus/screenshots use local X11; current capture reads the game framebuffer. If the loaded bridge lacks the capabilities, stop the supervisor, run `uv run --locked python linux/native/build.py`, and perform the authorized monitored restart with `uv run --locked python ai-game.py login --restart`, then verify status. Building source alone does not update an existing JVM. Keep world/PID/map/modal guards, applicable legacy focus guards, and unconditional release cleanup.

Reuse an already logged-in world. If a monitored session needs starting or login, use `uv run --locked python ai-game.py login`. The user has authorized local credential configuration for this project: a private `.env` may contain `DW3_USERNAME`, `DW3_PASSWORD`, `DW3_SERVER`, and `DW3_CHARACTER`. Only the placeholder `.env.example` may be published; keep actual `.env` ignored and private (mode `600`). Do not inspect or print its values merely to check setup. Explicit username/server/character CLI flags override process environment, which overrides project `.env`, then existing defaults. The password uses process environment or `.env`, with a hidden prompt when absent; no password CLI argument is supported. The parser reads literal assignments, not shell code—never source the file. Keep actual secrets out of source, skills, command arguments, screenshots, logs, and Git. A bridge rebuild needs one client restart to load new Java classes; ordinary inspection does not. An unmonitored older JVM cannot be safely attached through this launcher.

## Persistent automation

When the user asks to keep playing until stopped, use the persistent supervisor rather than scheduling another AI turn for each bounded action:

```bash
uv run --locked automation.py
```

This entry point conditionally builds native/runtime outputs, performs private credential login or reuses a monitored world, validates game-only input capabilities, restarts a stale monitored bridge when required, and avoids duplicate session controllers. It defaults to combat Space, known-popup checks and bounded Codex repair. The original game/APK, installed build/desktop tools and initial private credential setup are still required. Entry options `--no-codex-repair` and `--no-battle-space` disable those modes; `--max-cycles N` bounds a deliberate check. Normal control remains Python without AI calls. `uv run --locked automation.py --status` and `--stop` do not perform setup/login or input. For an explicitly prepared world, the advanced direct equivalent is `uv run --locked autoplay.py --resume --battle-space --repair-with-codex`.

It has no default deadline. For a detached run, use `nohup uv run --locked python -u -B autoplay.py --resume --battle-space --repair-with-codex > linux/ai-sessions/latest/autoplay.log 2>&1 < /dev/null &`. Inspect with `uv run --locked autoplay.py --status`; request shutdown with `uv run --locked autoplay.py --stop`. The supervisor pins its resolved session, so supply `--session PATH` for that original session after `latest` changes. `--pid` can bind an intended game PID; `--max-cycles` is only for an intentionally finite check.

The supported loop uses fresh quest/world state, GPS/local recovery, reported dialogue, ready linear story pages, and ready battle-result screens. It waits on stale/loading/login/session changes, story choices, incomplete telemetry and unknown objectives; legacy bridges also pause on focus loss; ongoing combat waits unless `--battle-space` is explicitly enabled. With `native_background_input: true` it never activates the game; legacy bridges focus once and pause on lost focus. Check `autoplay-state.json` and its pause reason; staying alive is not quest progress. Use the [user guide](../../AI-GAME-CONTROL.md) and the reference for files and boundaries. A singleton supervisor lock and the existing input lease prevent duplicate control.

Normal operation is deterministic Python without AI calls. The optional `--repair-with-codex` flag starts a Codex source-repair worker only after three matching eligible controller failures; omit it for manual repairs. Focus pauses, combat waits and choices are not repair triggers. The worker receives allowlisted context, does no game input or credential access, and must produce narrow source changes plus regression coverage. Only a successful complete locked test suite permits restarting the supervisor with the original session/PID. Keep the worker's workspace-write sandbox and approval flow; do not bypass approvals. Limits are one attempt per failure fingerprint, three workers per session, and a ten-minute cooldown. Inspect `repair-state.json` and `repairs/NNN-*/` before reporting a repair. The repair policy is fixture-tested. A real worker later proposed accepted `NoRouteError` handling, but verification was interrupted by a stop request; do not claim the full automatic repair/restart chain succeeded. A stop during verification is `repair_interrupted`, even if the worker itself exited zero.

`--battle-space` is enabled in the command above because the user requested normal Space during random combat. Default behavior without it waits through active combat and acknowledges only ready results. The opt-in sends one normal Space per cycle only for complete active-battle telemetry with no transition/submission, with fresh PID/map/quest guards and the applicable legacy focus guard before input. It confirms the selected option, without tactical selection, item logic, VIP changes or an auto-battle bypass. Check `battle_space_enabled` and `codex_repair_enabled` in the saved supervisor state.

After an observed battle ends with empty enabled GPS and `has_reply: false`, recovery refreshes GPS immediately, waits two seconds for a reply, then may use a cached observed endpoint only for unchanged PID/map/quest chapter/step/target. It validates a local atlas path, preserves NPC stand-off/talking and bounded exit crossing, and never replays another map's route. Check `post_battle_recovery`, `cached_route_available`, and the state/event reasons. The session `autoplay-route-cache.json` persists the validated route and pending-battle marker across supervisor restarts; a new game/map/quest identity invalidates it. Focus loss pauses recovery only without background capability. Verify actual position/map movement after recovery instead of treating a refresh key as success.

## Choose the right movement mode

| Task | Command |
| --- | --- |
| Inspect exported maps | `uv run --locked python world_map.py list` |
| Inspect one map's dimensions and files | `uv run --locked python world_map.py info s465` |
| Walk to known coordinates without a GPS trace | `uv run --locked python ai-game.py navigate --map s465 --x 442 --y 178 --seconds 30` |
| Follow the current server GPS route | `uv run --locked python ai-game.py follow --seconds 30` |
| Continue GPS following across maps | `uv run --locked python ai-game.py follow --seconds 60 --continuous` |
| Make a short deliberate movement | `uv run --locked python ai-game.py move right --milliseconds 150` |
| Export accessible maps after login | `uv run --locked python ai-game.py export-world` |
| Open or advance a normal NPC interaction | `uv run --locked python ai-game.py interact` |
| Advance completed dialogue pages within a bound | `uv run --locked python ai-game.py talk --seconds 30 --max-pages 12` |
| Advance a visually inspected story scene with an explicit bound | `uv run --locked python ai-game.py scene --seconds 60 --max-presses 30` |

Navigation coordinates are per-map world pixels: X increases right; Y increases down. The sample `navigate` destination belongs to `s465`; choose coordinates for the actual task and retain the `--map` guard. `navigate` plans from the local collision atlas and does not wait for GPS dots. It still checks live position and map state. `--cross-map` permits a brief forward attempt at a known exit destination.

Check `status.movement_directions` before using diagonal commands. A loaded bridge advertising `up_left`, `up_right`, `down_left`, and `down_right` supports native diagonal bursts (both arrow keys held together). Older bridges without that capability use cardinal movement or alternating cardinal approximations; do not infer the loaded capability from edited source alone. With the updated collision-aware controller, inspect `mode: collision_recovery` / `replanning` and the `replans` count when a corner blocks the preferred movement. Recovery remains bounded and must be verified by position or map progress, not by the mode name.

The movement watcher remembers failed directions near the current position for six seconds, detects insufficient projected progress and back-and-forth loops, and supplies blocked directions to terrain steering. Inspect `blocked_directions`, `redirects` and `planner_ms`; do not disable stop bounds to force a route. The fast local planner avoids repeated long clearance scans. Its 294-point benchmark improved from roughly two seconds to 1.1 ms; that fixture does not establish every map's timing.

The atlas has 300 map definitions, including unvisited maps, and 299 collision masks in the inspected version. `s415` uses rectangular bounds without a mask. Local terrain is known; dynamic NPCs, players, server access rules, and a complete map-exit connection graph are not all represented by it. Do not claim all-map autonomous travel or full quest autopilot from atlas coverage alone.

## Respect control ownership and stop reasons

Background/minimized operation requires loaded `native_background_input: true` and `native_capture: true`; inspect `background_input_enabled` in supervisor status. The one-command entry upgrades a legacy bridge with a rebuild and monitored restart/login, so keep private credentials configured. Native input/capture do not activate the game, and the client continues updating when minimized. Keep the desktop/OpenGL session running: this is not headless operation or logout/suspend support. Do not reclaim focus merely because a capable game is minimized. Legacy focus/capture guards remain applicable when capabilities are absent.

A live four-cycle run stayed minimized/unfocused, closed the known popup and moved with fresh framebuffer images. Repoll fresh state after potentially slow capture and verify PID/map/quest context before click or following; old pre-capture state is not input authorization. Capability loss or malformed/stale native capture must pause without X11 fallback. See the reference for evidence; do not turn the observed background run into an all-quest guarantee.

Input commands share `navigation.lock` for one monitored session. Stop or wait for the current controller before another move, popup dismissal, or navigation run. Do not bypass the lease with a second socket client to force concurrent control.

Check `native_background_input`. When true, the controller uses game-local input without activation and can continue minimized/unfocused. Legacy bridges focus once and stop with `focus_lost`; inspect ownership rather than repeatedly reclaiming focus. Continuous mode retains the legacy focus check on later segments. A changed `map` value confirms a transfer. `interaction_required` identifies a nearby interaction target, not a reason to keep pushing through the NPC. `unable_to_advance`, `no_map_exit_detected`, or stale state require inspection rather than endless retries.

For “game opens but stays still,” inspect status/events before changing input. Current capture uses the game framebuffer; legacy captures refresh actual X11 geometry and use a scoped error trap; `WindowUnavailable` becomes a `window_unavailable` pause without invoking Codex. Restore/focus a legacy window rather than repeatedly restarting the game. A foot-valid position clipped only by extra collision padding may use `escape_step`: bounded clear-foot movement whose nominal and 17-ms guard landings both restore normal padding. A genuinely missing local connection returns `local_route_unavailable`; blocked cached recovery backs off for 60 seconds. Do not weaken collision checks or spin the planner. A two-cycle live entry recovered from `s205` to `s330`; the reference records its evidence and limits.

A nearby type-2 NPC/terminal endpoint also needs correct facing. The updated supervisor can make a single short alignment move, then talk; at an NPC collision boundary it can use a bounded same-target fallback instead of repeatedly pushing. Inspect the report and verify dialogue actually opens. The new automatic alignment has fixture coverage; the recorded Station terminal opening used a manual alignment and should not be presented as a live automatic-alignment result.

NPC local/cached recovery must use `WorldMap.interaction_destination`, a bounded validated approach strictly within 24 units, rather than a blocked NPC center. Preserve `interaction_target` and `cross_map: false`; completion checks actual NPC distance, not the generic eight-unit waypoint tolerance or a stale GPS step count. Expected `NoRouteError` means backoff without Codex repair. Real-atlas simulation reproduced the original corner successfully; later live automation crossed maps and advanced chapter 9 step 2→3, rather than replaying that exact old NPC position. Keep those evidence types distinct.

At a usable GPS endpoint, the bounded crossing attempt aims toward the endpoint or final route segment, rather than a stale character facing left by collision recovery. Missing-route fallback still uses current facing. Neither attempt proves an exit exists; keep the time bound and verify the map change.

## Popups and quest interactions

Persistent mode checks the exact local close-button template before its first movement and no more than once every two seconds. A guarded game-only click is followed by `after-popup-close.png`; only disappearance of the known marker resets navigation backoff. Without `linux/ui/popup-close.png`, automatic detection skips. Do not fabricate a template, claim arbitrary-popup recognition, or treat a story choice as a close button. The public kit excludes the game-derived template.

`uv run --locked python ai-game.py dismiss` captures `before-dismiss.png`, looks for the known close-button image in `linux/ui/popup-close.png`, clicks the matched button, and otherwise tries the normal X key. Inspect `after-dismiss.png` to confirm closure. An unknown or scaled modal may not match that template; derive any fallback click from the current screenshot and window geometry rather than reusing old coordinates. Use the PID-bound window input helper under the navigation lease, then verify the resulting image.

Main-quest chapter, step, target map, and HUD objective are read from live progress. `required_action` and an NPC ID may be derived from a matching bundled `quests/steps.json` entry; preserve `action_source` and `target_npc_source`. A definition mismatch stays `unknown`. The raw `progress_value_f` field is not a verified NPC ID. Runtime entity IDs and bundled logical NPC IDs are different namespaces: the observed dialogue entity `7` is not the bundled quest NPC `121`. Use the explicit `entity_id` and `interaction_id` labels instead of comparing those numbers as though they were the same identifier.

For an authorized quest action, use `uv run --locked python ai-game.py interact` for one normal Space interaction. It saves `after-interact.png` and `interaction-state.json`. For ordinary dialogue pages, `uv run --locked python ai-game.py talk --seconds 30 --max-pages 12` waits until typing finishes and advances with normal Space, within the time/page bounds. It saves `dialogue-state.json` and `talk-state.json`. It does not automatically choose menus or spend resources. Inspect choices and reassess after the dialogue closes or a bound is reached.

Dialogue polling must remain read-only: `d.a()` and `aN.e()` are **mutating reveal/advance actions**, even though their return values resemble predicates. The current snapshot uses the verified `aN.b()` typing predicate and fields instead; see the reference before changing it. Wait for `dialogue.can_advance`; do not call advance methods just to inspect readiness.

Story scenes use a separate engine and may be absent from `status.dialogue`; the updated bridge reports them separately as `status.story`. Persistent mode uses complete ready story telemetry and pauses for choices. The manual `scene` command below does not perform that detection. For a scene the user has authorized advancing and the AI has visually inspected, `uv run --locked python ai-game.py scene --seconds 60 --max-presses 30` is an explicit normal-Space macro, at most once per second. It requires fresh world/quest/PID/map state and stops on its time/press bounds, quest or map/session changes or invalid state; it uses background input when advertised, otherwise focuses once and stops on lost focus. Space can confirm choices, and the command does not detect scenes or choices; absent dialogue is not enough reason to start it. Inspect the before/after images and `scene-state.json`. The reusable command has fixture coverage only; the verified Shaman House gameplay used a separate bounded prototype macro.

A talk window or pressed key is not proof of quest advancement. The talk command reports `quest_progressed` only from a changed chapter/step; verify valid before/after progress in the live state and do not treat a missing progress object during loading as advancement. Fixture checks and one live Gatomon conversation confirmed a main-quest step change; the reference records that evidence. Persistent mode supervises the supported loop; unsupported objectives, story choices and incomplete telemetry can pause it; ongoing combat waits without the optional combat-Space mode. Complete autonomous quest completion is not established.

## Reuse evidence and maintain the skill

Read [state-and-adapter.md](references/state-and-adapter.md) when inspecting schemas, debugging the bridge, or adapting a changed client. Use the REA skill for a new shipped-artifact question or client version, not for routine script execution. Do not rerun REA setup or provider installation when the needed tools are already available.

After a meaningful new workflow or fix is verified, update this skill or its reference with the actual command, required state, stop condition, and evidence. Replace stale instructions; keep credentials, copied asset contents, and transient session coordinates out. Record limitations separately from verified behavior. Run the focused regression checks for the change and validate this skill with the skill-creator validator. Do not call a newly added command verified until its observable result has been checked.
