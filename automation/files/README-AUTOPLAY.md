# Run DW3 automation

From the installed game directory, run one command:

```bash
uv run --locked automation.py
```

It builds native/runtime outputs when needed, logs in or reuses the monitored game, loads a current game-only input bridge, and starts persistent navigation/interactions. Tactical battle choices, HP/DS supplies, known-popup dismissal and bounded Codex repair are enabled. An existing controller is detected instead of duplicated.

You still need your original matching game/APK, the Linux build/desktop dependencies, and a one-time private credential setup in `.env` using `.env.example`. Keep actual credentials local. Codex must be installed and authenticated for source repair; use `--no-codex-repair` to disable it. Ordinary control runs in Python without AI calls. Use `--no-battle-space` to wait through ongoing combat instead of making battle decisions. There is no default end time; `--max-cycles 3` requests a finite check, and Ctrl+C stops foreground control. Current background-capable bridges allow an unfocused or minimized game; legacy bridges still need focus. Story choices, stale state and unsupported objectives can pause it. The current bridge exposes normal battle menus for guarded skill, item and forced party-switch decisions; older direct supervisors retain selected-option Space compatibility.

Keyboard and popup clicks use private game callbacks rather than host XTest injection or desktop sharing. Current capture reads the game framebuffer without activation; legacy focus/capture use local X11. The entry point checks loaded input capabilities and can rebuild/restart a stale monitored game; it has no host-input fallback.

For minimized operation, use the same command and check `background_input_enabled: true` in status. The loaded bridge must advertise `native_background_input: true` and `native_capture: true`. The entry upgrades an older bridge with one rebuild/restart/login; existing running Java processes do not gain capabilities from a source update alone. You can then minimize the game or use another window without the controller bringing it forward. The desktop session and game/OpenGL process must remain running; this is not a headless mode and does not promise operation after logout or suspend.

Live verification kept the game minimized and unfocused across four cycles, closed its known popup, and moved the character with fresh native screenshots. There were four actions and three progress events; these are observed workflow changes, not completed quest counts.

Inspect or stop from another terminal, without setup, login or game input:

```bash
uv run --locked automation.py --status
uv run --locked automation.py --stop
```

Only one supervisor may control a session. If `latest` changes, use the advanced `uv run --locked autoplay.py --session /absolute/original/session --status` or `--stop` to address the old supervisor. For an already prepared monitored game, advanced direct commands remain available: `uv run --locked autoplay.py --resume --battle-space --repair-with-codex`, with direct `--status` and `--stop`. That supervisor command reuses a logged-in world rather than doing setup/login.

Automatic popup closure requires the locally supplied `linux/ui/popup-close.png`. It checks the known icon before movement, at most once every two seconds, clicks through the game bridge and verifies its disappearance. Missing templates skip detection; unknown popups and choices are not recognized. The public kit excludes game-derived templates.

After a battle, an empty GPS reply gets an immediate refresh and a two-second reply window. If needed, the controller can use its previously observed same-map/same-quest endpoint with validated local collision routing. It preserves NPC interaction and exit handling, and retains the legacy focus pause only when background capability is absent. Its validated `autoplay-route-cache.json` survives a supervisor restart for the same game/session identity. Without an observed endpoint, it cannot reconstruct that missing route.

NPC recovery targets a validated clear approach within 24 world units, rather than the NPC's potentially blocked center. It keeps actual NPC distance and facing checks; stale GPS step counts do not prevent interaction when already near. An unavailable approach backs off without requesting a code repair. After this fix, a four-cycle live run crossed several maps and the resumed unlimited run advanced chapter 9 from step 2 to step 3. Unsupported objectives and real obstacles can still pause automation.

If the game opens but the character stays still, read `uv run --locked automation.py --status` and the session events first. A resized/unavailable window now produces a bounded `window_unavailable` pause instead of letting an X11 capture error terminate Python; restore the same window on a legacy capture/focus path. Legacy X11 captures query its actual size every time; the current bridge captures its framebuffer. A valid foot position clipped by the planner's extra clearance margin can use a short, checked escape to a normally padded landing. Genuinely unavailable routes stop with `local_route_unavailable`; blocked cached recovery backs off for 60 seconds rather than repeatedly running the planner.

State is saved under `linux/ai-sessions/latest/`: `autoplay-state.json`, `autoplay-events.jsonl`, and `autoplay-actions.log`. Optional repairs write `repair-state.json` and `repairs/NNN-*/`. Three matching eligible failures are required before a worker; focus/battle/choice pauses do not trigger one. The worker pauses gameplay input, fixes Python source with regression coverage, and must pass the full locked suite before the supervisor restarts on the same game/session. It retains sandbox and approval checks and may wait for approval. Repairs are bounded to three workers per session, one attempt per failure identity and a ten-minute cooldown. Live successful exception repair has not yet been demonstrated.

