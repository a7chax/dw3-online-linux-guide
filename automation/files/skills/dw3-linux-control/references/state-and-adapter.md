# State and Adapter Reference

Paths below are relative to the game directory. Read the current source when a field or command changes; this reference records the inspected 0.1.95 adapter.

## Files to inspect

| Path | Purpose |
| --- | --- |
| `.env` | User-authorized private local credentials; ignored by Git, never display or publish its contents. |
| `.env.example` | Publishable credential-key names with placeholders only. |
| `linux/ai-sessions/latest/state.json` | Atomic position/GPS/main-quest snapshot, refreshed about every 100 ms. |
| `linux/ai-sessions/latest/state-events.jsonl` | Changes in observed state. |
| `linux/ai-sessions/latest/quest-state.json` | Enriched quest description from the latest `quest` command. |
| `linux/ai-sessions/latest/follow-state.json` | Navigation source, starting/current state, stop reason, bursts and map transitions. |
| `linux/ai-sessions/latest/last-move.json` | Before/after state of the latest movement. |
| `linux/ai-sessions/latest/local-path.json` | Local navigation goal, path and planning time. |
| `linux/ai-sessions/latest/interaction-state.json` | Status after the latest `interact`, including dialogue when exposed by the loaded bridge. |
| `linux/ai-sessions/latest/dialogue-state.json` | Last dialogue snapshot saved by the bounded `talk` loop. |
| `linux/ai-sessions/latest/talk-state.json` | Dialogue run reason, pages advanced, and before/current status. |
| `linux/ai-sessions/latest/scene-state.json` | Explicit Space-macro run reason, press count, before/current status, and screenshot paths. |
| `linux/ai-sessions/latest/autoplay-state.json` | Atomic persistent supervisor report: PID, mode/reason, action, quest and counters. |
| `linux/ai-sessions/latest/autoplay-events.jsonl` | Append-only changes in supervisor state. |
| `linux/ai-sessions/latest/autoplay-actions.log` | Output from bounded actions selected by the supervisor. |
| `linux/ai-sessions/latest/autoplay.stop` | Stop request flag for the pinned session. |
| `linux/ai-sessions/latest/autoplay.lock` | Singleton supervisor lease. |
| `linux/ai-sessions/latest/autoplay-route-cache.json` | Validated route identity/points and pending-battle marker; mode 600. |
| `linux/ai-sessions/latest/repair-state.json` | Optional Codex worker status, failure observations, attempts and verification result. |
| `linux/ai-sessions/latest/repairs/NNN-*/` | Allowlisted context, prompt, worker log/report and regression verification log. |
| `linux/ai-sessions/latest/control.sock` | Private local command socket; prefer `ai-game.py` over handwritten requests. |
| `linux/world/atlas.json` | Exported map index and coverage/failure report. |
| `linux/world/maps/MAP/metadata.json` | Original map metadata through the client's normal asset reader. |
| `linux/world/maps/MAP/collision.png` | Static collision mask, if present. |
| `linux/world/auxiliary/npcs.json` | Bundled NPC definitions; not a live entity-position feed. |
| `linux/world/auxiliary/worldmap/world.json` | World-map placements; not proof of exit connectivity. |

`phase` is `starting`, `login`, `character_selection`, `loading_map`, `world`, or `other_screen`. First position samples and map changes reset the `moving` comparison. `moving` reports measured coordinate change, not animation or held keys. `tile_x`/`tile_y` are floors of world coordinates, not a separately established tile size.

`trace` includes `enabled`, `auto_walk`, `route_type`, `steps_remaining`, and world-coordinate `points`. Types 0 and 4 are unusable for the current route follower; type 2 identifies an interaction route. A two-step route beside an NPC may already require interaction rather than more movement.

`main_quest` contains live `chapter`, `chapter_count`, `step`, `step_count`, `target_map`, `action_code`, `objective_text`, and neutral `progress_value_f`. The enriched quest command matches chapter/step/target map against the shipped `quests/steps.json`; actions include `talk`, `enter`, `zone`, and `drop`. Inspect the source labels and keep unknowns unknown. Localized objective text can differ from the interface language expected by the operator.

When the dialogue hook is loaded, `status` can include `dialogue.entity_id`, `text_file`, `text_index`, full `text`, zero-based `page_index`, `page_count`, `typing`, `can_advance`, and `ready_to_close`. `can_advance` is `!typing`; `ready_to_close` also requires the last page. This hook is part of control status, not a guarantee that every version of `state.json` contains dialogue. Read full state after each normal interaction; do not infer options or quest completion from one screenshot of partial typewriter text.

For inspected 0.1.95, `aj.aM` is the dialogue bubble and its field `e` is the `aN` writer. The pure snapshot calls `aN.b()` for typing and reads writer `c` (page index), `a` (pages), and, when needed, `d` (revealed count). **Never use `d.a()` or `aN.e()` as readiness predicates:** they reveal/advance dialogue and make mere polling change game state. Keep progress comparisons based on valid before/after chapter and step; missing quest state during a transition is not progression.

Entity namespace: `bI.bg.b()` is the runtime entity ID, while `bI.bg.g()` is the outbound interaction identifier. Dialogue entity `7` and bundled quest NPC `121` were observed for the same quest target; compare the appropriate labeled identifier, not their raw equality. `target_npc_position` may carry both `entity_id` and `interaction_id`. The bundled `npcs.json` and `quests/steps.json` use logical NPC definitions, not a live entity-position feed.

