# AI Setup: Claude Code and Codex

For the current ready source kit, begin with [automation/README.md](automation/README.md).
Its [files/](automation/files/) directory is authoritative for current code; the playbook's embedded Appendix A is the original baseline.
Install the kit into the user's game directory after the baseline port procedure and before current runtime verification.

From this repository, preview with `uv run --no-project automation/install.py --game-dir "/path/to/DW3 Online"`; add `--apply` to install the reviewed source files.
Then change to that game directory and follow the kit's `uv sync --locked`, native build and login instructions.

## 1. Purpose

Use this guide before the [AI replication playbook](AI-LINUX-PORT-PLAYBOOK-STE100.md).
It applies to Claude Code and Codex on the Linux computer that will build the port.

Claude Code and Codex are coding agents.
A skill is a set of instructions in a `SKILL.md` file.
An MCP server supplies tools that the agent can call.
REA supplies the analysis tools for this task.
Hopper supplies the native disassembly and decompilation capability used in this port.

A skill file alone does not install REA or an analysis engine.
A normal browser chat without local tool access cannot perform the complete procedure.

## 2. Skills to Use

| Skill | Source | Role in this task |
| --- | --- | --- |
| `reverse-engineer-anything` | [REA](https://github.com/morluto/rea) | Main task skill. Inspect the APK and JNI library through REA. |
| `dw3-linux-control` | [Included skill](automation/files/skills/dw3-linux-control/SKILL.md) | Operate the installed port, read quest/state files, and maintain the supported automation workflow. |
| `systematic-debugging` | [Superpowers](https://github.com/obra/superpowers) | Recommended. Reproduce failures and identify their causes before changes. |
| `verification-before-completion` | [Superpowers](https://github.com/obra/superpowers) | Recommended. Require actual build, process, and graphical evidence before success claims. |
| `test-driven-development` | [Superpowers](https://github.com/obra/superpowers) | Optional. Use it when you change the supplied adapter or launcher behavior. |
| `requesting-code-review` | [Superpowers](https://github.com/obra/superpowers) | Optional. Review the implementation before the final handoff. |

For port/version analysis, use `reverse-engineer-anything`.
For an already installed port, use `dw3-linux-control` from the installed `skills/dw3-linux-control/SKILL.md` and its references.
Routine state inspection and automation do not require a new REA analysis.
The other skills support the engineering process.
They are not dependencies of the completed game.

The playbook contains the complete implementation procedure.
An agent can follow that procedure without the optional skill packages.
It must still have the required analysis tools and build tools.
It must disclose an unavailable skill instead of claiming to use it.

## 3. Configure REA for the Selected Agent

Use the [REA installation instructions](https://github.com/morluto/rea/blob/main/docs/getting-started/installation.md) as the setup reference.
The commands below use REA 6.3.0 to match the implementation workflow.
A different release requires a check of its available commands and tool schemas.

These commands require Node.js and npm.
Run them in a terminal on the Linux computer.

### 3.1 Claude Code

1. Check the existing registration.

   ```bash
   npx -y rea-agents@6.3.0 doctor --client claude_code --json
   ```

2. If setup is required, preview its changes.

   ```bash
   npx -y rea-agents@6.3.0 setup --client claude_code --dry-run --json
   ```

3. Review the proposed paths and changes.
4. Apply the reviewed setup when you approve its changes.

   ```bash
   npx -y rea-agents@6.3.0 setup --client claude_code
   ```

5. Restart Claude Code after the configuration changes.

### 3.2 Codex

1. Check the existing registration.

   ```bash
   npx -y rea-agents@6.3.0 doctor --client codex --json
   ```

2. If setup is required, preview its changes.

   ```bash
   npx -y rea-agents@6.3.0 setup --client codex --dry-run --json
   ```

3. Review the proposed paths and changes.
4. Apply the reviewed setup when you approve its changes.

   ```bash
   npx -y rea-agents@6.3.0 setup --client codex
   ```

5. Restart Codex after the configuration changes.

### 3.3 Check Actual Availability

1. Confirm that `reverse-engineer-anything` appears in the selected agent's skill list.
2. Confirm that the agent can call the REA tools.
3. Confirm that native analysis can use Hopper.
4. Record the installed REA version and provider details.

The required operations include `open_binary`, `inspect_artifact`, and native function inspection.
Their exposed names can include an MCP namespace prefix.
The agent must use the schemas from its active tool list.

Configure the analysis engine separately if its capability is unavailable.
The original workflow used Hopper for the native library.
JADX was unavailable during that workflow.
Android SDK `aapt` supplied the manifest information instead.

## 4. Add the Supporting Skills

Follow the [Superpowers installation guide](https://github.com/obra/superpowers#installation) for your selected agent.
Install the package for Claude Code, Codex, or both, as required.
Confirm that the required skill names appear after installation.

A manual installation must retain the complete skill directory and its references.
The following paths describe the standard local skill locations.
Plugins can manage their own installation paths.

| Agent | Project scope | User scope |
| --- | --- | --- |
| Claude Code | `.claude/skills/<name>/SKILL.md` | `~/.claude/skills/<name>/SKILL.md` |
| Codex | `.agents/skills/<name>/SKILL.md` | `~/.agents/skills/<name>/SKILL.md` |

See the [Claude Code skills documentation](https://code.claude.com/docs/en/skills) for Claude Code discovery rules.
See the [official Codex skills documentation](https://developers.openai.com/codex/skills/) for Codex discovery rules.

Installing a workflow skill does not install Java, GCC, or Android SDK Build Tools.
Those tools remain separate prerequisites in the playbook.

The current source kit includes the complete `skills/dw3-linux-control/` directory.
After installing it in the game directory, retain its references and expose it to the chosen agent through the project skill location in the table above, or ask the agent to read its `SKILL.md` directly.
Do not copy a single instruction file without its references.
Use `uv sync --locked` in the installed game directory and `uv run --locked` for Python commands.

## 5. Give the Task to Claude Code or Codex

Use the following prompt with either agent.
Replace the example paths before use.

```text
Read AI-SETUP.md and AI-LINUX-PORT-PLAYBOOK-STE100.md.

Use the reverse-engineer-anything skill for artifact inspection through REA.
Use systematic-debugging and verification-before-completion when those skills are available.
Report the skills and REA tools that are actually available.
Do not claim to load a skill that is absent.

Original Windows package: /absolute/path/to/Windows-game-files
Original APK: /absolute/path/to/DW3-Online.apk
Writable output directory: /absolute/path/to/linux-port-workspace

Reproduce the native Linux Java port from the playbook.
Use Appendix A to understand the baseline, then install the current automation/ source kit before building or verifying the current version.
Follow automation/README.md for installation and use uv for all Python dependencies and commands.
Use the matching desktop client, game data, and APK library.
Build the native adapter, Java bridge, executable, and included Java runtime.
Include the multi-window bootstrap and its regression checks.

Use REA for the APK inventory and native library analysis.
Preserve the original files, native asset code, and certificate checks.
Do not use Wine, Proton, Waydroid, or an Android emulator for the final application.

Verify the build, native initialization, rendered login screen, and process libraries.
Let me enter account credentials directly for login and gameplay checks.
Separate your observed results from results that I report.
Give me the executable path, start command, evidence, and remaining limits.
```

## 6. Runtime and User Verification

The completed game and its normal Python automation run without AI calls.
REA is used to inspect or adapt game versions; it is not a runtime dependency.
The optional `--repair-with-codex` mode invokes an installed, authenticated Codex CLI only after repeated eligible controller failures.
Without that flag, repair remains manual. Normal automation does not use Claude Code or Codex for each movement.

The user reported successful account login and gameplay on the original port.
The agent independently verified native startup, asset loading, and the rendered login screen.
The Markdown source also passed an independent rebuild and native initialization check.
Three regression checks passed for profile isolation, profile reuse, and existing-client compatibility.
Two real clients displayed their login screens at the same time.
The user confirmed that multiple game windows work.
A new computer or game version still requires its own verification.
