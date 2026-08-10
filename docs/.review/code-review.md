# Code Review — ISSUE-047 (PR #56, commit 8b7bbaa)

Dimension: code (degraded path — runtime /code-review not invocable) + minimality (folded in).
Reviewer confidence: High. Every finding below was empirically verified in the worktree; both
touched suites and the full suite are green (81 / 137 / 1154 passed).

## Verdict

**No blocking findings. Approve.** Three Low code findings and one Low minimality finding below —
all non-blocking suggestions.

**Scope absorption: ACCEPT.** The fedf95c isolation fix is (a) genuinely necessary and (b) minimal.

- (a) Necessary — recursion diagnosis independently confirmed by code trace + probes. At base
  c04b78b, `test_pass_when_pytest_succeeds` / `test_fallback_when_pytest_cov_missing` use
  `wt_path = str(tmp_path)`, which contains no `issue-001` slug. `_find_worktree_path`
  (scripts/verify_checkpoint.py:163-181) matches the slug regex against the *path string* from the
  mocked `git worktree list` output — probe confirmed `pat.search(tmp_style) → False` — so it
  returns None despite the mock, and `verify_implement_test` (scripts/verify_checkpoint.py:936-938)
  sets `wt = Path.cwd()` (real repo root). Both tests reach the `if ok:` gate block (mocked pytest
  returns rc 0), so `_run_verify_gates` (scripts/verify_checkpoint.py:855) imports verify_gates
  **in-process** and calls `run_applicable_gates` with the real `vg._run` (only `vc._run` was
  patched). `detect_platforms(repo root)` adds "unit" (tests/ dir exists — probe confirmed), so
  `run_gate_unit` spawns a real `python3 -m pytest -q --tb=short` over the full suite → recursion;
  `subprocess.run`'s timeout kill only reaches the direct child, orphaning grandchildren (the
  observed orphan storm). Consequence for THIS PR: raising the unit-gate default 120→600s makes the
  un-fixed suite cost ≥ 2×600s in these two tests alone (or fail outright for any timeout value on
  the blocking path, since the inner recursive suite necessarily exceeds any finite T). The
  mandatory full-suite test checkpoint could not reasonably pass without this fix.
- (b) Minimal — exactly the two recursing tests are touched; one `patch.object(vc,
  "_run_verify_gates", return_value=True)` context each, with `assert_called_once()` preserving the
  integration point (not a hollow bypass). The other two class tests were checked and do NOT need
  it: `test_fail_when_pytest_fails` short-circuits before the gate block (ok=False), and
  `test_runs_in_worktree_cwd`'s slugged tmp worktree has no test files, so `detect_platforms` never
  adds "unit" and only the cheap load-gate path runs (measured: all 4 class tests < 0.005s).
- Premise correction confirmed: full suite is 1154 passed in ~13s on this machine (claimed ~21s
  base — same order of magnitude, machine-dependent). The "~5-minute suite" premise was indeed an
  artifact of the recursion, not real suite cost.

## Verified with evidence

- **Exact semantic parity of the replicated `_test_timeout()`**: scripts/verify_gates.py:63-79 vs
  scripts/verify_checkpoint.py:58-73 — logic is byte-identical (only the cross-ref comment target
  differs). Runtime probe over 12 edge inputs (`""`, `"abc"`, `"0"`, `"-5"`, `"600"`, `"900"`,
  `" 900 "`, `"+900"`, `"9_00"`, `"12.5"`, `"1e3"`, Arabic-Indic `"٦٠٠"`): 12/12 PARITY. Notable
  shared int() semantics: whitespace/`+` sign/underscores/non-ASCII digits are accepted — identical
  in both, so "matching ISSUE-046 semantics exactly" (AC-2) holds by construction.
- **Both call sites converted, nothing else changed**: pytest branch (scripts/verify_gates.py:349-353)
  and npm branch (:355) both use `timeout=_test_timeout()`. `_run`'s module default `timeout: int = 120`
  (scripts/verify_gates.py:44) untouched; lint 15s / install 300s / docker 60s / e2e 300s /
  integration-collect 30s all untouched (diff contains no other timeout edits). rc-127
  FileNotFoundError path untouched.
- **verify_checkpoint.py delta is comment-only**: one `# keep in sync with
  verify_gates.py::_test_timeout` line (scripts/verify_checkpoint.py:65); the mirror comment exists
  in verify_gates.py:71 — the spec's keep-in-sync cross-references are present in both files.
- **Test coverage (12 new tests, TC-047a..d)**: TestUnitGateTimeout = 10 (override ×2 branches,
  unset-default ×2 branches, invalid `"abc"/"0"/"-5"` ×2 branches parametrized);
  TestTimeoutContract = 2. Assertions are non-hollow: `run_gate_unit` makes exactly one `_run` call
  per invocation (verified by reading :340-372 — no `_ensure_tool` in the unit gate), so
  `mock_run.call_args[1]["timeout"]` indexes the pytest/npm call and `timeout` is genuinely passed
  as a kwarg; npm tests additionally pin `call_args[0][0] == ["npm", "test"]`. Call-time (not
  import-time) env resolution is covered implicitly and correctly: `vg` is imported at collection,
  before `monkeypatch.setenv`, so a regression to module-level resolution would fail these tests.
  Unset tests use `delenv(raising=False)` — robust against a polluted dev environment.