The updated control status also reports `movement_ready`; a world screen can still contain a modal, story or battle that prevents movement. `trace.has_reply` distinguishes a known GPS reply state when available and may be null on an unsupported read. Keep unknown values distinct from false.

`story`, when active, includes `telemetry_complete`, `typing`, `awaiting_choice`, `choice_count`, `selected_choice`, `submitted`, `script_complete`, and `can_advance`. Only a complete snapshot with displayed bubbles, no typing, no choices and no submitted response permits automatic Space. Failed optional reads leave advancement disabled. `battle`, when active, includes `transitioning`, `telemetry_complete`, `result_ready`, `can_advance`, `submitted`, and `result` (`victory`, `escape`, or `defeat` when known). A ready result may be acknowledged; active combat itself does not authorize result acknowledgement or an invented combat strategy.

## Persistent supervisor

The primary entry is `uv run --locked automation.py`: conditional native/runtime build, private login or monitored-world reuse, capability validation/reload, then persistent supervision with combat Space, known-popup checks and Codex repair enabled. Required original game inputs, build/desktop dependencies and initial private credentials remain prerequisites. `automation.py --status` and `--stop` avoid setup/login/game input. Entry options are `--no-codex-repair`, `--no-battle-space`, and `--max-cycles N`. Status/stop selects `latest`; use direct `autoplay.py --session PATH --status` or `--stop` for an older pinned session. The direct interface below remains useful for an already prepared monitored session.

Known-popup checks run before movement on the first cycle and at most once every two seconds. A locally supplied `linux/ui/popup-close.png` is required. Detection uses the current screenshot and exact known icon; native game-only click is followed by `after-popup-close.png`. Only disappearance of that marker resets navigation no-progress/backoff. Missing template skips detection, and a remaining marker reports `popup_still_visible`; unknown dialogs/choices are not recognized. The public kit excludes the game-derived image.

`autoplay.py` runs indefinitely by default. `--resume` removes an earlier stop flag, `--status` prints the saved report without input, and `--stop` writes a stop request. `--session PATH` selects a concrete monitored session; the running process pins that path rather than silently following a new `latest` target. Optional `--pid PID` verifies the intended game process. A deliberate test may use `--max-cycles N`; normal persistent operation omits that limit.

Immediately before each automatic Space or GPS-refresh key, the supervisor rechecks fresh status, PID/map/quest and the legacy focus guard when background input is unavailable. Its policy uses explicit state: usable GPS selects bounded following, a stalled segment can select local-atlas endpoint recovery, ordinary dialogue/NPC arrival selects bounded talking, and complete ready story/battle-result telemetry selects one Space input. The optional combat-Space mode below confirms selected battle input; no tactical strategy is supplied. Empty enabled type-0 routes wait before a bounded GPS refresh; failures and no-progress cycles back off instead of hammering controls.

It stays alive in waiting states for stale/unavailable state, non-world screens, a changed PID/session, unsupported quest actions, story choices or incomplete telemetry. Ongoing combat waits unless the explicit combat-Space mode is enabled. Background-capable bridges do not activate the window. Legacy bridges acquire focus initially and pause on focus loss; neither path repeatedly reclaims focus. An old-session supervisor must be stopped/rebound deliberately when the game session changes. Stop requests are checked during short guarded actions. Report `active` or a running PID does not establish quest advancement. `progress_events` includes changes in the position/map/dialogue/story/battle fingerprint, not only quest steps; compare valid live quest chapter/step values for quest advancement.

For a GPS type-2 endpoint within 24 world units and no existing dialogue, the supervisor selects a 50-ms normal native alignment move when distance exceeds 16 units or the eight-way facing is wrong. At distance at most 16 with correct facing it talks; at distance at most eight with correct facing it does not push again. Fresh PID/map/quest/`movement_ready` checks precede the move. If a same-endpoint alignment advances less than two units but leaves correct facing, a 30-second boundary cache permits talking within 24 units. The same failed position/direction attempt is suppressed for 30 seconds and normal no-progress backoff remains in force. These are bounded normal inputs, not collision bypasses. The alignment policy has fixture coverage; live automatic alignment still needs separate evidence.

`--scene-target CHAPTER:STEP:MAP` is an explicit opt-in to the bounded manual scene macro at a known `enter`/`zone` objective. It is not scene recognition and Space may submit a choice. The automatic telemetry path pauses when a choice or incomplete story state is reported. Keep manual scene overrides distinct from the default supported loop.

`--battle-space` is a separate explicit opt-in to one normal Space per cycle during active combat. The user requested it for this session; the default remains waiting for a ready result. Policy and pre-input checks require complete active-battle telemetry, no transition, no submitted response, fresh state, the expected PID/map/quest and applicable legacy focus guard; a newly active story also blocks combat input. This confirms whichever battle option is selected, without arrow/item/tactical selection, VIP flag changes or an auto-battle bypass. The saved supervisor report includes `battle_space_enabled` and `codex_repair_enabled`. Current requested launch: `uv run --locked autoplay.py --resume --battle-space --repair-with-codex`.

### Missing route after battle