Read [AI-GAME-CONTROL.md](AI-GAME-CONTROL.md) for supported states, movement recovery, evidence and troubleshooting. Codex or Claude Code can reuse [the DW3 control skill](skills/dw3-linux-control/SKILL.md); REA is needed when adapting a different game version, rather than for ordinary autoplay.

Earlier verification passed 127 regression tests through uv. The persistent supervisor encountered a new random battle, confirmed combat and result screens with normal Space, then resumed walking without further operator input. That observed flow is recorded in `linux/diagnostics/autoplay/13-autonomous-random-battle-proof.json`; it does not establish every encounter or full quest completion.

Publication verification: the post-battle recovery update passed **133 controller tests** under uv. The exact source-kit payload was installed into an isolated temporary game layout and passed the same 133 tests using local original inputs. Its separate source installer passed **eight tests**. No credentials, original game binaries, map/dialogue exports, screenshots, or private sessions are included in the public kit.

Game-local input verification: the corrected popup command removed the visible Halloween panel; its close marker disappeared in the saved after image. The new key operation changed live GPS from enabled to disabled and back to enabled. The Python input helper no longer invokes XTest, and legacy login uses the local control bridge. These checks validate game-local input; an already-open GNOME sharing dialog can be cancelled instead of granting desktop sharing.

Integrated entry-point verification: `uv run --locked automation.py --max-cycles 2 --no-codex-repair` reused the logged-in world, moved into the quest target map, and aligned at its NPC. The full suite at that stage passed **148 tests** under uv, including automatic known-popup checks before navigation and the one-command setup fixtures. The standalone source installer has eight separate passing tests.

Startup recovery was also verified live: the two-cycle one-command entry moved from the recorded stuck position near `(776.5, 297.66)` on `s205` to `(1209, 472.75)` on `s330`, with two actions and two progress events and no AI game input. A deliberately oversized X11 capture error was trapped, and the next capture succeeded. These checks cover the observed resize/collision-margin failures, not every route or objective.

An earlier missing-route repair was interrupted during verification and recorded as `repair_interrupted`. A later non-interactive repair completed: the worker exited zero, the parent passed 251 tests, reloaded automation and the character moved from s650 to s655. This verifies that repair cycle; it does not establish autonomous completion of every quest.


## Automatic inn recovery

The default controller also has a no-progress watchdog. Repeated failed navigation or input guards can start a non-interactive `codex exec` repair after 60 seconds; eligible idle stories use 180 seconds. It passes a bounded, filtered game-state log and the repair prompt through stdin. Normal combat, typing, choices and missing funds are excluded. Repairs retain their attempt/cooldown limits and must pass the complete test suite before automation reloads. Inspect `repair-state.json` and `repair-game-state.json` in the current session for progress.

`uv run --locked automation.py` also watches the complete party, including reserves. If any Digimon has HP zero, recovery takes priority over quest walking after active battles have been handled. Unknown party telemetry waits. The controller selects the nearest estimated reachable inn from bundled world-map hints and collision paths; it does not choose the cheapest inn. If the route or keeper is unreachable, defer the inn trip for five minutes and resume the main quest with the living party. Three failed travel or interaction attempts also defer recovery. A reachable nearby keeper can interrupt the cooldown; the fainted member remains fainted until a confirmed stay.

At the inn it advances a catalog-matched innkeeper greeting, waits for the genuine inn offer, checks the server-provided BIT price against the wallet, and confirms the selected stay option once with normal Space. Insufficient BIT or an unconfirmed revival pauses instead of repeating purchases. After a submitted stay, quest control resumes only when every party member has HP above zero, the inn UI has closed, and world movement is ready. A deferred unreachable trip permits quest progress without claiming revival. Unknown party telemetry, an all-fainted party, insufficient BIT at an open offer, and unconfirmed payment or revival retain their wait guards. No revival item, cash purchase or direct HP write is used. Inspect `inn-recovery.json` and the supervisor state/events for progress and pause reasons.

A live Forest Inn stay was verified: the server charged 1,520 BIT (52,435 → 50,915; Cash remained zero), Agumon, Palmon and Renamon ended at HP 2,462, 1,202 and 2,002 respectively, and quest control resumed. The initial innkeeper approach was assisted after a distance/facing loop; subsequent greeting pages, genuine offer, payment and revival ran through automation. The approach now uses the client's exact interaction/facing predicate with regression fixtures. A complete unassisted travel-to-revival loop has not yet been verified.

