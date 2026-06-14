#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJ_ROOT="$(pwd)"

bash "$KIT_ROOT/scripts/ensure_gh.sh"

mkdir -p "$PROJ_ROOT/.claude"

# ── Install core + optional packs ────────────────────────────────────
# Forwards --pack=<name> args to install_packs.py. Defaults to core only.
# install_packs.py prints any per-pack settings_snippet paths to stdout
# (one per line); we capture them to merge after core's snippet.
PACK_SNIPPETS=$(python3 "$KIT_ROOT/scripts/install_packs.py" \
  "$KIT_ROOT" "$PROJ_ROOT" "$@")

rm -rf "$PROJ_ROOT/.claude/hooks"
ln -sfn "$KIT_ROOT/project/.claude/hooks" "$PROJ_ROOT/.claude/hooks"

# Merge core settings snippet first.
python3 "$KIT_ROOT/scripts/merge_settings.py" \
  "$PROJ_ROOT/.claude/settings.json" \
  "$KIT_ROOT/project/.claude/settings.snippet.json"

# Then merge each pack's snippet (alphabetical pack-name order).
# Pack snippets override core on key collision (deep merge, last write wins).
if [ -n "$PACK_SNIPPETS" ]; then
  while IFS= read -r snippet; do
    [ -z "$snippet" ] && continue
    python3 "$KIT_ROOT/scripts/merge_settings.py" \
      "$PROJ_ROOT/.claude/settings.json" \
      "$snippet"
  done <<< "$PACK_SNIPPETS"
fi

# Ensure settings.local.json has required sprint permissions
python3 "$KIT_ROOT/scripts/ensure_permissions.py" \
  "$PROJ_ROOT/.claude/settings.local.json"

# Register merge=ours driver for shared registry files (issues.md, STATUS.md, CHANGELOG.md)
git -C "$PROJ_ROOT" config merge.ours.driver true 2>/dev/null || true

# ── Linter / Formatter tools ──────────────────────────────────────────
# ruff (Python)
if ! command -v ruff &>/dev/null; then
  if command -v uv &>/dev/null; then
    uv tool install ruff 2>/dev/null || true
  else
    pip install ruff 2>/dev/null || pip3 install ruff 2>/dev/null || true
  fi
fi

# prettier (JS/TS/CSS/JSON)
if ! command -v prettier &>/dev/null; then
  npm install -g prettier 2>/dev/null || true
fi

# ── Linter config symlinks ────────────────────────────────────────────
ln -sfn "$KIT_ROOT/linters/ruff.toml" "$PROJ_ROOT/ruff.toml"
ln -sfn "$KIT_ROOT/linters/.prettierrc.json" "$PROJ_ROOT/.prettierrc.json"

echo "✅ Installed kit into: $PROJ_ROOT/.claude"
