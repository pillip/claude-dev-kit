"""RED-stage tests for ISSUE-067: the shared kit telemetry emitter
(``scripts/kit_telemetry.py``) must announce every skip/fallback path.

Contract under test (the module docstring of kit_telemetry.py is the API
contract; ISSUE-066 adopts it at ship-time):

- ``emit_event(event_type, payload=None, *, script_name, project_path=None,
  issue_id=None) -> bool`` — True = a line was written, False = skipped.
- Run-id resolution INSIDE the helper from env ``KIT_RUN_ID``:
  valid (``[A-Za-z0-9_-]{1,64}`` fullmatch) → clean path, prints NOTHING;
  unset/blank or invalid → event written under the explicit ``unattributed``
  run id with a top-level ``run_id_fallback`` field, plus ONE stdout
  announcement line naming the knob. The raw invalid value is NEVER used in
  a filename.
- ``.claude/runs/`` is auto-created (dir absence is no longer a silent-skip
  path, and mere creation is not announced).
- Containment violation (resolved runs dir escapes the project root) →
  announced, NOTHING written anywhere, returns False. The stdout line is the
  only signal on that path — tested via stdout + target emptiness, not JSONL.
- ISSUE-058 writer hardening preserved: O_NOFOLLOW append, 512-char detail
  truncation, 4096-byte event cap (the cap skip is now ANNOUNCED, previously
  a silent drop). Write failures announce; emit_event never raises.
- CLI: always exits 0 (non-blocking); invalid ``--payload`` JSON announces
  and writes nothing.

Mutation-tested in BOTH directions per the issue AC: each fallback asserts
its announcement; the clean path asserts stdout is EXACTLY empty
(hollow-pass guard). Asserted paths are pinned to the tmp_path fixture root.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import the modules under test from THIS checkout's scripts dir (pinned to
# the fixture root so a fallback resolution cannot hollow-pass elsewhere).
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kit_telemetry as kt  # noqa: E402
import synthesize_gate_results as sgr  # noqa: E402

CLI = SCRIPTS_DIR / "kit_telemetry.py"


# ── fixtures / helpers ───────────────────────────────────────────────


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """An isolated fake project root."""
    p = tmp_path / "proj"
    p.mkdir()
    return p


def _events(project: Path, run_id: str) -> list[dict]:
    path = project / ".claude" / "runs" / f"{run_id}.jsonl"
    assert path.is_file(), f"expected telemetry file at {path}"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _cli_env(run_id: str | None = None) -> dict:
    """Subprocess env: hermetic KIT_RUN_ID (conftest delenvs it in-process)."""
    env = dict(os.environ)
    env.pop(kt.RUN_ID_ENV, None)
    if run_id is not None:
        env[kt.RUN_ID_ENV] = run_id
    return env


def _run_cli(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        env=env,
    )


# ── clean path: valid KIT_RUN_ID → write, NO announcement ────────────


class TestCleanPath:
    def test_valid_run_id_writes_schema_exact_event_and_prints_nothing(
        self, project, monkeypatch, capsys
    ):
        """AC-1 clean direction (hollow-pass guard): a valid run id writes
        the schema-exact event and stdout is EXACTLY empty."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        (project / ".claude" / "runs").mkdir(parents=True)
        ok = kt.emit_event(
            "gates_degraded_path_used",
            {"reason": "skill_missing"},
            script_name="synthesize_gate_results",
            project_path=project,
        )
        assert ok is True
        [event] = _events(project, "testrun")
        # Exact schema per docs/telemetry_schema.md: issue_id only when
        # passed, and NO run_id_fallback on the clean path.
        assert set(event) == {"ts", "event_type", "skill_or_script", "payload"}
        assert event["event_type"] == "gates_degraded_path_used"
        assert event["skill_or_script"] == "synthesize_gate_results"
        assert event["payload"] == {"reason": "skill_missing"}
        ts = datetime.fromisoformat(event["ts"])
        assert ts.tzinfo is not None, "ts must be timezone-aware ISO-8601 UTC"
        assert capsys.readouterr().out == ""

    def test_issue_id_present_only_when_passed(self, project, monkeypatch, capsys):
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        ok = kt.emit_event(
            "spec_gate_triggered",
            {"mode": "sprint"},
            script_name="spec_gate",
            project_path=project,
            issue_id="ISSUE-067",
        )
        assert ok is True
        [event] = _events(project, "testrun")
        assert event["issue_id"] == "ISSUE-067"
        assert capsys.readouterr().out == ""

    def test_runs_dir_auto_created_on_clean_path_still_silent(
        self, project, monkeypatch, capsys
    ):
        """Dir absence is no longer a silent-skip path: the runs dir is
        auto-created, the event lands, and mere creation is NOT announced."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        assert not (project / ".claude").exists()
        ok = kt.emit_event(
            "test_event", {"k": "v"}, script_name="kit_test", project_path=project
        )
        assert ok is True
        assert (project / ".claude" / "runs" / "testrun.jsonl").is_file()
        assert capsys.readouterr().out == ""

    def test_second_emit_appends_not_overwrites(self, project, monkeypatch):
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        for i in range(2):
            assert kt.emit_event(
                "test_event", {"n": i}, script_name="kit_test", project_path=project
            )
        events = _events(project, "testrun")
        assert [e["payload"]["n"] for e in events] == [0, 1]


# ── KIT_RUN_ID fallback: unattributed + announced ────────────────────


class TestRunIdFallback:
    def test_unset_run_id_writes_unattributed_and_announces(self, project, capsys):
        """AC-2: without KIT_RUN_ID the event is written under the explicit
        ``unattributed`` run id — not dropped — with the fallback visible in
        the event body AND one stdout line naming the knob."""
        ok = kt.emit_event(
            "review_degraded_path_used",
            {"dimension": "code"},
            script_name="review",
            project_path=project,
        )
        assert ok is True
        [event] = _events(project, "unattributed")
        assert event["run_id_fallback"] == "KIT_RUN_ID unset"
        assert event["payload"] == {"dimension": "code"}
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert len(lines) == 1, f"expected exactly one announcement line: {out!r}"
        assert lines[0].startswith("[kit-telemetry]")
        assert "KIT_RUN_ID" in out, "the announcement must name the knob"
        assert "review_degraded_path_used" in out
        assert "unattributed" in out

    def test_blank_run_id_treated_as_unset(self, project, monkeypatch, capsys):
        monkeypatch.setenv(kt.RUN_ID_ENV, "   ")
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=project
        )
        assert ok is True
        [event] = _events(project, "unattributed")
        assert event["run_id_fallback"] == "KIT_RUN_ID unset"
        assert "KIT_RUN_ID" in capsys.readouterr().out

    @pytest.mark.parametrize("bad", ["../evil", "a b", "x" * 65])
    def test_invalid_run_id_falls_back_and_never_names_a_file_from_raw(
        self, project, tmp_path, monkeypatch, capsys, bad
    ):
        """An invalid KIT_RUN_ID still emits — under ``unattributed`` only.
        The raw value never becomes a filename anywhere under the fixture
        root; the announcement names the knob AND the whitelist."""
        monkeypatch.setenv(kt.RUN_ID_ENV, bad)
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=project
        )
        assert ok is True
        runs = project / ".claude" / "runs"
        assert [p.name for p in runs.iterdir()] == ["unattributed.jsonl"]
        for p in tmp_path.rglob("*"):
            assert bad not in p.name, f"raw invalid run id leaked into {p}"
        [event] = _events(project, "unattributed")
        assert "KIT_RUN_ID" in event["run_id_fallback"]
        assert "invalid" in event["run_id_fallback"]
        out = capsys.readouterr().out
        assert "KIT_RUN_ID" in out
        assert "[A-Za-z0-9_-]{1,64}" in out, "announcement must name the whitelist"


# ── containment violation: announced, NOTHING written ────────────────


class TestContainmentViolation:
    def _plant_escaping_runs_dir(self, project: Path, tmp_path: Path) -> Path:
        outside = tmp_path / "outside-runs"
        outside.mkdir()
        (project / ".claude").mkdir()
        (project / ".claude" / "runs").symlink_to(outside)
        return outside

    def test_symlinked_runs_dir_rejected_nothing_written(
        self, project, tmp_path, monkeypatch, capsys
    ):
        """A rejected containment violation writes NOTHING — its only signal
        is the stdout line (tested via output + target emptiness, not JSONL)."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        outside = self._plant_escaping_runs_dir(project, tmp_path)
        ok = kt.emit_event(
            "test_event", {"k": "v"}, script_name="kit_test", project_path=project
        )
        assert ok is False
        assert list(outside.iterdir()) == [], "containment must write nothing"
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert len(lines) == 1
        assert lines[0].startswith("[kit-telemetry]")
        assert "containment" in out
        assert "NOT written" in out
        assert "test_event" in out

    def test_symlinked_claude_dir_gains_no_directories(
        self, project, tmp_path, monkeypatch, capsys
    ):
        """Review fix (lesson 12 — pin the control's POSITION, not just its
        presence): containment must be checked BEFORE ``runs_dir.mkdir``.

        The sibling tests plant ``.claude/runs`` as a symlink to an
        ALREADY-EXISTING dir, where ``mkdir(exist_ok=True)`` is a no-op — so
        they pass even if the mkdir runs first. Here ``.claude`` itself is the
        symlink and ``runs/`` does not exist yet, so a mkdir ahead of the
        containment check creates ``<outside>/runs`` — an arbitrary-directory
        -creation primitive outside the project root. Mutation-verified:
        swapping the two lines makes THIS test fail and no other.
        """
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        outside = tmp_path / "outside-claude"
        outside.mkdir()
        before = sorted(p.name for p in outside.iterdir())
        (project / ".claude").symlink_to(outside)
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=project
        )
        assert ok is False
        assert sorted(p.name for p in outside.iterdir()) == before == [], (
            "containment must precede mkdir — the symlink target gained "
            f"entries: {[p.name for p in outside.iterdir()]}"
        )
        out = capsys.readouterr().out
        assert "containment" in out
        assert "NOT written" in out

    def test_containment_wins_over_run_id_fallback(self, project, tmp_path, capsys):
        """With KIT_RUN_ID unset AND a containment violation, nothing is
        written anywhere (no unattributed file either) and the announcement
        does not claim an event was written."""
        outside = self._plant_escaping_runs_dir(project, tmp_path)
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=project
        )
        assert ok is False
        assert list(outside.iterdir()) == []
        out = capsys.readouterr().out
        assert "containment" in out
        assert "written under" not in out, (
            "a rejected emit must not announce a successful fallback write"
        )


