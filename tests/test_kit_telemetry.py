"""Tests for the shared kit telemetry emitter (``scripts/kit_telemetry.py``):
it must announce every skip/fallback path (ISSUE-067) and it must be
containable, un-hangable and non-raising (ISSUE-070).

ISSUE-070 additions (see the classes at the bottom of this file):

- ``project_path`` is NO LONGER the containment root. The root is derived
  independently of the caller — main git work-tree root of the process CWD,
  else ``CLAUDE_PROJECT_DIR``, else CWD — so the containment check is
  FALSIFIABLE. Every test therefore has to establish the root it expects;
  the ``kit_root`` fixture does that and self-checks it.
- Planted-node family at the event path (FIFO / symlink / socket / directory
  / hardlink / device node) and the TOCTOU window between the containment
  check and the open. The FIFO probe runs in a BOUNDED subprocess and
  surfaces a hang as exit ``124`` — a distinct outcome from a wrong
  assertion, because a hang is what the guard actually prevents.
- ``emit_event`` NEVER raises is the CHOSEN contract (the catch set was
  widened rather than the docstring narrowed), pinned with stdout closed
  both in-process and in a real subprocess.

Contract under test (the module docstring of kit_telemetry.py is the API
contract; ISSUE-066/075 adopt it at ship-time):

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

import io
import json
import os
import socket
import stat
import subprocess
import sys
import textwrap
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
WORKTREE_SH = SCRIPTS_DIR / "worktree.sh"

# Wall-clock bound for every subprocess probe in this file. Without the
# ISSUE-070 open guard a FIFO planted at the event path blocks ``os.open``
# FOREVER, so these probes MUST be bounded or a guard regression hangs the
# whole suite instead of failing it. Env-configurable rather than hard-coded
# (recurring ISSUE-046/047 review lesson), and a timeout is surfaced as the
# ``timeout(1)`` convention exit code 124 so a HANG is a DISTINCT outcome
# from a non-zero exit or a merely different assertion.
PROBE_TIMEOUT_ENV = "KIT_TELEMETRY_PROBE_TIMEOUT"
DEFAULT_PROBE_TIMEOUT = 20.0
TIMEOUT_RC = 124


def _probe_timeout() -> float:
    raw = os.environ.get(PROBE_TIMEOUT_ENV, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_PROBE_TIMEOUT
    return value if value > 0 else DEFAULT_PROBE_TIMEOUT


# ── fixtures / helpers ───────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _hermetic_project_dir_env(monkeypatch):
    """ISSUE-070: ``CLAUDE_PROJECT_DIR`` participates in the containment-root
    derivation, so a value leaking in from the developer's shell would widen
    or narrow every containment assertion in this file. Cleared file-wide and
    set explicitly by the fixtures that need it (lesson 3 — hermetic delenv
    for the shared helper's env knobs).
    """
    monkeypatch.delenv(kt.PROJECT_DIR_ENV, raising=False)


@pytest.fixture()
def kit_root(tmp_path: Path, monkeypatch) -> Path:
    """The independently-derived containment root for a test (ISSUE-070).

    ``emit_event`` no longer treats ``project_path`` as its own containment
    root, so a test has to establish the real one. The assertion is a fixture
    self-check: if the derivation ever resolved somewhere else (an ambient
    repo, a stale env var), these tests would silently stop testing
    containment instead of failing.
    """
    root = tmp_path / "kitroot"
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv(kt.PROJECT_DIR_ENV, str(root))
    assert kt._containment_root() == root.resolve(), (
        "fixture self-check: the containment root under test must be the "
        "fixture root, not an ambient repo"
    )
    return root


@pytest.fixture()
def project(kit_root: Path) -> Path:
    """An isolated fake project root INSIDE the containment root."""
    p = kit_root / "proj"
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


def _cli_env(run_id: str | None = None, project_dir: Path | None = None) -> dict:
    """Subprocess env: hermetic KIT_RUN_ID / CLAUDE_PROJECT_DIR."""
    env = dict(os.environ)
    env.pop(kt.RUN_ID_ENV, None)
    env.pop(kt.PROJECT_DIR_ENV, None)
    if run_id is not None:
        env[kt.RUN_ID_ENV] = run_id
    if project_dir is not None:
        env[kt.PROJECT_DIR_ENV] = str(project_dir)
    return env


def _run_cli(
    args: list[str], env: dict, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=None if cwd is None else str(cwd),
        timeout=_probe_timeout(),
    )


def _run_cli_bounded(
    args: list[str], env: dict, cwd: Path
) -> tuple[int, str, str]:
    """Run the CLI under the wall-clock bound, reporting a hang as rc 124.

    Separate from ``_run_cli`` on purpose: here the timeout is the OUTCOME
    under test, so it must be caught and classified rather than raised.
    """
    try:
        done = subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(cwd),
            timeout=_probe_timeout(),
        )
    except subprocess.TimeoutExpired as exc:
        def _text(blob) -> str:
            if blob is None:
                return ""
            return blob.decode("utf-8", "replace") if isinstance(blob, bytes) else blob

        return TIMEOUT_RC, _text(exc.stdout), _text(exc.stderr)
    return done.returncode, done.stdout, done.stderr


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=kit@example.invalid",
            "-c",
            "user.name=kit",
            *args,
        ],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        timeout=_probe_timeout(),
    )


def _make_repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A real git repo plus a real linked worktree at ``<repo>/.worktrees/x``
    — the exact layout ``scripts/worktree.sh create`` produces, which is what
    ISSUE-075's worktree-rooted caller will run from."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init", "--no-verify")
    wt = repo / ".worktrees" / "feat"
    _git(repo, "worktree", "add", "-q", "-b", "feat", str(wt))
    return repo, wt


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
        self, kit_root, monkeypatch, capsys
    ):
        """Review fix (PR #123 security finding F1): the emitter auto-creates
        ``.claude/runs/`` but NEVER the project root — otherwise an
        attacker-influenced ``--project-path`` is a multi-level
        directory-creation primitive in an arbitrary location.

        Mutation direction 2 (the AC is NOT regressed) is pinned by
        ``test_runs_dir_auto_created_on_clean_path_still_silent``: inside an
        EXISTING root, dir absence is still not a skip path.

        ISSUE-070: the absent path is INSIDE the containment root, so this
        test still exercises the existence probe — which now runs strictly
        after containment, never before it.
        """
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        absent = kit_root / "does" / "not" / "exist" / "yet"
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=absent
        )
        assert ok is False
        assert not (kit_root / "does").exists(), (
            "the emitter must not materialize the project root"
        )
        out = capsys.readouterr().out
        assert "[kit-telemetry]" in out
        assert "not an existing directory" in out
        assert "NOT written" in out

    def test_absent_project_root_refused_through_the_cli(self, kit_root):
        """Same control at the surface F1 actually targets — the CLI whose
        ``--project-path`` is model-chosen at the SKILL call sites."""
        absent = kit_root / "victim" / "tree"
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--project-path", str(absent),
            ],
            _cli_env("clirun", kit_root),
            cwd=kit_root,
        )
        assert result.returncode == 0, result.stderr
        assert "not an existing directory" in result.stdout
        assert not (kit_root / "victim").exists()

    def test_never_raises_on_bogus_project_path(self, kit_root, capsys):
        """Non-blocking instrument: a project path that is a regular file
        cannot host a runs dir — emit_event announces and returns False
        instead of raising."""
        bogus = kit_root / "afile"
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
    def test_clean_path_writes_event_and_exits_zero(self, kit_root, project):
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--payload", '{"dimension": "code"}',
                "--issue-id", "ISSUE-067",
                "--project-path", str(project),
            ],
            _cli_env("clirun", kit_root),
            cwd=kit_root,
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
        self, kit_root, project
    ):
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--payload", '{"dimension": "security"}',
                "--project-path", str(project),
            ],
            _cli_env(project_dir=kit_root),
            cwd=kit_root,
        )
        assert result.returncode == 0, result.stderr
        assert "[kit-telemetry]" in result.stdout
        assert "KIT_RUN_ID" in result.stdout
        [event] = _events(project, "unattributed")
        assert event["run_id_fallback"] == "KIT_RUN_ID unset"

    def test_invalid_payload_json_exits_zero_announces_writes_nothing(
        self, kit_root, project
    ):
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--payload", "{not json",
                "--project-path", str(project),
            ],
            _cli_env("clirun", kit_root),
            cwd=kit_root,
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


# ═════════════════════════════════════════════════════════════════════
# ISSUE-070 — containment root, planted-node hardening, no-raise contract
# ═════════════════════════════════════════════════════════════════════


class TestContainmentRootDerivation:
    """TC-070a — ``_main_repo_root`` mirrors ``bash scripts/worktree.sh root``.

    Lesson 4/16: a hand-rolled mirror of an oracle the repo already owns must
    be pinned against that oracle, including the linked-worktree case — which
    is the one ISSUE-075 depends on. ``worktree.sh`` cannot be imported from
    Python, so it is consulted as a subprocess here instead.
    """

    @staticmethod
    def _oracle(cwd: Path) -> Path:
        done = subprocess.run(
            ["bash", str(WORKTREE_SH), "root"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=_probe_timeout(),
        )
        assert done.returncode == 0, done.stderr
        return Path(done.stdout.strip()).resolve()

    def test_matches_the_oracle_in_this_checkout(self, monkeypatch):
        """Runs from whatever checkout the suite lives in — the main repo on
        main, a linked worktree during a sprint. Both must agree."""
        for cwd in (SCRIPTS_DIR.parent, SCRIPTS_DIR):
            monkeypatch.chdir(cwd)
            assert kt._containment_root() == self._oracle(cwd), cwd

    def test_matches_the_oracle_for_a_real_repo_and_its_linked_worktree(
        self, tmp_path, monkeypatch
    ):
        repo, wt = _make_repo_with_worktree(tmp_path)
        (repo / "sub").mkdir()
        (wt / "sub").mkdir()
        for cwd in (repo, repo / "sub", wt, wt / "sub"):
            monkeypatch.chdir(cwd)
            derived = kt._containment_root()
            assert derived == self._oracle(cwd), cwd
            assert derived == repo.resolve(), cwd

    def test_a_worktree_is_inside_the_derived_root(self, tmp_path, monkeypatch):
        """The structural fact ISSUE-075 rests on: ``worktree.sh create``
        puts worktrees at ``<main-root>/.worktrees/<slug>``, so a root derived
        independently of the caller still admits a worktree-rooted caller."""
        repo, wt = _make_repo_with_worktree(tmp_path)
        monkeypatch.chdir(wt)
        assert wt.resolve().is_relative_to(kt._containment_root())

    def test_env_knob_is_the_fallback_when_there_is_no_git_work_tree(
        self, tmp_path, monkeypatch
    ):
        plain = tmp_path / "plain"
        plain.mkdir()
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(plain)
        monkeypatch.setenv(kt.PROJECT_DIR_ENV, str(elsewhere))
        assert kt._containment_root() == elsewhere.resolve()
        # ...and CWD is the last resort when the knob names nothing usable.
        monkeypatch.setenv(kt.PROJECT_DIR_ENV, str(tmp_path / "nope"))
        assert kt._containment_root() == plain.resolve()
        monkeypatch.delenv(kt.PROJECT_DIR_ENV)
        assert kt._containment_root() == plain.resolve()

    @pytest.mark.parametrize(
        "shape",
        ["sibling", "ancestor", "filesystem-root", "bare-repo-parent"],
    )
    def test_a_hijacked_commondir_cannot_move_the_root(
        self, tmp_path, monkeypatch, shape
    ):
        """Review finding (PR #141), ARM direction, all four hop shapes.

        A linked worktree's ``.git`` is a plain writable FILE inside the
        project, and the ``commondir`` it names is read to derive the
        containment ROOT. Unvalidated, an attacker with the write access
        AC-2 already assumes (they can plant a FIFO at the event path)
        re-opens AC-1 by pointing the hop wherever they like.

        ``ancestor`` and ``filesystem-root`` are the shapes a first review
        fix MISSED: it asserted only that the hop contains the work tree,
        which every ancestor does — ``commondir`` of ``/x`` yielded a root
        of ``/`` and made containment vacuous. ``bare-repo-parent`` is the
        same widening reached through a legitimate git layout.
        Parametrized rather than duplicated so the sideways-only version
        of this test cannot come back.
        """
        repo, wt = _make_repo_with_worktree(tmp_path)
        monkeypatch.chdir(wt)
        assert kt._containment_root() == repo.resolve(), "fixture self-check"

        victim = tmp_path / "victim-home"
        (victim / ".ssh").mkdir(parents=True)
        (victim / ".ssh" / "id_ed25519").write_text("KEY", encoding="utf-8")
        before = sorted(str(p.relative_to(victim)) for p in victim.rglob("*"))

        fake_gitdir = tmp_path / "fake-gitdir"
        fake_gitdir.mkdir()
        commondir = {
            # a directory beside the repo
            "sibling": f"{victim}/.git",
            # tmp_path CONTAINS the work tree — every ancestor passes an
            # is_relative_to check, which is why that check is not enough
            "ancestor": f"{tmp_path}/.git",
            "filesystem-root": "/x",
            # `git clone --bare` + `git worktree add`: commondir names
            # <dir>/proj.git, so `.parent` is the directory holding every
            # sibling project
            "bare-repo-parent": f"{tmp_path}/proj.git",
        }[shape]
        (fake_gitdir / "commondir").write_text(commondir + "\n", encoding="utf-8")
        (wt / ".git").write_text(f"gitdir: {fake_gitdir}\n", encoding="utf-8")

        root = kt._containment_root()
        assert root == wt.resolve(), (
            f"{shape}: a rejected hop must fall back to this work tree, the "
            f"conservative boundary; got {root}"
        )
        assert root != Path("/"), f"{shape}: containment became vacuous"
        assert not victim.resolve().is_relative_to(root), (
            f"{shape}: the victim tree fell inside the derived root {root}"
        )
        assert kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=victim / ".ssh"
        ) is False
        after = sorted(str(p.relative_to(victim)) for p in victim.rglob("*"))
        assert after == before == [".ssh", ".ssh/id_ed25519"], f"{shape}: {after}"

    def test_malformed_git_file_bytes_fall_back_instead_of_escaping(
        self, tmp_path, monkeypatch, capsys
    ):
        """Review finding (PR #141): the same untrusted-on-read lesson. A
        non-UTF-8 byte or an embedded NUL in planted workspace state must
        fail CLOSED to the work tree, not raise out of ``_main_repo_root``
        and turn every emit in the tree into ``emit failed``."""
        repo, wt = _make_repo_with_worktree(tmp_path)
        monkeypatch.chdir(wt)
        fake_gitdir = tmp_path / "fake-gitdir"
        fake_gitdir.mkdir()
        # (1) non-UTF-8 in commondir -> UnicodeDecodeError without errors=
        (fake_gitdir / "commondir").write_bytes(b"\xff\xfe not utf-8\n")
        (wt / ".git").write_text(f"gitdir: {fake_gitdir}\n", encoding="utf-8")
        assert kt._containment_root() == wt.resolve()

        # (2) NUL inside the commondir CONTENT -> Path.resolve() raises
        # ValueError, which is NOT an OSError. This is the case that pins
        # the widened catch: `Path.is_file()` swallows a NUL in the gitdir
        # path itself, so only this one reaches `resolve()`.
        (fake_gitdir / "commondir").write_bytes(b"/tmp/a\x00b\n")
        assert kt._containment_root() == wt.resolve()

        # (3) NUL in the gitdir line itself
        (wt / ".git").write_bytes(b"gitdir: /tmp/ev\x00il\n")
        assert kt._containment_root() == wt.resolve()

        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        assert kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=wt
        ) is True, "a corrupt .git byte must not disable telemetry wholesale"
        assert capsys.readouterr().out == ""

    def test_a_planted_git_file_in_a_subdir_cannot_move_the_root(
        self, tmp_path, monkeypatch
    ):
        """Same finding, the variant that needs no overwrite: a NEW
        directory inside the project carrying a crafted ``.git`` file."""
        repo, _wt = _make_repo_with_worktree(tmp_path)
        victim = tmp_path / "victim2"
        victim.mkdir()
        fake_gitdir = tmp_path / "fake-gitdir-2"
        fake_gitdir.mkdir()
        (fake_gitdir / "commondir").write_text(f"{victim}/.git\n", encoding="utf-8")
        planted = repo / "planted"
        planted.mkdir()
        (planted / ".git").write_text(f"gitdir: {fake_gitdir}\n", encoding="utf-8")

        monkeypatch.chdir(planted)
        root = kt._containment_root()
        assert root == planted.resolve(), root
        assert root.is_relative_to(repo.resolve()), (
            f"the derived root escaped the project: {root}"
        )
        assert kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=victim
        ) is False
        assert list(victim.iterdir()) == []

    def test_a_genuine_commondir_hop_is_still_followed(self, tmp_path, monkeypatch):
        """DISARM direction for the fix above (lesson 16): the validation
        must not break the real linked-worktree hop ISSUE-075 depends on —
        a guard that rejected every hop would pass both tests above."""
        repo, wt = _make_repo_with_worktree(tmp_path)
        assert (wt / ".git").is_file(), "fixture self-check: real worktree shape"
        monkeypatch.chdir(wt)
        assert kt._containment_root() == repo.resolve()
        assert kt._containment_root() != wt.resolve(), (
            "the hop was rejected — the main root must still win for a real "
            "linked worktree, or a main-root-targeted emit breaks"
        )
        assert kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=repo
        ) is True

    def test_git_work_tree_wins_over_the_env_knob(self, tmp_path, monkeypatch):
        """Order matters for the kit's own sprint flow: from inside a
        worktree the git answer is the MAIN root, which admits both the
        worktree and the main root. An env knob pointing at the worktree
        would refuse a main-root-targeted emit, so git goes first."""
        repo, wt = _make_repo_with_worktree(tmp_path)
        monkeypatch.chdir(wt)
        monkeypatch.setenv(kt.PROJECT_DIR_ENV, str(wt))
        assert kt._containment_root() == repo.resolve()


class TestProjectPathContainment:
    """AC-1 — the containment check is falsifiable, in BOTH directions."""

    def test_existing_writable_dirs_outside_the_root_are_refused(
        self, kit_root, monkeypatch, capsys
    ):
        """Arm direction, reproducing the ISSUE-067 review's demonstration
        (``~`` and ``~/.ssh``) against a tmp fixture — never the real home.

        The old check compared two values both derived from this very
        argument, so it could not fail for a non-symlinked root: these two
        emits both SUCCEEDED before ISSUE-070.
        """
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        home = kit_root.parent / "victim-home"
        (home / ".ssh").mkdir(parents=True)
        (home / ".ssh" / "id_ed25519").write_text("KEY", encoding="utf-8")
        before = sorted(str(p.relative_to(home)) for p in home.rglob("*"))

        for target in (home, home / ".ssh"):
            assert (
                kt.emit_event(
                    "test_event", {}, script_name="kit_test", project_path=target
                )
                is False
            )

        after = sorted(str(p.relative_to(home)) for p in home.rglob("*"))
        assert after == before == [".ssh", ".ssh/id_ed25519"], (
            f"nothing may be created under a refused root; got {after}"
        )
        assert (home / ".ssh" / "id_ed25519").read_text(encoding="utf-8") == "KEY"
        out = capsys.readouterr().out
        assert len(out.splitlines()) == 2, out
        assert out.count("containment violation") == 2
        assert out.count("outside the kit project root") == 2
        assert out.count("NOT written") == 2

    def test_the_same_call_against_the_real_root_succeeds(
        self, kit_root, project, monkeypatch, capsys
    ):
        """Disarm direction. Same arguments, same helper, a project path
        INSIDE the derived root — the event is appended and stdout is
        exactly empty. Without this pin, a guard that refused everything
        would pass the arm direction above."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=project
            )
            is True
        )
        assert kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=kit_root
        ) is True
        assert len(_events(project, "testrun")) == 1
        assert len(_events(kit_root, "testrun")) == 1
        assert capsys.readouterr().out == ""

    def test_symlink_into_an_outside_dir_is_refused_after_resolution(
        self, kit_root, monkeypatch, capsys
    ):
        """A project path that LOOKS contained but resolves out: the check
        compares the RESOLVED target, so the symlink does not launder it."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        outside = kit_root.parent / "outside-proj"
        outside.mkdir()
        bridge = kit_root / "bridge"
        bridge.symlink_to(outside)
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=bridge
            )
            is False
        )
        assert list(outside.iterdir()) == []
        assert "containment violation" in capsys.readouterr().out

    def test_refused_through_the_cli_the_attacker_influenced_surface(
        self, kit_root
    ):
        """``--project-path`` is the model-chosen surface the finding names."""
        home = kit_root.parent / "victim-home"
        home.mkdir()
        result = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--project-path", str(home),
            ],
            _cli_env("clirun", kit_root),
            cwd=kit_root,
        )
        assert result.returncode == 0, result.stderr
        assert "containment violation" in result.stdout
        assert "outside the kit project root" in result.stdout
        assert list(home.iterdir()) == []

    def test_existence_probe_runs_after_containment_not_before(
        self, kit_root, monkeypatch, capsys
    ):
        """Forgeable-attestation lesson, point 6: a pre-containment
        ``exists()`` probe whose refusal reason diverges is a filesystem
        existence oracle. Outside-root paths must be indistinguishable
        whether or not they exist."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        existing = kit_root.parent / "outside-real"
        existing.mkdir()
        missing = kit_root.parent / "outside-ghost"

        reasons = []
        for target in (existing, missing):
            assert (
                kt.emit_event(
                    "test_event", {}, script_name="kit_test", project_path=target
                )
                is False
            )
            line = capsys.readouterr().out.strip()
            reasons.append(line.replace(str(target), "<PATH>"))

        assert reasons[0] == reasons[1], (
            "the refusal reason leaks whether an out-of-root path exists: "
            f"{reasons!r}"
        )
        assert not missing.exists(), "a refused probe must not create anything"

    def test_announcement_cannot_be_forged_by_a_newline_in_the_path(
        self, kit_root, monkeypatch, capsys
    ):
        """Announcements are a single stdout line by contract, and this
        refusal is a NEW place where attacker-supplied text is printed — so
        a newline in ``--project-path`` must not manufacture a second
        ``[kit-telemetry]`` line that reads like an all-clear."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        evil = kit_root.parent / "x\n[kit-telemetry] fallback: all clear"
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=evil
            )
            is False
        )
        out = capsys.readouterr().out
        # One LINE, not one occurrence: the attacker's own text may contain
        # the prefix, but it must stay inside the single real line, escaped.
        assert len(out.splitlines()) == 1, out
        assert out.startswith("[kit-telemetry] skipped: containment violation")
        assert "\\n[kit-telemetry] fallback: all clear" in out, (
            "the embedded newline must be escaped, not emitted raw"
        )

    def test_worktree_rooted_callers_are_admitted_end_to_end(self, tmp_path):
        """ISSUE-075 pre-flight, executed: review runs from a worktree and
        passes ``project_path`` explicitly. All four real shapes must still
        write, and only a genuinely outside path may be refused."""
        repo, wt = _make_repo_with_worktree(tmp_path)
        env = _cli_env("wtrun")  # no CLAUDE_PROJECT_DIR — git must carry it
        shapes = [
            (wt, []),                             # skill one-liner: defaults to CWD
            (wt, ["--project-path", str(wt)]),    # ISSUE-075's own shape
            (repo, ["--project-path", str(wt)]),  # orchestrator on the main root
            (wt, ["--project-path", str(repo)]),  # and the reverse direction
        ]
        for cwd, extra in shapes:
            result = _run_cli(
                ["--script", "review", "--event", "review_degraded_path_used", *extra],
                env,
                cwd=cwd,
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout == "", (cwd, extra, result.stdout)
        assert len(_events(wt, "wtrun")) == 3
        assert len(_events(repo, "wtrun")) == 1

        outside = tmp_path / "elsewhere"
        outside.mkdir()
        refused = _run_cli(
            [
                "--script", "review",
                "--event", "review_degraded_path_used",
                "--project-path", str(outside),
            ],
            env,
            cwd=wt,
        )
        assert refused.returncode == 0, refused.stderr
        assert "containment violation" in refused.stdout
        assert list(outside.iterdir()) == []


class TestAnnouncementIntegrityEveryPath:
    """Review finding (PR #141): ``_quote`` shipped applied to the PATH
    only, so ``--event`` still forged a second ``[kit-telemetry]`` line on
    three other announcement paths. Lesson 16 — a new defence must be
    exercised through its REAL consumer (the CLI) at EVERY site, not only
    in the arm direction at the one site its author had in mind.

    Measured before the fix: 2 lines on all three shapes below.
    """

    EVIL = "benign_event\n[kit-telemetry] fallback: all clear"

    @pytest.mark.parametrize(
        "label,extra,run_id",
        [
            ("4096-byte cap", ["--payload", '{"f": "' + "y" * 5000 + '"}'], "capr"),
            ("KIT_RUN_ID fallback", [], None),
            ("invalid --payload", ["--payload", "{not json"], "badp"),
        ],
    )
    def test_event_type_cannot_forge_a_second_line(
        self, kit_root, project, label, extra, run_id
    ):
        result = _run_cli(
            ["--script", "review", "--event", self.EVIL,
             "--project-path", str(project), *extra],
            _cli_env(run_id, kit_root),
            cwd=kit_root,
        )
        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert len(lines) == 1, f"{label}: forged extra line(s): {result.stdout!r}"
        assert lines[0].startswith("[kit-telemetry]"), label
        assert "\\n[kit-telemetry] fallback: all clear" in result.stdout, (
            f"{label}: the embedded newline must be escaped, not emitted raw"
        )

    def test_an_ordinary_event_type_still_reads_cleanly(self, kit_root, project):
        """DISARM direction: escaping must not mangle the normal case —
        the event name stays greppable in the announcement."""
        result = _run_cli(
            ["--script", "review", "--event", "review_degraded_path_used",
             "--project-path", str(project)],
            _cli_env(None, kit_root),
            cwd=kit_root,
        )
        assert result.returncode == 0, result.stderr
        assert len(result.stdout.splitlines()) == 1, result.stdout
        assert "review_degraded_path_used" in result.stdout
        assert "KIT_RUN_ID" in result.stdout
        assert "unattributed" in result.stdout
        assert len(_events(project, "unattributed")) == 1


class TestPlantedNodeFamily:
    """AC-2 — nothing planted at the predictable event path may hang the
    emitter or receive a write."""

    @staticmethod
    def _runs(project: Path) -> Path:
        runs = project / ".claude" / "runs"
        runs.mkdir(parents=True)
        return runs

    def test_fifo_at_the_event_path_refused_without_hanging(
        self, kit_root, project
    ):
        """The load-bearing one. Without ``O_NONBLOCK`` on the open this
        subprocess never returns, and a hang is NOT caught by
        ``verify_checkpoint.py``'s exception wrapper — it stalls the gate.
        So the probe is bounded and a timeout is classified as rc 124, a
        DISTINCT outcome from any assertion failure below it.
        """
        target = self._runs(project) / "testrun.jsonl"
        os.mkfifo(target)
        rc, out, err = _run_cli_bounded(
            [
                "--script", "kit_test",
                "--event", "test_event",
                "--project-path", str(project),
            ],
            _cli_env("testrun", kit_root),
            kit_root,
        )
        assert rc != TIMEOUT_RC, (
            f"HANG: the emitter did not return within {_probe_timeout()}s with a "
            f"FIFO planted at {target} — the non-blocking open guard is missing. "
            f"Raise {PROBE_TIMEOUT_ENV} only if this machine is merely slow."
        )
        assert rc == 0, err
        assert "[kit-telemetry]" in out
        assert "NOT written" in out
        assert stat.S_ISFIFO(os.lstat(target).st_mode), "the FIFO was replaced"
        assert [p.name for p in target.parent.iterdir()] == ["testrun.jsonl"]

    def test_fifo_with_a_reader_attached_is_refused_by_the_file_type_guard(
        self, project, monkeypatch, capsys
    ):
        """Disarm the OTHER leg: with a reader attached the non-blocking open
        SUCCEEDS, so only the post-open file-type check stops the write.
        Nothing may reach the pipe."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        target = self._runs(project) / "testrun.jsonl"
        os.mkfifo(target)
        reader = os.open(target, os.O_RDONLY | os.O_NONBLOCK)
        try:
            assert (
                kt.emit_event(
                    "test_event", {}, script_name="kit_test", project_path=project
                )
                is False
            )
            assert os.read(reader, 4096) == b"", "data was pushed into the FIFO"
        finally:
            os.close(reader)
        out = capsys.readouterr().out
        assert "non-regular" in out
        assert "NOT written" in out

    def test_directory_at_the_event_path_refused(
        self, project, monkeypatch, capsys
    ):
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        target = self._runs(project) / "testrun.jsonl"
        target.mkdir()
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=project
            )
            is False
        )
        assert list(target.iterdir()) == []
        assert "NOT written" in capsys.readouterr().out

    def test_unix_socket_at_the_event_path_refused(
        self, project, monkeypatch, capsys
    ):
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        runs = self._runs(project)
        # AF_UNIX paths are capped near 104 bytes; bind relatively from
        # inside the runs dir so a long tmp_path cannot make this a skip.
        monkeypatch.chdir(runs)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind("testrun.jsonl")
            assert stat.S_ISSOCK(os.lstat(runs / "testrun.jsonl").st_mode)
            assert (
                kt.emit_event(
                    "test_event", {}, script_name="kit_test", project_path=project
                )
                is False
            )
            assert stat.S_ISSOCK(os.lstat(runs / "testrun.jsonl").st_mode)
        finally:
            sock.close()
        assert "NOT written" in capsys.readouterr().out

    def test_character_device_at_the_event_path_refused(
        self, project, monkeypatch, capsys
    ):
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        target = self._runs(project) / "testrun.jsonl"
        try:
            os.mknod(str(target), stat.S_IFCHR | 0o600, os.makedev(1, 3))
        except (PermissionError, OSError) as exc:
            pytest.skip(f"mknod of a character device is not permitted here: {exc}")
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=project
            )
            is False
        )
        assert stat.S_ISCHR(os.lstat(target).st_mode)
        assert "NOT written" in capsys.readouterr().out

    def test_multiply_linked_regular_file_refused(
        self, project, monkeypatch, capsys
    ):
        """A hardlink passes ``O_NOFOLLOW`` and the regular-file check — only
        the link count catches it. Appending here would write through to a
        file the attacker also owns a name for, outside ``.claude/runs``."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        victim = project / "victim.txt"
        victim.write_text("original", encoding="utf-8")
        target = self._runs(project) / "testrun.jsonl"
        os.link(victim, target)
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=project
            )
            is False
        )
        assert victim.read_text(encoding="utf-8") == "original"
        out = capsys.readouterr().out
        assert "multiply-linked" in out
        assert "NOT written" in out

    def test_single_linked_regular_file_still_appends(
        self, project, monkeypatch, capsys
    ):
        """Disarm direction for the link-count guard: an ordinary
        pre-existing event file (nlink 1) must still be appended to."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        target = self._runs(project) / "testrun.jsonl"
        target.write_text("", encoding="utf-8")
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=project
            )
            is True
        )
        assert len(_events(project, "testrun")) == 1
        assert capsys.readouterr().out == ""


