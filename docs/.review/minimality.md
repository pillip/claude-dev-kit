# Minimality (over-engineering axis) — PR #70 / ISSUE-044

Reviewed the diff for unnecessary complexity only (correctness lives in
code-review.md).

- `gate_server.sh` process-group rewrite: every line earns its place —
  `set -m`/`set +m` scope job control to the launch; the 3x TERM poll before
  KILL is a minimal graceful window; `rc` capture + `exit "$rc"` is the exact
  mechanism preserving the 124/125/passthrough contract. Nothing speculative.
- `ci.yml`: a straight, lean uv migration; no redundant steps, no dead config.
- `pyproject.toml`/`uv.lock`: this change REMOVES config + a dependency
  (`asyncio_mode`, `pytest-asyncio`) — the opposite of over-building.
- Tests: the 7+5 TCs each exercise a DISTINCT guaranteed behavior
  (passthrough, immediate-exit 125, health-timeout 124, usage 2, forked-child
  reaping, daemonizing-leader probe, SIGTERM-immune escalation, no-swallow,
  uv-install, interpreter-consistency, asyncio-removal, config-warning). No
  redundant TC; test helpers (`read_pid`/`wait_dead`/`best_effort_kill`) are
  justified shared infra, not gold-plating. The verbose comments explain
  non-obvious process-group semantics and are worth their lines.

Lean already. Ship.
