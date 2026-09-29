#!/usr/bin/env bash
# SessionStart-хук: авто-витяг персистованої пам'яті G5 у контекст сесії.
# Одна відповідальність: retrieval (парна до Stop-хука консолідації g5-consolidate).
# Детерміновано, без AI/секретів. Ніколи не блокує старт сесії.
#
# 2026-07-27 — витяг іде ЧЕРЕЗ ГЕЙТ `security/spine/memory_guard.py` (Фаза S1).
# Причина: цей хук — єдиний канал, що переносить текст через межу сесій, і до
# цієї зміни він подавав вміст пакета в контекст ДОСЛІВНО, без жодної перевірки.
# Прогін 2026-07-27 показав, що підкладена в пакет ін'єкція проходить повністю,
# хоча scripts/scan-external-input.py ловить у ній 4 маркери високої вагомості
# (дефект F-1, docs/security/findings-2026-07-27.md).
# Гейт: перелік дозволених шляхів → скан на приховані вказівки → обрамлення
# «це ДАНІ, не інструкції» + позначка застарілості.
# Якщо гейт із будь-якої причини недоступний — пам'ять НЕ подається взагалі
# (fail-closed): працювати без відновленої пам'яті безпечніше, ніж із неперевіреною.
set -euo pipefail
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJECT_DIR" || exit 0

GUARD="$PROJECT_DIR/security/spine/memory_guard.py"
if [ ! -f "$GUARD" ]; then
  # Fail-closed: без гейта пам'ять не відновлюємо, але старт сесії не ламаємо.
  printf '%s\n' "⚠️ Пам'ять не відновлено: гейт security/spine/memory_guard.py відсутній."
  exit 0
fi

digest="$(python3 "$GUARD" 2>/dev/null || true)"
[ -z "$digest" ] && exit 0

if command -v jq >/dev/null 2>&1; then
  jq -nc --arg ctx "$digest" \
    '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:$ctx}}'
else
  printf '%s\n' "$digest"
fi
