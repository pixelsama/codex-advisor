#!/usr/bin/env python3
"""Command-line entry point for Codex Advisor."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable

from advisor_core import (
    ConfigError,
    build_advisor_protocol,
    default_config,
    discover_subagent_models,
    load_config,
    save_config,
    state_dir_from_env,
)
from advisor_server import AdvisorService, create_server


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PLUGIN_ROOT / "assets"


def set_enabled(
    enabled: bool,
    *,
    state_dir: Path | None = None,
    discover: Callable[[], dict[str, Any]] = discover_subagent_models,
) -> dict[str, Any]:
    target_state_dir = state_dir or state_dir_from_env()
    discovery = discover()
    available_models = discovery.get("models", [])
    config = load_config(
        state_dir=target_state_dir,
        available_models=available_models,
    )
    if enabled and not config["models"]:
        config["models"] = default_config(available_models)["models"]
    config["enabled"] = enabled
    return save_config(config, state_dir=target_state_dir)


def status_payload(
    *,
    state_dir: Path | None = None,
    discover: Callable[[], dict[str, Any]] = discover_subagent_models,
) -> dict[str, Any]:
    target_state_dir = state_dir or state_dir_from_env()
    discovery = discover()
    return {
        "config": load_config(
            state_dir=target_state_dir,
            available_models=discovery.get("models", []),
        ),
        "availableModels": discovery.get("models", []),
        "modelSource": discovery.get("source", "unavailable"),
        "modelSourcePath": discovery.get("path"),
    }


def _write_ready_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def serve(
    *,
    state_dir: Path,
    token: str,
    ready_file: Path | None,
    lifetime_seconds: int,
) -> int:
    service = AdvisorService(state_dir=state_dir)
    server = create_server(
        host="127.0.0.1",
        port=0,
        service=service,
        assets_dir=ASSETS_DIR,
        token=token,
    )
    host, port = server.server_address
    url = f"http://{host}:{port}/?token={token}"
    if ready_file is not None:
        _write_ready_file(
            ready_file,
            {"url": url, "pid": os.getpid(), "port": port},
        )
    print(url, flush=True)

    if lifetime_seconds > 0:
        import threading

        timer = threading.Timer(lifetime_seconds, server.shutdown)
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def open_gui(*, state_dir: Path, timeout_seconds: float = 8.0) -> str:
    state_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    ready_file = state_dir / f"server-ready-{token}.json"
    log_path = state_dir / "server.log"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--state-dir",
        str(state_dir),
        "_serve",
        "--token",
        token,
        "--ready-file",
        str(ready_file),
        "--lifetime-seconds",
        "1800",
    ]
    with log_path.open("ab") as log_handle:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            if ready_file.exists():
                payload = json.loads(ready_file.read_text(encoding="utf-8"))
                url = payload["url"]
                webbrowser.open(url)
                return url
            time.sleep(0.05)
    finally:
        try:
            ready_file.unlink()
        except FileNotFoundError:
            pass
    raise RuntimeError(f"配置服务器未能启动，请查看日志：{log_path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-advisor",
        description="Configure and invoke Codex Advisor.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=state_dir_from_env(),
        help=argparse.SUPPRESS,
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("open", help="打开本地配置网页。")
    subparsers.add_parser("on", help="开启 Advisor。")
    subparsers.add_parser("off", help="关闭 Advisor。")

    status_parser = subparsers.add_parser("status", help="查看当前配置。")
    status_parser.add_argument("--json", action="store_true")

    models_parser = subparsers.add_parser("models", help="查看当前 subagent 模型。")
    models_parser.add_argument("--json", action="store_true")

    protocol_parser = subparsers.add_parser(
        "protocol",
        help="输出一次 Advisor 调用协议，供 $advisor ask 使用。",
    )
    protocol_parser.add_argument("--focus", default="")

    serve_parser = subparsers.add_parser("_serve", help=argparse.SUPPRESS)
    serve_parser.add_argument("--token", required=True)
    serve_parser.add_argument("--ready-file", type=Path)
    serve_parser.add_argument("--lifetime-seconds", type=int, default=1800)
    return parser


def _print_status(payload: dict[str, Any]) -> None:
    config = payload["config"]
    print(f"Advisor: {'开启' if config['enabled'] else '关闭'}")
    print(f"模式: {config['mode']}")
    print(f"模型来源: {payload['modelSource']}")
    if payload.get("modelSourcePath"):
        print(f"来源位置: {payload['modelSourcePath']}")
    if config["models"]:
        print("优先级:")
        for index, item in enumerate(config["models"], start=1):
            print(
                f"  {index}. {item['id']} "
                f"(额外重试 {item['retries']} 次)"
            )
    else:
        print("优先级: 尚未选择模型")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "open"
    state_dir = args.state_dir.expanduser()

    try:
        if command == "open":
            url = open_gui(state_dir=state_dir)
            print(f"Codex Advisor 配置页已打开：{url}")
            return 0
        if command == "on":
            config = set_enabled(True, state_dir=state_dir)
            print(
                f"Codex Advisor 已开启，已配置 {len(config['models'])} 个模型。"
            )
            return 0
        if command == "off":
            set_enabled(False, state_dir=state_dir)
            print("Codex Advisor 已关闭。")
            return 0
        if command == "status":
            payload = status_payload(state_dir=state_dir)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                _print_status(payload)
            return 0
        if command == "models":
            discovery = discover_subagent_models()
            if args.json:
                print(json.dumps(discovery, ensure_ascii=False, indent=2))
            else:
                print(f"来源: {discovery['source']}")
                for index, model in enumerate(discovery["models"], start=1):
                    print(f"{index}. {model}")
            return 0
        if command == "protocol":
            config = load_config(state_dir=state_dir, available_models=[])
            print(build_advisor_protocol(config, focus=args.focus))
            return 0
        if command == "_serve":
            return serve(
                state_dir=state_dir,
                token=args.token,
                ready_file=args.ready_file,
                lifetime_seconds=args.lifetime_seconds,
            )
    except (ConfigError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"codex-advisor: {exc}", file=sys.stderr)
        return 2

    parser.error(f"未知命令：{command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
