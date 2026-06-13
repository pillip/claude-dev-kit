"""Tests for ISSUE-013: design-auditor / ui-reviewer scope disjointness.

These tests verify the *declared* scope of the two agents is disjoint at the
file level. They do NOT run the agents; they parse the markdown.

What is verified:
1. Both files contain a mirrored "Scope" table that lists the same 12
   categories, with each row owned by exactly one agent.
2. Each file references the other by name (so a reader of either file knows
   where the other categories live).
3. Each agent's checklist explicitly EXCLUDES the categories owned by the
   other (so contributors don't drift back into overlap).
4. The `design-auditor` name is preserved (ISSUE-010's Pilot Gate will wire
   to this exact name).
"""

from __future__ import annotations

import re
from pathlib import Path

DESIGN_AUDITOR = Path("agents/design-auditor.md")
UI_REVIEWER = Path("agents/ui-reviewer.md")


def _read(path: Path) -> str:
    assert path.exists(), f"missing agent file: {path}"
    return path.read_text(encoding="utf-8")


def _parse_scope_table(text: str) -> dict[str, tuple[str, str]]:
    """Find the markdown scope table and return {category: (own_col, other_col)}.

    Looks for the table header `| Category | Owned by ... | Owned by ... |`
    and parses the body rows.
    """
    lines = text.splitlines()
    table_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("| Category | Owned by"):
            table_start = i
            break
    assert table_start is not None, "scope table not found"

    rows: dict[str, tuple[str, str]] = {}
    # Skip header + separator
    for line in lines[table_start + 2 :]:
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3:
            continue
        category = cells[0]
        rows[category] = (cells[1], cells[2])
    return rows


class TestScopeTables:
    def test_design_auditor_has_scope_table(self):
        rows = _parse_scope_table(_read(DESIGN_AUDITOR))
        assert len(rows) >= 12, (
            f"design-auditor scope table has only {len(rows)} rows; expected ≥12"
        )

    def test_ui_reviewer_has_scope_table(self):
        rows = _parse_scope_table(_read(UI_REVIEWER))
        assert len(rows) >= 12, (
            f"ui-reviewer scope table has only {len(rows)} rows; expected ≥12"
        )

    def test_categories_match_across_files(self):
        """Both files list the same 12 categories with mirrored ownership.

        Ownership is mirrored: a row owned by design-auditor in file A must be
        owned by design-auditor in file B (the partition is identical from
        either reader's perspective).
        """
        a_rows = _parse_scope_table(_read(DESIGN_AUDITOR))
        b_rows = _parse_scope_table(_read(UI_REVIEWER))
        assert set(a_rows.keys()) == set(b_rows.keys()), (
            f"category lists differ\n"
            f"design-auditor only: {set(a_rows) - set(b_rows)}\n"
            f"ui-reviewer only:    {set(b_rows) - set(a_rows)}"
        )

    def test_each_category_owned_by_exactly_one_agent(self):
        """For each category, exactly one column has a ✓ and the other a — / dash."""
        a_rows = _parse_scope_table(_read(DESIGN_AUDITOR))
        offenders: list[str] = []
        for category, (own, other) in a_rows.items():
            own_has_check = "✓" in own
            other_has_check = "✓" in other
            if own_has_check == other_has_check:
                # Either both checked or neither — bad.
                offenders.append(
                    f"  {category!r}: own={own!r} other={other!r}"
                )
        assert not offenders, (
            "design-auditor scope table has rows owned by both or neither:\n"
            + "\n".join(offenders)
        )

    def test_ui_reviewer_partition_matches_design_auditor(self):
        a_rows = _parse_scope_table(_read(DESIGN_AUDITOR))
        b_rows = _parse_scope_table(_read(UI_REVIEWER))
        # In ui-reviewer's table the first column is "owned by ui-reviewer".
        # In design-auditor's table the first column is "owned by design-auditor".
        # Each category should have its ✓ in opposite-column-headers.
        mismatches: list[str] = []
        for category in a_rows:
            a_own_check = "✓" in a_rows[category][0]
            b_own_check = "✓" in b_rows[category][0]
            # Both columns "Owned by <self>" — for any category exactly one
            # of these self-columns should have a check.
            if a_own_check == b_own_check:
                mismatches.append(
                    f"  {category!r}: "
                    f"design-auditor self-col={a_rows[category][0]!r}, "
                    f"ui-reviewer self-col={b_rows[category][0]!r}"
                )
        assert not mismatches, (
            "category ownership is not mirrored between the two files:\n"
            + "\n".join(mismatches)
        )


class TestCrossReferences:
    def test_design_auditor_mentions_ui_reviewer(self):
        text = _read(DESIGN_AUDITOR)
        assert "ui-reviewer" in text, (
            "design-auditor.md does not mention ui-reviewer by name; "
            "readers cannot find where the other categories live."
        )

    def test_ui_reviewer_mentions_design_auditor(self):
        text = _read(UI_REVIEWER)
        assert "design-auditor" in text, (
            "ui-reviewer.md does not mention design-auditor by name; "
            "readers cannot find where the other categories live."
        )


class TestExclusionLines:
    def test_design_auditor_explicitly_excludes_impl(self):
        text = _read(DESIGN_AUDITOR)
        # The skill file must instruct the agent NOT to audit prototype files.
        assert re.search(r"do NOT\s+scan\s+prototypes?", text, re.IGNORECASE), (
            "design-auditor.md does not explicitly forbid scanning prototype files."
        )

    def test_ui_reviewer_explicitly_excludes_system(self):
        text = _read(UI_REVIEWER)
        # The skill file must instruct the agent NOT to critique the system.
        assert re.search(r"do NOT\s+(?:critique|evaluate)\s+(?:the\s+)?(?:design\s+)?system", text, re.IGNORECASE), (
            "ui-reviewer.md does not explicitly forbid critiquing the design system."
        )


class TestAgentNamesPreserved:
    """ISSUE-010 wires Pilot Gate to the literal `design-auditor` agent name.
    This test guards against renames during the consolidation."""

    def test_design_auditor_name_preserved(self):
        text = _read(DESIGN_AUDITOR)
        m = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        assert m and m.group(1) == "design-auditor", (
            "design-auditor agent name has changed — ISSUE-010 Pilot Gate "
            "wiring will break."
        )

    def test_ui_reviewer_name_preserved(self):
        text = _read(UI_REVIEWER)
        m = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        assert m and m.group(1) == "ui-reviewer", (
            "ui-reviewer agent name has changed."
        )
