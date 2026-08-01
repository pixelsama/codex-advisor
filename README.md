# Codex Advisor

Codex Advisor adds an optional strategic-review workflow to Codex subagents.
It reads the live `subagentModels` roster, lets you choose an ordered Advisor
chain with per-model retries, and injects a bounded consultation protocol into
Codex.

## Features

- Automatic or manual Advisor mode
- Ordered model priority with fallback
- Configurable extra retries per model
- Live model discovery from OpenCodex, with a Codex model-list fallback
- Full-context Advisor forks (`fork_context=true`)
- A leaf-role prompt guard that prevents recursive Advisor creation
- Small localhost-only configuration UI with explicit save feedback

## Requirements

- Codex with subagent support enabled
- Python 3.10+
- Optional: OpenCodex for live `subagentModels` discovery

## Install in Codex

The following steps use Codex's default personal marketplace. They work on
macOS, Linux, and Windows through Git Bash or WSL. Keep the clone at
`~/plugins/codex-advisor`: the marketplace entry below intentionally refers to
that standard location.

### 1. Clone the plugin

```bash
mkdir -p ~/plugins
git clone https://github.com/pixelsama/codex-advisor.git ~/plugins/codex-advisor
```

If you already cloned it, update it instead:

```bash
git -C ~/plugins/codex-advisor pull --ff-only
```

### 2. Register it in your personal marketplace

#### 推荐：自动注册

This command creates the personal marketplace if needed and updates only the
`codex-advisor` entry. Existing plugin entries are preserved:

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

#### 手动注册

If you prefer to edit the file yourself, add the following object to its
`plugins` array. Do not delete your existing plugin entries:

```json
{
  "name": "codex-advisor",
  "source": { "source": "local", "path": "./plugins/codex-advisor" },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

For a new personal marketplace, create
`~/.agents/plugins/marketplace.json` with this complete content:

```json
{
  "name": "personal",
  "interface": { "displayName": "Personal" },
  "plugins": [
    {
      "name": "codex-advisor",
      "source": { "source": "local", "path": "./plugins/codex-advisor" },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

### 3. Install and verify it

```bash
codex plugin add codex-advisor@personal
codex plugin list | grep codex-advisor
```

The plugin should show as `installed, enabled`. Start a new Codex task after
installing or updating so it loads the current plugin version.

### 4. Configure Advisor

```bash
codex-advisor open
```

The command opens the local settings page. Select the Advisor mode and model
priority, then click **保存配置** in the top-right action area. The page shows
a confirmation banner after the configuration is written.

When developing locally, reinstall after source changes so Codex picks up the
new plugin cache version.

## Configure

```bash
codex-advisor open
```

The page reads the current subagent model list and provides:

- `自动：关键节点咨询` — the parent model may consult at consequential checkpoints
- `手动：只在 $advisor ask 时咨询` — no automatic consultation
- model priority, retry count, reasoning effort, and exhausted-chain behavior

Configuration is stored at `~/.codex/advisor/config.json`. The configuration
server binds to localhost and uses a short-lived session token.

## Usage

In manual mode, ask the parent model for a review with `$advisor ask` or an
equivalent explicit request. In automatic mode, the injected protocol allows
consultation before major decisions, after repeated blockers, or before a
substantial handoff.

Advisor children are instructed to use the inherited context for a read-only
review and must not create another Advisor.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 /path/to/codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

The plugin is intentionally small: the runtime integration lives in
`hooks/`, the local UI in `assets/`, and the configuration/orchestration logic
in `scripts/`.

## License

MIT. See [LICENSE](LICENSE).