The supervisor remembers validated finite type-1/type-2 route points before combat, keyed by PID, map, chapter, step and target map. An identity change discards that cache. After an observed active-to-inactive battle transition with enabled empty type-0 GPS and `has_reply: false`, it selects `post_battle_gps_refresh` immediately, clearing navigation cooldown. After a two-second reply window, an unchanged missing reply may select `post_battle_cached_route`. Fresh GPS data takes precedence over cached data; active battle/story, disabled GPS, unknown reply state or changed identity blocks cache use.

Recovery validates the full local collision path before normal movement. NPC endpoints use `WorldMap.interaction_destination` to choose a clear approach strictly within 24 units, with a bounded maximum of eight path attempts. Local and cached recovery preserve `interaction_target` and `cross_map: false`, then apply normal facing/talk policy; an exit retains bounded crossing. Following checks actual NPC distance rather than the generic eight-unit waypoint tolerance, and near-NPC policy ignores stale GPS step counts. Missing/blocked approaches raise expected `NoRouteError` and back off without a repair worker. The report adds `cached_route_available` and `post_battle_recovery`. The mode-600 session `autoplay-route-cache.json` persists the validated route and pending-battle marker across supervisor restarts; only the exact PID/map/chapter/step/target identity permits reuse. It cannot supply an endpoint never observed. Capability-appropriate focus/session/quest/modal checks remain active.

### Optional exception repair

`uv run --locked autoplay.py --resume --repair-with-codex` opts into `codex_repair.py`; omit the flag for ordinary autonomous Python without AI calls. Only `action_failed`, `unknown_action`, and `local_recovery_failed` are eligible. Three observations of the same hashed failure identity are required. Focus/stale-state pauses, combat waits and story choices do not request repairs. The session `repair.lock` allows one worker at a time; one attempt per fingerprint, three total workers per session, and a 600-second cooldown bound retries.

The parent pauses game input while `codex exec` runs with workspace-write sandboxing, on-request approvals and automatic approval review. It passes a prompt through stdin and removes `DW3_` environment variables. Context contains only selected map/position/quest/trace fields, error type and stack-frame locations; never add `.env`, secrets, dialogue, exception messages or raw logs. The worker is instructed to fix only the repeated Python failure and add a regression fixture, without game input, Java/native changes, publishing or approval bypasses. These prompt restrictions are instructions to the worker, not a claim of an independent filesystem security boundary.

Per-attempt `repairs/NNN-*/` contains `context.json`, `prompt.txt`, `worker.log`, `report.md` and, if verification runs, `verification.log`. A successful worker exit with no detected source changes does not restart. Changed Python source must pass `uv run --locked python -m unittest discover -s linux/native/tests` before the parent restarts the supervisor bound to its original session and game PID. It does not restart the game. Worker or verification failures stay recorded; stop requests interrupt the worker. Approval requests can leave it waiting. Fixture coverage verifies this policy. An earlier accepted worker contribution was interrupted during verification. A later non-interactive repair completed the full chain: worker exit zero, 251 parent verification tests passed, supervisor reload and subsequent movement from s650 to s655.

## Story scenes versus ordinary dialogue

Ordinary NPC bubbles use `aj.aM`; a story scene uses `aj.aX`, class `at`. The ordinary `dialogue` object does not describe that engine; the updated bridge exposes a separate read-only `story` snapshot. Normal Space/E/Z goes through `aj.p()`: when `at.e()` is true it submits the selected choice, otherwise `at.l()` reveals or advances scene bubbles. Do not treat missing ordinary dialogue as proof that pressing Space is safe or necessary.

`scene --seconds 60 --max-presses 30` is an explicit, bounded Space macro, not scene recognition. It requires a fresh world state with valid main-quest progress, PID and map; it uses background input when advertised, otherwise focuses the monitored window once and checks legacy focus before subsequent input. It sends at most one press per second and stops on a changed quest step, changed map/session, legacy focus loss, invalid/stale state, or the time/press bound. It saves `before-scene.png`, `after-scene.png`, and `scene-state.json`. Space can confirm choices; this macro has no choice detector or automatic choice policy. Use it only for an inspected scene within the user’s requested action.

The inspected story fields are `at.p` (bubble records: `e.a` is the `d` bubble, `e.c` text index, `e.d` style, `e.b` actor), `at.o` (text resource), `q` (instruction index), `t` (complete), `v` (choice count), `w` (selected choice), and `x` (submitted). The `at.e()` awaiting-choice predicate is pure. Do not call `at.f()` or `at.l()` as polling actions; the normal input path can submit or advance choices/pages. Read the bubble’s `e` writer through the established pure `aN` fields if extending the hook. The raw engine fields remain version-bound internals; the supported public telemetry is the separate `story` object described above.

## Native diagonal movement and collision recovery

`status.movement_directions` advertises the directions supported by the loaded bridge. Native eight-direction support includes `up_left`, `up_right`, `down_left`, and `down_right`; each diagonal move presses both normal arrow keys and releases both in cleanup. A Java rebuild changes the artifact on disk, not an already-running JVM. Missing diagonal capability means use the legacy cardinal path until an authorized reload.

The collision-aware navigation workflow uses the local terrain mask to check candidate bursts, including diagonal movement and shorter corrections at corners. Keep this distinct from a map-wide collision-free guarantee: server NPCs and other dynamic obstacles are not fully encoded in the static atlas. Watch navigation report fields `mode`, `replans`, `before`, and `current`. `collision_recovery` and `replanning` indicate a strategy change; measured position/map progress is the evidence that it helped. Preserve bounded time and no-progress stops rather than forcing repeated input forever.

