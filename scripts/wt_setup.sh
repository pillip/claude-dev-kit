#!/usr/bin/env bash
# wt_setup.sh — create a worktree and initialize the auto-freeze marker
#
# Wraps the compound sequence from skills/implement:
#   WT="$(bash scripts/worktree.sh create <branch>)"
#   mkdir -p "$WT/.claude-kit" && echo "$WT" > "$WT/.claude-kit/freeze-dir.txt"
#
# Usage:
#   WT="$(bash scripts/wt_setup.sh issue/123-foo)"
#
# Prints the absolute worktree path to stdout so callers can capture it.
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/wt_setup.sh <branch>" >&2
  exit 1
fi

BRANCH="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Prefer ${CLAUDE_PLUGIN_ROOT} for locating sibling scripts; fall back to this
# script's directory (standalone). ISSUE-023.
KIT_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd -P)}"

WT="$(bash "$KIT_ROOT/scripts/worktree.sh" create "$BRANCH")"

# Fallback freeze-marker write. On builds that fire the `WorktreeCreate` hook
# (see project/.claude/hooks/worktree_freeze.py) this is redundant but idempotent;
# on builds without that event it is the only path that writes the marker. Kept
# deliberately so worktree freezing never regresses (ISSUE-016).
mkdir -p "$WT/.claude-kit"
printf '%s\n' "$WT" > "$WT/.claude-kit/freeze-dir.txt"

printf '%s\n' "$WT"
