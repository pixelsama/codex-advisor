#!/usr/bin/env python3
"""Shared configuration, model discovery, and protocol generation."""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CONFIG_VERSION = 1
MAX_RETRIES = 5
DEFAULT_STATE_DIR = Path.home() / ".codex" / "advisor"
PREFERRED_MODELS = ("gpt-5.6-sol", "codex02/gpt-5.6-sol")
REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
MODES = {"auto", "manual"}
EXHAUSTED_POLICIES = {"continue", "block"}
AGENT_PROTOCOLS = {"auto", "v1", "v2"}
MODEL_SOURCES = {"codex", "cc-switch", "catalog", "manual"}
MAX_CATALOG_BYTES = 32 * 1024 * 1024
ADVISOR_MARKER = "[CODEX_ADVISOR]"
ADVISOR_LEAF_PREAMBLE = f"""{ADVISOR_MARKER}
你是最终 Advisor 子代理。根据下方审阅问题和主模型提供的背景完成只读审阅。
不得修改文件、发送消息、运行 Advisor 或调用任何子代理工具。背景不足时说明缺少哪些信息。"""


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


def _catalog_filename_allowed(path: Path) -> bool:
    name = path.name.lower()
    return name in {"models.json", "models_cache.json", "model_catalog.json"} or name.endswith("-catalog.json")


def _validate_model_source(source: Any, catalog_path: Any) -> tuple[str, str]:
    if not isinstance(source, str) or source not in MODEL_SOURCES:
        raise ConfigError("请选择有效的模型来源。")
    if not isinstance(catalog_path, str):
        raise ConfigError("模型目录路径必须是文本。")
    if source != "catalog":
        return source, ""
    try:
        path = Path(catalog_path.strip()).expanduser()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ConfigError("模型目录路径无效。") from exc
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")) or not _catalog_filename_allowed(path):
        raise ConfigError("请输入模型目录的绝对路径。文件名应为 models.json、models_cache.json、model_catalog.json 或以 -catalog.json 结尾。")
    return source, str(path)


def discover_subagent_models(
    *,
    source: str = "codex",
    catalog_path: str = "",
    codex_home: Path | None = None,
) -> dict[str, Any]:
    """Read only the selected Codex catalog and expose its model metadata."""

    source, catalog_path = _validate_model_source(source, catalog_path)
    result = {
        "models": [],
        "modelDetails": {},
        "source": source,
        "path": None,
        "updatedAt": None,
    }
    if source == "manual":
        return result

    if source == "catalog":
        path = Path(catalog_path)
    else:
        home = codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
        path = home / ("cc-switch-model-catalog.json" if source == "cc-switch" else "models_cache.json")
    result["path"] = str(path)
    try:
        resolved = path.resolve(strict=True)
        if str(resolved).startswith(("\\\\", "//")) or not _catalog_filename_allowed(resolved):
            result["error"] = "请选择一个 Codex 模型目录文件。"
            return result
        info = resolved.stat()
        if not stat.S_ISREG(info.st_mode):
            result["error"] = "请选择一个 Codex 模型目录文件。"
            return result
        if info.st_size > MAX_CATALOG_BYTES:
            result["error"] = "模型目录文件超过 32 MiB。"
            return result
        with resolved.open("rb") as handle:
            data = handle.read(MAX_CATALOG_BYTES + 1)
        if len(data) > MAX_CATALOG_BYTES:
            result["error"] = "模型目录文件超过 32 MiB。"
            return result
        catalog = json.loads(data.decode("utf-8-sig"))
    except FileNotFoundError:
        result["error"] = "还没有找到这个模型目录。可以先刷新 Codex 的模型列表，或手动填写。"
        return result
    except (OSError, RuntimeError, ValueError):
        result["error"] = "无法读取模型目录。请确认路径和文件格式，或手动填写。"
        return result

    rows = catalog.get("models") if isinstance(catalog, dict) else None
    if not isinstance(rows, list):
        result["error"] = "文件没有 Codex 模型列表。"
        return result

    details: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("visibility") not in (None, "list"):
            continue
        model = row.get("slug")
        if not isinstance(model, str) or not model.strip() or model in details:
            continue
        levels = row.get("supported_reasoning_levels")
        supported = _unique_strings(
            level.get("effort") for level in levels if isinstance(level, dict)
        ) if isinstance(levels, list) else []
        default_effort = row.get("default_reasoning_level")
        details[model] = {
            "efforts": [effort for effort in supported if effort in REASONING_EFFORTS],
            "defaultEffort": default_effort if default_effort in REASONING_EFFORTS else None,
        }
    result["models"] = list(details)
    result["modelDetails"] = details
    result["updatedAt"] = datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()
    return result


