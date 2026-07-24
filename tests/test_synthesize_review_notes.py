import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import synthesize_review_notes as s  # noqa: E402


def _payload(**overrides):
    base = {
        "pr_number": "47",
        "code_findings": [
            {
                "severity": "High",
                "title": "Unhandled null in process_payment",
                "evidence": "src/payment.py:142 returns None when invoice is missing",
                "fix": "Check invoice presence before dereferencing.",
            }
        ],
        "security_findings": [
            {
                "severity": "Critical",
                "title": "SQL injection in /search endpoint",
                "evidence": "src/api/search.py:88 concatenates user input",
                "fix": "Use parameterized query.",
            }
        ],
        "code_source": "code-review",
        "security_source": "security-review",
        "ui_findings": None,
        "design_findings": None,
        "a11y_findings": None,
        "figma_findings": None,
    }
    base.update(overrides)
    return base


class TestRender:
    def test_full_runtime_path_with_findings(self):
        out = s.render(_payload())
        assert "# Review Notes — PR #47" in out
        assert "## Code Review" in out
        assert "## Security Findings" in out
        assert "_Source: code-review_" in out
        assert "_Source: security-review_" in out

    def test_kit_distinctive_sections_omitted_when_null(self):
        out = s.render(_payload())
        # null sections must not appear at all (vs. empty list which renders the no-finding literal)
        assert "## UI Review" not in out
        assert "## Design Audit" not in out
        assert "## Accessibility Audit" not in out
        assert "## Figma Compliance" not in out

    def test_kit_distinctive_section_rendered_when_present(self):
        payload = _payload(
            ui_findings=[
                {
                    "severity": "Medium",
                    "title": "Loading state missing on /list",
                    "evidence": "prototype/screens/list.html has no skeleton",
                }
            ]
        )
        out = s.render(payload)
        assert "## UI Review" in out
        assert "Loading state missing" in out

    def test_empty_runtime_section_renders_no_findings_literal(self):
        payload = _payload(code_findings=[])
        out = s.render(payload)
        # Code Review section present, but renders the no-findings literal
        assert "## Code Review" in out
        # Section header appears AND the literal appears in the section body
        code_section = out.split("## Code Review", 1)[1].split("## Security", 1)[0]
        assert s.NO_FINDINGS_LINE in code_section

    def test_severity_preserved_verbatim(self):
        payload = _payload()
        out = s.render(payload)
        assert "[High]" in out
        assert "[Critical]" in out

    def test_findings_sorted_by_severity_within_section(self):
        payload = _payload(
            code_findings=[
                {"severity": "Low", "title": "Low one", "evidence": "x"},
                {"severity": "Critical", "title": "Crit one", "evidence": "x"},
                {"severity": "Medium", "title": "Med one", "evidence": "x"},
                {"severity": "High", "title": "High one", "evidence": "x"},
            ]
        )
        out = s.render(payload)
        code_section = out.split("## Code Review", 1)[1].split("## Security", 1)[0]
        positions = {
            sev: code_section.index(f"[{sev}]")
            for sev in ("Critical", "High", "Medium", "Low")
        }
        assert positions["Critical"] < positions["High"] < positions["Medium"] < positions["Low"]

    def test_evidence_preserved_verbatim_including_specials(self):
        payload = _payload(
            code_findings=[
                {
                    "severity": "High",
                    "title": "Subtle bug",
                    "evidence": "Off-by-one on `idx + 1`: 17.4% regression in p95 — see profiler.csv:88",
                }
            ]
        )
        out = s.render(payload)
        assert "Off-by-one on `idx + 1`: 17.4% regression in p95 — see profiler.csv:88" in out

    def test_fix_field_optional(self):
        payload = _payload(
            code_findings=[
                {"severity": "Low", "title": "No fix needed", "evidence": "x"}
            ]
        )
        out = s.render(payload)
        # Should render without raising even though fix is absent
        assert "No fix needed" in out
        assert "Fix:" not in out.split("No fix needed", 1)[1].split("##", 1)[0]

    def test_mixed_mode_source_labels(self):
        payload = _payload(
            code_source="code-review",
            security_source="reviewer-degraded",
        )
        out = s.render(payload)
        assert "_Source: code-review_" in out
        assert "_Source: reviewer-degraded_" in out


class TestValidation:
    def test_missing_code_findings_raises(self):
        payload = {"security_findings": []}
        with pytest.raises(ValueError, match="code_findings"):
            s.render(payload)

    def test_unknown_severity_raises(self):
        payload = _payload(
            code_findings=[
                {"severity": "Catastrophic", "title": "x", "evidence": "y"}
            ]
        )
        with pytest.raises(ValueError, match="severity"):
            s.render(payload)

    def test_missing_title_raises(self):
        payload = _payload(
            code_findings=[{"severity": "High", "evidence": "y"}]
        )
        with pytest.raises(ValueError, match="title"):
            s.render(payload)

    def test_missing_evidence_raises(self):
        payload = _payload(
            code_findings=[{"severity": "High", "title": "x"}]
        )
        with pytest.raises(ValueError, match="evidence"):
            s.render(payload)

    def test_kit_distinctive_list_only(self):
        # Non-list value for an optional section should be rejected
        payload = _payload(ui_findings="this should be a list")
        with pytest.raises(ValueError, match="ui_findings"):
            s.render(payload)


class TestCli:
    def test_main_writes_to_out(self, tmp_path, monkeypatch):
        input_path = tmp_path / "in.json"
        input_path.write_text(json.dumps(_payload()))
        out_path = tmp_path / "review_notes" / "47.md"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "synthesize_review_notes.py",
                "--input",
                str(input_path),
                "--out",
                str(out_path),
            ],
        )
        code = s.main()
        assert code == 0
        assert out_path.read_text().startswith("# Review Notes — PR #47")

    def test_main_returns_2_on_bad_input(self, tmp_path, monkeypatch, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"security_findings": []}))
        monkeypatch.setattr(
            sys, "argv", ["synthesize_review_notes.py", "--input", str(bad)]
        )
        code = s.main()
        assert code == 2
        err = capsys.readouterr().err
        assert "Input validation failed" in err
