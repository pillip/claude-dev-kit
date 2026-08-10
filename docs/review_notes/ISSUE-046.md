# Review Notes — PR #54

## Code Review
_Source: reviewer-degraded_

- **[Low] GREEN/ship-smoke timeout failures hide the timeout cause — stderr is dropped**
  Evidence: scripts/verify_checkpoint.py:776-778 (also :770-772, :800-802, :955-958, :1593-1596): on exit 124, _run sets stdout="" and puts 'timed out after Ns' in stderr, but these failure paths print only 'FAIL: pytest failed (exit 124)' plus stdout[-500:], which is empty on timeout
  Fix: In the generic non-zero failure paths, also echo a tail of result.stderr, or special-case exit 124 with a one-line hint: '(exit 124 = timed out after {timeout}s; raise KIT_CHECKPOINT_TEST_TIMEOUT)'. In-scope-adjacent but non-blocking given the 600s default makes GREEN timeouts rare

- **[Low] KIT_CHECKPOINT_TEST_TIMEOUT is undocumented outside the helper docstring**
  Evidence: grep of *.md across the worktree: zero mentions of KIT_CHECKPOINT_TEST_TIMEOUT; precedent exists (KIT_SPRINT_MODE is documented in skills/spec/SKILL.md and skills/implement/SKILL.md); the verify_checkpoint.py module docstring (:1-10) documents exit codes but not this knob
  Fix: Add one line to the verify_checkpoint.py module docstring (and optionally skills/implement/SKILL.md): 'KIT_CHECKPOINT_TEST_TIMEOUT — test-phase subprocess timeout in seconds (default 600)'

- **[Low] Triplicated identical 124-check block in verify_implement_red; message does not name the runner**
  Evidence: scripts/verify_checkpoint.py:628-630, :640-642, :652-654 — three byte-identical print+return blocks; the npm-branch message is indistinguishable from the pytest-branch message
  Fix: Acceptable as-is: it mirrors the function's pre-existing per-branch early-return structure, and extraction saves ~2 net lines (rejected on minimality grounds). If this function is touched again, extract a shared `_red_timeout_check(result, timeout)` and include cmd[0] in the message

- **[Low] [pre-existing, out of scope — ISSUE-047] verify_gates.py run_gate_unit hard-codes timeout=120 on the full suite; observed during this review's test checkpoint**
  Evidence: Observed live in the review test-phase checkpoint output (exit 0, non-blocking here): 'PASS: tests passed' followed by 'GATE FAIL: unit [blocking] (120.1s) / python3: timed out after 120s'. This is scripts/verify_gates.py (separate file, NOT touched by PR #54) — the known pre-existing bug already filed as ISSUE-047 (P0, Depends-On: ISSUE-046). Not a regression from this PR.
  Fix: No action in this PR (scope discipline — issue Scope Out names verify_gates.py explicitly). ISSUE-047 fixes it. Known consequence: ISSUE-046's own SHIP smoke checkpoint is expected to fail on this until ISSUE-047 lands.

- **[Low] [debt] KIT-DEBT ledger has 3 no-trigger markers (silent-rot risk) — all harvester-self-referential, none from this PR**
  Evidence: review debt checkpoint harvest (advisory): scripts/debt_harvest.py:44 (module docstring format example), tests/test_debt_harvest.py:27 and :59 (deliberate no-trigger test fixtures); total 14 markers, 3 no-trigger, 1 malformed — none introduced or touched by PR #54
  Fix: Pre-existing and self-referential (harvester's own docs/tests): consider teaching debt_harvest.py to exclude its own docstring examples and test fixture strings from the ledger so real no-trigger debt stands out

## Security Findings
_Source: reviewer-degraded_

- **[Low] No upper bound on KIT_CHECKPOINT_TEST_TIMEOUT: values >= ~1e9 crash the verifier with unhandled OverflowError; large-but-valid values silently remove the hang bound**
  Evidence: scripts/verify_checkpoint.py:70 `return value if value > 0 else _DEFAULT_TEST_TIMEOUT` — no upper clamp. Verified: KIT_CHECKPOINT_TEST_TIMEOUT=10**9 -> `OverflowError: timeout is too large` inside subprocess.run (uncaught by _run, which only handles TimeoutExpired/FileNotFoundError at scripts/verify_checkpoint.py:40-52); 10**6 works but effectively disables the timeout. Requires local env control, fails closed (crash = checkpoint failure), no gate bypass — hence Low, not Medium.
  Fix: Clamp in _test_timeout(), e.g. `return min(value, 86400) if value > 0 else _DEFAULT_TEST_TIMEOUT` (optionally print a WARN when clamping). Alternatively catch OverflowError alongside TimeoutExpired in _run, but the clamp is simpler and also restores a meaningful hang bound.

## Over-Engineering

_No findings._
