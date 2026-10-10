#!/usr/bin/env python3
"""Dormant test-execution delegation layer (ISSUE-058 / SPEC-058).

Extends the SPEC-018/019 delegation idiom to test execution: probe for a
runtime test-execution capability, delegate when a valid handoff artifact is
present, synthesize its results into the existing ``verify_gates.GateResult``
contract, and fall back to ``verify_gates.py`` (unchanged) in every other
case — with telemetry tagging which path ran.

The delegation branch is **dormant** today: the SPEC-058 survey found no
confirmed runtime test-execution capability with a machine-readable result
contract. Activation trigger (named per ISSUE-058 AC-3): a Claude Code
runtime build exposing a test-execution skill (expected name ``/verify``)
that emits per-gate results; the ship/review skill templates then invoke it,
persist the results JSON, and set ``KIT_GATE_RESULTS_FILE`` for the
checkpoint run.

Decision table (``decide_gate_path``):
    probe exit 1                          -> degraded, reason ``skill_missing``
    probe exit 0/2, env unset/empty       -> degraded, reason ``capability_dormant``
    probe exit 0/2, env set, bad file     -> degraded, reason ``invalid_results``
    probe exit 0/2, env set, binding fail -> degraded, reason ``binding-rejected``
    probe exit 0/2, env set, valid+bound  -> delegated (synthesized GateResults)

Binding layer (ISSUE-065, closing the ISSUE-058 review High finding —
schema validation is not provenance):
    - **Provenance**: the artifact must be accompanied by a sidecar at
      ``<artifact> + ".sig"`` holding the lowercase-hex HMAC-SHA256 of the
      artifact's raw bytes, keyed by a **per-run ephemeral in-process key**
      (``generate_binding_key()`` = ``secrets.token_bytes(32)``). The key is
      never persisted to the workspace and never read from the environment —
      there is NO new env knob. A missing, unreadable, or mismatching sidecar
      refuses the artifact (check name: ``mac``).
    - **Freshness**: the artifact's ``st_mtime`` must be >= the invoking
      checkpoint's process start (check name: ``stale``).
    - **Consume-once**: a successful delegated ingest renames the artifact to
      ``<artifact> + ".consumed"``; any later call targeting the same path —
      including a byte-perfect replay — refuses (check name: ``consumed``,
      checked BEFORE parse).
    Binding materials are REQUIRED keyword-only parameters of
    ``decide_gate_path`` with no defaults: unbound wiring cannot compile a
    call, so binding — not env-var presence — is the enforced activation
    precondition. Every binding refusal degrades toward running the real
    gates with reason ``binding-rejected``, emits telemetry whose detail
    names the failed check and ``KIT_GATE_RESULTS_FILE``, and prints ONE
    loud stdout line doing the same. Schema violations keep the existing
    ``invalid_results`` reason and never consume the artifact.

The results artifact is **untrusted input**: option-shaped paths are
rejected, the realpath must stay inside ``<project>/.claude/run/`` (the
kit's gitignored run-scoped scratch dir — a tracked artifact cannot live
there without a visible force-add), only a regular JSON file up to
``MAX_RESULTS_BYTES`` is accepted, and the payload must be a non-empty JSON
array matching the strict per-gate schema below. Every violation degrades
toward *running the real gates* — never toward skipping them. A delegated
run is never silent: the checkpoint consumer prints an unmistakable
``GATES DELEGATED`` stdout marker naming ``KIT_GATE_RESULTS_FILE`` (only
the *degraded* path is byte-identical to the legacy output).

Ingestion contract (the synthesis source): a JSON array of objects, each
exactly ``{gate: slug str (see _GATE_NAME_RE), status:
"pass"|"fail"|"skip"|"warn", blocking: bool, output?: str free of control
characters other than \\n and \\t, duration_s?: finite number in
[0, MAX_DURATION_S]}`` — no extra keys. The synthesis target is
``verify_gates.GateResult``; the checkpoint consumer
(``verify_checkpoint._run_verify_gates``) is unchanged.

Env knobs (documented here and in README's environment-variable list):
    KIT_GATE_RESULTS_FILE — path to the runtime per-gate results JSON
        (the model-layer handoff artifact). Unset => degraded path.
    KIT_RUN_ID — run id for best-effort telemetry appends to
        ``<project>/.claude/runs/<run-id>.jsonl`` (see docs/telemetry_schema.md).
        Resolved inside the shared emitter (``scripts/kit_telemetry.py``,
        ISSUE-067): unset or invalid => the event is written under the
        ``unattributed`` fallback run id with one ``[kit-telemetry]`` stdout
        announcement naming the knob — no longer a silent no-op. The runs
        dir is auto-created.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets
from pathlib import Path

import has_skill
import kit_telemetry
import verify_gates

# The prospective runtime test-execution capability (SPEC-019 follow-up
# signal; listed in has_skill.RUNTIME_BUILTIN_SKILLS so the probe returns
# 2 = "unknown" rather than 1 = "missing").
RUNTIME_TEST_SKILL = "verify"

# The activation handoff: set by the model layer only after it has actually
# invoked the runtime capability and persisted machine-readable results.
GATE_RESULTS_ENV = "KIT_GATE_RESULTS_FILE"

# Script-side run-id source for telemetry (docs/telemetry_schema.md). The
# knob's single home is the shared emitter (ISSUE-067); aliased here for the
# existing import surface.
RUN_ID_ENV = kit_telemetry.RUN_ID_ENV

# Untrusted-input size cap for the results artifact. Gate outputs are tails
# of <= 2000 chars each, so 1 MB is generous for any legitimate run.
MAX_RESULTS_BYTES = 1_000_000

# Exact status vocabulary consumed by verify_checkpoint's icon lookup.
ALLOWED_STATUSES = frozenset({"pass", "fail", "skip", "warn"})

_ALLOWED_KEYS = frozenset({"gate", "status", "blocking", "output", "duration_s"})

# Gate names are slugs (the real vocabulary is unit/integration/e2e-web/…);
# anything looser would let a crafted name forge transcript lines at the
# consumer's raw print (security review, PR #100 finding 5).
_GATE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")

# Output is printed raw by the checkpoint consumer (last lines of a fail
# tail) — reject C0/C1 control characters except \n and \t so a delegated
# artifact cannot drive the operator's terminal (ANSI/OSC injection).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

# Finite ceiling for duration_s (~115 days). Unbounded ints overflow the
# consumer's float formatting; NaN/Infinity parse from JSON by default.
MAX_DURATION_S = 10**7

_SCRIPT_NAME = "synthesize_gate_results"

# Untrusted-input size cap for the provenance sidecar: a hex HMAC-SHA256 is
# 64 chars, so 1 KiB tolerates whitespace padding without admitting bulk.
MAX_SIG_BYTES = 1024

# The sidecar body is exactly one lowercase-hex HMAC-SHA256 digest
# (surrounding whitespace tolerated via .strip() before matching).
_HEX_SIG_RE = re.compile(r"[0-9a-f]{64}")


class GateSynthesisError(ValueError):
    """Raised when a runtime results payload violates the ingestion contract."""


class _BindingRejected(Exception):
    """Raised when the handoff artifact fails provenance/freshness/consume-once
    binding. ``check`` names the failed check: ``consumed``, ``mac``, or
    ``stale``. Always degrades toward running the real gates."""

    def __init__(self, check: str, message: str) -> None:
        super().__init__(message)
        self.check = check


def generate_binding_key() -> bytes:
    """Return a per-run ephemeral 32-byte binding key.

    Sourced from the CSPRNG seam ``secrets.token_bytes(32)``. The key lives
    only in the invoking process: it is never persisted to the workspace and
    never read from the environment (no env knob exists for it by design —
    a persisted or env-sourced key would make every past artifact replayable).
    """
    return secrets.token_bytes(32)


# ── synthesis mapper (deterministic, unit-tested) ────────────────────


def synthesize_gate_results(payload: object) -> list["verify_gates.GateResult"]:
    """Map a runtime-shaped results payload to ``verify_gates.GateResult``s.

    Strict by design: any deviation from the documented ingestion contract
    raises :class:`GateSynthesisError`. An empty array is a violation — a
    delegation that ran zero gates cannot attest anything and must never be
    allowed to skip the real gates.
    """
    if not isinstance(payload, list):
        raise GateSynthesisError(
            f"results payload must be a JSON array, got {type(payload).__name__}"
        )
    if not payload:
        raise GateSynthesisError(
            "empty gate list — a delegation that ran zero gates cannot attest anything"
        )

    results: list[verify_gates.GateResult] = []
    for i, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise GateSynthesisError(
                f"entry {i}: expected a gate object, got {type(entry).__name__}"
            )
        unknown = set(entry) - _ALLOWED_KEYS
        if unknown:
            raise GateSynthesisError(f"entry {i}: unknown key(s) {sorted(unknown)}")

        gate = entry.get("gate")
        if not isinstance(gate, str) or not _GATE_NAME_RE.fullmatch(gate):
            raise GateSynthesisError(
                f"entry {i}: 'gate' must be a slug matching {_GATE_NAME_RE.pattern}"
            )

        status = entry.get("status")
        if status not in ALLOWED_STATUSES:
            raise GateSynthesisError(
                f"entry {i}: 'status' must be one of {sorted(ALLOWED_STATUSES)}, "
                f"got {status!r}"
            )

        blocking = entry.get("blocking")
        if not isinstance(blocking, bool):
            raise GateSynthesisError(f"entry {i}: 'blocking' must be a JSON boolean")

        output = entry.get("output", "")
        if not isinstance(output, str):
            raise GateSynthesisError(f"entry {i}: 'output' must be a string")
        if _CONTROL_CHARS_RE.search(output):
            raise GateSynthesisError(
                f"entry {i}: 'output' contains control characters "
                "(only \\n and \\t are allowed — it is printed raw)"
            )

        duration = entry.get("duration_s", 0.0)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise GateSynthesisError(
                f"entry {i}: 'duration_s' must be a non-negative number"
            )
        try:
            duration = float(duration)
        except OverflowError:
            raise GateSynthesisError(
                f"entry {i}: 'duration_s' out of range"
            ) from None
        if not math.isfinite(duration) or not 0 <= duration <= MAX_DURATION_S:
            raise GateSynthesisError(
                f"entry {i}: 'duration_s' must be a finite number in "
                f"[0, {MAX_DURATION_S}]"
            )

        results.append(
            verify_gates.GateResult(
                gate=gate,
                status=status,
                blocking=blocking,
                output=output,
                duration_s=duration,
            )
        )
    return results


# ── untrusted results-file loader ────────────────────────────────────


def _read_sidecar(sig_path: Path, run_dir_real: Path) -> str | None:
    """Read the provenance sidecar (untrusted input in the same
    attacker-writable dir as the artifact).

    Returns the lowercase-hex digest string, or ``None`` on ANY violation —
    missing, symlinked outside ``.claude/run/``, not a regular file,
    oversized, unreadable, or not exactly one hex HMAC-SHA256 digest
    (surrounding whitespace tolerated). Every ``None`` becomes a ``mac``
    refusal upstream: the failure direction is always toward the real gates.
    """
    try:
        if not sig_path.resolve().is_relative_to(run_dir_real):
            return None
        if not sig_path.is_file():
            return None
        if sig_path.stat().st_size > MAX_SIG_BYTES:
            return None
        text = sig_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not _HEX_SIG_RE.fullmatch(text):
        return None
    return text


def _load_results_file(
    raw: str,
    project_path: Path,
    *,
    binding_key: bytes,
    process_start: float,
) -> list["verify_gates.GateResult"]:
    """Validate, authenticate, and consume the handoff artifact.

    The artifact is untrusted input. Verification order: consume-once marker
    (BEFORE parse) -> path/containment/regular-file/size -> raw bytes ->
    MAC (provenance) -> freshness -> JSON parse + strict schema -> consume.
    Raises :class:`_BindingRejected` on binding failures and
    :class:`GateSynthesisError` on shape/path failures (which never consume).
    """
    if raw.startswith("-"):
        raise GateSynthesisError("option-shaped path rejected")

    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_path / candidate
    try:
        real = candidate.resolve()
        run_dir_real = (project_path / ".claude" / "run").resolve()
    except OSError as exc:  # pragma: no cover — platform-specific resolution errors
        raise GateSynthesisError(f"unresolvable path: {exc}") from exc

    # Consume-once comes first: an already-consumed path refuses before any
    # parse or MAC work — a byte-perfect replay must never re-attest.
    consumed_marker = Path(str(real) + ".consumed")
    if consumed_marker.exists():
        raise _BindingRejected(
            "consumed", "artifact was already consumed by a previous gate run"
        )

    if not real.is_relative_to(run_dir_real):
        # Containment is deliberately tighter than "inside the project":
        # .claude/run/ is gitignored, so a committed artifact cannot be
        # smuggled in as the handoff (security review, PR #100 finding 1).
        raise GateSynthesisError(
            "results file must live inside <project>/.claude/run/"
        )
    if not real.is_file():
        raise GateSynthesisError("results path is not a regular file")
    try:
        stat = real.stat()
        if stat.st_size > MAX_RESULTS_BYTES:
            raise GateSynthesisError(
                f"results file exceeds {MAX_RESULTS_BYTES} bytes"
            )
        data = real.read_bytes()
    except GateSynthesisError:
        raise
    except OSError as exc:
        raise GateSynthesisError(f"unreadable results file: {exc}") from exc

    # Provenance: the sidecar must authenticate the artifact's raw bytes
    # under this run's ephemeral key. Missing/invalid sidecar == mismatch.
    sig_path = Path(str(real) + ".sig")
    expected = _read_sidecar(sig_path, run_dir_real)
    if expected is None:
        raise _BindingRejected(
            "mac", "provenance sidecar (.sig) is missing or unreadable"
        )
    digest = hmac.new(binding_key, data, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, expected):
        raise _BindingRejected(
            "mac", "provenance sidecar does not authenticate the artifact"
        )

    # Freshness: an artifact older than the invoking process is not evidence
    # for this run (>= keeps the exact-boundary artifact fresh).
    if stat.st_mtime < process_start:
        raise _BindingRejected(
            "stale", "artifact predates this checkpoint process"
        )

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        # RecursionError: pathologically nested JSON must map into the
        # module's own error contract, not escape to the caller.
        raise GateSynthesisError(f"unreadable or non-JSON results file: {exc}") from exc

    results = synthesize_gate_results(payload)

    # Consume-once: only a fully verified, successfully parsed artifact is
    # consumed (schema refusals keep the artifact for forensics). If the
    # rename fails the ingest must not count — one artifact, one attestation.
    try:
        os.replace(real, consumed_marker)
    except OSError as exc:
        raise _BindingRejected(
            "consumed", f"could not mark the artifact consumed: {exc}"
        ) from exc
    try:
        os.unlink(sig_path)
    except OSError:
        pass  # best-effort cleanup; the .consumed marker alone blocks replay

    return results


# ── telemetry (best-effort, never raises — shared emitter, ISSUE-067) ─


def _emit_telemetry(project_path: Path, event_type: str, payload: dict) -> None:
    """Delegate to the shared hardened emitter (``kit_telemetry.emit_event``).

    The ISSUE-058 writer hardening (run-id whitelist, containment, detail
    truncation, O_NOFOLLOW, 4 KiB cap) lives in its single home there. Since
    ISSUE-067 an unconfigured ``KIT_RUN_ID`` falls back to the announced
    ``unattributed`` run id instead of silently dropping the event.
    """
    kit_telemetry.emit_event(
        event_type, payload, script_name=_SCRIPT_NAME, project_path=project_path
    )


# ── path decision ────────────────────────────────────────────────────


def decide_gate_path(
    project_path: Path,
    *,
    binding_key: bytes,
    process_start: float,
) -> tuple[str, list["verify_gates.GateResult"] | None, str]:
    """Decide between the delegated and degraded gate paths.

    ``binding_key`` (per-run ephemeral, see :func:`generate_binding_key`) and
    ``process_start`` (the invoker's own process-start timestamp) are
    REQUIRED keyword-only parameters with no defaults: wiring that cannot
    supply binding materials cannot compile a call, so the delegated branch
    is unreachable without provenance (the activation-blocked guard).

    Returns ``(decision, results, reason)`` where decision is ``"delegated"``
    (results is the synthesized GateResult list) or ``"degraded"`` (results is
    None; the caller runs ``verify_gates.run_applicable_gates`` unchanged).
    Gate-decision stdout is unchanged: the dormant flavors print no GATE
    output of their own, and a binding refusal prints ONE loud line naming
    the failed check and the env knob. The shared emitter (ISSUE-067) may
    additionally print its own ``[kit-telemetry]`` fallback announcement
    when telemetry is unconfigured (``KIT_RUN_ID`` unset/invalid).
    """
    pp = Path(project_path)

    code, _evidence = has_skill.find_skill(RUNTIME_TEST_SKILL)
    if code == 1:
        # Definitive miss: always degrade, even if a results artifact exists
        # (ISSUE-058 AC-1 — probe exit 1 pins today's behavior exactly).
        _emit_telemetry(pp, "gates_degraded_path_used", {"reason": "skill_missing"})
        return ("degraded", None, "skill_missing")

    raw = os.environ.get(GATE_RESULTS_ENV, "").strip()
    if not raw:
        # Delegation-eligible but dormant: no handoff artifact was produced.
        _emit_telemetry(
            pp, "gates_degraded_path_used", {"reason": "capability_dormant"}
        )
        return ("degraded", None, "capability_dormant")

    try:
        results = _load_results_file(
            raw, pp, binding_key=binding_key, process_start=process_start
        )
    except _BindingRejected as exc:
        _emit_telemetry(
            pp,
            "gates_degraded_path_used",
            {
                "reason": "binding-rejected",
                "detail": f"{exc.check}: {GATE_RESULTS_ENV} {exc}",
            },
        )
        # A refused attestation is never silent (unlike the dormant flavors):
        # one loud line naming the failed check and the env knob.
        print(
            f"  GATE BINDING REJECTED [{exc.check}]: {GATE_RESULTS_ENV} "
            f"artifact refused by the {exc.check} check — running the real "
            "gates instead"
        )
        return ("degraded", None, "binding-rejected")
    except GateSynthesisError as exc:
        _emit_telemetry(
            pp,
            "gates_degraded_path_used",
            {"reason": "invalid_results", "detail": f"{GATE_RESULTS_ENV}: {exc}"},
        )
        return ("degraded", None, "invalid_results")

    _emit_telemetry(
        pp,
        "gates_delegated_to_runtime",
        {"skill": RUNTIME_TEST_SKILL, "gate_count": len(results)},
    )
    return ("delegated", results, "")
