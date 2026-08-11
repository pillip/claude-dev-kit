"""Unit tests for scripts/sprint_queue.py."""

import json
import subprocess

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
        r = _runner(state="MERGED")
        _gh_pr_merge_state("PR-REF", runner=r)
        assert r.calls[0] == ["gh", "pr", "view", "PR-REF", "--json", "state,mergedAt"]


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
