"""RED-stage tests for ISSUE-065: provenance / freshness / consume-once
binding on the ``KIT_GATE_RESULTS_FILE`` delegation handoff.

Closes the unresolved High security finding from docs/review_notes/ISSUE-058.md
(forged attestation could bypass the blocking ship-smoke gate) per the
SPEC-058 Open Question that names binding REQUIRED before activation, and
per docs/test_plan.md GAP-058a (stale artifact -> degraded; replay ->
degraded; mutation-tested in both directions).

Contract under test (stage 2 implements exactly this API):

- ``synthesize_gate_results.generate_binding_key() -> bytes`` — per-run
  ephemeral 32-byte key via ``secrets.token_bytes(32)``; the mock seam.
- ``decide_gate_path(project_path, *, binding_key, process_start)`` —
  binding materials are REQUIRED keyword-only parameters with NO defaults:
  unbound wiring cannot compile a call (the activation-blocked guard).
- Provenance: sidecar ``<artifact> + ".sig"`` holding the lowercase-hex
  HMAC-SHA256 of the artifact's raw bytes keyed by ``binding_key``; a
  forged or missing sig refuses the artifact (named check: mac).
- Freshness: artifact ``st_mtime`` must be >= the invoker's process start;
  a backdated artifact refuses (named check: stale).
- Consume-once: a delegated ingest renames the artifact to
  ``<artifact> + ".consumed"``; any later call targeting the same path —
  including a replayed re-write of the artifact — refuses (named check:
  consumed), checked BEFORE parse.
- Every binding refusal returns ``("degraded", None, "binding-rejected")``,
  emits ``gates_degraded_path_used`` telemetry with reason exactly
  ``"binding-rejected"`` plus a detail naming the failed check, and prints
  ONE loud stdout line naming the failed check and KIT_GATE_RESULTS_FILE.
- The dormant degraded flavors (skill_missing / capability_dormant) still
  print NOTHING, and the delegated-success stdout through the real consumer
  stays byte-identical to the pre-binding delegated pin.

Every guard is mutation-tested in BOTH directions: each negative (forged /
stale / consumed) is paired with the positive fixture (correct sig, fresh
mtime, first use) that the delegated path must still accept.
"""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the modules under test from THIS checkout's scripts dir (pinned to
# the fixture root so a fallback resolution cannot hollow-pass elsewhere).
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import synthesize_gate_results as sgr  # noqa: E402
import verify_gates as vg  # noqa: E402
import verify_checkpoint as vc  # noqa: E402

# Reuse the existing suite's helpers and stdout pins (same tests/ dir): the
# byte-identity assertions below must compare against the SAME pre-binding
# pins test_gate_delegation.py enforces, not a re-typed copy that could drift.
import test_gate_delegation as tgd  # noqa: E402


# ── fixtures / helpers ───────────────────────────────────────────────

# Deterministic 32-byte keys for tests (the real key is per-run ephemeral
# via generate_binding_key — monkeypatched at the seam where needed).
KEY = b"\x11" * 32
OTHER_KEY = b"\x22" * 32


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """An isolated fake project root (same shape as test_gate_delegation)."""
    p = tmp_path / "proj"
    p.mkdir()
    return p


def _sign(artifact: Path, key: bytes) -> Path:
    """Write the provenance sidecar: lowercase-hex HMAC-SHA256 of the
    artifact's raw bytes, keyed by ``key``, at ``<artifact> + ".sig"``."""
    sig = Path(str(artifact) + ".sig")
    digest = hmac.new(key, artifact.read_bytes(), hashlib.sha256).hexdigest()
    sig.write_text(digest, encoding="utf-8")
    return sig


def _bound_artifact(
    project: Path,
    key: bytes,
    payload=None,
    name: str = "gate_results.json",
) -> Path:
    """A schema-valid results artifact in .claude/run/ with a MAC sidecar."""
    path = tgd._write_results(
        project, payload if payload is not None else tgd._valid_payload(), name
    )
    _sign(path, key)
    return path


