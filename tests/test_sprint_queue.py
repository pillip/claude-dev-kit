"""Unit tests for scripts/sprint_queue.py."""

import json

from scripts.sprint_queue import (
    choose_action,
    compute_queues,
    main,
    parse_issues_metadata,
    parse_sprint_table,
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