`motion_watch.py` measures projected movement with doubled Y to match isometric geometry. A burst needs at least two units and at least 25% of its expected projected advance; returning near recent positions detects a short oscillation. Failed directions are remembered for six seconds within 24 anisometric units of their origin. Steering excludes those directions and can redirect after a 50-ms terrain recovery pause; the legacy non-terrain route-refresh pause remains longer. `follow-state.json` adds `blocked_directions`, `redirects`, and `planner_ms` (latest steering calculation); `local-path.json.planned_ms` measures full-path planning. Fresh-state, PID/map/modal guards and the applicable legacy focus guard still apply.

The optimized local planner reuses grid/collision work rather than repeatedly checking long segments. A 294-point benchmark changed from 35,022 clearance checks and approximately 1.95–2.19 seconds to three checks and 1.1 ms. This is a measured fixture comparison, not a timing guarantee for all map geometries.

`WorldMap.escape_step` handles a foot-valid start clipped by the extra three-pixel horizontal/one-pixel vertical body margin. Candidates last 50–175 ms, keep the entire foot segment clear including a 17-ms release guard, and require full padded clearance at nominal and guarded landings. Path planning can prepend that bounded escape; normal padded planning resumes afterward. If no connection exists, `NoRouteError` is caught by navigation as `local_route_unavailable`, rather than treated as an unexpected controller exception. Blocked cached endpoint recovery records a 60-second retry backoff instead of repeatedly running A*.

Legacy X11 capture queries `XGetGeometry` on every image. Scoped `XSetErrorHandler` plus `XSync` catches asynchronous capture/focus X11 errors, restores the prior handler, and raises `WindowUnavailable`; the supervisor pauses with `window_unavailable` without a Codex repair. This prevents an old cached 1280×720 size against a resized 834×615 window from causing a fatal XGetImage BadMatch. Restore/focus the intended legacy window; do not replace the normal game-only input path with host injection.

## Offline main-quest catalog

`quest_catalog.py` reads `quests/steps.json` and `quests/places.json` from the original `app/client.jar` and optionally enriches exact map/logical-NPC matches from exported metadata. It does not connect to or operate the game. Use this workflow for future requirements or when the user says not to progress the quest:

```bash
uv run --locked python quest_catalog.py list --json
uv run --locked python quest_catalog.py chapter 5 --json
uv run --locked python quest_catalog.py export
```

All commands accept `--jar FILE`, `--world DIR`, and `--texts DIR`; `export` also accepts `--output DIR`. Defaults are `app/client.jar`, `linux/world`, English texts at `linux/world/auxiliary/text/en`, and exports at `linux/quest-catalog/main-quests.json` / `main-quests.md`.

The inspected catalog has 36 chapters, 113 steps, and 68 distinct step maps. Original action tokens are 55 `talk`, 17 `enter`, 40 `zone`, and one `drop`. The single `drop` is chapter 11 step 5 on `s405`; the client presents it as winning battles, but the exact battle target, count, and completion predicate are not specified. Chapter place lists are not an exit graph. NPC dialogue indices are candidates, not a full server-controlled quest script. Do not fill unknown rewards, access rules, branches, or titles with guesses.

The reusable `scripts/export-quest-text.py` invokes the original `bo.d()` reader in a separate temporary-compiled Java process. It checks the inspected client hash and reads only twelve English arrays: `text/en/places.json` and `text/en/talk0.json` through `talk10.json`. It does not load `.env`, authenticate, attach to the running game, or unlock additional asset groups. All twelve arrays were available offline in the inspected package; missing resources are reported rather than forced open.

Map names use `maps/MAP/map.json.place` as an index into the 136-entry `places.json` array, matching `al.a(stage)`. NPC names follow the original `al.k()` logic: find the exact `(stage, npc)` row in `npcs.json`, read `talk<file>.json`, scan its `texts` indices in order, and accept the first nonempty trimmed `\[name\](.*?)\[name\]` speaker without `[` and not starting with `?`. This yields a candidate speaker label, not independent confirmation of a live NPC name or dialogue selection. Unresolved names stay unknown.

## Credential configuration

`ai-game.py login` and `run` read the four `DW3_` keys only when login/character selection needs them. Precedence is explicit username/server/character flags, then process environment, project `.env`, then the existing defaults. Password has no CLI flag; environment or `.env` supplies it, otherwise login prompts privately. An explicitly empty password setting falls back to the prompt. The launcher excludes `DW3_PASSWORD` from the child game process environment.

The dependency-free `.env` parser accepts literal `KEY=value` assignments, matching outer single/double quotes, optional `export ` prefixes, and full-line `#` comments. It performs no command substitution, variable expansion, or backslash unescaping; put a value containing boundary whitespace inside quotes. Do not source the file through a shell. Only publish `.env.example`; the actual file and `.env.*` variants are ignored. When credentials are configured with the user’s authorization, maintain restrictive local permissions and avoid outputting values.

## Adapter boundaries

