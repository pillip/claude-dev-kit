#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJ_ROOT="$(pwd)"

bash "$KIT_ROOT/scripts/ensure_gh.sh"

mkdir -p "$PROJ_ROOT/.claude/agents" "$PROJ_ROOT/.claude/skills" "$PROJ_ROOT/.claude/hooks"
rsync -a --delete "$KIT_ROOT/agents/" "$PROJ_ROOT/.claude/agents/"
rsync -a --delete "$KIT_ROOT/skills/" "$PROJ_ROOT/.claude/skills/"
rsync -a --delete "$KIT_ROOT/project/.claude/hooks/" "$PROJ_ROOT/.claude/hooks/"

python3 "$KIT_ROOT/scripts/merge_settings.py" \
  "$PROJ_ROOT/.claude/settings.json" \
  "$KIT_ROOT/project/.claude/settings.snippet.json"

# Register merge=ours driver for shared registry files (issues.md, STATUS.md, CHANGELOG.md)
git -C "$PROJ_ROOT" config merge.ours.driver true 2>/dev/null || true

echo "✅ Installed kit into: $PROJ_ROOT/.claude"