# ── ISSUE-058 writer hardening, now announced ────────────────────────


class TestWriteHardening:
    def test_symlinked_event_file_not_followed_and_announced(
        self, project, tmp_path, monkeypatch, capsys
    ):
        """O_NOFOLLOW preserved: a pre-planted symlink at the event path
        refuses the append — and (new) the refusal is announced."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        runs = project / ".claude" / "runs"
        runs.mkdir(parents=True)
        target = tmp_path / "outside-target"
        target.write_text("", encoding="utf-8")
        (runs / "testrun.jsonl").symlink_to(target)
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=project
        )
        assert ok is False
        assert target.read_text(encoding="utf-8") == ""
        out = capsys.readouterr().out
        assert "write failed" in out
        assert "test_event" in out

    def test_oversized_detail_truncated_not_dropped(self, project, monkeypatch):
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        payload = {"reason": "invalid_results", "detail": "x" * 10_000}
        ok = kt.emit_event(
            "gates_degraded_path_used",
            payload,
            script_name="synthesize_gate_results",
            project_path=project,
        )
        assert ok is True
        [event] = _events(project, "testrun")
        assert event["payload"]["detail"].endswith("…[truncated]")
        assert len(event["payload"]["detail"]) <= kt._MAX_DETAIL_CHARS + len(
            "…[truncated]"
        )
        # The caller's dict is not mutated by the truncation.
        assert len(payload["detail"]) == 10_000

    def test_oversize_event_skipped_with_announcement(
        self, project, monkeypatch, capsys
    ):
        """The 4 KiB cap skip was a silent drop pre-ISSUE-067 — it must now
        announce, naming the cap and the event type."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        ok = kt.emit_event(
            "test_event",
            {"filler": "y" * 5000},  # not 'detail' → no truncation applies
            script_name="kit_test",
            project_path=project,
        )
        assert ok is False
        assert not (project / ".claude" / "runs" / "testrun.jsonl").exists()
        out = capsys.readouterr().out
        assert "4096" in out, "the announcement must name the byte cap"
        assert "test_event" in out
        assert "NOT written" in out

    def test_absent_project_root_is_refused_not_created(
        self, tmp_path, monkeypatch, capsys
    ):
        """Review fix (PR #123 security finding F1): the emitter auto-creates
        ``.claude/runs/`` but NEVER the project root — otherwise an
        attacker-influenced ``--project-path`` is a multi-level
        directory-creation primitive in an arbitrary location.

        Mutation direction 2 (the AC is NOT regressed) is pinned by
        ``test_runs_dir_auto_created_on_clean_path_still_silent``: inside an
        EXISTING root, dir absence is still not a skip path.
        """
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        absent = tmp_path / "does" / "not" / "exist" / "yet"
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=absent
        )
        assert ok is False
        assert not (tmp_path / "does").exists(), (
            "the emitter must not materialize the project root"
        )
        out = capsys.readouterr().out
        assert "[kit-telemetry]" in out
        assert "not an existing directory" in out
        assert "NOT written" in out

    def test_absent_project_root_refused_through_the_cli(self, tmp_path):
        """Same control at the surface F1 actually targets — the CLI whose
        ``--project-path`` is model-chosen at the SKILL call sites."""
        absent = tmp_path / "victim" / "tree"
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--project-path", str(absent),
            ],
            _cli_env("clirun"),
        )
        assert result.returncode == 0, result.stderr
        assert "not an existing directory" in result.stdout
        assert not (tmp_path / "victim").exists()

    def test_never_raises_on_bogus_project_path(self, tmp_path, capsys):
        """Non-blocking instrument: a project path that is a regular file
        cannot host a runs dir — emit_event announces and returns False
        instead of raising."""
        bogus = tmp_path / "afile"
        bogus.write_text("not a directory", encoding="utf-8")
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=bogus
        )
        assert ok is False
        out = capsys.readouterr().out
        assert "[kit-telemetry]" in out
        assert "NOT written" in out


