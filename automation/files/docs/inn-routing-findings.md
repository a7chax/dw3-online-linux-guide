# Inn routing evidence

Inspected client SHA256: `7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe`.
This is static analysis plus offline reads of the original reader, not live input.

* `U` is the inn menu, stored in `aj.bz`. The `bI.aJ` server event creates
  it; `bI.aK.a()` supplies the success boolean. `U.c` holds the offer record:
  `a` selects an inn title, `c` is the displayed Digimon count, `d` is total
  BIT price. `b` is unused in this UI. Price is supplied by the server; the
  UI says each Digimon pays according to level. `aj.bt`/`bI.cx.a()` is BIT.
* `U.d` is enum `U$a`: `a` offer, `b` submitted, `c` rejected, `d` resting,
  `e` closed. Selected option `U.e` defaults to zero. Normal confirmation
  calls `U.b(true)` only for selection zero, sending `bI.aI(true)`. A success
  starts a 4.333-second animation, then closes. No HP mutation is performed
  by this menu: recovery must be verified from subsequent party snapshots.
* `P.h()` accepts Enter, keypad Enter, Space and Z. The original
  `text/en/inn.json` entries 18, 19 and 20 are respectively “Stay in Inn”,
  “Do not stay in Inn”, and the insufficient-BIT message. Never infer that
  a closed menu alone means revived party members.
* `auxiliary/npcs.json` marks innkeepers as logical NPC 20, character
  `p039tail`, in 25 maps. Logical NPC 121 is also Gatomon in Swamp Inn but
  is a quest character. Exact NPC coordinates are supplied by server
  `aj.Y` records `bI.bg`: `c` x, `d` y, `g` runtime interaction identifier, `b` entity ID. Runtime `g` is not the bundled logical NPC ID. Match inn candidates by verified map/sprite and exact catalog greeting, then require the genuine offer.
* `auxiliary/worldmap/world.json` provides `spots`, `links`, `passages`,
  and `doors` per world. Links have two explicit endpoints. Passages have
  directed `spot`/`to` endpoints. Only POI type 2 identifies inns. Merely
  matching `doors.ids` is insufficient: e.g. Lamb Chop shares an inn ID.
  `spots.at` offsets are added to each map's coordinates to obtain common
  spot coordinates, before adding the spot's world position.

`InnRoutes.plan(map,x,y,excluded=())` returns serializable estimated costs
and legs. Current-map approach paths are checked against exported collision
masks. Future legs use geometric cost and require a fresh replan after each
actual transfer. Interior final legs use null coordinates until the runtime
NPC is known. Interior exit coordinates are not supplied by this resource,
so the planner does not invent reverse door movements. World-map hints do
not prove server unlock state, current doors, or battle-free reachability.

## Automatic inn recovery

`uv run --locked automation.py` also watches the complete party, including reserves. If any Digimon has HP zero, recovery takes priority over quest walking after active battles have been handled. Unknown party telemetry waits. The controller selects the nearest estimated reachable inn from bundled world-map hints and collision paths; it does not choose the cheapest inn. Locked or unusable routes can pause recovery.

At the inn it advances a catalog-matched innkeeper greeting, waits for the genuine inn offer, checks the server-provided BIT price against the wallet, and confirms the selected stay option once with normal Space. Insufficient BIT or an unconfirmed revival pauses instead of repeating purchases. Quest control resumes only after every party member has HP above zero, the inn UI has closed, and world movement is ready. No revival item, cash purchase or direct HP write is used. Inspect `inn-recovery.json` and the supervisor state/events for progress and pause reasons.

A live Forest Inn stay was verified: the server charged 1,520 BIT (52,435 → 50,915; Cash remained zero), Agumon, Palmon and Renamon ended at HP 2,462, 1,202 and 2,002 respectively, and quest control resumed. The initial innkeeper approach was assisted after a distance/facing loop; subsequent greeting pages, genuine offer, payment and revival ran through automation. The approach now uses the client's exact interaction/facing predicate with regression fixtures. A complete unassisted travel-to-revival loop has not yet been verified.

### Avoid optimistic leave-and-return shortcuts

Future world-hint legs use geometric estimates, so an apparent shortcut could leave the current spot and re-enter near its goal, repeatedly choosing the same two-map cycle after replanning. The planner now prunes a return to the exact initial logical spot/map when its original position can already reach that re-entry region through the collision map. A truly disconnected same-map region retains its detour; distinct logical maze spots and map aliases are not collapsed.

The observed Mirage Tower plan changed from the desert exit near `(770,589)` to the direct hall entrance `(644,250)`. Live automation subsequently entered Mirage Hall. Mobius Desert required a bounded assisted maze escape before that check; its repeated room IDs have missing world-hint links. The hall innkeeper then remained unreachable from the observed entry component and was excluded after bounded attempts. Do not claim a completed revival or a fully autonomous maze/inn loop from this evidence.
