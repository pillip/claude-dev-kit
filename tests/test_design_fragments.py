"""ISSUE-041: canonical UI/UX design-philosophy fragment.

Six near-identical boilerplate copies (3 skill tmpls + 3 developer agents)
are deduplicated into scripts/fragments.py:

- The three uiux tmpls consume the design-interview block via the
  {{DESIGN_PHILOSOPHY}} token and the Phase-2 philosophy checkpoint via
  {{DESIGN_PHILOSOPHY_CHECKPOINT}}, resolved per-skill by gen_skills.py
  (same mechanism as {{PREAMBLE}}/preambles.py).
- The three agent files are static (not generated); they must contain the
  canonical AGENT_DESIGN_FRAGMENTS chunks verbatim (whitespace-normalized).
  Editing a canonical chunk without syncing the agents makes the drift
  guard fail, naming the out-of-sync agent file (TC-041c).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from fragments import (  # noqa: E402
    AGENT_DESIGN_FRAGMENTS,
    UIUX_AGENT_FILES,
    UIUX_SKILLS,
    design_philosophy_checkpoint,
    design_philosophy_fragment,
    find_out_of_sync_fragments,
)
from gen_skills import RESOLVERS  # noqa: E402

# Sentinel lines that exist ONLY inside the canonical fragment content.
# If any of these appears inline in a tmpl, the extraction regressed.
INTERVIEW_SENTINEL = (
    'Also tell the user: "If any of these are hard to answer right now'
)
CASE_B_SENTINEL = "**Case B — User skips the entire interview**"
CHECKPOINT_SENTINEL = (
    "(a) a **Signature Move** that is numeric/token-specific (not prose-only);"
)


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _tmpl_path(skill: str) -> Path:
    return ROOT / "skills" / skill / "SKILL.md.tmpl"


def _generated_path(skill: str) -> Path:
    return ROOT / "skills" / skill / "SKILL.md"


class TestSkillFragmentResolvers:
    """TC-041a: fragment resolvers exist and resolve per-skill."""

    def test_uiux_skills_roster(self):
        assert UIUX_SKILLS == ("uiux", "mobile-uiux", "desktop-uiux")

    def test_tokens_registered_in_gen_skills(self):
        assert "DESIGN_PHILOSOPHY" in RESOLVERS
        assert "DESIGN_PHILOSOPHY_CHECKPOINT" in RESOLVERS
        assert RESOLVERS["DESIGN_PHILOSOPHY"] is design_philosophy_fragment
        assert (
            RESOLVERS["DESIGN_PHILOSOPHY_CHECKPOINT"]
            is design_philosophy_checkpoint
        )

    @pytest.mark.parametrize("skill", ["uiux", "mobile-uiux", "desktop-uiux"])
    def test_fragment_contains_shared_core(self, skill):
        frag = design_philosophy_fragment(skill)
        for marker in (
            "a) **Brand Personality**",
            "b) **Emotional Target**",
            "c) **Anti-Reference**",
            "d) **Aspiration Reference**",
            "**Case A — User answers (partially or fully)**",
            CASE_B_SENTINEL,
            "Do NOT silently proceed with generic defaults.",
            INTERVIEW_SENTINEL,
        ):
            assert marker in frag, f"{skill}: fragment missing {marker!r}"

    def test_desktop_interview_deltas_only_in_desktop(self):
        desktop = design_philosophy_fragment("desktop-uiux")
        assert "e) **Desktop Identity**" in desktop
        assert "e) Desktop Identity → infer from product type" in desktop
        for skill in ("uiux", "mobile-uiux"):
            frag = design_philosophy_fragment(skill)
            assert "Desktop Identity" not in frag, (
                f"{skill}: desktop-only interview delta leaked into fragment"
            )

    def test_response_step_numbering_per_skill(self):
        assert "5) Handle user response:" in design_philosophy_fragment("uiux")
        for skill in ("mobile-uiux", "desktop-uiux"):
            assert "5.6) Handle user response:" in design_philosophy_fragment(
                skill
            )

    def test_checkpoint_shortcut_delta_only_in_desktop(self):
        desktop = design_philosophy_checkpoint("desktop-uiux")
        assert "word/number/glyph/shortcut" in desktop
        for skill in ("uiux", "mobile-uiux"):
            ckpt = design_philosophy_checkpoint(skill)
            assert "word/number/glyph (NOT" in ckpt
            assert "/shortcut" not in ckpt

    @pytest.mark.parametrize("skill", ["uiux", "mobile-uiux", "desktop-uiux"])
    def test_checkpoint_contains_shared_core(self, skill):
        ckpt = design_philosophy_checkpoint(skill)
        assert "> **CHECKPOINT — MANDATORY — NEVER SKIP**" in ckpt
        assert CHECKPOINT_SENTINEL in ckpt
        assert (
            "If any of (a) / (b) / (c) fails: STOP and fix before proceeding."
            in ckpt
        )

    @pytest.mark.parametrize("bad_skill", ["implement", "figma2proto", ""])
    def test_unknown_skill_raises(self, bad_skill):
        with pytest.raises(ValueError):
            design_philosophy_fragment(bad_skill)
        with pytest.raises(ValueError):
            design_philosophy_checkpoint(bad_skill)


class TestTemplatesConsumeToken:
    """TC-041b / AC-1: no inline copy of the fragment survives in any tmpl."""

    @pytest.mark.parametrize("skill", ["uiux", "mobile-uiux", "desktop-uiux"])
    def test_tmpl_uses_tokens(self, skill):
        text = _tmpl_path(skill).read_text(encoding="utf-8")
        assert "{{DESIGN_PHILOSOPHY}}" in text, f"{skill}: token missing"
        assert "{{DESIGN_PHILOSOPHY_CHECKPOINT}}" in text, (
            f"{skill}: checkpoint token missing"
        )

    @pytest.mark.parametrize("skill", ["uiux", "mobile-uiux", "desktop-uiux"])
    def test_no_inline_fragment_copy_in_tmpl(self, skill):
        text = _tmpl_path(skill).read_text(encoding="utf-8")
        for sentinel in (
            INTERVIEW_SENTINEL,
            CASE_B_SENTINEL,
            CHECKPOINT_SENTINEL,
        ):
            assert sentinel not in text, (
                f"{skill}: inline copy of fragment content survives in tmpl "
                f"({sentinel[:40]!r}...)"
            )


class TestGeneratedOutput:
    """TC-041d: each generated SKILL.md contains the fragment exactly once."""

    @pytest.mark.parametrize("skill", ["uiux", "mobile-uiux", "desktop-uiux"])
    def test_fragment_appears_exactly_once(self, skill):
        text = _generated_path(skill).read_text(encoding="utf-8")
        for sentinel in (
            INTERVIEW_SENTINEL,
            CASE_B_SENTINEL,
            CHECKPOINT_SENTINEL,
        ):
            count = text.count(sentinel)
            assert count == 1, (
                f"{skill}/SKILL.md: expected exactly 1 occurrence of "
                f"{sentinel[:40]!r}..., found {count}"
            )

    @pytest.mark.parametrize("skill", ["uiux", "mobile-uiux", "desktop-uiux"])
    def test_no_duplicated_section_headers(self, skill):
        text = _generated_path(skill).read_text(encoding="utf-8")
        assert text.count("Handle user response:") == 1, (
            f"{skill}/SKILL.md: duplicated interview response section"
        )

    def test_desktop_output_keeps_platform_deltas(self):
        desktop = _generated_path("desktop-uiux").read_text(encoding="utf-8")
        assert "e) **Desktop Identity**" in desktop
        assert "word/number/glyph/shortcut" in desktop
        for skill in ("uiux", "mobile-uiux"):
            text = _generated_path(skill).read_text(encoding="utf-8")
            assert "e) **Desktop Identity**" not in text
            assert "word/number/glyph/shortcut" not in text


class TestAgentDriftGuard:
    """TC-041c / AC-3: agent copies stay verbatim-aligned with the canonical
    fragment chunks (whitespace-normalized containment)."""

    def test_agent_roster(self):
        assert UIUX_AGENT_FILES == (
            "agents/uiux-developer.md",
            "agents/mobile-uiux-developer.md",
            "agents/desktop-uiux-developer.md",
        )

    def test_fragments_are_nonempty_strings(self):
        assert AGENT_DESIGN_FRAGMENTS, "no canonical agent fragments defined"
        for name, frag in AGENT_DESIGN_FRAGMENTS.items():
            assert isinstance(frag, str) and frag.strip(), (
                f"canonical fragment {name!r} is empty"
            )

    @pytest.mark.parametrize(
        "agent_rel",
        [
            "agents/uiux-developer.md",
            "agents/mobile-uiux-developer.md",
            "agents/desktop-uiux-developer.md",
        ],
    )
    def test_agent_contains_canonical_fragments(self, agent_rel):
        agent_path = ROOT / agent_rel
        text = agent_path.read_text(encoding="utf-8")
        missing = find_out_of_sync_fragments(text)
        assert not missing, (
            f"{agent_rel} is out of sync with the canonical design-philosophy "
            f"fragment chunk(s) {missing} in scripts/fragments.py — sync the "
            f"agent file (or revert the fragment edit)."
        )

    def test_guard_detects_edited_canonical_fragment(self):
        """Editing a canonical chunk without syncing agents must flag every
        agent file (the drift-guard failure in the test above then names the
        out-of-sync file)."""
        doctored = dict(AGENT_DESIGN_FRAGMENTS)
        first_chunk = next(iter(doctored))
        doctored[first_chunk] = doctored[first_chunk] + " EDITED-WITHOUT-SYNC"
        for agent_rel in UIUX_AGENT_FILES:
            text = (ROOT / agent_rel).read_text(encoding="utf-8")
            missing = find_out_of_sync_fragments(text, fragments=doctored)
            assert first_chunk in missing, (
                f"drift guard failed to detect a canonical-fragment edit for "
                f"{agent_rel}"
            )

    def test_normalized_containment_ignores_whitespace_only_changes(self):
        """The guard compares normalized whitespace — reflowing lines in an
        agent file must NOT trip it (guard is for content drift only)."""
        agent_text = (ROOT / UIUX_AGENT_FILES[0]).read_text(encoding="utf-8")
        reflowed = _normalize(agent_text)
        assert not find_out_of_sync_fragments(reflowed)