class TestToctou:
    """AC — the window between the containment check and the open."""

    def test_node_planted_after_the_containment_check_is_refused_at_the_open(
        self, project, monkeypatch, capsys
    ):
        """``datetime.now()`` is called AFTER containment and the runs-dir
        mkdir and BEFORE ``os.open``, so planting there lands the node
        squarely inside the real check->open window. What saves the emitter
        is the open-time guard, not the (already passed) containment check.

        The planted FIFO is opened for reading by the test FIRST so that the
        emitter's own ``os.open`` cannot block on it. That is deliberate and
        load-bearing: this test runs IN-PROCESS, so a readerless FIFO here
        would hang the whole suite forever the moment the ``O_NONBLOCK``
        guard regressed, instead of failing it. The hang direction belongs
        to the bounded subprocess probe
        (``test_fifo_at_the_event_path_refused_without_hanging``); what this
        test owns is the TOCTOU-proof leg — the post-open ``fstat``, the
        only check that interrogates the descriptor actually opened.
        (Measured: with a readerless FIFO and the guard removed, the
        mutation run stalled past 600 s until it was killed.)
        """
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        runs = project / ".claude" / "runs"
        runs.mkdir(parents=True)
        target = runs / "testrun.jsonl"
        real_datetime = kt.datetime
        readers: list[int] = []

        class _PlantInsideTheWindow:
            @staticmethod
            def now(tz=None):
                if not readers:
                    os.mkfifo(target)
                    readers.append(os.open(target, os.O_RDONLY | os.O_NONBLOCK))
                return real_datetime.now(tz)

        monkeypatch.setattr(kt, "datetime", _PlantInsideTheWindow)
        try:
            ok = kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=project
            )
            assert readers, "the TOCTOU plant never ran — the window moved"
            assert ok is False
            assert stat.S_ISFIFO(os.lstat(target).st_mode)
            assert os.read(readers[0], 4096) == b"", "data reached the planted node"
        finally:
            for fd in readers:
                os.close(fd)
        out = capsys.readouterr().out
        assert "[kit-telemetry]" in out
        assert "non-regular" in out
        assert "NOT written" in out


