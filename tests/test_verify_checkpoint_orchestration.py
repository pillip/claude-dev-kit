"""Unit tests for the ISSUE-057 orchestration/design skill checkpoints.

Covers the new verify_checkpoint.py phases for kickoff, scan, and the
uiux family (uiux / mobile-uiux / desktop-uiux):

- TC-057a (AC-1): full-artifact fixtures pass; one missing file/section fails
  and the failure output NAMES the missing artifact.
- TC-057b (AC-2): every ``**CHECKPOINT`` block in the five generated SKILL.md
  files carries a ``checkpoint.sh`` invocation.
- TC-057c (AC-3): scan's conditional data-model phase reports skip (not fail)
  on a fixture without database usage.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_checkpoint as vc  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────


@pytest.fixture()
def repo_root(tmp_path, monkeypatch):
    """Patch _repo_root to a tmp fixture root with an empty docs/ dir."""
    monkeypatch.setattr(vc, "_repo_root", lambda: tmp_path)
    (tmp_path / "docs").mkdir()
    return tmp_path


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


PRD_DIGEST_FULL = """# PRD Digest

## Goals
Ship the thing.

## Target User
Kit developers.

## Must-have Features
1. Feature one.

## Key NFRs
1. p95 < 200ms.

## Scope Boundaries
In: core. Out: extras.
"""

KICKOFF_REQUIREMENTS_FULL = """# Requirements

## Goals
G1.

## User Stories
US-001: As a user ...

## NFRs
NFR-001: p95 < 200ms.
"""

SCAN_REQUIREMENTS_FULL = """# Requirements (scan)

## Goals
G1. [INFERRED]

## Functional Requirements
FR-001: parses manifests. [CONFIRMED]

## NFRs
NFR-001: startup < 2s. [INFERRED]
"""

UX_SPEC_FULL = """# UX Spec

## Key Flows
Login flow.

## Screen Inventory
Screen: Home — 5 states.
"""

ARCHITECTURE_FULL = """# Architecture

## Tech Stack
Python 3.11.

## Modules
- core
"""

DATA_MODEL_FULL = """# Data Model

## Schema
| table | column | type |
|-------|--------|------|
| users | id     | int  |
"""

ISSUES_KICKOFF_FULL = """# Issues

### ISSUE-001: Do the thing
- Priority: P1
- Status: backlog

#### Acceptance Criteria (DoD)
- [ ] Given X, when Y, then Z.
"""

ISSUES_SCAN_FULL = """# Issues

### ISSUE-001: Fix the gap
- Priority: P1
- Evidence: src/foo.py:12

#### Acceptance Criteria (DoD)
- [ ] Given X, when Y, then Z.
"""

TEST_PLAN_KICKOFF_FULL = """# Test Plan

## Strategy
Risk-based.

## Critical Flows
1. Login.
"""

TEST_PLAN_SCAN_FULL = """# Test Plan (scan)

## Current State Assessment
12 tests exist.

## Risk Matrix
| Flow | Likelihood | Impact | Risk | Coverage |
|------|-----------|--------|------|----------|
| auth | High | High | Critical | unit |
"""

PHILOSOPHY_FULL = """# Design Philosophy

Named aesthetic: Ink Ledger.

## Signature Move
All primary CTAs cast `box-shadow: -8px 16px 0 var(--accent)`.

## Reference Anchors
- cue: warm cream ground `#F4F1EA` — docs/references/a.png
literal_quote: "47.2-A" — order id on the detail screen
"""

PHILOSOPHY_SKIPPED_ANCHORS = """# Design Philosophy

## Signature Move
Every card uses `border-radius: 14px 4px 14px 4px`.

