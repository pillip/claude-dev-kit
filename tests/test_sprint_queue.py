"""Unit tests for scripts/sprint_queue.py."""

import functools
import json
import re
import subprocess
from pathlib import Path

import pytest

import scripts.sprint_queue as sq
from scripts.sprint_queue import (
    _gh_pr_merge_state,
    choose_action,
    classify_ship_ready,
    compute_queues,
    main,
    parse_issues_metadata,
    parse_sprint_table,
    ship_merge_decision,
    validate_transitions,
)


# ── Fixtures ────────────────────────────────────────────────────────


def _make_sprint_state(rows: list[tuple[str, str, str, str, str]]) -> str:
    """Build sprint_state.md content.

    Each row: (issue, status, attempts, last_error, phase).
    """
    lines = [
        "# Sprint State\n",
        "## Meta",
        "- Started: 2025-01-01",
        "- Iteration: 1 / 20",
        "- Parallel: 3",
        "- Status: running\n",
        "## Issue Progress",
        "| Issue | Status | Attempts | Last Error | Phase |",
        "|-------|--------|----------|------------|-------|",
    ]
    for issue, status, attempts, last_error, phase in rows:
        lines.append(f"| {issue} | {status} | {attempts} | {last_error} | {phase} |")
    lines.append("")
    lines.append("## Discovered Issues")
    lines.append("")
    lines.append("## Escalations")
    return "\n".join(lines) + "\n"


def _make_issue(
    num: str = "001",
    title: str = "Do something",
    priority: str = "P1",
    status: str = "backlog",
    depends_on: str = "none",
    manual: str = "",
) -> str:
    """Build a minimal issue markdown block."""
    manual_line = f"\n- Manual: {manual}" if manual else ""
    return f"""### ISSUE-{num}: {title}
- Track: product
- Priority: {priority}
- Status: {status}
- Depends-On: {depends_on}{manual_line}

#### Acceptance Criteria (DoD)
- [ ] Given something, when action, then result
- [ ] Given another, when action, then result
"""


# ── TestParseSprintTable ────────────────────────────────────────────


class TestParseSprintTable:
    def test_parses_standard_table(self):
        text = _make_sprint_state([
            ("ISSUE-001", "active", "1", "—", "implemented"),
            ("ISSUE-002", "active", "0", "—", "backlog"),
        ])
        rows = parse_sprint_table(text)
        assert len(rows) == 2
        assert rows[0]["issue"] == "ISSUE-001"
        assert rows[0]["phase"] == "implemented"
        assert rows[1]["issue"] == "ISSUE-002"
        assert rows[1]["phase"] == "backlog"

    def test_handles_empty_table(self):
        text = _make_sprint_state([])
        rows = parse_sprint_table(text)
        assert rows == []

    def test_strips_whitespace_from_cells(self):
        text = _make_sprint_state([
            ("  ISSUE-001  ", "active", "1", "—", "  implemented  "),
        ])
        rows = parse_sprint_table(text)
        assert rows[0]["issue"] == "ISSUE-001"
        assert rows[0]["phase"] == "implemented"

    def test_handles_missing_section(self):
        text = "# Sprint State\n## Meta\n- Status: running\n"
        rows = parse_sprint_table(text)
        assert rows == []

    def test_lowercases_phase_and_status(self):
        text = _make_sprint_state([
            ("ISSUE-001", "Active", "0", "—", "Implemented"),
        ])
        rows = parse_sprint_table(text)
        assert rows[0]["status"] == "active"
        assert rows[0]["phase"] == "implemented"


# ── TestParseIssuesMetadata ─────────────────────────────────────────


class TestParseIssuesMetadata:
    def test_parses_basic_metadata(self):
        text = _make_issue(num="001", priority="P0", depends_on="ISSUE-002")
        meta = parse_issues_metadata(text)
        assert "ISSUE-001" in meta
        assert meta["ISSUE-001"]["priority"] == "p0"
        assert meta["ISSUE-001"]["depends_on"] == ["ISSUE-002"]
        assert meta["ISSUE-001"]["manual"] is False

    def test_parses_manual_true(self):
        text = _make_issue(num="001", manual="true")
        meta = parse_issues_metadata(text)
        assert meta["ISSUE-001"]["manual"] is True

    def test_depends_on_none(self):
        text = _make_issue(num="001", depends_on="none")
        meta = parse_issues_metadata(text)
        assert meta["ISSUE-001"]["depends_on"] == []

    def test_multiple_dependencies(self):
        text = _make_issue(num="003", depends_on="ISSUE-001, ISSUE-002")
        meta = parse_issues_metadata(text)
        assert meta["ISSUE-003"]["depends_on"] == ["ISSUE-001", "ISSUE-002"]

    def test_multiple_issues(self):
        text = _make_issue(num="001") + "\n" + _make_issue(num="002", priority="P0")
        meta = parse_issues_metadata(text)
        assert len(meta) == 2
        assert meta["ISSUE-002"]["priority"] == "p0"


# ── TestComputeQueues ───────────────────────────────────────────────


