---
name: advisor
description: Configure, enable, disable, inspect, or explicitly invoke Codex Advisor from the parent/root agent. Use when the user mentions Advisor, wants a strategic second opinion from configured subagent models, asks to open the Advisor GUI, change model priority or retries, or toggle the global Advisor workflow. Never invoke the orchestration workflow when the current assigned task starts with [CODEX_ADVISOR]; that marker means this agent is already the final leaf Advisor and must answer directly.
---

# Codex Advisor

Codex Advisor uses the user's current subagent model list as an ordered strategic-review chain. Configuration lives in `~/.codex/advisor/config.json`; the `codex-advisor` command opens the local settings page and manages that state.

## Leaf Advisor role gate

Before routing any request, inspect the current assigned task message:

- If it begins with `[CODEX_ADVISOR]`, this agent is already the final leaf Advisor. The inherited automatic Advisor protocol belongs only to the parent executor.
- In that leaf role, do not run `codex-advisor`, `$advisor`, `spawn_agent`, `wait_agent`, or `close_agent`; do not create another Advisor and do not report Advisor unavailable because those tools are absent.
- Use the required `[ADVISOR_CONTEXT]` packet as the primary evidence for the requested read-only strategic review; the bounded fork provides recent intent but does not carry the parent agent's current-turn tool output. If the packet contains the relevant findings, answer without re-reading `already_read`. Read only the smallest missing evidence that could materially change the conclusion.
- Only a parent/root agent whose current task does not begin with the marker may continue to the routing and orchestration sections below.

## Route the request

- For `$advisor`, `$advisor config`, `open`, `gui`, or settings requests: run `codex-advisor open`.
- For enable/disable requests: run `codex-advisor on` or `codex-advisor off`.
- For status or model discovery requests: run `codex-advisor status` or `codex-advisor models`.
- For `$advisor ask [focus]` or an explicit request for an Advisor review: run `codex-advisor protocol --focus "<focus>"`, then follow the emitted protocol exactly.

If `codex-advisor` is not on `PATH`, resolve this `SKILL.md` to its plugin root and run `python3 <plugin-root>/scripts/advisorctl.py` with the same arguments.

## Advisor invocation

When invoking an Advisor:

1. Treat the CLI-emitted model order and retry counts as authoritative.
2. Use `spawn_agent` with the protocol's bounded `fork_turns`, selected model, and reasoning effort. Do not restore the legacy `fork_context` field.
3. Prefix the Advisor subagent prompt with `[CODEX_ADVISOR]`, then include a complete `[ADVISOR_CONTEXT]` packet with `goal`, `verified_evidence`, `already_read`, `parent_assessment`, and `open_questions`. The guard denies incomplete Advisor handoffs.
4. Keep the Advisor read-only and evidence-on-demand. It reviews strategy, assumptions, risks, omissions, and next steps; the main agent remains responsible for execution.
5. A `wait_agent` polling timeout or empty snapshot is non-terminal. Continue waiting on the same agent ID; never close or replace a running Advisor because a poll returned no result.
6. Capture a completed Advisor answer in the parent context before cleanup. Do not reinterpret a completed but disagreeable answer as a failure.
7. On a resumed parent turn, continue any existing Advisor consultation before creating a replacement.
8. Never alter ordinary subagent calls that do not carry the marker.

## Automatic mode

When the saved configuration is enabled and mode is `auto`, the `UserPromptSubmit` Hook injects the current protocol. Use Advisor selectively at consequential planning/review checkpoints, after repeated failures, or before a substantial final handoff. Skip it for trivial work.

When mode is `manual`, never start an Advisor unless the user explicitly requests `$advisor ask` or an equivalent consultation.
