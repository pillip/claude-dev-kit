#!/usr/bin/env bash
# gate_server.sh — Server lifecycle wrapper for verify gates.
#
# Starts a server in the background, waits for a health endpoint,
# runs a test command, then cleans up the server process.
#
# Usage:
#   gate_server.sh --start-cmd CMD --health-url URL --test-cmd CMD \
#                  [--timeout SEC] [--cwd DIR]
#
# Exit codes:
#   Same as --test-cmd exit code on success
#   124 — health check timed out
#   125 — server failed to start
#   2   — usage error

set -euo pipefail

START_CMD=""
HEALTH_URL=""
TEST_CMD=""
TIMEOUT=30
CWD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-cmd) START_CMD="$2"; shift 2 ;;
    --health-url) HEALTH_URL="$2"; shift 2 ;;
    --test-cmd) TEST_CMD="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --cwd) CWD="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$START_CMD" || -z "$HEALTH_URL" || -z "$TEST_CMD" ]]; then
  echo "Error: --start-cmd, --health-url, and --test-cmd are required" >&2
  exit 2
fi

# Change to working directory if specified
if [[ -n "$CWD" ]]; then
  cd "$CWD"
fi

# Start server in its OWN process group, redirecting its I/O to /dev/null so it
# doesn't hold parent's pipes open (prevents subprocess.run() from hanging).
# `set -m` (job control) makes the background job a process-group leader whose
# PGID equals its PID, so cleanup can signal the whole group — reaping any
# children the server forks (portable across macOS bash 3.2 and Linux CI).
set -m
eval "$START_CMD" > /dev/null 2>&1 &
SERVER_PID=$!
set +m

# Ensure cleanup on any exit — signal the whole process GROUP so forked
# children are reaped, not just the leader PID. Kills are best-effort so a
# failing kill under `set -e` never overrides the intended exit code (the
# fix for the old trap clobbering `exit 125` with 1 on bash 3.2).
cleanup() {
  local rc=$?
  set +e
  # Graceful TERM to the group, then poll before escalating to KILL.
  kill -TERM "-$SERVER_PID" 2>/dev/null || true
  for _ in 1 2 3; do
    kill -0 "-$SERVER_PID" 2>/dev/null || break
    sleep 0.3
  done
  # Force kill any survivors in the group.
  kill -KILL "-$SERVER_PID" 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT

# Verify the server group is alive — probe the GROUP, not just the leader, so a
# daemonizing start-cmd (leader exits after forking a worker) is not
# misclassified as "exited immediately".
sleep 0.5
if ! kill -0 "-$SERVER_PID" 2>/dev/null; then
  echo "Error: Server process exited immediately" >&2
  exit 125
fi

# Health check polling
ELAPSED=0
INTERVAL=1
while [[ $ELAPSED -lt $TIMEOUT ]]; do
  if curl -sf --max-time 2 "$HEALTH_URL" > /dev/null 2>&1; then
    break
  fi
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

if [[ $ELAPSED -ge $TIMEOUT ]]; then
  echo "Error: Health check timed out after ${TIMEOUT}s (url: $HEALTH_URL)" >&2
  exit 124
fi

# Run test command and capture exit code
set +e
eval "$TEST_CMD"
TEST_EXIT=$?
set -e

exit $TEST_EXIT
