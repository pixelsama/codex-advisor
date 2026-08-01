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

## Install as a local Codex plugin

Clone this repository into a local plugin directory, then add the plugin to
your personal Codex marketplace entry:

```bash
git clone https://github.com/pixelsama/codex-advisor.git ~/plugins/codex-advisor
```

The marketplace entry should point to the cloned directory:

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

Then install it from the marketplace:

```bash
codex plugin add codex-advisor@personal
```

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
