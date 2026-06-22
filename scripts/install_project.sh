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

# ── Expose kit scripts at the project root ────────────────────────────
# Skill templates invoke `bash scripts/<name>` (checkpoint.sh, wt_setup.sh,
# verify_checkpoint.py, …) from the repo root, and the permission allowlist is
# prefix-matched on `scripts/`. So the kit's scripts/ must be reachable there.
# Prefer a single directory symlink (keeps inter-script imports / sibling
# lookups working). If the project already has its own real scripts/ dir,
# symlink each kit script in individually, skipping name collisions.
if [ -e "$PROJ_ROOT/scripts" ] && [ ! -L "$PROJ_ROOT/scripts" ]; then
  echo "  Project has its own scripts/ — linking kit scripts individually."
  for src in "$KIT_ROOT"/scripts/*; do
    name="$(basename "$src")"
    [ "$name" = "__pycache__" ] && continue
    dst="$PROJ_ROOT/scripts/$name"
    if [ -e "$dst" ] && [ ! -L "$dst" ]; then
      echo "  ⚠️  skip scripts/$name (project already has its own)"
      continue
    fi
    ln -sfn "$src" "$dst"
  done
else
  ln -sfn "$KIT_ROOT/scripts" "$PROJ_ROOT/scripts"
fi

# ── Ignore the per-worktree freeze marker ─────────────────────────────
# wt_setup.sh writes an absolute path into .claude-kit/freeze-dir.txt inside
# each worktree. If committed, parallel branches merge-conflict on it even
# when their source diffs are disjoint. Make sure it's ignored.
GITIGNORE="$PROJ_ROOT/.gitignore"
if ! { [ -f "$GITIGNORE" ] && grep -qxF '.claude-kit/freeze-dir.txt' "$GITIGNORE"; }; then
  printf '\n# claude-dev-kit: per-worktree freeze marker (never track)\n.claude-kit/freeze-dir.txt\n' >> "$GITIGNORE"
fi

echo "✅ Installed kit into: $PROJ_ROOT/.claude"