`stall_watch.py` records bounded numeric/flag snapshots and spatial novelty, ignoring facing-only changes and revisits as progress. After at least three failed navigation actions plus 60 seconds without new cells/map/quest progress it qualifies `navigation_stalled`; repeated eligible guard failures use `input_guard_stalled`, and safe idle stories use 180 seconds. Actual battles, animation/typing, choices, stale/loading/focus/session states and insufficient funds are not navigation stalls. Healthy combat Space never triggers a repair merely because map coordinates stay fixed. The supervisor defers a qualified repair until outside all action leases, rechecks its context, and retains eligibility across cooldowns. Codex runs through `exec` with stdin prompt, not an interactive terminal. Each repair owns a mode-600 filtered history file; no raw session log, credential or chat text is supplied.

An active battle can coexist with a completed background story object. Battle Space must not be blocked solely by `story.active` when story telemetry explicitly confirms `script_complete: true`, `typing: false`, `awaiting_choice: false`, zero choices and `submitted: false`. Incomplete or unfinished story telemetry and choices still block that input. A live Byakko Dome fight reproduced this mismatch; after the narrow guard fix, normal Space commands reduced Numemon HP from 3,247 to 1,799. This is battle progress, not proof of victory.

Background mode is capability-driven: `native_background_input: true` permits game-local control without host focus; `native_capture: true` enables game-framebuffer screenshots. The supervisor reports `background_input_enabled`. The inspected LWJGL backend continues rendering while minimized but skips its input update; the bridge supplies that update and clears one-frame flags after rendering, preserving callbacks queued for the next frame. Neither Python nor the updated bridge requires desktop activation for normal input; legacy bridges retain focus checks. `automation.py` treats missing background/capture capabilities as requiring a bridge build/restart/login. Keep PID/map/session/modal checks, leases, time bounds and unconditional releases. A graphical desktop and live OpenGL context remain required; background operation is not a headless client or logout/suspend guarantee.

The bridge `capture` operation accepts `expected_pid` and returns `png_base64`, `width`, `height`, and `pid`. The current `GameWindow` path uses that framebuffer image without opening an X11 connection or activating a host window. Its native `focus()` verifies the fresh expected process without OS activation; `focused()` still reports the actual `window_focused` GLFW value rather than pretending focus is present. Background-capable policy skips the focus requirement explicitly. Do not use a false focused-state report as a substitute for the capability check. Legacy capture/focus remains an X11 fallback only when native capabilities are absent.

Once selected, native capture must fail recoverably on lost capabilities, stale process status, invalid PNG/dimensions or mismatched PID; it must not silently open an X11 fallback. A four-second capture exposed another stale-state race: repoll after capture and validate PID/map/quest context before both a popup click and subsequent following. Keep the earlier context guard while allowing a fresh sample; do not bypass freshness because the image succeeded.

Popup clicks also compare battle/story/dialogue context after capture and at the final guarded poll, so an old image cannot click a newly opened modal. The bounded scene input timer starts after its preparatory capture; a slow image must not consume the one-second battle-Space budget. Each press still revalidates the current process, map and quest.

`native_key_input: ["space", "enter", "g", "x"]` and `native_click_input: true` advertise the loaded game-only UI input. `press_key` sends allowlisted normal keys through the game's GLFW input callback; `click` calls the game backend cursor-position and mouse-button callbacks with window-local coordinates, updating its polled cursor and input event queue. Both use private IPC, bounded durations, world/PID/map/modal guards, applicable legacy focus guards and uncancellable release cleanup. No host XTest fake keyboard/mouse path is retained. The previous XTest path could trigger GNOME's Remote Desktop portal. Local X11 window discovery and legacy focus/screenshots remain separate from keyboard/mouse injection; current capture reads the game framebuffer without activation. Missing capability must fail with a rebuild/restart instruction rather than silently use host input.

Upgrade sequence: `uv run --locked autoplay.py --stop`, `uv sync --locked`, `uv run --locked python linux/native/build.py`, then an authorized `uv run --locked python ai-game.py login --restart`. Recheck status capabilities and world/PID before resuming. The rebuild changes files on disk; the restart loads them. Fixture tests trap host input APIs and check native bridge dispatch/release. Live no-portal behavior must be checked separately on the reloaded client.

- `autoplay.py`: persistent singleton supervisor selecting bounded actions from explicit live telemetry.
- `automation.py`: one-command conditional setup/login and supervisor entry, plus status/stop without setup or input.
- `codex_repair.py`: opt-in, bounded source-repair worker and full-suite verification before supervisor restart.
- `ai-game.py`: login, state requests, quest enrichment, input lease, bounded navigation.
- `motion_watch.py`: recent movement/oscillation tracking and short-lived blocked-direction memory.
- `world_map.py`: collision-mask inspection and local path planning. It does not know every server-controlled NPC obstacle or map exit.
- `game-control.py` / import `game_control`: PID-bound local X11 window discovery/legacy focus/capture, current native framebuffer capture, and private bridge wrappers for game-only UI input. It has no XTest injection dependency.
- `StatePrinter.java`: render-thread field reads; worker-thread formatting and file output. Keep disk/terminal I/O off the render thread.
- `ControlBridge.java`: allowlisted normal client interactions on its render thread; delayed key releases must still execute after a caller timeout.
- `WorldAtlas.java`: copies visible map metadata and collision assets through the authenticated client's original reader. It does not extract or save protection keys.

Original `app/client.jar` SHA-256:

```text
7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe
```

The observer is pinned to that inspected client. Use CFR/javap and REA as appropriate for an actual version change. REA's archive inventory rejected case-distinct obfuscated class names in this JAR; that limitation did not establish a malformed game, so Java analysis used the original artifact with other tools. Do not patch protection checks to obtain coordinates.

