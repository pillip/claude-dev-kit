"""Tests for ISSUE-012: Reference Anchor tuning (2-3 cues + 1 literal quote).

These tests verify the three uiux skill templates declare:
- "2–3 strong cues" (not "5 specific visual cues")
- A `literal_quote:` field is mandated when Phase 1.5 is not skipped
- The Phase 5.x prototype-verification phase grep-checks for the literal
  quote verbatim in rendered output
- The Phase 2 CHECKPOINT requires the literal_quote field

The tests parse the markdown — they do NOT run /uiux.

Since ISSUE-041 the design-interview and Phase 2 checkpoint boilerplate is
injected via the {{DESIGN_PHILOSOPHY}} / {{DESIGN_PHILOSOPHY_CHECKPOINT}}
tokens (scripts/fragments.py), so the contract is asserted against the
RESOLVED template content — what /uiux actually reads — not the raw tmpl.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gen_skills import process_template  # noqa: E402

UIUX_TMPL_PATHS = [
    ROOT / "skills/uiux/SKILL.md.tmpl",
    ROOT / "skills/mobile-uiux/SKILL.md.tmpl",
    ROOT / "skills/desktop-uiux/SKILL.md.tmpl",
]


def _read(path: Path) -> str:
    assert path.exists(), f"missing template: {path}"
    return process_template(path)


class TestCueCountReduced:
    """Every uiux template declares 2–3 adopted cues, not the old 5."""

    def test_no_old_five_cue_phrasing(self):
        offenders: list[tuple[str, int, str]] = []
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            for line_no, line in enumerate(text.splitlines(), 1):
                # The OLD shape was "5 specific visual cues to adopt" /
                # "5 adopted cues". Any line that still uses the count "5"
                # in the context of "cues to adopt" is a regression.
                if re.search(r"\b5\s+(?:specific\s+visual\s+)?cues?\s+to\s+adopt", line, re.IGNORECASE):
                    offenders.append((str(tmpl), line_no, line.strip()))
                if re.search(r"\b5\s+adopted\s+cues?\b", line, re.IGNORECASE):
                    offenders.append((str(tmpl), line_no, line.strip()))
        assert not offenders, (
            "Old 5-cue phrasing resurfaced (ISSUE-012 reduced to 2–3):\n"
            + "\n".join(f"  {p}:{n}: {ln}" for p, n, ln in offenders)
        )

    def test_two_to_three_phrasing_present(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert re.search(r"\b2[–\-]3\s+strong\s+(?:adopted\s+)?cues?", text), (
                f"{tmpl} does not declare 2–3 strong adopted cues."
            )


class TestLiteralQuoteMandate:
    """Every uiux template introduces the literal_quote field and its render check."""

    def test_literal_quote_field_introduced(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert "literal_quote:" in text, (
                f"{tmpl} does not mention `literal_quote:` field."
            )
            assert "verbatim" in text.lower(), (
                f"{tmpl} does not mention verbatim rendering of the literal quote."
            )

    def test_phase_2_checkpoint_requires_literal_quote(self):
        """The Phase 2 CHECKPOINT block must require the literal_quote field."""
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            # Find the Phase 2 CHECKPOINT block (the one near the end of Phase 2).
            # It is the block that mentions design_philosophy.md.
            checkpoint_blocks = re.findall(
                r"^> \*\*CHECKPOINT.*?(?=\n###|\n\Z)",
                text,
                re.MULTILINE | re.DOTALL,
            )
            phase2_checkpoint = None
            for block in checkpoint_blocks:
                if "design_philosophy.md" in block:
                    phase2_checkpoint = block
                    break
            assert phase2_checkpoint is not None, (
                f"{tmpl}: no Phase 2 CHECKPOINT mentioning design_philosophy.md found."
            )
            assert "literal_quote" in phase2_checkpoint, (
                f"{tmpl} Phase 2 CHECKPOINT does not require literal_quote:\n"
                f"{phase2_checkpoint[:300]}..."
            )
            assert re.search(r"2[–\-]3", phase2_checkpoint), (
                f"{tmpl} Phase 2 CHECKPOINT does not enforce 2–3 cues:\n"
                f"{phase2_checkpoint[:300]}..."
            )

    def test_phase_5_verbatim_render_check_present(self):
        """Phase 5.x has a step that grep-checks for the literal_quote verbatim."""
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert re.search(
                r"Literal quote verbatim render check",
                text,
                re.IGNORECASE,
            ), (
                f"{tmpl} does not declare a 'Literal quote verbatim render check' "
                "step in Phase 5.x."
            )

    def test_literal_quote_rejects_abstract_words(self):
        """Each template tells the model to reject abstract concepts as the quote."""
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            # The instruction should explicitly call out adjectives/concepts
            # like "luxury" or "trust" as invalid.
            assert "luxury" in text.lower() or "trust" in text.lower(), (
                f"{tmpl} does not exemplify rejected abstract quotes "
                "(literal_quote must be concrete text/digits/glyphs)."
            )
