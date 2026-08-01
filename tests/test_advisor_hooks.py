import os
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
os.sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
os.sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))

from advisor_context import build_context_hook_output  # noqa: E402
from advisor_guard import build_guard_hook_output  # noqa: E402


def enabled_config():
    return {
        "version": 1,
        "enabled": True,
        "mode": "auto",
        "reasoning_effort": "high",
        "on_exhausted": "continue",
        "models": [
            {"id": "gpt-5.6-sol", "retries": 1},
            {"id": "codex02/gpt-5.6-sol", "retries": 0},
        ],
    }


class ContextHookTests(unittest.TestCase):
    def test_disabled_advisor_injects_nothing(self):
        config = enabled_config()
        config["enabled"] = False

        self.assertIsNone(build_context_hook_output({}, config))

    def test_manual_mode_injects_nothing_automatically(self):
        config = enabled_config()
        config["mode"] = "manual"

        self.assertIsNone(build_context_hook_output({}, config))

    def test_auto_mode_injects_ordered_retry_protocol(self):
        output = build_context_hook_output({}, enabled_config())
        context = output["hookSpecificOutput"]["additionalContext"]

        self.assertIn("用户已手动开启 Codex Advisor", context)
        self.assertIn("Advisor 角色分流（最高优先级）", context)
        self.assertIn("你就是最终 Advisor 子代理", context)
        self.assertLess(
            context.index("gpt-5.6-sol"),
            context.index("codex02/gpt-5.6-sol"),
        )
        self.assertIn("最多 2 次", context)


class GuardHookTests(unittest.TestCase):
    def test_non_advisor_subagent_is_untouched(self):
        payload = {
            "tool_name": "spawn_agent",
            "tool_input": {
                "message": "ordinary delegated task",
                "model": "deepseek/deepseek-v4-flash",
            },
        }

        self.assertIsNone(build_guard_hook_output(payload, enabled_config()))

    def test_advisor_call_is_forced_to_fork_context_and_configured_effort(self):
        payload = {
            "tool_name": "spawn_agent",
            "tool_input": {
                "message": "[CODEX_ADVISOR] review this plan",
                "model": "gpt-5.6-sol",
                "fork_context": False,
            },
        }

        output = build_guard_hook_output(payload, enabled_config())
        updated = output["hookSpecificOutput"]["updatedInput"]

        self.assertTrue(updated["fork_context"])
        self.assertEqual(updated["reasoning_effort"], "high")
        self.assertEqual(updated["model"], "gpt-5.6-sol")
        self.assertTrue(updated["message"].startswith("[CODEX_ADVISOR]"))
        self.assertIn("你是最终 Advisor 子代理", updated["message"])
        self.assertIn("父上下文里的 Advisor 自动编排协议只适用于父执行模型", updated["message"])
        self.assertIn("不得调用 `spawn_agent`", updated["message"])
        self.assertIn("review this plan", updated["message"])

    def test_advisor_call_with_unconfigured_model_is_denied(self):
        payload = {
            "tool_name": "spawn_agent",
            "tool_input": {
                "message": "[CODEX_ADVISOR] review this plan",
                "model": "deepseek/deepseek-v4-flash",
            },
        }

        output = build_guard_hook_output(payload, enabled_config())

        self.assertEqual(
            output["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )


if __name__ == "__main__":
    unittest.main()