class TestComputeQueues:
    def test_ship_ready_from_reviewed(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "reviewed"}]
        queues = compute_queues(rows, {})
        assert queues["ship_ready"] == ["ISSUE-001"]
        assert queues["review_ready"] == []

    def test_review_ready_from_implemented(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "implemented"}]
        queues = compute_queues(rows, {})
        assert queues["review_ready"] == ["ISSUE-001"]

    def test_implement_ready_basic(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "0", "last_error": "—", "phase": "backlog"}]
        meta = {"ISSUE-001": {"manual": False, "depends_on": [], "priority": "p1", "status": "backlog"}}
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == ["ISSUE-001"]

    def test_implement_ready_filters_manual(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "0", "last_error": "—", "phase": "backlog"}]
        meta = {"ISSUE-001": {"manual": True, "depends_on": [], "priority": "p1", "status": "backlog"}}
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == []

    def test_implement_ready_filters_unresolved_deps(self):
        rows = [
            {"issue": "ISSUE-001", "status": "active", "attempts": "0", "last_error": "—", "phase": "backlog"},
            {"issue": "ISSUE-002", "status": "active", "attempts": "1", "last_error": "—", "phase": "implementing"},
        ]
        meta = {
            "ISSUE-001": {"manual": False, "depends_on": ["ISSUE-002"], "priority": "p1", "status": "backlog"},
        }
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == []

    def test_implement_ready_includes_resolved_deps(self):
        rows = [
            {"issue": "ISSUE-001", "status": "active", "attempts": "0", "last_error": "—", "phase": "backlog"},
            {"issue": "ISSUE-002", "status": "active", "attempts": "1", "last_error": "—", "phase": "shipped"},
        ]
        meta = {
            "ISSUE-001": {"manual": False, "depends_on": ["ISSUE-002"], "priority": "p1", "status": "backlog"},
        }
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == ["ISSUE-001"]

    def test_in_flight_detection(self):
        rows = [
            {"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "implementing"},
            {"issue": "ISSUE-002", "status": "active", "attempts": "1", "last_error": "—", "phase": "reviewing"},
        ]
        queues = compute_queues(rows, {})
        assert set(queues["in_flight"]) == {"ISSUE-001", "ISSUE-002"}

    def test_all_shipped_returns_empty_queues(self):
        rows = [
            {"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "shipped"},
            {"issue": "ISSUE-002", "status": "active", "attempts": "1", "last_error": "—", "phase": "shipped"},
        ]
        queues = compute_queues(rows, {})
        assert all(v == [] for v in queues.values())

    def test_skips_dropped_and_waiting_issues(self):
        rows = [
            {"issue": "ISSUE-001", "status": "dropped", "attempts": "0", "last_error": "—", "phase": "backlog"},
            {"issue": "ISSUE-002", "status": "waiting", "attempts": "2", "last_error": "err", "phase": "implemented"},
        ]
        meta = {"ISSUE-001": {"manual": False, "depends_on": [], "priority": "p1", "status": "backlog"}}
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == []
        assert queues["review_ready"] == []

    def test_implement_ready_sorted_by_priority(self):
        rows = [
            {"issue": "ISSUE-001", "status": "active", "attempts": "0", "last_error": "—", "phase": "backlog"},
            {"issue": "ISSUE-002", "status": "active", "attempts": "0", "last_error": "—", "phase": "backlog"},
            {"issue": "ISSUE-003", "status": "active", "attempts": "0", "last_error": "—", "phase": "backlog"},
        ]
        meta = {
            "ISSUE-001": {"manual": False, "depends_on": [], "priority": "p2", "status": "backlog"},
            "ISSUE-002": {"manual": False, "depends_on": [], "priority": "p0", "status": "backlog"},
            "ISSUE-003": {"manual": False, "depends_on": [], "priority": "p1", "status": "backlog"},
        }
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == ["ISSUE-002", "ISSUE-003", "ISSUE-001"]

    def test_deps_resolved_by_dropped_status(self):
        rows = [
            {"issue": "ISSUE-001", "status": "active", "attempts": "0", "last_error": "—", "phase": "backlog"},
            {"issue": "ISSUE-002", "status": "dropped", "attempts": "0", "last_error": "—", "phase": "backlog"},
        ]
        meta = {
            "ISSUE-001": {"manual": False, "depends_on": ["ISSUE-002"], "priority": "p1", "status": "backlog"},
        }
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == ["ISSUE-001"]


# ── TestChooseAction ────────────────────────────────────────────────


class TestChooseAction:
    def test_ship_takes_priority_over_review(self):
        queues = {
            "ship_ready": ["ISSUE-001"],
            "review_ready": ["ISSUE-002"],
            "implement_ready": ["ISSUE-003"],
            "in_flight": [],
        }
        result = choose_action(queues, max_parallel=3)
        assert result["action"] == "SHIP"
        assert result["targets"] == ["ISSUE-001"]

    def test_review_takes_priority_over_pipeline(self):
        queues = {
            "ship_ready": [],
            "review_ready": ["ISSUE-001"],
            "implement_ready": ["ISSUE-002"],
            "in_flight": [],
        }
        result = choose_action(queues, max_parallel=3)
        assert result["action"] == "REVIEW"
        assert result["targets"] == ["ISSUE-001"]

    def test_pipeline_when_only_backlog(self):
        queues = {
            "ship_ready": [],
            "review_ready": [],
            "implement_ready": ["ISSUE-001", "ISSUE-002"],
            "in_flight": [],
        }
        result = choose_action(queues, max_parallel=3)
        assert result["action"] == "PIPELINE"
        assert result["targets"] == ["ISSUE-001", "ISSUE-002"]

    def test_stuck_when_only_in_flight(self):
        queues = {
            "ship_ready": [],
            "review_ready": [],
            "implement_ready": [],
            "in_flight": ["ISSUE-001"],
        }
        result = choose_action(queues, max_parallel=3)
        assert result["action"] == "STUCK"

    def test_done_when_all_complete(self):
        queues = {
            "ship_ready": [],
            "review_ready": [],
            "implement_ready": [],
            "in_flight": [],
        }
        result = choose_action(queues, max_parallel=3)
        assert result["action"] == "DONE"

    def test_max_parallel_caps_targets(self):
        queues = {
            "ship_ready": [],
            "review_ready": [],
            "implement_ready": ["ISSUE-001", "ISSUE-002", "ISSUE-003", "ISSUE-004"],
            "in_flight": [],
        }
        result = choose_action(queues, max_parallel=2)
        assert len(result["targets"]) == 2
        assert result["targets"] == ["ISSUE-001", "ISSUE-002"]


# ── TestValidateTransitions ─────────────────────────────────────────


class TestValidateTransitions:
    def test_valid_ship_transition(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "shipped"}]
        result = validate_transitions(rows, "SHIP", ["ISSUE-001"])
        assert result["valid"] is True
        assert result["transitioned"] == ["ISSUE-001"]
        assert result["stuck"] == []

    def test_valid_review_transition(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "reviewed"}]
        result = validate_transitions(rows, "REVIEW", ["ISSUE-001"])
        assert result["valid"] is True

    def test_valid_implement_transition(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "implemented"}]
        result = validate_transitions(rows, "IMPLEMENT", ["ISSUE-001"])
        assert result["valid"] is True

    def test_stuck_issue_detected(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "implementing"}]
        result = validate_transitions(rows, "IMPLEMENT", ["ISSUE-001"])
        assert result["valid"] is False
        assert result["stuck"] == ["ISSUE-001"]
        assert "ISSUE-001" in result["errors"][0]

    def test_partial_transition(self):
        rows = [
            {"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "implemented"},
            {"issue": "ISSUE-002", "status": "active", "attempts": "1", "last_error": "err", "phase": "implementing"},
        ]
        result = validate_transitions(rows, "IMPLEMENT", ["ISSUE-001", "ISSUE-002"])
        assert result["valid"] is False
        assert result["transitioned"] == ["ISSUE-001"]
        assert result["stuck"] == ["ISSUE-002"]

    def test_waiting_issue_counts_as_handled(self):
        rows = [{"issue": "ISSUE-001", "status": "waiting", "attempts": "2", "last_error": "err", "phase": "reviewing"}]
        result = validate_transitions(rows, "REVIEW", ["ISSUE-001"])
        assert result["valid"] is True
        assert result["transitioned"] == ["ISSUE-001"]

    def test_unknown_action(self):
        result = validate_transitions([], "UNKNOWN", ["ISSUE-001"])
        assert result["valid"] is False

    def test_pipeline_fully_shipped(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "shipped"}]
        result = validate_transitions(rows, "PIPELINE", ["ISSUE-001"])
        assert result["valid"] is True
        assert result["transitioned"] == ["ISSUE-001"]

    def test_pipeline_stopped_at_implemented(self):
        """Pipeline stopped mid-way (e.g. review failed) — counts as progressed, not stuck."""
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "review fail", "phase": "implemented"}]
        result = validate_transitions(rows, "PIPELINE", ["ISSUE-001"])
        assert result["valid"] is True
        assert result["transitioned"] == ["ISSUE-001"]

    def test_pipeline_stopped_at_reviewed(self):
        """Pipeline stopped at reviewed (e.g. ship failed) — counts as progressed."""
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "ship fail", "phase": "reviewed"}]
        result = validate_transitions(rows, "PIPELINE", ["ISSUE-001"])
        assert result["valid"] is True
        assert result["transitioned"] == ["ISSUE-001"]

    def test_pipeline_stuck_at_backlog(self):
        """Pipeline didn't make any progress — stuck."""
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "backlog"}]
        result = validate_transitions(rows, "PIPELINE", ["ISSUE-001"])
        assert result["valid"] is False
        assert result["stuck"] == ["ISSUE-001"]

    def test_pipeline_mixed_results(self):
        """One issue shipped, another stuck at backlog."""
        rows = [
            {"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "shipped"},
            {"issue": "ISSUE-002", "status": "active", "attempts": "1", "last_error": "—", "phase": "backlog"},
        ]
        result = validate_transitions(rows, "PIPELINE", ["ISSUE-001", "ISSUE-002"])
        assert result["valid"] is False
        assert result["transitioned"] == ["ISSUE-001"]
        assert result["stuck"] == ["ISSUE-002"]


# ── TestCLI ─────────────────────────────────────────────────────────


class TestCLI:
    def test_next_action_json_output(self, tmp_path):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(_make_sprint_state([
            ("ISSUE-001", "active", "1", "—", "implemented"),
            ("ISSUE-002", "active", "0", "—", "backlog"),
        ]))
        issues = tmp_path / "issues.md"
        issues.write_text(
            _make_issue(num="001") + "\n" + _make_issue(num="002")
        )

        import io
        import sys as _sys

        captured = io.StringIO()
        old_stdout = _sys.stdout
        _sys.stdout = captured
        try:
            exit_code = main([
                "next-action",
                "--sprint-state", str(sprint),
                "--issues", str(issues),
                "--max-parallel", "3",
            ])
        finally:
            _sys.stdout = old_stdout

        output = json.loads(captured.getvalue())
        assert exit_code == 0
        assert output["action"] == "REVIEW"
        assert output["targets"] == ["ISSUE-001"]

    def test_validate_json_output(self, tmp_path):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(_make_sprint_state([
            ("ISSUE-001", "active", "1", "—", "shipped"),
        ]))

        import io
        import sys as _sys

        captured = io.StringIO()
        old_stdout = _sys.stdout
        _sys.stdout = captured
        try:
            exit_code = main([
                "validate",
                "--sprint-state", str(sprint),
                "--action", "SHIP",
                "--targets", "ISSUE-001",
            ])
        finally:
            _sys.stdout = old_stdout

        output = json.loads(captured.getvalue())
        assert exit_code == 0
        assert output["valid"] is True

    def test_missing_file_returns_exit_2(self):
        exit_code = main([
            "next-action",
            "--sprint-state", "/nonexistent/sprint_state.md",
            "--issues", "/nonexistent/issues.md",
        ])
        assert exit_code == 2

    def test_no_subcommand_returns_exit_2(self):
        exit_code = main([])
        assert exit_code == 2

    def test_next_action_empty_table_returns_exit_1(self, tmp_path):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(_make_sprint_state([]))
        issues = tmp_path / "issues.md"
        issues.write_text(_make_issue(num="001"))

        import io
        import sys as _sys

        captured = io.StringIO()
        old_stdout = _sys.stdout
        _sys.stdout = captured
        try:
            exit_code = main([
                "next-action",
                "--sprint-state", str(sprint),
                "--issues", str(issues),
            ])
        finally:
            _sys.stdout = old_stdout

        assert exit_code == 1
        output = json.loads(captured.getvalue())
        assert output["action"] == "DONE"


# ── ISSUE-052: crash-recovery — already-merged PR awareness ──────────


class _FakeProc:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _runner(*, returncode=0, state=None, merged_at=None, stdout=None, stderr=""):
    """Build a fake `runner` for _gh_pr_merge_state that records the argv."""
    calls: list = []

    def _run(cmd, **kwargs):
        calls.append(cmd)
        payload = stdout
        if payload is None:
            payload = json.dumps({"state": state, "mergedAt": merged_at})
        return _FakeProc(returncode=returncode, stdout=payload, stderr=stderr)

    _run.calls = calls
    return _run


class TestGhPrMergeState:
    def test_merged_by_state(self):
        assert _gh_pr_merge_state("123", runner=_runner(state="MERGED")) == "merged"

    def test_merged_by_mergedat_even_if_state_open(self):
        # A PR can report a mergedAt timestamp; treat presence as merged.
        r = _runner(state="OPEN", merged_at="2026-08-11T00:00:00Z")
        assert _gh_pr_merge_state("123", runner=r) == "merged"

    def test_open(self):
        assert _gh_pr_merge_state("123", runner=_runner(state="OPEN")) == "open"

    def test_empty_ref_returns_none_without_calling_gh(self):
        r = _runner(state="MERGED")
        assert _gh_pr_merge_state("", runner=r) is None
        assert r.calls == []

    def test_nonzero_exit_degrades_to_none_with_warning(self, capsys):
        r = _runner(returncode=1, stderr="gh: not authenticated")
        assert _gh_pr_merge_state("123", runner=r) is None
        assert "Warning" in capsys.readouterr().err

    def test_exception_degrades_to_none_with_warning(self, capsys):
        def _boom(cmd, **kwargs):
            raise OSError("gh executable not found")

        assert _gh_pr_merge_state("123", runner=_boom) is None
        assert "Warning" in capsys.readouterr().err

    def test_unparseable_json_degrades_to_none(self):
        r = _runner(stdout="not-json")
        assert _gh_pr_merge_state("123", runner=r) is None

    def test_argv_is_fixed_and_shell_free(self):
        # ISSUE-073 AC-6: the old `"PR-REF"` placeholder is rejected by the
        # whitelist, so the fixture carries a legitimate ref instead — the
        # validator is NOT loosened to keep a placeholder green.
        r = _runner(state="MERGED")
        _gh_pr_merge_state("121", runner=r)
        argv = r.calls[0]
        assert argv == ["gh", "pr", "view", "--json", "state,mergedAt", "--", "121"]
        # Every flag sits AHEAD of the `--` separator and the ref is last, so a
        # value can never be re-read as an option (gh's cobra parser treats
        # everything after `--` as positional; verified against gh 2.76.2).
        sep = argv.index("--")
        flag_positions = [
            i for i, a in enumerate(argv) if a.startswith("-") and i != sep
        ]
        assert flag_positions, argv
        assert all(i < sep for i in flag_positions), argv
        assert argv[-1] == "121"
        assert sep == len(argv) - 2


class TestClassifyShipReady:
    def test_merged_goes_to_finalize(self):
        meta = {"ISSUE-001": {"pr": "https://x/y/pull/1"}}
        fin, ship = classify_ship_ready(
            ["ISSUE-001"], meta, merge_state_fn=lambda ref, **kw: "merged"
        )
        assert fin == ["ISSUE-001"]
        assert ship == []

    def test_open_stays_ship(self):
        meta = {"ISSUE-001": {"pr": "pull/1"}}
        fin, ship = classify_ship_ready(
            ["ISSUE-001"], meta, merge_state_fn=lambda ref, **kw: "open"
        )
        assert fin == []
        assert ship == ["ISSUE-001"]

    def test_gh_error_stays_ship(self):
        meta = {"ISSUE-001": {"pr": "pull/1"}}
        fin, ship = classify_ship_ready(
            ["ISSUE-001"], meta, merge_state_fn=lambda ref, **kw: None
        )
        assert fin == []
        assert ship == ["ISSUE-001"]

    def test_missing_pr_ref_stays_ship_without_probe(self):
        meta = {"ISSUE-001": {"pr": ""}}
        calls = []

        def _fn(ref, **kw):
            calls.append(ref)
            return "merged"

        fin, ship = classify_ship_ready(["ISSUE-001"], meta, merge_state_fn=_fn)
        assert fin == []
        assert ship == ["ISSUE-001"]
        assert calls == []  # no PR ref → no gh probe

    def test_order_preserved_and_probe_cached(self):
        meta = {
            "ISSUE-001": {"pr": "pull/1"},
            "ISSUE-002": {"pr": "pull/1"},  # same ref → probed once
            "ISSUE-003": {"pr": "pull/3"},
        }
        calls = []

        def _fn(ref, **kw):
            calls.append(ref)
            return "merged" if ref == "pull/1" else "open"

        fin, ship = classify_ship_ready(
            ["ISSUE-001", "ISSUE-002", "ISSUE-003"], meta, merge_state_fn=_fn
        )
        assert fin == ["ISSUE-001", "ISSUE-002"]
        assert ship == ["ISSUE-003"]
        assert calls == ["pull/1", "pull/3"]  # pull/1 cached, not re-probed


class TestChooseActionFinalize:
    def test_finalize_takes_priority_over_ship(self):
        queues = {
            "finalize_ready": ["ISSUE-001"],
            "ship_ready": ["ISSUE-002"],
            "review_ready": ["ISSUE-003"],
            "implement_ready": [],
            "in_flight": [],
        }
        result = choose_action(queues, max_parallel=3)
        assert result["action"] == "FINALIZE"
        assert result["targets"] == ["ISSUE-001"]

    def test_ship_when_no_finalize_key_present(self):
        # Backward compat: compute_queues never emits finalize_ready.
        queues = {
            "ship_ready": ["ISSUE-001"],
            "review_ready": [],
            "implement_ready": [],
            "in_flight": [],
        }
        result = choose_action(queues, max_parallel=3)
        assert result["action"] == "SHIP"

    def test_finalize_caps_at_max_parallel(self):
        queues = {
            "finalize_ready": ["ISSUE-001", "ISSUE-002", "ISSUE-003"],
            "ship_ready": [],
            "review_ready": [],
            "implement_ready": [],
            "in_flight": [],
        }
        result = choose_action(queues, max_parallel=2)
        assert result["targets"] == ["ISSUE-001", "ISSUE-002"]


class TestShipMergeDecision:
    def test_skip_when_already_merged(self):
        d = ship_merge_decision("pull/1", merge_state_fn=lambda ref, **kw: "merged")
        assert d["action"] == "skip"
        assert "pull/1" in d["reason"]

    def test_merge_when_open(self):
        d = ship_merge_decision("pull/1", merge_state_fn=lambda ref, **kw: "open")
        assert d["action"] == "merge"

    def test_merge_when_gh_indeterminate(self):
        # gh error → default to merge; the real `gh pr merge` surfaces any failure.
        d = ship_merge_decision("pull/1", merge_state_fn=lambda ref, **kw: None)
        assert d["action"] == "merge"


class TestParsePrField:
    def test_parses_pr_field(self):
        text = (
            "### ISSUE-009: t\n- Priority: P1\n- Status: reviewed\n"
            "- Depends-On: none\n- PR: https://github.com/x/y/pull/9\n\n"
            "#### Acceptance Criteria (DoD)\n- [ ] a\n"
        )
        meta = parse_issues_metadata(text)
        assert meta["ISSUE-009"]["pr"] == "https://github.com/x/y/pull/9"

    def test_pr_defaults_to_empty(self):
        text = _make_issue(num="001")
        meta = parse_issues_metadata(text)
        assert meta["ISSUE-001"]["pr"] == ""


class TestValidateFinalize:
    def test_valid_finalize_transition(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "shipped"}]
        result = validate_transitions(rows, "FINALIZE", ["ISSUE-001"])
        assert result["valid"] is True
        assert result["transitioned"] == ["ISSUE-001"]

    def test_finalize_stuck_if_not_shipped(self):
        rows = [{"issue": "ISSUE-001", "status": "active", "attempts": "1", "last_error": "—", "phase": "reviewed"}]
        result = validate_transitions(rows, "FINALIZE", ["ISSUE-001"])
        assert result["valid"] is False
        assert result["stuck"] == ["ISSUE-001"]


