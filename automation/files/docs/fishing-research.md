# Fishing research

Original artifact: `app/client.jar`, SHA-256 `7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe`.
CFR 0.152 SHA-256 `f686e8f3ded377d7bc87d216a90e9e9512df4156e75b06c655a16648ae8765b2` produced `/tmp/dw3-fishing-analysis/*.java`. A local Python translation of original `aE.a(String)` decoded string constants into `*.decoded.java`; no game code ran.

REA `capture_process_scenario` ran `javap -p -c -classpath app/client.jar J bB`, exit zero, evidence `ev_f509acb9dfdc25c007368da9ef4fc5d558d06827114556c5dfeaeed1033ff6aa`. Raw PTY retained 26,455/26,455 bytes; cumulative rendered output truncated. REA process capture labels artifact identity unknown; the hash above comes from separate local SHA-256 and is not an atomic process-binding proof. This is bytecode inspection, not live fishing proof.

## Destination

Bundled English `places.json[36]` is `Divermon's Lake`. World map primary world spot 23 has `ids:[s380]`, local fishing POI `[5,590,519]`, size 1280x1024. Alternate world same spot uses `[s381,s950]` and same POI. World spot links go to spot19 and25; no doors/passages directly from this spot. POI coordinates are hints; they do not establish a castable shore or server-permitted fishing. Actual accepted coordinate must be verified by `aj.ap` from server messages. NPCs on s380 include logical33/75/103/212; none is needed for the normal cast/reel interaction.

Original English sidequest dialogue says Tai Kong Wang makes a fishing pole from Bamboo Spear, Spider Web, Red Snapper. No verified inventory rule identifying the current character's rod ownership was found. Snapshot reports rod_available null; it must not invent ownership from POI presence.

## Original fishing UI

`aj.decoded.java:463 c()` consumes normal Space: active minigame `ag.b()` triggers the original reel command and sets `ag.f`; with no game, aq>=0/ar<0/aV-as>=1 triggers the original cast. `aj.p():1940` first checks bn/battle/story/dialogue/other guards, then calls c(). The automation must send only the ordinary Space callback after fresh checks, never construct packets or call c() directly.

`ap` is the server-provided allowed fishing facing (`255` disabled). `az` is player facing. Original `bB.a(ap,az)` allows the same or neighboring facing (difference mod8 is0/1/7). Casting animation readiness `aj.c(float):443` additionally requires ag null, aM/aX/ba/bn/aC null, ac/G<0, and one-second cooldown. `J` minigame `ag` is constructed only by original incoming fishing message; its d is fishing type, e is the displayed `Lançamentos` value, h is elapsed frames, f is submitted, a() is (int)(h-91), and b() allows reeling only d!=255,!f,h>=91. Neither snapshots nor policy advance these values.

`aj.e():485` implements optional original automatic fishing, gated by server VIP/time flag be. Do not toggle be or buy VIP. Its exact success timing can be reused independently: `bB.b(type,bB.a(n,false))==2 && (bB.b(type,bB.a(n,true))==2 || n>=96)`. Class bB contains pure integer reflection/drag trajectory functions and a 9-row outcome table. Type8 is exhausted and displays `A pesca deste mapa acabou: saia e volte para pescar de novo.` (leave and return to fish again); this is not a good reel window. Original X can cancel a ready active minigame; do not invoke cancellation without a distinct bounded policy.

`aj.C():3059` is the existing pure world UI readiness predicate and permits ag presence. Extra original movement overlays (`aj.f(float):2032`) must also suppress cast/reel input, including inventory, shop, chat, GPS, transport, story, battle, menus and transition. `FishingControl.snapshot` uses pure reads and pure original C/J/bB methods; any missing field/method or invalid timing produces incomplete telemetry and no readiness. Tokens bind the screen/minigame object, facing, submission and modal state, while excluding continuous timer drift. The input dispatcher must validate expected state_token and recheck readiness on the render thread. Strict `reel` still requires can_reel&&reel_good; the explicitly selected best-effort `reel_attempt` requires can_reel after the Python wait budget. Submitted, stale, modal and incomplete states remain blocked for either mode. A token alone never authorizes input.

## Verification

`test_fishing_control.py` compiles an isolated aj/J-shaped fixture with the actual original bB class on the classpath. It checks snapshot purity, cast facing/cooldown/release state, minigame timing/submission, an actual good reel window, exhaustion, overlays, stable tokens under elapsed-frame drift, changed minigame tokens and missing telemetry. Focused test passed. This establishes policy/readiness fixture behavior, not actual live casting, caught fish, shoreline reachability or fishing tool ownership.

## Choose main quest or fishing

Run one activity from the installed game directory:

```bash
uv run --locked automation.py fishing
uv run --locked automation.py main-quest
uv run --locked automation.py after-loss
```

`fishing` immediately travels to Divermon's Lake and fishes without waiting for a battle loss. `main-quest` runs quest automation without the loss-triggered fishing switch; it is also the default for bare `uv run --locked automation.py`. `after-loss` explicitly enables the earlier rule: count complete, visible defeat results once per native battle ID and switch to fishing after one additional confirmed loss. Victory, escape, early result packets and an individual fainted Digimon do not count. The private session file `fishing-goal.json` persists the count and fishing state; `autoplay-state.json` publishes `activity` and `fishing_goal`.