Reference Anchors skipped (no image input).
"""


# ── kickoff ──────────────────────────────────────────────────────────


class TestKickoffPrdDigest:
    def test_full_fixture_passes(self, repo_root, capsys):
        _write(repo_root, "docs/prd_digest.md", PRD_DIGEST_FULL)
        assert vc.VERIFIERS[("kickoff", "prd-digest")]("-") is True
        assert "PASS" in capsys.readouterr().out

    def test_missing_file_fails_naming_it(self, repo_root, capsys):
        assert vc.VERIFIERS[("kickoff", "prd-digest")]("-") is False
        assert "prd_digest.md" in capsys.readouterr().out

    def test_missing_section_fails_naming_it(self, repo_root, capsys):
        content = PRD_DIGEST_FULL.replace("## Scope Boundaries", "## Elsewhere")
        content = content.replace("In: core. Out: extras.", "nothing")
        _write(repo_root, "docs/prd_digest.md", content)
        assert vc.VERIFIERS[("kickoff", "prd-digest")]("-") is False
        assert "Scope Boundaries" in capsys.readouterr().out


class TestKickoffRequirements:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "docs/requirements.md", KICKOFF_REQUIREMENTS_FULL)
        assert vc.VERIFIERS[("kickoff", "requirements")]("-") is True

    def test_missing_file_fails_naming_it(self, repo_root, capsys):
        assert vc.VERIFIERS[("kickoff", "requirements")]("-") is False
        assert "requirements.md" in capsys.readouterr().out

    def test_missing_user_stories_fails_naming_it(self, repo_root, capsys):
        content = KICKOFF_REQUIREMENTS_FULL.replace("## User Stories", "## Items")
        content = content.replace("US-001: As a user ...", "none")
        _write(repo_root, "docs/requirements.md", content)
        assert vc.VERIFIERS[("kickoff", "requirements")]("-") is False
        assert "User Stories" in capsys.readouterr().out


class TestKickoffUxArchitecture:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "docs/ux_spec.md", UX_SPEC_FULL)
        _write(repo_root, "docs/architecture.md", ARCHITECTURE_FULL)
        assert vc.VERIFIERS[("kickoff", "ux-architecture")]("-") is True

    def test_missing_architecture_fails_naming_it(self, repo_root, capsys):
        _write(repo_root, "docs/ux_spec.md", UX_SPEC_FULL)
        assert vc.VERIFIERS[("kickoff", "ux-architecture")]("-") is False
        assert "architecture.md" in capsys.readouterr().out

    def test_ux_spec_without_screens_fails_naming_term(self, repo_root, capsys):
        _write(repo_root, "docs/ux_spec.md", "## Key Flows\nLogin flow only.\n")
        _write(repo_root, "docs/architecture.md", ARCHITECTURE_FULL)
        assert vc.VERIFIERS[("kickoff", "ux-architecture")]("-") is False
        assert "Screen" in capsys.readouterr().out


class TestKickoffDataModel:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "docs/data_model.md", DATA_MODEL_FULL)
        assert vc.VERIFIERS[("kickoff", "data-model")]("-") is True

    def test_missing_file_fails_naming_it(self, repo_root, capsys):
        assert vc.VERIFIERS[("kickoff", "data-model")]("-") is False
        assert "data_model.md" in capsys.readouterr().out

    def test_missing_schema_fails_naming_it(self, repo_root, capsys):
        _write(repo_root, "docs/data_model.md", "# Data Model\n\njust prose\n")
        assert vc.VERIFIERS[("kickoff", "data-model")]("-") is False
        assert "Schema" in capsys.readouterr().out


class TestKickoffPlanning:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "issues.md", ISSUES_KICKOFF_FULL)
        _write(repo_root, "docs/test_plan.md", TEST_PLAN_KICKOFF_FULL)
        assert vc.VERIFIERS[("kickoff", "planning")]("-") is True

    def test_no_issue_blocks_fails(self, repo_root, capsys):
        _write(repo_root, "issues.md", "# Issues\n\nnothing here\n")
        _write(repo_root, "docs/test_plan.md", TEST_PLAN_KICKOFF_FULL)
        assert vc.VERIFIERS[("kickoff", "planning")]("-") is False
        assert "ISSUE-" in capsys.readouterr().out

    def test_missing_critical_flows_fails_naming_it(self, repo_root, capsys):
        _write(repo_root, "issues.md", ISSUES_KICKOFF_FULL)
        plan = TEST_PLAN_KICKOFF_FULL.replace("## Critical Flows", "## Flows")
        plan = plan.replace("1. Login.", "none")
        _write(repo_root, "docs/test_plan.md", plan)
        assert vc.VERIFIERS[("kickoff", "planning")]("-") is False
        assert "Critical Flows" in capsys.readouterr().out

    def test_missing_issues_md_fails_naming_it(self, repo_root, capsys):
        _write(repo_root, "docs/test_plan.md", TEST_PLAN_KICKOFF_FULL)
        assert vc.VERIFIERS[("kickoff", "planning")]("-") is False
        assert "issues.md" in capsys.readouterr().out


# ── scan ─────────────────────────────────────────────────────────────


class TestScanPrdDigest:
    def test_shares_kickoff_contract(self, repo_root):
        _write(repo_root, "docs/prd_digest.md", PRD_DIGEST_FULL)
        assert vc.VERIFIERS[("scan", "prd-digest")]("-") is True

    def test_missing_file_fails(self, repo_root):
        assert vc.VERIFIERS[("scan", "prd-digest")]("-") is False


class TestScanRequirements:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "docs/requirements.md", SCAN_REQUIREMENTS_FULL)
        assert vc.VERIFIERS[("scan", "requirements")]("-") is True

    def test_missing_functional_requirements_fails_naming_it(self, repo_root, capsys):
        content = SCAN_REQUIREMENTS_FULL.replace(
            "## Functional Requirements", "## Features"
        )
        _write(repo_root, "docs/requirements.md", content)
        assert vc.VERIFIERS[("scan", "requirements")]("-") is False
        assert "Functional Requirements" in capsys.readouterr().out


class TestScanArchitecture:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "docs/architecture.md", ARCHITECTURE_FULL)
        assert vc.VERIFIERS[("scan", "architecture")]("-") is True

    def test_missing_file_fails_naming_it(self, repo_root, capsys):
        assert vc.VERIFIERS[("scan", "architecture")]("-") is False
        assert "architecture.md" in capsys.readouterr().out


class TestScanDataModelConditional:
    """AC-3: skip (not fail) when no database usage is detected."""

    def test_no_db_fixture_reports_skip(self, repo_root, capsys):
        # No data_model.md, no DB indicators anywhere in the fixture.
        assert vc.VERIFIERS[("scan", "data-model")]("-") is True
        out = capsys.readouterr().out
        assert "SKIP" in out.upper()
        assert "FAIL" not in out

    def test_db_detected_but_doc_missing_fails_naming_it(self, repo_root, capsys):
        _write(repo_root, "requirements.txt", "sqlalchemy==2.0.30\n")
        assert vc.VERIFIERS[("scan", "data-model")]("-") is False
        assert "data_model.md" in capsys.readouterr().out

    def test_migrations_dir_counts_as_db_indicator(self, repo_root, capsys):
        (repo_root / "migrations").mkdir()
        assert vc.VERIFIERS[("scan", "data-model")]("-") is False
        assert "data_model.md" in capsys.readouterr().out

    def test_doc_present_with_schema_passes(self, repo_root):
        _write(repo_root, "requirements.txt", "sqlalchemy==2.0.30\n")
        _write(repo_root, "docs/data_model.md", DATA_MODEL_FULL)
        assert vc.VERIFIERS[("scan", "data-model")]("-") is True

    def test_doc_present_without_schema_fails_naming_it(self, repo_root, capsys):
        _write(repo_root, "docs/data_model.md", "# Data Model\n\nprose only\n")
        assert vc.VERIFIERS[("scan", "data-model")]("-") is False
        assert "Schema" in capsys.readouterr().out


class TestScanTestPlan:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "docs/test_plan.md", TEST_PLAN_SCAN_FULL)
        assert vc.VERIFIERS[("scan", "test-plan")]("-") is True

    def test_missing_risk_matrix_fails_naming_it(self, repo_root, capsys):
        content = TEST_PLAN_SCAN_FULL.replace("## Risk Matrix", "## Risks")
        _write(repo_root, "docs/test_plan.md", content)
        assert vc.VERIFIERS[("scan", "test-plan")]("-") is False
        assert "Risk Matrix" in capsys.readouterr().out


class TestScanIssues:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "issues.md", ISSUES_SCAN_FULL)
        assert vc.VERIFIERS[("scan", "issues")]("-") is True

    def test_missing_evidence_fails_naming_it(self, repo_root, capsys):
        _write(repo_root, "issues.md", ISSUES_KICKOFF_FULL)  # no Evidence field
        assert vc.VERIFIERS[("scan", "issues")]("-") is False
        assert "Evidence" in capsys.readouterr().out

    def test_missing_file_fails_naming_it(self, repo_root, capsys):
        assert vc.VERIFIERS[("scan", "issues")]("-") is False
        assert "issues.md" in capsys.readouterr().out


# ── uiux family: philosophy (fragment checkpoint, presence-level) ────


class TestUiuxPhilosophy:
    def test_full_fixture_passes(self, repo_root):
        _write(repo_root, "docs/design_philosophy.md", PHILOSOPHY_FULL)
        assert vc.VERIFIERS[("uiux", "philosophy")]("-") is True

    def test_missing_file_fails_naming_it(self, repo_root, capsys):
        assert vc.VERIFIERS[("uiux", "philosophy")]("-") is False
        assert "design_philosophy.md" in capsys.readouterr().out

    def test_missing_signature_move_fails_naming_it(self, repo_root, capsys):
        content = PHILOSOPHY_FULL.replace("Signature Move", "Big Idea")
        _write(repo_root, "docs/design_philosophy.md", content)
        assert vc.VERIFIERS[("uiux", "philosophy")]("-") is False
        assert "Signature Move" in capsys.readouterr().out

    def test_no_anchors_and_no_skip_line_fails(self, repo_root, capsys):
        _write(
            repo_root,
            "docs/design_philosophy.md",
            "## Signature Move\n`translateY(-2px)` on hover.\n",
        )
        assert vc.VERIFIERS[("uiux", "philosophy")]("-") is False
        assert "Reference Anchors" in capsys.readouterr().out

    def test_skip_line_passes_without_literal_quote(self, repo_root):
        _write(repo_root, "docs/design_philosophy.md", PHILOSOPHY_SKIPPED_ANCHORS)
        assert vc.VERIFIERS[("uiux", "philosophy")]("-") is True

    def test_anchors_without_literal_quote_fails_naming_it(self, repo_root, capsys):
        content = PHILOSOPHY_FULL.replace(
            'literal_quote: "47.2-A" — order id on the detail screen', ""
        )
        _write(repo_root, "docs/design_philosophy.md", content)
        assert vc.VERIFIERS[("uiux", "philosophy")]("-") is False
        assert "literal_quote" in capsys.readouterr().out

    @pytest.mark.parametrize("skill", ["mobile-uiux", "desktop-uiux"])
    def test_shared_across_uiux_family(self, skill, repo_root):
        _write(repo_root, "docs/design_philosophy.md", PHILOSOPHY_FULL)
        assert vc.VERIFIERS[(skill, "philosophy")]("-") is True


# ── uiux family: system docs (with extend-mode alternate) ────────────


class TestUiuxSystem:
    WEB_DOCS = ["design_system.md", "wireframes.md", "interactions.md", "copy_guide.md"]

    def _write_all(self, root, names):
        for name in names:
            _write(root, f"docs/{name}", f"# {name}\ncontent\n")

    def test_all_docs_pass(self, repo_root):
        self._write_all(repo_root, self.WEB_DOCS)
        assert vc.VERIFIERS[("uiux", "system")]("-") is True

    def test_missing_doc_fails_naming_it(self, repo_root, capsys):
        self._write_all(repo_root, self.WEB_DOCS[:-1])  # no copy_guide.md
        assert vc.VERIFIERS[("uiux", "system")]("-") is False
        assert "copy_guide.md" in capsys.readouterr().out

    def test_extend_mode_extracted_alternate_accepted(self, repo_root):
        # extend mode "write alongside": design_system.extracted.md instead
        self._write_all(
            repo_root,
            ["design_system.extracted.md", "wireframes.md", "interactions.md", "copy_guide.md"],
        )
        assert vc.VERIFIERS[("uiux", "system")]("-") is True

    def test_mobile_system_docs(self, repo_root):
        self._write_all(
            repo_root,
            ["design_system_mobile.md", "wireframes_mobile.md", "interactions_mobile.md", "copy_guide.md"],
        )
        assert vc.VERIFIERS[("mobile-uiux", "system")]("-") is True

    def test_mobile_extracted_alternate_accepted(self, repo_root):
        self._write_all(
            repo_root,
            ["design_system_mobile.extracted.md", "wireframes_mobile.md", "interactions_mobile.md", "copy_guide.md"],
        )
        assert vc.VERIFIERS[("mobile-uiux", "system")]("-") is True

    def test_desktop_system_docs(self, repo_root):
        self._write_all(
            repo_root,
            ["design_system_desktop.md", "wireframes_desktop.md", "interactions_desktop.md", "copy_guide.md"],
        )
        assert vc.VERIFIERS[("desktop-uiux", "system")]("-") is True

    def test_desktop_missing_doc_fails_naming_it(self, repo_root, capsys):
        self._write_all(
            repo_root,
            ["design_system_desktop.md", "wireframes_desktop.md", "copy_guide.md"],
        )
        assert vc.VERIFIERS[("desktop-uiux", "system")]("-") is False
        assert "interactions_desktop.md" in capsys.readouterr().out


# ── registry / CLI wiring ────────────────────────────────────────────


NEW_PHASES = [
    ("kickoff", "prd-digest"),
    ("kickoff", "requirements"),
    ("kickoff", "ux-architecture"),
    ("kickoff", "data-model"),
    ("kickoff", "planning"),
    ("scan", "prd-digest"),
    ("scan", "requirements"),
    ("scan", "architecture"),
    ("scan", "data-model"),
    ("scan", "test-plan"),
    ("scan", "issues"),
    ("desktop-uiux", "context"),
    ("desktop-uiux", "philosophy"),
    ("desktop-uiux", "system"),
]


class TestRegistryAndCli:
    @pytest.mark.parametrize("key", NEW_PHASES, ids=lambda k: f"{k[0]}/{k[1]}")
    def test_phase_registered(self, key):
        assert key in vc.VERIFIERS

    @pytest.mark.parametrize("key", NEW_PHASES, ids=lambda k: f"{k[0]}/{k[1]}")
    def test_new_phases_are_blocking(self, key):
        # Conservative tiering (ISSUE-057): artifact presence = blocking.
        assert key not in vc.ADVISORY_PHASES

    def test_desktop_uiux_context_aliases_uiux_context(self):
        assert vc.VERIFIERS[("desktop-uiux", "context")] is vc.VERIFIERS[("uiux", "context")]

    def test_main_accepts_missing_issue_arg(self, monkeypatch):
        # kickoff/scan/uiux runs have no issue ID — --issue must be optional.
        monkeypatch.setitem(
            vc.VERIFIERS, ("kickoff", "prd-digest"), lambda issue_id, **_: True
        )
        rc = vc.main(["--skill", "kickoff", "--phase", "prd-digest"])
        assert rc == 0

    def test_main_blocking_failure_exits_nonzero(self, monkeypatch):
        monkeypatch.setitem(
            vc.VERIFIERS, ("scan", "issues"), lambda issue_id, **_: False
        )
        rc = vc.main(["--skill", "scan", "--phase", "issues"])
        assert rc == 1


# ── AC-2: generated SKILL.md checkpoint blocks carry invocations ─────


FIVE_SKILLS = ["kickoff", "scan", "uiux", "mobile-uiux", "desktop-uiux"]


class TestGeneratedSkillCheckpointInvocations:
    """Every ``**CHECKPOINT`` block heading in the five generated SKILL.md
    files must be followed by a ``checkpoint.sh`` invocation within 3 lines —
    no bare prose self-assertion remains (AC-2)."""

    @pytest.mark.parametrize("skill", FIVE_SKILLS)
    def test_every_checkpoint_block_has_invocation(self, skill):
        md = ROOT / "skills" / skill / "SKILL.md"
        lines = md.read_text(encoding="utf-8").splitlines()
        misses = []
        for i, line in enumerate(lines):
            if "**CHECKPOINT" not in line:
                continue
            window = "\n".join(lines[i : i + 4])
            if "checkpoint.sh" not in window:
                misses.append(f"line {i + 1}: {line.strip()}")
        assert not misses, f"{skill}: CHECKPOINT block(s) without checkpoint.sh: {misses}"

    @pytest.mark.parametrize("skill", FIVE_SKILLS)
    def test_at_least_one_checkpoint_block_exists(self, skill):
        # Guard against satisfying AC-2 by deleting all blocks.
        md = ROOT / "skills" / skill / "SKILL.md"
        assert "**CHECKPOINT" in md.read_text(encoding="utf-8")
