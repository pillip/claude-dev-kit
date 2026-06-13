"""Unit tests for scripts/spec_gate.py — covers every row of the decision table."""

import json
from pathlib import Path

import pytest

from scripts.spec_gate import decide, main, parse_issue, scan_signals


def _issue_block(
    num: str = "007",
    spec_required: str = "false",
    spec_path: str = "none",
    estimate: str = "1d",
    status: str = "doing",
    extra_body: str = "",
) -> str:
    return f"""### ISSUE-{num}: Sample task
- Track: platform
- PRD-Ref: FR-1
- Priority: P1
- Estimate: {estimate}
- Status: {status}
- Spec-Required: {spec_required}
- Spec: {spec_path}
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
{extra_body if extra_body else "Add feature X."}

#### Scope (In/Out)
- In: stuff
- Out: nothing
"""


def _write_issues(tmp_path: Path, blocks: list[str]) -> Path:
    p = tmp_path / "issues.md"
    p.write_text("\n\n".join(blocks), encoding="utf-8")
    return p


class TestParseIssue:
    def test_finds_issue(self, tmp_path: Path):
        p = _write_issues(tmp_path, [_issue_block()])
        issue = parse_issue(p, "ISSUE-007")
        assert issue is not None
        assert issue["estimate"] == "1d"
        assert issue["spec_required"] == "false"

    def test_returns_none_when_missing(self, tmp_path: Path):
        p = _write_issues(tmp_path, [_issue_block()])
        assert parse_issue(p, "ISSUE-999") is None


class TestScanSignals:
    def test_detects_api_keyword(self):
        sigs = scan_signals("This changes the API surface")
        assert any(s["signal"] == "API surface" for s in sigs)

    def test_detects_schema_and_migration(self):
        sigs = scan_signals("Adds a new schema and a migration step")
        labels = {s["signal"] for s in sigs}
        assert "schema" in labels
        assert "migration" in labels

    def test_detects_estimate_at_cap(self):
        body = "- Estimate: 1.5d\n"
        sigs = scan_signals(body)
        assert any("1.5d cap" in s["signal"] for s in sigs)

    def test_no_signals_on_clean_body(self):
        sigs = scan_signals("Rename a variable in a single function.")
        assert sigs == []


class TestDecideTable:
    """One test per row of the decision table from conversation 2026-06-13."""

    def _gate(self, tmp_path, **issue_kwargs):
        sprint = issue_kwargs.pop("sprint", False)
        skip = issue_kwargs.pop("skip", False)
        block = _issue_block(**issue_kwargs)
        p = _write_issues(tmp_path, [block])
        issue = parse_issue(p, f"ISSUE-{issue_kwargs.get('num', '007')}")
        assert issue is not None
        return decide(issue, p.resolve().parent, sprint_mode=sprint, skip_gate=skip)

    # Row 1: sprint + Spec-Required=true + SPEC exists → proceed
    def test_sprint_required_with_spec(self, tmp_path: Path):
        specs = tmp_path / "docs" / "specs"
        specs.mkdir(parents=True)
        (specs / "SPEC-007.md").write_text("# SPEC-007", encoding="utf-8")
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="docs/specs/SPEC-007.md",
            sprint=True,
        )
        assert result["decision"] == "proceed"

    # Row 2: sprint + Spec-Required=true + SPEC missing → auto_spec
    def test_sprint_required_no_spec(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="none",
            sprint=True,
        )
        assert result["decision"] == "auto_spec"

    # Row 3: sprint + Spec-Required=false + signals → proceed (with recommendation)
    def test_sprint_signals_only(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="false",
            spec_path="none",
            extra_body="Adds an API schema migration.",
            sprint=True,
        )
        assert result["decision"] == "proceed"
        assert len(result["signals"]) >= 1

    # Row 4: sprint + Spec-Required=false + no signals → proceed (silent)
    def test_sprint_no_signal_no_required(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="false",
            spec_path="none",
            extra_body="Rename a function in one file.",
            sprint=True,
        )
        assert result["decision"] == "proceed"
        assert result["signals"] == []

    # Row 5: non-sprint + Spec-Required=true + SPEC missing → hold
    def test_nonsprint_required_no_spec(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="none",
            sprint=False,
        )
        assert result["decision"] == "hold"

    # Row 6: non-sprint + Spec-Required=true + SPEC exists → proceed
    def test_nonsprint_required_with_spec(self, tmp_path: Path):
        specs = tmp_path / "docs" / "specs"
        specs.mkdir(parents=True)
        (specs / "SPEC-007.md").write_text("# SPEC-007", encoding="utf-8")
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="docs/specs/SPEC-007.md",
            sprint=False,
        )
        assert result["decision"] == "proceed"

    # Row 7: non-sprint + Spec-Required=false + signals → hold (no default)
    def test_nonsprint_signals_only(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="false",
            spec_path="none",
            extra_body="Touches the API protocol and adds a migration.",
            sprint=False,
        )
        assert result["decision"] == "hold"
        assert len(result["signals"]) >= 2

    # Row 8: non-sprint + Spec-Required=false + no signals → proceed (silent)
    def test_nonsprint_no_signal(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="false",
            spec_path="none",
            extra_body="Rename a variable.",
            sprint=False,
        )
        assert result["decision"] == "proceed"

    # Row 9: any mode + --skip-spec-gate → bypassed
    @pytest.mark.parametrize("sprint", [True, False])
    def test_skip_gate_bypasses(self, tmp_path: Path, sprint: bool):
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="none",
            sprint=sprint,
            skip=True,
        )
        assert result["decision"] == "bypassed"


class TestMainCli:
    def test_emits_json_decision(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        p = _write_issues(tmp_path, [_issue_block()])
        rc = main(["ISSUE-007", "--issues-md", str(p)])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert "decision" in out
        assert out["issue_id"] == "ISSUE-007"

    def test_invalid_issue_id_exits_2(self, tmp_path: Path):
        p = _write_issues(tmp_path, [_issue_block()])
        rc = main(["not-an-id", "--issues-md", str(p)])
        assert rc == 2

    def test_missing_issue_exits_2(self, tmp_path: Path):
        p = _write_issues(tmp_path, [_issue_block()])
        rc = main(["ISSUE-999", "--issues-md", str(p)])
        assert rc == 2

    def test_force_sprint_mode_flag(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        # Spec-Required=true with no SPEC, force-sprint → auto_spec.
        p = _write_issues(
            tmp_path,
            [_issue_block(spec_required="true", spec_path="none")],
        )
        rc = main(
            ["ISSUE-007", "--issues-md", str(p), "--force-sprint-mode"]
        )
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["decision"] == "auto_spec"
        assert out["sprint_mode"] is True
