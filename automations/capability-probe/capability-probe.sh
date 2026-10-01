#!/bin/bash
# capability-probe.sh — SessionStart-хук: профіль можливостей виконавця.
#
# Єдина відповідальність: на старті сесії (і на старті КОЖНОГО суб-агента)
# з'ясувати, ЩО виконавець уміє нативно й що з цього справді діє тут, і подати
# це в контекст стисло. Мета — не інлайнити інструкції, які й так виконаються.
#
# ЧОМУ ЦЕ ХУК, А НЕ ПРАВИЛО В CLAUDE.md: ID моделі недоступний як env-змінна —
# він приходить ЛИШЕ в payload хука (звірено на робочому харнесі 2.1.220).
# Payload також несе `agent_type`/`agent_id`, тож профіль однаково працює на
# оркестраційному й на суб-рівні.
#
# ЧОМУ ВИВІД ТАКИЙ КОРОТКИЙ: цей текст додається в контекст КОЖНОЇ сесії, тобто
# перечитується щоходу з кешу. Профіль, довший за інструкції, які він дозволяє
# не інлайнити, з'їв би власну економію. Тому — тільки факти, що змінюють
# поведінку: жодних таблиць, пояснень і переліку невідомого.
#
# Активується через ../../.claude/settings.json. Ідемпотентний, неінтерактивний,
# без мережі. Вимкнути: прибрати блок із settings.json.
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
SCAN="$PROJECT_DIR/scripts/capability-scan.py"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/ai-lab"

# Хук ніколи не має ламати старт сесії: будь-яка проблема нижче = тихий вихід
# із порожнім профілем, тобто повний набір правил (fail-closed).
[ -f "$SCAN" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

payload="$(cat 2>/dev/null || true)"
[ -n "$payload" ] || exit 0

# --- Кеш: повторний скан має сенс лише коли змінився стан ------------------
# Ключ рахує сам сканер (модель + версія харнесу + перемикачі + settings).
# Збіг ключа означає, що відповідь буде та сама → читаємо з диска.
mkdir -p "$CACHE_DIR" 2>/dev/null || exit 0
key="$(printf '%s' "$payload" | python3 "$SCAN" --hook-payload --json 2>/dev/null \
       | python3 -c 'import json,sys; print(json.load(sys.stdin)["cache_key"])' 2>/dev/null || true)"
[ -n "$key" ] || exit 0

cache_file="$CACHE_DIR/profile-$key.json"
if [ ! -s "$cache_file" ]; then
  printf '%s' "$payload" | python3 "$SCAN" --hook-payload --json > "$cache_file.tmp" 2>/dev/null \
    && mv "$cache_file.tmp" "$cache_file" || { rm -f "$cache_file.tmp"; exit 0; }
fi

# --- Рендер стислого профілю ----------------------------------------------
python3 - "$cache_file" <<'PY'
import json, sys

try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        p = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(0)

harness = p.get("harness") or {}
caps = p.get("capabilities") or []
active = [c for c in caps if c.get("effective") is True]
# Показуємо лише ті вимкнені можливості, що мають наше правило-замінник:
# «авто-пам'ять не діє» — це вказівка тримати G5-цикл, а не довідка.
inactive = [c for c in caps if c.get("effective") is False and c.get("rule_candidate")]

# Мовчання за замовчуванням. Профіль потрапляє в кешований префікс і
# перечитується КОЖНОГО ходу — тому він має право на місце в контексті лише
# тоді, коли змінює поведінку. Нема чого сказати → нічого не кажемо, 0 токенів.
if harness.get("trusted") and not active and not inactive:
    sys.exit(0)

if not harness.get("trusted"):
    # Єдиний випадок, коли мовчати не можна: невпізнаний харнес означає, що
    # будь-яке скорочення правил зараз було б здогадкою.
    digest = ("## Профіль виконавця\n"
              "⚠️ Харнес не впізнано → профіль недостовірний. Діє ПОВНИЙ набір правил.")
else:
    lines = ["## Профіль виконавця",
             f"`{p.get('model','?')}` · {p.get('agent_type') or 'root'} · "
             f"харнес {harness.get('version_running') or '?'}"]
    if active:
        lines.append("✅ нативно діє: " + ", ".join(f"`{c['id']}`" for c in active))
    if inactive:
        lines.append("❌ НЕ діє (правило лишається): "
                     + "; ".join(f"`{c['id']}` → {c['rule_candidate']}" for c in inactive))
    lines.append("Skip інструкції — лише за ✅ і лише з пост-перевіркою. "
                 "Чого тут нема — невідоме → повне правило. Перевірки не скорочуються.")
    digest = "\n".join(lines)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart", "additionalContext": digest}},
    ensure_ascii=False))
PY
