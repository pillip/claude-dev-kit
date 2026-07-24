#!/usr/bin/env python3
"""Lint that {{PREAMBLE}} appears immediately after frontmatter in skill templates.

Cache-friendly authoring rule: stable content first, dynamic content last.
{{PREAMBLE}} expands to the kit's tiered boilerplate (preambles.py). Placing
it anywhere later interleaves dynamic skill-specific content before the
stable prefix, which prevents the prompt cache from keying on the same
prefix across the multi-turn execution of a single skill invocation.

Rule: the first non-blank, non-comment line after the closing `---` of the
frontmatter must be exactly `{{PREAMBLE}}`.

Usage:
    python3 scripts/lint_skill_cache_order.py            # check all
    python3 scripts/lint_skill_cache_order.py --skill X  # check one

Exits 0 on success, 1 on lint failure, 2 on usage error.

See docs/cache_friendly_authoring.md for the rationale.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "scripts"))
from gen_skills import discover_templates  # noqa: E402

PREAMBLE_TOKEN = "{{PREAMBLE}}"
RULE_DOC = "docs/cache_friendly_authoring.md"


def check_template(tmpl_path: Path) -> tuple[bool, str]:
    """Return (ok, message). ok=False carries a diagnostic on failure."""
    text = tmpl_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        return False, (
            f"{tmpl_path}: missing opening `---` frontmatter delimiter "
            f"(cache-friendly authoring rule — see {RULE_DOC})"
        )

    close_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close_idx = i
            break
    if close_idx is None:
        return False, (
            f"{tmpl_path}: missing closing `---` frontmatter delimiter "
            f"(cache-friendly authoring rule — see {RULE_DOC})"
        )

    for i in range(close_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--"):
            continue
        if stripped == PREAMBLE_TOKEN:
            return True, ""
        snippet = line.rstrip()[:60]
        return False, (
            f"{tmpl_path}:{i + 1}: first non-frontmatter content line is "
            f"`{snippet}` but must be `{PREAMBLE_TOKEN}` "
            f"(cache-friendly authoring rule — see {RULE_DOC})"
        )

    return False, (
        f"{tmpl_path}: no content after frontmatter — missing "
        f"`{PREAMBLE_TOKEN}` (cache-friendly authoring rule — see {RULE_DOC})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint {{PREAMBLE}} placement in skill templates."
    )
    parser.add_argument(
        "--skill",
        help="Check a single skill by name (e.g. --skill review).",
        default=None,
    )
    args = parser.parse_args()

    templates = discover_templates()
    if args.skill:
        templates = [t for t in templates if t.parent.name == args.skill]
        if not templates:
            print(
                f"No SKILL.md.tmpl found for skill '{args.skill}'.",
                file=sys.stderr,
            )
            return 2

    failures: list[str] = []
    for tmpl in templates:
        ok, msg = check_template(tmpl)
        if not ok:
            failures.append(msg)

    if failures:
        print("Cache-order lint failures:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print(f"All {len(templates)} skill templates pass cache-order lint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
