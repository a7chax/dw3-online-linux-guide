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

`aj.C():3059` is the existing pure world UI readiness predicate and permits ag presence. Extra original movement overlays (`aj.f(float):2032`) must also suppress cast/reel input, including inventory, shop, chat, GPS, transport, story, battle, menus and transition. `FishingControl.snapshot` uses pure reads and pure original C/J/bB methods; any missing field/method or invalid timing produces incomplete telemetry and no readiness. Tokens bind the screen/minigame object, facing, submission and modal state, while excluding continuous timer drift. The input dispatcher must validate expected state_token and recheck can_cast or can_reel&&reel_good on the render thread. A token alone never authorizes input.

## Verification

`test_fishing_control.py` compiles an isolated aj/J-shaped fixture with the actual original bB class on the classpath. It checks snapshot purity, cast facing/cooldown/release state, minigame timing/submission, an actual good reel window, exhaustion, overlays, stable tokens under elapsed-frame drift, changed minigame tokens and missing telemetry. Focused test passed. This establishes policy/readiness fixture behavior, not actual live casting, caught fish, shoreline reachability or fishing tool ownership.

## Switch to fishing after the next loss

Full automation now counts complete, visible `defeat` results by native battle ID. After one additional confirmed loss it acknowledges the result normally and switches from main-quest travel to Divermon's Lake (s380; alternate-world variants s381/s950). Victory, escape, early result packets and an individual fainted Digimon do not count. The private session file `fishing-goal.json` retains the count and fishing goal across Python controller restarts; `autoplay-state.json` includes `fishing_goal`. The new counter starts at zero when first enabled, without counting historical logs.

Fishing mode takes priority over quest and inn/shop detours. Unavoidable encounters still use the battle controller; normal ready dialogue, stories and known popups retain their handlers. Routing uses exported world links and collision checks. At the lake, the bundled (590,519) fishing POI is an approach hint. Casting requires fresh server-provided fishing-spot direction and original cast readiness. Reeling requires the original good timing predicate, validated again on the render thread. Normal Space performs both actions through the original game UI. Exhaustion is acknowledged, followed by a collision-validated exit and return. No VIP flag, resource, fishing result or packet is written directly.

A missing route, unconfirmed shoreline or incomplete fishing state produces a reported wait instead of reverting to quest travel or blindly pressing Space. Rod ownership is unknown until supported by real game behavior. Static/fixture verification does not prove that this account has the required tool or has caught fish. See `docs/fishing-research.md` for provenance and limits.

The map marker at (590,519) lies on a disconnected island. `ShoreApproach` searches the current collision component, caches up to 24 separated shoreline candidates, and requires server `at_spot` telemetry before casting. The first mainland candidate (486.5,571.5) has bounded collision paths from both known entrances (340,106) and (1199,886). Reaching that candidate is not proof of a fishing trigger. Travel stops immediately when a fresh server fishing spot appears; unconfirmed reached hints are recorded as probes and skipped on later attempts. Local route estimates cap search at 12,000 nodes instead of exhausting the entire map.