class TestNeverRaisesContract:
    """AC-3 — the CHOSEN contract is the docstring's "NEVER raises": the
    catch set was widened rather than the docstring narrowed, so no call
    site needs a handler. Only one of the two options is asserted."""

    def test_docstring_still_advertises_the_no_raise_guarantee(self):
        """Pins the decision itself: if a future change narrows the
        docstring instead, this test must be rewritten deliberately rather
        than left agreeing with both options."""
        assert "NEVER raises" in kt.__doc__

    def test_closed_stdout_does_not_raise_and_still_writes(
        self, project, monkeypatch
    ):
        """The reproduced defect: the fallback path announces, ``print`` on a
        closed stream raises ``ValueError``, and the outer handler announced
        again — so the exception escaped the "never raises" wrapper."""
        sink = io.StringIO()
        sink.close()
        monkeypatch.setattr(sys, "stdout", sink)
        ok = kt.emit_event(
            "test_event", {}, script_name="kit_test", project_path=project
        )
        assert ok is True, "the event must still land; only the announcement is lost"
        [event] = _events(project, "unattributed")
        assert event["run_id_fallback"] == "KIT_RUN_ID unset"

    def test_closed_stdout_on_a_refusal_path_does_not_raise(
        self, kit_root, monkeypatch
    ):
        """The refusal paths announce too, and they are the ones a gate hits
        under attack — so they are pinned separately from the fallback."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")
        outside = kit_root.parent / "outside"
        outside.mkdir()
        sink = io.StringIO()
        sink.close()
        monkeypatch.setattr(sys, "stdout", sink)
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=outside
            )
            is False
        )

    def test_closed_stdout_in_a_real_process_exits_clean(self, kit_root, project):
        """Through a real ``sys.stdout.close()`` rather than a stand-in —
        the exact repro recorded in the ISSUE-067 review."""
        script = textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(SCRIPTS_DIR)!r})
            import kit_telemetry as kt
            sys.stdout.close()
            ok = kt.emit_event(
                "test_event", {{}}, script_name="kit_test",
                project_path={str(project)!r},
            )
            sys.stderr.write("RESULT=%r\\n" % (ok,))
            """
        )
        done = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=_cli_env(project_dir=kit_root),  # KIT_RUN_ID unset -> announce path
            cwd=str(kit_root),
            timeout=_probe_timeout(),
        )
        assert done.returncode == 0, done.stderr
        assert "Traceback" not in done.stderr, done.stderr
        assert "RESULT=True" in done.stderr
        assert len(_events(project, "unattributed")) == 1

    def test_recursion_error_from_the_announcer_is_still_contained(
        self, kit_root, monkeypatch, capsys
    ):
        """``RecursionError`` is not a ``ValueError``: a catch set narrowed
        to ``ValueError`` would pass the closed-stdout tests above and still
        break the contract."""
        monkeypatch.setenv(kt.RUN_ID_ENV, "testrun")

        def _boom(*_a, **_k):
            raise RecursionError("maximum recursion depth exceeded")

        monkeypatch.setattr("builtins.print", _boom)
        outside = kit_root.parent / "outside"
        outside.mkdir()
        assert (
            kt.emit_event(
                "test_event", {}, script_name="kit_test", project_path=outside
            )
            is False
        )
        assert list(outside.iterdir()) == []


class TestEnvKnobDocumentation:
    """Recurring ISSUE-046/047/049/052/069/083 lesson: a new env knob is
    documented in the owning module AND in the user-facing doc, in the same
    PR that adds it."""

    def test_claude_project_dir_is_documented_in_both_places(self):
        assert kt.PROJECT_DIR_ENV == "CLAUDE_PROJECT_DIR"
        assert kt.PROJECT_DIR_ENV in kt.__doc__
        readme = (SCRIPTS_DIR.parent / "README.md").read_text(encoding="utf-8")
        assert kt.PROJECT_DIR_ENV in readme