def _decide(project: Path, *, key: bytes = KEY, process_start: float | None = None):
    """Call decide_gate_path through the new REQUIRED binding kwargs.

    Default process_start lies one hour in the past so a just-written
    artifact is fresh by construction.
    """
    if process_start is None:
        process_start = time.time() - 3600.0
    return sgr.decide_gate_path(
        project, binding_key=key, process_start=process_start
    )


def _delegated_pin_payload() -> list[dict]:
    """The payload whose synthesis is exactly tgd._fixture_results() — so the
    real consumer's rendering must be byte-identical to the existing pins."""
    return [asdict(r) for r in tgd._fixture_results()]


def _assert_loud_refusal(out: str, check_name: str) -> None:
    """ONE loud stdout line naming the failed check and the env knob."""
    assert out.count("\n") == 1, f"expected exactly one loud line, got: {out!r}"
    assert check_name in out.lower(), f"line must name the {check_name} check: {out!r}"
    assert "KIT_GATE_RESULTS_FILE" in out


def _runs_dir(project: Path) -> Path:
    d = project / ".claude" / "runs"
    d.mkdir(parents=True)
    return d


def _events(project: Path, run_id: str = "testrun") -> list[dict]:
    path = project / ".claude" / "runs" / f"{run_id}.jsonl"
    assert path.is_file(), f"expected telemetry file at {path}"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ── the per-run ephemeral key (provenance source) ────────────────────


class TestGenerateBindingKey:
    def test_returns_32_ephemeral_bytes_never_a_constant(self):
        """Provenance keys are per-run ephemeral: 32 bytes, fresh each call."""
        key = sgr.generate_binding_key()
        assert isinstance(key, bytes)
        assert len(key) == 32
        # Two runs must never share a key (a hardcoded/persisted key would
        # make every past artifact replayable forever).
        assert sgr.generate_binding_key() != key

    def test_uses_secrets_token_bytes_as_the_mock_seam(self):
        """The key comes from the CSPRNG seam secrets.token_bytes(32) —
        switching to a weaker source breaks provenance."""
        with patch.object(
            sgr.secrets, "token_bytes", return_value=b"k" * 32
        ) as seam:
            assert sgr.generate_binding_key() == b"k" * 32
        seam.assert_called_once_with(32)


# ── AC-5: activation-blocked guard ───────────────────────────────────


class TestActivationBlockedGuard:
    """Binding, not env-var presence, is the enforced activation precondition."""

    def test_binding_kwargs_are_keyword_only_with_no_defaults(self):
        """AC-5a: binding_key / process_start are keyword-only and
        default-less. Mutation direction: anyone adding a default re-opens
        unbound activation and breaks this test."""
        sig = inspect.signature(sgr.decide_gate_path)
        for name in ("binding_key", "process_start"):
            assert name in sig.parameters, (
                f"decide_gate_path must require binding parameter {name!r}"
            )
            param = sig.parameters[name]
            assert param.kind is inspect.Parameter.KEYWORD_ONLY
            assert param.default is inspect.Parameter.empty

    def test_unbound_wiring_without_binding_kwargs_raises_typeerror(
        self, project, monkeypatch
    ):
        """AC-5b: unbound wiring cannot compile a call — even the most
        tempting scenario (valid artifact + env set + probe eligible) raises
        TypeError without binding materials, so activation cannot proceed
        accidentally."""
        path = _bound_artifact(project, KEY)
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)
        with pytest.raises(TypeError):
            sgr.decide_gate_path(project)

    def test_consumer_always_carries_binding_material(self, project, monkeypatch):
        """AC-5c: the only blocking-checkpoint consumer invokes the decision
        with a 32-byte binding_key and the module-level process start."""
        recorder = MagicMock(return_value=("degraded", None, "capability_dormant"))
        monkeypatch.setattr(sgr, "decide_gate_path", recorder)
        with patch.object(
            vg, "run_applicable_gates", return_value=tgd._fixture_results()
        ):
            vc._run_verify_gates(str(project), blocking=False)
        recorder.assert_called_once()
        kwargs = recorder.call_args.kwargs
        assert isinstance(kwargs["binding_key"], bytes)
        assert len(kwargs["binding_key"]) == 32
        assert isinstance(kwargs["process_start"], float)
        assert kwargs["process_start"] == vc._GATE_PROCESS_START


