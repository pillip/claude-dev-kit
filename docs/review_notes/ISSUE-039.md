# Review Notes — PR #63

## Code Review
_Source: reviewer-degraded_

- **[Low] Closed stdin fd still tracebacks (sys.stdin is None)**
  Evidence: project/.claude/hooks/secret_guard.py:54, project/.claude/hooks/dangerous_command_guard.py:44 — `python3 secret_guard.py 0<&-` raises `AttributeError: 'NoneType' object has no attribute 'read'`, rc=1. When fd 0 is closed at exec (not merely empty), CPython sets sys.stdin = None, so .read() raises before json.loads and outside the caught exception types. Not reachable under Claude Code's hook invocation (runtime always provides a stdin pipe; the `|| true` wrappers in hooks/hooks.json:62,71 mask the nonzero exit). AC1's empty-stdin case is handled; this is the adjacent absent-stdin case.
  Fix: `raw = sys.stdin.read() if sys.stdin is not None else ""` inside the try, or add AttributeError / OSError to the except tuple. One line per guard.

- **[Low] UnicodeDecodeError coverage is load-bearing but implicit and untested**
  Evidence: project/.claude/hooks/secret_guard.py:55, project/.claude/hooks/dangerous_command_guard.py:45 — `printf '\xff\xfe{"a":1}' | python3 secret_guard.py` yields the diagnostic with rc 0 only because UnicodeDecodeError subclasses ValueError. Nothing in the code says so, and no test exercises it: run_hook_raw uses text=True so it physically cannot send undecodable bytes. A future cleanup narrowing the except to json.JSONDecodeError alone would reintroduce a traceback on undecodable stdin and the suite would stay green.
  Fix: Append `# ValueError also covers UnicodeDecodeError (undecodable stdin)` to the except line, and optionally add one bytes-mode test per file (subprocess.run without text=True, input=b"\xff\xfe") asserting rc 0 + diagnostic.

- **[Low] run_hook_raw / run_hook subprocess calls have no timeout (assessed per recalled hard-coded-timeout lesson)**
  Evidence: tests/test_secret_guard.py:22-28, tests/test_dangerous_command_guard.py:22-28 (pre-existing run_hook:9-19 likewise) — subprocess.run([sys.executable, str(SCRIPT)], input=raw_stdin, capture_output=True, text=True) with no timeout=. Assessed against the ISSUE-046/047 timeout lesson: this seam is NOT the test-runner-spawning class that bit us. The child is a ~90-line script with no network, no recursion, and stdin fully delivered and closed by subprocess.run(input=); hang risk is negligible and the 39-test targeted run completes in 0.69s. Flagged only for completeness; the timeout-sentinel concern does not apply.
  Fix: Optional: timeout=10 on both helpers as cheap insurance against a future hook edit that blocks on input.

- **[Low] [debt] Debt-ledger no-trigger markers are pre-existing harvester self-matches, none from this PR**
  Evidence: Advisory debt checkpoint: total 14 markers, 3 no-trigger (scripts/debt_harvest.py:44 docstring example line; tests/test_debt_harvest.py:27,59 test-fixture strings), 1 malformed (tests/test_debt_harvest.py:35 fixture). All are the harvester's own documentation/fixture text matching its own pattern — known false-positive class already recorded in the ISSUE-047 review. This diff introduces zero KIT-DEBT markers.
  Fix: No action for this PR. Follow-up candidate: teach debt_harvest.py to skip its own source/tests or require the marker at comment position.

## Security Findings
_Source: reviewer-degraded_

_No findings._

## Over-Engineering

- **[Low] [shrink] run_hook can delegate to run_hook_raw in test_secret_guard.py**
  Evidence: tests/test_secret_guard.py:9 — run_hook's duplicated subprocess.run block.
  Fix: out = run_hook_raw(json.dumps(payload)).stdout.strip(); return json.loads(out) if out else None (~7 lines removable).

- **[Low] [shrink] run_hook can delegate to run_hook_raw in test_dangerous_command_guard.py**
  Evidence: tests/test_dangerous_command_guard.py:9 — same duplicated subprocess.run block.
  Fix: Same delegation of run_hook to run_hook_raw (~7 lines removable). Net removable across both files: ~14 lines. Deliberately NOT flagged: the duplicated footgun comment block (guards are standalone scripts with no import path) and the technically-redundant (JSONDecodeError, ValueError) tuple — its ValueError breadth is load-bearing per code finding 2; do not narrow it.
