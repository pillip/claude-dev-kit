#!/usr/bin/env bash
# kit_root.sh — print the kit's installation root (the dir holding scripts/,
# agents/, skills/, hooks/).
#
# Resolution order (ISSUE-023):
#   1. ${CLAUDE_PLUGIN_ROOT}        — set when the kit runs as a Claude Code plugin
#   2. realpath parent of this file — standalone / symlinked scripts/ install
#
# This is the single place the kit answers "where am I installed", replacing the
# repo-root `scripts/` symlink assumption that caused the #34 bug class. It is
# distinct from the *project* root (a user's repo, resolved via git in
# worktree.sh) — this is the *kit* root.
set -euo pipefail

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -d "${CLAUDE_PLUGIN_ROOT}/scripts" ]; then
  printf '%s\n' "${CLAUDE_PLUGIN_ROOT}"
else
  script_dir="$(cd "$(dirname "$0")" && pwd -P)"
  printf '%s\n' "$(cd "$script_dir/.." && pwd -P)"
fi
