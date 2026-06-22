#!/usr/bin/env bash
# checkpoint.sh — resolve main repo root and run verify_checkpoint.py
#
# Wraps the common compound command:
#   ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" [args]
#
# Usage:
#   bash scripts/checkpoint.sh --skill implement --phase code --issue 123
#
# Exists so that skill templates can use a single prefix-matchable command
# (Bash(bash scripts/checkpoint.sh *)) instead of an inline compound that
# Claude Code's permission matcher cannot reliably allowlist.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Resolve the kit root, preferring ${CLAUDE_PLUGIN_ROOT} (plugin install) and
# falling back to this script's own directory (standalone / symlinked scripts/).
# verify_checkpoint.py lives under <kit-root>/scripts/, so this works under both
# layouts without a repo-root symlink — closes the #34 bug class. ISSUE-023.
KIT_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd -P)}"
exec python3 "$KIT_ROOT/scripts/verify_checkpoint.py" "$@"
