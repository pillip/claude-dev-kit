"""ISSUE-054 / SPEC-054: brownfield design extraction (create vs extend mode).

SPEC-054 chose Option A — ONE platform-parameterized `design-scanner` agent
invoked directly by the three uiux skills, deliberately not a /scan-family
member. The shared create/extend branch lives in scripts/fragments.py as the
{{DESIGN_EXTEND_MODE}} token, resolved per skill over UIUX_SKILLS (the same
mechanism ISSUE-041 established for the design-philosophy boilerplate).

Coverage map:
- TC-054a  resolver exists, registered, resolves per skill, rejects unknown
- TC-054b  per-platform source maps do not leak across skills
- TC-054c  the three tmpls consume the token and keep no inline copy
- TC-054d  generated SKILL.md carries the fragment exactly once
- TC-054e  AC-4 no-regression: each skill's original detection globs survive
- TC-054f  design-scanner agent contract (read-only, provenance, all 3 maps)
- TC-054g  roster grew 32 -> 33 and the README surfaces agree
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from fragments import (  # noqa: E402
    UIUX_SKILLS,
    design_extend_mode_fragment,
)
from gen_skills import RESOLVERS  # noqa: E402

SCANNER = ROOT / "agents" / "design-scanner.md"

# Sentinels that exist ONLY inside the canonical extend-mode fragment.
MODE_SENTINEL = "**Mode selection — `create` or `extend`"
CONFIRM_SENTINEL = "Never switch modes silently"
SCANNER_SENTINEL = "invoke the **design-scanner** agent via the Task tool"

# The detection globs each skill used before ISSUE-054. AC-4 says a project
# with no existing UI must behave exactly as it does today, so the detection
# input must survive the refactor verbatim.
ORIGINAL_GLOBS = {
    "uiux": [
        "`**/*.html`",
        "`**/*.css`",
        "`**/*.tsx`",
        "`**/*.jsx`",
        "`**/*.vue`",
        "`**/*.svelte`",
    ],
    "mobile-uiux": [
        "`**/*.tsx`",
        "`**/*.ts`",
        "`app.json`",
        "`app.config.js`",
        "`app.config.ts`",
    ],
    "desktop-uiux": [
        "`**/electron/**`",
        "`**/main.ts`",
        "`**/preload.ts`",
        "`**/electron-builder.*`",
        "`**/forge.config.*`",
    ],
}

# Phrasing that lived inline in each tmpl before the fragment absorbed it.
# ISSUE-041/PR#72 lesson: a presence-only drift guard stays green when an
# orphaned copy of the superseded wording survives next to the new text, so
# every presence assertion here is paired with an absence assertion.
SUPERSEDED_INLINE = {
    "uiux": "4) Scan the project for existing UI code:",
    "mobile-uiux": "5) Scan the project for existing mobile code:",
    "desktop-uiux": "5) Scan the project for existing desktop code:",
}


def _norm(text: str) -> str:
    """Whitespace-normalize so assertions survive line reflow in the fragment
    (same principle as find_out_of_sync_fragments' drift guard)."""
    return " ".join(text.split())


def _tmpl(skill: str) -> str:
    return (ROOT / "skills" / skill / "SKILL.md.tmpl").read_text(encoding="utf-8")


def _generated(skill: str) -> str:
    return (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---")
    # Mirror scripts/validate_frontmatter.py: a body-only key must not pass
    # when the closing fence is missing (ISSUE-042 lesson).
    assert len(parts) >= 3, f"{path.name}: no closing frontmatter fence"
    fm: dict[str, list[str]] = {}
    for line in parts[1].splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            fm.setdefault(m.group(1), []).append(m.group(2).strip())
    # Collect-all, then assert single occurrence — YAML is last-wins, so a
    # first-match-wins lookup diverges from the real parser (ISSUE-042).
    for key, values in fm.items():
        assert len(values) == 1, f"{path.name}: duplicate frontmatter key {key!r}"
    return {k: v[0] for k, v in fm.items()}


class TestExtendModeResolver:
    """TC-054a: the fragment resolver exists and is wired into the generator."""

    def test_token_registered_in_gen_skills(self):
        assert "DESIGN_EXTEND_MODE" in RESOLVERS
        assert RESOLVERS["DESIGN_EXTEND_MODE"] is design_extend_mode_fragment

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_fragment_contains_shared_core(self, skill):
        frag = design_extend_mode_fragment(skill)
        for marker in (
            MODE_SENTINEL,
            CONFIRM_SENTINEL,
            SCANNER_SENTINEL,
            "CONFIRMED",
            "INFERRED",
        ):
            assert marker in frag, f"{skill}: extend-mode fragment missing {marker!r}"

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_fragment_keeps_original_detection_globs(self, skill):
        """TC-054e / AC-4: detection input is unchanged by the refactor."""
        frag = design_extend_mode_fragment(skill)
        for glob in ORIGINAL_GLOBS[skill]:
            assert glob in frag, (
                f"{skill}: detection glob {glob} dropped — a project that "
                f"detects today must still detect after ISSUE-054"
            )

    @pytest.mark.parametrize("bad_skill", ["implement", "figma2proto", ""])
    def test_unknown_skill_raises(self, bad_skill):
        with pytest.raises(ValueError):
            design_extend_mode_fragment(bad_skill)


class TestModeContract:
    """AC-3: `extend` must actually change what Phase 2 and the pilot gate do.
    Without these, the mode branch would emit a scan report nobody obeys."""

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_philosophy_does_not_invent(self, skill):
        frag = _norm(design_extend_mode_fragment(skill))
        assert "do NOT commit to a new aesthetic direction" in frag
        assert "signature_move" in frag
        assert "never invent one" in frag

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_pilot_gate_becomes_consistency_check(self, skill):
        frag = _norm(design_extend_mode_fragment(skill))
        assert "consistency check" in frag
        assert "A pilot that reads as a redesign FAILS the gate" in frag

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_interview_is_reframed(self, skill):
        frag = _norm(design_extend_mode_fragment(skill))
        assert 'to "what should change, and what must stay?"' in frag

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_host_tells_route_to_brief_overrides(self, skill):
        """The Anti-AI-Slop sweeps must not rewrite the host product's own
        conventions — they route through the `Brief overrides:` seam."""
        assert "Brief overrides:" in design_extend_mode_fragment(skill)

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_tags_are_transcribed_not_promoted(self, skill):
        frag = design_extend_mode_fragment(skill)
        assert "Never promote an" in frag
        assert "extraction_verdict: insufficient" in frag


class TestPlatformSourceMaps:
    """TC-054b: SPEC-054 bets on one method with three source maps. Each skill
    must get its own map and only its own."""

    def test_web_map(self):
        frag = design_extend_mode_fragment("uiux")
        assert "tailwind.config" in frag
        assert "CSS custom propert" in frag
        assert "StyleSheet" not in frag

    def test_mobile_map(self):
        frag = design_extend_mode_fragment("mobile-uiux")
        assert "StyleSheet" in frag
        assert "src/theme/" in frag
        assert "tailwind.config" not in frag

    def test_desktop_map(self):
        frag = design_extend_mode_fragment("desktop-uiux")
        assert "renderer" in frag
        assert "src/theme/" in frag
        assert "StyleSheet" not in frag

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_system_doc_is_platform_specific(self, skill):
        expected = {
            "uiux": "docs/design_system.md",
            "mobile-uiux": "docs/design_system_mobile.md",
            "desktop-uiux": "docs/design_system_desktop.md",
        }[skill]
        assert expected in design_extend_mode_fragment(skill)


class TestTemplatesConsumeToken:
    """TC-054c: no inline copy survives in any tmpl (presence + absence)."""

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_tmpl_uses_token(self, skill):
        assert "{{DESIGN_EXTEND_MODE}}" in _tmpl(skill), f"{skill}: token missing"

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_no_inline_fragment_copy_in_tmpl(self, skill):
        text = _tmpl(skill)
        for sentinel in (MODE_SENTINEL, CONFIRM_SENTINEL, SCANNER_SENTINEL):
            assert sentinel not in text, (
                f"{skill}: inline copy of extend-mode content survives in tmpl"
            )

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_superseded_inline_step_is_gone(self, skill):
        """The old scan step must be REMOVED, not left orphaned beside the
        token (ISSUE-041/PR#72 absence-guard lesson)."""
        assert SUPERSEDED_INLINE[skill] not in _tmpl(skill), (
            f"{skill}: superseded inline scan step still present alongside "
            f"{{{{DESIGN_EXTEND_MODE}}}} — orphaned copy"
        )


class TestGeneratedOutput:
    """TC-054d: each generated SKILL.md carries the fragment exactly once."""

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_fragment_appears_exactly_once(self, skill):
        text = _generated(skill)
        for sentinel in (MODE_SENTINEL, CONFIRM_SENTINEL, SCANNER_SENTINEL):
            count = text.count(sentinel)
            assert count == 1, (
                f"{skill}/SKILL.md: expected exactly 1 occurrence of "
                f"{sentinel[:40]!r}, found {count}"
            )

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_generated_keeps_original_globs(self, skill):
        text = _generated(skill)
        for glob in ORIGINAL_GLOBS[skill]:
            assert glob in text, f"{skill}/SKILL.md: detection glob {glob} lost"

    def test_platform_maps_do_not_cross_contaminate(self):
        assert "tailwind.config" not in _generated("mobile-uiux")
        assert "StyleSheet" not in _generated("uiux")


class TestDesignScannerAgent:
    """TC-054f: the extraction agent's contract."""

    def test_agent_file_exists(self):
        assert SCANNER.is_file(), "agents/design-scanner.md missing"

    def test_frontmatter_shape(self):
        fm = _frontmatter(SCANNER)
        assert fm["name"] == "design-scanner"
        assert fm["description"].strip()
        assert fm["effort"] in {"low", "medium", "high", "xhigh"}
        assert "model" not in fm, "ISSUE-030: agents inherit the session model"

    def test_agent_is_read_only(self):
        """Extraction must never mutate the host codebase. ISSUE-054 scope
        explicitly excludes refactoring or rewriting existing UI code."""
        tools = {t.strip() for t in _frontmatter(SCANNER)["tools"].split(",")}
        assert tools == {"Read", "Glob", "Grep"}, (
            f"design-scanner must be read-only; got {sorted(tools)}"
        )

    def test_agent_covers_all_three_source_maps(self):
        text = SCANNER.read_text(encoding="utf-8")
        for marker in (
            "tailwind.config",
            "CSS custom propert",
            "StyleSheet",
            "src/theme/",
            "renderer",
        ):
            assert marker in text, f"design-scanner missing source-map marker {marker!r}"

    def test_agent_mandates_provenance(self):
        text = SCANNER.read_text(encoding="utf-8")
        assert "file:line" in text
        assert "CONFIRMED" in text and "INFERRED" in text
        assert "never invent" in text.lower() or "do not invent" in text.lower()

    def test_agent_refuses_to_write_docs_itself(self):
        """The agent reports; the skill writes. Keeps the no-write tool set
        honest instead of relying on the model to abstain."""
        text = SCANNER.read_text(encoding="utf-8")
        assert "NOT written to disk" in text or "does not write" in text.lower()


class TestRosterSurfaces:
    """TC-054g: roster 32 -> 33 lands on every surface that asserts it."""

    def test_roster_count(self):
        agents = sorted((ROOT / "agents").glob("*.md"))
        assert len(agents) == 33

    def test_readme_prose_count_updated(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "33 engineering agents" in readme
        assert "32 engineering agents" not in readme

    def test_readme_agents_table_has_design_scanner(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        rows = [ln for ln in readme.splitlines() if ln.startswith("| `design-scanner`")]
        assert len(rows) == 1, "expected exactly 1 design-scanner row in the agents table"
        fm = _frontmatter(SCANNER)
        assert f"| {fm['effort']} |" in rows[0], (
            "README agents-table effort cell disagrees with agent frontmatter "
            "(ISSUE-050 lint contract)"
        )
