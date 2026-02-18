#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$HOME/.claude/kit/bin"
mkdir -p "$TARGET"
cp "$KIT_ROOT/user/kit/bin/cc-statusline.py" "$TARGET/cc-statusline"
chmod +x "$TARGET/cc-statusline"
echo "✅ Installed statusline script to: $TARGET/cc-statusline"
