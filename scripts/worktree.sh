#!/usr/bin/env bash
# worktree.sh — git worktree lifecycle manager
# Usage:
#   bash scripts/worktree.sh create <branch>   # create worktree, print path
#   bash scripts/worktree.sh path   <branch>   # print existing worktree path
#   bash scripts/worktree.sh remove <branch>   # remove worktree + branch
#   bash scripts/worktree.sh root              # print main repo root
#
# Branch resolution for `create` (ISSUE-083)
# ------------------------------------------
# Resolution order:  refs/heads/<branch>  ->  refs/remotes/origin/<branch>  ->  base
#
#   Before ISSUE-083 only `refs/heads/<branch>` was consulted, so re-creating a
#   worktree for a branch whose LOCAL ref had been deleted (which `remove`
#   below does unconditionally on every review-phase cleanup) but which still
#   existed on the remote carrying the reviewed commits silently re-rooted it
#   onto the caller's current HEAD, with no upstream, while reporting success.
#
# DIVERGENCE RESOLUTION — the LOCAL ref always wins. When both
#   `refs/heads/<branch>` and `refs/remotes/origin/<branch>` exist at different
#   shas, the worktree is created from the LOCAL ref and the divergence is
#   named on stderr with both short shas and which side is ahead. The remote is
#   never force-applied over a local ref: that would discard unpushed local
#   commits, which is a strictly worse failure than the one this fix removes.
#   Resolve it by hand (`git merge`, `git rebase`, or `git reset --hard`) after
#   reading the warning.
#
# FETCH DECISION — a `git fetch` runs on EXACTLY ONE path: when the branch is
#   remote-only (no local ref, a remote-tracking ref present). There the cached
#   `refs/remotes/origin/<branch>` is not trusted as the tip: the remote is
#   consulted live (`git ls-remote`, then a single-branch fetch) so the worktree
#   starts at the true remote tip. No fetch runs when a local ref exists or when
#   the branch is genuinely new, so `create` stays offline on those paths. The
#   consequence is named in output: the divergence warning states that the
#   origin side it compared against is the CACHED remote-tracking ref and may be
#   stale.
#
# FAIL-CLOSED — when the branch is remote-only but its tip cannot be established
#   (origin unreachable, no remote named `origin`, the branch gone from the
#   remote, or the consultation timing out), `create` refuses: non-zero exit, a
#   named `reason=` on stderr, no local branch created, no worktree directory,
#   and NOTHING on stdout, so a caller doing `WT="$(... create <branch>)"`
#   cannot proceed into a silently re-rooted tree.
#
# COUNTER-EVIDENCE — every successful resolution names its source on stderr
#   (`source=local-ref` / `source=remote-tip` / `source=new-from-base`). The
#   healthy and the defeated outputs were otherwise byte-identical, which is
#   what let the defect live undetected for the whole life of this script.
#
# Environment
# -----------
#   KIT_WORKTREE_FETCH_TIMEOUT — wall-clock seconds allowed for EACH remote
#     consultation on the remote-only create path (`git ls-remote`, then
#     `git fetch`). Default 60; invalid or non-positive values fall back to the
#     default. A timeout is reported as its own `reason=remote-fetch-timeout`
#     refusal rather than being folded into "unreachable", because an offline
#     remote stalls rather than failing fast. Requires `timeout` (or
#     `gtimeout`); where neither exists the consultation runs unbounded and
#     says so on stderr.
set -euo pipefail

WORKTREE_DIR=".worktrees"

# Default wall-clock bound for a single remote consultation, in seconds.
DEFAULT_REMOTE_TIMEOUT=60

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

# Seconds allowed for one remote consultation. Honours
# KIT_WORKTREE_FETCH_TIMEOUT; anything that is not a positive number falls back
# to the default (same convention as KIT_CHECKPOINT_TEST_TIMEOUT).
remote_timeout() {
  local v="${KIT_WORKTREE_FETCH_TIMEOUT:-}"
  if [ -n "$v" ] \
     && printf '%s' "$v" | grep -Eq '^[0-9]+(\.[0-9]+)?$' \
     && ! printf '%s' "$v" | grep -Eq '^0+(\.0+)?$'; then
    printf '%s' "$v"
  else
    printf '%s' "$DEFAULT_REMOTE_TIMEOUT"
  fi
}

# Name of the available wall-clock bounding binary, or empty. `timeout` is GNU
# coreutils and is absent on a stock macOS, where Homebrew installs `gtimeout`.
timeout_bin() {
  if command -v timeout >/dev/null 2>&1; then
    printf 'timeout'
  elif command -v gtimeout >/dev/null 2>&1; then
    printf 'gtimeout'
  fi
}

# Run a command under the wall-clock bound when one is available. Exit 124 (the
# `timeout` convention) therefore reaches the caller as a distinct outcome.
run_bounded() {
  local tb
  tb="$(timeout_bin)"
  if [ -n "$tb" ]; then
    "$tb" "$(remote_timeout)" "$@"
  else
    "$@"
  fi
}

refuse_create() {
  local branch="$1" reason="$2" detail="$3"
  echo "worktree.sh: ERROR: refusing to create worktree for '$branch': reason=$reason — $detail" >&2
  echo "worktree.sh: refusing rather than re-rooting '$branch' onto the current base; no branch and no worktree were created." >&2
}