## Verification and changes

Run relevant tests in `linux/native/tests/`; the complete local suite is:

```bash
uv run --locked python -m unittest discover -s linux/native/tests -p 'test_*.py' -q
```

The delayed-release fixture binds a local Unix socket, which a restricted sandbox may block. That is an execution-environment limitation, not a failing game assertion.

A local planner change should cover collision cells touched by diagonal segments and narrow passages, not only wide open terrain. A navigation change should cover focus loss, duplicate-controller rejection, map-transfer timing, nearby endpoints and NPC arrival. A quest-reader change should cover live progress separately from inferred bundled actions.

For Java bridge changes, rebuild with `uv run --locked python linux/native/build.py`, verify focused tests, and load the classes through a new monitored client only when the ongoing task authorizes that restart. `./DW3-Online-Linux --check` verifies native initialization; it does not verify login, navigation, or quest completion. Keep prior live-state results distinct from a newly rebuilt version that has not been loaded.

## Verified workflow evidence

On 14 November 2026, `talk --seconds 30 --max-pages 8` waited for complete dialogue pages and advanced three Gatomon pages. Live main quest 5 changed from step 1 targeting `s470` to step 2 targeting `s475` (Shaman House), and the command reported `quest_progressed`. This verifies that interaction, not merely arrival, advanced that step; it does not establish completion of the entire quest chain.

A separate live `navigate` run within `s470` reached its requested coordinates with `navigation_source: local_collision_atlas` and `reason: destination_reached`; planning took approximately 0.15 ms for that short path. The saved evidence is `linux/diagnostics/local-navigation-proof.json`. That timing belongs to this short path, not every map route.

The later Shaman House recovery was verified live after loading native diagonal input. Local navigation backed away from the bank on `s465`, then used native diagonal movement to reach `s475` (Shaman House), stopping with `map_changed`. The route planned in approximately 172 ms; evidence is `linux/diagnostics/next-quest-step/02-shaman-house-recovery.json` and `02-local-path.json`. This is one verified recovery, not a guarantee that every dynamic obstacle is passable.

An explicitly bounded prototype macro then made 18 normal Space presses during the inspected story. Its result stopped on a map change; the recorded current state confirmed main quest 5 advanced from step 2 to step 3, now targeting `s375` (Protocol Ruins), with the player back on `s465`. Evidence is `linux/diagnostics/next-quest-step/03-story-completion.json` and `04-next-quest.json`. The reusable `scene` CLI was added afterward and tested with ten fixtures; it has not itself been used to advance another live objective. At that stage the combined regression suite reported 77 passing tests.

The persistent supervisor was separately verified live on 14 November 2026. A bounded three-cycle run moved from `s445` to `s440`, ending near `(232.56, 426.10)`; evidence is `linux/diagnostics/autoplay/02-three-cycle-live-check.json`. The launched persistent process then reached 116 cycles and six actions, recorded focus-loss pauses, resumed after refocusing, and honored the stop flag with `active: false` / `reason: stop_requested`. The launch is recorded in `linux/diagnostics/autoplay/03-persistent-launch.json`; its pinned session retains the state/events. An observed Victory panel was closed using normal Space before route movement resumed. This does not verify an ongoing-combat strategy or all-quest completion.

