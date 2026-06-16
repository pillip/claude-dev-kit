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
# verify_checkpoint.py always lives beside this script, so resolve it via
# SCRIPT_DIR rather than "$ROOT/scripts/…". This keeps the checkpoint working
# even when the kit's scripts/ isn't symlinked at the repo root.
exec python3 "$SCRIPT_DIR/verify_checkpoint.py" "$@"
