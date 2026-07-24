"""Grep guard for ISSUE-018 — research-grounding hardening.

After SPEC-018 lands, no SKILL.md.tmpl or agent file for /brainstorm or
/bizanalysis should reference WebFetch for free-form claim extraction.
WebSearch is allowed (candidate URL discovery for the degraded path),
and `WebFetch` may still appear in other kit assets (review skill, etc.)
— this guard scopes only to the two skills that ISSUE-018 hardens.

These checks are intentionally text-level: they would fail noisily if a
future contributor copy-pastes the old free-form WebFetch pattern back
in. The lint message points the contributor at SPEC-018 / the platform-
first rule so the fix path is obvious.
"""

from __future__ import annotations

from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]

# Files SPEC-018 hardens. WebFetch must NOT appear in any of these.
SCOPED_FILES = [
    KIT_ROOT / "skills" / "brainstorm" / "SKILL.md.tmpl",
    KIT_ROOT / "skills" / "bizanalysis" / "SKILL.md.tmpl",
    KIT_ROOT / "agents" / "brainstormer.md",
    KIT_ROOT / "agents" / "business-analyst.md",
]


class TestNoWebFetchInScopedFiles:
    def test_no_webfetch_in_brainstorm_skill_template(self):
        path = KIT_ROOT / "skills" / "brainstorm" / "SKILL.md.tmpl"
        assert path.is_file(), f"missing expected file {path}"
        text = path.read_text(encoding="utf-8")
        assert "WebFetch" not in text, (
            f"{path} still references WebFetch. SPEC-018 removed free-form "
            "WebFetch claim extraction from /brainstorm. See "
            "docs/specs/SPEC-018.md."
        )

    def test_no_webfetch_in_bizanalysis_skill_template(self):
        path = KIT_ROOT / "skills" / "bizanalysis" / "SKILL.md.tmpl"
        assert path.is_file(), f"missing expected file {path}"
        text = path.read_text(encoding="utf-8")
        assert "WebFetch" not in text, (
            f"{path} still references WebFetch. SPEC-018 removed free-form "
            "WebFetch claim extraction from /bizanalysis. See "
            "docs/specs/SPEC-018.md."
        )

    def test_no_webfetch_in_brainstormer_agent(self):
        path = KIT_ROOT / "agents" / "brainstormer.md"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "WebFetch" not in text, (
            f"{path} still references WebFetch. SPEC-018 Migration step 5 "
            "drops WebSearch/WebFetch from this agent's tools — without it "
            "the skill-level delegation gate is bypassable via direct Task "
            "invocation."
        )

    def test_no_webfetch_in_business_analyst_agent(self):
        path = KIT_ROOT / "agents" / "business-analyst.md"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "WebFetch" not in text, (
            f"{path} still references WebFetch. SPEC-018 Migration step 5 "
            "drops WebSearch/WebFetch from this agent's tools — without it "
            "the skill-level delegation gate is bypassable via direct Task "
            "invocation."
        )


class TestRequiredArtifactsPresent:
    """If the SPEC-018 deliverables ever go missing, fail loudly so the
    skill template's degraded-path instructions don't dangle.
    """

    def test_research_claim_template_exists(self):
        assert (KIT_ROOT / "templates" / "research_claim.md").is_file()

    def test_research_auditor_agent_exists(self):
        assert (KIT_ROOT / "agents" / "research-auditor.md").is_file()

    def test_synthesizer_auditor_agent_exists(self):
        assert (KIT_ROOT / "agents" / "synthesizer-auditor.md").is_file()

    def test_has_skill_script_exists(self):
        assert (KIT_ROOT / "scripts" / "has_skill.py").is_file()

    def test_capture_source_script_exists(self):
        assert (KIT_ROOT / "scripts" / "capture_source.py").is_file()

    def test_validate_research_claim_script_exists(self):
        assert (KIT_ROOT / "scripts" / "validate_research_claim.py").is_file()

    def test_synthesizer_script_exists(self):
        assert (KIT_ROOT / "scripts" / "synthesize_from_deep_research.py").is_file()

    def test_telemetry_schema_documents_research_events(self):
        text = (KIT_ROOT / "docs" / "telemetry_schema.md").read_text(encoding="utf-8")
        required_events = [
            "research_delegated_to_deep_research",
            "research_degraded_path_used",
            "synthesis_claim_dropped",
            "research_quote_validated",
            "research_quote_rejected",
            "research_source_stale",
            "research_triangulation_single",
        ]
        for ev in required_events:
            assert ev in text, (
                f"docs/telemetry_schema.md must document {ev!r} per SPEC-018."
            )


class TestSkillTemplateMentionsDelegationFlow:
    """If the skill templates lose the delegation flow language, the lint
    won't catch it — these positive-content checks do.
    """

    def test_brainstorm_template_references_has_skill_probe(self):
        text = (KIT_ROOT / "skills" / "brainstorm" / "SKILL.md.tmpl").read_text()
        assert "has_skill.py" in text
        assert "deep-research" in text

    def test_bizanalysis_template_references_has_skill_probe(self):
        text = (KIT_ROOT / "skills" / "bizanalysis" / "SKILL.md.tmpl").read_text()
        assert "has_skill.py" in text
        assert "deep-research" in text

    def test_bizanalysis_template_references_no_data_literal(self):
        text = (KIT_ROOT / "skills" / "bizanalysis" / "SKILL.md.tmpl").read_text()
        assert "Data: not available" in text
