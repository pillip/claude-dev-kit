#!/usr/bin/env bash
# worktree.sh — git worktree lifecycle manager
# Usage:
#   bash scripts/worktree.sh create <branch>   # create worktree, print path
#   bash scripts/worktree.sh path   <branch>   # print existing worktree path
#   bash scripts/worktree.sh remove <branch>   # remove worktree + branch
#   bash scripts/worktree.sh root              # print main repo root
set -euo pipefail

WORKTREE_DIR=".worktrees"

# Convert branch name to filesystem-safe slug
# e.g. issue/ISSUE-001-login → issue-ISSUE-001-login
# Replaces / and other filesystem-unsafe characters with -
slug() {
  echo "$1" | tr '/\\*?[]:<>|'"'"'"' '-'
}

# Get the main repo root (the original working tree, not a worktree)
repo_root() {
  local root
  root="$(git rev-parse --show-toplevel)"
  # If we're inside a worktree, follow the commondir link
  local gitdir
  gitdir="$(git rev-parse --git-dir)"
  if [ -f "$gitdir/commondir" ]; then
    local commondir
    commondir="$(cat "$gitdir/commondir")"
    if [[ "$commondir" != /* ]]; then
      commondir="$gitdir/$commondir"
    fi
    # commondir points to the .git dir of the main repo
    root="$(cd "$commondir/.." && pwd)"
  fi
  echo "$root"
}

cmd_create() {
  local branch="$1"
  local s
  s="$(slug "$branch")"
  local root
  root="$(repo_root)"
  local wt_path="$root/$WORKTREE_DIR/$s"

  if [ -d "$wt_path" ]; then
    echo "$wt_path"
    return 0
  fi

  mkdir -p "$root/$WORKTREE_DIR"

  # Create the branch from the default branch if it doesn't exist
  if ! git show-ref --verify --quiet "refs/heads/$branch"; then
    local default_branch
    default_branch="$(git symbolic-ref --short HEAD 2>/dev/null || echo main)"
    git branch "$branch" "$default_branch"
  fi

  git worktree add "$wt_path" "$branch" --quiet
  echo "$wt_path"
}

cmd_path() {
  local branch="$1"
  local s
  s="$(slug "$branch")"
  local root
  root="$(repo_root)"
  local wt_path="$root/$WORKTREE_DIR/$s"

  if [ -d "$wt_path" ]; then
    echo "$wt_path"
  else
    echo "error: worktree not found for branch '$branch'" >&2
    return 1
  fi
}

cmd_remove() {
  local branch="$1"
  local s
  s="$(slug "$branch")"
  local root
  root="$(repo_root)"
  local wt_path="$root/$WORKTREE_DIR/$s"

  # If CWD is inside the worktree being removed, cd to repo root first
  local cwd
  cwd="$(pwd -P)"
  local real_wt
  real_wt="$(cd "$wt_path" 2>/dev/null && pwd -P || echo "")"
  if [ -n "$real_wt" ] && [[ "$cwd" == "$real_wt"* ]]; then
    cd "$root"
  fi

  if [ -d "$wt_path" ]; then
    if ! git worktree remove "$wt_path" --force 2>&1; then
      echo "warning: failed to remove worktree at $wt_path, cleaning up manually" >&2
      rm -rf "$wt_path"
      git worktree prune 2>/dev/null || true
    fi
  fi

  # Clean up the branch (local only)
  if git show-ref --verify --quiet "refs/heads/$branch"; then
    git branch -D "$branch" >/dev/null 2>&1 || true
  fi

  # Print repo root so callers can update their CWD
  echo "$root"
}

cmd_root() {
  repo_root
}

# --- main ---
if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/worktree.sh {create|path|remove|root} [branch]" >&2
  exit 1
fi

CMD="$1"
shift

case "$CMD" in
  create)
    [ $# -ge 1 ] || { echo "error: create requires <branch>" >&2; exit 1; }
    cmd_create "$1"
    ;;
  path)
    [ $# -ge 1 ] || { echo "error: path requires <branch>" >&2; exit 1; }
    cmd_path "$1"
    ;;
  remove)
    [ $# -ge 1 ] || { echo "error: remove requires <branch>" >&2; exit 1; }
    cmd_remove "$1"
    ;;
  root)
    cmd_root
    ;;
  *)
    echo "error: unknown command '$CMD'" >&2
    exit 1
    ;;
esac
