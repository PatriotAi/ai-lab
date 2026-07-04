# Skill Guard — Інструкція безпечного оновлення

## Обов'язковий протокол перед будь-яким оновленням SKILL.md

```
ПЕРЕД редагуванням:   python skill_guard.py snapshot
ПІСЛЯ редагування:    python skill_guard.py validate
ДО публікації:        python skill_guard.py update proposed_skill.md
```

---

## Команди

| Команда | Що робить |
|---|---|
| `snapshot` | Зберігає відбиток поточного стану |
| `validate` | Перевіряє поточний SKILL.md (59 перевірок) |
| `diff` | Показує що змінилось з останнього snapshot |
| `update <file>` | Diff + validate нової версії перед заміною |
| `baseline --create` | Записує поточний стан як еталон |
| `baseline --check` | Перевіряє регресії відносно еталону |
| `history` | Показує лог усіх операцій |
| `add-term <term>` | Інструкція як додати новий canonical term |

---

## Що перевіряє Guard (14 категорій, 59+ елементів)

### Canonical Terms (59)
Кожен термін шукається case-insensitive. Відсутній → ERROR і блок.

- Python MCP tools: 19 (open_notebook, get_all_content, ...)
- Browserbase tools: 12 (navigate, click, type, extract, scroll, wait + 6 NLM)
- Studio features: 13 (Audio, Video, Briefing, Study Guide, FAQ, ...)
- i18n / Collab Browser: 6 (translatePage, BroadcastChannel, window.storage, ...)
- Android: 5 (Cookie Editor, Browserbase, Smithery, days_remaining, needs_refresh)
- Integrations: 3 (docx skill, pptx skill, theme-factory)
- Interactive: 1 (Interactive Mode)

### Section Line Counts (мінімуми)
```
## Step 0    ≥ 12 lines
## Step 1    ≥ 55 lines
## Step 2    ≥  8 lines
## Step 3    ≥ 10 lines
## Step 4    ≥ 25 lines
## Step 5    ≥  4 lines
## Behavior  ≥ 15 lines
## References ≥  6 lines
```

### Behavior Rules Table
- Мінімум 14 рядків таблиці
- Регресія відносно baseline → ERROR

### Frontmatter
- Тільки `name` + `description`
- Без XML символів `< >`
- description ≤ 1024 символів

### Regression Detection
При наявності baseline або snapshot:
- Будь-який term що був присутній і зник → REGRESSION ERROR
- Секція що скоротилась >20% → REGRESSION ERROR
- Менше рядків у Behavior Rules → REGRESSION ERROR

---

## Workflow: безпечне оновлення крок за кроком

```bash
# 1. Зафіксувати поточний стан
cd notebooklm-connector
python scripts/skill_guard.py snapshot

# 2. Перевірити поточний стан (має бути 100%)
python scripts/skill_guard.py validate

# 3. Внести зміни до SKILL.md

# 4. Побачити що змінилось
python scripts/skill_guard.py diff

# 5. Валідувати нову версію (автоматично блокує при помилках)
python scripts/skill_guard.py validate

# 6. Або, якщо редагуєш окремий файл:
python scripts/skill_guard.py update /path/to/new_skill.md

# Якщо є навмисні видалення (підтверджені):
python scripts/skill_guard.py update /path/to/new_skill.md --force
# --force ТІЛЬКИ коли ти свідомо видаляєш deprecated функціонал
```

---

## Як додати новий функціонал (щоб Guard знав про нього)

```bash
# 1. Розробити новий інструмент/функцію
# 2. Додати до SKILL.md
# 3. Зареєструвати у Guard
python scripts/skill_guard.py add-term "new_tool_name"
# Guard покаже рядок для додавання в CANONICAL_TERMS

# 4. Оновити baseline
python scripts/skill_guard.py baseline --create
```

---

## Розуміння помилок Guard

```
❌ Missing canonical term: 'open_notebook'
→ Термін відсутній у SKILL.md. Він там був раніше і потрібен.

❌ Section '## Step 1' too short: 45 lines (min 55)
→ Секція скорочена нижче мінімуму. Перевір що не видалив tools.

❌ Behavior Rules table: only 11 rows (min 14)
→ З таблиці правил зникли рядки. Порівняй з backup.

❌ REGRESSION: Term 'browserbase_click' was present in baseline, now missing
→ Регресія. Цей термін був в еталоні. Відновити або оновити baseline.

❌ REGRESSION: Behavior Rules 19→17 rows (rows deleted)
→ Рядки таблиці видалені відносно baseline. Відновити або підтвердити --force.
```

---

## Де зберігаються дані Guard

```
scripts/
├── skill_guard.py           — головний скрипт
├── baseline.json            — еталонний відбиток (commit це!)
├── audit.jsonl              — лог усіх операцій
├── SKILL_GUARD_USAGE.md     — ця інструкція
└── .snapshots/
    ├── latest.json          — останній snapshot
    └── snapshot_YYYYMMDD_HHMMSS.json  — архів
```

**Важливо:** `baseline.json` і `audit.jsonl` — версіонувати разом зі SKILL.md.