# ── CLI (skill-prompt call sites) ────────────────────────────────────


class TestCli:
    def test_clean_path_writes_event_and_exits_zero(self, project):
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--payload", '{"dimension": "code"}',
                "--issue-id", "ISSUE-067",
                "--project-path", str(project),
            ],
            _cli_env("clirun"),
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
        [event] = _events(project, "clirun")
        assert event["event_type"] == "review_degraded_path_used"
        assert event["skill_or_script"] == "review"
        assert event["payload"] == {"dimension": "code"}
        assert event["issue_id"] == "ISSUE-067"
        assert "run_id_fallback" not in event

    def test_without_run_id_exits_zero_announces_and_writes_unattributed(
        self, project
    ):
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--payload", '{"dimension": "security"}',
                "--project-path", str(project),
            ],
            _cli_env(),
        )
        assert result.returncode == 0, result.stderr
        assert "[kit-telemetry]" in result.stdout
        assert "KIT_RUN_ID" in result.stdout
        [event] = _events(project, "unattributed")
        assert event["run_id_fallback"] == "KIT_RUN_ID unset"

    def test_invalid_payload_json_exits_zero_announces_writes_nothing(self, project):
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--payload", "{not json",
                "--project-path", str(project),
            ],
            _cli_env("clirun"),
        )
        assert result.returncode == 0, result.stderr
        assert "--payload" in result.stdout
        assert "NOT written" in result.stdout
        assert not (project / ".claude").exists(), "invalid payload must write nothing"


# ── migration seam: synthesize_gate_results delegates to the helper ──


class TestSynthesizeGateResultsMigration:
    def test_sgr_emit_telemetry_delegates_to_shared_helper(
        self, project, monkeypatch
    ):
        """Lesson 3: mock the delegation seam (kit_telemetry.emit_event),
        assert_called_once, and pin the identity-bearing kwargs."""
        recorder = MagicMock(return_value=True)
        monkeypatch.setattr(kt, "emit_event", recorder)
        sgr._emit_telemetry(
            project, "gates_degraded_path_used", {"reason": "skill_missing"}
        )
        recorder.assert_called_once()
        call = recorder.call_args
        assert call.args[0] == "gates_degraded_path_used"
        assert call.args[1] == {"reason": "skill_missing"}
        assert call.kwargs["script_name"] == "synthesize_gate_results"
        assert call.kwargs["project_path"] == project

    def test_run_id_env_knob_has_a_single_home(self):
        """RUN_ID_ENV stays importable from sgr (existing test surface) but
        aliases the shared helper's constant — one home for the knob."""
        assert sgr.RUN_ID_ENV == "KIT_RUN_ID"
        assert sgr.RUN_ID_ENV is kt.RUN_ID_ENV
