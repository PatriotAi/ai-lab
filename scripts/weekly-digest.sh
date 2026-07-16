#!/bin/bash
# weekly-digest.sh — детермінований щотижневий дайджест лабораторії ai-lab.
# Єдина відповідальність: зібрати «сирий» тижневий зріз у markdown на stdout
# (git-активність за 7 днів, статус docs/PLAN.md, останній висновок
# docs/learnings.md). Глибокі висновки/пріоритети — окремо, скіл `weekly-review`.
# Викликається з .github/workflows/weekly-digest.yml (розклад cron). Read-only.
set -euo pipefail

PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_DIR" || exit 1

SINCE="7 days ago"
TODAY="$(date -u +%Y-%m-%d)"

printf '## 🗓 Щотижневий дайджест ai-lab — %s\n\n' "$TODAY"
printf '_Автоматичний зріз (детермінований, без AI). Глибокі висновки додай скілом `weekly-review`._\n\n'

# --- Git-активність за тиждень ---
printf '### Активність за 7 днів\n'
commits="$(git log --since="$SINCE" --pretty=format:'- %s (%an, %ad)' --date=format:'%Y-%m-%d' 2>/dev/null || true)"
count="$(git log --since="$SINCE" --oneline 2>/dev/null | wc -l | tr -d ' ')"
if [ -n "$commits" ]; then
  printf 'Комітів: **%s**\n\n%s\n\n' "$count" "$commits"
else
  printf 'Комітів за тиждень: **0** (тихий тиждень).\n\n'
fi

# --- Статус плану (той самий патерн, що й SessionStart-хук) ---
if [ -f docs/PLAN.md ]; then
  printf '### Статус плану (docs/PLAN.md)\n'
  grep -E '^## Фаза' docs/PLAN.md 2>/dev/null | sed 's/^## /- /' || true
  printf '\n'
fi

# --- Останній висновок ---
if [ -f docs/learnings.md ]; then
  last="$(grep -E '^## [0-9]{4}-[0-9]{2}-[0-9]{2}' docs/learnings.md 2>/dev/null | tail -n 1 | sed 's/^## //' || true)"
  [ -n "${last:-}" ] && printf '### Останній висновок (docs/learnings.md)\n- %s\n\n' "$last"
fi

# --- Наступні кроки (чекліст) ---
printf '### Наступний крок\n'
printf -- '- [ ] Провести ретроспективу скілом `weekly-review` (висновки + пріоритети тижня)\n'
printf -- '- [ ] Оновити `docs/PLAN.md` і `docs/learnings.md` за підсумками\n'
printf -- '- [ ] Закрити цей Issue після ретроспективи\n'