# ── AC-1: provenance (HMAC sidecar) ──────────────────────────────────


class TestProvenanceMac:
    """A schema-valid artifact without authentic provenance is forged."""

    def _setenv(self, project, monkeypatch, path):
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)

    def test_missing_sig_refused_as_binding_rejected(
        self, project, monkeypatch, capsys
    ):
        """AC-1a: no sidecar at all → the mac check refuses; the forged
        artifact never yields delegated results."""
        path = tgd._write_results(project, tgd._valid_payload())
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "binding-rejected")
        _assert_loud_refusal(capsys.readouterr().out, "mac")
        # Refusal must not consume: the artifact stays for forensics.
        assert path.is_file()

    def test_forged_sig_wrong_key_refused(self, project, monkeypatch, capsys):
        """AC-1b: a sidecar forged under a different key fails
        hmac.compare_digest — provenance, not shape, gates delegation."""
        path = _bound_artifact(project, OTHER_KEY)
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project, key=KEY)
        assert (decision, results, reason) == ("degraded", None, "binding-rejected")
        assert results is None, "a forged artifact must never yield delegated results"
        _assert_loud_refusal(capsys.readouterr().out, "mac")

    def test_corrupted_sig_refused(self, project, monkeypatch, capsys):
        """AC-1b: a single flipped hex char in an otherwise-correct sig is a
        mac mismatch."""
        path = tgd._write_results(project, tgd._valid_payload())
        good = hmac.new(KEY, path.read_bytes(), hashlib.sha256).hexdigest()
        corrupted = good[:-1] + ("0" if good[-1] != "0" else "1")
        Path(str(path) + ".sig").write_text(corrupted, encoding="utf-8")
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "binding-rejected")
        _assert_loud_refusal(capsys.readouterr().out, "mac")

    def test_artifact_tampered_after_signing_refused(
        self, project, monkeypatch, capsys
    ):
        """AC-1b: the MAC covers the artifact's raw bytes — swapping in a
        forged all-pass payload under a once-valid sig refuses."""
        path = _bound_artifact(project, KEY)
        # Tamper after signing: the classic forged-attestation vector from
        # the ISSUE-058 High finding (all-pass artifact, zero tests run).
        path.write_text(
            json.dumps(
                [{"gate": "unit", "status": "pass", "blocking": True}]
            ),
            encoding="utf-8",
        )
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "binding-rejected")
        assert results is None
        _assert_loud_refusal(capsys.readouterr().out, "mac")

    def test_correct_hmac_sig_same_key_delegates(self, project, monkeypatch, capsys):
        """AC-1 positive fixture (mutation pair for every mac refusal): the
        SAME artifact with a correct HMAC-SHA256 sidecar under the same key
        delegates with the synthesized GateResults — and the module itself
        prints nothing on success (the consumer owns the marker)."""
        path = _bound_artifact(project, KEY)
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project)
        assert decision == "delegated"
        assert reason == ""
        assert [asdict(r) for r in results] == tgd._valid_payload()
        assert capsys.readouterr().out == ""


# ── AC-2: freshness ──────────────────────────────────────────────────


