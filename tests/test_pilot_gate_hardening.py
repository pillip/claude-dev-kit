"""Tests for ISSUE-010: Pilot Gate hardening.

Each uiux template must declare the 4-substep pilot gate:
- Step 2.x.0 — Neutral observation (banned vocabulary in this step)
- Step 2.x.1 — Separate-context critique via Task → design-auditor
- Step 2.x.2 — Specificity check (3 product-specific details, literal_quote = 1)
- Step 2.x.3 — Auto-correction cycle with N=3 hard cap

The test parses the markdown — it does not run /uiux.
"""

from __future__ import annotations

import re
from pathlib import Path

UIUX_TMPL_PATHS = [
    Path("skills/uiux/SKILL.md.tmpl"),
    Path("skills/mobile-uiux/SKILL.md.tmpl"),
    Path("skills/desktop-uiux/SKILL.md.tmpl"),
]


def _read(path: Path) -> str:
    assert path.exists(), f"missing template: {path}"
    return path.read_text(encoding="utf-8")


class TestNeutralObservation:
    def test_neutral_observation_step_present(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert re.search(r"Neutral observation", text, re.IGNORECASE), (
                f"{tmpl} does not declare a 'Neutral observation' step."
            )

    def test_banned_vocabulary_enforced(self):
        """Every template must list banned vocabulary for the observation step."""
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            # Find the observation section and check it lists banned words.
            m = re.search(
                r"Neutral observation.*?(?=Separate-context critique|\Z)",
                text,
                re.DOTALL | re.IGNORECASE,
            )
            assert m, f"{tmpl}: no observation section body"
            section = m.group(0).lower()
            # Required forbidden vocabulary tokens — the writer must list these
            # so the model is told what NOT to use.
            for word in ["signature move", "aesthetic", "philosophy"]:
                assert word in section, (
                    f"{tmpl} observation section does not list banned word "
                    f"{word!r} — model may use the same vocabulary the "
                    f"generator used, defeating the observation purpose."
                )


class TestSeparateContextCritic:
    def test_design_auditor_invoked_via_task(self):
        """Each template must instruct invoking design-auditor via Task tool."""
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            # Must mention design-auditor + Task tool in the pilot gate region.
            assert re.search(
                r"design-auditor.*?Task tool|Task tool.*?design-auditor",
                text,
                re.DOTALL | re.IGNORECASE,
            ), (
                f"{tmpl} does not instruct invoking design-auditor via the Task tool."
            )

    def test_separate_context_explicitly_noted(self):
        """Each template must say 'separate context' or 'do not inline-critique'."""
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            has_separate = re.search(r"separate.context", text, re.IGNORECASE)
            has_no_inline = re.search(
                r"do NOT inline.critique|do not inline.critique",
                text,
                re.IGNORECASE,
            )
            assert has_separate or has_no_inline, (
                f"{tmpl} does not explicitly call out the separate-context "
                "requirement (or forbid inline critique). The whole point of "
                "ISSUE-010 is to break the generator-as-judge loop."
            )


class TestSpecificityCheck:
    def test_specificity_step_present(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert re.search(r"Specificity check", text, re.IGNORECASE), (
                f"{tmpl} does not declare a 'Specificity check' step."
            )

    def test_three_details_required(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            # Must demand 3 product-specific details.
            assert re.search(
                r"Name 3 details|3 product.specific details|fewer than 3.*FAIL",
                text,
                re.IGNORECASE,
            ), (
                f"{tmpl} specificity check does not demand exactly 3 details."
            )

    def test_literal_quote_counts_as_one(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            # Must clarify literal_quote contributes exactly 1.
            assert re.search(
                r"literal_quote.*?exactly\s+\*?\*?1\*?\*?|literal_quote.*?counts as.*?1",
                text,
                re.IGNORECASE | re.DOTALL,
            ), (
                f"{tmpl} does not clarify that literal_quote counts as exactly 1 "
                "of the 3 specificity details."
            )


class TestAutoCorrectionCycle:
    def test_cycle_step_present(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert re.search(r"Auto.correction cycle", text, re.IGNORECASE), (
                f"{tmpl} does not declare an 'Auto-correction cycle' step."
            )

    def test_hard_cap_three_cycles(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            # Must have N=3 hard cap to prevent runaway loops.
            assert re.search(
                r"hard cap N=3|hard cap.*N\s*=\s*3|Hard stop at N=3",
                text,
                re.IGNORECASE,
            ), (
                f"{tmpl} auto-correction cycle does not declare an N=3 hard cap "
                "(runaway loop risk)."
            )

    def test_cycles_log_documented(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert "cycles.log" in text or "cycles\\.log" in text, (
                f"{tmpl} does not document the cycles.log artifact that "
                "records what each cycle changed."
            )


class TestDegradedMode:
    def test_degraded_mode_documented(self):
        """When the screenshot backend (or equivalent) is unavailable,
        the gate must enter degraded mode — NOT silently skip."""
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert "pilot_degraded" in text or "degraded mode" in text.lower(), (
                f"{tmpl} does not declare a degraded-mode behavior; the gate "
                "might silently skip critique when the backend is missing."
            )

    def test_no_silent_skip_of_critique(self):
        """Each template must explicitly forbid silent skip in the gate region."""
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert re.search(
                r"DO NOT silently skip|do not silently skip",
                text,
                re.IGNORECASE,
            ) or re.search(
                r"DO NOT\s+(?:inline-|inline\s+)?critique",
                text,
                re.IGNORECASE,
            ), (
                f"{tmpl} does not explicitly forbid silently skipping the critique."
            )


class TestUserGateUsesArtifacts:
    """Step 3 (user gate) must surface the critique + cycles.log artifacts."""

    def test_user_gate_shares_critique(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            assert "critique.md" in text, (
                f"{tmpl} user gate does not share the critique.md artifact."
            )

    def test_user_gate_includes_specificity_question(self):
        for tmpl in UIUX_TMPL_PATHS:
            text = _read(tmpl)
            # Must include a user-facing question about the 3 product-specific details.
            assert re.search(
                r"3 product.specific details",
                text,
                re.IGNORECASE,
            ), (
                f"{tmpl} user gate does not ask about the 3 product-specific "
                "details from the specificity check."
            )
