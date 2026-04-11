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
ROOT="$(bash "$SCRIPT_DIR/worktree.sh" root)"
exec python3 "$ROOT/scripts/verify_checkpoint.py" "$@"
