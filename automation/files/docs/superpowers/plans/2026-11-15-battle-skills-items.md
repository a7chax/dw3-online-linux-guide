# Battle Skills and Recovery Items Implementation Plan

> For agentic workers: apply the existing execution and test-first workflow task by task. The user approved continuing with tactical skills and normal HP/DS consumable purchases.

**Goal:** Make `uv run --locked automation.py` choose useful affordable skills and maintain HP/DS supplies through normal client actions.

**Architecture:** A deterministic Python planner consumes complete native snapshots and produces one guarded menu action. Native adapters inspect original loaded fields and call the original UI handlers; they do not invent damage results or edit HP/DS/inventory/currency. Existing movement, dialogue, inn recovery, session leases and Codex repair remain in force.

**Tech stack:** Python via locked uv, Java reflection adapter, isolated unittest fixtures and the inspected original client.

## Constraints

- Keep `.env`, original binaries/assets and raw game logs private.
- No desktop keyboard injection or focus requirement for capable native bridge.
- Missing/changed actor, menu, stock, target, DS, price, wallet or session rejects input.
- Use owned items first. Restock normal BIT only; retain a reserve and cap each purchase run.
- Preserve inn recovery for fainted party members where consumables cannot revive.
- Label power/cost ranking as a heuristic unless an authoritative damage formula is found.
- No interactive Codex UI; exception repair continues through bounded `codex exec` with stdin prompt.

## Task 1: establish original interfaces

- [x] Record actor/menu/skill/cost/target mappings and ordinary battle selection handlers in `docs/battle-research.md`.
- [x] Record inventory/effect/shop/currency/purchase handlers and merchant hints in `docs/item-shop-research.md`.
- [x] Distinguish pure getters from submission actions and server-confirmed state.

## Task 2: tactical planner and bridge

- [x] Add failing fixtures for stronger affordable skills, insufficient DS, disabled options, urgent healing, result screens, unknown telemetry, repeated submission and changed actor/menu guards.
- [x] Add a focused native battle adapter with read-only snapshots and normal menu selection under expected-state checks.
- [x] Add Python battle ranking with explicit reason, estimated score and DS cost in the session decision file.
- [x] Integrate into persistent supervisor; keep normal result acknowledgement and battle waits.

## Task 3: supplies

- [x] Add failing inventory and purchase fixtures for effect/deficit matching, target validity, missing rules, stock, quantity, stale price/wallet, affordability and duplicate confirmation.
- [x] Add read-only inventory/shop snapshots and guarded original UI actions.
- [x] Use permitted HP/DS supplies when useful; route to verified merchants for bounded BIT restocking when needed.
- [x] Confirm inventory/currency changes before treating purchases or use as successful.

## Task 4: verify and publish

- [x] Run focused and complete locked tests, installer tests and skill validation.
- [x] Build/restart once to load native additions, reuse private login, verify live skill selection and item behavior separately.
- [x] Resume one background-capable controller.
- [x] Update DW3 skill, user guide, reviewed source payload and manifest; audit secrets and push.

Validation: 315 full installed-game tests, 43 installed-source tactical/supplies smoke tests and nine installer checks passed. Live inventory initialization and two different battle skills, result acknowledgement and subsequent map transfer were verified. No live purchase or item-effect check was required by the observed resources; those confirmations have fixture coverage.
