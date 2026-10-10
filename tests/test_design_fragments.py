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

ISSUE-060 / SPEC-060 extends the mechanism with three new tokens —
{{PILOT_GATE}}, {{AI_TELLS}}, {{DESIGN_SWEEPS}} — pinned below the same
way (AC2: shared surviving text exists once in scripts/fragments.py and
zero times as per-skill copies), and deletes the `self_review_confidence`
chunk (SPEC-060 D5, the ISSUE-059 debt explicitly assigned to ISSUE-060).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import fragments as fragments_module  # noqa: E402
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


# ---------------------------------------------------------------------------
# ISSUE-060 / SPEC-060: contract-conversion fragment tokens
# ---------------------------------------------------------------------------

# Token -> resolver function name in scripts/fragments.py (same naming
# convention as design_philosophy_fragment / slop_calibration_fragment /
# design_extend_mode_fragment).
NEW_FRAGMENT_RESOLVERS: dict[str, str] = {
    "PILOT_GATE": "pilot_gate_fragment",
    "AI_TELLS": "ai_tells_fragment",
    "DESIGN_SWEEPS": "design_sweeps_fragment",
}

# Once-only sentinels: one distinctive sentence per shared block, copied
# verbatim from the pre-conversion tmpls (each occurs exactly once in every
# tmpl today, and zero times in scripts/fragments.py — grep-verified
# 2026-10-10). Post-conversion the ownership inverts: exactly once in
# scripts/fragments.py, zero inline tmpl copies, exactly once per generated
# SKILL.md.
NEW_FRAGMENT_SENTINELS: dict[str, str] = {
    "PILOT_GATE": (
        "Generator-as-judge fails: the same context that produced the "
        "pilot will not reliably catch its own slop."
    ),
    "AI_TELLS": (
        "Concrete signatures LLMs default to. Banned unless the brief "
        "explicitly calls for one."
    ),
    "DESIGN_SWEEPS": "catches the failures that ship most",
}

ALL_UIUX_SKILLS = ["uiux", "mobile-uiux", "desktop-uiux"]


def _resolver_for(token: str):
    """getattr-based lookup so a missing resolver is a clean assert failure
    naming the gap, never a collection-time ImportError."""
    name = NEW_FRAGMENT_RESOLVERS[token]
    fn = getattr(fragments_module, name, None)
    assert fn is not None, (
        f"scripts/fragments.py defines no {name}() resolver for "
        f"{{{{{token}}}}} (SPEC-060 Migration step 1)"
    )
    return fn


def _fragments_source_normalized() -> str:
    """fragments.py source with backslash-continued string lines joined,
    then whitespace-normalized — so a sentinel split across continuation
    lines (the _SLOP_CALIBRATION style) still counts as one occurrence."""
    src = (SCRIPTS_DIR / "fragments.py").read_text(encoding="utf-8")
    return _normalize(src.replace("\\\n", ""))


class TestContractConversionTokens:
    """TC-060a / AC2: shared surviving text exists once in
    scripts/fragments.py and zero times as per-skill copies — the three
    SPEC-060 blocks (pilot gate, Specific AI Tells, Phase 5.5 sweeps) are
    extracted to {{PILOT_GATE}} / {{AI_TELLS}} / {{DESIGN_SWEEPS}} tokens
    parameterized over UIUX_SKILLS like {{DESIGN_EXTEND_MODE}}."""

    @pytest.mark.parametrize("token", sorted(NEW_FRAGMENT_RESOLVERS))
    @pytest.mark.parametrize("skill", ALL_UIUX_SKILLS)
    def test_tmpl_uses_token(self, token, skill):
        text = _tmpl_path(skill).read_text(encoding="utf-8")
        assert f"{{{{{token}}}}}" in text, (
            f"{skill}: {{{{{token}}}}} token missing from the tmpl"
        )

    @pytest.mark.parametrize("token", sorted(NEW_FRAGMENT_RESOLVERS))
    def test_resolver_registered_in_gen_skills(self, token):
        fn = _resolver_for(token)
        assert RESOLVERS.get(token) is fn, (
            f"gen_skills.RESOLVERS[{token!r}] is not "
            f"fragments.{NEW_FRAGMENT_RESOLVERS[token]}"
        )

    @pytest.mark.parametrize("token", sorted(NEW_FRAGMENT_RESOLVERS))
    @pytest.mark.parametrize("skill", ALL_UIUX_SKILLS)
    def test_resolver_output_contains_shared_sentinel(self, token, skill):
        frag = _resolver_for(token)(skill)
        assert NEW_FRAGMENT_SENTINELS[token] in _normalize(frag), (
            f"{token} resolution for {skill} lost the shared sentinel "
            f"{NEW_FRAGMENT_SENTINELS[token][:40]!r}..."
        )

    @pytest.mark.parametrize("token", sorted(NEW_FRAGMENT_RESOLVERS))
    @pytest.mark.parametrize("bad_skill", ["implement", "figma2proto", ""])
    def test_resolver_rejects_unknown_skill(self, token, bad_skill):
        fn = _resolver_for(token)
        with pytest.raises(ValueError):
            fn(bad_skill)


