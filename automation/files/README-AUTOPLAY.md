# Run DW3 automation

From the installed game directory, run one command:

```bash
uv run --locked automation.py
```

It builds native/runtime outputs when needed, logs in or reuses the monitored game, loads a current game-only input bridge, and starts persistent navigation/interactions. Selected-option combat Space, known-popup dismissal and bounded Codex repair are enabled. An existing controller is detected instead of duplicated.

You still need your original matching game/APK, the Linux build/desktop dependencies, and a one-time private credential setup in `.env` using `.env.example`. Keep actual credentials local. Codex must be installed and authenticated for source repair; use `--no-codex-repair` to disable it. Ordinary control runs in Python without AI calls. Use `--no-battle-space` to wait through ongoing combat instead of confirming its selected option. There is no default end time; `--max-cycles 3` requests a finite check, and Ctrl+C stops foreground control. Current background-capable bridges allow an unfocused or minimized game; legacy bridges still need focus. Story choices, stale state and unsupported objectives can pause it. Combat Space confirms the selected option without item/tactical selection or auto-battle bypasses.

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

A real Codex worker proposed accepted missing-route handling. Its verification was stopped, so the complete automatic repair/restart chain remains unverified; a stop during verification is `repair_interrupted`, not a successful verified repair or a worker failure.


## Automatic inn recovery

The default controller also has a no-progress watchdog. Repeated failed navigation or input guards can start a non-interactive `codex exec` repair after 60 seconds; eligible idle stories use 180 seconds. It passes a bounded, filtered game-state log and the repair prompt through stdin. Normal combat, typing, choices and missing funds are excluded. Repairs retain their attempt/cooldown limits and must pass the complete test suite before automation reloads. Inspect `repair-state.json` and `repair-game-state.json` in the current session for progress.

`uv run --locked automation.py` also watches the complete party, including reserves. If any Digimon has HP zero, recovery takes priority over quest walking after active battles have been handled. Unknown party telemetry waits. The controller selects the nearest estimated reachable inn from bundled world-map hints and collision paths; it does not choose the cheapest inn. Locked or unusable routes can pause recovery.

At the inn it advances a catalog-matched innkeeper greeting, waits for the genuine inn offer, checks the server-provided BIT price against the wallet, and confirms the selected stay option once with normal Space. Insufficient BIT or an unconfirmed revival pauses instead of repeating purchases. Quest control resumes only after every party member has HP above zero, the inn UI has closed, and world movement is ready. No revival item, cash purchase or direct HP write is used. Inspect `inn-recovery.json` and the supervisor state/events for progress and pause reasons.

A live Forest Inn stay was verified: the server charged 1,520 BIT (52,435 → 50,915; Cash remained zero), Agumon, Palmon and Renamon ended at HP 2,462, 1,202 and 2,002 respectively, and quest control resumed. The initial innkeeper approach was assisted after a distance/facing loop; subsequent greeting pages, genuine offer, payment and revival ran through automation. The approach now uses the client's exact interaction/facing predicate with regression fixtures. A complete unassisted travel-to-revival loop has not yet been verified.
