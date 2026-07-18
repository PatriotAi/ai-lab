#!/bin/bash
# sync.sh — SessionStart-хук: тримає Stop-хук git-перевірки в актуальному стані.
# Єдина відповідальність: якщо копія в ~/.claude/ відсутня або відрізняється від
# канону (automations/stop-git-check/stop-hook-git-check.sh) — оновити її.
# Потрібен, бо контейнер середовища Claude Code (web) на кожному старті відновлює
# базову версію хука, яка зчиняє фальшиві тривоги на серверних merge-комітах.
# Ідемпотентний, тихий (вивід лише при фактичному оновленні), неінтерактивний.
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
SRC="$PROJECT_DIR/automations/stop-git-check/stop-hook-git-check.sh"
DST="$HOME/.claude/stop-hook-git-check.sh"

[ -f "$SRC" ] || exit 0
if [ ! -f "$DST" ] || ! cmp -s "$SRC" "$DST"; then
  cp "$SRC" "$DST" && chmod +x "$DST" || exit 0
fi
exit 0
