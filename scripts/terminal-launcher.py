#!/usr/bin/env python3
"""Resolve the installed Advisor release for the Windows terminal command."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


def resolve_advisor_script(codex_directory: Path) -> Path | None:
    cache = codex_directory / "plugins" / "cache" / "advisor-market" / "codex-advisor"
    try:
        releases = sorted(
            (path for path in cache.iterdir() if VERSION.fullmatch(path.name) and path.is_dir()),
            key=lambda path: tuple(int(part) for part in path.name.split(".")),
            reverse=True,
        )
    except OSError:
        return None

    for release in releases:
        script = release / "scripts" / "advisorctl.py"
        manifest = release / ".codex-plugin" / "plugin.json"
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if (
            isinstance(metadata, dict)
            and metadata.get("name") == "codex-advisor"
            and metadata.get("version") == release.name
            and script.is_file()
        ):
            return script
    return None


def main() -> int:
    codex_directory = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    script = resolve_advisor_script(codex_directory)
    if script is None:
        print("Codex Advisor is missing. Install codex-advisor@advisor-market in Codex.", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, "-X", "utf8", str(script), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
