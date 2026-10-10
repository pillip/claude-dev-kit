"""Unit tests for scripts/review_context.py (ISSUE-066 / SPEC-066).

Covers the context-decision-once module for /review's SPEC-019 delegation:
- the pure decision table (``decide_review_context`` with an injected probe):
  probe exit 1 -> degraded/``capability-absent``; probe 0/2 + invocation
  tools absent -> degraded/``context-unreachable``; probe 0/2 + tools
  present -> delegated — including mixed per-dimension modes,
- closed-vocabulary validation at the CLI boundary (bad --invocation-tools,
  bad issue id, unknown emit event/dimension/reason -> exit 2, no event),
- the hardened best-effort telemetry seam ``_emit_event`` (KIT_RUN_ID
  whitelist, runs-dir containment, O_NOFOLLOW, 4096-byte cap, long-string
  truncation, never raises, silent no-op when unconfigured),
- the decision-made-once property: one ``decide`` call covers BOTH
  dimensions and emits at most one reason-tagged event per dimension.

Absence assertions ("no event written") are pinned by positive controls in
the same test (the same fixture WITH valid config DOES write), per the
review-lessons mutation-direction discipline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Import the module under test from THIS checkout's scripts dir (pinned to the
# fixture root so a fallback resolution cannot hollow-pass against another repo).
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import review_context as rc  # noqa: E402


# ── fixtures / helpers ───────────────────────────────────────────────

RUN_ID = "testrun"


def _probe_map(codes: dict[str, int]):
    """Injected probe returning (exit_code, evidence) per skill name."""

    def probe(name: str) -> tuple[int, str]:
        return codes[name], "stub"

    return probe


def _patch_probe(monkeypatch, codes: dict[str, int]):
    """Mock the probe at the delegation seam (has_skill.find_skill)."""
    monkeypatch.setattr(rc.has_skill, "find_skill", _probe_map(codes))


@pytest.fixture()
def project(tmp_path: Path, monkeypatch) -> Path:
    """Isolated fake project root with a runs dir; cwd for the CLI."""
    p = tmp_path / "proj"
    (p / ".claude" / "runs").mkdir(parents=True)
    monkeypatch.chdir(p)
    return p


def _events(project: Path, run_id: str = RUN_ID) -> list[dict]:
    path = project / ".claude" / "runs" / f"{run_id}.jsonl"
    assert path.is_file(), f"expected telemetry file at {path}"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _no_events(project: Path, run_id: str = RUN_ID) -> bool:
    return not (project / ".claude" / "runs" / f"{run_id}.jsonl").exists()


# KIT_RUN_ID ambient isolation is suite-wide (tests/conftest.py autouse
# fixture deletes it) — telemetry tests must opt in via monkeypatch.setenv.


# ── pure decision table ──────────────────────────────────────────────


class TestDecideReviewContext:
    @pytest.mark.parametrize("code_probe", [0, 2])
    @pytest.mark.parametrize("security_probe", [0, 2])
    def test_tools_present_with_probe_0_or_2_delegates_both(
        self, code_probe, security_probe
    ):
        # Probe exit 0 (filesystem-visible) delegates exactly like exit 2.
        decisions = rc.decide_review_context(
            "present",
            probe=_probe_map(
                {"code-review": code_probe, "security-review": security_probe}
            ),
        )
        assert decisions == {
            "code": {"path": "delegated", "reason": ""},
            "security": {"path": "delegated", "reason": ""},
        }

    @pytest.mark.parametrize("invocation_tools", ["present", "absent"])
    def test_probe_exit_1_degrades_capability_absent_regardless_of_tools(
        self, invocation_tools
    ):
        decisions = rc.decide_review_context(
            invocation_tools,
            probe=_probe_map({"code-review": 1, "security-review": 1}),
        )
        assert decisions == {
            "code": {"path": "degraded", "reason": "capability-absent"},
            "security": {"path": "degraded", "reason": "capability-absent"},
        }

    @pytest.mark.parametrize("probe_code", [0, 2])
    def test_tools_absent_with_probe_0_or_2_degrades_context_unreachable(
        self, probe_code
    ):
        decisions = rc.decide_review_context(
            "absent",
            probe=_probe_map(
                {"code-review": probe_code, "security-review": probe_code}
            ),
        )
        assert decisions == {
            "code": {"path": "degraded", "reason": "context-unreachable"},
            "security": {"path": "degraded", "reason": "context-unreachable"},
        }

    def test_mixed_capability_absent_and_context_unreachable(self):
        # code probe=1 + security probe=2 with tools absent: two different
        # degradation reasons in ONE decision.
        decisions = rc.decide_review_context(
            "absent",
            probe=_probe_map({"code-review": 1, "security-review": 2}),
        )
        assert decisions == {
            "code": {"path": "degraded", "reason": "capability-absent"},
            "security": {"path": "degraded", "reason": "context-unreachable"},
        }

    def test_mixed_capability_absent_and_delegated(self):
        decisions = rc.decide_review_context(
            "present",
            probe=_probe_map({"code-review": 1, "security-review": 0}),
        )
        assert decisions == {
            "code": {"path": "degraded", "reason": "capability-absent"},
            "security": {"path": "delegated", "reason": ""},
        }

    def test_probe_receives_the_runtime_skill_names(self):
        # Pin the dimension -> runtime skill-name mapping.
        seen: list[str] = []

        def probe(name: str) -> tuple[int, str]:
            seen.append(name)
            return 2, "stub"

        rc.decide_review_context("present", probe=probe)
        assert sorted(seen) == ["code-review", "security-review"]
        assert len(seen) == 2  # exactly one probe call per dimension

    def test_invalid_invocation_tools_raises_value_error(self):
        with pytest.raises(ValueError):
            rc.decide_review_context(
                "maybe", probe=_probe_map({"code-review": 2, "security-review": 2})
            )


# ── decide CLI ───────────────────────────────────────────────────────


class TestDecideCli:
    def test_decide_prints_json_with_issue_and_both_dimensions(
        self, project, monkeypatch, capsys
    ):
        _patch_probe(monkeypatch, {"code-review": 2, "security-review": 2})
        rcode = rc.main(
            ["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"]
        )
        assert rcode == 0
        data = json.loads(capsys.readouterr().out)
        assert data["issue_id"] == "ISSUE-066"
        assert data["invocation_tools"] == "absent"
        assert set(data["dimensions"]) == {"code", "security"}
        for decision in data["dimensions"].values():
            assert decision == {"path": "degraded", "reason": "context-unreachable"}

    def test_decide_tools_present_reports_delegated(
        self, project, monkeypatch, capsys
    ):
        _patch_probe(monkeypatch, {"code-review": 2, "security-review": 0})
        rcode = rc.main(
            ["decide", "--invocation-tools", "present", "--issue", "ISSUE-066"]
        )
        assert rcode == 0
        data = json.loads(capsys.readouterr().out)
        assert data["dimensions"]["code"] == {"path": "delegated", "reason": ""}
        assert data["dimensions"]["security"] == {"path": "delegated", "reason": ""}

    def test_decide_bad_invocation_tools_exits_2_writes_nothing(
        self, project, monkeypatch
    ):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        _patch_probe(monkeypatch, {"code-review": 2, "security-review": 2})
        rcode = rc.main(
            ["decide", "--invocation-tools", "maybe", "--issue", "ISSUE-066"]
        )
        assert rcode == 2
        assert _no_events(project)
        # Positive control: the same fixture with a valid flag DOES write.
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        assert len(_events(project)) == 2

    @pytest.mark.parametrize(
        "bad_issue", ["066", "ISSUE-", "ISSUE-66x", "issue-066", "../evil"]
    )
    def test_decide_bad_issue_id_exits_2_writes_nothing(
        self, project, monkeypatch, bad_issue
    ):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        _patch_probe(monkeypatch, {"code-review": 1, "security-review": 1})
        rcode = rc.main(["decide", "--invocation-tools", "absent", "--issue", bad_issue])
        assert rcode == 2
        assert _no_events(project)

    def test_decide_missing_issue_exits_2(self, project, monkeypatch):
        _patch_probe(monkeypatch, {"code-review": 2, "security-review": 2})
        assert rc.main(["decide", "--invocation-tools", "absent"]) == 2

    def test_no_subcommand_exits_2(self, project):
        assert rc.main([]) == 2


# ── telemetry: decide-time emissions ─────────────────────────────────


class TestDecideTelemetry:
    def test_one_reason_tagged_event_per_degraded_dimension(
        self, project, monkeypatch
    ):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        _patch_probe(monkeypatch, {"code-review": 1, "security-review": 2})
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        events = _events(project)
        assert len(events) == 2
        by_dim = {e["payload"]["dimension"]: e for e in events}
        assert set(by_dim) == {"code", "security"}
        assert by_dim["code"]["payload"]["reason"] == "capability-absent"
        assert by_dim["security"]["payload"]["reason"] == "context-unreachable"
        for event in events:
            assert event["event_type"] == "review_degraded_path_used"
            assert event["skill_or_script"] == "review_context"
            assert event["issue_id"] == "ISSUE-066"
            assert "ts" in event

    def test_delegated_dimensions_emit_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        _patch_probe(monkeypatch, {"code-review": 2, "security-review": 2})
        # Positive control first: tools absent in project A DOES write.
        proj_a = tmp_path / "proj_a"
        (proj_a / ".claude" / "runs").mkdir(parents=True)
        monkeypatch.chdir(proj_a)
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        assert len(_events(proj_a)) == 2
        # Absence under test: tools present in project B writes nothing.
        proj_b = tmp_path / "proj_b"
        (proj_b / ".claude" / "runs").mkdir(parents=True)
        monkeypatch.chdir(proj_b)
        assert (
            rc.main(["decide", "--invocation-tools", "present", "--issue", "ISSUE-066"])
            == 0
        )
        assert _no_events(proj_b)

    def test_decision_made_once_single_event_per_dimension_json_carries_both(
        self, project, monkeypatch, capsys
    ):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        _patch_probe(monkeypatch, {"code-review": 2, "security-review": 2})
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        data = json.loads(capsys.readouterr().out)
        assert set(data["dimensions"]) == {"code", "security"}
        events = _events(project)
        # At most ONE emission per dimension — no per-dimension retry detour.
        dims = [e["payload"]["dimension"] for e in events]
        assert sorted(dims) == ["code", "security"]

    def test_unset_run_id_is_silent_noop_exit_0(self, project, monkeypatch):
        # conftest's autouse fixture guarantees KIT_RUN_ID is unset here.
        _patch_probe(monkeypatch, {"code-review": 1, "security-review": 1})
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        assert _no_events(project)
        # Positive control: same fixture WITH the run id set does write.
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        assert len(_events(project)) == 2

    def test_invalid_run_id_refused(self, project, monkeypatch, tmp_path):
        monkeypatch.setenv("KIT_RUN_ID", "../evil")
        _patch_probe(monkeypatch, {"code-review": 1, "security-review": 1})
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        assert list((project / ".claude" / "runs").iterdir()) == []
        assert not (project / ".claude" / "evil.jsonl").exists()
        # Positive control: a whitelisted run id in the same fixture writes.
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        assert len(_events(project)) == 2

    def test_symlinked_event_file_not_followed(self, project, tmp_path, monkeypatch):
        # A pre-planted symlink at the event path must not redirect the
        # append outside the project (O_NOFOLLOW) — and must not raise.
        target = tmp_path / "outside-target"
        target.write_text("", encoding="utf-8")
        (project / ".claude" / "runs" / f"{RUN_ID}.jsonl").symlink_to(target)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        _patch_probe(monkeypatch, {"code-review": 1, "security-review": 1})
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        assert target.read_text(encoding="utf-8") == ""

    def test_symlinked_runs_dir_not_written(self, tmp_path, monkeypatch):
        # .claude/runs symlinked outside the project -> realpath containment
        # fails -> silent no-op, nothing lands at the symlink target.
        proj = tmp_path / "proj"
        (proj / ".claude").mkdir(parents=True)
        outside = tmp_path / "outside-runs"
        outside.mkdir()
        (proj / ".claude" / "runs").symlink_to(outside)
        monkeypatch.chdir(proj)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        _patch_probe(monkeypatch, {"code-review": 1, "security-review": 1})
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-066"])
            == 0
        )
        assert list(outside.iterdir()) == []


# ── telemetry: _emit_event hardening ─────────────────────────────────


class TestEmitEventHardening:
    def test_never_raises_on_nonexistent_project(self, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        # Must be a silent no-op, never an exception.
        rc._emit_event(
            Path("/nonexistent-kit-issue-066"),
            "review_degraded_path_used",
            {"dimension": "code", "reason": "capability-absent"},
        )

    def test_never_raises_when_runs_path_is_a_file(self, tmp_path, monkeypatch):
        proj = tmp_path / "proj"
        (proj / ".claude").mkdir(parents=True)
        (proj / ".claude" / "runs").write_text("not a dir", encoding="utf-8")
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rc._emit_event(
            proj,
            "review_degraded_path_used",
            {"dimension": "code", "reason": "capability-absent"},
        )
        assert (proj / ".claude" / "runs").read_text(encoding="utf-8") == "not a dir"

    def test_long_string_values_truncated_not_dropped(self, project, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rc._emit_event(
            project,
            "review_delegated_to_code_review",
            {"pr_number": "9" * 10_000},
            issue_id="ISSUE-066",
        )
        event = _events(project)[0]
        assert event["payload"]["pr_number"].endswith("…[truncated]")
        assert len(event["payload"]["pr_number"]) <= rc._MAX_DETAIL_CHARS + len(
            "…[truncated]"
        )

    def test_event_over_4096_cap_dropped(self, project, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        # 20 keys x 400 chars: no single value trips truncation, but the
        # whole event exceeds the 4096-byte POSIX-atomicity cap -> dropped.
        oversized = {f"k{i}": "x" * 400 for i in range(20)}
        rc._emit_event(project, "review_degraded_path_used", oversized)
        assert _no_events(project)
        # Positive control: a small payload in the same fixture writes.
        rc._emit_event(
            project, "review_degraded_path_used", {"dimension": "code"}
        )
        assert len(_events(project)) == 1


# ── emit CLI (the prose-side seam) ───────────────────────────────────


class TestEmitCli:
    def test_emit_delegated_code_review_with_pr(self, project, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rcode = rc.main(
            [
                "emit",
                "--event",
                "review_delegated_to_code_review",
                "--issue",
                "ISSUE-066",
                "--pr",
                "123",
            ]
        )
        assert rcode == 0
        events = _events(project)
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "review_delegated_to_code_review"
        assert event["skill_or_script"] == "review_context"
        assert event["issue_id"] == "ISSUE-066"
        assert event["payload"]["pr_number"] == "123"

    def test_emit_delegated_security_review_without_pr(self, project, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rcode = rc.main(
            [
                "emit",
                "--event",
                "review_delegated_to_security_review",
                "--issue",
                "ISSUE-066",
            ]
        )
        assert rcode == 0
        event = _events(project)[0]
        assert event["event_type"] == "review_delegated_to_security_review"
        assert "pr_number" not in event["payload"]

    def test_emit_degraded_inline_attempt_failed(self, project, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rcode = rc.main(
            [
                "emit",
                "--event",
                "review_degraded_path_used",
                "--dimension",
                "security",
                "--reason",
                "inline-attempt-failed",
                "--issue",
                "ISSUE-066",
            ]
        )
        assert rcode == 0
        event = _events(project)[0]
        assert event["event_type"] == "review_degraded_path_used"
        assert event["payload"] == {
            "dimension": "security",
            "reason": "inline-attempt-failed",
        }

    def test_emit_unknown_event_exits_2_writes_nothing(self, project, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rcode = rc.main(
            ["emit", "--event", "review_forged_event", "--issue", "ISSUE-066"]
        )
        assert rcode == 2
        assert _no_events(project)
        # Positive control: an allowlisted event in the same fixture writes.
        assert (
            rc.main(
                [
                    "emit",
                    "--event",
                    "review_delegated_to_code_review",
                    "--issue",
                    "ISSUE-066",
                ]
            )
            == 0
        )
        assert len(_events(project)) == 1

    @pytest.mark.parametrize(
        "decide_time_reason", ["capability-absent", "context-unreachable"]
    )
    def test_emit_degraded_with_decide_time_reason_exits_2(
        self, project, monkeypatch, decide_time_reason
    ):
        # decide-time reasons are emitted by `decide` ONLY — the prose seam
        # accepts exactly inline-attempt-failed.
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rcode = rc.main(
            [
                "emit",
                "--event",
                "review_degraded_path_used",
                "--dimension",
                "code",
                "--reason",
                decide_time_reason,
                "--issue",
                "ISSUE-066",
            ]
        )
        assert rcode == 2
        assert _no_events(project)

    def test_emit_degraded_bad_dimension_exits_2(self, project, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rcode = rc.main(
            [
                "emit",
                "--event",
                "review_degraded_path_used",
                "--dimension",
                "figma",
                "--reason",
                "inline-attempt-failed",
                "--issue",
                "ISSUE-066",
            ]
        )
        assert rcode == 2
        assert _no_events(project)

    def test_emit_degraded_missing_dimension_or_reason_exits_2(
        self, project, monkeypatch
    ):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        assert (
            rc.main(
                [
                    "emit",
                    "--event",
                    "review_degraded_path_used",
                    "--reason",
                    "inline-attempt-failed",
                    "--issue",
                    "ISSUE-066",
                ]
            )
            == 2
        )
        assert (
            rc.main(
                [
                    "emit",
                    "--event",
                    "review_degraded_path_used",
                    "--dimension",
                    "code",
                    "--issue",
                    "ISSUE-066",
                ]
            )
            == 2
        )
        assert _no_events(project)

    def test_emit_delegated_with_degraded_only_flags_exits_2(
        self, project, monkeypatch
    ):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rcode = rc.main(
            [
                "emit",
                "--event",
                "review_delegated_to_code_review",
                "--dimension",
                "code",
                "--issue",
                "ISSUE-066",
            ]
        )
        assert rcode == 2
        assert _no_events(project)

    def test_emit_bad_issue_id_exits_2(self, project, monkeypatch):
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        rcode = rc.main(
            ["emit", "--event", "review_delegated_to_code_review", "--issue", "nope"]
        )
        assert rcode == 2
        assert _no_events(project)

    def test_emit_unconfigured_is_silent_noop_exit_0(self, project):
        # KIT_RUN_ID unset (conftest autouse) -> exit still 0, nothing written.
        rcode = rc.main(
            [
                "emit",
                "--event",
                "review_delegated_to_code_review",
                "--issue",
                "ISSUE-066",
            ]
        )
        assert rcode == 0
        assert _no_events(project)