Queued modal repairs are discarded if the modal closes or its filtered state changes. An unreachable nonempty travel or NPC GPS route can be refreshed with normal G input after collision-path rejection; existing guards and refresh limits still apply.

After a valid static-route rejection, movement backoff is shortened only enough to permit the next rate-limited GPS refresh. The 30-second refresh interval and 60-second local-recovery exclusion remain enforced; saturated movement backoff must not starve refresh.

## Skills and HP/DS supplies

The complete entry enables `native_battle_control` and `native_supplies_control`, rebuilding and restarting an old monitored bridge when needed. `--no-battle-space` disables active-combat decisions; result acknowledgement remains normal Space.

`battle_policy.py` checks normal attacks and known finishing skills before collecting another baseline. An affordable known skill finisher takes precedence over a basic probe when the basic outcome is unknown. It compares conservative observed HP-loss estimates with current enemy HP. An estimated normal-attack finisher takes precedence over skill/item use. A known skill can finish or reduce estimated turns; ordinary skill use retains 10% maximum DS, while an affordable known finisher may use that reserve when necessary. Unknown skills can be explored after a basic baseline exists whenever the normal attack cannot finish, including an estimated two-hit enemy, with sufficient DS. A known normal-attack finisher still takes precedence and spends no DS.

Routine HP/DS recovery and injured reserves wait until after combat. Only the active fighter can request emergency battle healing: HP at or below 15%, or danger indicated by observed incoming HP loss. A heal that leaves the fighter in the same predicted danger is skipped. After one submitted battle item, an accepted attack or skill is required before another; opening item submenus alone does not count as an item. The restriction survives controller restart.

Incoming damage and offensive estimates are observations, not a recovered server formula. Skill animation/range fields are not power. Positive hit estimates use a lower observed quartile, safety margin and recorded misses. Killing hits are capped by the enemy's remaining HP and stored separately as observed kill bounds, with miss weighting. Learning waits for a ready turn or visible result; an early result packet does not finalize unfinished HP animations. The original submitting actor remains attributed when the next controllable actor changes. Missing targets do not authorize invented kills.

Outside combat, `supplies_recovery.py` uses owned recovery items when HP is at or below 65% or DS at or below 25%. It reads genuine loaded item rules; names are insufficient to classify an item. It uses normal I/directional/Space menu actions, confirms inventory and HP/DS changes, and preserves inn recovery for fainted members.

When supplies are low, it estimates a route to an item merchant from bundled POI type 0 and current collision masks, then requires a real shop offer. The target is three HP and three DS recovery items. Each restock run may spend at most 10% of its initial BIT wallet, capped at 5,000 BIT, while retaining 5,000 BIT; each purchase has quantity at most five. Runtime BIT prices and wallet are checked again for every input. Cash, equipment, permanent-stat chips and raw inventory/currency writes are excluded. Unknown offers or unavailable routes do not authorize purchases. World-map hints cannot prove server unlocks.

A submitted purchase waits for both stock gain and a matching BIT decrease. A used item waits for quantity loss and HP/DS gain. Missing confirmations time out into a recorded issue and guarded closure/backoff; they are not retried as successful transactions. Inspect `battle-decisions.json`, `battle-learning.json`, `supplies-recovery.json` and `autoplay-state.json` in the private session. Story choices and unknown UI still require inspection.

Live inventory initialization was verified after loading both new capabilities: normal I opened and closed the inventory, pure snapshots read the loaded recovery effects and stock, and four supervised cycles resumed navigation. Sufficient existing HP/DS stock correctly avoided a purchase. A subsequent random battle used Golpe de metal (39 DS) and Giga Destruidor (98 DS), received a ready result, refreshed/recovered GPS and transferred from s345 to s840. One observed enemy HP-loss sample was saved. That verifies skill submission, result handling and resumed movement for that encounter. Purchases and actual healing effects are fixture-tested but were not needed in this live check.

Live verification of the efficiency correction used a normal attack against an enemy with 377 HP, retained a separate observed kill bound of 377, acknowledged the ready result and resumed cached-route walking. No skill or healing item was selected in that encounter. This verifies that observed free-attack/result/navigation cycle; broader combat outcomes remain estimates and fixture coverage.

Finishing priority is based on avoiding an extra enemy response: normal attack when estimated sufficient; otherwise the least-DS available known finishing skill, even before an additional basic probe. If neither is known to finish, compare estimated turns and allow bounded skill trials when basic damage is insufficient. These remain observed-loss estimates rather than guaranteed kills.

Inn/shop world-hint routing now rejects optimistic current-map leave-and-return cycles when the re-entry region is already collision-reachable. Legitimate disconnected-region detours remain. The corrected live tower route reached Mirage Hall; revival there was not verified because the observed entry region could not reach its innkeeper.
