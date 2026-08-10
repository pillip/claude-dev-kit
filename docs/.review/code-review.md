# Code Review — ISSUE-046 (PR #54, commit 7476313)

Dimension: code (degraded path — runtime /code-review not invocable) + minimality (folded in).
Reviewer confidence: High. All 137 tests in tests/test_verify_checkpoint.py pass (4:04 wall);
the 17 new ISSUE-046 tests run fully mocked in 6.3s with no real child processes or sleeps.

## Verdict

**No blocking findings. Approve.** Three Low, non-blocking findings below.

**Scope absorption: ACCEPT.** The two absorbed High findings (verify_ship_smoke timeout=120 at
scripts/verify_checkpoint.py:1592/1601, verify_implement_test no-runner fallback timeout=60 at
:954) are one-line conversions through the exact `_test_timeout()` seam this issue creates, were
done tests-first (TC-046f/g, commit 5962166 precedes 7476313), and are trivially revertible.
Leaving ship-smoke at 120s would deterministically fail this PR's own SHIP phase — the test file
alone takes ~244s. This is the minimal correct change set, not scope creep; splitting it out
would add process overhead to re-touch the same seam.

## Verified (with evidence)

1. **`_run()` contract preserved** — the diff does not touch `_run`; TimeoutExpired → 124
   sentinel intact at scripts/verify_checkpoint.py:40-45. AC5's `test_timeout_returns_124`
   (tests/test_verify_checkpoint.py:1096) is unchanged and passes.
2. **RED-gate ordering correct in all three branches** — the `returncode == 124` check precedes
   the `== 0` check and the non-zero → PASS fall-through in npm (:628-630), pytest (:640-642),
   and fallback pytest (:652-654), each printing a "timed out … inconclusive" FAIL.
3. **`_test_timeout()` (:58-70)** — reads env at call time; probed empirically: `""`, `"  "`,
   `"abc"`, `"45.5"`, `"-5"`, `"0"`, `"1e6"` → 600; `"  45  "`, `"+45"` → 45; unset → 600.
   Matches the documented contract exactly; cannot raise (str input, ValueError caught).
4. **All test-phase call sites converted** — cov run (:753-761) + pytest-cov fallback (:768),
   RED ×3 (:627/:639/:651), JS worktree (:798), implement-test fallback (:954), ship-smoke
   pytest (:1592) + npm (:1601). Full `grep timeout=` audit: every remaining hard-coded timeout
   is non-test-phase (visual diff :338/:1254, computed styles :1298, layout :1342, structural
   :1387, figma compliance :1436, debt :1467) or explicitly out of scope (deps install
   :916/:923/:925). verify_gates.py is ISSUE-047 — not flagged.
5. **Test quality** — mock side-effects are faithful to the real flows: `_red_side_effect`'s
   `git worktree` porcelain stub satisfies `_find_worktree_path` (:162-180, slug-boundary match
   on "issue-001-slug"); `_has_real_tests` (:472) and `_detect_test_runners` (:807) operate on
   real tmp files written by `_make_red_worktree`; `_default_branch` is patched (necessary — the
   real impl would return "" under the stub); TC-046f/g patch targets (`_run_verify_gates` :854)
   exist and match the real call sequence. All behavioral asserts; no hollow tests. TC-046a is
   the first direct coverage of `_run_python_tests_with_coverage` — not duplicate coverage.
6. **AC coverage** — AC1: suite passes in 244s < 600s (live-run claim consistent); AC2:
   `test_red_gate_timeout_124_fails_inconclusive`; AC3: `test_red_gate_genuine_failure_exit_1_passes`;
   AC4: TC-046c/d (mocked, both override and >= 600 default); AC5: passes unchanged.

## Findings

```json
[
  {
    "severity": "Low",
    "title": "GREEN/ship-smoke timeout failures hide the timeout cause — stderr is dropped",
    "evidence": "scripts/verify_checkpoint.py:776-778 (also :770-772, :800-802, :955-958, :1593-1596): on exit 124, _run sets stdout=\"\" and puts 'timed out after Ns' in stderr, but these failure paths print only 'FAIL: pytest failed (exit 124)' plus stdout[-500:], which is empty on timeout",
    "fix": "In the generic non-zero failure paths, also echo a tail of result.stderr, or special-case exit 124 with a one-line hint: '(exit 124 = timed out after {timeout}s; raise KIT_CHECKPOINT_TEST_TIMEOUT)'. In-scope-adjacent but non-blocking given the 600s default makes GREEN timeouts rare"
  },
  {
    "severity": "Low",
    "title": "KIT_CHECKPOINT_TEST_TIMEOUT is undocumented outside the helper docstring",
    "evidence": "grep of *.md across the worktree: zero mentions of KIT_CHECKPOINT_TEST_TIMEOUT; precedent exists (KIT_SPRINT_MODE is documented in skills/spec/SKILL.md and skills/implement/SKILL.md); the verify_checkpoint.py module docstring (:1-10) documents exit codes but not this knob",
    "fix": "Add one line to the verify_checkpoint.py module docstring (and optionally skills/implement/SKILL.md): 'KIT_CHECKPOINT_TEST_TIMEOUT — test-phase subprocess timeout in seconds (default 600)'"
  },
  {
    "severity": "Low",
    "title": "Triplicated identical 124-check block in verify_implement_red; message does not name the runner",
    "evidence": "scripts/verify_checkpoint.py:628-630, :640-642, :652-654 — three byte-identical print+return blocks; the npm-branch message is indistinguishable from the pytest-branch message",
    "fix": "Acceptable as-is: it mirrors the function's pre-existing per-branch early-return structure, and extraction saves ~2 net lines (rejected on minimality grounds). If this function is touched again, extract a shared `_red_timeout_check(result, timeout)` and include cmd[0] in the message"
  }
]
```

## Minimality

Weighed and rejected: extracting the RED 124 triplication (3 call sites, ~2 net lines saved —
below threshold, and the surrounding ==0/PASS blocks are already per-branch); the redundant
double-assert `>= 600` + `== _DEFAULT_TEST_TIMEOUT` in TC-046d (3 lines, deliberately encodes
AC4's ">= 600" plus the exact default — contract pinning, not bloat). `_test_timeout()` has 9
call sites — not yagni. No dead code, no stdlib reinvention, no speculative config.

```json
[]
```

Lean already. Ship.
