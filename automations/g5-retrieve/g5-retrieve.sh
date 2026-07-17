#!/usr/bin/env bash
# SessionStart-хук: авто-витяг персистованої пам'яті G5 у контекст сесії.
# Одна відповідальність: retrieval (парна до Stop-хука консолідації g5-consolidate).
# Детерміновано, без AI/секретів. Ніколи не блокує старт сесії.
set -euo pipefail
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_DIR" || exit 0

digest="$(python3 scripts/g5-retrieve.py 2>/dev/null || true)"
[ -z "$digest" ] && exit 0

if command -v jq >/dev/null 2>&1; then
  jq -nc --arg ctx "$digest" \
    '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:$ctx}}'
else
  printf '%s\n' "$digest"
fi