Starting the same running activity returns `already_running`. Requesting a different activity asks the current controller to stop, waits up to 15 seconds for its singleton lock, then starts the requested activity. If the old controller is still stopping, the command reports that condition and starts no duplicate controller. `uv run --locked automation.py --stop` stops the current activity.

Fishing takes priority over quest and inn/shop detours. Incidental encounters still use the battle controller, while ready dialogue, stories and known popups retain their handlers. The destination is s380, with alternate-world variants s381/s950. Routing uses exported world links and collision checks. For a known interior absent from the world graph, a fresh enabled type-1 GPS endpoint can authorize one bounded exit; fishing replans after the actual map change. This fallback does not follow main-quest GPS continuously. Other missing links remain reported waits.

The map marker at (590,519) lies on a disconnected island. `ShoreApproach` searches the current collision component, caches up to 24 separated shoreline candidates, and requires fresh server `at_spot` telemetry before casting. The first mainland candidate (486.5,571.5) has bounded collision paths from both known entrances (340,106) and (1199,886). Travel stops when a usable server fishing spot appears; unconfirmed reached hints are recorded as probes and skipped later. Local route estimates cap search at 12,000 nodes. Casting requires the original spot/facing and cast readiness. Reeling prefers the original good timing predicate, checked again on the render thread. If the current cast has waited two seconds without a usable good window, the Python controller may request one best-effort `reel_attempt` instead of waiting indefinitely. Both use ordinary Space with unconditional release; best-effort timing does not guarantee a catch or landing in the green band.

The original per-cast `cast_count` comes from the server and is displayed as “Lançamentos”. Following the user's 15-to-zero bait rule, the controller stores complete integer readings from 0 through 15 as `bait_remaining`, retains the last value when the minigame disappears, and requests a lake refresh at zero. It finishes the final good-window reel, result and any battle before leaving; zero blocks a new cast rather than discarding the pending catch. Idle rod pose can keep `fishing.active` true, so readiness to leave uses the absent minigame (`fishing_type: null`), closed modals and world readiness. An actual map exit clears stale bait readings and shoreline probes; the controller returns to the lake and reads the new count from fresh server telemetry. Type-8 exhaustion also uses normal acknowledgement followed by exit and re-entry. No VIP flag, resource, fishing result or packet is written directly.

A live fishing run reached s380, accepted ordinary cast/reel inputs, handled fishing encounters and observed server counts 15 → 14 → 13 → 12 → 11. The full suite passed 396 tests. Live depletion to zero, exit via s355, return to s380 and replenishment to 15 were verified, followed by another cast. The decreasing per-cast sequence supports the user's remaining-bait interpretation; static code alone labels it only as casts. The inventory rule identifying rod ownership remains unknown, and no caught-fish outcome is established by these checks. A missing route, unconfirmed shoreline or incomplete fishing state produces a reported wait. The preceding source analysis records provenance and limits.

### Live fishing evidence

The explicit `fishing` activity reached s380 near (835.5,524.5). Native telemetry reported `at_spot: true` and `cast_facing: 2`; repeated ordinary cast and reel operations returned `fishing_cast_ready` and `fishing_reel_ready`. Server-displayed counts decreased 15 → 14 → 13 → 12 → 11, and incidental fishing battles remained under the existing battle controller. The complete updated suite passed 396 tests. These observations verify repeated fishing input and decreasing counts at this location. Subsequent live checks verified zero bait, an automatic s380 → s355 → s380 transition, replenishment to 15 and resumed casting. A specific caught-fish reward remains unverified.

### Bounded best-effort reel fallback

A live hard fishing bar remained ready at type 1, frame 5069 and displayed count 10 while the strict good-window predicate stayed false. The user requested best-effort timing rather than indefinite waiting. The controller therefore prefers a good window for up to two seconds per cast, then may submit one normal Space through `reel_attempt` if the original UI still permits reeling. The native `reel` mode retains its strict timing predicate. The new native fixture first reproduced a missing best-effort action, then passed after implementing the separate mode; it also checks stale tokens, submitted casts, missing telemetry and active modals. No VIP state, game resource, result or packet is changed directly. This verifies adapter policy, not reel accuracy or a successful catch on every difficult bar.

The updated native best-effort reel was accepted live (`fishing_reel_attempt_ready`), and fishing continued beyond the stalled count of 10 to lower counts. The complete suite passed 396 tests; installed-source command/fishing checks passed 58 and installer checks passed nine. Accepted input does not guarantee a green-band result or a catch.

### Verified bait refresh

On 15 November 2026, the final controller observed zero bait at 06:41:54 UTC, left s380 for s355 by 06:42:54, returned to s380 by 06:43:00, and accepted a new cast with server count 15 at 06:43:30. The private session proof records these map/count transitions. The process remained in explicit fishing mode and continued handling the resulting encounter. This verifies the observed automatic depletion/exit/re-entry/replenishment loop; it does not guarantee a green-band result or a specific reward.
