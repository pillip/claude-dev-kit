# Security Review — PR #70 / ISSUE-044 (degraded-path, dimension: security)

Checklist run: injection, authz, secrets, input validation, deserialization,
dependency CVEs, XSS (n/a — no user-facing output), misconfiguration.

## Findings

### Low — `eval` of operator-supplied start/test commands (pre-existing trust boundary, not widened)
- **file:line**: `scripts/gate_server.sh:52` (`eval "$START_CMD" ...`),
  `scripts/gate_server.sh:102` (`eval "$TEST_CMD"`)
- **what**: Both `--start-cmd` and `--test-cmd` are executed via `eval`, i.e.
  arbitrary shell execution. This is pre-existing and by design: `gate_server.sh`
  is a gate harness whose commands come from trusted kit config
  (`verify_gates.py:325,328` passes `config["server_start_cmd"]` and the gate's
  own `test_cmd`), not from external/untrusted request data.
- **why**: No exploit path within the kit's trust model (an attacker who can set
  `server_start_cmd` already controls the CI config / repo). This PR does **not**
  widen the surface: the new cleanup logic only interpolates the numeric
  `$SERVER_PID` into `kill -TERM "-$SERVER_PID"` etc. `$SERVER_PID` is
  `set -u`-guarded and can never be empty at trap time (trap registered at
  line 73, after the assignment at line 53), so the "empty var → `kill -TERM -`
  wipes the caller's own process group" failure mode is unreachable.
- **fix**: No change required for this PR. Keep `--start-cmd`/`--test-cmd`
  sourced only from trusted config; if the harness is ever exposed to
  externally-influenced input, replace `eval` with an argv array
  (`bash -c "$CMD"` is no safer; prefer structured `exec "$@"`).

## Assessment summary (no other findings)

- ci.yml migration to `astral-sh/setup-uv@v5` + `uv sync --locked` removes the
  `pip install -e ".[dev]" 2>/dev/null || true` failure-swallow — a security/
  supply-chain improvement (installs now fail loudly and are pinned by
  `--locked`). `enable-cache: true` caches the uv package cache, not secrets.
- No hardcoded secrets, credentials, or tokens introduced.
- No new deserialization; `tomllib.load` (stdlib) and text reads only. The two
  yaml-importing tests use `yaml.safe_load` (safe loader), unchanged by this PR.
- No new/changed dependencies with known CVEs introduced; net change is the
  REMOVAL of `pytest-asyncio` (fewer deps).
- Negative-PID `kill` reviewed for injection/priv escalation: numeric-only
  interpolation, `set -u`-guarded, no shell metacharacters — no injection.
