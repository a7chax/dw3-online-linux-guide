# AI battle model draft

Status: proposal only. No new model, training process or dependency is implemented or enabled.

First finish and validate the deterministic combat fixes: prefer a useful free normal attack, compare observed damage with enemy HP, conserve DS, allow one effective emergency heal between offensive commands, and perform routine HP/DS recovery after battle.

## Proposed first experiment

Use a small contextual action-value learner behind those rules. A contextual bandit is the proposed first experiment; it would rank permitted attack/skill actions from their context and observed outcomes. This is a design choice, not a claim that a trained model already exists or would beat the corrected controller. [Vowpal Wabbit contextual-bandit documentation](https://vowpalwabbit.org/docs/vowpal_wabbit/python/latest/tutorials/python_Contextual_bandits_and_Vowpal_Wabbit.html) describes context/action features and logged feedback.

Inputs would include active fighter form/HP/DS, enemy form/HP, available commands and costs, observed hit/loss uncertainty, incoming-threat estimates, remaining opponents and recent item use. Only complete fresh snapshots could supply a decision.

The action mask would preserve original enabled flags, affordability, session/menu guards, normal-finisher preference, bounded emergency item use and purchase budgets. The learner would rank permitted actions; it could not override those checks or write game resources.

Reward is a proposed normalized combination of victory/progress and enemy HP loss, minus fighter loss, elapsed turns, DS consumption and item consumption. Reward weights require evaluation. Delayed outcomes and other fighters/status effects can confound a turn's HP delta, so the existing estimates are not exact causal damage labels. Logging would need selection probabilities, state/action IDs, outcome timing, censoring flags and model version, excluding credentials and chat.

## Evaluation before enablement

1. Keep the corrected rule controller as the baseline.
2. Collect private battle logs and run the candidate in shadow mode without sending its choices.
3. Compare held-out outcomes by enemy/form group: win/loss, turns, DS per victory, items per victory, and repeated-healing rate. Logged-policy bias must be considered; replay alone cannot prove unchosen actions would have succeeded.
4. Promote only after meaningful evidence, with an immediate fallback to the rule controller and bounded exploration.

## Full reinforcement learning later

A full episodic RL experiment would first need a validated battle environment with explicit observations, actions, rewards, episode termination and reproducible reset. The current online game is not a verified resettable simulator. A separate environment would follow an interface such as [Gymnasium reset/step](https://gymnasium.farama.org/introduction/create_custom_env/); its dynamics would need validation against actual battles before training results could be treated as game evidence. Selecting a deep RL algorithm comes after that environment and evaluation design.