class TestCLIFinalize:
    def _sprint_and_issues(self, tmp_path, pr_line="- PR: https://github.com/x/y/pull/1"):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(_make_sprint_state([
            ("ISSUE-001", "active", "1", "—", "reviewed"),
        ]))
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: t\n- Priority: P1\n- Status: reviewed\n"
            f"- Depends-On: none\n{pr_line}\n\n"
            "#### Acceptance Criteria (DoD)\n- [ ] a\n"
        )
        return sprint, issues

    def _run_next_action(self, sprint, issues, capsys, extra=None):
        argv = [
            "next-action",
            "--sprint-state", str(sprint),
            "--issues", str(issues),
            "--max-parallel", "2",
        ]
        if extra:
            argv += extra
        exit_code = main(argv)
        out = json.loads(capsys.readouterr().out)
        return exit_code, out

    def test_finalize_when_pr_merged(self, tmp_path, capsys, monkeypatch):
        import scripts.sprint_queue as q
        monkeypatch.setattr(q, "_gh_pr_merge_state", lambda ref, **kw: "merged")
        sprint, issues = self._sprint_and_issues(tmp_path)
        _, out = self._run_next_action(sprint, issues, capsys)
        assert out["action"] == "FINALIZE"
        assert out["targets"] == ["ISSUE-001"]

    def test_ship_when_pr_open(self, tmp_path, capsys, monkeypatch):
        import scripts.sprint_queue as q
        monkeypatch.setattr(q, "_gh_pr_merge_state", lambda ref, **kw: "open")
        sprint, issues = self._sprint_and_issues(tmp_path)
        _, out = self._run_next_action(sprint, issues, capsys)
        assert out["action"] == "SHIP"
        assert out["targets"] == ["ISSUE-001"]

    def test_ship_when_gh_unavailable(self, tmp_path, capsys, monkeypatch):
        import scripts.sprint_queue as q
        monkeypatch.setattr(q, "_gh_pr_merge_state", lambda ref, **kw: None)
        sprint, issues = self._sprint_and_issues(tmp_path)
        exit_code, out = self._run_next_action(sprint, issues, capsys)
        assert out["action"] == "SHIP"  # graceful phase-only fallback
        assert exit_code == 0

    def test_no_check_merged_flag_skips_probe(self, tmp_path, capsys, monkeypatch):
        import scripts.sprint_queue as q

        def _boom(ref, **kw):
            raise AssertionError("gh probe must not run with --no-check-merged")

        monkeypatch.setattr(q, "_gh_pr_merge_state", _boom)
        sprint, issues = self._sprint_and_issues(tmp_path)
        _, out = self._run_next_action(sprint, issues, capsys, extra=["--no-check-merged"])
        assert out["action"] == "SHIP"

    def test_ship_merge_decision_subcommand_skip(self, capsys, monkeypatch):
        import scripts.sprint_queue as q
        monkeypatch.setattr(q, "_gh_pr_merge_state", lambda ref, **kw: "merged")
        exit_code = main(["ship-merge-decision", "--pr", "1"])
        out = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        assert out["action"] == "skip"

    def test_ship_merge_decision_subcommand_merge(self, capsys, monkeypatch):
        import scripts.sprint_queue as q
        monkeypatch.setattr(q, "_gh_pr_merge_state", lambda ref, **kw: "open")
        exit_code = main(["ship-merge-decision", "--pr", "1"])
        out = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        assert out["action"] == "merge"


class TestGhPrMergeStateRobustness:
    """Regression guards: the probe must NEVER raise (AC3 'never crashes')."""

    def test_non_object_json_degrades_to_none(self, capsys):
        # Valid JSON that is not an object — must not raise AttributeError.
        for payload in ("null", "[]", "123", '"x"'):
            r = _runner(stdout=payload)
            assert _gh_pr_merge_state("123", runner=r) is None
        assert "Warning" in capsys.readouterr().err

    def test_timeout_is_passed_to_runner(self):
        seen = {}

        def _run(cmd, **kwargs):
            seen.update(kwargs)
            return _FakeProc(returncode=0, stdout=json.dumps({"state": "OPEN"}))

        _gh_pr_merge_state("123", timeout=3.5, runner=_run)
        assert seen.get("timeout") == 3.5

    def test_timeout_expired_degrades_to_none(self, capsys):
        def _run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

        assert _gh_pr_merge_state("123", runner=_run) is None
        assert "Warning" in capsys.readouterr().err


# ── ISSUE-073: PR-ref validation before the gh merge-state probe ─────
#
# The Board `PR:` field and the model-chosen `ship-merge-decision --pr` argument
# are both untrusted, and both funnel into ONE subprocess site inside
# `_gh_pr_merge_state`. Every test below drives that production function (via
# `runner=` or by monkeypatching the module attribute to a `functools.partial`
# of the real probe) so the guard ACTUALLY EXECUTES. A `merge_state_fn=` double
# replaces the probe wholesale and bypasses the guard by design, which is why
# the existing `merge_state_fn` doubles in TestClassifyShipReady /
# TestShipMergeDecision are left exactly as they are.

# The three ref shapes the live Board demonstrably carries (census 2026-10-11:
# 14 bare `#N` rows, ~35 full-URL rows). No bare-number-without-`#` value is
# live, but `_gh_pr_merge_state`'s own tests use one, so it stays whitelisted.
LIVE_REF_FORMS = (
    "123",
    "#123",
    "https://github.com/pillip/claude-dev-kit/pull/123",
)


def _probe_ref(ref):
    """Run the production probe against a MERGED fake; return (state, calls).

    `calls == []` proves the guard refused the ref UPSTREAM of the subprocess
    seam; a non-empty `calls` exposes the exact argv `gh` would have received.
    """
    r = _runner(state="MERGED")
    return _gh_pr_merge_state(ref, runner=r), r.calls


def _real_probe_with_seam(monkeypatch, runner):
    """Point the module attribute at the REAL probe bound to a recording seam.

    Keeps the validation guard in the call path for the Board (`classify_ship_ready`)
    and CLI (`ship_merge_decision`) entry points, both of which resolve
    `_gh_pr_merge_state` as a module global at call time.
    """
    monkeypatch.setattr(
        sq,
        "_gh_pr_merge_state",
        functools.partial(_gh_pr_merge_state, runner=runner),
    )


class TestPrRefGuardBoardPath:
    """AC-1: an option-shaped Board `PR:` value can never reach `gh`."""

    HOSTILE = "--repo attacker/evil"

    def _write(self, tmp_path, pr_value):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(_make_sprint_state([
            ("ISSUE-001", "active", "1", "—", "reviewed"),
        ]))
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: t\n- Priority: P1\n- Status: reviewed\n"
            f"- Depends-On: none\n- PR: {pr_value}\n\n"
            "#### Acceptance Criteria (DoD)\n- [ ] a\n"
        )
        return sprint, issues

    def _run_next_action(self, sprint, issues, capsys):
        exit_code = main([
            "next-action",
            "--sprint-state", str(sprint),
            "--issues", str(issues),
            "--max-parallel", "2",
        ])
        captured = capsys.readouterr()
        return exit_code, json.loads(captured.out), captured.err

    def test_option_shaped_board_pr_never_reaches_gh(self, tmp_path, capsys, monkeypatch):
        fake = _runner(state="MERGED")
        _real_probe_with_seam(monkeypatch, fake)
        sprint, issues = self._write(tmp_path, self.HOSTILE)
        exit_code, out, err = self._run_next_action(sprint, issues, capsys)
        # Zero invocations is what pins the guard's POSITION: it must sit
        # upstream of the runner call, not inspect the answer afterwards. A
        # guard placed after `runner(...)` would still return None here but
        # would record the invocation and fail this assertion.
        assert fake.calls == []
        # The MERGED fake would have forged FINALIZE; the refusal degrades to
        # indeterminate, which keeps the issue on the (safe) ship path.
        assert out["action"] == "SHIP"
        assert out["targets"] == ["ISSUE-001"]
        assert exit_code == 0
        # The warning must name BOTH the rejected value and the field it came from.
        assert self.HOSTILE in err
        assert "PR:" in err

    def test_valid_board_pr_still_reaches_gh_and_finalizes(self, tmp_path, capsys, monkeypatch):
        """Positive control for the absence assertion above, same fixture.

        Without this, a seam that is simply never wired would make the
        zero-invocation assertion pass hollowly.
        """
        fake = _runner(state="MERGED")
        _real_probe_with_seam(monkeypatch, fake)
        ref = "https://github.com/pillip/claude-dev-kit/pull/1"
        sprint, issues = self._write(tmp_path, ref)
        exit_code, out, _ = self._run_next_action(sprint, issues, capsys)
        assert fake.calls[0][-1] == ref
        assert out["action"] == "FINALIZE"
        assert out["targets"] == ["ISSUE-001"]
        assert exit_code == 0


class TestPrRefGuardCLIPath:
    """AC-2: the model-chosen `--pr` argument is refused at the same chokepoint."""

    # Why the `--pr=<value>` form: argparse's `_parse_optional` only treats a
    # dash-leading token as an option when the token contains NO space, so
    # `--pr '--repo=attacker/evil'` exits 2 while `--pr '--repo attacker/evil'`
    # is accepted. The `=` form is reachable for BOTH shapes (verified against
    # this interpreter), so pinning it keeps the test honest about what an
    # attacker-influenced model can actually pass.
    def _decide(self, capsys, pr_arg, monkeypatch):
        fake = _runner(state="MERGED")
        _real_probe_with_seam(monkeypatch, fake)
        exit_code = main(["ship-merge-decision", pr_arg])
        return exit_code, json.loads(capsys.readouterr().out), fake.calls

    def test_option_shaped_cli_pr_decides_merge_with_zero_invocations(self, capsys, monkeypatch):
        exit_code, out, calls = self._decide(
            capsys, "--pr=--repo attacker/evil", monkeypatch
        )
        assert exit_code == 0
        assert calls == []
        # Fail-safe direction: indeterminate → `merge`, so the real `gh pr merge`
        # surfaces the truth instead of `skip` silently finalizing an unmerged PR.
        assert out["action"] == "merge"

    def test_single_token_option_shaped_cli_pr_also_refused(self, capsys, monkeypatch):
        exit_code, out, calls = self._decide(
            capsys, "--pr=--repo=attacker/evil", monkeypatch
        )
        assert exit_code == 0
        assert calls == []
        assert out["action"] == "merge"

    def test_ac2_literal_two_token_argv_form_is_refused(self, capsys, monkeypatch):
        """AC-2's literal spelling: `ship-merge-decision --pr '--repo attacker/evil'`.

        Added in review (PR #127). The three tests above all use the single-token
        `--pr=<value>` form, which is the only form reachable for a value with NO
        space; AC-2 names the TWO-token form, which argparse accepts because the
        value contains a space. Both spellings reach the same chokepoint, but the
        AC was not literally auditable against the suite until this pin existed.
        """
        fake = _runner(state="MERGED")
        _real_probe_with_seam(monkeypatch, fake)
        exit_code = main(["ship-merge-decision", "--pr", "--repo attacker/evil"])
        out = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        assert fake.calls == []
        assert out["action"] == "merge"

    def test_valid_cli_pr_still_reaches_gh_and_skips(self, capsys, monkeypatch):
        """Positive control: the seam IS wired, so the refusals above are real."""
        exit_code, out, calls = self._decide(capsys, "--pr=121", monkeypatch)
        assert exit_code == 0
        assert calls[0][-1] == "121"
        assert out["action"] == "skip"


