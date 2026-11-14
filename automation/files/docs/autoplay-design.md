# Persistent quest automation

The user authorized continuing game automation without a time limit, including normal Space input for dialogue and interactions. Implement a local process that stays running until stopped, rather than requiring another AI turn for every bounded movement.

Reuse the existing monitored client, credential configuration, control socket, movement planner, and input lease. A supervisor reads fresh status and the current quest before each action. It follows GPS routes, falls back to the collision atlas after a blocked segment, advances reported dialogue, and advances reported linear story scenes with normal Space. Missing routes receive a bounded GPS refresh and retry delay. Keep quest chapter/step and map changes as evidence of progress.

The process has no default deadline. It records its PID, current action, progress, pause reason, and events in the monitored session. A singleton lock prevents duplicate supervisors. Provide status and stop commands and a finite-cycle option for verification. Stop requests take effect between short actions.

Focus loss, stale state, loading, login screens, unsupported objectives, and choices put the supervisor into a waiting state. It must remain alive without repeatedly reclaiming focus or hammering blocked keys. No automatic hidden password prompt, purchases, or invented battle implementation. A waiting supervisor is not proof of quest advancement.

Add read-only story/GPS telemetry to the existing bridge when required. Inspect only known pure predicates and fields; do not call reveal/advance actions while polling. Rebuild and restart once to load that telemetry, then verify it in live status.

Verify policy decisions, focus/session guards, retry backoff, stop handling, and singleton ownership with fixtures. Verify actual movement and state transitions separately in the live game. Record the tested scope in the existing DW3 control skill and user instructions.
