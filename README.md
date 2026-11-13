# Codex Advisor

Codex Advisor 是一个运行在 Codex 全局环境中的可配置 Advisor 插件。它利用 Codex 的
`spawn_agent` 创建一个只读的战略审阅子代理，在关键方案、连续受阻或重大交付前提供第二意见。

它支持手动或自动触发 Advisor，并允许按优先级配置多个模型；当前模型不可用时，可以按该模型的
重试次数重试，仍然失败后再切换到下一个模型。顾问在当前会话中作为子代理运行，由主模型在任务中交接审阅所需背景。

## 模型来源

模型目录供 WebUI 选模型和推理档位，无需单独安装 Codex CLI 或 OpenCodex。

- **Codex 本机缓存**读取 `~/.codex/models_cache.json`，适合官方登录。目录是最近一次缓存的列表，Codex 会话负责验证模型能否启动。
- **CC Switch 发布的目录**读取 `~/.codex/cc-switch-model-catalog.json`。直连已配置模型映射或使用聚合时，可以从这份目录选择。
- **自定义 Codex 模型目录**接受模型目录文件的绝对路径，例如 OpenCodex 生成的 `opencodex-catalog.json`。文件名应为 `models.json`、`models_cache.json`、`model_catalog.json` 或以 `-catalog.json` 结尾。
- **手动添加**随时可用。粘贴 Codex 模型选择器里的完整 ID，再选推理档位。手动添加不会向 Codex 注册模型。

设置 `CODEX_HOME` 时，两个标准目录从该位置读取。Advisor 从模型目录提取可显示的模型 ID 和推理档位，
供应商配置、API Key 和登录凭据由 Codex 或 CC Switch 管理。网页显示当前选择的目录来源和文件更新时间。

## 功能

- 自动模式：由父模型在关键节点主动咨询 Advisor
- 手动模式：只有用户明确要求 `$advisor ask` 时才咨询
- 自定义 Advisor 模型优先级
- 每个模型独立配置推理强度和额外重试次数
- 当前模型失败后按优先级切换到下一个模型
- 自动识别当前会话的 V1 或 V2 子代理接口，也可显式指定
- 只对带 `[CODEX_ADVISOR]` 标记的子代理启用最终 Advisor 角色提示
- 防止 Advisor 把自己当成父执行模型，递归创建下一层 Advisor
- 本机 localhost 配置网页
- 保存配置后显示成功或失败横幅

## 安装要求

- 已安装带 subagent 能力的 Codex
- Python 3.10 或更高版本

## 安装到 Codex

仓库带有本地 marketplace。Windows 可以用 PowerShell 和 Windows Python Launcher 安装及打开配置页。

### 1. 从 GitHub 安装

在 Codex Desktop 的「添加插件市场」中，将来源填为 `pixelsama/codex-advisor`，Git 引用填 `main`，稀疏路径留空。
添加市场后，按第 3 步安装插件。

### 2. 从本地仓库安装

```text
git clone https://github.com/pixelsama/codex-advisor.git codex-advisor
cd codex-advisor
```

如果已经克隆过，在仓库目录运行：

```bash
git pull --ff-only
```

仓库包含本地市场文件。在 Codex Desktop 的「添加插件市场」中，将来源填为仓库根目录的绝对路径，Git 引用和稀疏路径留空。
也可以在仓库根目录运行 `codex plugin marketplace add .`。

### 3. 启用并检查插件

如果已安装旧版，请先在 Codex 的已安装插件中停用旧来源的 Advisor，例如 `codex-advisor@vibecoding-local`。
保留旧版和设置文件方便回滚。每次只启用一个 Advisor，避免两版同时向对话加入不同的调用说明。

在插件目录选择「Codex Advisor」来源并安装。使用终端时，先添加市场，再安装：

```bash
codex plugin marketplace add pixelsama/codex-advisor --ref main
codex plugin add codex-advisor@advisor-market
codex plugin list
```

确认 `codex-advisor@advisor-market` 已启用，旧来源已停用。若 Codex 提示审核插件 Hook，请按界面审核后启用。
安装或更新后请新建 Codex 对话以加载当前插件版本。

### 4. 打开配置页面

在 Codex 输入 `$advisor config`。也可以在仓库目录运行
`py -3 -X utf8 scripts/advisorctl.py open`（Windows），或
`python3 scripts/advisorctl.py open`（macOS/Linux）。

选择模型来源后，可以加入目录中的模型或手动填写模型 ID。点击「保存配置」后，下次发消息或手动咨询时读取新设置。

