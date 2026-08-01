#!/usr/bin/env python3
"""Localhost-only configuration server for Codex Advisor."""

from __future__ import annotations

import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from advisor_core import (
    ConfigError,
    discover_subagent_models,
    load_config,
    save_config,
)


class AdvisorService:
    def __init__(
        self,
        *,
        state_dir: Path,
        discover: Callable[[], dict[str, Any]] = discover_subagent_models,
    ) -> None:
        self.state_dir = state_dir
        self.discover = discover

    def bootstrap(self) -> dict[str, Any]:
        discovery = self.discover()
        models = discovery.get("models", [])
        return {
            "config": load_config(
                state_dir=self.state_dir,
                available_models=models,
            ),
            "models": models,
            "modelSource": discovery.get("source", "unavailable"),
            "modelSourcePath": discovery.get("path"),
        }

    def update_config(self, payload: Any) -> dict[str, Any]:
        return save_config(payload, state_dir=self.state_dir)


class AdvisorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        service: AdvisorService,
        assets_dir: Path,
        token: str,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.service = service
        self.assets_dir = assets_dir.resolve()
        self.token = token
        self.last_activity = time.monotonic()


class AdvisorRequestHandler(BaseHTTPRequestHandler):
    server: AdvisorHTTPServer

    def log_message(self, format_string: str, *args: Any) -> None:
        del format_string, args

    def _touch(self) -> None:
        self.server.last_activity = time.monotonic()

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        parsed = urlparse(self.path)
        query_token = parse_qs(parsed.query).get("token", [None])[0]
        header_token = self.headers.get("X-Advisor-Token")
        return self.server.token in (query_token, header_token)

    def _require_api_auth(self) -> bool:
        if self._authorized():
            return True
        self._send_json(403, {"error": "无效的本地配置会话令牌。"})
        return False

    def _serve_asset(self) -> None:
        parsed = urlparse(self.path)
        relative = unquote(parsed.path).lstrip("/") or "index.html"
        candidate = (self.server.assets_dir / relative).resolve()
        if (
            candidate != self.server.assets_dir
            and self.server.assets_dir not in candidate.parents
        ):
            self._send_json(404, {"error": "Not found"})
            return
        if not candidate.is_file():
            self._send_json(404, {"error": "Not found"})
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "application/json",
        }:
            content_type += "; charset=utf-8"
        self._send_bytes(200, candidate.read_bytes(), content_type)

    def do_GET(self) -> None:
        self._touch()
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            if not self._require_api_auth():
                return
            try:
                self._send_json(200, self.server.service.bootstrap())
            except ConfigError as exc:
                self._send_json(400, {"error": str(exc)})
            return
        self._serve_asset()

    def do_PUT(self) -> None:
        self._touch()
        if urlparse(self.path).path != "/api/config":
            self._send_json(404, {"error": "Not found"})
            return
        if not self._require_api_auth():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ConfigError("请求体过大。")
            payload = json.loads(self.rfile.read(length))
            config = self.server.service.update_config(payload)
            self._send_json(200, {"config": config})
        except (ConfigError, json.JSONDecodeError, ValueError) as exc:
            self._send_json(400, {"error": str(exc)})

    def do_POST(self) -> None:
        self._touch()
        if urlparse(self.path).path != "/api/shutdown":
            self._send_json(404, {"error": "Not found"})
            return
        if not self._require_api_auth():
            return
        self._send_json(200, {"ok": True})
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def create_server(
    *,
    host: str,
    port: int,
    service: AdvisorService,
    assets_dir: Path,
    token: str,
) -> AdvisorHTTPServer:
    return AdvisorHTTPServer(
        (host, port),
        AdvisorRequestHandler,
        service=service,
        assets_dir=assets_dir,
        token=token,
    )
