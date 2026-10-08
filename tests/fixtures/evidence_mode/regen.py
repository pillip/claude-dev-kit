#!/usr/bin/env python3
"""Regenerate the ISSUE-061 golden section fixtures.

Usage (from the kit root):
    uv run --extra dev python3 tests/fixtures/evidence_mode/regen.py

For each merged domain this captures the markdown headings found inside the
first fenced code block after the `## Output Structure` heading:

- `<stem>_greenfield_sections.txt` — from `agents/<stem>.md` (regenerable
  at any time; the greenfield template is unchanged by SPEC-061).
- `<stem>_evidence_sections.txt` — from the scan twin `agents/scan-*.md`.
  The twins are DELETED by the ISSUE-061 merge, so these fixtures were
  captured pre-merge and are FROZEN afterwards: when a twin file no longer
  exists the script leaves its fixture untouched.

Extraction logic is imported from tests/test_evidence_mode_consolidation.py
so the fixtures and the assertions share one parser (review lesson:
hand-rolled parsers mirroring an oracle must match edge cases — fence
guards included).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS_DIR = HERE.parents[1]
KIT_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(TESTS_DIR))

from test_evidence_mode_consolidation import (  # noqa: E402
    DOMAINS,
    GREENFIELD_OUTPUT_HEADING,
    headings_in_output_structure_fence,
    split_evidence_mode_section,
)


def _write(path: Path, headings: list) -> None:
    path.write_text("\n".join(headings) + "\n", encoding="utf-8")
    print(f"  wrote {path.name} ({len(headings)} headings)")


def main() -> None:
    agents = KIT_ROOT / "agents"
    for stem, twin in DOMAINS:
        greenfield_text = (agents / f"{stem}.md").read_text(encoding="utf-8")
        # Strip any Evidence Mode section so only the greenfield template
        # fence is considered (no-op pre-merge).
        _, outside = split_evidence_mode_section(greenfield_text)
        _write(
            HERE / f"{stem}_greenfield_sections.txt",
            headings_in_output_structure_fence(outside, GREENFIELD_OUTPUT_HEADING),
        )

        twin_path = agents / f"{twin}.md"
        if twin_path.exists():
            _write(
                HERE / f"{stem}_evidence_sections.txt",
                headings_in_output_structure_fence(
                    twin_path.read_text(encoding="utf-8"),
                    GREENFIELD_OUTPUT_HEADING,
                ),
            )
        else:
            print(
                f"  frozen: {stem}_evidence_sections.txt "
                f"(twin {twin}.md retired — pre-merge capture kept)"
            )


if __name__ == "__main__":
    main()