# Create the local branch at the live remote tip, with tracking set, or refuse.
# Only called when refs/heads/<branch> is absent and refs/remotes/origin/<branch>
# is present, i.e. the state a review-phase `remove` leaves behind.
resolve_from_remote() {
  local branch="$1"
  local to
  to="$(remote_timeout)"

  if [ -z "$(timeout_bin)" ]; then
    echo "worktree.sh: note: no 'timeout'/'gtimeout' binary found — the remote consultation for '$branch' runs unbounded (KIT_WORKTREE_FETCH_TIMEOUT has no effect)." >&2
  fi

  if ! git remote get-url origin >/dev/null 2>&1; then
    refuse_create "$branch" "no-remote-configured" \
      "a stale refs/remotes/origin/$branch exists but no remote named 'origin' is configured, so the remote tip cannot be established"
    return 1
  fi

  # `git ls-remote --exit-code` is git's own oracle for "can I reach the remote,
  # and does this ref exist there": 0 = found, 2 = no matching ref, non-zero
  # otherwise = could not talk to the remote. Classify from those exit codes
  # rather than by matching git's prose.
  local rc=0
  run_bounded git ls-remote --exit-code origin "refs/heads/$branch" >/dev/null 2>&1 || rc=$?
  case "$rc" in
    0) ;;
    2)
      refuse_create "$branch" "no-such-remote-ref" \
        "refs/remotes/origin/$branch is present locally but origin no longer has refs/heads/$branch (the remote branch was deleted); the cached ref is stale"
      return 1
      ;;
    124)
      refuse_create "$branch" "remote-fetch-timeout" \
        "consulting origin for refs/heads/$branch exceeded ${to}s — raise KIT_WORKTREE_FETCH_TIMEOUT if the remote is merely slow"
      return 1
      ;;
    *)
      refuse_create "$branch" "remote-unreachable" \
        "could not read refs/heads/$branch from origin (git ls-remote exit $rc); the remote tip cannot be established"
      return 1
      ;;
  esac

  rc=0
  run_bounded git fetch --quiet origin \
    "+refs/heads/$branch:refs/remotes/origin/$branch" || rc=$?
  if [ "$rc" -eq 124 ]; then
    refuse_create "$branch" "remote-fetch-timeout" \
      "fetching refs/heads/$branch from origin exceeded ${to}s — raise KIT_WORKTREE_FETCH_TIMEOUT if the remote is merely slow"
    return 1
  elif [ "$rc" -ne 0 ]; then
    refuse_create "$branch" "remote-fetch-failed" \
      "origin advertised refs/heads/$branch but fetching it failed (git fetch exit $rc)"
    return 1
  fi

  # HEAD and upstream in one step. Setting the upstream without re-pointing
  # HEAD (or the reverse) is the failure this fix exists to remove.
  git branch --quiet --track "$branch" "origin/$branch" >&2
}

# Both refs exist. Report the divergence instead of silently picking a side.
announce_divergence() {
  local branch="$1"
  local l r
  l="$(git rev-parse "refs/heads/$branch")"
  r="$(git rev-parse "refs/remotes/origin/$branch")"
  if [ "$l" = "$r" ]; then
    return 0
  fi

  local ls rs rel
  ls="$(git rev-parse --short "refs/heads/$branch")"
  rs="$(git rev-parse --short "refs/remotes/origin/$branch")"
  if git merge-base --is-ancestor "$l" "$r"; then
    rel="origin/$branch is ahead (fast-forwardable)"
  elif git merge-base --is-ancestor "$r" "$l"; then
    rel="the local ref is ahead"
  else
    rel="diverged (neither side is an ancestor of the other)"
  fi

  echo "worktree.sh: WARNING: divergence for '$branch': local $ls vs origin/$branch $rs — $rel; resolving to the LOCAL ref (see this script's header)." >&2
  echo "worktree.sh: the origin side above is the CACHED remote-tracking ref — no fetch runs when a local ref exists, so it may be stale." >&2
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

  local has_local=0 has_remote_ref=0
  if git show-ref --verify --quiet "refs/heads/$branch"; then
    has_local=1
  fi
  if git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    has_remote_ref=1
  fi

  if [ "$has_local" -eq 1 ]; then
    if [ "$has_remote_ref" -eq 1 ]; then
      announce_divergence "$branch"
    fi
    echo "worktree.sh: branch '$branch' source=local-ref $(git rev-parse --short "refs/heads/$branch")" >&2
  elif [ "$has_remote_ref" -eq 1 ]; then
    # Refuses (non-zero, nothing on stdout) when the remote tip cannot be
    # established, instead of falling through to the base.
    resolve_from_remote "$branch" || return 1
    echo "worktree.sh: branch '$branch' source=remote-tip origin/$branch $(git rev-parse --short "refs/heads/$branch") (upstream origin/$branch)" >&2
  else
    # Genuinely new branch. Unchanged on purpose: `default_branch` is really
    # `git symbolic-ref --short HEAD`, i.e. whatever branch the caller is on.
    local default_branch
    default_branch="$(git symbolic-ref --short HEAD 2>/dev/null || echo main)"
    git branch "$branch" "$default_branch"
    echo "worktree.sh: branch '$branch' source=new-from-base base='$default_branch' $(git rev-parse --short "refs/heads/$branch")" >&2
  fi

  # After resolution, so a refusal leaves no directory behind.
  mkdir -p "$root/$WORKTREE_DIR"

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