class TestFreshness:
    """A validly MACed artifact from a previous run is stale, not evidence."""

    def _setenv(self, project, monkeypatch, path):
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)

    def test_backdated_artifact_refused_as_stale(self, project, monkeypatch, capsys):
        """AC-2a: os.utime-backdated mtime < process_start → refused, named
        stale, degraded binding-rejected."""
        now = time.time()
        path = _bound_artifact(project, KEY)
        os.utime(path, (now - 7200.0, now - 7200.0))
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project, process_start=now - 3600.0)
        assert (decision, results, reason) == ("degraded", None, "binding-rejected")
        _assert_loud_refusal(capsys.readouterr().out, "stale")

    def test_stale_refusal_shape_identical_to_forged_refusal(
        self, project, monkeypatch, capsys
    ):
        """AC-2: the stale refusal is shaped exactly like the forged (mac)
        refusal — same (decision, results, reason) tuple; only the named
        check in the loud line differs."""
        now = time.time()
        forged_path = _bound_artifact(project, OTHER_KEY, name="forged.json")
        self._setenv(project, monkeypatch, forged_path)
        forged = _decide(project, key=KEY, process_start=now - 3600.0)
        out_forged = capsys.readouterr().out

        stale_path = _bound_artifact(project, KEY, name="stale.json")
        os.utime(stale_path, (now - 7200.0, now - 7200.0))
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(stale_path))
        stale = _decide(project, key=KEY, process_start=now - 3600.0)
        out_stale = capsys.readouterr().out

        assert forged == stale == ("degraded", None, "binding-rejected")
        assert "mac" in out_forged.lower() and "stale" not in out_forged.lower()
        assert "stale" in out_stale.lower() and "mac" not in out_stale.lower()

    def test_fresh_artifact_accepted(self, project, monkeypatch):
        """AC-2 positive fixture: mtime >= process_start passes freshness."""
        path = _bound_artifact(project, KEY)
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(
            project, process_start=time.time() - 3600.0
        )
        assert decision == "delegated"
        assert [asdict(r) for r in results] == tgd._valid_payload()

    def test_mtime_exactly_at_process_start_is_fresh(self, project, monkeypatch):
        """AC-2 boundary: st_mtime == process_start is fresh (>=, not >) —
        mutation direction for an off-by-one freshness comparison."""
        path = _bound_artifact(project, KEY)
        boundary = path.stat().st_mtime
        self._setenv(project, monkeypatch, path)
        decision, _results, reason = _decide(project, process_start=boundary)
        assert (decision, reason) == ("delegated", "")


# ── AC-3: consume-once ───────────────────────────────────────────────


class TestConsumeOnce:
    """One artifact attests at most one run — replay refuses."""

    def _setenv(self, project, monkeypatch, path):
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)

    def test_first_call_delegates_and_consumes_the_artifact(
        self, project, monkeypatch
    ):
        """AC-3a: the first decide_gate_path call delegates AND renames the
        artifact to <artifact>.consumed (original gone, marker present,
        sidecar no longer at its original path)."""
        path = _bound_artifact(project, KEY)
        sig = Path(str(path) + ".sig")
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project)
        assert decision == "delegated"
        assert [asdict(r) for r in results] == tgd._valid_payload()
        assert not path.exists(), "consumed artifact must be renamed away"
        assert Path(str(path) + ".consumed").is_file()
        assert not sig.exists(), "sidecar must be removed or renamed with the artifact"

    def test_second_call_same_path_refused_as_consumed(
        self, project, monkeypatch, capsys
    ):
        """AC-3b: a second call targeting the same path refuses as consumed
        — degraded, binding-rejected, loud line."""
        path = _bound_artifact(project, KEY)
        self._setenv(project, monkeypatch, path)
        first = _decide(project)
        assert first[0] == "delegated"
        capsys.readouterr()  # flush any first-call output

        second = _decide(project)
        assert second == ("degraded", None, "binding-rejected")
        _assert_loud_refusal(capsys.readouterr().out, "consumed")

    def test_replayed_artifact_after_consume_refused(
        self, project, monkeypatch, capsys
    ):
        """GAP-058a replay mutation: re-writing the SAME artifact + valid
        fresh sig at the consumed path still refuses — the .consumed marker
        wins over a byte-perfect replay."""
        path = _bound_artifact(project, KEY)
        self._setenv(project, monkeypatch, path)
        assert _decide(project)[0] == "delegated"
        capsys.readouterr()

        # Replay: identical payload, correctly re-signed, fresh mtime.
        replayed = _bound_artifact(project, KEY)
        assert replayed == path
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "binding-rejected")
        _assert_loud_refusal(capsys.readouterr().out, "consumed")

    def test_consumed_marker_checked_before_parse(self, project, monkeypatch, capsys):
        """AC-3 ordering: the consumed marker refuses BEFORE parse (and
        before the mac check) — unparseable garbage plus a marker yields
        binding-rejected/consumed, never invalid_results."""
        path = tgd._write_results(project, "{{{ not json")
        Path(str(path) + ".consumed").write_text("", encoding="utf-8")
        # Deliberately no sidecar: if mac ran first the detail would name
        # mac; if parse ran first the reason would be invalid_results.
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "binding-rejected")
        _assert_loud_refusal(capsys.readouterr().out, "consumed")


