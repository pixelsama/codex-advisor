# Codex Advisor

Codex Advisor 是一个运行在 Codex 全局环境中的可配置 Advisor 插件。它利用 Codex 的
`spawn_agent` 创建一个只读的战略审阅子代理，在关键方案、连续受阻或重大交付前提供第二意见。

它支持手动或自动触发 Advisor，并允许按优先级配置多个模型；当前模型不可用时，可以按该模型的
重试次数重试，仍然失败后再切换到下一个模型。Advisor 使用 `fork_context=true`，因此可以直接看到
父任务的完整上下文，同时通过角色提示词阻止 Advisor 再递归创建 Advisor。

## 为什么推荐搭配 OpenCodex

本插件最适合与 [OpenCodex](https://opencodex.me/) 一起使用。OpenCodex 可以统一管理 Codex 的
provider、路由模型和 subagent 模型列表；本插件直接读取 OpenCodex 的配置，不需要你手动把模型名称
抄到 Advisor 配置里。

相关链接：

- [OpenCodex 项目主页](https://opencodex.me/)
- [OpenCodex GitHub 仓库](https://github.com/lidge-jun/opencodex)
- [OpenCodex 配置参考](https://opencodex.me/reference/configuration/)
- [OpenCodex 的 Codex 集成说明](https://opencodex.me/guides/codex-integration/)

OpenCodex 的配置文件默认是 `~/.opencodex/config.json`。其中的 `subagentModels` 是 Codex
subagent 模型选择器使用的模型列表，例如：

```json
{
  "subagentModels": [
    "gpt-5.6-sol",
    "codex02/gpt-5.6-sol",
    "gpt-5.6-luna"
  ]
}
```

Codex Advisor 启动配置页面时会优先读取这个列表，并把它显示为可选择的 Advisor 模型。列表中的顺序
只决定 OpenCodex/Codex 的展示优先级；Advisor 自己的调用顺序在本插件网页中单独配置。Advisor 只会
使用列表中已经存在且当前可见的模型，不负责创建或注册 subagent 模型；实际可用模型还取决于 provider、
catalog 和账号权限，详见上面的官方文档。

如果没有安装或配置 OpenCodex，本插件会退回尝试 `codex debug models` 获取模型列表；但推荐使用
OpenCodex，因为它可以更方便地添加、路由和切换不同 provider 的模型，例如
`codex02/gpt-5.6-sol`。

## 功能

- 自动模式：由父模型在关键节点主动咨询 Advisor
- 手动模式：只有用户明确要求 `$advisor ask` 时才咨询
- 自定义 Advisor 模型优先级
- 每个模型独立配置额外重试次数
- 当前模型失败后按优先级切换到下一个模型
- 通过 `fork_context=true` 继承父任务的完整上下文
- 只对带 `[CODEX_ADVISOR]` 标记的子代理启用最终 Advisor 角色提示
- 防止 Advisor 把自己当成父执行模型，递归创建下一层 Advisor
- 本机 localhost 配置网页
- 保存配置后显示成功或失败横幅

## 安装要求

- 已安装带 subagent 能力的 Codex
- Python 3.10 或更高版本
- 推荐安装并配置 [OpenCodex](https://opencodex.me/)，以提供可用的 `subagentModels`

## 安装到 Codex

下面的步骤使用 Codex 默认的 personal marketplace，适用于 macOS、Linux，以及通过 Git Bash 或 WSL
运行的 Windows 环境。建议把插件放在 `~/plugins/codex-advisor`，因为 marketplace 中的本地路径按此
位置配置。

### 1. 克隆插件

```bash
mkdir -p ~/plugins
git clone https://github.com/pixelsama/codex-advisor.git ~/plugins/codex-advisor
```

如果已经克隆过：

```bash
git -C ~/plugins/codex-advisor pull --ff-only
```

### 2. 注册 personal marketplace

推荐使用下面的脚本。它会创建 personal marketplace（如果尚不存在），只更新
`codex-advisor` 条目，并保留已有插件：

```bash
python3 - <<'PY'
import json
from pathlib import Path

marketplace = Path.home() / ".agents" / "plugins" / "marketplace.json"
marketplace.parent.mkdir(parents=True, exist_ok=True)

if marketplace.exists():
    data = json.loads(marketplace.read_text(encoding="utf-8"))
else:
    data = {
        "name": "personal",
        "interface": {"displayName": "Personal"},
        "plugins": [],
    }

data.setdefault("name", "personal")
data.setdefault("interface", {"displayName": "Personal"})
plugins = data.setdefault("plugins", [])
plugins[:] = [item for item in plugins if item.get("name") != "codex-advisor"]
plugins.append({
    "name": "codex-advisor",
    "source": {"source": "local", "path": "./plugins/codex-advisor"},
    "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    },
    "category": "Productivity",
})
marketplace.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Updated {marketplace}")
PY
```

也可以手动把下面的对象加入 `~/.agents/plugins/marketplace.json` 的 `plugins` 数组：

```json
{
  "name": "codex-advisor",
  "source": {"source": "local", "path": "./plugins/codex-advisor"},
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

### 3. 安装并检查插件

```bash
codex plugin add codex-advisor@personal
codex plugin list | grep codex-advisor
```

插件状态应显示为 `installed, enabled`。安装或更新后请新建一个 Codex 任务，以便加载当前插件版本。

### 4. 打开配置页面

```bash
codex-advisor open
```

页面会读取当前可见的 subagent 模型。你可以选择自动/手动模式、调整模型优先级、设置每个模型的重试
次数、选择 reasoning effort，以及决定所有模型都失败后的行为。点击“保存配置”后，页面顶部会显示
保存成功或失败的横幅。

## 使用方式

### 开启和关闭

```bash
codex-advisor on
codex-advisor off
codex-advisor status
codex-advisor models
```

也可以直接运行 `codex-advisor` 或 `advisor`，默认打开配置网页。

### 手动模式

把网页中的模式设置为手动，然后在 Codex 中明确要求：

```text
$advisor ask 请审查当前方案的风险、遗漏和下一步
```

手动模式不会因为普通任务而自动创建 Advisor。

### 自动模式

把网页中的模式设置为自动。父模型会根据注入的协议自行判断是否值得咨询，例如：

- 形成重要技术方案之前
- 连续遇到阻塞或失败之后
- 准备完成重大交付之前

简单问题不会被要求机械地调用 Advisor。Advisor 只提供建议，最终判断和文件修改仍由父执行模型负责。

### 模型优先级和重试

网页中的模型从上到下就是 Advisor 的调用顺序。对每个模型可以单独设置“额外重试次数”：

1. 先尝试当前模型
2. 如果是启动失败、模型/提供商不可用、限流、超时或子代理失败，则按配置重试
3. 重试次数用完后，切换到下一个模型
4. 某个模型给出了正常但不符合预期的建议，不会因此当成调用失败

例如：

```text
1. gpt-5.6-sol             额外重试 1 次，最多 2 次
2. codex02/gpt-5.6-sol    额外重试 1 次，最多 2 次
```

### 完整上下文与递归保护

Advisor 调用固定使用 `fork_context=true`，这样 Advisor 可以直接利用父会话中的代码、讨论和上下文，
减少重新读取和复述的成本。为了避免 Advisor 把自己误认为父执行模型，调用消息会带有
`[CODEX_ADVISOR]` 标记和最终叶子角色提示：带标记的子代理只做只读审阅，不调用
`spawn_agent`、`wait_agent`、`close_agent`，也不会再次创建 Advisor。

## 配置文件

Advisor 配置默认保存于：

```text
~/.codex/advisor/config.json
```

OpenCodex 的 subagent 模型来源默认是：

```text
~/.opencodex/config.json
```

本插件也支持通过 `CODEX_ADVISOR_STATE_DIR` 指定 Advisor 状态目录，以及通过 `CODEX_CLI_PATH` 指定
Codex CLI 路径。配置网页只监听 localhost，并使用短期 token 保护当前配置会话。

## 开发与验证

```bash
python3 -m unittest discover -s tests -v
python3 /path/to/codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

插件源码分为三部分：`hooks/` 负责 Codex 运行时注入和子代理角色保护，`scripts/` 负责配置、模型发现、
协议和本地服务，`assets/` 负责配置网页。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
