# Consumable and BIT shop research

Inspected original inputs, version 0.1.95:

* `app/client.jar`: SHA256 `7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe`, 727 ZIP members.
* `DW3-Online.apk`: SHA256 `e1865b79e6af7d6fde18568221d15edddaf419a6d137e0f77ec01e1eca685baa`, 119 ZIP members, Android manifest and `classes.dex` present.

Evidence is original bytecode decompiled with existing CFR 0.152, focused
`javap`/enum inspection, and offline resource reads through the unmodified
client asset reader. No login, game input, purchase, asset-key extraction,
or restart was performed for this investigation. Temporary evidence is in
`/tmp/dw3-item-analysis/`, `/tmp/dw3-item-data/`, and the existing
`/tmp/dw3-battle-analysis/` and `/tmp/dw3-inn-analysis/`.

## Definitions and authoritative effects

`F.f()` lazily reads `itemrules.json` into cached field `F.O`, class `bz`.
`bz.a` is the map from integer item ID to rule `bz$a`. The JSON parser reads
`kind`, `buy`, `sell`, optional `heal`, optional `healDs`, `power`, `lasts`,
`bound`, and a `shops` array of shop-name indices/item IDs.

| Rule accessor | Backing field | Meaning in original UI |
| --- | --- | --- |
| `c()` | `a` | Kind enum: ordinal 0 KEY, 1 USE, 2 WEAPON, 3 ARMOUR, 4 ACCESSORY. |
| `d()` | `b` | Definition's buy BIT price. |
| `e()` | `c` | Definition's sell BIT price. |
| `f()` | `d` | Fixed HP restoration outside battle. |
| `g()` | `e` | Accessory power: NONE, BITS, EXP by ordinal. |
| `h()` | `f` | Fixed DS restoration outside battle. |
| `a()` | — | Pure predicate: HP restoration or DS restoration is positive. |

`W.a(...)` explicitly describes these rules as recovery **outside battle**.
`G.a(rule,member,count)` calculates the ceiling of the HP/DS deficit divided
by each fixed restoration value, capped by inventory quantity. There is no
percentage unit in these outside-battle heal fields.

The standalone base asset reader returned missing for `itemrules.json` and
root `items.json`. It could read English item names, descriptions, shop names
and shop-window text. Therefore this investigation does not establish the
current rule amounts, prices or complete stock table offline. Read already
loaded `F.O` in the monitored client; unknown rules must remain unknown.
Do not make telemetry invoke `F.f()` and introduce asset I/O on the render
thread. Opening the ordinary inventory lets its normal render load rules.

English resource labels identify these candidates; description amounts are
legacy/localized text and must not replace live rules:

| ID | English name | Description claim |
| --- | --- | --- |
| 43 | Power Charge | 500 HP. |
| 44 | Super Charge | 1,000 HP. |
| 45 | Ultra Charge | 5,000 HP. |
| 46 | Max Charge | Maximum HP. |
| 463 | Mind Charge | 1,000 DS. |
| 70 | Life Disk | Revives fallen allies; amount unspecified. |
| 71 | Life Plug | Half HP/MP; context/actual effect must come from live rules. |

HP Chip (47) and MP Chip (48) permanently raise maxima; they are not ordinary
HP/DS refill candidates. Revive Disk (67) is described as curing paralysis,
not reviving a fainted Digimon. Never classify items by name substring alone.

Battle item effects are a separate server description: `g.by` maps item IDs
to `bI$m`; `g.bz` is battle inventory. `m.a` is item ID, `b` HP flat, `c` HP
percent, `d` DS percent, `e` cured statuses, `f` revival capability/value,
`g` DS flat. The original eligibility predicate permits HP-zero targets only
when `m.f()>0`. Its label does not establish the **unit** of `m.f`, so expose
revival availability or a neutral raw value, not an invented percentage.
Actor/skill/target integration belongs to the separate battle controller.

## Inventory and normal use

`aj.bv` is `List<bI$aG>`, replaced on server `bI$aN`: record `a` item ID,
`b` quantity. `aj.bu.d` is the entire party; member `bI$bm.a` is Digimon ID,
`e` HP, `f` DS, and `g` stats (`bw.a` max HP, `bw.b` max DS).

`aj.by` is the normal `G` menu:

| Field | Meaning |
| --- | --- |
| `t` | -1 closed, 0 party, 1 inventory, 2 map. |
| `u` | Selected filtered/timed inventory grid index. |
| `v` | Item being used in the party target picker; zero if absent. |
| `y` | Selected party target index. |
| `k`, `j` | Search active and search buffer. |
| static `l`, `m` | Category filter and sorted display. |
| `w`, `aj`, `z`, `K`, `A`, `S`, `ac` | Other nested UI states; do not send unrelated confirm input. |