class TestPrRefAcceptForms:
    """AC-3: every ref shape the live Board carries keeps working, unchanged."""

    def test_each_live_form_resolves_to_merged_with_ref_unchanged(self):
        for ref in LIVE_REF_FORMS:
            state, calls = _probe_ref(ref)
            assert state == "merged", ref
            assert len(calls) == 1, ref
            # Unchanged AND last: no normalization, no rewriting, and nothing
            # can be appended behind the ref.
            assert calls[0][-1] == ref, ref

    def test_classify_ship_ready_still_finalizes_each_live_form(self, monkeypatch):
        for ref in LIVE_REF_FORMS:
            fake = _runner(state="MERGED")
            _real_probe_with_seam(monkeypatch, fake)
            fin, ship = classify_ship_ready(["ISSUE-001"], {"ISSUE-001": {"pr": ref}})
            assert fin == ["ISSUE-001"], ref
            assert ship == [], ref
            assert fake.calls[0][-1] == ref, ref


class TestPrRefCompoundCensusValues:
    """AC-4: the two compound `#N <url>` values the live Board already carries."""

    LIVE_COMPOUND = (
        "#108 https://github.com/pillip/claude-dev-kit/pull/108",
        "#122 https://github.com/pillip/claude-dev-kit/pull/122",
    )

    def test_live_compound_board_values_are_refused_not_normalized(self, capsys):
        """Recorded decision: REFUSE as indeterminate; do NOT normalize.

        Rationale, four points:
        (1) Refusal reproduces today's observable result exactly — `gh` already
            exits 1 on a two-token ref (`no pull requests found for branch
            "#122 https://..."`, gh 2.76.2), which `_gh_pr_merge_state` already
            maps to None — so the two live rows (ISSUE-062/PR #108,
            ISSUE-066/PR #122) see ZERO behaviour change.
        (2) Normalizing would move the outcome toward FINALIZE, the unsafe
            direction: a wrong "merged" finalizes an unmerged PR as shipped.
        (3) Refusal keeps this a pure `fullmatch` whitelist; normalizing needs a
            search/extract step, i.e. the fail-open shape this issue exists to
            remove.
        (4) Refusal is self-correcting via ISSUE-052's attested fail-safe:
            None → `still_ship` → `merge` → the real `gh pr merge` surfaces the
            truth, the same observable mode `--no-check-merged` already produces.
        """
        for value in self.LIVE_COMPOUND:
            state, calls = _probe_ref(value)
            assert state is None, value
            assert calls == [], value
        err = capsys.readouterr().err
        for value in self.LIVE_COMPOUND:
            assert value in err
            assert "PR:" in err

    def test_compound_value_keeps_the_issue_on_the_ship_path(self, monkeypatch):
        """Point (1) made observable end-to-end: SHIP, exactly as on main."""
        fake = _runner(state="MERGED")
        _real_probe_with_seam(monkeypatch, fake)
        meta = {"ISSUE-001": {"pr": self.LIVE_COMPOUND[0]}}
        fin, ship = classify_ship_ready(["ISSUE-001"], meta)
        assert fin == []
        assert ship == ["ISSUE-001"]
        assert fake.calls == []


class TestPrRefGuardNeverRaises:
    """AC-7: the ISSUE-052 never-raises contract survives the new early return."""

    HOSTILE_REFS = (
        "--repo=x",
        "-",
        "--help",
        "; rm -rf /",
        "$(whoami)",
        "a" * 500,
        "#" + "9" * 20,
        "https://evil.example.com/pillip/x/pull/1",
        "https://github.com/o/r/pull/" + "9" * 12,
    )

    def test_hostile_refs_return_none_without_raising(self, capsys):
        for value in self.HOSTILE_REFS:
            state, calls = _probe_ref(value)
            assert state is None, value
            assert calls == [], value
        assert "Warning" in capsys.readouterr().err

    def test_six_degradation_modes_still_reach_gh_and_return_none(self, capsys):
        """Anti-vacuity companion to the pre-existing degradation tests.

        Those probe with `"123"` and assert only `is None` — which a guard that
        rejected `"123"` would satisfy VACUOUSLY. Each mode here additionally
        asserts whether the runner was invoked, so a valid ref is proven to pass
        the whitelist and reach `gh` before degrading for its own reason.
        """
        seen: list = []

        def _raiser(exc):
            def _run(cmd, **kwargs):
                seen.append(cmd)
                raise exc

            return _run

        # 1. empty ref — the ONLY mode that must short-circuit before the seam.
        r = _runner(state="MERGED")
        assert _gh_pr_merge_state("", runner=r) is None
        assert r.calls == []
        # 2. non-zero exit
        r = _runner(returncode=1, stderr="gh: not authenticated")
        assert _gh_pr_merge_state("123", runner=r) is None
        assert len(r.calls) == 1
        # 3. OSError (gh missing)
        assert _gh_pr_merge_state("123", runner=_raiser(OSError("not found"))) is None
        # 4. TimeoutExpired
        timeout = subprocess.TimeoutExpired(cmd=["gh"], timeout=1)
        assert _gh_pr_merge_state("123", runner=_raiser(timeout)) is None
        assert len(seen) == 2  # both raising runners were actually entered
        # 5. unparseable JSON
        r = _runner(stdout="not-json")
        assert _gh_pr_merge_state("123", runner=r) is None
        assert len(r.calls) == 1
        # 6. valid-but-non-object JSON
        r = _runner(stdout="null")
        assert _gh_pr_merge_state("123", runner=r) is None
        assert len(r.calls) == 1
        assert "Warning" in capsys.readouterr().err


class TestPrRefBoundsBind:
    """The bounded quantifiers must actually bind.

    Same defect class as ISSUE-068's `_ROSTER_ID_RE`: an unbounded `\\d+` or
    segment run applied to text the kit does not author. Asserting the bound
    behaviourally (not by reading the pattern) is what keeps a later `\\d+`
    from slipping back in.
    """

    URL = "https://github.com/pillip/claude-dev-kit/pull/{}"
    OWNER_URL = "https://github.com/{}/claude-dev-kit/pull/1"
    REPO_URL = "https://github.com/pillip/{}/pull/1"

    def _accepted(self, ref):
        """(state, last argv element) for a ref the whitelist must admit."""
        state, calls = _probe_ref(ref)
        return state, (calls[0][-1] if calls else None)

    def test_bare_digit_run_bound_binds_at_nine(self):
        assert self._accepted("9" * 9) == ("merged", "9" * 9)
        assert _probe_ref("9" * 10) == (None, [])

    def test_hash_digit_run_bound_binds_at_nine(self):
        ref = "#" + "9" * 9
        assert self._accepted(ref) == ("merged", ref)
        assert _probe_ref("#" + "9" * 10) == (None, [])

    def test_url_digit_run_bound_binds_at_nine(self):
        ref = self.URL.format("9" * 9)
        assert self._accepted(ref) == ("merged", ref)
        assert _probe_ref(self.URL.format("9" * 10)) == (None, [])

    def test_owner_segment_bound_binds_at_sixty_four(self):
        ref = self.OWNER_URL.format("o" * 64)
        assert self._accepted(ref) == ("merged", ref)
        assert _probe_ref(self.OWNER_URL.format("o" * 65)) == (None, [])

    def test_repo_segment_bound_binds_at_sixty_four(self):
        ref = self.REPO_URL.format("r" * 64)
        assert self._accepted(ref) == ("merged", ref)
        assert _probe_ref(self.REPO_URL.format("r" * 65)) == (None, [])


class TestPrRefPatternIsAnchoredWhitelist:
    """AC-5 mutation harness: one named target to delete or weaken.

    Accessed as a module attribute rather than a top-level import so a missing
    guard fails THIS test instead of erroring the whole module at collection.
    """

    def test_pattern_accepts_only_the_censused_forms(self):
        for ref in LIVE_REF_FORMS:
            assert sq._PR_REF_RE.fullmatch(ref), ref
        assert sq._PR_REF_RE.fullmatch("--repo attacker/evil") is None

    def test_pattern_rejects_an_embedded_ref_under_fullmatch(self):
        hostile = "--repo=attacker/evil 121"
        assert sq._PR_REF_RE.fullmatch(hostile) is None
        # `search` WOULD admit it — documents why the guard must use fullmatch.
        assert sq._PR_REF_RE.search(hostile) is not None


# ── ISSUE-068: discovered-issue Board visibility ─────────────────────


def _row(issue, phase="shipped", status="active", attempts="1", last_error="—"):
    """Build a rostered sprint-table row (parse_sprint_table dict shape)."""
    return {
        "issue": issue,
        "status": status,
        "attempts": attempts,
        "last_error": last_error,
        "phase": phase,
    }


def _board_meta(status="backlog", depends_on=None, priority="p1", manual=False):
    """Build an issues.md metadata entry (parse_issues_metadata dict shape)."""
    return {
        "manual": manual,
        "depends_on": list(depends_on or []),
        "priority": priority,
        "status": status,
    }


def _roster(lo=56, hi=62, phase="shipped"):
    """Rostered rows ISSUE-0<lo>..ISSUE-0<hi> — watermark is the max ID."""
    return [_row(f"ISSUE-{n:03d}", phase=phase) for n in range(lo, hi + 1)]


class TestAugmentRosterFromBoard:
    def test_synthesizes_above_watermark_board_backlog_issue(self):
        """A Board backlog issue above the watermark gets a synthesized row."""
        rows = _roster()
        augmented, unrostered = sq.augment_roster_from_board(
            rows, {"ISSUE-063": _board_meta()}
        )
        assert unrostered == ["ISSUE-063"]
        assert len(augmented) == len(rows) + 1
        # Pin the full synthesized row shape (note ASCII "-" last_error).
        assert augmented[-1] == {
            "issue": "ISSUE-063",
            "status": "active",
            "attempts": "0",
            "last_error": "-",
            "phase": "backlog",
            "unrostered": True,
        }

    def test_original_rows_form_unchanged_prefix(self):
        import copy

        rows = _roster()
        snapshot = copy.deepcopy(rows)
        augmented, _ = sq.augment_roster_from_board(
            rows, {"ISSUE-063": _board_meta()}
        )
        assert augmented[: len(rows)] == snapshot
        assert rows == snapshot  # inputs never mutated

    def test_skips_already_rostered_id(self):
        rows = _roster(56, 61) + [_row("ISSUE-062", phase="backlog", attempts="0")]
        augmented, unrostered = sq.augment_roster_from_board(
            rows, {"ISSUE-062": _board_meta()}
        )
        assert unrostered == []
        assert augmented == rows

    def test_skips_board_status_done(self):
        augmented, unrostered = sq.augment_roster_from_board(
            _roster(), {"ISSUE-063": _board_meta(status="done")}
        )
        assert unrostered == []
        assert augmented == _roster()

    def test_skips_board_status_doing(self):
        augmented, unrostered = sq.augment_roster_from_board(
            _roster(), {"ISSUE-063": _board_meta(status="doing")}
        )
        assert unrostered == []
        assert augmented == _roster()

    def test_skips_manual_true(self):
        augmented, unrostered = sq.augment_roster_from_board(
            _roster(), {"ISSUE-063": _board_meta(manual=True)}
        )
        assert unrostered == []
        assert augmented == _roster()

    def test_below_watermark_backlog_stays_invisible(self):
        """Pre-existing, deliberately-excluded Board backlog is never synthesized."""
        rows = _roster(56, 62)
        augmented, unrostered = sq.augment_roster_from_board(
            rows, {"ISSUE-010": _board_meta()}
        )
        assert unrostered == []
        assert augmented == rows

    def test_empty_sprint_table_no_synthesis(self):
        """Legacy empty-table DONE path pinned: no roster → no synthesis."""
        augmented, unrostered = sq.augment_roster_from_board(
            [], {"ISSUE-063": _board_meta()}
        )
        assert augmented == []
        assert unrostered == []

    def test_no_exact_issue_id_rows_no_synthesis(self):
        """No rostered cell matching ISSUE-<digits> exactly → no watermark → no-op."""
        rows = [_row("TASK-7", phase="backlog", attempts="0")]
        augmented, unrostered = sq.augment_roster_from_board(
            rows, {"ISSUE-063": _board_meta()}
        )
        assert unrostered == []
        assert augmented == rows

    def test_multiple_synthesized_rows_sorted_by_numeric_id(self):
        rows = _roster()
        meta = {
            "ISSUE-065": _board_meta(),
            "ISSUE-063": _board_meta(),
            "ISSUE-064": _board_meta(),
        }
        augmented, unrostered = sq.augment_roster_from_board(rows, meta)
        assert unrostered == ["ISSUE-063", "ISSUE-064", "ISSUE-065"]
        appended = [r["issue"] for r in augmented[len(rows):]]
        assert appended == ["ISSUE-063", "ISSUE-064", "ISSUE-065"]


