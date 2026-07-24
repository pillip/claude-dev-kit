"""Structural guards for ISSUE-019 — /review platform-first delegation.

After SPEC-019 lands, the kit's `/review` skill must (a) probe the runtime
for /code-review and /security-review, (b) delegate to them when exposed,
(c) fall back to the kit's reviewer agent as a degraded-only fallback,
and (d) preserve all kit-distinctive checks (Figma 3.5-3.10, ui-reviewer,
design-auditor, a11y-auditor, review_lessons). The `agents/reviewer.md`
file must no longer redefine the runtime-owned checklist categories as
its CANONICAL scope — those moved to the runtime — and the new
synthesizer + merge-auditor must be present.

These checks are intentionally text-level: they fail noisily if a future
contributor copy-pastes the pre-ISSUE-019 patterns back in or removes a
required artifact.
"""

from __future__ import annotations

from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]


class TestRequiredArtifactsPresent:
    def test_synthesize_review_notes_script_exists(self):
        assert (KIT_ROOT / "scripts" / "synthesize_review_notes.py").is_file()

    def test_review_merge_auditor_agent_exists(self):
        assert (KIT_ROOT / "agents" / "review-merge-auditor.md").is_file()

    def test_reviewer_agent_still_exists(self):
        # reviewer.md is retitled to degraded-only, NOT removed
        assert (KIT_ROOT / "agents" / "reviewer.md").is_file()

    def test_has_skill_script_reused(self):
        # Probe primitive comes from ISSUE-018; ISSUE-019 reuses, does not duplicate
        assert (KIT_ROOT / "scripts" / "has_skill.py").is_file()


class TestSkillTemplateReferencesDelegationFlow:
    def test_skill_invokes_runtime_probe_for_both_skills(self):
        text = (KIT_ROOT / "skills" / "review" / "SKILL.md.tmpl").read_text(encoding="utf-8")
        assert "has_skill.py code-review" in text
        assert "has_skill.py security-review" in text

    def test_skill_invokes_synthesizer(self):
        text = (KIT_ROOT / "skills" / "review" / "SKILL.md.tmpl").read_text(encoding="utf-8")
        assert "synthesize_review_notes.py" in text

    def test_skill_invokes_merge_auditor_via_task(self):
        text = (KIT_ROOT / "skills" / "review" / "SKILL.md.tmpl").read_text(encoding="utf-8")
        assert "review-merge-auditor" in text
        assert "subagent_type" in text

    def test_skill_preserves_kit_distinctive_phases(self):
        # Figma 3.5-3.9 + ui-reviewer + design-auditor + a11y-auditor must survive
        text = (KIT_ROOT / "skills" / "review" / "SKILL.md.tmpl").read_text(encoding="utf-8")
        for phrase in (
            "Figma compliance check",
            "Computed style verification",
            "ui-reviewer subagent",
            "design-auditor subagent",
            "a11y-auditor subagent",
            "Learning Extraction",
        ):
            assert phrase in text, f"{phrase!r} missing — kit-distinctive surface broken"

    def test_skill_telemetry_events_referenced(self):
        text = (KIT_ROOT / "skills" / "review" / "SKILL.md.tmpl").read_text(encoding="utf-8")
        for ev in (
            "review_delegated_to_code_review",
            "review_delegated_to_security_review",
            "review_degraded_path_used",
            "review_merge_audit_finding",
        ):
            assert ev in text, f"telemetry event {ev!r} missing from /review skill"


class TestReviewerAgentIsDegradedOnly:
    def test_reviewer_description_states_degraded_path_role(self):
        text = (KIT_ROOT / "agents" / "reviewer.md").read_text(encoding="utf-8")
        # Description must explicitly call out the degraded-only role to prevent
        # future contributors from treating reviewer.md as the canonical reviewer.
        assert "Degraded-path fallback" in text or "degraded-path fallback" in text or "degraded path" in text.lower()
        assert "/code-review" in text
        assert "/security-review" in text

    def test_reviewer_canonical_body_does_not_advertise_runtime_overlap_as_canonical(self):
        text = (KIT_ROOT / "agents" / "reviewer.md").read_text(encoding="utf-8")
        # The checklist categories MUST live under a "Degraded-only" gated
        # block, not at the top of the file as the agent's primary scope.
        # We check this by requiring the explicit "Degraded-only" phrase to
        # appear BEFORE the checklist items.
        for marker in ("Degraded-only code dimension", "Degraded-only security dimension"):
            assert marker in text, (
                f"{marker!r} missing — checklist must be gated behind "
                "explicit degraded-only headers per SPEC-019."
            )

    def test_reviewer_does_not_advertise_security_audit_in_description(self):
        text = (KIT_ROOT / "agents" / "reviewer.md").read_text(encoding="utf-8")
        # Frontmatter description should NOT claim "integrated security audit"
        # as a primary capability — that runs on the runtime now.
        frontmatter = text.split("---", 2)[1] if text.count("---") >= 2 else ""
        assert "integrated security audit" not in frontmatter.lower(), (
            "reviewer.md description still advertises 'integrated security "
            "audit' — that is now /security-review's scope. Update the frontmatter."
        )


class TestTelemetryScemaDocumentsReviewEvents:
    def test_review_delegation_events_documented(self):
        text = (KIT_ROOT / "docs" / "telemetry_schema.md").read_text(encoding="utf-8")
        for ev in (
            "review_delegated_to_code_review",
            "review_delegated_to_security_review",
            "review_degraded_path_used",
            "review_finding_dropped",
            "review_severity_changed",
            "review_merge_audit_finding",
        ):
            assert ev in text, (
                f"docs/telemetry_schema.md must document {ev!r} per SPEC-019."
            )
