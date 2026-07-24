#!/usr/bin/env python3
"""Best-effort probe for whether a Claude Code skill is exposed at runtime.

Used by /brainstorm and /bizanalysis (and later /review per ISSUE-019) to
decide between the platform-first path (delegate to a runtime skill like
/deep-research) and a kit-internal degraded path.

Exit codes:
    0 = skill is filesystem-visible (installed plugin or local skill dir)
    1 = skill is NOT filesystem-visible (definitive miss)
    2 = unknown — runtime-built-in skills (e.g. /deep-research, /code-review,
        /security-review) leave no filesystem trace. Caller should attempt
        the primary path inline and degrade on failure.

Caveats: this script CANNOT confirm a runtime-built-in skill is exposed,
only that it is filesystem-installed somewhere it can be checked. For
runtime-built-ins, exit code 2 means "ask the runtime, not me." The skill
template owns that fallback decision per SPEC-018 / SPEC-019.

Usage:
    python3 scripts/has_skill.py deep-research   # exit 0/1/2
    python3 scripts/has_skill.py deep-research --verbose
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Runtime-built-in skills the kit knows about. Filesystem-invisible by design.
# Listed here so the probe returns "unknown" (2) rather than "missing" (1),
# which downstream skill templates use to attempt the primary path inline.
RUNTIME_BUILTIN_SKILLS: set[str] = {
    "deep-research",
    "code-review",
    "security-review",
    "verify",
    "run",
    "init",
    "loop",
    "schedule",
    "simplify",
    "fewer-permission-prompts",
    "update-config",
    "claude-api",
    "keybindings-help",
}


def user_skills_dir() -> Path:
    return Path(os.path.expanduser("~/.claude/skills"))


def project_skills_dir() -> Path:
    # Standalone project skill layout (a plugin install resolves via the
    # plugin cache paths below instead).
    return Path.cwd() / ".claude" / "skills"


def plugin_install_paths() -> list[Path]:
    """Return install paths from ~/.claude/plugins/installed_plugins.json."""
    manifest = Path(os.path.expanduser("~/.claude/plugins/installed_plugins.json"))
    if not manifest.is_file():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    paths: list[Path] = []
    for entries in (data.get("plugins") or {}).values():
        for entry in entries or []:
            install = entry.get("installPath")
            if install:
                paths.append(Path(install))
    return paths


def find_skill(name: str) -> tuple[int, str]:
    """Return (exit_code, evidence)."""
    candidates: list[Path] = [
        user_skills_dir() / name / "SKILL.md",
        project_skills_dir() / name / "SKILL.md",
    ]
    for plugin_root in plugin_install_paths():
        candidates.append(plugin_root / "skills" / name / "SKILL.md")
        candidates.append(plugin_root / name / "SKILL.md")

    for path in candidates:
        if path.is_file():
            return 0, f"found at {path}"

    if name in RUNTIME_BUILTIN_SKILLS:
        return 2, (
            f"'{name}' is a known runtime-built-in skill — filesystem-invisible "
            "by design. Caller should attempt the primary path inline."
        )

    return 1, (
        f"'{name}' not found in user / project / plugin skill dirs and is "
        "not in the runtime-built-in allowlist."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe whether a Claude Code skill is exposed."
    )
    parser.add_argument("name", help="Skill name without leading slash (e.g. deep-research)")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print the evidence string."
    )
    args = parser.parse_args()

    name = args.name.lstrip("/")
    code, evidence = find_skill(name)
    if args.verbose:
        print(evidence)
    return code


if __name__ == "__main__":
    sys.exit(main())
