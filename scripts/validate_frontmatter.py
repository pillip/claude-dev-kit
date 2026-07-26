#!/usr/bin/env python3
"""Strict frontmatter validator for skills + agents (release gate).

Catches the class of bug `claude plugin tag` surfaced but the regular test
suite and `claude plugin validate` missed: a SKILL.md/agent .md whose YAML
frontmatter fails to parse (unquoted `argument-hint: [a] [b]`, a description
with a `: ` colon-space, etc.) loads at runtime with ALL frontmatter fields
silently dropped — no name, no description, no allowed-tools.

Runs in CI without depending on the `claude` CLI. Uses PyYAML when present
(CI installs it) for a real parse; always applies the plain-string pattern
checks so it's meaningful even where PyYAML is absent.

Exit 0 = all clean; exit 1 = at least one file has invalid frontmatter.

Usage: python3 scripts/validate_frontmatter.py
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = (
    sorted(glob.glob(str(ROOT / "skills/*/SKILL.md")))
    + sorted(glob.glob(str(ROOT / "packs/*/skills/*/SKILL.md")))
    + sorted(glob.glob(str(ROOT / "agents/*.md")))
    + sorted(glob.glob(str(ROOT / "packs/*/agents/*.md")))
)

SCALAR_KEYS = {"name", "description", "argument-hint"}


def _frontmatter(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else None


def _quoted(v: str) -> bool:
    v = v.strip()
    return (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"'))


def _pattern_errors(block: str) -> list[str]:
    errs = []
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key not in SCALAR_KEYS or _quoted(value):
            continue
        if value.startswith("[") and not (value.endswith("]") and value.count("[") == 1):
            errs.append(f"unquoted flow-sequence {key}: {value!r} (quote it)")
        if ": " in value:
            errs.append(f"unquoted {key} contains ': ' (YAML reads it as a mapping — quote it)")
    return errs


def main() -> int:
    try:
        import yaml  # noqa: F401
        have_yaml = True
    except ImportError:
        have_yaml = False

    failures: list[str] = []
    for f in FILES:
        p = Path(f)
        block = _frontmatter(p)
        rel = p.relative_to(ROOT)
        if block is None:
            failures.append(f"{rel}: no frontmatter block at byte 0")
            continue
        for e in _pattern_errors(block):
            failures.append(f"{rel}: {e}")
        if have_yaml:
            import yaml
            try:
                data = yaml.safe_load(block)
            except yaml.YAMLError as exc:
                failures.append(f"{rel}: YAML parse error — {str(exc).splitlines()[0]}")
                continue
            if not isinstance(data, dict):
                failures.append(f"{rel}: frontmatter did not parse to a mapping")
                continue
            for key in ("name", "description"):
                if key not in data:
                    failures.append(f"{rel}: frontmatter dropped required key {key!r}")

    if failures:
        print("Frontmatter validation FAILED:", file=sys.stderr)
        for msg in failures:
            print(f"  ✘ {msg}", file=sys.stderr)
        return 1
    print(f"Frontmatter OK — {len(FILES)} skill/agent files parse cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