class TestComputeQueuesUnrostered:
    def test_synthesized_row_without_deps_is_implement_ready(self):
        rows = [_row("ISSUE-056")]
        meta = {
            "ISSUE-056": _board_meta(status="done"),
            "ISSUE-063": _board_meta(),
        }
        augmented, unrostered = sq.augment_roster_from_board(rows, meta)
        assert unrostered == ["ISSUE-063"]
        queues = compute_queues(augmented, meta)
        assert queues["implement_ready"] == ["ISSUE-063"]

    def test_synthesized_row_dep_on_shipped_rostered_row_is_ready(self):
        rows = [_row("ISSUE-056", phase="shipped")]
        meta = {
            "ISSUE-056": _board_meta(status="done"),
            "ISSUE-063": _board_meta(depends_on=["ISSUE-056"]),
        }
        augmented, _ = sq.augment_roster_from_board(rows, meta)
        queues = compute_queues(augmented, meta)
        assert queues["implement_ready"] == ["ISSUE-063"]

    def test_synthesized_dep_on_other_synthesized_backlog_is_flagged_only(self):
        """Dep on another synthesized backlog row → in NO queue (flagged only)."""
        rows = [_row("ISSUE-056")]
        meta = {
            "ISSUE-056": _board_meta(status="done"),
            "ISSUE-063": _board_meta(),
            "ISSUE-064": _board_meta(depends_on=["ISSUE-063"]),
        }
        augmented, unrostered = sq.augment_roster_from_board(rows, meta)
        assert unrostered == ["ISSUE-063", "ISSUE-064"]
        queues = compute_queues(augmented, meta)
        assert queues["implement_ready"] == ["ISSUE-063"]
        assert all("ISSUE-064" not in members for members in queues.values())

    def test_synthesized_row_dep_board_resolved_without_sprint_row(self):
        """Unrostered rows also treat Board done/drop/dropped deps as resolved."""
        for board_status in ("done", "drop", "dropped"):
            rows = [_row("ISSUE-056")]
            meta = {
                "ISSUE-056": _board_meta(status="done"),
                "ISSUE-063": _board_meta(status=board_status),  # NO sprint row
                "ISSUE-064": _board_meta(depends_on=["ISSUE-063"]),
            }
            augmented, unrostered = sq.augment_roster_from_board(rows, meta)
            assert unrostered == ["ISSUE-064"], board_status
            queues = compute_queues(augmented, meta)
            assert queues["implement_ready"] == ["ISSUE-064"], board_status

    def test_legacy_rostered_row_without_key_stays_filtered(self):
        """Lesson-8 pin: a ROSTERED backlog row (no `unrostered` key) depending on
        an issue that is Board-done but has no sprint row stays FILTERED —
        byte-identical legacy semantics."""
        rows = [
            _row("ISSUE-056"),
            _row("ISSUE-064", phase="backlog", attempts="0"),  # no `unrostered` key
        ]
        meta = {
            "ISSUE-056": _board_meta(status="done"),
            "ISSUE-063": _board_meta(status="done"),  # Board-done, NO sprint row
            "ISSUE-064": _board_meta(depends_on=["ISSUE-063"]),
        }
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == []

    def test_priority_sort_spans_rostered_and_synthesized(self):
        rows = [
            _row("ISSUE-056"),
            _row("ISSUE-057", phase="backlog", attempts="0"),  # rostered backlog, p2
        ]
        meta = {
            "ISSUE-056": _board_meta(status="done"),
            "ISSUE-057": _board_meta(priority="p2"),
            "ISSUE-063": _board_meta(priority="p0"),
        }
        augmented, _ = sq.augment_roster_from_board(rows, meta)
        queues = compute_queues(augmented, meta)
        assert queues["implement_ready"] == ["ISSUE-063", "ISSUE-057"]


class TestNextActionDiscoveredVisibility:
    def _write(self, tmp_path, rows, issues_text):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(_make_sprint_state(rows))
        issues = tmp_path / "issues.md"
        issues.write_text(issues_text)
        return sprint, issues

    def _run_next_action(self, sprint, issues, capsys):
        exit_code = sq.main([
            "next-action",
            "--sprint-state", str(sprint),
            "--issues", str(issues),
            "--max-parallel", "3",
        ])
        out = json.loads(capsys.readouterr().out)
        return exit_code, out

    def test_replay_063_064_065_all_surfaced_without_intervention(self, tmp_path, capsys):
        """AC3 replay: the SPEC-055 case — all three mid-sprint issues surfaced."""
        rows = [(f"ISSUE-{n:03d}", "active", "1", "—", "shipped") for n in range(56, 63)]
        board = [_make_issue(num=f"{n:03d}", status="done") for n in range(56, 63)]
        board += [
            _make_issue(num="063", priority="P1", status="backlog", depends_on="ISSUE-056"),
            _make_issue(num="064", priority="P2", status="backlog", depends_on="ISSUE-063"),
            _make_issue(num="065", priority="P1", status="backlog", depends_on="ISSUE-058"),
        ]
        sprint, issues = self._write(tmp_path, rows, "\n".join(board))
        exit_code, out = self._run_next_action(sprint, issues, capsys)
        assert exit_code == 0
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-063", "ISSUE-065"]
        assert out["unrostered"] == ["ISSUE-063", "ISSUE-064", "ISSUE-065"]
        for issue_id in ("ISSUE-063", "ISSUE-064", "ISSUE-065"):
            assert issue_id in out["reason"]

    def test_replay_stage2_board_done_dep_unblocks_064(self, tmp_path, capsys):
        """AC3 stage 2: ISSUE-063 Board-done (never rostered) unblocks ISSUE-064."""
        rows = [(f"ISSUE-{n:03d}", "active", "1", "—", "shipped") for n in range(56, 63)]
        board = [_make_issue(num=f"{n:03d}", status="done") for n in range(56, 63)]
        board += [
            _make_issue(num="063", priority="P1", status="done", depends_on="ISSUE-056"),
            _make_issue(num="064", priority="P2", status="backlog", depends_on="ISSUE-063"),
            _make_issue(num="065", priority="P1", status="backlog", depends_on="ISSUE-058"),
        ]
        sprint, issues = self._write(tmp_path, rows, "\n".join(board))
        exit_code, out = self._run_next_action(sprint, issues, capsys)
        assert exit_code == 0
        assert out["action"] == "PIPELINE"
        assert "ISSUE-064" in out["targets"]
        assert sorted(out["targets"]) == ["ISSUE-064", "ISSUE-065"]
        assert out["unrostered"] == ["ISSUE-064", "ISSUE-065"]

    def test_flagged_during_active_sprint_keeps_strict_priority(self, tmp_path, capsys):
        """AC1: mid-sprint discovery is flagged, strict action priority preserved."""
        rows = [("ISSUE-056", "active", "1", "—", "implemented")]
        board = "\n".join([
            _make_issue(num="056", status="doing"),
            _make_issue(num="057", status="backlog"),
        ])
        sprint, issues = self._write(tmp_path, rows, board)
        exit_code, out = self._run_next_action(sprint, issues, capsys)
        assert exit_code == 0
        assert out["action"] == "REVIEW"
        assert out["targets"] == ["ISSUE-056"]
        assert out["unrostered"] == ["ISSUE-057"]
        assert "ISSUE-057" in out["reason"]

    def test_done_annotated_with_stranded_discovered_issue(self, tmp_path, capsys):
        """AC2: DONE with an unresolvable discovered issue is annotated, not silent."""
        rows = [
            ("ISSUE-056", "active", "1", "—", "shipped"),
            ("ISSUE-057", "active", "1", "—", "shipped"),
        ]
        board = "\n".join([
            _make_issue(num="010", status="backlog"),  # below watermark, unresolved
            _make_issue(num="056", status="done"),
            _make_issue(num="057", status="done"),
            _make_issue(num="058", status="backlog", depends_on="ISSUE-010"),
        ])
        sprint, issues = self._write(tmp_path, rows, board)
        exit_code, out = self._run_next_action(sprint, issues, capsys)
        assert exit_code == 1
        assert out["action"] == "DONE"
        assert out["unrostered"] == ["ISSUE-058"]
        assert out["stranded"] == ["ISSUE-058"]
        assert "All issues are shipped, waiting, or dropped" in out["reason"]
        assert "stranded" in out["reason"]
        assert "ISSUE-058" in out["reason"]

    def test_done_refused_structurally_when_discovered_issue_ready(self, tmp_path, capsys):
        """AC2: a dep-free discovered issue is targeted — DONE never emitted."""
        rows = [("ISSUE-056", "active", "1", "—", "shipped")]
        board = "\n".join([
            _make_issue(num="056", status="done"),
            _make_issue(num="057", status="backlog"),
        ])
        sprint, issues = self._write(tmp_path, rows, board)
        exit_code, out = self._run_next_action(sprint, issues, capsys)
        assert exit_code == 0
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-057"]
        assert out["unrostered"] == ["ISSUE-057"]

    def test_legacy_done_reason_byte_pinned_without_unrostered(self, tmp_path, capsys):
        """Legacy pin: only below-watermark Board backlog → untouched DONE output."""
        rows = [("ISSUE-056", "active", "1", "—", "shipped")]
        board = "\n".join([
            _make_issue(num="010", status="backlog"),
            _make_issue(num="056", status="done"),
        ])
        sprint, issues = self._write(tmp_path, rows, board)
        exit_code, out = self._run_next_action(sprint, issues, capsys)
        assert exit_code == 1
        assert out["action"] == "DONE"
        assert out["reason"] == "All issues are shipped, waiting, or dropped"
        assert "unrostered" not in out
        assert "stranded" not in out

    def test_legacy_empty_table_pin_no_synthesis(self, tmp_path, capsys):
        """Legacy pin: empty Issue Progress table never synthesizes a roster."""
        board = _make_issue(num="063", status="backlog")
        sprint, issues = self._write(tmp_path, [], board)
        exit_code, out = self._run_next_action(sprint, issues, capsys)
        assert exit_code == 1
        assert out["action"] == "DONE"
        assert out["reason"] == "No issues found in sprint_state.md Issue Progress table"
        assert "unrostered" not in out
        assert "stranded" not in out


class TestValidateMissingRow:
    def test_target_without_row_reports_no_row(self):
        rows = [_row("ISSUE-056", phase="shipped")]
        result = validate_transitions(rows, "SHIP", ["ISSUE-056", "ISSUE-099"])
        assert result["valid"] is False
        assert result["transitioned"] == ["ISSUE-056"]
        assert result["stuck"] == ["ISSUE-099"]
        missing_errors = [e for e in result["errors"] if "ISSUE-099" in e]
        assert missing_errors, result["errors"]
        assert "no row" in missing_errors[0]


# ── ISSUE-068 review hardening (PR #121) ────────────────────────────


class TestBoardTextRobustness:
    """Board/roster text is untrusted engine input — neither site may crash or
    silently drop a row on shapes real issues.md demonstrably produces."""

    # CPython 3.11+ caps str→int at sys.int_max_str_digits (4300); an unbounded
    # `\d+` handed to int() therefore raises ValueError on a wider digit run.
    OVERLONG_ID = "1" * 4301

    def test_overlong_roster_id_cell_does_not_crash(self):
        """Site 1 (watermark scan): a pathological roster cell is ignored."""
        rows = [
            _row("ISSUE-056"),
            _row(f"ISSUE-{self.OVERLONG_ID}", phase="backlog", attempts="0"),
        ]
        augmented, unrostered = sq.augment_roster_from_board(
            rows,
            {"ISSUE-056": _board_meta(status="done"), "ISSUE-063": _board_meta()},
        )
        # Watermark comes from ISSUE-056 only; the overlong cell contributes none.
        assert unrostered == ["ISSUE-063"]
        assert len(augmented) == len(rows) + 1

    def test_overlong_board_issue_id_does_not_crash(self):
        """Site 2 (candidate scan): a pathological Board heading is skipped."""
        rows = _roster()
        augmented, unrostered = sq.augment_roster_from_board(
            rows, {f"ISSUE-{self.OVERLONG_ID}": _board_meta()}
        )
        assert unrostered == []
        assert augmented == rows

    def test_overlong_id_next_action_still_emits_json(self, tmp_path, capsys):
        """End-to-end: the engine returns a parseable action, not a traceback."""
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(
            _make_sprint_state([
                ("ISSUE-056", "active", "1", "—", "shipped"),
                (f"ISSUE-{self.OVERLONG_ID}", "active", "0", "—", "backlog"),
            ])
        )
        issues = tmp_path / "issues.md"
        issues.write_text("\n".join([
            _make_issue(num="056", status="done"),
            _make_issue(num=self.OVERLONG_ID, status="backlog"),
        ]))
        exit_code = sq.main([
            "next-action",
            "--sprint-state", str(sprint),
            "--issues", str(issues),
            "--no-check-merged",
        ])
        out = json.loads(capsys.readouterr().out)
        assert out["action"] in ("DONE", "PIPELINE", "STUCK")
        assert exit_code in (0, 1)


