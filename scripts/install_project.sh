#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJ_ROOT="$(pwd)"

bash "$KIT_ROOT/scripts/ensure_gh.sh"

mkdir -p "$PROJ_ROOT/.claude"

# Remove old copies (if any) and create symlinks to kit source
for dir in agents skills; do
  rm -rf "$PROJ_ROOT/.claude/$dir"
  ln -sfn "$KIT_ROOT/$dir" "$PROJ_ROOT/.claude/$dir"
done

rm -rf "$PROJ_ROOT/.claude/hooks"
ln -sfn "$KIT_ROOT/project/.claude/hooks" "$PROJ_ROOT/.claude/hooks"

python3 "$KIT_ROOT/scripts/merge_settings.py" \
  "$PROJ_ROOT/.claude/settings.json" \
  "$KIT_ROOT/project/.claude/settings.snippet.json"

# Ensure settings.local.json has required sprint permissions
python3 "$KIT_ROOT/scripts/ensure_permissions.py" \
  "$PROJ_ROOT/.claude/settings.local.json"

# Register merge=ours driver for shared registry files (issues.md, STATUS.md, CHANGELOG.md)
git -C "$PROJ_ROOT" config merge.ours.driver true 2>/dev/null || true

echo "✅ Installed kit into: $PROJ_ROOT/.claude"
