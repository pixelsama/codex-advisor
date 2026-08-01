#!/usr/bin/env python3
"""Inject the enabled automatic Advisor protocol into each user turn."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from advisor_core import ConfigError, build_advisor_protocol, load_config


def build_context_hook_output(
    payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    del payload
    if not config.get("enabled") or config.get("mode") != "auto":
        return None
    context = build_advisor_protocol(config, automatic=True)
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        output = build_context_hook_output(payload, load_config())
        if output is not None:
            print(json.dumps(output, ensure_ascii=False))
        return 0
    except (ConfigError, json.JSONDecodeError, OSError) as exc:
        print(
            json.dumps(
                {
                    "systemMessage": f"Codex Advisor 配置未能加载：{exc}",
                },
                ensure_ascii=False,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