class TestAnnotatedBoardStatusFailsClosed:
    """Both ISSUE-068 Board `Status` comparisons are deliberately EXACT.

    Real issues.md entries DO annotate the field (this repo carries
    `drop (superseded by ISSUE-033, 2026-07-16)`), so prefix-matching the
    leading keyword looks like a robustness win. It is not: both comparisons
    gate autonomous dispatch, and an annotation usually states the opposite of
    its keyword. These tests pin the fail-CLOSED direction so the tolerant form
    cannot be reintroduced silently — a prefix match makes each of them fail.
    """

    def test_annotated_backlog_is_not_admitted(self):
        """`backlog (blocked — do NOT auto-dispatch)` must not become a candidate."""
        rows = _roster()
        augmented, unrostered = sq.augment_roster_from_board(
            rows,
            {
                "ISSUE-063": _board_meta(
                    status="backlog (blocked on the vendor contract — do NOT dispatch)"
                )
            },
        )
        assert unrostered == []
        assert augmented == rows

    def test_annotated_done_does_not_resolve_a_dependency(self):
        """`done (security sign-off still pending)` must NOT unblock its dependent."""
        rows = [_row("ISSUE-056")]
        meta = {
            "ISSUE-056": _board_meta(status="done"),
            "ISSUE-063": _board_meta(
                status="done (code landed, security sign-off still pending)"
            ),
            "ISSUE-064": _board_meta(depends_on=["ISSUE-063"]),
        }
        augmented, unrostered = sq.augment_roster_from_board(rows, meta)
        assert unrostered == ["ISSUE-064"]
        queues = compute_queues(augmented, meta)
        assert queues["implement_ready"] == []

    def test_bare_keywords_keep_their_behavior(self):
        """The fail-closed choice costs nothing for the documented bare vocabulary."""
        rows = [_row("ISSUE-056")]
        meta = {
            "ISSUE-056": _board_meta(status="done"),
            "ISSUE-063": _board_meta(status="done"),
            "ISSUE-064": _board_meta(depends_on=["ISSUE-063"]),
        }
        augmented, unrostered = sq.augment_roster_from_board(rows, meta)
        assert unrostered == ["ISSUE-064"]
        assert compute_queues(augmented, meta)["implement_ready"] == ["ISSUE-064"]

    def test_parser_returns_the_raw_annotated_value(self):
        """Documents what the filters receive: the whole lowercased Status value."""
        text = _make_issue(num="003", status="drop (superseded by ISSUE-033)")
        meta = parse_issues_metadata(text)
        assert meta["ISSUE-003"]["status"] == "drop (superseded by issue-033)"


class TestDiscoveryNeverStarvesStuckEscalation:
    """STUCK is the only path that escalates a wedged issue to a human.

    `choose_action` checks implement_ready before in_flight, so a synthesized
    row landing in implement_ready converts STUCK into PIPELINE — and the row is
    rebuilt with `attempts: "0"` every invocation, so the wedged issue's Attempts
    can never reach the >=3 escalation. Discovery is deferred (still flagged),
    not dropped.
    """

    def _run(self, tmp_path, capsys, rows, board):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(_make_sprint_state(rows))
        issues = tmp_path / "issues.md"
        issues.write_text("\n".join(board))
        exit_code = sq.main([
            "next-action",
            "--sprint-state", str(sprint),
            "--issues", str(issues),
            "--no-check-merged",
        ])
        return exit_code, json.loads(capsys.readouterr().out)

    def test_wedged_shipping_row_still_reports_stuck(self, tmp_path, capsys):
        exit_code, out = self._run(
            tmp_path,
            capsys,
            [("ISSUE-100", "active", "2", "ship crashed after merge", "shipping")],
            [
                _make_issue(num="100", status="doing"),
                _make_issue(num="101", status="backlog"),
            ],
        )
        assert out["action"] == "STUCK"
        assert out["targets"] == ["ISSUE-100"]
        assert exit_code == 1
        # Still surfaced — AC-1 is satisfied by flagging, not by dispatch.
        assert out["unrostered"] == ["ISSUE-101"]
        assert "ISSUE-101" in out["reason"]

    def test_each_in_flight_phase_defers_discovery(self, tmp_path, capsys):
        for phase in ("implementing", "reviewing", "shipping"):
            exit_code, out = self._run(
                tmp_path,
                capsys,
                [("ISSUE-100", "active", "1", "—", phase)],
                [
                    _make_issue(num="100", status="doing"),
                    _make_issue(num="101", status="backlog"),
                ],
            )
            assert out["action"] == "STUCK", phase
            assert out["unrostered"] == ["ISSUE-101"], phase

    def test_discovery_dispatches_once_the_pipeline_is_drained(self, tmp_path, capsys):
        """The deferral is bounded: a drained roster targets the discovered issue."""
        exit_code, out = self._run(
            tmp_path,
            capsys,
            [("ISSUE-100", "active", "1", "—", "shipped")],
            [
                _make_issue(num="100", status="done"),
                _make_issue(num="101", status="backlog"),
            ],
        )
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-101"]
        assert exit_code == 0

    def test_rostered_backlog_row_still_pre_empts_stuck(self, tmp_path, capsys):
        """Legacy pin: the deferral is scoped to synthesized rows ONLY.

        A ROSTERED backlog row keeps main's priority outcome (implement_ready is
        checked before in_flight) — unchanged by this PR.
        """
        exit_code, out = self._run(
            tmp_path,
            capsys,
            [
                ("ISSUE-100", "active", "1", "—", "shipping"),
                ("ISSUE-101", "active", "0", "—", "backlog"),
            ],
            [
                _make_issue(num="100", status="doing"),
                _make_issue(num="101", status="backlog"),
            ],
        )
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-101"]
        assert "unrostered" not in out


# ── ISSUE-076: Issue Progress section scoping ────────────────────────
#
# `parse_sprint_table` must read EXACTLY the Issue Progress table. The pre-fix
# capture (`r"## Issue Progress\s*\n(.*?)(?=\n## |\Z)"`) terminated only on an
# h2 heading, so a phase executor's `### Review outcomes` h3 subsection table
# fell inside it — and because that table has 6 columns while the row guard was
# `len(cells) < 5`, `cells[4]` read the "High unresolved" cell as the Phase.
#
# Target contract (copied from the document structure, not approximated):
#   1. find `## Issue Progress`;
#   2. scan forward for the first pipe row — a heading of ANY level reached
#      first ends the section with no table;
#   3. consume CONTIGUOUS pipe rows only;
#   4. terminate at the first non-pipe-row line (blank, prose, or any heading);
#   5. a row whose cell count is not exactly 5 is skipped, never index-read.

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sprint_state"

# The exact phantom Phase values the live 2026-10-11 incident produced from the
# `### Review outcomes` table's "High unresolved" column.
PHANTOM_PHASES = ("2", "0 (6 medium, 8 low)")

# Legitimate Phase vocabulary, derived from the module's own constants rather
# than a hand-copied literal list so it cannot drift from the pipeline.
LEGIT_PHASES = (
    set(sq.ACTION_END_PHASE.values()) | set(sq.IN_FLIGHT_PHASES) | {"backlog"}
)

ROSTER_ID_SHAPE = re.compile(r"^ISSUE-\d+$")

# Real sprint_state docs that carry a roster. Pinned to the repo root via the
# test file's own location (never the CWD). The selection predicate is a pure
# presence check — it deliberately does NOT mirror the parser's boundary logic,
# so it cannot mask a boundary regression.
_ROSTER_LINE = re.compile(r"^\|\s*ISSUE-\d+\s*\|", re.MULTILINE)
REAL_SPRINT_STATE_DOCS = sorted(
    path
    for path in (REPO_ROOT / "docs").glob("sprint_state*.md")
    if "## Issue Progress" in (text := path.read_text(encoding="utf-8"))
    and _ROSTER_LINE.search(text)
)


def _fixture_text(name: str) -> str:
    """Read a frozen sprint_state fixture.

    Deliberately NO skip/importorskip fallback: a missing fixture must fail
    loudly, because a silent skip here is a hollow pass.
    """
    return (FIXTURES / name).read_text(encoding="utf-8")


def _sprint_state(issue_progress_body: str, *, trailer: str = "## Escalations\n") -> str:
    """Build a sprint_state.md with a verbatim `## Issue Progress` body.

    Unlike `_make_sprint_state`, the body is passed through byte-for-byte so a
    test can place prose, subsection headings, blank lines, and off-shape rows
    exactly where a real phase executor would write them.
    """
    return (
        "# Sprint State\n\n"
        "## Meta\n"
        "- Started: 2026-10-10\n"
        "- Status: running\n\n"
        "## Issue Progress\n"
        f"{issue_progress_body}"
        f"{trailer}"
    )


ROSTER_HEADER = (
    "| Issue | Status | Attempts | Last Error | Phase |\n"
    "|-------|--------|----------|------------|-------|\n"
)


class TestFixtureReplayOfTheLiveFalseNegative:
    """AC-1 — the real 2026-10-11 file must validate as shipped.

    The frozen fixture is a byte-identical copy of the sprint_state.md a phase
    executor wrote while closing ISSUE-066..068 (see the fixture README). Pre-fix
    it yielded 6 rows — the 3 real `shipped` rows followed by 3 phantoms whose
    Phase came from the h3 table — and the phantoms, arriving last, overwrote the
    real rows in `validate_transitions`' `phase_by_issue` lookup.
    """

    FIXTURE = "issue_progress_with_h3_subsection.md"
    TARGETS = ["ISSUE-066", "ISSUE-067", "ISSUE-068"]

    def test_parses_exactly_the_three_roster_rows(self):
        rows = sq.parse_sprint_table(_fixture_text(self.FIXTURE))
        assert len(rows) == 3
        assert [r["issue"] for r in rows] == self.TARGETS
        assert [r["phase"] for r in rows] == ["shipped", "shipped", "shipped"]
        assert [r["status"] for r in rows] == ["done", "done", "done"]

    def test_no_row_carries_a_phantom_phase(self):
        """The load-bearing assertion: the h3 table's cells never become a Phase."""
        rows = sq.parse_sprint_table(_fixture_text(self.FIXTURE))
        phases = [r["phase"] for r in rows]
        for phantom in PHANTOM_PHASES:
            assert phantom not in phases, phases
        # And no row at all may be sourced from the 6-column h3 table.
        assert all(r["status"] == "done" for r in rows), rows
        assert not [r for r in rows if r["status"].startswith("#")], rows

    def test_every_row_has_a_legitimate_phase(self):
        """The exact Phase vocabulary is pinned HERE, not on the live docs.

        This fixture is frozen by contract (see the fixture README), so pinning
        its vocabulary generates no future maintenance — whereas the mutable
        `docs/sprint_state*.md` records would fail the moment an executor wrote
        any new wording into a Phase cell.
        """
        rows = sq.parse_sprint_table(_fixture_text(self.FIXTURE))
        assert rows, "frozen fixture parsed to zero rows"
        for row in rows:
            assert row["phase"] in LEGIT_PHASES, row

    def test_ship_validation_reports_valid(self):
        rows = sq.parse_sprint_table(_fixture_text(self.FIXTURE))
        result = validate_transitions(rows, "SHIP", self.TARGETS)
        assert result["valid"] is True
        assert result["stuck"] == []
        assert result["errors"] == []
        assert result["transitioned"] == self.TARGETS

    def test_validate_cli_exits_zero_on_the_real_file(self, capsys):
        """End-to-end through the actual consumer the orchestrator ran."""
        exit_code = main([
            "validate",
            "--sprint-state", str(FIXTURES / self.FIXTURE),
            "--action", "SHIP",
            "--targets", ",".join(self.TARGETS),
        ])
        out = json.loads(capsys.readouterr().out)
        assert out["valid"] is True, out
        assert out["stuck"] == [], out
        assert out["errors"] == [], out
        assert out["transitioned"] == self.TARGETS, out
        assert exit_code == 0