## 使用方式

### 开启和关闭

在此仓库的根目录运行，例如 Windows PowerShell：

```powershell
py -3 -X utf8 scripts/advisorctl.py on
py -3 -X utf8 scripts/advisorctl.py off
py -3 -X utf8 scripts/advisorctl.py status
py -3 -X utf8 scripts/advisorctl.py models
```

macOS/Linux 使用 `python3 scripts/advisorctl.py` 加同样的子命令。
在 Codex 里调用 `$advisor` 时，技能会直接运行自己安装目录中的脚本。

### 在 Windows PowerShell 创建 `codex-advisor` 命令

从 GitHub 市场安装 `codex-advisor@advisor-market` 的 `0.2.2` 或更新版本后，新开 Codex 对话并输入 `$advisor install-command`。
Codex 会运行已安装插件自带的 PowerShell 脚本。出现用户目录写入授权提示时，按界面完成授权。
打开一个新的 PowerShell 窗口即可演示。

```powershell
codex-advisor status
codex-advisor
```

脚本会把命令写到 `%USERPROFILE%\.local\bin`，并在需要时将该目录加入当前用户的 PATH。
如果已有旧启动脚本，会先在同一目录创建 `.bak` 备份。命令每次运行时都会从 `advisor-market` 缓存选择最高的完整版本，之后升级插件可以继续使用同一个命令。
`codex-advisor` 默认打开配置页，也可带上 `status`、`models`、`on` 或 `off`。

也可以在 PowerShell 直接运行插件安装目录中的 `scripts\install-terminal-command.ps1`。例如使用默认 Codex 目录的 `0.2.2` 可以这样运行。

```powershell
& "$env:USERPROFILE\.codex\plugins\cache\advisor-market\codex-advisor\0.2.2\scripts\install-terminal-command.ps1"
```

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

每个模型还可以设置推理强度。选择「跟随 Advisor 默认」使用页面上的全局档位。选择「由 Codex 决定」
会省略这次调用的显式档位，交给 Codex 的默认逻辑。旧配置中的模型、顺序、重试次数和全局档位可继续使用。

### 子代理接口和上下文

默认选择「自动跟随当前会话」。Advisor 根据当前 `spawn_agent` 工具的声明识别 V1 或 V2。
显式选择 V1 或 V2 时，当前会话必须提供匹配的工具。这项设置只作用于 Advisor，Codex 会话的接口由 Codex 决定。

- **V2** 使用 `fork_turns="none"`，由主模型在调用时提供模型、适用的推理档位和完整任务消息，然后等待顾问结果。
- **V1** 省略 `fork_context`，显式传入所选模型，等待结果后使用 V1 的 `close_agent`。

两套接口都由主模型提供审阅问题、目标、约束、已有决定和相关证据或文件路径。
以 `[CODEX_ADVISOR]` 开头的子代理只做只读审阅，也不会再派发顾问。
插件只在能识别明文顾问任务的 V1 调用中使用 Guard。V2 的任务可能是密文，接口偏好和模型参数由主模型在调用前检查和填写。

### 搭配 CC Switch

- **直连**跟随当前会话实际提供的接口。Advisor 可选择当前连接和 Codex 模型目录能访问的模型。
- **聚合跨供应商**在 CC Switch 保留默认开启的「聚合模式下子 agent 用经典工具」。Advisor 用自动或 V1，
  并选模型目录公布的完整 ID（必要时带 `ccs-…/…` 前缀）。V2 的跨供应商任务传递还受上游兼容性影响。
- **切换模式、经典工具或聚合目录**按 CC Switch 的提示彻底退出并重开 Codex Desktop，再新开对话验证。
  如果全局配置显式强制 V2，它可能覆盖经典工具设置。

详见 [CC Switch 聚合模式指南](https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/zh/4-proxy/4.6-aggregation.md)。

## 配置文件

Advisor 配置默认保存于：

```text
~/.codex/advisor/config.json
```

本插件支持通过 `CODEX_ADVISOR_STATE_DIR` 指定状态目录。配置网页只监听 localhost，并使用短期 token 保护当前配置会话。

## 开发与验证

```bash
python3 -m unittest discover -s tests -v
node --check assets/app.js
```

插件源码分为三部分：`hooks/` 负责 Codex 运行时注入和子代理角色保护，`scripts/` 负责配置、模型发现、
协议和本地服务，`assets/` 负责配置网页。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
