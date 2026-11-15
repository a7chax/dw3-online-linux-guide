# Native battle research and adapter contract

Inspected the shipped client without game input, attachment, login, restart, or changes to the engine. The running Linux client uses `app/client.jar`; Android-class equivalence was **not** established.

## Provenance and limits

- Desktop JAR SHA-256: `7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe`.
- APK SHA-256: `e1865b79e6af7d6fde18568221d15edddaf419a6d137e0f77ec01e1eca685baa`.
- REA APK inspection Evidence: `ev_5ea82dd7f647e6561df91bb3c8e55bd385b0d8bdef0fe1dff79db3a3b156a325`; underlying inventory Evidence: `ev_63392eb01a5b56c390d3d18864f68829bc5c919b5b68c019cd457def33c51124`. These establish artifact inventory/provenance, **not battle semantics**.
- REA `inspect_android_package` reported unavailable JADX configuration (`REA_JADX_MCP_JAR`); nothing was installed. REA JAR inventory rejected the original archive's case-distinct `k$A.class` / `k$a.class` names. The original archive was not altered.
- Semantic findings below derive from existing CFR 0.152 and `javap -p -c`, principally `/tmp/dw3-battle-analysis/g.java`, nested records, `/tmp/dw3-state-analysis/aj.java`, and `/tmp/dw3-party-analysis/bJ.java`. Decoding the original `aE.a` string literals verified JSON keys `name`, `ds`, `sequence`, `range`, `icon`. Temporary analyses are not distributable game assets.

## Pure state to read

`aj.ba` is the active `g` battle object; `aj.bn` is the battle transition. `aj.a(bI)` forwards server `bI.o` action/turn records to `g.a(List<bu>,List<Integer>)`, and result `bI.k` to `g.a(bI.k)`.

| Original field | Verified meaning |
| --- | --- |
| `g.bs` / `g.br` | Command menu open / waiting for server reply |
| `g.bc`, `g.M` | Current battle animation/event / queued events |
| `g.aY` | Intro time remaining; normal menu opens after it finishes |
| `g.bC`, `g.bD`, `g.bK` | Result packet, result overlay visible, result acknowledgement submitted |
| `g.bB` | Additional original menu-opening blocker; preserve it |
| `g.bt`, `g.bu`, `g.bw`, `g.bx` | Switch submenu, digivolve submenu, item submenu, selected item ID |
| `g.N`, `g.bA` | Current menu row objects / selected row index |
| `g.ay`, `g.K` | Server turn order / controllable group flags |
| `g.H`, `g.I` | Lists of members/forms per group / active index per group |
| `g.aC`, `g.aB` | Selected enemy group / multiple target selection permitted |
| `g.by`, `g.bz` | Server battle item definitions / inventory quantities |

The current actor follows pure `g.j()`: first `ay` group when controllable, otherwise group 0. Its active member is `H[group][I[group]]`. Allies occupy groups 0/2/3; the original enemy target array is 1/4/5. Do not treat every entry in `H[group]` as a separately active fighter.

`g$i` member fields: `b` current form ID, `c` base ID, `d` level, `e` maximum HP, `f` maximum DS, `i` current HP, `j` current DS, `k` status enum set. `a` is species/display metadata `g$e`; its `a` is the name and `d` is a skill list. All these reads are passive; do not substitute battle animation/reveal methods for predicates.

### Skills: cost is known; power is not

`g$h` is `(a name, b ds, c sequence, d range, e icon)`. The `sequence` selects animation, `range` is used in animation approach geometry, and `icon` draws the action icon. None is a verified power, damage, accuracy, elemental modifier, or speed stat.

Original `g.w()` creates one `bv$f(skillIndex)` row per skill, enabled when actor DS covers its `b` cost and status set does not contain original constant `bx.e`. That constant's user-facing status name was not verified. No client-side damage formula or complete attack/defense statistics were established. Tactical effectiveness must be labeled estimated/empirical, e.g. observed enemy HP loss after a submitted skill and a subsequent ready menu; cost alone does not establish strength.

### Battle consumables

`bI$m` supplies `(a itemID, b HP-flat, c HP-percent, d DS-percent, e cured statuses, f revival value, g DS-flat)`. `f>0` permits a fainted target, but its units are **unknown**; do not call it a percentage. `bI$aG` supplies `(a itemID,b quantity)`.

