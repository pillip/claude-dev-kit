# Security Review — PR #54 (ISSUE-046, degraded path)

Scope: `git diff main...HEAD` at 7476313 — scripts/verify_checkpoint.py (+49/-9), tests/test_verify_checkpoint.py (+311). Local/CI developer tooling, not user-facing.

## Verdict

Clean on every high-impact axis. Verified in the actual code, not just the diff description:

- **Injection**: `KIT_CHECKPOINT_TEST_TIMEOUT` flows through `int()` (scripts/verify_checkpoint.py:65-70) and only into the `timeout=` kwarg of `subprocess.run` (scripts/verify_checkpoint.py:38-39). It never reaches argv or a shell string. All call sites use static list-form argv; `grep shell=True` over the file returns nothing. No new subprocess call sites introduced.
- **Input validation**: probed empirically — empty, `"abc"`, `"-5"`, `"0"`, `"inf"`, `"4.5"`, unicode digits (`"٦٠٠"` → 600, harmless int), whitespace, underscores, and 5000-digit strings (Python 3.11 int-str limit raises ValueError → caught) all resolve safely to the default or a plain int. `timeout=0` ("disable" path in `_run`) is unreachable via the env var since non-positive maps to the default. One robustness gap remains (finding below).
- **Fail direction**: the one crash path found is fail-closed — an unhandled exception in the verifier fails the checkpoint; no gate-bypass path exists. The new returncode==124 branch also fails closed (`return False`).
- **Secrets / dependencies / deserialization / network / XSS / misconfig**: nothing added or touched by this diff.
- **DoS from raised defaults (60/120s → 600s)**: deliberate, documented tradeoff (suite runs ~4.5 min); a hung suite now occupies a runner up to 10 min, bounded in practice by CI job-level timeouts. Not a finding.

One Low-severity robustness finding; nothing blocking.

## Findings

```json
[
  {
    "severity": "Low",
    "title": "No upper bound on KIT_CHECKPOINT_TEST_TIMEOUT: values >= ~1e9 crash the verifier with unhandled OverflowError; large-but-valid values silently remove the hang bound",
    "evidence": "scripts/verify_checkpoint.py:70 `return value if value > 0 else _DEFAULT_TEST_TIMEOUT` — no upper clamp. Verified: KIT_CHECKPOINT_TEST_TIMEOUT=10**9 -> `OverflowError: timeout is too large` inside subprocess.run (uncaught by _run, which only handles TimeoutExpired/FileNotFoundError at scripts/verify_checkpoint.py:40-52); 10**6 works but effectively disables the timeout. Requires local env control, fails closed (crash = checkpoint failure), no gate bypass — hence Low, not Medium.",
    "fix": "Clamp in _test_timeout(), e.g. `return min(value, 86400) if value > 0 else _DEFAULT_TEST_TIMEOUT` (optionally print a WARN when clamping). Alternatively catch OverflowError alongside TimeoutExpired in _run, but the clamp is simpler and also restores a meaningful hang bound."
  }
]
```

## Self-review

- Severity re-checked: the crash needs env control on the developer's own machine/runner (anyone with that can already run arbitrary code) and fails closed — Low is impact-honest.
- False-positive check: both the OverflowError (10**9 and 10**18 variants) and the fail-back cases were reproduced by executing `_test_timeout()`/`_run()` directly, not inferred.
- Blind-spot re-scan: re-read the diff for shell usage, string-built commands, secrets, deserialization of the env value, and log injection via the f-string 124 messages (value is an int by print time) — nothing found.
- Confidence: High — small diff, every claim executed against the worktree code.
