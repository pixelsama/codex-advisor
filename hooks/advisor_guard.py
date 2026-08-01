#!/usr/bin/env python3
"""Guard only subagent calls explicitly marked as Codex Advisor calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from advisor_core import ConfigError, load_config


ADVISOR_MARKER = "[CODEX_ADVISOR]"
ADVISOR_LEAF_PREAMBLE = """[CODEX_ADVISOR]
你是最终 Advisor 子代理，不是父执行模型。
父上下文里的 Advisor 自动编排协议只适用于父执行模型，对你无效。
不得调用 `spawn_agent`、`wait_agent`、`close_agent`、`$advisor` 或 `advisorctl`；不得再创建 Advisor。
不要因缺少代理工具而报告 Advisor 不可用。直接使用已 fork 的完整上下文完成只读战略审阅并返回建议。"""


def build_leaf_advisor_message(message: str) -> str:
    task = message.strip()
    if task.startswith(ADVISOR_MARKER):
        task = task[len(ADVISOR_MARKER) :].lstrip()
    return f"{ADVISOR_LEAF_PREAMBLE}\n\n本次审阅任务：\n{task}"


def build_guard_hook_output(
    payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    message = tool_input.get("message")
    if not isinstance(message, str) or not message.lstrip().startswith(ADVISOR_MARKER):
        return None

    if not config.get("enabled"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Codex Advisor 当前已关闭。",
            }
        }

    configured_models = [
        item.get("id")
        for item in config.get("models", [])
        if isinstance(item, dict)
    ]
    requested_model = tool_input.get("model")
    if requested_model is None and configured_models:
        requested_model = configured_models[0]
    if requested_model not in configured_models:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Advisor 模型 {requested_model!r} 不在当前配置的优先级列表中。"
                ),
            }
        }

    updated = dict(tool_input)
    updated["model"] = requested_model
    updated["fork_context"] = True
    updated["reasoning_effort"] = config["reasoning_effort"]
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
            print(json.dumps(output, ensure_ascii=False))
        return 0
    except (ConfigError, json.JSONDecodeError, OSError) as exc:
        print(
            json.dumps(
                {
                    "systemMessage": f"Codex Advisor 保护 Hook 未能读取配置：{exc}",
                },
                ensure_ascii=False,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