# ── schema violations keep their existing reason ─────────────────────


class TestSchemaViolationsStayInvalidResults:
    """Binding verifies provenance/freshness/one-shot; shape violations keep
    the existing invalid_results contract — they are NOT binding-rejected."""

    def _setenv(self, project, monkeypatch, path):
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)

    def test_schema_violation_with_valid_binding_stays_invalid_results(
        self, project, monkeypatch
    ):
        """A correctly MACed, fresh artifact with a bad status degrades with
        reason invalid_results — and is NOT consumed (consume happens only
        after a successful parse)."""
        path = _bound_artifact(
            project, KEY, payload=[{"gate": "unit", "status": "bogus", "blocking": True}]
        )
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "invalid_results")
        assert path.is_file(), "a schema refusal must not consume the artifact"
        assert not Path(str(path) + ".consumed").exists()

    def test_non_json_with_valid_mac_stays_invalid_results(
        self, project, monkeypatch
    ):
        """The MAC covers raw bytes, so authentic-but-unparseable content
        passes mac and fails at the existing parse step."""
        path = _bound_artifact(project, KEY, payload="not json at all {")
        self._setenv(project, monkeypatch, path)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "invalid_results")


# ── dormant paths stay silent through the bound API ──────────────────


class TestDormantPathsStaySilent:
    """The dormant degraded flavors print NOTHING — the existing
    byte-identity pins in test_gate_delegation.py must keep holding once the
    bound signature lands."""

    def test_skill_missing_prints_nothing(self, project, monkeypatch, capsys):
        tgd._probe(monkeypatch, 1)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "skill_missing")
        assert capsys.readouterr().out == ""

    def test_capability_dormant_prints_nothing_and_reason_unchanged(
        self, project, monkeypatch, capsys
    ):
        """Dormant-path regression guard: env unset → reason stays
        capability_dormant, zero stdout, through the new bound signature."""
        tgd._probe(monkeypatch, 2)
        decision, results, reason = _decide(project)
        assert (decision, results, reason) == ("degraded", None, "capability_dormant")
        assert capsys.readouterr().out == ""


# ── telemetry ────────────────────────────────────────────────────────


class TestBindingTelemetry:
    def test_mac_refusal_emits_binding_rejected_with_detail(
        self, project, monkeypatch
    ):
        """AC-1 telemetry: reason is EXACTLY "binding-rejected"; detail names
        the mac check."""
        _runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        path = tgd._write_results(project, tgd._valid_payload())  # no sig
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)
        _decide(project)
        events = _events(project)
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "gates_degraded_path_used"
        assert event["payload"]["reason"] == "binding-rejected"
        assert "mac" in event["payload"]["detail"].lower()

    def test_stale_refusal_detail_names_stale(self, project, monkeypatch):
        """AC-2 telemetry: the stale refusal's detail names the freshness
        check."""
        _runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        now = time.time()
        path = _bound_artifact(project, KEY)
        os.utime(path, (now - 7200.0, now - 7200.0))
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)
        _decide(project, process_start=now - 3600.0)
        event = _events(project)[0]
        assert event["payload"]["reason"] == "binding-rejected"
        assert "stale" in event["payload"]["detail"].lower()

    def test_consumed_refusal_detail_names_consumed(self, project, monkeypatch):
        """AC-3 telemetry: the consume-once refusal's detail names the
        consumed check."""
        _runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        run_dir = project / ".claude" / "run"
        run_dir.mkdir(parents=True)
        path = run_dir / "gate_results.json"
        Path(str(path) + ".consumed").write_text("", encoding="utf-8")
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)
        decision, _results, reason = _decide(project)
        assert (decision, reason) == ("degraded", "binding-rejected")
        event = _events(project)[0]
        assert event["payload"]["reason"] == "binding-rejected"
        assert "consumed" in event["payload"]["detail"].lower()

    def test_dormant_telemetry_unchanged_through_bound_api(
        self, project, monkeypatch
    ):
        """Dormant paths keep their existing telemetry tags — binding changes
        nothing when no artifact is offered."""
        _runs_dir(project)
        monkeypatch.setenv(sgr.RUN_ID_ENV, "testrun")
        tgd._probe(monkeypatch, 1)
        decision, _results, reason = _decide(project)
        assert (decision, reason) == ("degraded", "skill_missing")
        event = _events(project)[0]
        assert event["event_type"] == "gates_degraded_path_used"
        assert event["payload"]["reason"] == "skill_missing"


