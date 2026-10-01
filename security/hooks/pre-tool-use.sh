#!/usr/bin/env bash
# PreToolUse-хук: механічний гейт дій (Фаза S2, закриває дефект F-3).
#
# Одна відповідальність: передати опис виклику інструмента в класифікатор і
# повернути рішення Claude Code. Уся логіка — у security/spine/pretooluse.py;
# цей файл лише міст, щоб хук не залежав від поточної теки.
#
# Контракт: stdin — JSON виклику; stdout — JSON рішення; код виходу 0.
# Свідомо БЕЗ `set -e`: аварія гейта не має ламати сесію. Але й не має мовчки
# пропускати — тому нижче явний fallback на "ask".
set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
GATE="$PROJECT_DIR/security/spine/pretooluse.py"

input="$(cat)"

if [ ! -f "$GATE" ]; then
  # Гейта немає — не вдаємо, що перевірили.
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Безпековий гейт не знайдено (security/spine/pretooluse.py). Дію не перевірено — підтвердь її свідомо."}}'
  exit 0
fi

if ! out="$(printf '%s' "$input" | python3 "$GATE" 2>/dev/null)"; then
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Безпековий гейт не запустився. Дію не перевірено — підтвердь її свідомо."}}'
  exit 0
fi

# Порожній вивід = рівень нижчий за R4 = не втручаємось (жодного зайвого токена).
[ -n "$out" ] && printf '%s\n' "$out"
exit 0