Original pure `g.a(bI$m,g$i)` eligibility: a target with HP 0 requires positive revival value; a living target must benefit from HP recovery, DS recovery, or a matching status cure. Item-target rows use `bv$e(itemID, memberIndex)` in the current actor's group. Preserve original row enabled flags, including revive restrictions; an enemy group is not the party member index.

World item rules and purchases are covered separately in `item-shop-research.md`; legacy English descriptions are not authoritative runtime quantities.

## Normal actions: deliberately mutating

| Original method | Normal UI action |
| --- | --- |
| `g.a(int delta)` | Cycle selected menu row, wrapping `N` |
| `g.a(int delta,boolean target)` | With `target=true`, cycle enemy only when menu open and `g.l().size()>1`; otherwise cycles menu rows |
| `g.b()` | Confirm current enabled row: open its submenu or submit the original command |
| `g.d()` | Original submenu Back; forced switch after actor fainting may not support Back |

`g.b()` uses original `bI.i(rowCommand,g.k())` submission and then sets menu closed / server-wait flags. `g.k()` returns a live selected enemy, falling back to the first living enemy. `g.l()` is the pure selectable-target list; target cycling must not be requested when the list has fewer than two entries, since `g.a(delta,true)` would instead move the command selection.

Command classes: `bv$a` attack; `bv$f(index)` skill; `bv$d(index)` switch member; `bv$b(formID)` digivolve; `bv$c` escape; `bv$e(itemID,memberIndex)` battle item. Null command rows open submenus using `g$f.h`: 1 switch, 2 digivolve, 3 item list, 4 target selection for item ID `g$f.i`.

The normal world input path maps arrows/WASD into `aj.a(delta,target)`, which delegates to `g`; Space/E/Z call `aj.p()` then `g.b()`, and X/backspace call `aj.i()` then `g.d()`. The adapter uses these same menu methods; it never writes HP/DS, fabricates skill objects, emits raw packets, changes VIP/auto flags, or changes the game engine.

## `BattleControl` API

`BattleControl.snapshot(aj)` returns an extension to existing battle/result telemetry:

- `telemetry_complete`, `command_ready`, opaque `battle_id`, opaque `menu_token`.
- `menu`: `main`, `items`, `item_target`, `switch`, or `digivolve`; `selected_option_index`, `selected_item_id`.
- `actor`: `group`, `active_index`, `controlled`, `form_id`, `base_id`, `hp`, `max_hp`, `ds`, `max_ds`, status ordinals.
- `fighters`: each occupied group's active fighter, same resources plus `group`, `active_index`, `controlled`.
- `party`: all members in the current actor's group, with `slot` and resources.
- `options`: `index`, `label`, original `enabled`, normalized `kind`; skills add `skill_index`, `ds_cost`, `sequence`, `range`, `icon`; item rows add `item_id`; item targets add `item_id`, `target_slot`, and `effect`; switch/digivolve targets add their member/form key. Unknown kinds remain `unknown`.
- `items` in every menu: `item_id`, `quantity`, `heal_hp`, `heal_hp_percent`, `heal_ds`, `heal_ds_percent`, `revive_available`, neutral `revival_value`, and `revive_percent:null`.
- `enemy_groups` as integer IDs, `target_group`, `turn_order`.

`command_ready` requires original menu open, no wait/block/result/ack, no pending result packet, no intro, no current/queued animation, no transition, and at least one row. Missing or invalid fields/resources fail closed.

`choose(aj,{expected_token,option_index,target_group?})` verifies fresh complete readiness and exact token, enabled option, skill affordability and optional legal enemy target; it calls original target/row cycling, rechecks actor/turn/menu/row identity, then invokes normal confirm exactly once. `back(aj,{expected_token})` verifies the same readiness and a supported submenu, then calls original Back. Both return `{before,after}` adapter snapshots and invalidate the old token, even when the normal method makes no immediate visible change.

The token binds a process-unique battle identity, newly built menu-row object generation, actor/resources/statuses, fighters, inventory/definitions, current menu, readiness and turn order. This distinguishes consecutive identical-looking turns by the new objects created in `g.w()`, not merely by actor ID or label hashes. A submenu confirmation is **not** proof of a submitted attack; learning logic must distinguish menu transitions from actual server-wait submission.

The parent `ControlBridge` must call these methods on the render thread, under fresh PID/map/world/story guards and the existing navigation lease. This class does not independently validate those outer guards. Successful fixture execution is not live tactical-combat proof.
