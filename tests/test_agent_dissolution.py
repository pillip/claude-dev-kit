"""SPEC-062 — the five A-bucket agents are dissolved into their skill contracts.

Per-agent regression pins (ISSUE-062 AC #1): every invariant a dissolved agent
enforced must remain observably enforced at the skill level. Each class below
asserts (a) the roster file `agents/<name>.md` is gone, (b) the absorbed or
retained contract lines are present in the calling skill's `.tmpl` AND the
generated `SKILL.md`, and (c) the pre-existing skill invariants that must
SURVIVE the deletion are still pinned.

Absence guards follow the mutation-test discipline: every `not in` assertion
targets a string verified to exist on main@776ac73 before the dissolution
commits removed it (occurrence-whitelist, not phrasing blacklist).
"""

from __future__ import annotations

from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = KIT_ROOT / "agents"
SKILL_DIR = KIT_ROOT / "skills"

# The exact literal both research skills must render when no source exists
# (SPEC-018; formerly duplicated into the two research agent files).
NO_DATA_LITERAL = (
    "Data: not available — re-run /deep-research with a sharper question "
    'or accept "no data".'
)


def _skill_texts(name: str) -> dict[str, str]:
    """Return {label: content} for a skill's template and generated file."""
    return {
        f"skills/{name}/SKILL.md.tmpl": (
            SKILL_DIR / name / "SKILL.md.tmpl"
        ).read_text(encoding="utf-8"),
        f"skills/{name}/SKILL.md": (
            SKILL_DIR / name / "SKILL.md"
        ).read_text(encoding="utf-8"),
    }


# ── brainstormer → /brainstorm ───────────────────────────────────────


class TestBrainstormerDissolved:
    def test_agent_file_removed(self):
        assert not (AGENT_DIR / "brainstormer.md").exists(), (
            "agents/brainstormer.md still exists — SPEC-062 dissolves it into "
            "the /brainstorm skill contract"
        )

    def test_brainstorm_skill_retains_research_path_invariants(self):
        # Regression pins for AC #1: these invariants pre-date the deletion
        # (SPEC-018 moved them into the skill) and must survive it.
        for label, text in _skill_texts("brainstorm").items():
            assert NO_DATA_LITERAL in text, f"{label} lost the no-data literal"
            assert "has_skill.py" in text, f"{label} lost the runtime probe"
            assert "deep-research" in text, f"{label} lost the primary path"
            assert (
                "Author Existing Landscape claims from training-data knowledge"
                in text
            ), f"{label} lost the training-data NEVER"


# ── business-analyst → /bizanalysis ──────────────────────────────────


class TestBusinessAnalystDissolved:
    def test_agent_file_removed(self):
        assert not (AGENT_DIR / "business-analyst.md").exists(), (
            "agents/business-analyst.md still exists — SPEC-062 dissolves it "
            "into the /bizanalysis skill contract"
        )

    def test_bizanalysis_skill_retains_research_invariants(self):
        # Regression pins for AC #1: no-data literal, single-source range
        # rendering, and the canonical five-section order live in the skill.
        for label, text in _skill_texts("bizanalysis").items():
            assert NO_DATA_LITERAL in text, f"{label} lost the no-data literal"
            assert "range: <low–high> [single-source]" in text, (
                f"{label} lost the single-source range rendering rule"
            )
            assert (
                "Executive Summary / Market Analysis / Competitive Landscape "
                "/ Business Model / Risks & Mitigations"
            ) in text, f"{label} lost the canonical five-section order"

    def test_synthesizer_section_order_comment_repoints_to_skill(self):
        src = (KIT_ROOT / "scripts" / "synthesize_from_deep_research.py").read_text(
            encoding="utf-8"
        )
        assert "skills/bizanalysis/SKILL.md.tmpl" in src, (
            "synthesize_from_deep_research.py section-order comment should "
            "cite skills/bizanalysis/SKILL.md.tmpl as its authority"
        )
        # Present on main@776ac73 (line 60) — must be gone after dissolution.
        assert "agents/business-analyst.md" not in src, (
            "synthesize_from_deep_research.py still cites the deleted "
            "agents/business-analyst.md"
        )


# ── devops agent → /devops skill ─────────────────────────────────────


class TestDevopsAgentDissolved:
    def test_agent_file_removed(self):
        assert not (AGENT_DIR / "devops.md").exists(), (
            "agents/devops.md still exists — SPEC-062 dissolves it into the "
            "/devops skill contract"
        )

    def test_sprint_dispatch_routes_to_devops_skill_not_agent(self):
        for label, text in _skill_texts("sprint").items():
            assert (
                "| Infrastructure/CI/CD | (run the devops skill) "
                "| skills/devops/SKILL.md |"
            ) in text, f"{label} missing the no-agent devops dispatch row"
            # Agent-dispatch cell, present on main@776ac73 (tmpl line 155).
            assert "| devops |" not in text, (
                f"{label} still dispatches to the deleted devops agent"
            )
            assert '"deploy" → the devops skill' in text, (
                f"{label} 'How to determine' should route to the devops skill"
            )
            # Present on main@776ac73 (tmpl line 164).
            assert '"deploy" → devops' not in text, (
                f"{label} 'How to determine' still routes to the devops agent"
            )

    def test_devops_skill_absorbs_pr_check_duration_guideline(self):
        # The one agent invariant the skill Guidelines did not already carry.
        for label, text in _skill_texts("devops").items():
            assert "under ~10 minutes" in text, (
                f"{label} missing the absorbed PR-check CI duration guideline"
            )
            assert "caching and parallelism" in text, (
                f"{label} missing the caching/parallelism optimization clause"
            )
