#!/usr/bin/env bash
# wt_cleanup.sh — safely cd to repo root and remove a worktree
#
# Wraps the compound from skills/ship:
#   cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove <branch>
#
# Usage:
#   bash scripts/wt_cleanup.sh issue/123-foo
#
# The cd is performed inside this subshell so that the caller's shell
# does not need to change directory (important because Claude's Bash tool
# spawns a fresh shell per invocation anyway).
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/wt_cleanup.sh <branch>" >&2
  exit 1
fi

BRANCH="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Prefer ${CLAUDE_PLUGIN_ROOT} for locating sibling scripts; fall back to this
# script's directory (standalone). ISSUE-023.
KIT_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd -P)}"

ROOT="$(bash "$KIT_ROOT/scripts/worktree.sh" root)"
cd "$ROOT"
exec bash "$KIT_ROOT/scripts/worktree.sh" remove "$BRANCH"
