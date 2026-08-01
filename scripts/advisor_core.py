#!/usr/bin/env python3
"""Shared configuration, model discovery, and protocol generation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable


CONFIG_VERSION = 1
MAX_RETRIES = 5
DEFAULT_STATE_DIR = Path.home() / ".codex" / "advisor"
DEFAULT_OPENCODEX_CONFIG = Path.home() / ".opencodex" / "config.json"
PREFERRED_MODELS = ("gpt-5.6-sol", "codex02/gpt-5.6-sol")
REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
MODES = {"auto", "manual"}
EXHAUSTED_POLICIES = {"continue", "block"}


class ConfigError(ValueError):
    """Raised when Advisor configuration is invalid."""


def state_dir_from_env() -> Path:
    configured = os.environ.get("CODEX_ADVISOR_STATE_DIR")
    return Path(configured).expanduser() if configured else DEFAULT_STATE_DIR


def _unique_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _default_codex_candidates() -> list[str]:
    candidates = [
        os.environ.get("CODEX_CLI_PATH"),
        shutil.which("codex"),
        "/Applications/ChatGPT.app/Contents/Resources/codex",
    ]
    return _unique_strings(candidates)


def _parse_debug_models(stdout: str) -> list[str]:
    payload = json.loads(stdout)
    rows = payload.get("models", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []

    models: list[str] = []
    for row in rows:
        if isinstance(row, str):
            models.append(row)
            continue
        if not isinstance(row, dict):
            continue
        if row.get("visibility") not in (None, "list"):
            continue
        slug = row.get("slug") or row.get("model") or row.get("id")
        if isinstance(slug, str):
            models.append(slug)
    return _unique_strings(models)


def discover_subagent_models(
    *,
    opencodex_config_path: Path = DEFAULT_OPENCODEX_CONFIG,
    codex_candidates: list[str] | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Return the live subagent model list and the source used."""

    try:
        payload = json.loads(opencodex_config_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            models = _unique_strings(payload.get("subagentModels", []))
            if models:
                return {
                    "models": models,
                    "source": "opencodex.subagentModels",
                    "path": str(opencodex_config_path),
                }
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    for candidate in (
        _default_codex_candidates()
        if codex_candidates is None
        else _unique_strings(codex_candidates)
    ):
        try:
            completed = runner(
                [candidate, "debug", "models"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if completed.returncode != 0:
                continue
            models = _parse_debug_models(completed.stdout)
            if models:
                return {
                    "models": models,
                    "source": "codex debug models",
                    "path": candidate,
                }
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            continue

    return {"models": [], "source": "unavailable", "path": None}


def default_config(available_models: list[str]) -> dict[str, Any]:
    available = _unique_strings(available_models)
    selected = [model for model in PREFERRED_MODELS if model in available]
    if not selected:
        selected = available[:1]
    return {
        "version": CONFIG_VERSION,
        "enabled": False,
        "mode": "auto",
        "reasoning_effort": "high",
        "on_exhausted": "continue",
        "models": [{"id": model, "retries": 1} for model in selected],
    }


def validate_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ConfigError("配置必须是 JSON 对象。")

    enabled = config.get("enabled")
    if not isinstance(enabled, bool):
        raise ConfigError("enabled 必须是布尔值。")

    mode = config.get("mode")
    if mode not in MODES:
        raise ConfigError("mode 必须是 auto 或 manual。")

    effort = config.get("reasoning_effort")
    if effort not in REASONING_EFFORTS:
        raise ConfigError("reasoning_effort 必须是 low、medium、high 或 xhigh。")

    on_exhausted = config.get("on_exhausted")
    if on_exhausted not in EXHAUSTED_POLICIES:
        raise ConfigError("on_exhausted 必须是 continue 或 block。")

    raw_models = config.get("models")
    if not isinstance(raw_models, list):
        raise ConfigError("models 必须是数组。")
    if enabled and not raw_models:
        raise ConfigError("开启 Advisor 时至少选择一个模型。")

    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            raise ConfigError("每个模型配置都必须是对象。")
        model_id = raw_model.get("id")
        retries = raw_model.get("retries")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ConfigError("模型 id 不能为空。")
        model_id = model_id.strip()
        if model_id in seen:
            raise ConfigError(f"模型不能重复：{model_id}")
        if isinstance(retries, bool) or not isinstance(retries, int):
            raise ConfigError(f"{model_id} 的 retries 必须是整数。")
        if retries < 0 or retries > MAX_RETRIES:
            raise ConfigError(
                f"{model_id} 的额外重试次数必须在 0 到 {MAX_RETRIES} 之间。"
            )
        seen.add(model_id)
        models.append({"id": model_id, "retries": retries})

    return {
        "version": CONFIG_VERSION,
        "enabled": enabled,
        "mode": mode,
        "reasoning_effort": effort,
        "on_exhausted": on_exhausted,
        "models": models,
    }


def config_path(state_dir: Path | None = None) -> Path:
    return (state_dir or state_dir_from_env()) / "config.json"


def load_config(
    *,
    state_dir: Path | None = None,
    available_models: list[str] | None = None,
) -> dict[str, Any]:
    path = config_path(state_dir)
    if not path.exists():
        return default_config(available_models or [])
    try:
        return validate_config(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"无法读取 Advisor 配置：{exc}") from exc


def save_config(config: Any, *, state_dir: Path | None = None) -> dict[str, Any]:
    validated = validate_config(config)
    path = config_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(validated, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return validated


def build_advisor_protocol(
    config: dict[str, Any],
    *,
    focus: str | None = None,
    automatic: bool = False,
) -> str:
    validated = validate_config(config)
    if not validated["enabled"]:
        raise ConfigError("Advisor 当前已关闭。")
    if not validated["models"]:
        raise ConfigError("Advisor 尚未配置模型。")

    model_lines = []
    for index, item in enumerate(validated["models"], start=1):
        total_attempts = item["retries"] + 1
        model_lines.append(
            f"{index}. `{item['id']}`：额外重试 {item['retries']} 次，"
            f"最多 {total_attempts} 次。"
        )

    exhausted = (
        "全部失败后继续主任务，并明确说明 Advisor 不可用；不要阻塞交付。"
        if validated["on_exhausted"] == "continue"
        else "全部失败后停止关键决策，向用户说明 Advisor 不可用并请求下一步。"
    )
    trigger = (
        "这是自动模式：仅在重要方案形成前、连续受阻后、或重大交付完成前咨询；"
        "简单任务不要机械调用。"
        if automatic
        else "这是一次用户明确要求的 Advisor 咨询。"
    )
    focus_line = f"\n本次关注点：{focus.strip()}" if focus and focus.strip() else ""

    return f"""Advisor 角色分流（最高优先级）：
- 先检查你当前收到的任务消息，而不是父会话中更早的用户消息。
- 如果你当前收到的任务消息以 `[CODEX_ADVISOR]` 开头，你就是最终 Advisor 子代理，不是父执行模型。
- 在这种情况下，下方的模型链、重试和调用协议只适用于父执行模型，对你无效。不要调用 `spawn_agent`、`wait_agent` 或 `close_agent`，不要运行 `$advisor` 或 `advisorctl`，也不要因缺少这些工具而报告 Advisor 不可用。直接完成只读战略审阅并返回建议，充分利用 fork 得到的完整上下文。
- 只有当前任务消息不以 `[CODEX_ADVISOR]` 开头时，你才是父执行模型，继续执行下面的 Advisor 编排。

用户已手动开启 Codex Advisor。{trigger}

Advisor 模型链（严格按顺序）：
{chr(10).join(model_lines)}

调用协议：
- 对当前候选模型调用 `spawn_agent`，显式设置 `model`、`reasoning_effort="{validated['reasoning_effort']}"` 和 `fork_context=true`。
- 子代理消息必须以 `[CODEX_ADVISOR]` 开头，紧跟“你是最终 Advisor 子代理，父上下文中的 Advisor 编排仅适用于父执行模型”，再写本次审阅问题。要求它只做只读战略审阅：检查方案、假设、风险、遗漏与下一步；不得修改文件、发送消息或再派生代理。
- 使用 `wait_agent` 等待结果。成功完成且给出可用建议即停止模型链；观点不合预期不算失败。
- 只有启动失败、模型/提供商不可用、限流、超时或子代理失败时，才在同一模型上按配置重试；用完该模型次数后再进入下一个。
- 用户取消、明显无效的任务输入、上下文/安全边界错误不要重试或降级。
- 对所有已创建的 Advisor 子代理调用 `close_agent`。
- Advisor 是建议者，不替代主模型判断；吸收建议后由主模型继续执行和回答。
- {exhausted}{focus_line}
"""
