#!/bin/bash
# session-start.sh — SessionStart-хук лабораторії ai-lab.
# Єдина відповідальність: підвантажити робочий контекст на старті сесії
# (мова/безпека, активні навички, статус docs/PLAN.md, останній висновок
# docs/learnings.md). Бутстрап pre-commit — окремо: scripts/setup.sh.
# Активується через ../../.claude/settings.json. Ідемпотентний, неінтерактивний.
# Вимкнути: прибрати блок SessionStart у settings.json.
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_DIR" || exit 0

# --- Зібрати дайджест контексту ---
build_digest() {
  printf '## Контекст лабораторії ai-lab — SessionStart\n\n'
  printf '**Мова:** спілкування українською; UA — канон, EN — дзеркало для публікацій.\n'
  printf '**Безпека:** жодних секретів у репо (лише env); перед комітом — pre-commit.\n\n'
  printf '**Дій за Робочим стандартом щозапиту (CLAUDE.md § Робочий стандарт).**\n\n'

  if compgen -G ".claude/skills/*/SKILL.md" >/dev/null 2>&1; then
    printf '**Активні навички:**\n'
    for f in .claude/skills/*/SKILL.md; do
      d="${f%/SKILL.md}"
      printf -- '- /%s\n' "${d##*/}"
    done
    printf '\n'
  fi

  # Рівень пояснень. Один рядок, бо він потрапляє в кешований префікс і
  # перечитується щоходу — довша довідка з'їла б те, заради чого існує.
  # Живе тут, а не в окремому хуці: відповідальність та сама (контекст сесії),
  # а другий процес коштував би більше за сам рядок.
  if [ -f .claude/ai-lab.json ] && command -v python3 >/dev/null 2>&1; then
    lvl="$(python3 -c 'import json;print(json.load(open(".claude/ai-lab.json")).get("explain_level","brief"))' 2>/dev/null || true)"
    if [ -n "${lvl:-}" ]; then
      printf '**Рівень пояснень:** `%s` (`.claude/ai-lab.json`). Звіти про ризик, питання про згоду й чесність про межі не скорочуються за жодного рівня.\n\n' "$lvl"
    fi
  fi

  if [ -f docs/PLAN.md ]; then
    printf '**Статус плану (docs/PLAN.md):**\n'
    grep -E '^## Фаза' docs/PLAN.md 2>/dev/null | sed 's/^## /- /' || true
    printf '\n'
  fi

  if [ -f docs/learnings.md ]; then
    last="$(grep -E '^## [0-9]{4}-[0-9]{2}-[0-9]{2}' docs/learnings.md 2>/dev/null | tail -n 1 | sed 's/^## //' || true)"
    if [ -n "${last:-}" ]; then
      printf '**Останній висновок:** %s\n\n' "$last"
    fi
  fi

  if ! command -v pre-commit >/dev/null 2>&1; then
    printf '⚠️ pre-commit не встановлено — для git-хуків запусти `scripts/setup.sh`.\n\n'
  fi

  printf '_Цикл: гіпотеза → дизайн → запуск → вимір → лиши/прибери → висновок (docs/methodology.md)._\n'
}

digest="$(build_digest)"

# --- Віддати контекст у сесію (JSON additionalContext; fallback — plain stdout) ---
if command -v jq >/dev/null 2>&1; then
  jq -nc --arg ctx "$digest" \
    '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:$ctx}}'
else
  printf '%s\n' "$digest"
fi
