#!/usr/bin/env python3
"""Harvest KIT-DEBT markers into a tracked ledger.

A KIT-DEBT marker records an *intentionally deferred* simplification so it
becomes an explicit, tracked obligation rather than silent rot. Convention:

    # KIT-DEBT(ceiling=<constraint that holds today>, trigger=<condition to revisit>): <what was simplified>
    // KIT-DEBT(ceiling=..., trigger=...): ...

This script greps the tree (excluding VCS/venv/build dirs), parses every
marker, and prints a ledger. Markers missing a `trigger=` are flagged
`no-trigger` — they are the silent-rot risk ("later means never"). Markers
that can't be parsed into the param form are flagged `malformed` (the script
never crashes on them).

Exit codes:
    0  ran successfully (clean tree OR debt found — this is a ledger, not a gate)
    2  usage error (e.g. path does not exist)

Usage:
    python3 scripts/debt_harvest.py                 # scan repo root
    python3 scripts/debt_harvest.py --path some/dir  # scan a subtree
    python3 scripts/debt_harvest.py --json           # machine-readable ledger
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MARKER_TOKEN = "KIT-DEBT"

# Directories never worth scanning. Pruned in-place during the walk.
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".tox", ".idea", ".vscode",
    "figma-export", ".claude-kit",
}

# `# KIT-DEBT(...)?: description` or `// KIT-DEBT(...)?: description`.
# The params group and the leading colon are both optional so malformed
# markers are still captured (and then classified as malformed/no-trigger).
_MARKER_RE = re.compile(
    r"(?:#|//)\s*" + re.escape(MARKER_TOKEN) + r"\b\s*(?:\(([^)]*)\))?\s*:?\s*(.*)$"
)
_CEILING_RE = re.compile(r"ceiling\s*=\s*([^,]+?)\s*(?:,|$)")
_TRIGGER_RE = re.compile(r"trigger\s*=\s*([^,]+?)\s*(?:,|$)")


def _classify(params: str | None, trigger: str | None) -> str:
    """Return the marker status: ok | no-trigger | malformed."""
    if params is None:
        # No parens at all — can't carry a ceiling or trigger.
        return "malformed"
    if trigger is None:
        return "no-trigger"
    return "ok"


def parse_line(line: str) -> dict | None:
    """Parse a single source line into a marker dict, or None if no marker."""
    if MARKER_TOKEN not in line:
        return None
    m = _MARKER_RE.search(line)
    if not m:
        # Token appears only as prose / a string literal, not in `#`/`//`
        # comment form (e.g. this script's own source). Not a debt marker.
        return None
    params, desc = m.group(1), m.group(2).strip()
    ceiling = trigger = None
    if params is not None:
        cm = _CEILING_RE.search(params)
        tm = _TRIGGER_RE.search(params)
        ceiling = cm.group(1).strip() if cm else None
        trigger = tm.group(1).strip() if tm else None
    return {
        "params": params,
        "ceiling": ceiling,
        "trigger": trigger,
        "description": desc,
        "status": _classify(params, trigger),
    }


def harvest(root: Path) -> list[dict]:
    """Walk `root` and collect every KIT-DEBT marker with its location."""
    entries: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            fpath = Path(dirpath) / name
            try:
                text = fpath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable — skip silently
            if MARKER_TOKEN not in text:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                marker = parse_line(line)
                if marker is None:
                    continue
                marker["file"] = str(fpath.relative_to(root))
                marker["line"] = lineno
                entries.append(marker)
    entries.sort(key=lambda e: (e["file"], e["line"]))
    return entries


def render_text(entries: list[dict]) -> str:
    """Render the human-readable ledger."""
    if not entries:
        return "No KIT-DEBT. Clean ledger."

    lines: list[str] = ["KIT-DEBT ledger", "=" * 60]
    for e in entries:
        flag = "" if e["status"] == "ok" else f"  [{e['status'].upper()}]"
        lines.append(f"{e['file']}:{e['line']}{flag}")
        lines.append(f"    simplification: {e['description'] or '—'}")
        lines.append(f"    ceiling:        {e['ceiling'] or '—'}")
        lines.append(f"    trigger:        {e['trigger'] or '—'}")
    no_trigger = sum(1 for e in entries if e["status"] == "no-trigger")
    malformed = sum(1 for e in entries if e["status"] == "malformed")
    lines.append("-" * 60)
    lines.append(
        f"total: {len(entries)}  |  no-trigger (silent-rot risk): {no_trigger}"
        f"  |  malformed: {malformed}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harvest KIT-DEBT markers into a ledger.")
    parser.add_argument(
        "--path", default=".", help="Root directory to scan (default: current dir)."
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit the ledger as JSON."
    )
    args = parser.parse_args(argv)

    root = Path(args.path)
    if not root.exists():
        print(f"ERROR: path does not exist: {root}", file=sys.stderr)
        return 2

    entries = harvest(root)

    if args.json:
        no_trigger = sum(1 for e in entries if e["status"] == "no-trigger")
        malformed = sum(1 for e in entries if e["status"] == "malformed")
        payload = {
            "total": len(entries),
            "no_trigger": no_trigger,
            "malformed": malformed,
            "entries": entries,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render_text(entries))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
