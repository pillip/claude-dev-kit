# Code Review — PR #70 / ISSUE-044 (degraded-path, dimension: code)

Scope: `scripts/gate_server.sh`, `.github/workflows/ci.yml`, `pyproject.toml`,
`tests/test_gate_server.py`, `tests/test_ci_workflow.py`.

## Verification performed (positive results — not findings)

- `set -m` process-group isolation confirmed empirically on this host (bash
  3.2.57, macOS 26.2, no tty): a backgrounded job gets `PGID == PID` distinct
  from the script's own PGID (observed `40481==40481` vs script pgid `40478`).
  So `kill -TERM "-$SERVER_PID"` targets ONLY the server group, never the
  script's or pytest's group — no wrong-kill risk.
- Fallback safety: if `set -m` ever failed to make the child a group leader,
  `$SERVER_PID` (a freshly-allocated child PID) is not the PGID of any existing
  group, so `kill -- -$SERVER_PID` returns ESRCH and is swallowed by `|| true`.
  Failure mode is **leak, not wrong-kill** — the safe direction.
- 125 immediate-exit probe confirmed: with `bash -c 'exit 1'` as start-cmd the
  group is gone by the 0.5s probe (`kill -0 -PGID` → ESRCH → `exit 125`). No
  zombie-leader false-positive on this host; matches the 12-passed suite + both
  green CI matrix jobs (Linux 3.11/3.12).
- `local rc=$?` correctly captures the pending exit status (no command-
  substitution masking gotcha), and `exit "$rc"` inside the EXIT trap does not
  re-enter the trap — 124/125/passthrough(0,7) contract is preserved.
- `SERVER_PID` can never be empty when `cleanup` runs: it is assigned from `$!`
  at line 53 and the `trap cleanup EXIT` is registered later at line 73, so an
  early usage-error `exit 2` (line 38) fires before any trap exists. Combined
  with `set -u`, no `kill -TERM -` group-wipe is reachable.
- Removing `asyncio_mode`/`pytest-asyncio` is safe: repo-wide grep finds no
  `async def` / `await` / `@pytest.mark.asyncio`; lock has no asyncio residue;
  `uv.lock` carries `pytest-cov` and `pyyaml` under `extra == 'dev'`, so
  `uv sync --locked --extra dev` + `uv run pytest --cov` resolves cleanly and
  `--locked` fails loudly on a stale lock.

## Findings

### Low — Misleading rationale comment in `test_ci_workflow.py`
- **file:line**: `tests/test_ci_workflow.py:2-4` (module docstring)
- **what**: The docstring states "Reads ci.yml as plain text (no yaml import —
  the uv venv has no pyyaml)". This is factually wrong: `pyyaml>=6.0` is in the
  `dev` extra (`pyproject.toml:15`, `uv.lock:277`), so the dev venv used by
  `uv run pytest` DOES have pyyaml — indeed the full CI suite runs
  `tests/test_skill_frontmatter_yaml.py` and `tests/test_plugin_manifest.py`,
  which both `import yaml`, and CI is green.
- **why**: A false statement about the environment can mislead a future
  maintainer into thinking pyyaml is unavailable (e.g. into refactoring other
  tests around a non-existent constraint). The choice to read ci.yml as text is
  itself fine and robust; only the stated reason is wrong.
- **fix**: Reword to the real rationale, e.g. "Reads ci.yml as plain text to
  avoid a yaml dependency for a trivial substring assertion" — drop the false
  "the uv venv has no pyyaml" clause.

### Low — Cleanup trap covers only EXIT, not INT/TERM (partial orphan gap vs AC)
- **file:line**: `scripts/gate_server.sh:73` (`trap cleanup EXIT`)
- **what**: Only the EXIT pseudo-signal is trapped. If the wrapper process is
  cancelled by SIGINT/SIGTERM (operator Ctrl-C, or a CI job cancel), bash does
  not run the EXIT trap, so `cleanup` never fires and the entire server process
  group is left orphaned — the precise "no orphaned forked children" outcome
  ISSUE-044 targets, for the signal-termination path. Note the caller
  `verify_gates.py:335` wraps this in `subprocess.run(..., timeout=120)`, whose
  timeout sends SIGKILL to the bash child; SIGKILL is untrappable, so that
  specific path would also leak the group regardless.
- **why**: Real (if narrow) leak path against the issue's stated guarantee.
  It is pre-existing (the old code also trapped only EXIT), so it is not a
  regression and stays Low, but it is in-scope for the AC.
- **fix**: `trap cleanup INT TERM EXIT` — `cleanup` already re-`exit "$rc"`s
  idempotently and is safe to run once on the signal path. The SIGKILL-on-
  timeout case is unfixable in-script; if that leak matters, have
  `verify_gates._run_with_server` launch bash in its own group and kill the
  group on `TimeoutExpired`. (Optional; do not block merge on it.)

## Test-quality assessment (per recalled Lesson 3 — not findings)

- Tests are genuine, not hollow: TC-044a/e/f/g fork REAL children, record their
  PIDs to files, and assert `wait_dead(pid)` on both the leader and the
  forked child/worker after gate exit. Exit-code contract is asserted directly
  (0, 7, 124, 125, 2).
- TC-044l is a BOUNDED `pytest --collect-only -q -p no:cacheprovider` of a
  SINGLE file — not the recursive full-suite anti-pattern. `timeout=60/120`
  harness caps are generous relative to the ~1-6s operations they guard →
  out-of-class per Lesson 1, no finding.
