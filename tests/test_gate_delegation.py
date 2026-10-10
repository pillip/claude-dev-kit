"""Unit tests for scripts/synthesize_gate_results.py (ISSUE-058 / SPEC-058).

Covers the dormant test-execution delegation layer:
- the deterministic synthesis mapper (runtime-shaped JSON -> verify_gates.GateResult),
- the probe/handoff decision table (skill_missing / capability_dormant /
  invalid_results / delegated),
- untrusted-results hardening (the KIT_GATE_RESULTS_FILE artifact is untrusted
  input: every violation degrades toward running the real gates),
- schema-conformant best-effort telemetry through the shared emitter
  (ISSUE-067: unconfigured KIT_RUN_ID falls back to the announced
  ``unattributed`` run id instead of a silent no-op),
- the verify_checkpoint._run_verify_gates wiring seam (degraded path is
  byte-identical to the legacy verify_gates path; delegated path never calls
  verify_gates; a crashing delegation layer still falls back).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the modules under test from THIS checkout's scripts dir (pinned to the
# fixture root so a fallback resolution cannot hollow-pass against another repo).
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kit_telemetry as kt  # noqa: E402
import synthesize_gate_results as sgr  # noqa: E402
import verify_gates as vg  # noqa: E402
import verify_checkpoint as vc  # noqa: E402


# ── fixtures / helpers ───────────────────────────────────────────────


def _valid_payload() -> list[dict]:
    """A runtime-shaped results payload covering all four statuses."""
    return [
        {"gate": "unit", "status": "pass", "blocking": True,
         "output": "ok", "duration_s": 1.25},
        {"gate": "integration", "status": "skip", "blocking": True,
         "output": "No integration tests found", "duration_s": 0.0},
        {"gate": "e2e-web", "status": "fail", "blocking": False,
         "output": "line1\nline2", "duration_s": 12.5},
        {"gate": "load", "status": "warn", "blocking": False,
         "output": "", "duration_s": 3.0},
    ]


def _write_results(project: Path, payload, name: str = "gate_results.json") -> Path:
    run_dir = project / ".claude" / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / name
    data = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(data, encoding="utf-8")
    return path


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """An isolated fake project root."""
    p = tmp_path / "proj"
    p.mkdir()
    return p


# Ambient-env isolation for KIT_GATE_RESULTS_FILE / KIT_RUN_ID lives in
# tests/conftest.py (autouse, suite-wide) — every test that reaches
# _run_verify_gates traverses the delegation consult, not just this file.


def _probe(monkeypatch, code: int, evidence: str = "stub"):
    """Mock the probe at the delegation seam (has_skill.find_skill)."""
    mock = MagicMock(return_value=(code, evidence))
    monkeypatch.setattr(sgr.has_skill, "find_skill", mock)
    return mock


# ISSUE-065 bound-API helpers: decide_gate_path now REQUIRES keyword-only
# binding materials (binding_key / process_start). These helpers migrate the
# pre-binding call sites without weakening any assertion: positive fixtures
# get a valid HMAC sidecar + a process_start in the past (fresh by
# construction); every expected (decision, results, reason) stays as-is.

BINDING_KEY = b"\x42" * 32


def _sign(path: Path, key: bytes = BINDING_KEY) -> Path:
    """Write the provenance sidecar for ``path`` under ``key``."""
    sig = Path(str(path) + ".sig")
    digest = hmac.new(key, path.read_bytes(), hashlib.sha256).hexdigest()
    sig.write_text(digest, encoding="utf-8")
    return sig


def _decide(project: Path, *, key: bytes = BINDING_KEY,
            process_start: float | None = None):
    """Call decide_gate_path through the bound API (fresh by default)."""
    if process_start is None:
        process_start = time.time() - 3600.0
    return sgr.decide_gate_path(project, binding_key=key,
                                process_start=process_start)


# ── synthesis mapper: schema fidelity ────────────────────────────────


class TestSynthesizeMapper:
    def test_happy_path_maps_all_four_statuses(self):
        results = sgr.synthesize_gate_results(_valid_payload())
        assert [r.status for r in results] == ["pass", "skip", "fail", "warn"]
        assert [r.gate for r in results] == ["unit", "integration", "e2e-web", "load"]

    def test_returns_real_gateresult_instances(self):
        results = sgr.synthesize_gate_results(_valid_payload())
        assert all(isinstance(r, vg.GateResult) for r in results)

    def test_exact_schema_round_trip(self):
        results = sgr.synthesize_gate_results(_valid_payload())
        assert [asdict(r) for r in results] == _valid_payload()

    def test_blocking_flag_preserved_both_ways(self):
        results = sgr.synthesize_gate_results(_valid_payload())
        assert [r.blocking for r in results] == [True, True, False, False]

    def test_optional_fields_default(self):
        results = sgr.synthesize_gate_results(
            [{"gate": "unit", "status": "pass", "blocking": True}]
        )
        assert results[0].output == ""
        assert results[0].duration_s == 0.0

    def test_output_newline_and_tab_allowed(self):
        # \n and \t are legitimate in test-runner tails; only other control
        # characters are rejected.
        results = sgr.synthesize_gate_results(
            [{"gate": "unit", "status": "fail", "blocking": True,
              "output": "FAILED a.py::t\n\tassert 1 == 2"}]
        )
        assert results[0].output == "FAILED a.py::t\n\tassert 1 == 2"

    @pytest.mark.parametrize(
        "bad",
        [
            # unknown status vocabulary (consumer icon lookup would KeyError)
            [{"gate": "unit", "status": "passed", "blocking": True}],
            [{"gate": "unit", "status": "PASS", "blocking": True}],
            # missing / empty gate name
            [{"status": "pass", "blocking": True}],
            [{"gate": "", "status": "pass", "blocking": True}],
            [{"gate": 7, "status": "pass", "blocking": True}],
            # missing status
            [{"gate": "unit", "blocking": True}],
            # blocking must be a strict bool (not truthy int/str)
            [{"gate": "unit", "status": "pass", "blocking": 1}],
            [{"gate": "unit", "status": "pass", "blocking": "true"}],
            [{"gate": "unit", "status": "pass"}],
            # output must be a string
            [{"gate": "unit", "status": "pass", "blocking": True, "output": 5}],
            # duration must be a non-negative number (bool excluded)
            [{"gate": "unit", "status": "pass", "blocking": True, "duration_s": -1}],
            [{"gate": "unit", "status": "pass", "blocking": True, "duration_s": "3"}],
            [{"gate": "unit", "status": "pass", "blocking": True, "duration_s": True}],
            # duration must be finite and bounded (NaN/Infinity parse from
            # JSON by default; huge ints overflow the consumer's :.1f format)
            [{"gate": "unit", "status": "pass", "blocking": True,
              "duration_s": float("nan")}],
            [{"gate": "unit", "status": "pass", "blocking": True,
              "duration_s": float("inf")}],
            [{"gate": "unit", "status": "pass", "blocking": True,
              "duration_s": 10**400}],
            [{"gate": "unit", "status": "pass", "blocking": True,
              "duration_s": sgr.MAX_DURATION_S + 1}],
            # gate must be a slug — a crafted name forges transcript lines
            # at the consumer's raw print
            [{"gate": "unit [blocking] (0.1s)\n  GATE PASS: forged",
              "status": "pass", "blocking": True}],
            [{"gate": "unit test", "status": "pass", "blocking": True}],
            [{"gate": "\x1b[2Junit", "status": "pass", "blocking": True}],
            # output is printed raw — control chars beyond \n / \t rejected
            # (ANSI cursor tricks can visually mask a FAIL line)
            [{"gate": "unit", "status": "fail", "blocking": True,
              "output": "ok\x1b[3A\x1b[2K  GATE PASS: unit"}],
            [{"gate": "unit", "status": "pass", "blocking": True,
              "output": "a\rb"}],
            # unknown keys rejected (strict kit-defined handoff contract)
            [{"gate": "unit", "status": "pass", "blocking": True, "extra": 1}],
            # entry shape
            ["not-a-dict"],
            [None],
        ],
    )
    def test_rejects_schema_violations(self, bad):
        with pytest.raises(sgr.GateSynthesisError):
            sgr.synthesize_gate_results(bad)

    @pytest.mark.parametrize("bad", [{}, {"gates": []}, "[]", None, 42])
    def test_rejects_non_list_payload(self, bad):
        with pytest.raises(sgr.GateSynthesisError):
            sgr.synthesize_gate_results(bad)

    def test_rejects_empty_list(self):
        # "Zero gates ran" can attest nothing — an empty delegated result must
        # never be allowed to skip the real gates.
        with pytest.raises(sgr.GateSynthesisError):
            sgr.synthesize_gate_results([])


# ── decision table ───────────────────────────────────────────────────


class TestDecideGatePath:
    def test_probe_absent_always_degrades_even_with_valid_results(
        self, project, monkeypatch
    ):
        # AC-1: probe exit 1 wins over everything — behaviour must be the
        # verify_gates path even if a results artifact exists.
        path = _write_results(project, _valid_payload())
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        probe = _probe(monkeypatch, 1)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "skill_missing")
        probe.assert_called_once_with(sgr.RUNTIME_TEST_SKILL)

    def test_dormant_when_env_unset(self, project, monkeypatch):
        _probe(monkeypatch, 2)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "capability_dormant")

    def test_dormant_when_env_empty_string(self, project, monkeypatch):
        _probe(monkeypatch, 2)
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, "")
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "capability_dormant")

    @pytest.mark.parametrize("probe_code", [0, 2])
    def test_delegated_with_valid_results(self, project, monkeypatch, probe_code):
        path = _write_results(project, _valid_payload())
        _sign(path)
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        _probe(monkeypatch, probe_code)
        decision, results, reason = _decide(project)
        assert decision == "delegated"
        assert reason == ""
        assert [asdict(r) for r in results] == _valid_payload()

    def test_nonexistent_project_path_is_safe(self, monkeypatch):
        _probe(monkeypatch, 2)
        decision, results, reason = _decide(Path("/nonexistent-kit-issue-058"))
        assert decision == "degraded"
        assert results is None


class TestUntrustedResultsFile:
    """The results artifact is untrusted input — every violation degrades."""

    def _decide(self, project, monkeypatch, env_value: str):
        _probe(monkeypatch, 2)
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, env_value)
        return _decide(project)  # module-level bound-API helper

    def test_nonexistent_file(self, project, monkeypatch):
        decision, results, reason = self._decide(
            project, monkeypatch, str(project / "nope.json")
        )
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_path_outside_project_root(self, project, tmp_path, monkeypatch):
        outside = tmp_path / "outside"
        outside.mkdir()
        path = outside / "gate_results.json"
        path.write_text(json.dumps(_valid_payload()), encoding="utf-8")
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_option_shaped_path_rejected(self, project, monkeypatch):
        decision, results, reason = self._decide(project, monkeypatch, "--pdb")
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_directory_instead_of_file(self, project, monkeypatch):
        d = project / ".claude" / "run"
        d.mkdir(parents=True)
        decision, results, reason = self._decide(project, monkeypatch, str(d))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    # The shape-violation fixtures below carry a VALID binding sidecar so
    # they keep exercising the invalid_results contract — binding precedes
    # parse, and the unsigned flavor is pinned as binding-rejected in
    # tests/test_gate_binding.py (ISSUE-065).

    def test_non_json_content(self, project, monkeypatch):
        path = _write_results(project, "not json at all {")
        _sign(path)
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_schema_violation_in_file(self, project, monkeypatch):
        path = _write_results(
            project, [{"gate": "unit", "status": "bogus", "blocking": True}]
        )
        _sign(path)
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_empty_array_in_file(self, project, monkeypatch):
        path = _write_results(project, [])
        _sign(path)
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_oversized_file(self, project, monkeypatch):
        path = _write_results(project, "x" * (sgr.MAX_RESULTS_BYTES + 1))
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_file_inside_project_but_outside_run_dir(self, project, monkeypatch):
        # Containment is <project>/.claude/run/ (gitignored), not merely
        # "inside the project" — a committed artifact elsewhere in the tree
        # must never activate delegation (security review, PR #100 finding 1).
        path = project / "gate_results.json"
        path.write_text(json.dumps(_valid_payload()), encoding="utf-8")
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_deeply_nested_json_degrades(self, project, monkeypatch):
        # RecursionError from json.loads maps into GateSynthesisError and
        # degrades — it must not escape the module's error contract.
        path = _write_results(project, "[" * 100_000 + "]" * 100_000)
        _sign(path)
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")


# ── telemetry ────────────────────────────────────────────────────────


class TestTelemetry:
    def _runs_dir(self, project: Path) -> Path:
        d = project / ".claude" / "runs"
        d.mkdir(parents=True)
        return d

    def _events(self, project: Path, run_id: str) -> list[dict]:
        path = project / ".claude" / "runs" / f"{run_id}.jsonl"
        assert path.is_file(), f"expected telemetry file at {path}"
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_degraded_event_emitted(self, project, monkeypatch):
        self._runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        _probe(monkeypatch, 1)
        _decide(project)
        events = self._events(project, "testrun")
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "gates_degraded_path_used"
        assert event["skill_or_script"] == "synthesize_gate_results"
        assert event["payload"]["reason"] == "skill_missing"
        assert "ts" in event

    def test_delegated_event_emitted(self, project, monkeypatch):
        self._runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        path = _write_results(project, _valid_payload())
        _sign(path)
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        _probe(monkeypatch, 2)
        _decide(project)
        events = self._events(project, "testrun")
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "gates_delegated_to_runtime"
        assert event["payload"]["skill"] == sgr.RUNTIME_TEST_SKILL
        assert event["payload"]["gate_count"] == len(_valid_payload())

    def test_invalid_results_payload_names_the_env_knob(self, project, monkeypatch):
        # Review lesson: the knob's name appears in the failure signal it
        # remediates.
        self._runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(project / "nope.json"))
        _probe(monkeypatch, 2)
        _decide(project)
        event = self._events(project, "testrun")[0]
        assert event["payload"]["reason"] == "invalid_results"
        assert sgr.GATE_RESULTS_ENV in json.dumps(event["payload"])

    def test_missing_runs_dir_auto_created_and_silent(
        self, project, monkeypatch, capsys
    ):
        # ISSUE-067: dir absence is no longer a silent-skip path — the shared
        # emitter auto-creates .claude/runs/ and writes, with NO announcement
        # on the clean (valid run id) path.
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        _probe(monkeypatch, 1)
        _decide(project)  # must not raise
        event = self._events(project, "testrun")[0]
        assert event["payload"]["reason"] == "skill_missing"
        assert capsys.readouterr().out == ""

    def test_missing_run_id_falls_back_to_unattributed(
        self, project, monkeypatch, capsys
    ):
        # ISSUE-067: KIT_RUN_ID unset is no longer a silent drop — the event
        # lands under the explicit 'unattributed' run id with the fallback
        # visible in the event body, and stdout announces the named knob.
        self._runs_dir(project)
        _probe(monkeypatch, 1)
        _decide(project)  # must not raise
        event = self._events(project, "unattributed")[0]
        assert event["payload"]["reason"] == "skill_missing"
        assert event["run_id_fallback"] == "KIT_RUN_ID unset"
        out = capsys.readouterr().out
        assert "[kit-telemetry]" in out
        assert "KIT_RUN_ID" in out

    def test_invalid_run_id_falls_back_to_unattributed(
        self, project, monkeypatch, capsys
    ):
        # The whitelist still rejects odd values as filenames — but the event
        # now survives under 'unattributed' instead of being dropped.
        runs = self._runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "bad id!")
        _probe(monkeypatch, 1)
        _decide(project)  # must not raise
        assert [p.name for p in runs.iterdir()] == ["unattributed.jsonl"]
        event = self._events(project, "unattributed")[0]
        assert "invalid" in event["run_id_fallback"]
        assert "KIT_RUN_ID" in capsys.readouterr().out

    def test_symlinked_event_file_not_followed(
        self, project, tmp_path, monkeypatch, capsys
    ):
        # A pre-planted symlink at the event path must not redirect the
        # append outside the project (O_NOFOLLOW) — and the refused write is
        # announced (ISSUE-067), no longer silent.
        runs = self._runs_dir(project)
        target = tmp_path / "outside-target"
        target.write_text("", encoding="utf-8")
        (runs / "testrun.jsonl").symlink_to(target)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        _probe(monkeypatch, 1)
        _decide(project)  # must not raise
        assert target.read_text(encoding="utf-8") == ""
        assert "write failed" in capsys.readouterr().out

    def test_symlinked_runs_dir_not_written(
        self, project, tmp_path, monkeypatch, capsys
    ):
        # .claude/runs symlinked outside the project → realpath containment
        # fails → nothing lands at the symlink target, and the rejection is
        # announced with its named reason (ISSUE-067), no longer silent.
        outside = tmp_path / "outside-runs"
        outside.mkdir()
        (project / ".claude").mkdir()
        (project / ".claude" / "runs").symlink_to(outside)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        _probe(monkeypatch, 1)
        _decide(project)  # must not raise
        assert list(outside.iterdir()) == []
        assert "containment" in capsys.readouterr().out

    def test_oversized_detail_truncated_not_dropped(self, project, monkeypatch):
        # Attacker-padded detail must not suppress the forensic event via
        # the 4 KiB cap — truncate the detail, keep the event.
        self._runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        sgr._emit_telemetry(
            project,
            "gates_degraded_path_used",
            {"reason": "invalid_results", "detail": "x" * 10_000},
        )
        event = self._events(project, "testrun")[0]
        assert event["payload"]["reason"] == "invalid_results"
        assert event["payload"]["detail"].endswith("…[truncated]")
        assert len(event["payload"]["detail"]) <= kt._MAX_DETAIL_CHARS + len(
            "…[truncated]"
        )


# ── verify_checkpoint wiring seam ────────────────────────────────────


def _fixture_results() -> list:
    # All four statuses flow through the real consumer's icon lookup so a
    # mapper/consumer status-vocabulary drift fails loudly as a KeyError
    # (lesson-4 oracle-mirror, mutation-tested in both directions).
    return [
        vg.GateResult(gate="unit", status="pass", blocking=True,
                      output="ok", duration_s=1.23),
        vg.GateResult(gate="integration", status="skip", blocking=False,
                      output="", duration_s=0.0),
        vg.GateResult(gate="e2e-web", status="fail", blocking=True,
                      output="line1\nline2", duration_s=0.0),
        vg.GateResult(gate="load", status="warn", blocking=False,
                      output="", duration_s=2.0),
    ]


EXPECTED_LEGACY_STDOUT = (
    "  GATE PASS: unit [blocking] (1.2s)\n"
    "  GATE SKIP: integration (0.0s)\n"
    "  GATE FAIL: e2e-web [blocking] (0.0s)\n"
    "        line1\n"
    "        line2\n"
    "  GATE WARN: load (2.0s)\n"
    "WARN: gate failures detected (non-blocking during implement phase)\n"
)

# A delegated run is never byte-indistinguishable from a real gate run —
# the wiring prints this marker before the legacy rendering (security
# review, PR #100 finding 2). The DEGRADED path stays byte-identical.
EXPECTED_DELEGATED_MARKER = (
    "  GATES DELEGATED: 4 synthesized gate result(s) ingested from "
    "KIT_GATE_RESULTS_FILE — tests were NOT executed by this checkpoint process\n"
)


class TestRunVerifyGatesWiring:
    def test_degraded_path_calls_verify_gates_seam_once(
        self, project, monkeypatch, capsys
    ):
        # Env unset -> dormant -> the real fallback seam must execute.
        with patch.object(
            vg, "run_applicable_gates", return_value=_fixture_results()
        ) as seam:
            assert vc._run_verify_gates(str(project), blocking=False) is True
        seam.assert_called_once()
        assert seam.call_args.args[0] == Path(str(project))

    def test_degraded_stdout_byte_identical_to_legacy(
        self, project, monkeypatch, capsys
    ):
        # AC-1: with the delegation layer dormant, stdout is byte-identical to
        # the pre-ISSUE-058 verify_gates path. A valid run id keeps the shared
        # emitter on its clean, silent path (ISSUE-067) so the pin keeps its
        # original meaning.
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        with patch.object(vg, "run_applicable_gates", return_value=_fixture_results()):
            vc._run_verify_gates(str(project), blocking=False)
        assert capsys.readouterr().out == EXPECTED_LEGACY_STDOUT

    def test_delegated_path_never_calls_verify_gates(self, project, monkeypatch):
        monkeypatch.setattr(
            sgr, "decide_gate_path",
            MagicMock(return_value=("delegated", _fixture_results(), "")),
        )
        with patch.object(vg, "run_applicable_gates") as seam:
            # AC-2: blocking fail inside synthesized results still blocks.
            assert vc._run_verify_gates(str(project), blocking=True) is False
        seam.assert_not_called()

    def test_delegated_results_flow_through_legacy_consumer(
        self, project, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            sgr, "decide_gate_path",
            MagicMock(return_value=("delegated", _fixture_results(), "")),
        )
        with patch.object(vg, "run_applicable_gates"):
            assert vc._run_verify_gates(str(project), blocking=False) is True
        # Same consumer, same schema, same rendering (AC-2: no consumer
        # change) — PLUS the unconditional delegation marker so a delegated
        # (possibly forged) run can never masquerade as a real gate run.
        assert capsys.readouterr().out == (
            EXPECTED_DELEGATED_MARKER + EXPECTED_LEGACY_STDOUT
        )

    def test_delegation_layer_crash_falls_back_to_verify_gates(
        self, project, monkeypatch
    ):
        monkeypatch.setattr(
            sgr, "decide_gate_path", MagicMock(side_effect=RuntimeError("boom"))
        )
        with patch.object(
            vg, "run_applicable_gates", return_value=_fixture_results()
        ) as seam:
            assert vc._run_verify_gates(str(project), blocking=False) is True
        seam.assert_called_once()
