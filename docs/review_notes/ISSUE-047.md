# Review Notes — PR #56

## Code Review
_Source: reviewer-degraded_

- **[Low] KIT_CHECKPOINT_TEST_TIMEOUT now governs a second script but remains undocumented in any user-facing doc — and the "documented in docs/troubleshooting.md" premise is false**
  Evidence: `git grep KIT_CHECKPOINT_TEST_TIMEOUT c04b78b -- '*.md'` and a worktree-wide grep both return only review-artifact files (docs/.review/, docs/review_notes/ISSUE-046.md); docs/troubleshooting.md contains zero mentions at base and at HEAD. ISSUE-046's review already carries an open Low for this; this PR broadens the knob's surface (verify_gates.py unit gate, incl. standalone CLI use) without a doc touch. Recalled lesson 2 applies.
  Fix: One line in each module docstring ("KIT_CHECKPOINT_TEST_TIMEOUT — test-phase subprocess timeout in seconds, default 600; shared by verify_checkpoint.py and verify_gates.py") plus a short docs/troubleshooting.md entry. Also worth noting there that the "CHECKPOINT" name now also covers the gates script (name reuse is per spec, so doc-only).

- **[Low] Known unclamped upper bound is now replicated: huge values crash verify_gates and, in the checkpoint's non-blocking path, silently skip gates**
  Evidence: Probe in the worktree — KIT_CHECKPOINT_TEST_TIMEOUT=1000000000 → vg._test_timeout() returns 1000000000 and vg._run(["true"], timeout=...) raises uncaught OverflowError: timeout is too large (vg._run at scripts/verify_gates.py:44-59 catches only TimeoutExpired/FileNotFoundError). Standalone verify_gates.py would crash (fail closed); via _run_verify_gates's except Exception (scripts/verify_checkpoint.py:869-872) it degrades to WARN and returns True when blocking=False. Exact parity with ISSUE-046 semantics is mandated by AC-2, so inheriting this is by-design — filed as a tracking Low so the eventual clamp (already flagged in docs/review_notes/ISSUE-046.md) is applied to BOTH helpers; the keep-in-sync comments make that cheap. Local-env-only, no attack vector → Low.
  Fix: Tracking note: when ISSUE-046's open Low (upper clamp) is addressed, apply it to BOTH _test_timeout helpers — the keep-in-sync comments make this a paired one-line change.

- **[Low] Comment-only sync guarantee: no test enforces parity between the two _test_timeout helpers**
  Evidence: Sync is guaranteed only by the cross-ref comments (scripts/verify_gates.py:71, scripts/verify_checkpoint.py:65); my 12-input parity probe passes today, but silent drift in either file would not fail any test. The spec chose comment-based sync, so this is a nice-to-have hardening, not a gap in the mandated work.
  Fix: A ~6-line parametrized test importing both modules and asserting vg._test_timeout() == vc._test_timeout() across the edge inputs ("", "abc", "0", "-5", "900").

- **[Low] [debt] KIT-DEBT ledger has 3 no-trigger markers (silent-rot risk) — all harvester self-references, none introduced by this PR**
  Evidence: checkpoint.sh --skill review --phase debt --issue ISSUE-047: total 14 markers, 3 no-trigger (scripts/debt_harvest.py:44 docstring format example; tests/test_debt_harvest.py:27 and :59 deliberate no-trigger test fixtures), 1 malformed (tests/test_debt_harvest.py:35 deliberate fixture). Identical state to the ISSUE-046 review's ledger — pre-existing, not from this diff.
  Fix: No action in this PR. If the harvester grows an ignore-mechanism for its own fixtures/docstring examples, these false positives disappear from the ledger.

## Security Findings
_Source: reviewer-degraded_

- **[Low] No upper bound on KIT_CHECKPOINT_TEST_TIMEOUT in verify_gates.py: values >= ~1e9 raise unhandled OverflowError inside subprocess.run (fails closed); large-but-valid values silently remove the unit gate's hang bound**
  Evidence: scripts/verify_gates.py:79 `return value if value > 0 else _DEFAULT_TEST_TIMEOUT` — no upper clamp; scripts/verify_gates.py:49-60 — `_run` catches only TimeoutExpired and FileNotFoundError, so OverflowError propagates. Reproduced in the worktree: `vg._run(["true"], timeout=10**9)` -> `OverflowError: timeout is too large`; `10**12` -> `timestamp too large to convert to C _PyTime_t`. Containment verified fail-closed on both paths: CLI -> unhandled traceback -> exit 1 (blocking-failure semantics); in-process -> caught by `except Exception` at scripts/verify_checkpoint.py:870-872 -> checkpoint FAIL when blocking=True. Values just under the threshold (e.g. 1e8 s ~ 3 years) effectively disable the hang bound for the blocking unit gate. Requires local env control, no gate bypass, crash fails closed — hence Low.
  Fix: Clamp in _test_timeout(), e.g. `return min(value, 86400) if value > 0 else _DEFAULT_TEST_TIMEOUT` (optionally WARN when clamping), and apply the same clamp to the mirrored helper in verify_checkpoint.py (the '# keep in sync' comment makes this a single change done twice). Alternatively catch OverflowError alongside TimeoutExpired in _run, but the clamp is simpler and also restores a meaningful hang bound.

## Over-Engineering

- **[Low] [shrink] TestUnitGateTimeout's 6 methods are 3 near-identical pytest/npm pairs — parametrize over branch**
  Evidence: tests/test_verify_gates.py:322-380: shrink — 6 TestUnitGateTimeout methods are 3 near-identical pytest/npm pairs differing only in project setup → parametrize over branch (fixture writing pyproject.toml vs package.json) × env value
  Fix: Parametrize; same 10 cases, ~35 fewer lines, per-case pytest ids preserved. Both branches stay covered, so AC-2 is unaffected. Net removable lines: ~35 (report-only).