- **_run timeout-mock contract (AC-3)**: TC-047d patches the real `subprocess.run` with
  `TimeoutExpired` and asserts rc 124 + exact stderr `"python3: timed out after 600s"`; a second
  test pins that rc 124 propagates to `status="fail", blocking=True`. Contract intact.
- **Suites**: `tests/test_verify_gates.py` 81 passed (2.0s); `tests/test_verify_checkpoint.py`
  137 passed (2.3s); full `tests/` 1154 passed (13.1s). Existing tests pass unchanged (AC-3).
- **AC-1** (blocking ship-smoke unit gate completes with new default): default is now 600s and the
  real root cause (recursion) is fixed; full suite at ~13s clears 600s with wide margin. Ship-smoke
  itself not runnable from this review context, but the mechanics are verified.

## Findings (code)

1. **[Low] KIT_CHECKPOINT_TEST_TIMEOUT now governs a second script but remains undocumented in any
   user-facing doc — and the "documented in docs/troubleshooting.md" premise is false.**
   Evidence: `git grep KIT_CHECKPOINT_TEST_TIMEOUT c04b78b -- '*.md'` and a worktree-wide grep
   both return only review-artifact files (docs/.review/, docs/review_notes/ISSUE-046.md);
   docs/troubleshooting.md contains zero mentions at base and at HEAD. ISSUE-046's review already
   carries an open Low for this; this PR broadens the knob's surface (verify_gates.py unit gate,
   incl. standalone CLI use) without a doc touch. Recalled lesson 2 applies.
   Fix: one line in each module docstring ("KIT_CHECKPOINT_TEST_TIMEOUT — test-phase subprocess
   timeout in seconds, default 600; shared by verify_checkpoint.py and verify_gates.py") plus a
   short docs/troubleshooting.md entry. Also worth noting there that the "CHECKPOINT" name now
   also covers the gates script (name reuse is per spec, so doc-only).

2. **[Low] Known unclamped upper bound is now replicated: huge values crash verify_gates and, in
   the checkpoint's non-blocking path, silently skip gates.**
   Evidence: probe in the worktree — `KIT_CHECKPOINT_TEST_TIMEOUT=1000000000` →
   `vg._test_timeout()` returns 1000000000 and `vg._run(["true"], timeout=...)` raises uncaught
   `OverflowError: timeout is too large` (vg._run at scripts/verify_gates.py:44-59 catches only
   TimeoutExpired/FileNotFoundError). Standalone `verify_gates.py` would crash (fail closed); via
   `_run_verify_gates`'s `except Exception` (scripts/verify_checkpoint.py:869-872) it degrades to
   WARN and returns True when blocking=False. Exact parity with ISSUE-046 semantics is mandated by
   AC-2, so inheriting this is by-design — filed as a tracking Low so the eventual clamp (already
   flagged in docs/review_notes/ISSUE-046.md) is applied to BOTH helpers; the keep-in-sync
   comments make that cheap. Local-env-only, no attack vector → Low.

3. **[Low] Comment-only sync guarantee: no test enforces parity between the two `_test_timeout`
   helpers.**
   Evidence: sync is guaranteed only by the cross-ref comments (scripts/verify_gates.py:71,
   scripts/verify_checkpoint.py:65); my 12-input parity probe passes today, but silent drift in
   either file would not fail any test. The spec chose comment-based sync, so this is a
   nice-to-have hardening, not a gap in the mandated work.
   Fix: a ~6-line parametrized test importing both modules and asserting
   `vg._test_timeout() == vc._test_timeout()` across the edge inputs ("", "abc", "0", "-5", "900").

## Findings (minimality)

- tests/test_verify_gates.py:322-380: shrink — 6 TestUnitGateTimeout methods are 3 near-identical
  pytest/npm pairs differing only in project setup → parametrize over branch (fixture writing
  pyproject.toml vs package.json) × env value; same 10 cases, ~35 fewer lines, per-case pytest ids
  preserved. Both branches stay covered, so AC-2 is unaffected.

Everything else is lean: the helper replication, constant, docstring, and cross-ref comments are
spec-mandated; the TC-047d pair guards AC-3 end-to-end and does not duplicate the existing rc-1
fail-path test.

Net removable lines: ~35 (report-only; do not apply during review).

## Self-Review

- Severity re-assessment: all four findings re-checked against impact — none blocks; the overflow
  finding stays Low per the same rationale ISSUE-046's audit used (local env control required,
  blocking path fails closed).
- False-positive check: one candidate finding was dropped after empirical disproof —
  `test_runs_in_worktree_cwd` does NOT spawn a real pytest (tmp worktree has no test files, so
  "unit" is never detected; class runtime < 5ms). Doc-gap and overflow findings were verified by
  grep and runtime probe rather than assumed.
- Blind-spot scan: re-checked error handling (127 path untouched), hollow-assertion risk
  (call_args indexing valid — single `_run` call in unit gate), import-time vs call-time env
  resolution (covered), and other-gate timeout drift (none in diff).
- AC verification: AC-1/2/3 each verified above with evidence.
- Confidence: High.
