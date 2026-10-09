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
            # Body-level pins: the frontmatter allowed-tools line also contains
            # "has_skill.py" / "deep-research", so pin the step-5a strings that
            # only exist in the routing body (review fix, PR #108).
            assert "python3 scripts/has_skill.py deep-research" in text, (
                f"{label} lost the runtime probe step"
            )
            assert "invoke `/deep-research`" in text, (
                f"{label} lost the primary-path routing step"
            )
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


# ── documenter → /ship step 3.5 inline contract ──────────────────────


class TestDocumenterDissolved:
    def test_agent_file_removed(self):
        assert not (AGENT_DIR / "documenter.md").exists(), (
            "agents/documenter.md still exists — SPEC-062 dissolves it into "
            "the /ship step 3.5 inline contract"
        )

    def test_ship_step_3_5_carries_inline_doc_contract(self):
        for label, text in _skill_texts("ship").items():
            assert "3.5)" in text, f"{label} lost ship step 3.5"
            assert "affected by the PR diff" in text, (
                f"{label} lost the diff-scoping contract line"
            )
            assert "must exist in the codebase" in text, (
                f"{label} lost the command/path-existence verification line"
            )
            assert "no updates needed" in text, (
                f"{label} lost the 'no updates needed' valid-outcome line"
            )
            # Review fixes (PR #108): the dissolved documenter's tools:
            # frontmatter and review-lessons consumption were enforced
            # invariants too — the inline contract must carry both.
            assert "must not run Bash or fetch web content" in text, (
                f"{label} lost the subagent toolset restriction line"
            )
            assert "recalled review lessons" in text, (
                f"{label} lost the review-lessons pass-through line"
            )
            # Both present on main@776ac73 (ship tmpl lines 19-20).
            assert "agents/documenter.md" not in text, (
                f"{label} still references the deleted agents/documenter.md"
            )
            assert "documenter subagent" not in text, (
                f"{label} still launches the deleted documenter roster agent"
            )

    def test_ship_step_3_5_keeps_task_call_and_registry_wrapper(self):
        # Context isolation survives dissolution: the Task launch stays, and
        # the surrounding registry_edit guidance is untouched.
        for label, text in _skill_texts("ship").items():
            assert "Use the Task tool to launch" in text, (
                f"{label} step 3.5 no longer launches a separate-context "
                "subagent"
            )
            assert "bash scripts/registry_edit.sh STATUS.md -- bash -c" in text, (
                f"{label} lost the registry wrapper guidance around step 3.5"
            )


# ── copywriter → uiux-triplet Phase 4.5 inline contract ──────────────


UIUX_SKILLS = ["uiux", "mobile-uiux", "desktop-uiux"]


class TestCopywriterDissolved:
    def test_agent_file_removed(self):
        assert not (AGENT_DIR / "copywriter.md").exists(), (
            "agents/copywriter.md still exists — SPEC-062 dissolves it into "
            "the uiux-triplet Phase 4.5 inline contract"
        )

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_phase_4_5_carries_inline_copy_contract(self, skill):
        for label, text in _skill_texts(skill).items():
            # Present on main@776ac73 in each file's Phase 4.5 — must be gone.
            assert "copywriter" not in text, (
                f"{label} still invokes the deleted copywriter roster agent"
            )
            assert "appears in the copy inventory" in text, (
                f"{label} lost the per-screen coverage contract line"
            )
            assert "empty, loading, error, and success states" in text, (
                f"{label} lost the per-state coverage contract line"
            )
            assert "one-concept-one-word" in text, (
                f"{label} lost the glossary one-concept-one-word rule"
            )
            assert "[what happened] + [what to do]" in text, (
                f"{label} lost the error copy formula"
            )
            assert "design_philosophy" in text, (
                f"{label} lost the voice-derivation contract line"
            )
            # Review fixes (PR #108): the dissolved copywriter's tools:
            # frontmatter and review-lessons consumption were enforced
            # invariants too — the inline contract must carry both.
            assert "must not run Bash or fetch web content" in text, (
                f"{label} lost the subagent toolset restriction line"
            )
            assert "recalled review lessons" in text, (
                f"{label} lost the review-lessons pass-through line"
            )

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_phase_4_5_surroundings_survive(self, skill):
        # The rewrite must not take the neighbouring enforcement blocks with it.
        for label, text in _skill_texts(skill).items():
            assert "Banned copy tells" in text, (
                f"{label} lost the banned-copy-tells block"
            )
            assert "MUST complete before Phase 5" in text, (
                f"{label} lost the Phase 5 ordering requirement"
            )

    def test_mobile_desktop_adaptation_branches_survive(self):
        # The "If exists → append adaptations" branches never invoked the
        # agent and must stay as-is, as must the 16-a a11y-label requirements.
        for label, text in _skill_texts("mobile-uiux").items():
            assert "## Mobile Adaptations" in text, (
                f"{label} lost the Mobile Adaptations append branch"
            )
            assert "accessibilityLabel" in text, (
                f"{label} lost the 16-a accessibilityLabel requirement"
            )
        for label, text in _skill_texts("desktop-uiux").items():
            assert "## Desktop Adaptations" in text, (
                f"{label} lost the Desktop Adaptations append branch"
            )
            assert "aria-label" in text, (
                f"{label} lost the 16-a aria-label requirement"
            )
