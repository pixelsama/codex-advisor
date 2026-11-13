---
name: advisor
description: Configure, enable, disable, inspect, or explicitly invoke Codex Advisor from the parent/root agent. Use when the user mentions Advisor, wants a strategic second opinion from configured subagent models, asks to open the Advisor GUI, change model priority or retries, or toggle the global Advisor workflow. Never invoke the orchestration workflow when the current assigned task starts with [CODEX_ADVISOR]; that marker means this agent is already the final leaf Advisor and must answer directly.
---

# Codex Advisor

Codex Advisor uses the configured models as an ordered review chain. Settings live in `~/.codex/advisor/config.json`.

## Leaf Advisor role gate

Before routing any request, inspect the current assigned task message:

- If it begins with `[CODEX_ADVISOR]`, complete the read-only review using the supplied task, background, and relevant files. State what is missing if the context is insufficient. Do not run Advisor commands or delegate work.
- Otherwise, follow the routes below from the parent agent.

## Route the request

Always run `scripts/advisorctl.py` from the plugin that supplied this `SKILL.md`. Resolve `../../scripts/advisorctl.py` relative to the directory containing this file. Use its quoted absolute path, even if `codex-advisor` is on `PATH`, because that command may point to a different installation.

- Windows: `py -3 -X utf8 "<absolute-script-path>"`
- macOS/Linux: `python3 "<absolute-script-path>"`

Append the subcommand for the request:

- `$advisor`, `$advisor config`, `open`, `gui`, or settings: `open`.
- Enable or disable: `on` or `off`.
- Status or model discovery: `status` or `models`.
- `$advisor ask [focus]` or an explicit request for a review: `protocol --focus "<focus>"`, then follow the emitted protocol.

## Advisor invocation

When invoking an Advisor:

1. Follow the emitted model order, per-model reasoning effort, retry limits, and failure policy.
2. Use the `spawn_agent` interface exposed by the current session. In auto mode, use the tool schema to distinguish V2 (`fork_turns`) from V1 (`fork_context`). Report a mismatch with an explicit preference. V2 uses `fork_turns="none"`; V1 omits `fork_context` and uses its `close_agent` after the review.
3. Send the full Advisor role and context in `message` as shown in the emitted protocol. The parent supplies the model, reasoning effort, and history parameters on the initial call. V2 does not rely on the Guard to fill in any fields.
4. Keep the Advisor read-only. It reviews strategy, assumptions, risks, omissions, and next steps; the main agent remains responsible for execution.
5. Do not reinterpret a completed but disagreeable answer as a failure. Retry only tool-level or provider/model failures listed in the protocol.
6. Never alter ordinary subagent calls that do not carry the marker.

## Automatic mode

When the saved configuration is enabled and mode is `auto`, the `UserPromptSubmit` Hook injects the current protocol. Use Advisor selectively at consequential planning/review checkpoints, after repeated failures, or before a substantial final handoff. Skip it for trivial work.

When mode is `manual`, never start an Advisor unless the user explicitly requests `$advisor ask` or an equivalent consultation.
