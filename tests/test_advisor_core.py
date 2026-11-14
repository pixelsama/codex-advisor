import json
import os
import tempfile
import unittest
from pathlib import Path


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
    def test_discovers_selected_catalog_with_reasoning_and_no_provider_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            (home / "models_cache.json").write_text(
                json.dumps({"models": [{"slug": "native-model"}]}), encoding="utf-8"
            )
            (home / "cc-switch-model-catalog.json").write_text(
                json.dumps(
                    {
                        "models": [
                            {"slug": "hidden", "visibility": "hide"},
                            {
                                "slug": "ccs-provider/third-party",
                                "visibility": "list",
                                "supported_reasoning_levels": [
                                    {"effort": "low"}, {"effort": "max"}, {"effort": "unsupported"}
                                ],
                                "default_reasoning_level": "max",
                                "api_key": "fixture-secret",
                            },
                        ]
                    }
                ),
                encoding="utf-8-sig",
            )

            official = discover_subagent_models(codex_home=home)
            ccs = discover_subagent_models(source="cc-switch", codex_home=home)
            manual = discover_subagent_models(source="manual", codex_home=home)

        self.assertEqual(official["models"], ["native-model"])
        self.assertEqual(ccs["models"], ["ccs-provider/third-party"])
        self.assertEqual(
            ccs["modelDetails"]["ccs-provider/third-party"],
            {"efforts": ["low", "max"], "defaultEffort": "max"},
        )
        self.assertTrue(ccs["updatedAt"])
        self.assertNotIn("fixture-secret", json.dumps(ccs))
        self.assertEqual(manual["models"], [])

    def test_rejects_credential_and_network_paths_before_opening_them(self):
        with self.assertRaises(ConfigError):
            discover_subagent_models(source="catalog", catalog_path=str(Path.cwd() / "auth.json"))
        with self.assertRaises(ConfigError):
            discover_subagent_models(source="catalog", catalog_path="//example.test/share/models.json")

    def test_uses_custom_codex_catalog_without_falling_back_to_another_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            (home / "models_cache.json").write_text(
                json.dumps({"models": [{"slug": "native-model"}]}), encoding="utf-8"
            )
            catalog = home / "custom-catalog.json"
            missing = discover_subagent_models(source="catalog", catalog_path=str(catalog), codex_home=home)
            self.assertEqual(missing["models"], [])
            self.assertIn("error", missing)
            catalog.write_text(json.dumps({"models": [{"slug": "custom-model"}]}), encoding="utf-8")
            result = discover_subagent_models(source="catalog", catalog_path=str(catalog), codex_home=home)
            self.assertEqual(result["models"], ["custom-model"])
            self.assertEqual(result["path"], str(catalog))


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
            self.assertEqual(loaded["agent_protocol"], "auto")
            self.assertEqual(loaded["model_source"], "codex")
            self.assertEqual(loaded["reasoning_effort"], "high")
            self.assertEqual(loaded["models"], proposed["models"])
            self.assertEqual(
                [item["id"] for item in loaded["models"]],
                ["codex02/gpt-5.6-sol", "gpt-5.6-sol"],
            )
            if os.name != "nt":
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
        self.assertIn('fork_turns="none"', protocol)
        self.assertNotIn('fork_context=true', protocol)
        self.assertIn("[CODEX_ADVISOR]", protocol)
        self.assertIn("检查迁移风险", protocol)

    def test_explicit_protocol_uses_matching_parameters_and_lifecycle(self):
        config = {
            "version": 1,
            "enabled": True,
            "mode": "auto",
            "reasoning_effort": "high",
            "on_exhausted": "continue",
            "models": [{"id": "gpt-5.6-sol", "retries": 1}],
        }

        for interface in ("v1", "v2"):
            with self.subTest(interface=interface):
                config["agent_protocol"] = interface
                protocol = build_advisor_protocol(config)
                self.assertIn("[CODEX_ADVISOR]", protocol)
                self.assertIn("主动提供本次问题", protocol)
                self.assertEqual('fork_turns="none"' in protocol, interface == "v2")
                self.assertEqual("`close_agent`" in protocol, interface == "v1")
                self.assertNotIn("fork_context=true", protocol)

    def test_disabled_config_cannot_build_an_advisor_protocol(self):
        config = default_config(["gpt-5.6-sol"])

        with self.assertRaises(ConfigError):
            build_advisor_protocol(config)


if __name__ == "__main__":
    unittest.main()
