"""Unit tests for scripts/synthesize_gate_results.py (ISSUE-058 / SPEC-058).

Covers the dormant test-execution delegation layer:
- the deterministic synthesis mapper (runtime-shaped JSON -> verify_gates.GateResult),
- the probe/handoff decision table (skill_missing / capability_dormant /
  invalid_results / delegated),
- untrusted-results hardening (the KIT_GATE_RESULTS_FILE artifact is untrusted
  input: every violation degrades toward running the real gates),
- schema-conformant best-effort telemetry (silent no-op when unconfigured),
- the verify_checkpoint._run_verify_gates wiring seam (degraded path is
  byte-identical to the legacy verify_gates path; delegated path never calls
  verify_gates; a crashing delegation layer still falls back).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the modules under test from THIS checkout's scripts dir (pinned to the
# fixture root so a fallback resolution cannot hollow-pass against another repo).
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

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
    if isinstance(payload, (bytes, str)):
        data = payload if isinstance(payload, str) else payload.decode("utf-8", "replace")
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """An isolated fake project root."""
    p = tmp_path / "proj"
    p.mkdir()
    return p


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """Keep ambient env from leaking into the decision table."""
    monkeypatch.delenv(sgr.GATE_RESULTS_ENV, raising=False)
    monkeypatch.delenv(sgr.RUN_ID_ENV, raising=False)


def _probe(monkeypatch, code: int, evidence: str = "stub"):
    """Mock the probe at the delegation seam (has_skill.find_skill)."""
    mock = MagicMock(return_value=(code, evidence))
    monkeypatch.setattr(sgr.has_skill, "find_skill", mock)
    return mock


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
        decision, results, reason = sgr.decide_gate_path(project)
        assert (decision, results, reason) == ("degraded", None, "skill_missing")
        probe.assert_called_once_with(sgr.RUNTIME_TEST_SKILL)

    def test_dormant_when_env_unset(self, project, monkeypatch):
        _probe(monkeypatch, 2)
        decision, results, reason = sgr.decide_gate_path(project)
        assert (decision, results, reason) == ("degraded", None, "capability_dormant")

    def test_dormant_when_env_empty_string(self, project, monkeypatch):
        _probe(monkeypatch, 2)
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, "")
        decision, results, reason = sgr.decide_gate_path(project)
        assert (decision, results, reason) == ("degraded", None, "capability_dormant")

    @pytest.mark.parametrize("probe_code", [0, 2])
    def test_delegated_with_valid_results(self, project, monkeypatch, probe_code):
        path = _write_results(project, _valid_payload())
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        _probe(monkeypatch, probe_code)
        decision, results, reason = sgr.decide_gate_path(project)
        assert decision == "delegated"
        assert reason == ""
        assert [asdict(r) for r in results] == _valid_payload()

    def test_nonexistent_project_path_is_safe(self, monkeypatch):
        _probe(monkeypatch, 2)
        decision, results, reason = sgr.decide_gate_path(
            Path("/nonexistent-kit-issue-058")
        )
        assert decision == "degraded"
        assert results is None


class TestUntrustedResultsFile:
    """The results artifact is untrusted input — every violation degrades."""

    def _decide(self, project, monkeypatch, env_value: str):
        _probe(monkeypatch, 2)
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, env_value)
        return sgr.decide_gate_path(project)

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

    def test_non_json_content(self, project, monkeypatch):
        path = _write_results(project, "not json at all {")
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_schema_violation_in_file(self, project, monkeypatch):
        path = _write_results(
            project, [{"gate": "unit", "status": "bogus", "blocking": True}]
        )
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_empty_array_in_file(self, project, monkeypatch):
        path = _write_results(project, [])
        decision, results, reason = self._decide(project, monkeypatch, str(path))
        assert (decision, results, reason) == ("degraded", None, "invalid_results")

    def test_oversized_file(self, project, monkeypatch):
        path = _write_results(project, "x" * (sgr.MAX_RESULTS_BYTES + 1))
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
        sgr.decide_gate_path(project)
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
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        _probe(monkeypatch, 2)
        sgr.decide_gate_path(project)
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
        sgr.decide_gate_path(project)
        event = self._events(project, "testrun")[0]
        assert event["payload"]["reason"] == "invalid_results"
        assert sgr.GATE_RESULTS_ENV in json.dumps(event["payload"])

    def test_silent_noop_without_runs_dir(self, project, monkeypatch):
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        _probe(monkeypatch, 1)
        sgr.decide_gate_path(project)  # must not raise
        assert not (project / ".claude" / "runs").exists()

    def test_silent_noop_without_run_id(self, project, monkeypatch):
        runs = self._runs_dir(project)
        _probe(monkeypatch, 1)
        sgr.decide_gate_path(project)  # must not raise
        assert list(runs.iterdir()) == []


# ── verify_checkpoint wiring seam ────────────────────────────────────


def _fixture_results() -> list:
    return [
        vg.GateResult(gate="unit", status="pass", blocking=True,
                      output="ok", duration_s=1.23),
        vg.GateResult(gate="e2e-web", status="fail", blocking=True,
                      output="line1\nline2", duration_s=0.0),
    ]


EXPECTED_LEGACY_STDOUT = (
    "  GATE PASS: unit [blocking] (1.2s)\n"
    "  GATE FAIL: e2e-web [blocking] (0.0s)\n"
    "        line1\n"
    "        line2\n"
    "WARN: gate failures detected (non-blocking during implement phase)\n"
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
        # the pre-ISSUE-058 verify_gates path.
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
        # Same consumer, same schema, same rendering (AC-2: no consumer change).
        assert capsys.readouterr().out == EXPECTED_LEGACY_STDOUT

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
