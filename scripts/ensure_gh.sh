#!/usr/bin/env bash
set -euo pipefail
if ! command -v gh >/dev/null 2>&1; then
  echo "❌ 'gh' is not installed."
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "❌ 'gh' is not authenticated. Run: gh auth login"
  exit 1
fi
echo "✅ gh is installed and authenticated."
