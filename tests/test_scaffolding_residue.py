"""ISSUE-059 grep guard: scaffolding residue stays deleted.

Three A-bucket deletion classes from the SPEC-055 evolution audit
(roadmap 3a):

1. Persona blocks — `## Execution Principles (absorbed from ...` sections
   in the prd/diagnose/refactor/migrate skills (plus diagnose's step 5.5
   six-item cognitive checklist). The behavioural invariants survive as
   contract lines in each skill's Guidelines/Quality sections and are
   pinned here and in tests/test_integration.py.
2. Confidence-rating ritual — the High/Medium/Low self-grading item at
   the tail of agents' Self-Review blocks. SPEC-010 recorded self-grading
   sycophancy as a defect; the load-bearing gates are separate-context
   auditors and checkpoint scripts. Distinctive, content-specific
   checklists stay — only the rating ritual goes.
3. /implement's inline figma-converter prompt — the ~50-line duplicated
   prompt body in step 2a item 4 is replaced by a reference contract;
   `agents/figma-converter.md` is the single source. Content that lived
   ONLY in the inline prompt (the node-level `segments` mixed-font-weight
   → `<span>` instruction; the old prompt misnamed it
   `text_style.segments`, but `scripts/figma_fetch.py` emits it at node
   level) moved into the agent file.

Occurrence-whitelist convention (ISSUE-040/042 lessons): allowed files
are enumerated and asserted to STILL contain the pattern so the list
cannot rot; no phrasing blacklists. The uiux triplet agents and the
`self_review_confidence` fragment in scripts/fragments.py are owned by
ISSUE-060 and intentionally untouched here.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
AGENTS_DIR = ROOT / "agents"

PERSONA_MARKER = "Execution Principles (absorbed from"
CONFIDENCE_MARKER = "**Confidence rating**"
DIAGNOSE_CHECKLIST_MARKER = "Rate confidence (High/Medium/Low)"
# A verbatim line from the inline figma-converter prompt body deleted in
# ISSUE-059 — unique to skills/implement (mutation-tested: present before
# the deletion, absent after).
INLINE_PROMPT_MARKER = "## Required Steps (do ALL of these"

# Agents still allowed to carry the confidence-rating ritual: the uiux
# triplet is synced verbatim to scripts/fragments.py AGENT_DESIGN_FRAGMENTS
# (drift guard: tests/test_design_fragments.py) and is deflated by
# ISSUE-060, not here. No other kept exceptions.
CONFIDENCE_WHITELIST = frozenset(
    {
        "desktop-uiux-developer.md",
        "mobile-uiux-developer.md",
        "uiux-developer.md",
    }
)

TEXT_SUFFIXES = {".md", ".tmpl"}


def _skill_files():
    return sorted(
        p
        for p in SKILLS_DIR.rglob("*")
        if p.is_file() and p.suffix in TEXT_SUFFIXES
    )


def _agent_files():
    return sorted(AGENTS_DIR.glob("*.md"))


def test_rosters_are_nonempty():
    # Guard against silent glob rot making the sweeps vacuous.
    assert len(_skill_files()) > 10
    assert len(_agent_files()) > 10


def test_no_persona_blocks_in_skills_or_agents():
    offenders = [
        str(p.relative_to(ROOT))
        for p in [*_skill_files(), *_agent_files()]
        if PERSONA_MARKER in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"persona blocks (ISSUE-034 scaffolding, deleted in ISSUE-059) "
        f"found in: {offenders}"
    )


def test_confidence_rating_only_in_uiux_whitelist():
    hits = {
        p.name
        for p in _agent_files()
        if CONFIDENCE_MARKER in p.read_text(encoding="utf-8")
    }
    unexpected = sorted(hits - CONFIDENCE_WHITELIST)
    assert unexpected == [], (
        f"confidence-rating ritual (deleted in ISSUE-059 per SPEC-010) "
        f"found outside the ISSUE-060 whitelist: {unexpected}"
    )
    rotted = sorted(CONFIDENCE_WHITELIST - hits)
    assert rotted == [], (
        f"whitelisted files no longer contain the pattern — remove them "
        f"from CONFIDENCE_WHITELIST: {rotted}"
    )
    # The ritual's third habitat was a skill (diagnose step 5.5), so the
    # sweep must cover skills too. No skill is whitelisted — the uiux
    # exception set is agents-only.
    skill_hits = [
        str(p.relative_to(ROOT))
        for p in _skill_files()
        if CONFIDENCE_MARKER in p.read_text(encoding="utf-8")
    ]
    assert skill_hits == [], (
        f"confidence-rating ritual (deleted in ISSUE-059 per SPEC-010) "
        f"found in skills (no skill is whitelisted): {skill_hits}"
    )


def test_diagnose_cognitive_checklist_deleted_invariants_survive():
    for name in ("SKILL.md.tmpl", "SKILL.md"):
        content = (SKILLS_DIR / "diagnose" / name).read_text(encoding="utf-8")
        assert DIAGNOSE_CHECKLIST_MARKER not in content, (
            f"skills/diagnose/{name} regained step 5.5's confidence ritual"
        )
        lower = content.lower()
        assert "root cause" in lower, f"{name}: root-cause invariant lost"
        assert "regression test" in lower, (
            f"{name}: regression-test invariant lost"
        )
        assert "suppressing errors" in lower, (
            f"{name}: error-suppression prohibition lost"
        )


def test_absorbed_invariants_survive_as_contract_lines():
    # Each skill's behavioural invariants from the deleted persona blocks
    # must survive somewhere in the skill body (tmpl AND generated).
    pins = {
        "prd": ["developer-verifiable"],
        "refactor": ["structure-only", "rewriting, not refactoring"],
        "migrate": [
            "One major version bump per PR",
            "after each step",
            "rollback plan",
            "never assume backward compatibility",
            "deprecated API usage",
        ],
    }
    for skill, needles in pins.items():
        for name in ("SKILL.md.tmpl", "SKILL.md"):
            content = (SKILLS_DIR / skill / name).read_text(encoding="utf-8")
            for needle in needles:
                assert needle.lower() in content.lower(), (
                    f"skills/{skill}/{name}: invariant {needle!r} lost"
                )


def test_implement_figma_section_is_reference_contract():
    for name in ("SKILL.md.tmpl", "SKILL.md"):
        content = (SKILLS_DIR / "implement" / name).read_text(encoding="utf-8")
        assert INLINE_PROMPT_MARKER not in content, (
            f"skills/implement/{name} still embeds the inline "
            f"figma-converter prompt body (deleted in ISSUE-059)"
        )
        # Reference contract: agent file is the single source ...
        assert "agents/figma-converter.md" in content
        # ... plus the genuinely per-invocation call parameters:
        assert "prototype/screens/desktop.html" in content
        assert "figma-export/" in content
        assert "placeholder" in content.lower()
        # The orchestrator-side output verification (step 2a item 5) is an
        # external check, not scaffolding — it must survive.
        assert "Verify the output is not a placeholder" in content


def test_figma_converter_agent_owns_segments_instruction():
    # The mixed-font-weight node-level `segments` → <span> instruction
    # previously lived ONLY in /implement's inline prompt. Single source
    # means the agent file wins — it must own it now. (figma_fetch.py
    # emits `segments` at node level; the old inline prompt's
    # `text_style.segments` path was a schema error.)
    content = (AGENTS_DIR / "figma-converter.md").read_text(encoding="utf-8")
    assert "segments" in content, (
        "agents/figma-converter.md lost the node-level segments "
        "(mixed font-weight spans) instruction moved in ISSUE-059"
    )
    assert "<span>" in content
