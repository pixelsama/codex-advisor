import json
import os
import subprocess
import sys
import tempfile
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
        self.assertIn('fork_turns="none"', context)
        self.assertIn("你就是最终 Advisor 子代理", context)
        self.assertLess(
            context.index("gpt-5.6-sol"),
            context.index("codex02/gpt-5.6-sol"),
        )
        self.assertIn("最多 2 次", context)


class HookTransportTests(unittest.TestCase):
    def _run_hook(self, script_name, payload):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            (state_dir / "config.json").write_text(
                json.dumps(enabled_config(), ensure_ascii=True), encoding="utf-8"
            )
            environment = os.environ.copy()
            environment["CODEX_ADVISOR_STATE_DIR"] = str(state_dir)
            return subprocess.run(
                [sys.executable, "-B", "-X", "utf8", str(PLUGIN_ROOT / "hooks" / script_name)],
                input=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
                capture_output=True,
                env=environment,
                check=False,
            )

    def test_context_hook_output_is_ascii_safe_json(self):
        completed = self._run_hook("advisor_context.py", {})
        self.assertEqual(completed.returncode, 0)
        output = json.loads(completed.stdout.decode("ascii"))
        self.assertIn("Advisor 角色分流", output["hookSpecificOutput"]["additionalContext"])

    def test_guard_hook_output_is_ascii_safe_json(self):
        completed = self._run_hook(
            "advisor_guard.py",
            {"tool_name": "spawn_agent", "tool_input": {"message": "[CODEX_ADVISOR] review", "model": "gpt-5.6-sol"}},
        )
        self.assertEqual(completed.returncode, 0)
        output = json.loads(completed.stdout.decode("ascii"))
        self.assertIn("你是最终 Advisor 子代理", output["hookSpecificOutput"]["updatedInput"]["message"])


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

    def test_v1_uses_the_configured_model_and_effort_without_forking(self):
        payload = {
            "tool_name": "spawn_agent",
            "tool_input": {
                "message": "[CODEX_ADVISOR] review this plan",
                "model": "gpt-5.6-sol",
                "fork_context": True,
            },
        }

        output = build_guard_hook_output(payload, enabled_config())
        updated = output["hookSpecificOutput"]["updatedInput"]

        self.assertNotIn("fork_context", updated)
        self.assertNotIn("fork_turns", updated)
        self.assertEqual(updated["reasoning_effort"], "high")
        self.assertEqual(updated["model"], "gpt-5.6-sol")
        self.assertTrue(updated["message"].startswith("[CODEX_ADVISOR]"))
        self.assertIn("你是最终 Advisor 子代理", updated["message"])
        self.assertIn("review this plan", updated["message"])

    def test_v1_honors_per_model_effort_and_preserves_the_full_advisor_message(self):
        config = enabled_config()
        config["models"][0]["reasoning_effort"] = "max"
        config["models"][1]["reasoning_effort"] = None
        protocol = build_context_hook_output({}, config)["hookSpecificOutput"]["additionalContext"]
        preamble = protocol.split("\n[CODEX_ADVISOR]\n", 1)[1].split("\n- ", 1)[0]
        message = f"[CODEX_ADVISOR]\n{preamble}\n\nCurrent constraint: use local catalog."
        for item in config["models"]:
            with self.subTest(model=item["id"]):
                payload = {
                    "tool_name": "spawn_agent",
                    "tool_input": {
                        "message": message,
                        "model": item["id"],
                        "fork_context": True,
                        "reasoning_effort": "high",
                    },
                }
                updated = build_guard_hook_output(payload, config)["hookSpecificOutput"]["updatedInput"]
                self.assertNotIn("fork_context", updated)
                self.assertEqual(updated["model"], item["id"])
                self.assertEqual(updated["message"], message)
                if item["reasoning_effort"] is None:
                    self.assertNotIn("reasoning_effort", updated)
                else:
                    self.assertEqual(updated["reasoning_effort"], "max")

    def test_v2_calls_are_left_to_the_parent_even_with_a_plaintext_marker(self):
        config = enabled_config()
        config["agent_protocol"] = "v1"
        for name, message in (
            ("collaborationspawn_agent", "gAAAA-example-encrypted-argument"),
            ("collaboration__spawn_agent", "[CODEX_ADVISOR] review"),
            ("spawn_agent", "[CODEX_ADVISOR] review"),
        ):
            with self.subTest(tool=name):
                payload = {
                    "tool_name": name,
                    "tool_input": {"task_name": "advisor", "fork_turns": "none", "message": message},
                }
                self.assertIsNone(build_guard_hook_output(payload, config))

    def test_explicit_v2_preference_rejects_v1_advisor_calls(self):
        config = enabled_config()
        config["agent_protocol"] = "v2"
        output = build_guard_hook_output({
            "tool_name": "spawn_agent",
            "tool_input": {"message": "[CODEX_ADVISOR] review"},
        }, config)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("当前调用使用 V1", output["permissionDecisionReason"])

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
