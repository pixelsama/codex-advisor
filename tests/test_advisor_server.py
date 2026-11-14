import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
os.sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from advisor_server import AdvisorService, create_server  # noqa: E402


class AdvisorServerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name)
        self.discovery = {
            "models": ["gpt-5.6-sol", "codex02/gpt-5.6-sol"],
            "source": "test",
        }
        service = AdvisorService(
            state_dir=self.state_dir,
            discover=lambda **_: self.discovery,
        )
        self.server = create_server(
            host="127.0.0.1",
            port=0,
            service=service,
            assets_dir=PLUGIN_ROOT / "assets",
            token="secret-token",
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def request(self, path, *, method="GET", body=None, token=True):
        headers = {}
        if token:
            headers["X-Advisor-Token"] = "secret-token"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=data,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())

    def test_bootstrap_returns_live_models_and_default_config(self):
        status, payload = self.request("/api/bootstrap")

        self.assertEqual(status, 200)
        self.assertEqual(payload["models"], self.discovery["models"])
        self.assertEqual(payload["modelSource"], "test")
        self.assertEqual(
            [item["id"] for item in payload["config"]["models"]],
            ["gpt-5.6-sol", "codex02/gpt-5.6-sol"],
        )

    def test_config_can_be_saved_without_losing_priority_or_retries(self):
        config = {
            "version": 1,
            "enabled": True,
            "mode": "auto",
            "agent_protocol": "v2",
            "model_source": "manual",
            "catalog_path": "",
            "reasoning_effort": "xhigh",
            "on_exhausted": "block",
            "models": [
                {"id": "ccs-custom/model-id", "retries": 3, "reasoning_effort": "max"},
                {"id": "gpt-5.6-sol", "retries": 0, "reasoning_effort": None},
            ],
        }

        status, saved = self.request(
            "/api/config",
            method="PUT",
            body=config,
        )

        self.assertEqual(status, 200)
        self.assertEqual(saved["config"], config)

        _, bootstrap = self.request("/api/bootstrap")
        self.assertEqual(bootstrap["config"], config)

    def test_api_rejects_requests_without_session_token(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/bootstrap", token=False)

        self.assertEqual(raised.exception.code, 403)
        raised.exception.close()

    def test_catalog_refresh_preserves_saved_configuration(self):
        status, payload = self.request("/api/models?source=cc-switch")
        self.assertEqual(status, 200)
        self.assertEqual(payload["models"], self.discovery["models"])
        self.assertFalse((self.state_dir / "config.json").exists())


if __name__ == "__main__":
    unittest.main()
