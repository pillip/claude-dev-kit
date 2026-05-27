#!/usr/bin/env bash
# find_shared.sh — walk up from cwd to find a shared sales-pack file in a docs/ directory.
#
# Use case: sales repo organized as accounts/<account>/docs/... with shared files
# (sales_lessons.md, sales_email_persona.md) at the repo-root docs/.
# When a skill runs from inside an account directory, it needs to find the shared
# file without hardcoding the full path.
#
# Usage:
#   bash scripts/find_shared.sh <filename>
#
# Behavior:
#   - Starts from $PWD, checks $dir/docs/<filename>, walks up one directory.
#   - Stops at filesystem root, or at a directory containing .git (repo root boundary).
#   - On success: prints absolute path of found file, exits 0.
#   - On failure (not found within repo): prints nothing, exits 1.
#
# Example:
#   $ cd accounts/kt-millie
#   $ bash ../../scripts/find_shared.sh sales_lessons.md
#   /Users/me/sales-ops/docs/sales_lessons.md

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: find_shared.sh <filename>" >&2
  exit 2
fi

filename="$1"
dir="$(pwd)"

while true; do
  candidate="$dir/docs/$filename"
  if [ -f "$candidate" ]; then
    # Resolve to absolute path (realpath not universally available on macOS; use cd/pwd)
    abs="$(cd "$(dirname "$candidate")" && pwd)/$(basename "$candidate")"
    echo "$abs"
    exit 0
  fi

  # Stop at git repo root (check after candidate so a docs/ at repo root is still found)
  if [ -d "$dir/.git" ]; then
    exit 1
  fi

  # Stop at filesystem root
  if [ "$dir" = "/" ]; then
    exit 1
  fi

  dir="$(dirname "$dir")"
done
