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
try_mkdir() {
  local lockdir="${LOCKFILE}.d"
  local deadline=$((SECONDS + 30))

  while ! mkdir "$lockdir" 2>/dev/null; do
    if [ $SECONDS -ge $deadline ]; then
      echo "error: timed out waiting for lock on $TARGET" >&2
      exit 1
    fi
    sleep 0.1
  done

  # Ensure cleanup on exit
  trap 'rmdir "$lockdir" 2>/dev/null || true' EXIT

  "$@"
  local rc=$?

  rmdir "$lockdir" 2>/dev/null || true
  trap - EXIT
  return $rc
}

# --- main ---
if command -v flock >/dev/null 2>&1; then
  try_flock "$@"
else
  try_mkdir "$@"
fi
