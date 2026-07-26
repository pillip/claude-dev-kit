"""ISSUE-002: LLM-as-judge review eval — pure-function + wiring tests.

The judge invocation itself (`claude -p`) is not exercised here; these tests
pin the rubric contract, verdict parsing/derivation, determinism math, report
rendering, degraded mode, and the /ship advisory wiring.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import eval_review as ev  # noqa: E402


# ── Rubric ────────────────────────────────────────────────────────────

def test_rubric_exists_with_all_dimensions():
    text = ev.load_rubric()
    for d in ev.REQUIRED_DIMENSIONS:
        assert f"### {d}" in text


def test_rubric_loader_rejects_missing_dimension(tmp_path):
    bad = tmp_path / "rubric.md"
    bad.write_text("### coverage\nonly one dimension\n", encoding="utf-8")
    try:
        ev.load_rubric(bad)
        assert False, "should have raised on missing dimensions"
    except ValueError as e:
        assert "false_positive_rate" in str(e)


# ── Verdict parsing / derivation ──────────────────────────────────────

GOOD = {
    "scores": {"coverage": 5, "false_positive_rate": 5, "actionability": 4, "traceability": 5},
    "verdict": "pass", "missed_findings": [], "concerns": [],
}
MISSING_CRIT = {
    "scores": {"coverage": 2, "false_positive_rate": 5, "actionability": 4, "traceability": 4},
    "verdict": "pass",  # judge said pass, but a High was missed → must derive concerns
    "missed_findings": [
        {"severity": "High", "title": "unchecked auth", "diff_ref": "api.py:20-24",
         "rubric": "coverage", "evidence": "no permission check on the new route"}
    ],
    "concerns": [],
}


def test_parse_good_review_scores_pass():
    v = ev.parse_verdict(json.dumps(GOOD))
    assert v["verdict"] == "pass"


def test_parse_missing_critical_derives_concerns():
    # Even though the judge JSON said "pass", a missed High forces "concerns".
    v = ev.parse_verdict(json.dumps(MISSING_CRIT))
    assert v["verdict"] == "concerns"
    assert ev.high_finding_keys(v) == {"High::api.py:20-24"}


def test_parse_tolerates_json_fences_and_prose():
    raw = "Here is my verdict:\n```json\n" + json.dumps(GOOD) + "\n```\nDone."
    assert ev.parse_verdict(raw)["verdict"] == "pass"


def test_parse_rejects_non_numeric_scores():
    bad = {"scores": {"coverage": "high", "false_positive_rate": 5,
                      "actionability": 4, "traceability": 4}}
    try:
        ev.parse_verdict(json.dumps(bad))
        assert False
    except ValueError as e:
        assert "coverage" in str(e)


def test_low_dimension_score_forces_concerns():
    obj = json.loads(json.dumps(GOOD))
    obj["scores"]["traceability"] = 1
    assert ev.parse_verdict(json.dumps(obj))["verdict"] == "concerns"


# ── Determinism math ──────────────────────────────────────────────────

def test_overlap_both_empty_is_full_agreement():
    assert ev.overlap_ratio(set(), set()) == 1.0


def test_overlap_partial():
    a = {"High::a.py:1", "Critical::b.py:2"}
    b = {"High::a.py:1"}
    assert ev.overlap_ratio(a, b) == 0.5


# ── Report rendering ──────────────────────────────────────────────────

def test_render_report_has_verdict_scores_and_sections():
    v = ev.parse_verdict(json.dumps(MISSING_CRIT))
    md = ev.render_report("42", v, determinism=0.8)
    assert "# Review Eval — PR #42" in md
    assert "**Verdict:** concerns" in md
    assert "unchecked auth" in md and "api.py:20-24" in md
    assert "80%" in md
    for d in ev.REQUIRED_DIMENSIONS:
        assert d in md


def test_render_report_no_findings():
    v = ev.parse_verdict(json.dumps(GOOD))
    md = ev.render_report("7", v, determinism=None)
    assert "## Missed findings\n_None._" in md


# ── Degraded mode / CLI wiring ────────────────────────────────────────

def test_main_degraded_when_cli_absent(monkeypatch, capsys, tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text("## Code Review\n_No findings._\n", encoding="utf-8")
    monkeypatch.setattr(ev, "cli_available", lambda: False)
    rc = ev.main(["--pr", "1", "--notes", str(notes)])
    assert rc == 0
    assert "eval skipped: claude CLI not available" in capsys.readouterr().err


def test_main_degraded_when_notes_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(ev, "cli_available", lambda: True)
    rc = ev.main(["--pr", "1", "--notes", str(tmp_path / "nope.md")])
    assert rc == 0
    assert "review notes not found" in capsys.readouterr().err


def test_main_writes_report_with_mocked_judge(monkeypatch, tmp_path, capsys):
    notes = tmp_path / "notes.md"
    notes.write_text("## Code Review\n- **[High] real bug**\n", encoding="utf-8")
    monkeypatch.setattr(ev, "cli_available", lambda: True)
    monkeypatch.setattr(ev, "get_pr_diff", lambda pr: "diff --git a/x b/x\n+bug")
    monkeypatch.setattr(ev, "run_judge", lambda prompt, model: json.dumps(GOOD))
    out = tmp_path / "eval.md"
    rc = ev.main(["--pr", "9", "--notes", str(notes), "--out", str(out)])
    assert rc == 0
    assert out.exists() and "Verdict:** pass" in out.read_text()
    assert "eval: pass" in capsys.readouterr().out


def test_main_never_blocks_on_judge_error(monkeypatch, tmp_path, capsys):
    notes = tmp_path / "notes.md"
    notes.write_text("## Code Review\n", encoding="utf-8")
    monkeypatch.setattr(ev, "cli_available", lambda: True)
    monkeypatch.setattr(ev, "get_pr_diff", lambda pr: "diff")
    def boom(prompt, model):
        raise RuntimeError("judge exploded")
    monkeypatch.setattr(ev, "run_judge", boom)
    rc = ev.main(["--pr", "9", "--notes", str(notes)])
    assert rc == 0  # advisory: never fails the ship
    assert "eval skipped: judge exploded" in capsys.readouterr().err


def test_determinism_overlap_across_two_runs(monkeypatch, tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text("## Code Review\n", encoding="utf-8")
    monkeypatch.setattr(ev, "get_pr_diff", lambda pr: "diff")
    outputs = iter([json.dumps(MISSING_CRIT), json.dumps(MISSING_CRIT)])
    monkeypatch.setattr(ev, "run_judge", lambda prompt, model: next(outputs))
    v = ev.evaluate("9", notes, model=None, runs=2)
    assert v["_determinism"] == 1.0  # identical high findings both runs


# ── /ship advisory wiring ─────────────────────────────────────────────

def test_ship_skill_wires_non_blocking_eval():
    text = (ROOT / "skills" / "ship" / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/eval_review.py" in text
    assert "non-blocking" in text.lower()
    assert "no separate billing" in text.lower()
