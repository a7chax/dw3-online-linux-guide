# Local World Atlas and Quest State

The inspected client version 0.1.95 exposes 300 map directories after normal login. The local export contains all 300 definitions and 299 collision masks. Map `s415` has no mask; the client uses rectangular map bounds there.

The atlas includes maps this character has not visited. Coordinates use the map ID plus local world pixels: X increases right and Y increases down. For example, `s450` (Bulk Bridge) is 1792 by 1024 and `s465` (Tranquil Swamp) is 1408 by 768. All 299 exported masks are grayscale images matching their map's dimensions.

## Inspect or refresh

```bash
python3 ai-game.py export-world
python3 world_map.py list
python3 world_map.py info s465
```

Export uses the authenticated client's original asset reader. It saves metadata and collision masks, not protection keys. The exporter captures the asset-reader reference on the render thread and performs asset reads and file output on its separate control worker.

Files under `linux/world/`:

| File | Content |
| --- | --- |
| `atlas.json` | Map dimensions, source files, collision hashes, coverage and failures. |
| `maps/MAP/metadata.json` | Map metadata. |
| `maps/MAP/collision.png` | Walkability raster where available; a nonzero first-band value is traversable in the original client. |
| `auxiliary/npcs.json` | 1,490 bundled NPC definitions, including logical IDs, map IDs and character assets. |
| `auxiliary/worldmap/world.json` | World overview placements: 123 spots each for Asuka and Amaterasu, covering 232 distinct map IDs. These placements do not establish exit destinations. |
| `last-path.json` | Last path calculated with `world_map.py path`. |

## Plan or walk without a GPS trace

Calculate a path from known coordinates entirely locally:

```bash
python3 world_map.py path s465 --start 789.5 504.5 --goal 442 178
```

The first live-asset planning check took about 206 milliseconds. Later collision checks use conservative raster-cell traversal and a finer search fallback for narrow passages. Planning time varies with the map and destination.

Walk to coordinates on the current map:

```bash
python3 ai-game.py navigate --map s465 --x 442 --y 178 --seconds 30
```

Use coordinates appropriate to the intended map. `--map` rejects a mismatched starting map. The command uses the local collision atlas, ignores missing GPS dots, and continues reading actual player position while walking. It stops near the destination. Add `--cross-map` for a known exit destination when a short forward movement is needed to activate the exit.

Static collision data does not include every live NPC, player, quest gate or temporary obstacle. A destination in blocked terrain is rejected. The atlas has no complete verified graph of map-to-map exits; knowing all client terrain does not yet imply unattended travel between every map.

For GPS navigation across several maps:

```bash
python3 ai-game.py follow --seconds 60 --continuous
```

This command still uses server GPS routes. It stops for focus loss, required interaction, expiry or lack of progress. It does not turn local navigation into a quest-completion bot. Only one input controller can own a monitored session at a time.

## Read the main quest

```bash
python3 ai-game.py quest
```

The live `main_quest` object contains chapter, chapter count, step, step count, target map, raw action code and the client's HUD-objective formatter text. The enriched command matches that progress against `quests/steps.json` inside the original JAR and labels derived actions such as `talk`, `enter`, `zone` or `drop`. Unknown definitions remain unknown. The raw `progress_value_f` is not an established NPC ID.

`quest-state.json` records the enriched result in the latest session. A verified example is chapter 5 of 36, step 1 of 6, target `s470` (Swamp Inn); the matched bundled instruction is talk to logical NPC 121. Gatomon was observed in the normal interaction. Runtime entity IDs and bundled logical NPC IDs can differ; do not equate them from numeric similarity.

```bash
python3 ai-game.py interact
```

This sends the normal Space interaction key. It saves a screenshot and `interaction-state.json`. Updated control status includes dialogue text and text-file/index identifiers. Inspect the state after each interaction and verify a changed quest step before claiming progression. The command does not select menu choices or spend resources automatically.

To advance a bounded conversation from its actual page state:

```bash
python3 ai-game.py talk --seconds 30 --max-pages 12
```

This waits for the current page to finish typing before sending Space. It reads page/typing state without calling the client's reveal/advance action. It stops on focus loss, invalid state, dialogue closure, a changed quest step or its time/page limit, and saves `talk-state.json`. Live validation completed three pages of Gatomon's conversation and confirmed chapter 5, step 1 (`s470`) changed to step 2, Shaman House (`s475`).

A separate live local-navigation check on `s470` moved from `(304.5, 342.5)` to `(332.62, 342.5)` for goal `(335, 342)`, with `destination_reached` and `navigation_source: local_collision_atlas`. The saved plan took 0.15 milliseconds and did not use the GPS route; the proof is in `linux/diagnostics/local-navigation-proof.json`.

## Evidence and reproduction

The original `app/client.jar` SHA-256 is `7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe`. REA bound that exact JAR. Its archive inventory rejected case-distinct obfuscated classes (`k$A.class` and `k$a.class`); inspection continued with CFR 0.152 and `javap` against the unchanged JAR.

Relevant inspected code: `aa` reads `maps/<id>/map.json` and collision coordinates; `bC` indexes raster band zero without scaling; `bo` exposes additional asset packs after normal authentication; `al` stores quest progress and formats its objective. The new Java adapter is in `linux/native/src/dw3/linux/WorldAtlas.java`, `StatePrinter.java` and `ControlBridge.java`.

```bash
python3 -m unittest discover -s linux/native/tests -p 'test_*.py' -q
```

The reusable agent instructions are [skills/dw3-linux-control/SKILL.md](skills/dw3-linux-control/SKILL.md). Codex and Claude Code registrations point to that maintained source.

## Inspect every bundled main quest without playing it

The complete main-quest sequence bundled with client 0.1.95 has 36 chapters and 113 ordered steps: 55 talks, 17 `enter` steps, 40 `zone` steps and one `drop` step. The client presents `drop` as winning battles. The ordered steps use 68 maps. Chapter place lists are summaries and do not replace step order or prove exit connections.

```bash
python3 quest_catalog.py list
python3 quest_catalog.py chapter 5
python3 quest_catalog.py export
```

These commands only read local files. They do not log in, move, interact, or advance progress. The full outputs are [main-quests.md](linux/quest-catalog/main-quests.md) and [main-quests.json](linux/quest-catalog/main-quests.json).

To regenerate the English map/NPC text enrichment through the original offline reader:

```bash
python3 scripts/export-quest-text.py
python3 quest_catalog.py export
```

The standalone reader exports only `text/en/places.json` and `talk0.json` through `talk10.json`. It does not need the running client or credentials. The catalog preserves source data and leaves missing chapter titles, exact trigger conditions, rewards, prerequisites and server-only quests unknown. A full bundled sequence is not a complete server walkthrough.