class TestWatermarkIsolationFromSubsectionTables:
    """AC-2 — phantom IDs in an h3 subsection must not reach the watermark.

    `augment_roster_from_board` derives its mid-sprint watermark from
    `max(rostered ids)`. A phantom `ISSUE-900` row lifted out of a subsection
    table pushes the watermark to 900, which silently vanishes every real
    mid-range Board candidate — no target, no `unrostered`, no `stranded`.
    """

    REVIEW_OUTCOMES_H3 = (
        "\n"
        "### Review outcomes\n"
        "| Issue | PR | Verdict | Crit | High unresolved | Review commit |\n"
        "|-------|----|---------|------|-----------------|---------------|\n"
        "| ISSUE-900 | #999 | PASS | 0 | 2 | c9bc35b |\n"
        "\n"
    )

    def _state(self, subsection: str) -> str:
        return _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | done | 1 | - | shipped |\n"
            + subsection
        )

    def test_phantom_h3_id_does_not_raise_the_watermark(self):
        rows = sq.parse_sprint_table(self._state(self.REVIEW_OUTCOMES_H3))
        meta = {
            "ISSUE-100": _board_meta(status="done"),
            # Mid-range: above the real roster max (100), below the phantom (900).
            "ISSUE-500": _board_meta(status="backlog"),
        }
        augmented, unrostered = sq.augment_roster_from_board(rows, meta)
        # Pre-fix the watermark was 900, so the real candidate vanished.
        assert unrostered == ["ISSUE-500"]
        assert "ISSUE-500" in [r["issue"] for r in augmented]

    def test_phantom_h3_id_is_in_no_row_and_no_queue(self):
        state = self._state(self.REVIEW_OUTCOMES_H3)
        rows = sq.parse_sprint_table(state)
        assert "ISSUE-900" not in [r["issue"] for r in rows], rows
        meta = {
            "ISSUE-100": _board_meta(status="done"),
            "ISSUE-500": _board_meta(status="backlog"),
        }
        augmented, _ = sq.augment_roster_from_board(rows, meta)
        assert "ISSUE-900" not in [r["issue"] for r in augmented], augmented
        queues = compute_queues(augmented, meta)
        assert all("ISSUE-900" not in members for members in queues.values()), queues

    def test_five_column_subsection_table_never_enters_a_queue(self):
        """Non-vacuous queue pin: a roster-SHAPED subsection row is still excluded.

        Pre-fix this landed `ISSUE-900` in `implement_ready` — the engine would
        have dispatched work off a record table.
        """
        state = self._state(
            "\n"
            "### Carried-over candidates\n"
            + ROSTER_HEADER
            + "| ISSUE-900 | active | 0 | - | backlog |\n"
            "\n"
        )
        rows = sq.parse_sprint_table(state)
        assert [r["issue"] for r in rows] == ["ISSUE-100"], rows
        meta = {
            "ISSUE-100": _board_meta(status="done"),
            "ISSUE-900": _board_meta(status="backlog"),
        }
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == [], queues
        assert all("ISSUE-900" not in members for members in queues.values()), queues


class TestColumnShapeGuard:
    """AC-3 — the 5-column roster shape is required, asserted in BOTH directions.

    The old `if len(cells) < 5: continue` admitted 6+ columns, so a wider row was
    index-read at `cells[4]`. Tightening it risks the opposite failure (a
    legitimate row no longer parsing), so both halves are pinned here.
    """

    MIXED_TABLE = _sprint_state(
        ROSTER_HEADER
        + "| ISSUE-100 | done | 1 | - | shipped |\n"
        # 6 columns, otherwise valid roster shape — cells[4] is NOT the Phase.
        + "| ISSUE-200 | done | 1 | - | 0 (6 Medium, 8 Low) | c9bc35b |\n"
        # 4 columns — pins the surviving half of the legacy `< 5` guard.
        + "| ISSUE-300 | active | 0 | - |\n"
        + "| ISSUE-400 | active | 1 | - | reviewed |\n"
    )

    def test_six_column_row_is_skipped_not_index_read(self):
        rows = sq.parse_sprint_table(self.MIXED_TABLE)
        assert "ISSUE-200" not in [r["issue"] for r in rows], rows
        # The specific mechanism: the 5th-of-6 cell must never become a phase.
        assert "0 (6 medium, 8 low)" not in [r["phase"] for r in rows], rows

    def test_four_column_row_is_skipped(self):
        rows = sq.parse_sprint_table(self.MIXED_TABLE)
        assert "ISSUE-300" not in [r["issue"] for r in rows], rows

    def test_legitimate_five_column_rows_in_the_same_table_still_parse(self):
        """The over-tightening direction: off-shape rows must not kill the table."""
        rows = sq.parse_sprint_table(self.MIXED_TABLE)
        assert [(r["issue"], r["phase"]) for r in rows] == [
            ("ISSUE-100", "shipped"),
            ("ISSUE-400", "reviewed"),
        ]


class TestIssueProgressBoundaryCompleteness:
    """AC-4 — the table's own end is the boundary, in both directions.

    The new terminator must be strictly tighter than the legacy next-h2 one
    WITHOUT dropping anything the legacy capture accepted.
    """

    def test_blank_line_terminates_the_table(self):
        """A roster-shaped row after a blank line is no longer in the table."""
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "\n"
            "| ISSUE-900 | active | 0 | - | backlog |\n"
            "\n"
        )
        rows = sq.parse_sprint_table(state)
        assert [(r["issue"], r["phase"]) for r in rows] == [
            ("ISSUE-100", "reviewed")
        ]

    def test_h3_heading_terminates_the_table(self):
        """An h3 reached with no intervening blank line also ends the table."""
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "### Review outcomes\n"
            "| ISSUE-900 | active | 0 | - | backlog |\n"
            "\n"
        )
        rows = sq.parse_sprint_table(state)
        assert [(r["issue"], r["phase"]) for r in rows] == [
            ("ISSUE-100", "reviewed")
        ]

    def test_h2_heading_still_terminates_the_table(self):
        """Legacy boundary pin: the stricter terminator must not regress this."""
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "## Other Section\n"
            "| ISSUE-900 | active | 0 | - | backlog |\n"
        )
        rows = sq.parse_sprint_table(state)
        assert [(r["issue"], r["phase"]) for r in rows] == [
            ("ISSUE-100", "reviewed")
        ]

    def test_prose_between_the_heading_and_the_table_still_parses(self):
        """Legacy tolerance pin: the table may be preceded by a prose line."""
        state = _sprint_state(
            "Rostered this iteration (ascending ID order):\n"
            "\n"
            + ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "\n"
        )
        rows = sq.parse_sprint_table(state)
        assert [(r["issue"], r["phase"]) for r in rows] == [
            ("ISSUE-100", "reviewed")
        ]

    def test_h3_subsection_without_a_table_still_yields_the_real_rows(self):
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "\n"
            "### Review outcomes\n",
            trailer="",
        )
        rows = sq.parse_sprint_table(state)
        assert [(r["issue"], r["phase"]) for r in rows] == [
            ("ISSUE-100", "reviewed")
        ]

    def test_heading_before_any_table_yields_no_rows(self):
        """Contract step 2: a heading reached first means the section has no table."""
        state = _sprint_state(
            "### Review outcomes\n"
            "| ISSUE-900 | active | 0 | - | backlog |\n",
            trailer="",
        )
        assert sq.parse_sprint_table(state) == []

    def test_missing_section_and_empty_table_still_return_empty(self):
        """Preserved public behaviour, re-pinned next to the new boundary."""
        assert sq.parse_sprint_table("# Sprint State\n## Meta\n- Status: running\n") == []
        assert sq.parse_sprint_table(_sprint_state(ROSTER_HEADER)) == []


class TestRealSprintStateDocsStillParse:
    """AC-4 — every real sprint_state doc in the repo keeps parsing cleanly.

    Review lesson 8: this change tightens the input contract, so the risk is a
    legitimate row no longer parsing. These replay the committed docs rather than
    fixtures, and assert parser behaviour only — never the docs' accuracy.

    The assertions are therefore split by the mutability of what is read. These
    docs are RECORDS the orchestrator rewrites — `docs/sprint_state.md` on every
    phase transition, and the `archive-*` set grows each sprint — so they get only
    mutation-proof structural invariants: roster ID shape, and ID uniqueness
    (a roster is keyed by issue, so a duplicate silently overwrites a real row in
    `validate_transitions`' `phase_by_issue` — the live incident's exact
    mechanism). The exact Phase vocabulary is pinned on the frozen fixture in
    `TestFixtureReplayOfTheLiveFalseNegative` instead: a future executor writing
    `blocked` or `shipped (finalized)` into a Phase cell is a record's wording,
    not a parser defect, and must not fail this suite on an unrelated branch.
    """

    def test_glob_found_real_sprint_state_docs(self):
        """Guard against a silently empty parametrization (a hollow pass)."""
        assert len(REAL_SPRINT_STATE_DOCS) > 0, (
            f"no roster-carrying docs/sprint_state*.md under {REPO_ROOT}"
        )

    def test_at_least_one_real_doc_yields_parsed_rows(self):
        """Suite-wide anti-vacuity guard — deliberately NOT per-doc.

        `_ROSTER_LINE` is an un-scoped presence check, so a future
        `sprint_state.md` with an empty roster table but an ISSUE-row in some
        subsection table would be selected and then correctly parse to zero rows.
        Per-doc emptiness is not a defect; suite-wide emptiness is.
        """
        assert any(
            sq.parse_sprint_table(path.read_text(encoding="utf-8"))
            for path in REAL_SPRINT_STATE_DOCS
        ), "no roster-carrying doc yielded a single parsed row"

    @pytest.mark.parametrize(
        "doc_path", REAL_SPRINT_STATE_DOCS, ids=lambda p: p.name
    )
    def test_doc_yields_only_roster_shaped_rows(self, doc_path):
        rows = sq.parse_sprint_table(doc_path.read_text(encoding="utf-8"))
        for row in rows:
            assert ROSTER_ID_SHAPE.match(row["issue"]), (doc_path.name, row)
        ids = [row["issue"] for row in rows]
        assert len(ids) == len(set(ids)), (
            f"{doc_path.name}: duplicate roster IDs "
            f"{sorted({i for i in ids if ids.count(i) > 1})} — rows captured from "
            "outside the Issue Progress table"
        )


# ── ISSUE-076 review fix: a truncated roster must never be acted on ──────
#
# Terminating the table at the first non-table line is GFM-correct, but it is
# SILENT: a stray blank — or whitespace-only, hence invisible — line inside the
# roster drops every row beneath it. A dropped row is not merely absent.
# `augment_roster_from_board` re-offers it as fresh backlog work, so the live
# consequence measured on this branch was `next-action` flipping from
#   {"action": "SHIP",     "targets": ["ISSUE-200"]}                    (correct)
# to
#   {"action": "PIPELINE", "targets": ["ISSUE-200"], "unrostered": [...]}
# — re-implementing an already-reviewed issue from scratch, at exit 0, with no
# warning. Review lesson 5: workspace-persisted state read by a gate is
# untrusted input, so validate on read. The boundary is unchanged (it is the
# issue's specified contract); the under-read is now loud.


