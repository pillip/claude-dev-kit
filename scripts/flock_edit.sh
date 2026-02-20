#!/usr/bin/env bash
# flock_edit.sh — run a command while holding an exclusive lock on a file
# Usage:
#   bash scripts/flock_edit.sh <file> -- <command> [args...]
#
# Uses flock(1) if available, falls back to mkdir-based locking.
set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: bash scripts/flock_edit.sh <file> -- <command> [args...]" >&2
  exit 1
fi

TARGET="$1"
shift

if [ "$1" != "--" ]; then
  echo "error: expected '--' separator after file path" >&2
  exit 1
fi
shift

LOCKFILE="${TARGET}.lock"

# --- flock-based locking ---
try_flock() {
  (
    flock -x 200
    "$@"
  ) 200>"$LOCKFILE"
}

# --- mkdir-based fallback ---
# Stale lock threshold in seconds (process crashed without cleanup)
STALE_LOCK_SECONDS=120

try_mkdir() {
  local lockdir="${LOCKFILE}.d"
  local pidfile="${lockdir}/pid"
  local deadline=$((SECONDS + 30))

  while ! mkdir "$lockdir" 2>/dev/null; do
    # Check for stale lock: if the lock directory is older than threshold
    # or the PID that created it is no longer running, force-remove it
    if [ -f "$pidfile" ]; then
      local lock_pid
      lock_pid="$(cat "$pidfile" 2>/dev/null || echo "")"
      if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
        echo "warning: removing stale lock (pid $lock_pid no longer running)" >&2
        rm -rf "$lockdir"
        continue
      fi
    elif [ -d "$lockdir" ]; then
      # No pidfile but lockdir exists — check age
      local lock_age=0
      if stat -f %m "$lockdir" >/dev/null 2>&1; then
        # macOS stat
        lock_age=$(( $(date +%s) - $(stat -f %m "$lockdir") ))
      elif stat -c %Y "$lockdir" >/dev/null 2>&1; then
        # Linux stat
        lock_age=$(( $(date +%s) - $(stat -c %Y "$lockdir") ))
      fi
      if [ "$lock_age" -ge "$STALE_LOCK_SECONDS" ]; then
        echo "warning: removing stale lock (age ${lock_age}s >= ${STALE_LOCK_SECONDS}s)" >&2
        rm -rf "$lockdir"
        continue
      fi
    fi

    if [ $SECONDS -ge $deadline ]; then
      echo "error: timed out waiting for lock on $TARGET" >&2
      exit 1
    fi
    sleep 0.1
  done

  # Write PID for stale detection
  echo $$ > "$pidfile"

  # Ensure cleanup on exit (including signals)
  trap 'rm -rf "$lockdir" 2>/dev/null || true' EXIT INT TERM HUP

  "$@"
  local rc=$?

  rm -rf "$lockdir" 2>/dev/null || true
  trap - EXIT INT TERM HUP
  return $rc
}

# --- main ---
if command -v flock >/dev/null 2>&1; then
  try_flock "$@"
else
  try_mkdir "$@"
fi