A Station terminal live check separately showed why facing matters: a deliberate 50-ms `up_right` movement aligned the character before Space opened the ordinary NPC dialogue (runtime entity 6, text file 6/index 811, “Let's go to East Sector”). That was a manual root-agent alignment, not a live run of the newly added automatic alignment policy.

An earlier persistent run was confirmed alive with `active: true` while handling reported ready story pages at South Station; its snapshot is `linux/diagnostics/autoplay/06-final-persistent-state.json`. Ready story/result Space actions do not use navigation no-progress backoff merely because position and quest remain unchanged. The complete regression suite at that stage passed **104 tests**; automatic alignment remains fixture-tested separately from the manual terminal interaction.

A later East Station stop had two causes: lost focus and a one-point GPS endpoint within eight units while the character faced downward. Restoring focus alone left repeated `no_map_exit_detected`. The corrected crossing heading used the endpoint vector and immediately transferred `s410` to `s400`. The regression reproduces the recorded endpoint/facing mismatch. Proof: `linux/diagnostics/autoplay/07-east-station-exit-fixed.json`. Persistent autoplay was resumed with the Python fix; no client rebuild was required.

After the fast planner and movement-watcher changes, `uv sync --locked` prepared CPython 3.12.13 with Pillow 12.1.1. The complete locked suite passed **124 tests in 28.466 seconds** before the combat-Space addition. A two-cycle live run moved on `s400` from approximately `(674.92, 1099.05)` to `(479.38, 662.94)` in 24 seconds and correctly interrupted movement with `battle_active`; see `linux/diagnostics/autoplay/09-fast-uv-live-check.json`. These measurements verify that observed route, not a universal movement speed or quest completion.

A separate bounded live check closed the current battle with one normal Space; evidence is `linux/diagnostics/autoplay/10-battle-space-live-check.json`. The persistent supervisor was then launched through uv with `--resume --battle-space --repair-with-codex`, recorded in `11-uv-persistent-launch.json`. The updated combat/repair focused tests passed (28 supervisor and eight repair fixtures). The real Codex CLI also passed a read-only smoke command with the configured sandbox/approval flags and exited successfully; that does not demonstrate an actual exception repair. At that stage no live repair event had been established.

The earlier locked uv suite passed **127 tests in 25.791 seconds**. The final persistent process then handled a new random battle without intervening root-agent game input: following stopped with `battle_active`, cycles 3–6 selected `battle_input_ready` / normal Space, cycles 7–8 selected `battle_result_ready` / normal Space, and following resumed to approximately `(337.8, 324.7)` on `s400`. Evidence is `linux/diagnostics/autoplay/13-autonomous-random-battle-proof.json`; `12-final-uv-enabled-state.json` confirms both optional modes enabled. This verifies the observed combat-confirmation and route-resumption flow, not every battle or tactical strategy. At that stage genuine exception repair was fixture-only despite the successful read-only Codex CLI smoke check.

Publication verification: the post-battle recovery update passed **133 controller tests** under uv. The exact source-kit payload was installed into an isolated temporary game layout and passed the same 133 tests using local original inputs. Its separate source installer passed **eight tests**. No credentials, original game binaries, map/dialogue exports, screenshots, or private sessions are included in the public kit.

Game-local input verification: the corrected popup command removed the visible Halloween panel; its close marker disappeared in the saved after image. The new key operation changed live GPS from enabled to disabled and back to enabled. The Python input helper no longer invokes XTest, and legacy login uses the local control bridge. These checks validate game-local input; an already-open GNOME sharing dialog can be cancelled instead of granting desktop sharing.

Integrated entry-point verification: `uv run --locked automation.py --max-cycles 2 --no-codex-repair` reused the logged-in world, moved into the quest target map, and aligned at its NPC. The full suite at that stage passed **148 tests** under uv, including automatic known-popup checks before navigation and the one-command setup fixtures. The standalone source installer has eight separate passing tests.

Startup recovery was subsequently verified with an intentional oversized-capture error, followed by a successful capture in the same process. The two-cycle one-command entry then moved from a stuck foot-valid/padding-clipped start on `s205` at `(776.5, 297.6646)` to `s330` near `(1209, 472.75)`, with two actions/progress events and no AI game input. This proves that observed window/terrain-margin recovery, not every route or objective.

A real Codex worker proposed the `NoRouteError` / `local_route_unavailable` change. The parent reviewed and accepted it; a stop request interrupted the automatic verification stage despite a zero worker exit. Stop during worker/verification is now labeled `repair_interrupted`. Keep that interrupted contribution distinct from the later completed automatic repair/test/restart cycle described above.

Background operation was verified live in a four-cycle run. The game remained minimized with `window_focused: false` before and after, moved on `s335` from approximately `(396.5, 410.5)` to `(388.01, 358.26)`, recorded four actions/three progress events, and closed the known popup with its marker absent afterward. The 834×615 native PNG changed during the run. Evidence is the local session `linux/ai-sessions/session.iOyr7vqM/background-proof.json`. The close template was derived from the current inspected frame and remains private/excluded from the public kit. These observations verify that background run, not every quest, headless execution or logout/suspend behavior.

A later stop occurred on a type-2 NPC route: the player was approximately 27.13 units from the endpoint on `s255`, and local recovery targeted its blocked center. The worker produced an accepted `WorldMap.path` change that classifies blocked goals as `NoRouteError`; the parent stopped during verification, so that was not a completed automatic repair cycle. The bounded interaction-approach change subsequently passed real-atlas and MotionWatch simulation of the original corner, reaching NPC range in 24 guarded bursts. That is simulation, not a live replay at the old position. A four-cycle live run then crossed `s255` → `s237` → `s202`, and resumed unlimited automation advanced chapter 9 step 2→3. Preserve expected no-route backoff and actual-distance checks; these observations do not establish all-objective completion.

## Automatic inn recovery

`uv run --locked automation.py` also watches the complete party, including reserves. If any Digimon has HP zero, recovery takes priority over quest walking after active battles have been handled. Unknown party telemetry waits. The controller selects the nearest estimated reachable inn from bundled world-map hints and collision paths; it does not choose the cheapest inn. Locked or unusable routes can pause recovery.

At the inn it advances a catalog-matched innkeeper greeting, waits for the genuine inn offer, checks the server-provided BIT price against the wallet, and confirms the selected stay option once with normal Space. Insufficient BIT or an unconfirmed revival pauses instead of repeating purchases. Quest control resumes only after every party member has HP above zero, the inn UI has closed, and world movement is ready. No revival item, cash purchase or direct HP write is used. Inspect `inn-recovery.json` and the supervisor state/events for progress and pause reasons.

A live Forest Inn stay was verified: the server charged 1,520 BIT (52,435 → 50,915; Cash remained zero), Agumon, Palmon and Renamon ended at HP 2,462, 1,202 and 2,002 respectively, and quest control resumed. The initial innkeeper approach was assisted after a distance/facing loop; subsequent greeting pages, genuine offer, payment and revival ran through automation. The approach now uses the client's exact interaction/facing predicate with regression fixtures. A complete unassisted travel-to-revival loop has not yet been verified.

The bridge provides complete-party HP/wallet snapshots and an explicit inn offer/rest state. Nearby NPC interaction IDs are server identifiers, not bundled logical NPC numbers. Inn matching uses the known map/sprite plus exact bundled greeting `text_file`/`text_index`; it must not equate runtime `g` with logical NPC 20 or confuse quest Gatomon 121 with an innkeeper. `InnRoutes.is_inn_dialogue(map, dialogue)` performs the greeting catalog match. A genuine inn offer remains required before spending.

### Verified non-interactive stall repair

The no-progress watchdog launched `codex exec` with 96 filtered game-state samples and a prompt on stdin. The first worker repaired a collision-rejected nonempty travel or NPC GPS route, added replay coverage and exited zero; parent verification passed 251 tests before reloading the supervisor. Subsequent fresh state showed a transfer from s650 to s655. A second worker repaired the NPC-route variant; parent verification passed 258 tests and the character reached the NPC story interaction on s655. Rejected route refresh uses normal G input with unchanged PID/map/quest/position/route checks and existing refresh limits. No collision or modal guard was removed. Queued modal repairs are invalidated by a changed filtered modal snapshot, including closure or incomplete telemetry. Keep the historical interrupted repair separate from this successful cycle.

After a valid static-route rejection, movement backoff is shortened only enough to permit the next rate-limited GPS refresh. The 30-second refresh interval and 60-second local-recovery exclusion remain enforced; saturated movement backoff must not starve refresh.

### Tactical combat and supplies adapter

`BattleControl` reads original g menu rows and emits guarded calls to normal selection, target-cycle, confirm and back handlers. A unique menu generation binds the original first-row object, battle instance, actor, turn order, resources and options. Server waits, intros, transitions, queued animations and result packets block commands. A defeated actor's forced switch chooses a living original enabled reserve, rather than calling forbidden back. A canceled local pre-dispatch decision may release its reservation; an ambiguous RPC outcome remains reserved.

Skill sequence/range/icon values must never be mislabeled damage power. The Python planner learns bounded observed HP-loss samples with an explicit non-causal label. This may guide skill-versus-attack decisions but cannot reconstruct server formulas.

`SuppliesControl` reads aj.bv inventory, aj.bu full HP/DS party, loaded F.O item rules and aj.bA shop offers. It supplies one normal-key plan per state, with explicit submission markers. Native `supplies_step` rechecks the full state token, process/map/quest, live BIT price, quantity, budget and reserve in the same render callback before key-down, with unconditional key-up. Battle transition bn and transport aC are included in the modal/token guard. Snapshot polling does not open menus or load item rules. No raw cv/ce packet construction or HP/DS/inventory/currency writes are used by this adapter.

`ShopRoutes` reuses the inn graph's collision and transition handling with exact merchant NPC22/sprite p038wiza and POI0. Current runtime positions and original facing predicates guide approach; only a genuine buy offer qualifies a purchase. World hints do not establish server access. Recovery waits for inventory and HP/DS or BIT updates; terminal zero-key plans and confirmation timeouts are recorded instead of endlessly resubmitting.

The first live supplies check loaded the rule cache via normal inventory I, reported complete HP/DS/inventory telemetry, closed the inventory, and resumed world movement in four supervised cycles. Existing recovery stock was sufficient, so it did not buy anything. Do not claim that initialization as a live purchase or item-effect verification.

Live tactical combat then selected Golpe de metal for 39 DS and Giga Destruidor for 98 DS through the original menu, with accepted submissions and updated DS. It acknowledged the result, refreshed GPS, recovered the cached route and transferred from s345 to s840. One observed HP-loss comparison was retained. This verifies that battle-to-navigation cycle; item-effect and purchase confirmation remain fixture evidence because existing stock and resources did not require a live purchase/use during the check. The final full suite passed 315 tests; installed-source tactical/supplies smoke checks passed 43, and installer checks passed nine.

### Offense priority and post-battle recovery

The previous 35% all-party battle-heal rule could repeatedly spend active turns on wounded reserves before considering a finishing attack. Replace it with normal-attack baseline/finisher priority, known skill turn savings, and active-only emergency healing. Routine HP/DS and reserve healing use the existing world supplies controller after combat. One submitted battle item requires an accepted attack/skill before another; menu navigation alone does not count. The private persisted streak survives reload.

Battle learning records only a subsequent ready menu or visible result (`result_ready`/`can_advance`), because the raw server result can precede HP animation/events. Attribute enemy loss to the stored submitting actor even if the next actor rotates. Store terminal zero-HP observations separately as capped kill bounds; do not average them as exact full damage. A lower positive-hit quartile with a margin and recorded misses guides estimates. Bounds-only estimates also reflect misses. Unknown enemies get a normal attack baseline; zero observed basic damage permits a bounded affordable skill trial. These are conservative observed-loss heuristics, not a guarantee of damage or victory.

The corrected policy passed 337 full installed-game tests, 65 installed-source combat/recovery fixtures and nine installer checks. The supervisor was reloaded in the existing logged-in JVM; no Java rebuild or game restart was needed. Temporary incomplete menu telemetry preserves accepted healing streaks and pending observations. Unsupported legacy routine-heal intents back out normally after upgrade.

Live verification of the efficiency correction used a normal attack against an enemy with 377 HP, retained a separate observed kill bound of 377, acknowledged the ready result and resumed cached-route walking. No skill or healing item was selected in that encounter. This verifies that observed free-attack/result/navigation cycle; broader combat outcomes remain estimates and fixture coverage.