class TestTruncatedRosterIsDetected:
    """`orphaned_roster_rows` — the under-read detector, both directions."""

    def test_blank_line_inside_the_roster_drops_the_rows_below(self):
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | done | 1 | - | shipped |\n"
            "\n"
            "| ISSUE-200 | active | 1 | - | reviewed |\n"
            "\n"
        )
        # The parse is an under-read ...
        assert [r["issue"] for r in sq.parse_sprint_table(state)] == ["ISSUE-100"]
        # ... and it is now reported rather than silent.
        orphans = sq.unparsed_roster_rows(state)
        assert len(orphans) == 1, orphans
        assert "ISSUE-200" in orphans[0], orphans

    def test_whitespace_only_line_inside_the_roster_is_detected(self):
        """The invisible trigger — a renderer treats `   ` as a blank line too."""
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | done | 1 | - | shipped |\n"
            "   \n"
            "| ISSUE-200 | active | 1 | - | reviewed |\n"
            "\n"
        )
        assert [r["issue"] for r in sq.parse_sprint_table(state)] == ["ISSUE-100"]
        assert len(sq.unparsed_roster_rows(state)) == 1

    def test_prose_line_inside_the_roster_is_detected(self):
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | done | 1 | - | shipped |\n"
            "(continued below)\n"
            "| ISSUE-200 | active | 1 | - | reviewed |\n"
            "\n"
        )
        assert len(sq.unparsed_roster_rows(state)) == 1

    def test_all_data_rows_dropped_is_detected(self):
        """Degenerate case: the stray line sits directly under the separator."""
        state = _sprint_state(
            ROSTER_HEADER
            + "\n"
            "| ISSUE-100 | done | 1 | - | shipped |\n"
            "\n"
        )
        assert sq.parse_sprint_table(state) == []
        assert len(sq.unparsed_roster_rows(state)) == 1

    # ── the over-firing direction: the excluded patterns are NOT orphans ──

    def test_h3_subsection_table_is_not_reported(self):
        """The pattern this issue exists to exclude must not trip the detector."""
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | done | 1 | - | shipped |\n"
            "\n"
            "### Review outcomes\n"
            "| Issue | PR | Verdict | Crit | High unresolved | Commit |\n"
            "|-------|----|---------|------|-----------------|--------|\n"
            "| ISSUE-900 | #999 | PASS | 0 | 2 | c9bc35b |\n"
            "\n"
        )
        assert [r["issue"] for r in sq.parse_sprint_table(state)] == ["ISSUE-100"]
        assert sq.unparsed_roster_rows(state) == []

    def test_next_h2_section_table_is_not_reported(self):
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | done | 1 | - | shipped |\n"
            "\n",
            trailer=(
                "## Review outcomes\n"
                "| ISSUE-900 | active | 0 | - | backlog |\n"
            ),
        )
        assert sq.unparsed_roster_rows(state) == []

    def test_off_shape_roster_row_inside_the_table_is_detected(self):
        """The column guard's own silent drop — a wide row vanishes entirely.

        It does NOT truncate the roster (ISSUE-300 below it still parses), so the
        boundary half of the detector cannot see it; it needs the in-table shape
        check.
        """
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | done | 1 | - | shipped |\n"
            "| ISSUE-200 | done | 1 | - | 0 (6 Medium) | c9bc35b |\n"
            "| ISSUE-300 | active | 1 | - | reviewed |\n"
            "\n"
        )
        assert [r["issue"] for r in sq.parse_sprint_table(state)] == [
            "ISSUE-100",
            "ISSUE-300",
        ]
        unparsed = sq.unparsed_roster_rows(state)
        assert len(unparsed) == 1, unparsed
        assert "ISSUE-200" in unparsed[0], unparsed

    def test_unescaped_pipe_in_last_error_is_detected(self):
        """The realistic trigger: Last Error carries executor output.

        A shell pipeline in an error message makes the row 6 cells wide, so the
        issue silently leaves the roster entirely.
        """
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | pytest | head failed | reviewed |\n"
            "\n"
        )
        assert sq.parse_sprint_table(state) == []
        assert len(sq.unparsed_roster_rows(state)) == 1

    def test_header_and_separator_rows_are_never_reported(self):
        """The shape regex must not fire on an ordinary empty roster table."""
        assert sq.unparsed_roster_rows(_sprint_state(ROSTER_HEADER)) == []

    def test_clean_roster_has_no_unparsed_rows(self):
        assert sq.unparsed_roster_rows(_make_sprint_state([
            ("ISSUE-100", "done", "1", "-", "shipped"),
            ("ISSUE-200", "active", "1", "-", "reviewed"),
        ])) == []

    def test_missing_section_and_empty_table_have_no_unparsed_rows(self):
        assert sq.unparsed_roster_rows("# Sprint State\n## Meta\n") == []
        assert sq.unparsed_roster_rows(_sprint_state(ROSTER_HEADER)) == []

    def test_frozen_real_fixture_has_no_unparsed_rows(self):
        """Load-bearing no-false-positive pin on the real executor's output.

        The 2026-10-11 file is exactly the `roster → blank → ### Review outcomes
        → 6-column table` shape, i.e. the closest real input to a false positive.
        """
        assert sq.unparsed_roster_rows(
            _fixture_text("issue_progress_with_h3_subsection.md")
        ) == []

    @pytest.mark.parametrize(
        "doc_path", REAL_SPRINT_STATE_DOCS, ids=lambda p: p.name
    )
    def test_real_docs_have_no_unparsed_rows(self, doc_path):
        """Structural invariant only — never these mutable records' wording."""
        assert sq.unparsed_roster_rows(
            doc_path.read_text(encoding="utf-8")
        ) == [], doc_path.name


class TestNextActionRefusesATruncatedRoster:
    """The destructive outcome itself: no dispatch off an under-read roster."""

    TRUNCATED = _sprint_state(
        ROSTER_HEADER
        + "| ISSUE-100 | done | 1 | - | shipped |\n"
        "   \n"
        "| ISSUE-200 | active | 1 | - | reviewed |\n"
        "\n"
    )

    def _issues(self):
        return (
            _make_issue(num="100", status="done")
            + "\n"
            + _make_issue(num="200", status="backlog")
        )

    def test_exits_2_and_emits_no_dispatch(self, tmp_path, capsys):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(self.TRUNCATED)
        issues = tmp_path / "issues.md"
        issues.write_text(self._issues())

        exit_code = main([
            "next-action",
            "--sprint-state", str(sprint),
            "--issues", str(issues),
            "--no-check-merged",
        ])
        captured = capsys.readouterr()
        assert exit_code == 2, captured
        # The regression pin: the re-implement dispatch must NOT be emitted.
        assert captured.out.strip() == "", captured.out
        assert "PIPELINE" not in captured.out
        assert "were not parsed" in captured.err, captured.err
        assert "ISSUE-200" in captured.err, captured.err

    def test_same_roster_without_the_stray_line_dispatches_ship(
        self, tmp_path, capsys
    ):
        """Both-direction pin: remove the invisible line and work flows again.

        Also the exact behaviour this fix protects — `reviewed` must SHIP, not
        re-enter the pipeline.
        """
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(self.TRUNCATED.replace("   \n", ""))
        issues = tmp_path / "issues.md"
        issues.write_text(self._issues())

        exit_code = main([
            "next-action",
            "--sprint-state", str(sprint),
            "--issues", str(issues),
            "--no-check-merged",
        ])
        out = json.loads(capsys.readouterr().out)
        assert exit_code == 0, out
        assert out["action"] == "SHIP", out
        assert out["targets"] == ["ISSUE-200"], out
        assert "unrostered" not in out, out

    def test_frozen_real_fixture_still_dispatches(self, tmp_path, capsys):
        """No false positive through the CLI on the real executor's file."""
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(_fixture_text("issue_progress_with_h3_subsection.md"))
        issues = tmp_path / "issues.md"
        issues.write_text(_make_issue(num="066", status="done"))

        exit_code = main([
            "next-action",
            "--sprint-state", str(sprint),
            "--issues", str(issues),
            "--no-check-merged",
        ])
        captured = capsys.readouterr()
        assert "were not parsed" not in captured.err, captured.err
        assert exit_code != 2, captured


class TestValidateWarnsOnATruncatedRoster:
    """`validate` keeps its verdict contract; the warning only names the cause."""

    def test_warns_on_stderr_without_changing_the_verdict(self, tmp_path, capsys):
        sprint = tmp_path / "sprint_state.md"
        sprint.write_text(
            _sprint_state(
                ROSTER_HEADER
                + "| ISSUE-100 | done | 1 | - | shipped |\n"
                "\n"
                "| ISSUE-200 | done | 1 | - | shipped |\n"
                "\n"
            )
        )
        exit_code = main([
            "validate",
            "--sprint-state", str(sprint),
            "--action", "SHIP",
            "--targets", "ISSUE-100,ISSUE-200",
        ])
        captured = capsys.readouterr()
        # Verdict unchanged: the truncated-away target still reports stuck.
        out = json.loads(captured.out)
        assert out["valid"] is False, out
        assert out["stuck"] == ["ISSUE-200"], out
        assert exit_code == 1
        # ... and the cause is now named instead of being a mystery.
        assert "were not parsed" in captured.err, captured.err

    def test_frozen_real_fixture_emits_no_warning(self, capsys):
        main([
            "validate",
            "--sprint-state",
            str(FIXTURES / "issue_progress_with_h3_subsection.md"),
            "--action", "SHIP",
            "--targets", "ISSUE-066,ISSUE-067,ISSUE-068",
        ])
        assert "were not parsed" not in capsys.readouterr().err


class TestFencedCodeBlocksAreNotRosterState:
    """A fenced example is illustration, never state (review lesson 4's fence clause).

    `agents/team-lead.md` teaches the writer agent a FENCED `## Issue Progress`
    example, so this is the kit's own documented output shape — not a contrived
    input. Pre-fix, the first fenced heading won the section outright and its
    illustration rows were dispatched as real work (main was identically broken,
    so this half is a pre-existing defect rather than a regression).
    """

    FENCED_EXAMPLE = (
        "Format reminder:\n"
        "\n"
        "```markdown\n"
        "## Issue Progress\n"
        + ROSTER_HEADER
        + "| ISSUE-900 | active | 0 | - | backlog |\n"
        "```\n"
        "\n"
    )

    def test_fenced_heading_does_not_win_the_section(self):
        """The real roster must be found even when a fenced one precedes it."""
        state = (
            "# Sprint State\n\n"
            "## Meta\n- Status: running\n\n"
            + self.FENCED_EXAMPLE
            + "## Issue Progress\n"
            + ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "\n## Escalations\n"
        )
        rows = sq.parse_sprint_table(state)
        assert [(r["issue"], r["phase"]) for r in rows] == [
            ("ISSUE-100", "reviewed")
        ]
        assert "ISSUE-900" not in [r["issue"] for r in rows], rows
        assert sq.unparsed_roster_rows(state) == []

    def test_fenced_example_under_the_real_heading_is_skipped(self):
        """A fenced illustration between the heading and the real table."""
        state = _sprint_state(
            "```\n"
            + ROSTER_HEADER
            + "| ISSUE-900 | active | 0 | - | backlog |\n"
            "```\n"
            "\n"
            + ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "\n"
        )
        rows = sq.parse_sprint_table(state)
        assert [r["issue"] for r in rows] == ["ISSUE-100"], rows
        assert sq.unparsed_roster_rows(state) == []

    def test_fenced_rows_are_never_reported_as_unparsed(self):
        """Over-firing direction: a fence AFTER the roster is not an under-read."""
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "\n"
            "```\n"
            "| ISSUE-900 | active | 0 | - | backlog |\n"
            "```\n"
            "\n"
        )
        assert [r["issue"] for r in sq.parse_sprint_table(state)] == ["ISSUE-100"]
        assert sq.unparsed_roster_rows(state) == []

    def test_tilde_fences_are_honoured(self):
        state = (
            "# Sprint State\n\n"
            "~~~\n"
            "## Issue Progress\n"
            + ROSTER_HEADER
            + "| ISSUE-900 | active | 0 | - | backlog |\n"
            "~~~\n"
            "\n"
            "## Issue Progress\n"
            + ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
        )
        assert [r["issue"] for r in sq.parse_sprint_table(state)] == ["ISSUE-100"]

    def test_a_fence_terminates_the_table_like_any_non_row_line(self):
        """A fence opening immediately after a row ends the table, per GFM.

        The rows below it are inside the fence, so they are illustration and must
        NOT be reported as truncated-away roster rows.
        """
        state = _sprint_state(
            ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "```\n"
            "| ISSUE-900 | active | 0 | - | backlog |\n"
            "```\n"
            "\n"
        )
        assert [r["issue"] for r in sq.parse_sprint_table(state)] == ["ISSUE-100"]
        assert sq.unparsed_roster_rows(state) == []

    def test_unfenced_helper_blanks_only_fenced_positions(self):
        """Direct unit pin on the helper, including the fence delimiters."""
        assert sq._unfenced(
            ["a", "```", "b", "```", "c"]
        ) == ["a", None, None, None, "c"]
        # An unterminated fence swallows the remainder — a renderer does the same.
        assert sq._unfenced(["a", "```", "b"]) == ["a", None, None]

    @pytest.mark.parametrize(
        "doc_path", REAL_SPRINT_STATE_DOCS, ids=lambda p: p.name
    )
    def test_fence_handling_does_not_change_any_real_doc(self, doc_path):
        """No real sprint_state doc contains a fence, so nothing may shift."""
        text = doc_path.read_text(encoding="utf-8")
        assert sq.parse_sprint_table(text), doc_path.name
        assert sq.unparsed_roster_rows(text) == [], doc_path.name

    def test_fewer_than_three_delimiters_is_not_a_fence(self):
        """Over-firing direction: a fence needs 3+ delimiters, per GFM.

        Without the threshold, an ordinary prose line opening with a backtick or
        a tilde blanks the rest of the section and silently zeroes the roster.
        """
        state = _sprint_state(
            "`parse_sprint_table` rosters this iteration:\n"
            "\n"
            + ROSTER_HEADER
            + "| ISSUE-100 | active | 1 | - | reviewed |\n"
            "\n"
        )
        assert [r["issue"] for r in sq.parse_sprint_table(state)] == ["ISSUE-100"]
        assert sq._unfenced(["`x`", "~approx~", "``y``"]) == [
            "`x`",
            "~approx~",
            "``y``",
        ]
