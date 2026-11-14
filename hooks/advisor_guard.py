#!/usr/bin/env python3
"""Guard plaintext Advisor calls made through the classic subagent tool."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from advisor_core import (
    ADVISOR_LEAF_PREAMBLE,
    ADVISOR_MARKER,
    ConfigError,
    load_config,
    model_reasoning_effort,
)


def build_leaf_advisor_message(message: str) -> str:
    task = message.strip()
    if task.startswith(ADVISOR_LEAF_PREAMBLE):
        return task
    if task.startswith(ADVISOR_MARKER):
        task = task[len(ADVISOR_MARKER) :].lstrip()
    return f"{ADVISOR_LEAF_PREAMBLE}\n\n本次审阅任务：\n{task}"


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def build_guard_hook_output(
    payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    # V2 task messages may be encrypted and cannot be identified or rewritten here.
    if payload.get("tool_name") not in ("Agent", "spawn_agent") or "task_name" in tool_input or "fork_turns" in tool_input:
        return None
    message = tool_input.get("message")
    if not isinstance(message, str) or not message.lstrip().startswith(ADVISOR_MARKER):
        return None

    if not config.get("enabled"):
        return _deny("Codex Advisor 当前已关闭。")

    preference = config.get("agent_protocol", "auto")
    if preference not in ("auto", "v1"):
        return _deny("当前调用使用 V1，Advisor 设置要求 V2。请改为自动或使用匹配的 Codex 会话。")

    configured_models = {
        item["id"]: item
        for item in config.get("models", [])
    }
    requested_model = tool_input.get("model")
    if requested_model is None and configured_models:
        requested_model = next(iter(configured_models))
    if not isinstance(requested_model, str) or requested_model not in configured_models:
        return _deny("请指定 Advisor 优先级列表中的模型。")

    updated = dict(tool_input)
    updated["model"] = requested_model
    updated.pop("fork_context", None)
    effort = model_reasoning_effort(config, configured_models[requested_model])
    if effort is None:
        updated.pop("reasoning_effort", None)
    else:
        updated["reasoning_effort"] = effort
    updated["message"] = build_leaf_advisor_message(message)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated,
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        output = build_guard_hook_output(payload, load_config())
        if output is not None:
            print(json.dumps(output, ensure_ascii=True))
        return 0
    except (ConfigError, json.JSONDecodeError, OSError) as exc:
        print(
            json.dumps(
                {
                    "systemMessage": f"Codex Advisor 保护 Hook 未能读取配置：{exc}",
                },
                ensure_ascii=True,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