# ── AC-4: byte-identity through the real consumer ────────────────────


class TestConsumerWiringBinding:
    def test_gate_process_start_is_module_level_float(self):
        """The invoker's freshness reference is captured at import — a float
        that lies in the past relative to any later call."""
        assert isinstance(vc._GATE_PROCESS_START, float)
        assert vc._GATE_PROCESS_START <= time.time()

    def test_delegated_stdout_byte_identical_to_pre_binding_pin(
        self, project, monkeypatch, capsys
    ):
        """AC-4: through the real consumer with the seam key
        (generate_binding_key monkeypatched to a known key) and a past
        _GATE_PROCESS_START, a validly bound fresh artifact renders stdout
        byte-identical to the pre-binding delegated pin — marker + all four
        statuses through the renderer — and the verify_gates seam is NEVER
        called."""
        path = tgd._write_results(project, _delegated_pin_payload())
        _sign(path, KEY)
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        tgd._probe(monkeypatch, 2)
        monkeypatch.setattr(sgr, "generate_binding_key", lambda: KEY)
        monkeypatch.setattr(vc, "_GATE_PROCESS_START", time.time() - 3600.0)
        with patch.object(vg, "run_applicable_gates") as seam:
            assert vc._run_verify_gates(str(project), blocking=False) is True
        seam.assert_not_called()
        assert capsys.readouterr().out == (
            tgd.EXPECTED_DELEGATED_MARKER + tgd.EXPECTED_LEGACY_STDOUT
        )

    def test_binding_rejected_parity_with_dormant_degraded(
        self, project, monkeypatch, capsys
    ):
        """Degradation parity: a binding-rejected run's checkpoint-visible
        result equals the capability-dormant degraded run — the verify_gates
        seam runs exactly once in both; only the loud refusal line (naming
        mac + KIT_GATE_RESULTS_FILE) differs on stdout."""
        tgd._probe(monkeypatch, 2)
        monkeypatch.setattr(sgr, "generate_binding_key", lambda: KEY)
        monkeypatch.setattr(vc, "_GATE_PROCESS_START", time.time() - 3600.0)

        # Run A: forged artifact (sig under the wrong key) → binding-rejected.
        path = _bound_artifact(project, OTHER_KEY, payload=_delegated_pin_payload())
        monkeypatch.setenv(sgr.GATE_RESULTS_ENV, str(path))
        with patch.object(
            vg, "run_applicable_gates", return_value=tgd._fixture_results()
        ) as seam_a:
            ret_a = vc._run_verify_gates(str(project), blocking=False)
        seam_a.assert_called_once()
        out_a = capsys.readouterr().out

        # Run B: dormant (env unset) — the legacy byte-identical degraded run.
        monkeypatch.delenv(sgr.GATE_RESULTS_ENV)
        with patch.object(
            vg, "run_applicable_gates", return_value=tgd._fixture_results()
        ) as seam_b:
            ret_b = vc._run_verify_gates(str(project), blocking=False)
        seam_b.assert_called_once()
        out_b = capsys.readouterr().out

        assert ret_a is True
        assert ret_a == ret_b
        assert out_b == tgd.EXPECTED_LEGACY_STDOUT
        assert "GATES DELEGATED" not in out_a, (
            "a forged artifact must never yield delegated results"
        )
        assert out_a.endswith(tgd.EXPECTED_LEGACY_STDOUT)
        loud = out_a[: -len(tgd.EXPECTED_LEGACY_STDOUT)]
        _assert_loud_refusal(loud, "mac")
