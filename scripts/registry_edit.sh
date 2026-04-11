#!/usr/bin/env bash
# registry_edit.sh — flock_edit.sh on a registry file rooted at the main repo
#
# Wraps the compound pattern from skills/implement and skills/ship:
#   ROOT="$(bash scripts/worktree.sh root)"
#   bash scripts/flock_edit.sh "$ROOT/<file>" -- <command> [args...]
#
# Usage:
#   bash scripts/registry_edit.sh issues.md -- bash -c '<update command>'
#   bash scripts/registry_edit.sh STATUS.md -- bash -c '<update command>'
#
# Resolves the main repo root internally so callers never need to build
# paths with command substitution.
set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: bash scripts/registry_edit.sh <file> -- <command> [args...]" >&2
  exit 1
fi

FILE="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(bash "$SCRIPT_DIR/worktree.sh" root)"

exec bash "$SCRIPT_DIR/flock_edit.sh" "$ROOT/$FILE" "$@"