Private `G.a(List)` only filters/sorts; overloaded `a(List,List<Long>)`
expands timed rows. They read cached definitions, so only inspect them when
the rules cache exists. The normal grid has ten columns and 60 cells/page.
Arrows select an item; Space opens its target picker; up/down select a party
slot; Space performs normal use. The original branch produces
`bI.cv(itemID,partySlot)`. Automation must drive the normal UI, not construct
that packet. Normal outside-battle healing requires **HP > 0** and a matching
HP/DS deficit; it cannot substitute for the inn's fainted-party recovery.

I opens/switches inventory; I toggles its main page closed. X cancels the
target picker. X does **not** close the inventory main page: that page uses
I or Escape. Search, delete, context and other nested UI should pause plans.

## BIT shop offers and normal purchase

`aj.bA` is shop UI `ax`, opened on server `bI$cd`: `a` shop-name index,
`b` ordered list of `bI$bB` (`a` item ID, `b` unit BIT price). This server
offer is authoritative for purchase price and availability.

| `ax` field | Meaning |
| --- | --- |
| `c` | Current server offer. |
| `f` | false buy, true sell. |
| `g`, `h` | Selected row and scroll top. |
| `i` | Selected quantity, initially one. |
| `j`, `m` | Submission pending and shop closed. |
| `n`, `o`, `p`, `q` | Confirmation item, sell flag, quantity and seconds since arming. |

Up/down select stock; left/right change quantity. Normal Space purchases
the selected offer. Quantity is limited by owned count + purchase <= 999
and available BIT. The normal handler sends `bI.ce(!f,itemID,quantity)`;
server `bI$cf.a` reports success, calling `ax.a(boolean)` and resetting the
quantity to one. X/Escape closes through the original close handler.
Never infer purchase completion merely from a key press: require inventory
increase and the expected wallet debit, or an explicit failure/wait state.

Buying at least ten items or paying at least 10,000 BIT arms an additional
confirmation. A second identical confirmation within three seconds submits;
the first Space alone is not a purchase. Selling always uses this extra
confirmation and is outside the requested buying workflow. The maintained
planner restricts purchases to at most five healing items and never sells.

## Merchant location evidence

Original `aL.k` world-map legend verifies POI 0 = item shop, 1 = card shop,
2 = inn. Some general item-shop markers can represent an armory or another
stock source; the marker does not prove healing stock.

Bundled logical NPC 22, sprite `p038wiza`, is Wizardmon with explicit item-shop
greetings on maps `s245`, `s246`, `s250`, `s251`, `s425`, `s426`, `s500`,
`s501`, `s660`, `s661`, `s760`, `s761`, `s931`, `s932`, `s957`. Runtime
`bI.bg.g` is an interaction identifier, not bundled logical NPC 22. Match
map/sprite and catalog greeting, then require an actual shop offer.

World POI/door hints include Asuka shop doors from `s200` at `(468,465)` or
`(564,417)` to `s245`; side approaches from `s250` at `(550,236)` or
`(310,420)`; and `s420` `(472,419)` to `s425`. Amaterasu has corresponding
map variants in the same world-map entries. Outdoor shop-map POI 0 entries
occur on `s250/s251/s932`, `s500/s501`, `s660/s661`, and `s760/s761`.
Respect each `spots.at` alias offset. These hints cannot prove current
server unlocks or assign exact merchant identity to each POI; use fresh
NPC coordinates and the original pure `bF.a(...)` interaction/facing test.

## Implemented adapter seam and verification

`SuppliesControl.snapshot(current)` reads cached rules, inventory, full-party
HP/DS, wallet and original menu/shop state. It returns `state_token`,
`inventory_open`, `inventory`, `party`, `wallet`, `menu`, and `shop` with
an offer token. Incomplete data remains explicitly incomplete. It neither
loads missing assets nor mutates gameplay/UI state.

`planInspect`, `planUse`, `planBuy`, and `planClose` return **one normal key**
or null plus a reason. They do not inject input or send packets. Root control
must verify expected PID/map and `state_token` immediately before executing
the key on the render thread, repoll afterward, and stop on modal changes.
`submit` is true only on final use/purchase confirmation; opening a target
picker or arming a large-purchase confirmation is false. A JVM fixture
checks effects, DS, eligibility, stale offer rejection, budget/quantity
guards, UI plans, token changes, missing fields and submission semantics.
No live consumable use or shop purchase has yet been verified by this work.