def default_config(available_models: list[str]) -> dict[str, Any]:
    available = _unique_strings(available_models)
    selected = [model for model in PREFERRED_MODELS if model in available]
    if not selected:
        selected = available[:1]
    return {
        "version": CONFIG_VERSION,
        "enabled": False,
        "mode": "auto",
        "agent_protocol": "auto",
        "model_source": "codex",
        "catalog_path": "",
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

    agent_protocol = config.get("agent_protocol", "auto")
    if not isinstance(agent_protocol, str) or agent_protocol not in AGENT_PROTOCOLS:
        raise ConfigError("子代理接口必须是自动、V1 或 V2。")
    model_source, catalog_path = _validate_model_source(
        config.get("model_source", "codex"), config.get("catalog_path", "")
    )

    effort = config.get("reasoning_effort")
    if effort not in REASONING_EFFORTS:
        raise ConfigError("请选择有效的 Advisor 默认推理强度。")

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
        if any(character.isspace() or not character.isprintable() or character == "`" for character in model_id):
            raise ConfigError("模型 ID 不能包含空白、控制字符或反引号。请粘贴 Codex 显示的完整 ID。")
        if model_id in seen:
            raise ConfigError(f"模型不能重复：{model_id}")
        if isinstance(retries, bool) or not isinstance(retries, int):
            raise ConfigError(f"{model_id} 的 retries 必须是整数。")
        if retries < 0 or retries > MAX_RETRIES:
            raise ConfigError(
                f"{model_id} 的额外重试次数必须在 0 到 {MAX_RETRIES} 之间。"
            )
        seen.add(model_id)
        model = {"id": model_id, "retries": retries}
        if "reasoning_effort" in raw_model:
            model_effort = raw_model["reasoning_effort"]
            if model_effort is not None and model_effort not in REASONING_EFFORTS:
                raise ConfigError(f"{model_id} 的推理强度无效。")
            model["reasoning_effort"] = model_effort
        models.append(model)

    return {
        "version": CONFIG_VERSION,
        "enabled": enabled,
        "mode": mode,
        "agent_protocol": agent_protocol,
        "model_source": model_source,
        "catalog_path": catalog_path,
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


def model_reasoning_effort(config: dict[str, Any], model: dict[str, Any]) -> str | None:
    return model.get("reasoning_effort", config["reasoning_effort"])


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
        effort = model_reasoning_effort(validated, item)
        effort_description = f'`reasoning_effort="{effort}"`' if effort is not None else "省略 `reasoning_effort`，由 Codex 决定"
        model_lines.append(
            f"{index}. `{item['id']}`：额外重试 {item['retries']} 次，"
            f"最多 {total_attempts} 次。{effort_description}。"
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
    protocol = validated["agent_protocol"]
    v2 = (
        'V2：使用当前会话的 `spawn_agent`，按工具声明提供唯一的 `task_name`，传 `fork_turns="none"`。'
        '初次调用须按工具声明提供全部参数和下方完整任务消息，Guard 不会改写 V2 请求。用 V2 的 `wait_agent` 等待顾问结果。'
    )
    v1 = 'V1：使用当前会话的经典 `spawn_agent`，省略 `fork_context`。按返回的代理 ID 等待结果，完成后用该接口的 `close_agent` 关闭顾问。'
    if protocol == "auto":
        interface_rules = (
            "- 自动判断：检查当前会话提供的 `spawn_agent` 声明。支持 `fork_turns` 就用 V2，支持 `fork_context` 就用 V1。"
            "工具未直接显示时先用当前会话的工具发现能力。\n"
            f"- {v2}\n- {v1}"
        )
    else:
        interface_rules = f"- 已指定 {protocol.upper()}。确认当前会话提供这套接口。\n- {v2 if protocol == 'v2' else v1}"

    return f"""Advisor 角色分流：
- 如果当前任务消息以 `{ADVISOR_MARKER}` 开头，你就是最终 Advisor 子代理。仅根据收到的审阅任务和其中提供的背景完成只读战略审阅并返回建议。不要调用 Advisor 或任何子代理工具。
- 以下调用说明只适用于负责派发审阅的主模型。

用户已手动开启 Codex Advisor。{trigger}

Advisor 模型链（严格按顺序）：
{chr(10).join(model_lines)}

调用协议：
{interface_rules}
- 调用前检查实际接口是否匹配，以及工具是否支持指定模型和该候选所需的显式推理强度。无法确认或不匹配时，说明原因并按下方失败策略处理。使用当前会话的子代理工具，不创建独立对话。
- 对每个候选显式传入 `model`，按该候选的说明设置或省略 `reasoning_effort`。
- 两套接口均以无父对话历史的方式调用。主动提供本次问题、目标、约束、相关决定和所需证据或文件路径，使顾问无需读取父对话就能回答。
- 将下方三行作为 `message` 的开头，接上本次审阅问题和背景：
{ADVISOR_LEAF_PREAMBLE}
- 成功完成且给出可用建议即停止模型链；观点不合预期不算失败。
- 只有启动失败、模型/提供商不可用、限流、超时或子代理失败时，才在同一模型上按配置重试；用完该模型次数后再进入下一个。
- 用户取消、工具格式不匹配、明显无效的任务输入、上下文或安全边界错误不要重试或降级。
- Advisor 是建议者，不替代主模型判断；吸收建议后由主模型继续执行和回答。
- {exhausted}{focus_line}
"""
