# Code Review — ISSUE-039 guard stdin hardening (PR #63)

Reviewer: degraded-path code reviewer (runtime `/code-review` not exposed).
Diff range: `e87bc38..cde204d`. All 39 tests pass (`uv run pytest tests/test_secret_guard.py tests/test_dangerous_command_guard.py -q` → 39 passed, 0.69s).

## AC verification

- **AC1 (malformed/empty stdin → exit 0, no traceback, stderr diagnostic): PASS.**
  Verified by tests (garbage / empty / truncated JSON) and empirically: `null`,
  `[1,2]`, `"str"`, `42`, `true`, invalid UTF-8 bytes (`\xff\xfe...`), and
  C-locale (`LC_ALL=C`) all produce the diagnostic + rc 0 with no traceback.
- **AC2 (valid Write secret payload blocks exactly as before, stderr clean): PASS.**
  `tests/test_secret_guard.py:198` asserts block JSON on stdout and `stderr == ""`;
  all 7 pre-existing detection tests unchanged and passing.
- **AC3 (valid Bash dangerous payload blocks as before): PASS.**
  `tests/test_dangerous_command_guard.py:158` plus 13 pre-existing blocking tests.
- **RED honesty verified:** the base-commit hook (`git show e87bc38:...`) tracebacks
  with rc=1 on garbage stdin, so the new tests genuinely failed before the fix and
  would fail again if the try/except, the diagnostic, or the exit-0 behavior regressed.
- **Recalled-lesson checks:** no new env-var knobs introduced (lesson 2 — n/a);
  subprocess children are the tiny hook scripts themselves — no recursion, no pytest
  spawn, no network, stdin fully written and closed by `subprocess.run(input=...)`,
  so they always terminate (lesson 3 — clean); guards read only stdin (lesson 4 —
  top-level gate in scope, field-level typing is GAP-039a, out of scope, boundary
  re-confirmed empirically: `{"tool_name": "Write", "tool_input": null}` still
  tracebacks, exactly as logged).

## Findings

### 1. Low — Closed stdin fd still tracebacks (`sys.stdin` is `None`)

- **File:** `project/.claude/hooks/secret_guard.py:54`, `project/.claude/hooks/dangerous_command_guard.py:44`
- **Evidence:** `python3 secret_guard.py 0<&-` →
  `AttributeError: 'NoneType' object has no attribute 'read'`, rc=1. When fd 0 is
  closed at exec (not merely empty), CPython sets `sys.stdin = None`, so the
  `.read()` call raises before `json.loads` and outside the caught exception types.
- **Impact:** Not reachable under Claude Code's hook invocation (the runtime always
  provides a stdin pipe, and the `|| true` wrappers in `hooks/hooks.json:62,71`
  mask the nonzero exit), but it is the one remaining stdin-acquisition crash in
  the hardened path. AC1's "empty stdin" (empty string) case is handled; this is
  the adjacent "absent stdin" case.
- **Fix:** `raw = sys.stdin.read() if sys.stdin is not None else ""` inside the
  try, or add `AttributeError` / `OSError` to the except tuple. One line per guard.

### 2. Low — UnicodeDecodeError coverage is load-bearing but implicit and untested

- **File:** `project/.claude/hooks/secret_guard.py:55`, `project/.claude/hooks/dangerous_command_guard.py:45`; tests `tests/test_secret_guard.py:22`, `tests/test_dangerous_command_guard.py:22`
- **Evidence:** `printf '\xff\xfe{"a":1}' | python3 secret_guard.py` → diagnostic,
  rc 0 — works only because `UnicodeDecodeError` is a subclass of `ValueError`.
  Nothing in the code says so, and no test exercises it: `run_hook_raw` uses
  `text=True` so it physically cannot send undecodable bytes.
- **Impact:** A future "cleanup" narrowing the except to `json.JSONDecodeError`
  alone would reintroduce a traceback on undecodable stdin, and the suite would
  stay green.
- **Fix:** Append `# ValueError also covers UnicodeDecodeError (undecodable stdin)`
  to the except line, and optionally add one bytes-mode test per file
  (`subprocess.run([...], input=b"\xff\xfe", capture_output=True)` without
  `text=True`) asserting rc 0 + diagnostic.

### 3. Low — `run_hook_raw` / `run_hook` subprocess calls have no `timeout` (assessed per recalled lesson 1)

- **File:** `tests/test_secret_guard.py:22-28`, `tests/test_dangerous_command_guard.py:22-28` (pre-existing `run_hook:9-19` likewise)
- **Evidence:** `subprocess.run([sys.executable, str(SCRIPT)], input=raw_stdin, capture_output=True, text=True)` — no `timeout=`.
- **Impact:** Assessed against the ISSUE-046/047 timeout lesson: this seam is NOT
  the test-runner-spawning class that bit us. The child is a ~90-line script with
  no network, no recursion, and stdin fully delivered and closed by
  `subprocess.run(input=)`; hang risk is negligible and the 39-test suite runs in
  0.69s. Flagged only for completeness; the sentinel-outcome concern does not apply.
- **Fix (optional):** `timeout=10` on both helpers as cheap insurance against a
  future hook edit that blocks on input.

## Minimality (over-engineering axis)

- `tests/test_secret_guard.py:9`: shrink — `run_hook`'s duplicated `subprocess.run` block → `out = run_hook_raw(json.dumps(payload)).stdout.strip(); return json.loads(out) if out else None` (~7 lines)
- `tests/test_dangerous_command_guard.py:9`: shrink — same delegation of `run_hook` to `run_hook_raw` (~7 lines)

Not flagged (deliberate, correct tradeoffs): the footgun comment block is duplicated
across both guards, but the guards are standalone scripts run from
`$CLAUDE_PLUGIN_ROOT` with no import path — a shared module would add a real seam
to remove a comment; `except (json.JSONDecodeError, ValueError)` is technically
redundant (subclass) but the breadth is load-bearing (finding 2) — do not narrow it.

**Net removable lines: ~14.**

## Self-Review

- Severity re-assessment: all findings Low — none has a practical trigger under
  real hook invocation; none blocks merge. No inflation, no suppression.
- False-positive check: findings 1 and 2 verified by direct execution; finding 3
  verified as a real absence and explicitly assessed as low-risk for this seam.
- Blind spot scan: probed non-dict JSON, undecodable bytes, C locale, closed fd,
  empty stdin, valid-path stderr cleanliness; re-read test assertions for honesty
  (each asserts rc, stdout emptiness, diagnostic substrings, and no "Traceback").
- AC verification: all 3 ACs pass (see above), RED→GREEN honesty confirmed against
  the base commit.
- Confidence: **High** — every claim in this review was verified empirically, not
  by inspection alone.

**Verdict: approve.** No blocking findings; the three Lows are follow-up polish.
