import os
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
os.sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from advisor_core import load_config  # noqa: E402
from advisorctl import set_enabled, status_payload  # noqa: E402


class AdvisorCliTests(unittest.TestCase):
    def test_enabling_first_time_uses_discovered_preferred_models(self):
        discovery = {
            "models": [
                "gpt-5.6-luna",
                "gpt-5.6-sol",
                "codex02/gpt-5.6-sol",
            ],
            "source": "test",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            saved = set_enabled(
                True,
                state_dir=state_dir,
                discover=lambda **_: discovery,
            )

            self.assertTrue(saved["enabled"])
            self.assertEqual(
                [item["id"] for item in saved["models"]],
                ["gpt-5.6-sol", "codex02/gpt-5.6-sol"],
            )
            self.assertEqual(
                load_config(state_dir=state_dir, available_models=[]),
                saved,
            )

    def test_status_reports_live_model_source_and_saved_config(self):
        discovery = {
            "models": ["gpt-5.6-sol"],
            "source": "test-source",
            "path": "/test/config.json",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            set_enabled(
                True,
                state_dir=state_dir,
                discover=lambda **_: discovery,
            )

            payload = status_payload(
                state_dir=state_dir,
                discover=lambda **_: discovery,
            )

        self.assertTrue(payload["config"]["enabled"])
        self.assertEqual(payload["availableModels"], ["gpt-5.6-sol"])
        self.assertEqual(payload["modelSource"], "test-source")


if __name__ == "__main__":
    unittest.main()
