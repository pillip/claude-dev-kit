# Security Review — ISSUE-047 (PR #56, commit 8b7bbaa)

Dimension: security (degraded path — runtime /security-review not invocable)

Scope: `git diff c04b78b..HEAD` — scripts/verify_gates.py (+25/-2: `_DEFAULT_TEST_TIMEOUT`, `_test_timeout()`, two `run_gate_unit` call sites), scripts/verify_checkpoint.py (+1 comment), tests/test_verify_gates.py (+94), tests/test_verify_checkpoint.py (+14/-2). Local/CI developer tooling, not user-facing.

## Verdict

Clean on every high-impact axis. One Low-severity finding — the same no-upper-bound gap ISSUE-046's review found in the identical `verify_checkpoint.py` pattern, re-verified here against verify_gates.py's own exception handling and both invocation paths. Nothing blocking.

Verified in the worktree code, not just the diff description:

- **Injection**: `KIT_CHECKPOINT_TEST_TIMEOUT` flows through `int()` (scripts/verify_gates.py:74-79) and only into the `timeout=` kwarg of `_run` → `subprocess.run` (scripts/verify_gates.py:349-355, 44-48). It never reaches argv or a shell string. `grep 'shell=True|os.system|eval(|exec('` over both changed scripts returns nothing. The only place the value is stringified is the `f"{prog}: timed out after {timeout}s"` stderr message — plain output, and by that point it is a plain int. No new subprocess call sites introduced.
- **Input validation**: probed empirically by executing `_test_timeout()` in the worktree — `""`, `"abc"`, `"0"`, `"-5"`, `"600.5"` all fall back to 600; `" 900 "`, `"+900"`, `"1_000"` parse as plain ints. Fail direction on bad input is fail-safe (default), never crash, never 0. The `timeout=0` → `None` ("no timeout") branch in `_run` (scripts/verify_gates.py:47) is unreachable via the env var since non-positive maps to the default — confirmed by TC-047c tests and by direct execution.
- **Denial / gate bypass**: no fail-open path. A tiny valid value (e.g. `1`) makes the unit gate time out → rc 124 → `status="fail"`, `blocking=True` (scripts/verify_gates.py:366) — fails closed. A huge value crashes or removes the hang bound (finding below) but can never convert a failing test run into a pass. Crash containment verified on both invocation paths: (a) CLI `main()` — unhandled exception → interpreter exit 1, which callers interpret as "blocking gate failed"; (b) in-process via `verify_checkpoint._run_verify_gates` (scripts/verify_checkpoint.py:868-872) — `except Exception` catches OverflowError and returns `not blocking`, i.e. FAIL when blocking=True. The blocking=False implement-phase path warns and continues, but in that mode gate failures are warnings by design, so nothing is bypassed that would otherwise block.
- **Secrets / dependencies / deserialization / XSS / misconfig**: nothing added or touched by this diff. No new dependencies.
- **Tests execute nothing real**: confirmed. `TestUnitGateTimeout` and `TestTimeoutContract.test_gate_fails_when_run_times_out` patch `vg._run`; `test_run_returns_rc_124_and_timed_out_stderr_on_timeout` patches global `subprocess.run` before calling the real `_run`, so no process spawns. Env mutation uses `monkeypatch` (auto-restored). The `test_verify_checkpoint.py` changes patch `_run_verify_gates`, which *removes* a pre-existing real-execution hazard (accidental recursive full-suite pytest spawn from the repo root) — a test-safety improvement, not a finding.

## Findings

```json
[
  {
    "severity": "Low",
    "title": "No upper bound on KIT_CHECKPOINT_TEST_TIMEOUT in verify_gates.py: values >= ~1e9 raise unhandled OverflowError inside subprocess.run (fails closed); large-but-valid values silently remove the unit gate's hang bound",
    "evidence": "scripts/verify_gates.py:79 `return value if value > 0 else _DEFAULT_TEST_TIMEOUT` — no upper clamp; scripts/verify_gates.py:49-60 — `_run` catches only TimeoutExpired and FileNotFoundError, so OverflowError propagates. Reproduced in the worktree: `vg._run([\"true\"], timeout=10**9)` -> `OverflowError: timeout is too large`; `10**12` -> `timestamp too large to convert to C _PyTime_t`. Containment verified fail-closed on both paths: CLI -> unhandled traceback -> exit 1 (blocking-failure semantics); in-process -> caught by `except Exception` at scripts/verify_checkpoint.py:870-872 -> checkpoint FAIL when blocking=True. Values just under the threshold (e.g. 1e8 s ~ 3 years) effectively disable the hang bound for the blocking unit gate. Requires local env control, no gate bypass, crash fails closed — hence Low.",
    "fix": "Clamp in _test_timeout(), e.g. `return min(value, 86400) if value > 0 else _DEFAULT_TEST_TIMEOUT` (optionally WARN when clamping), and apply the same clamp to the mirrored helper in verify_checkpoint.py (the '# keep in sync' comment makes this a single change done twice). Alternatively catch OverflowError alongside TimeoutExpired in _run, but the clamp is simpler and also restores a meaningful hang bound."
  }
]
```

## Self-review

- Severity re-checked: exploitation requires setting an env var on the developer's own machine/runner — anyone with that access can already run arbitrary code or skip the gate entirely; the crash fails closed and no input value can flip a failing gate to pass. Low is impact-honest; matches the ISSUE-046 precedent rating for the identical pattern.
- False-positive check: every claim was executed against the worktree code (parsing table, OverflowError at 1e9/1e12/1e20, harmless `true` command), and both crash-containment paths were read in source, not assumed from the ISSUE-046 report.
- Blind-spot re-scan (security dimension only): re-read the diff for shell usage, string-built commands, secrets, deserialization of the env value, new dependencies, and log injection via the rc-124 f-string (int by print time) — nothing found. Considered TOCTOU (env read once per gate at call time — fine) and tiny-timeout DoS (fails closed).
- AC check: env override, 600 default, invalid-value fallback, and fully mocked tests are all present in the diff; no acceptance criterion introduces a security regression.
- Confidence: High — small diff, the env value's full data flow was traced end to end and behavior verified empirically.
