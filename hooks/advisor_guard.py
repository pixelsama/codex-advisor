#!/usr/bin/env python3
"""Guard only subagent calls explicitly marked as Codex Advisor calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from advisor_core import ConfigError, DEFAULT_FORK_TURNS, load_config


ADVISOR_MARKER = "[CODEX_ADVISOR]"
ADVISOR_CONTEXT_START = "[ADVISOR_CONTEXT]"
ADVISOR_CONTEXT_END = "[/ADVISOR_CONTEXT]"
ADVISOR_CONTEXT_FIELDS = (
    "goal",
    "verified_evidence",
    "already_read",
    "parent_assessment",
    "open_questions",
)
ADVISOR_LEAF_PREAMBLE = """[CODEX_ADVISOR]
你是最终 Advisor 子代理，不是父执行模型。
父上下文里的 Advisor 自动编排协议只适用于父执行模型，对你无效。
不得调用 `spawn_agent`、`wait_agent`、`close_agent`、`$advisor` 或 `advisorctl`；不得再创建 Advisor。
不要因缺少代理工具而报告 Advisor 不可用。直接使用有限 fork 得到的父上下文完成只读战略审阅并返回建议。

证据使用规则：
- `[ADVISOR_CONTEXT]` 是主代理从当前回合文件读取和命令输出中整理出的显式交接；把其中的 `verified_evidence` 作为首要证据。
- 先判断上下文包是否已经包含完成审阅所需的信息。证据足够时，不要重复读取 `already_read` 中的文件，直接据此判断。
- 只有缺失证据会实质改变结论时，才使用只读工具补读最少量的相关文件；不得先做宽泛仓库扫描。
- 返回时说明主要依据来自父上下文还是补读，并列出补读过的文件；没有补读时明确写“补读过的文件：无”。"""


def context_packet_error(message: str) -> str | None:
    start = message.find(ADVISOR_CONTEXT_START)
    end = message.find(ADVISOR_CONTEXT_END)
    if start < 0 or end < 0 or end <= start:
        return (
            "Advisor 调用必须包含完整的 [ADVISOR_CONTEXT]..."
            "[/ADVISOR_CONTEXT] 上下文包。"
        )
    packet = message[start + len(ADVISOR_CONTEXT_START) : end]
    missing = [
        field for field in ADVISOR_CONTEXT_FIELDS if f"{field}:" not in packet
    ]
    if missing:
        return "Advisor 上下文包缺少字段：" + ", ".join(missing)
    return None


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

    packet_error = context_packet_error(message)
    if packet_error is not None:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": packet_error,
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
    updated.pop("fork_context", None)
    updated["fork_turns"] = DEFAULT_FORK_TURNS
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