class TestContractConversionOnceOnly:
    """TC-060b / AC2 once-only sentinels: the canonical copy lives in
    scripts/fragments.py exactly once; no literal per-skill copy survives
    in any tmpl; each generated SKILL.md contains the resolved content
    exactly once."""

    @pytest.mark.parametrize("token", sorted(NEW_FRAGMENT_SENTINELS))
    def test_sentinel_exactly_once_in_fragments_py(self, token):
        sentinel = _normalize(NEW_FRAGMENT_SENTINELS[token])
        count = _fragments_source_normalized().count(sentinel)
        assert count == 1, (
            f"scripts/fragments.py contains the {token} sentinel "
            f"{NEW_FRAGMENT_SENTINELS[token][:40]!r}... {count} times "
            f"(expected exactly 1 canonical copy)"
        )

    @pytest.mark.parametrize("token", sorted(NEW_FRAGMENT_SENTINELS))
    @pytest.mark.parametrize("skill", ALL_UIUX_SKILLS)
    def test_sentinel_zero_times_in_tmpl(self, token, skill):
        text = _normalize(_tmpl_path(skill).read_text(encoding="utf-8"))
        sentinel = _normalize(NEW_FRAGMENT_SENTINELS[token])
        assert sentinel not in text, (
            f"{skill}: inline per-skill copy of the {token} block survives "
            f"in the tmpl ({NEW_FRAGMENT_SENTINELS[token][:40]!r}...)"
        )

    @pytest.mark.parametrize("token", sorted(NEW_FRAGMENT_SENTINELS))
    @pytest.mark.parametrize("skill", ALL_UIUX_SKILLS)
    def test_generated_contains_sentinel_exactly_once(self, token, skill):
        text = _normalize(_generated_path(skill).read_text(encoding="utf-8"))
        sentinel = _normalize(NEW_FRAGMENT_SENTINELS[token])
        count = text.count(sentinel)
        assert count == 1, (
            f"{skill}/SKILL.md: expected exactly 1 occurrence of the "
            f"{token} sentinel, found {count}"
        )

    @pytest.mark.parametrize("token", sorted(NEW_FRAGMENT_RESOLVERS))
    @pytest.mark.parametrize("skill", ALL_UIUX_SKILLS)
    def test_generated_contains_full_resolved_fragment(self, token, skill):
        """The generated SKILL.md carries the resolver's full output
        (whitespace-normalized containment, the drift-guard convention)."""
        frag = _resolver_for(token)(skill)
        generated = _generated_path(skill).read_text(encoding="utf-8")
        assert _normalize(frag) in _normalize(generated), (
            f"{skill}/SKILL.md does not contain the resolved "
            f"{{{{{token}}}}} content — regenerate via "
            f"python3 scripts/gen_skills.py"
        )


class TestConfidenceRitualChunkRemoved:
    """TC-060c / SPEC-060 D5 (the ISSUE-059 debt assigned to ISSUE-060):
    the `self_review_confidence` chunk is deleted from
    AGENT_DESIGN_FRAGMENTS; the surviving Self-Review chunks stay."""

    def test_self_review_confidence_chunk_absent(self):
        assert "self_review_confidence" not in AGENT_DESIGN_FRAGMENTS, (
            "AGENT_DESIGN_FRAGMENTS still carries the "
            "self_review_confidence chunk (SPEC-060 D5 deletes the "
            "confidence-rating ritual; SPEC-010 recorded self-grading "
            "sycophancy as a defect)"
        )

    def test_no_chunk_carries_confidence_rating_content(self):
        offenders = [
            name
            for name, frag in AGENT_DESIGN_FRAGMENTS.items()
            if "**Confidence rating**" in frag
        ]
        assert offenders == [], (
            f"canonical chunk(s) {offenders} still contain the "
            f"confidence-rating ritual content (SPEC-060 D5)"
        )

    def test_surviving_self_review_chunks_stay(self):
        # Deleting the ritual must not take the load-bearing Self-Review
        # chunks with it.
        assert "self_review_alignment" in AGENT_DESIGN_FRAGMENTS
        assert "self_review_token_rule" in AGENT_DESIGN_FRAGMENTS
