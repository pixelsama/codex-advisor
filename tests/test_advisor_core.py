import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
os.sys.path.insert(0, str(SCRIPTS_DIR))

from advisor_core import (  # noqa: E402
    ConfigError,
    build_advisor_protocol,
    default_config,
    discover_subagent_models,
    load_config,
    save_config,
    validate_config,
)


class ModelDiscoveryTests(unittest.TestCase):
    def test_reads_opencodex_subagent_models_in_exact_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "subagentModels": [
                            "gpt-5.6-luna",
                            "gpt-5.6-sol",
                            "codex02/gpt-5.6-sol",
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = discover_subagent_models(
                opencodex_config_path=config_path,
                codex_candidates=[],
            )

        self.assertEqual(
            result["models"],
            [
                "gpt-5.6-luna",
                "gpt-5.6-sol",
                "codex02/gpt-5.6-sol",
            ],
        )
        self.assertEqual(result["source"], "opencodex.subagentModels")

    def test_falls_back_to_codex_debug_models(self):
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps(
                {
                    "models": [
                        {"slug": "hidden", "visibility": "hide"},
                        {"slug": "gpt-5.6-sol", "visibility": "list"},
                        {"slug": "codex02/gpt-5.6-sol", "visibility": "list"},
                    ]
                }
            ),
            stderr="",
        )

        result = discover_subagent_models(
            opencodex_config_path=Path("/missing/config.json"),
            codex_candidates=["/fake/codex"],
            runner=mock.Mock(return_value=completed),
        )

        self.assertEqual(
            result["models"],
            ["gpt-5.6-sol", "codex02/gpt-5.6-sol"],
        )
        self.assertEqual(result["source"], "codex debug models")


class ConfigTests(unittest.TestCase):
    def test_default_prefers_requested_sol_models_and_one_retry(self):
        config = default_config(
            [
                "gpt-5.6-luna",
                "gpt-5.6-sol",
                "codex02/gpt-5.6-sol",
            ]
        )

        self.assertFalse(config["enabled"])
        self.assertEqual(
            config["models"],
            [
                {"id": "gpt-5.6-sol", "retries": 1},
                {"id": "codex02/gpt-5.6-sol", "retries": 1},
            ],
        )

    def test_validates_order_retries_and_round_trips_atomically(self):
        proposed = {
            "version": 1,
            "enabled": True,
            "mode": "auto",
            "reasoning_effort": "high",
            "on_exhausted": "continue",
            "models": [
                {"id": "codex02/gpt-5.6-sol", "retries": 2},
                {"id": "gpt-5.6-sol", "retries": 0},
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            saved = save_config(proposed, state_dir=state_dir)
            loaded = load_config(state_dir=state_dir, available_models=[])

            self.assertEqual(loaded, saved)
            self.assertEqual(
                [item["id"] for item in loaded["models"]],
                ["codex02/gpt-5.6-sol", "gpt-5.6-sol"],
            )
            self.assertEqual(
                (state_dir / "config.json").stat().st_mode & 0o777,
                0o600,
            )

    def test_rejects_duplicate_models_and_excessive_retries(self):
        bad_config = default_config(["gpt-5.6-sol"])
        bad_config["models"] = [
            {"id": "gpt-5.6-sol", "retries": 1},
            {"id": "gpt-5.6-sol", "retries": 6},
        ]

        with self.assertRaises(ConfigError):
            validate_config(bad_config)


class ProtocolTests(unittest.TestCase):
    def test_protocol_preserves_priority_and_retry_semantics(self):
        config = {
            "version": 1,
            "enabled": True,
            "mode": "auto",
            "reasoning_effort": "high",
            "on_exhausted": "continue",
            "models": [
                {"id": "gpt-5.6-sol", "retries": 1},
                {"id": "codex02/gpt-5.6-sol", "retries": 2},
            ],
        }

        protocol = build_advisor_protocol(config, focus="检查迁移风险")

        self.assertLess(
            protocol.index("gpt-5.6-sol"),
            protocol.index("codex02/gpt-5.6-sol"),
        )
        self.assertIn("最多 2 次", protocol)
        self.assertIn("最多 3 次", protocol)
        self.assertIn("fork_context=true", protocol)
        self.assertIn("[CODEX_ADVISOR]", protocol)
        self.assertIn("检查迁移风险", protocol)

    def test_protocol_routes_a_forked_advisor_to_leaf_review(self):
        config = {
            "version": 1,
            "enabled": True,
            "mode": "auto",
            "reasoning_effort": "high",
            "on_exhausted": "continue",
            "models": [{"id": "gpt-5.6-sol", "retries": 1}],
        }

        protocol = build_advisor_protocol(config)

        role_gate = protocol.index("Advisor 角色分流（最高优先级）")
        model_chain = protocol.index("Advisor 模型链")
        self.assertLess(role_gate, model_chain)
        self.assertIn(
            "如果你当前收到的任务消息以 `[CODEX_ADVISOR]` 开头",
            protocol,
        )
        self.assertIn("你就是最终 Advisor 子代理", protocol)
        self.assertIn(
            "不要调用 `spawn_agent`、`wait_agent` 或 `close_agent`",
            protocol,
        )
        self.assertIn("直接完成只读战略审阅并返回建议", protocol)

    def test_disabled_config_cannot_build_an_advisor_protocol(self):
        config = default_config(["gpt-5.6-sol"])

        with self.assertRaises(ConfigError):
            build_advisor_protocol(config)


if __name__ == "__main__":
    unittest.main()
