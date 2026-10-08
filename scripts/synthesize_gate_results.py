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
    probe exit 1                        -> degraded, reason ``skill_missing``
    probe exit 0/2, env unset/empty     -> degraded, reason ``capability_dormant``
    probe exit 0/2, env set, bad file   -> degraded, reason ``invalid_results``
    probe exit 0/2, env set, valid file -> delegated (synthesized GateResults)

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
        Unset or no runs dir => emission is a silent no-op.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import has_skill
import verify_gates

# The prospective runtime test-execution capability (SPEC-019 follow-up
# signal; listed in has_skill.RUNTIME_BUILTIN_SKILLS so the probe returns
# 2 = "unknown" rather than 1 = "missing").
RUNTIME_TEST_SKILL = "verify"

# The activation handoff: set by the model layer only after it has actually
# invoked the runtime capability and persisted machine-readable results.
GATE_RESULTS_ENV = "KIT_GATE_RESULTS_FILE"

# Script-side run-id source for telemetry (docs/telemetry_schema.md).
RUN_ID_ENV = "KIT_RUN_ID"

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

# Telemetry payload ceiling per docs/telemetry_schema.md (POSIX O_APPEND
# atomicity for small writes).
_MAX_EVENT_BYTES = 4096


class GateSynthesisError(ValueError):
    """Raised when a runtime results payload violates the ingestion contract."""


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


def _load_results_file(raw: str, project_path: Path) -> list["verify_gates.GateResult"]:
    """Validate and load the handoff artifact (untrusted input)."""
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
        if real.stat().st_size > MAX_RESULTS_BYTES:
            raise GateSynthesisError(
                f"results file exceeds {MAX_RESULTS_BYTES} bytes"
            )
        payload = json.loads(real.read_text(encoding="utf-8"))
    except GateSynthesisError:
        raise
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        # RecursionError: pathologically nested JSON must map into the
        # module's own error contract, not escape to the caller.
        raise GateSynthesisError(f"unreadable or non-JSON results file: {exc}") from exc

    return synthesize_gate_results(payload)


# ── telemetry (best-effort, silent no-op, never raises) ──────────────


# Whitelist for the attacker-influenced run-id filename component.
_RUN_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")

# Attacker-derived text (e.g. GateSynthesisError messages quoting unknown
# keys) is truncated rather than allowed to pad the event past the 4 KiB
# cap — padding would silently drop the forensic record.
_MAX_DETAIL_CHARS = 512


def _emit_telemetry(project_path: Path, event_type: str, payload: dict) -> None:
    """Append one schema-conformant event line; silent no-op when unconfigured.

    Hardened as an untrusted-path write: run-id is whitelist-validated, the
    runs dir realpath must stay inside the project, the event file is opened
    ``O_NOFOLLOW`` so a pre-planted symlink cannot redirect the append.
    """
    try:
        run_id = os.environ.get(RUN_ID_ENV, "").strip()
        if not _RUN_ID_RE.fullmatch(run_id):
            return
        runs_dir = project_path / ".claude" / "runs"
        if not runs_dir.is_dir():
            return
        if not runs_dir.resolve().is_relative_to(project_path.resolve()):
            return
        detail = payload.get("detail")
        if isinstance(detail, str) and len(detail) > _MAX_DETAIL_CHARS:
            payload = {**payload, "detail": detail[:_MAX_DETAIL_CHARS] + "…[truncated]"}
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "skill_or_script": _SCRIPT_NAME,
            "payload": payload,
        }
        data = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        if len(data) > _MAX_EVENT_BYTES:
            return
        fd = os.open(
            runs_dir / f"{run_id}.jsonl",
            os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o644,
        )
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    except Exception:
        # Never fail the parent gate run on a telemetry write error.
        return


# ── path decision ────────────────────────────────────────────────────


def decide_gate_path(
    project_path: Path,
) -> tuple[str, list["verify_gates.GateResult"] | None, str]:
    """Decide between the delegated and degraded gate paths.

    Returns ``(decision, results, reason)`` where decision is ``"delegated"``
    (results is the synthesized GateResult list) or ``"degraded"`` (results is
    None; the caller runs ``verify_gates.run_applicable_gates`` unchanged).
    Prints nothing — the degraded path must stay byte-identical on stdout.
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
        results = _load_results_file(raw, pp)
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
