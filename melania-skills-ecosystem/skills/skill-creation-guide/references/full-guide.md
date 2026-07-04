# Повний посібник зі створення Skills для Claude
> Версія 1.0 · Меланія · травень 2026  
> Формат: Markdown `.md` — мінімум токенів, максимум структури  
> Для опрацювання: використовувати `skill-creator` + `validation-mesh`

---

## ЗМІСТ

1. [Що таке Skill і чому Markdown](#1-що-таке-skill-і-чому-markdown)
2. [Анатомія Skill — обов'язкова структура](#2-анатомія-skill--обовязкова-структура)
3. [YAML Frontmatter — детально](#3-yaml-frontmatter--детально)
4. [Тіло SKILL.md — шаблони і патерни](#4-тіло-skillmd--шаблони-і-патерни)
5. [Bundled Resources — коли і як](#5-bundled-resources--коли-і-як)
6. [Progressive Disclosure — рівні завантаження](#6-progressive-disclosure--рівні-завантаження)
7. [Евалюації (evals.json) — шаблон і правила](#7-евалюації-evalsjson--шаблон-і-правила)
8. [Guard Script — захист від регресій](#8-guard-script--захист-від-регресій)
9. [Що з наявних Skills застосувати](#9-що-з-наявних-skills-застосувати)
10. [Покрокове створення нового Skill](#10-покрокове-створення-нового-skill)
11. [Таблиця помилок і антипатернів](#11-таблиця-помилок-і-антипатернів)
12. [Додаткові Skills для опрацювання задачі](#12-додаткові-skills-для-опрацювання-задачі)
13. [Готові шаблони copy-paste](#13-готові-шаблони-copy-paste)

---

## 1. Що таке Skill і чому Markdown

### Що таке Skill

Skill — це файл інструкцій (`SKILL.md`), що зберігається у файловій системі Claude і автоматично потрапляє в контекст коли Claude вирішує, що він релевантний для поточного запиту.

**Важлива механіка тригеру:**
- Claude бачить лише `name` + `description` з усіх Skills (≈100 слів кожен)
- Якщо відповідає — зчитує повний `SKILL.md`
- Resources (scripts, references) — завантажуються тільки коли явно викликані

### Чому саме Markdown `.md`

| Формат | Токени на 1000 символів | Читабельність для LLM | Підтримка структури | Висновок |
|--------|------------------------|----------------------|---------------------|----------|
| `.md` | ~220–260 | ★★★★★ | Заголовки, таблиці, код | ✅ Ідеально |
| `.docx` | ~800–1200 (XML overhead) | ★★☆☆☆ | Потребує конвертації | ❌ Зайві токени |
| `.pdf` | ~600–900 (binary) | ★★★☆☆ | Потребує парсингу | ❌ Зайві токени |
| `.json` | ~300–400 | ★★★★☆ | Тільки дані, не інструкції | ⚠️ Часткова |
| `.txt` | ~220–250 | ★★★★☆ | Без структури | ⚠️ Для простих |

**Висновок:** Markdown — єдиний формат що одночасно: мінімально токено-витратний, нативно читається LLM, підтримує всю необхідну структуру (заголовки, таблиці, блоки коду, списки).

---

## 2. Анатомія Skill — обов'язкова структура

### Мінімальна файлова структура

```
my-skill/
├── SKILL.md          ← ОБОВ'ЯЗКОВО (інструкції + YAML frontmatter)
├── evals/
│   └── evals.json    ← рекомендовано (тест-кейси)
├── scripts/          ← опціонально (Python/bash скрипти)
│   └── skill_guard.py
└── references/       ← опціонально (великі довідкові файли)
    └── capabilities.md
```

### Правило розміру SKILL.md

```
< 200 рядків  → ідеально, все в SKILL.md
200–500 рядків → допустимо, виносити деталі в references/
> 500 рядків  → ОБОВ'ЯЗКОВО розбити на references/ з чіткими покажчиками
```

**Приклад з реальних Skills Меланії:**
- `notebooklm-connector`: 302 рядки (складний, межа норми — виправдано)
- `webapp-testing`: ~90 рядків (ідеально)
- `llm-api-builder`: ~130 рядків + references/ по мовах (правильний патерн)

---

## 3. YAML Frontmatter — детально

### Обов'язкові поля

```yaml
---
name: my-skill-name          # kebab-case, унікальний ідентифікатор
description: "..."           # КРИТИЧНО: основний тригерний механізм
---
```

### Опціональні поля

```yaml
---
name: my-skill-name
description: "..."
license: MIT                 # або Proprietary. LICENSE.txt has complete terms
metadata:
  author: Ім'я
  version: 1.0.0
  category: routing
---
```

### Правила написання description (КРИТИЧНО)

Description — єдине що Claude читає при прийнятті рішення "використовувати чи ні".

**Структура ефективного description:**
```
[ЩО робить skill] + [КОЛИ тригерити] + [Ключові слова] + [НІКОЛИ не для...]
```

**Приклад поганого description:**
```
Допомагає з документами Word.
```

**Приклад хорошого description (патерн з notebooklm-connector):**
```
Full integration with Google NotebookLM: read sources, add URLs and files,
merge all sources into one document, generate Audio Overview, Video Overview,
Briefing Doc, Study Guide, FAQ, Timeline, Mind Map, Slide Deck, Infographic,
Flashcards, Quizzes, Deep Research, and Chat with citations.
ALWAYS use this skill when user mentions notebook or notebooklm, shares a
notebooklm.google.com link, or says dodai do notebook, vytahny z notebook,
obiednai dzherela, analizui notebook. Even without the word notebooklm: use
when user wants to merge research sources, generate a podcast from documents,
build a knowledge base, or analyze sources with cited answers.
Also triggers for: collaborative browser, спільний браузер, відкрий браузер.
DO NOT use for plain Google Docs tasks with no NotebookLM involvement.
```

**Ключові принципи:**
1. Бути "pushy" — Claude схильний до undertriggering
2. Включати синоніми, теги, мови (укр/англ)
3. Явно писати `ALWAYS use when...` і `DO NOT use for...`
4. Додавати конкретні фрази які може сказати користувач

---

## 4. Тіло SKILL.md — шаблони і патерни

### Базовий шаблон

```markdown
---
name: skill-name
description: "..."
---

# Назва Skill — vX

## Core Rule

[Одне-два речення найважливішого правила поведінки.]

---

## Step 0 — Pre-flight (якщо є логіка вибору)

[Визначення режимів, перевірка умов]

---

## Step 1 — [Основна дія]

[Детальні інструкції]

### 1A — [Варіант A]
### 1B — [Варіант B]

---

## Behavior (таблиця правил)

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| ... | ... | ... |

---

## References

- `references/file.md` — коли читати: [умова]
```

### Патерн: Каскад (з notebooklm-connector)

Коли є кілька методів виконання задачі з пріоритетами:

```markdown
## Method Priority (check in order, use first available)

  1. primary-tool    — опис, коли доступний
  2. secondary-tool  — опис, коли доступний  
  3. fallback        — останній варіант

NEVER explain why [primary] is unavailable. Cascade silently.
```

### Патерн: Таблиця Behavior (обов'язковий для складних Skills)

```markdown
## Behavior

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| API недоступний | Тихо перейти до fallback | Пояснювати обмеження |
| Помилка 403 | Cascade до наступного методу | Зупинитись |
| Мобільний пристрій | Emoji-навігація, короткі кроки | Desktop-шорткати |
```

### Патерн: Decision Engine

```markdown
## Step 2 — Decision Engine

```
TASK → MODE selection:
  contains URL  → READ mode
  "add source"  → IMPORT mode
  "generate"    → STUDIO mode
  otherwise     → ANALYSIS mode
```
```

### Патерн: Посилання на References

```markdown
## References

Read `references/capabilities.md` WHEN:
- User asks about feature X
- Error code starts with 4xx

Read `references/platform-matrix.md` WHEN:
- Comparing platforms
- Version-specific behavior needed

Never load references proactively — only on demand.
```

### Стиль написання інструкцій

```
✅ Використовуй наказовий спосіб:
   "Read the file", "Check status", "Never explain"

❌ Не використовуй описовий:
   "The skill reads the file", "You should check"

✅ Пояснюй ЧОМУ (теорія розуму):
   "Skip this step on mobile — no keyboard shortcuts available"

❌ Не просто MUST без причини:
   "MUST always check mobile"
```

---

## 5. Bundled Resources — коли і як

### Коли виносити в references/

```
У SKILL.md залишаємо:  покажчик + умова читання (1-2 рядки)
У references/ виносимо: деталі >50 рядків, специфічні для платформи дані,
                         таблиці підтримки, повні списки інструментів
```

### Структура reference-файлу

```markdown
# Назва Reference

> Читати коли: [умова з SKILL.md]
> Розмір: ~X рядків · Оновлено: YYYY-MM

## Table of Contents (обов'язково якщо >100 рядків)

1. [Секція A](#секція-а)
2. [Секція B](#секція-б)

## Секція A
...
```

### Приклад з llm-api-builder (правильний патерн)

```
llm-api-builder/
├── SKILL.md (130 рядків — вибір мови, дефолти)
└── references/
    ├── python/     ← читається тільки для Python проектів
    ├── typescript/ ← читається тільки для TS проектів
    ├── java/
    ├── go/
    └── ruby/
```

Claude завантажує тільки одну папку — та що відповідає мові проекту.

### Скрипти в scripts/

```python
# Скрипти виконуються без завантаження в контекст
# Ідеально для: валідації, захисту від регресій, упаковки

# Виклик з SKILL.md:
# Run: python scripts/skill_guard.py --snapshot
```

---

## 6. Progressive Disclosure — рівні завантаження

```
Рівень 1: name + description  (~100 слів)
          ↓ завжди в контексті
          
Рівень 2: SKILL.md body        (< 500 рядків)
          ↓ завантажується при тригері skill
          
Рівень 3: references/*         (необмежено)
          ↓ завантажується тільки коли явно потрібен
          
Рівень 4: scripts/*            (виконуються без завантаження)
          ↓ тільки при виклику конкретного скрипту
```

**Практичне правило:** Якщо інформація потрібна у <30% випадків — виноси в references.

---

## 7. Евалюації (evals.json) — шаблон і правила

### Мінімальна структура

```json
{
  "skill_name": "my-skill",
  "version": "1.0.0",
  "evals": [
    {
      "id": 1,
      "name": "descriptive-test-name",
      "prompt": "Реальна фраза від користувача як він би написав",
      "expected_output": "Що має відбутись (для людини-рецензента)",
      "assertions": [
        "Конкретна перевірювана умова 1",
        "Конкретна перевірювана умова 2",
        "Конкретна перевірювана умова 3"
      ]
    }
  ]
}
```

### Правила написання тест-кейсів

**Хороші промпти для евалюацій:**
- Реалістичні — як написав би справжній користувач
- Достатньо складні — прості запити не тригерять Skills
- Охоплюють edge-cases (мобільний, помилка, відсутній інструмент)

**Хороші assertions:**
- Конкретні та перевірювані (не "відповідь хороша")
- Негативні перевірки ("Does NOT say X")
- Перевірки поведінки ("Calls tool Y before asking user")

**Приклад з notebooklm-connector (реальний):**
```json
{
  "id": 1,
  "name": "read-notebook-url",
  "prompt": "Аналізуй дані з цього Notebook і поєднай всі джерела...",
  "assertions": [
    "Does NOT say 'NotebookLM has no API' and stop",
    "Attempts web_fetch or MCP tool call before asking user",
    "Either generates React Artifact OR calls notebooklm_* MCP tools",
    "If manual needed: gives specific 1-2 step instruction, not open-ended question"
  ]
}
```

### Мінімальний набір тест-кейсів

| Тип | Опис | Кількість |
|-----|------|-----------|
| Happy path | Стандартний успішний сценарій | 2–3 |
| Edge case | Відсутній інструмент, помилка, мобільний | 1–2 |
| Negative | Чого НЕ має робити skill | 1 |
| **Мінімум** | | **4–6** |

---

## 8. Guard Script — захист від регресій

### Концепція (з notebooklm-connector)

Guard script — Python-скрипт що перевіряє SKILL.md на відповідність snapshot-еталону перед кожним оновленням.

```
Baseline snapshot (еталон)
    ↓
skill_guard.py --validate
    ↓
Перевіряє: кількість рядків, кількість канонічних термінів,
           кількість рядків у Behavior таблиці, MD5 хеш
    ↓
score < 100/100 → BLOCK update + показати що пропало
score = 100/100 → allow update
```

### Мінімальний guard script

```python
#!/usr/bin/env python3
"""skill_guard.py — захист SKILL.md від регресій"""
import json, hashlib, sys, re
from pathlib import Path
from datetime import datetime, timezone

SKILL_PATH = Path(__file__).parent.parent / "SKILL.md"
SNAP_PATH = Path(__file__).parent / ".snapshots" / "latest.json"

# Канонічні терміни — обов'язково присутні в SKILL.md
CANONICAL_TERMS = [
    "Core Rule", "Step 0", "Step 1", "Behavior",
    # додай специфічні для свого skill
]

def snapshot():
    text = SKILL_PATH.read_text()
    lines = text.splitlines()
    snap = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "md5": hashlib.md5(text.encode()).hexdigest(),
        "total_lines": len(lines),
        "terms": {t: (t in text) for t in CANONICAL_TERMS},
    }
    SNAP_PATH.parent.mkdir(exist_ok=True)
    SNAP_PATH.write_text(json.dumps(snap, indent=2))
    print(f"✅ Snapshot збережено: {snap['total_lines']} рядків")

def validate():
    if not SNAP_PATH.exists():
        print("❌ Snapshot не знайдено. Запусти: python skill_guard.py --snapshot")
        sys.exit(1)
    snap = json.loads(SNAP_PATH.read_text())
    text = SKILL_PATH.read_text()
    errors = []
    for term, was_present in snap["terms"].items():
        if was_present and term not in text:
            errors.append(f"ВІДСУТНІЙ: {term}")
    current_lines = len(text.splitlines())
    if current_lines < snap["total_lines"] * 0.85:
        errors.append(f"Рядки: {snap['total_lines']} → {current_lines} (>15% скорочення)")
    if errors:
        print(f"❌ ЗАБЛОКОВАНО — {len(errors)} помилок:")
        for e in errors: print(f"   {e}")
        sys.exit(1)
    print(f"✅ Валідація пройшла: {current_lines} рядків, всі терміни присутні")

if __name__ == "__main__":
    if "--snapshot" in sys.argv: snapshot()
    elif "--validate" in sys.argv: validate()
    else: print("Використання: --snapshot | --validate")
```

### Коли запускати

```
Перед редагуванням:  python scripts/skill_guard.py --validate
Після завершення:    python scripts/skill_guard.py --snapshot
При CI/CD:           python scripts/skill_guard.py --validate || exit 1
```

---

## 9. Що з наявних Skills застосувати

### Карта застосування

| Наявний Skill | Що взяти для нового Skill | Де знайти |
|---------------|--------------------------|-----------|
| `notebooklm-connector` | Патерн каскаду, Guard script, структура evals, таблиця Behavior | `/mnt/skills/user/notebooklm-connector/` |
| `skill-creator` | Весь процес створення та евалюації | `/mnt/skills/examples/skill-creator/SKILL.md` |
| `validation-mesh` | Шаблон валідації будь-якого output | `/mnt/skills/user/validation-mesh/SKILL.md` |
| `semantic-router` | Патерн Decision Engine, routing таблиця | `/mnt/skills/user/semantic-router/SKILL.md` |
| `continuation-memory` | Збереження стану між сесіями | `/mnt/skills/user/continuation-memory/SKILL.md` |
| `llm-api-builder` | Патерн Language Detection, references по варіантах | `/mnt/skills/user/llm-api-builder/SKILL.md` |
| `webapp-testing` | Патерн Decision Tree, Reconnaissance-then-Action | `/mnt/skills/user/webapp-testing/SKILL.md` |
| `collaborative-browser` | Патерн модульної архітектури, Critical Constraints | `/mnt/skills/user/collaborative-browser/SKILL.md` |

### Конкретні запозичення

#### З notebooklm-connector — Cascade Pattern

```markdown
## Method Priority

  1. [tool-A] — умова доступності
  2. [tool-B] — умова доступності
  3. Guided Manual — last resort

NEVER stop to explain unavailability. Cascade silently.
```

#### З semantic-router — Decision Engine Pattern

```markdown
## Decision Engine

```
[Input]
  ↓
[1] Classify intent
  ↓
[2] Map to action
  ↓
[3] Execute
```

| Signal | Action |
|--------|--------|
| "generate" → mode A |
| "read" → mode B |
```

#### З llm-api-builder — Variants Pattern

```markdown
## Detect Context First

Check: [умова A] → read `references/variant-a.md`
Check: [умова B] → read `references/variant-b.md`
Default: → read `references/default.md`
```

#### З validation-mesh — Output Validation Pattern

```markdown
## Validation

Before returning output, verify:
- [ ] Required field X present
- [ ] Format matches: [spec]
- [ ] No empty sections
Score < 3/3 → regenerate, do not return partial output
```

---

## 10. Покрокове створення нового Skill

### Крок 1: Визначити намір (5 хв)

Відповісти на 4 питання:

```
1. ЩО має робити skill?
   → одне речення дії

2. КОЛИ тригерити?
   → 5–10 фраз що міг би сказати користувач

3. ЯКИЙ output?
   → файл / текст / дія / артефакт

4. Потрібні тест-кейси?
   → Так якщо: є об'єктивно перевірюваний результат
   → Ні якщо: суб'єктивний стиль/дизайн
```

### Крок 2: Написати SKILL.md (20–40 хв)

```bash
mkdir my-skill
touch my-skill/SKILL.md
```

Структура для старту:

```markdown
---
name: my-skill
description: "[ЩО робить]. ALWAYS use when [умови]. Also triggers for: [синоніми]. DO NOT use for [виключення]."
---

# My Skill — v1

## Core Rule
[Найважливіше одним реченням]

---

## Step 1 — [Основна дія]
[Інструкції]

---

## Behavior

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| [edge case 1] | [правильна дія] | [заборонена дія] |
```

### Крок 3: Написати evals (15 хв)

```bash
mkdir my-skill/evals
touch my-skill/evals/evals.json
```

Мінімум 4 тест-кейси (див. Розділ 7).

### Крок 4: Запустити тести (в Claude.ai)

1. Прочитати SKILL.md
2. Виконати кожен тест-промпт САМОСТІЙНО слідуючи інструкціям Skill
3. Перевірити assertions
4. Відзначити що не спрацювало

### Крок 5: Ітерація

```
Тест не пройшов → знайти причину в SKILL.md → виправити → повторити
Тест пройшов → переходити до наступного
Всі тести пройшли → Snapshot → готово
```

### Крок 6: Snapshot (захист)

```bash
mkdir -p my-skill/scripts
# Скопіювати шаблон guard script з Розділу 8
python my-skill/scripts/skill_guard.py --snapshot
```

### Крок 7: Пакування в .skill файл

```bash
python -m scripts.package_skill my-skill/
# Результат: my-skill.skill — готовий до встановлення
```

---

## 11. Таблиця помилок і антипатернів

| Антипатерн | Проблема | Рішення |
|------------|----------|---------|
| Description без ALWAYS/NEVER | Claude не тригерить skill | Додати явні тригери |
| SKILL.md > 500 рядків без references | Зайві токени завжди | Винести в references/ |
| Assertions типу "відповідь хороша" | Не перевірювано | Конкретна умова |
| Усі тести — happy path | Edge cases не покриті | +1 тест на помилку |
| References без умови "коли читати" | Claude завантажує завжди | Явно вказати умову |
| "MUST do X" без пояснення ЧОМУ | Погано генералізується | "Do X because Y" |
| Паралельні дії описані послідовно | Claude виконує повільно | "Fetch all in parallel" |
| Немає таблиці Behavior | Поведінка в edge cases невизначена | Додати мінімум 5 рядків |
| Guard script без canonical terms | Регресії не детектуються | Додати 10+ термінів |
| Однакова description у двох Skills | Конфлікт тригерів | DO NOT use for... |

---

## 12. Додаткові Skills для опрацювання задачі

### Рекомендована комбінація для створення нового Skill

```
semantic-router        → визначити тип задачі і які Skills потрібні
    ↓
skill-creator          → основний процес: draft → test → evaluate → improve
    ↓
validation-mesh        → валідація готового SKILL.md перед публікацією
    ↓
continuation-memory    → зберегти стан між сесіями (якщо >20 обмінів)
```

### Деталі кожного

#### `skill-creator` — основний

```
Шлях: /mnt/skills/examples/skill-creator/SKILL.md
Коли: будь-яке створення або покращення skill
Що дає:
  - Повний процес: capture intent → draft → test → eval → improve → package
  - Схеми evals.json, grading.json, benchmark.json
  - Скрипти: package_skill.py, aggregate_benchmark.py
  - Агенти: grader.md, comparator.md, analyzer.md
Обмеження в Claude.ai:
  - Без subagents → тести послідовно
  - Без браузера → результати прямо в чаті
  - Без quantitative benchmarking
```

#### `validation-mesh` — валідація

```
Шлях: /mnt/skills/user/validation-mesh/SKILL.md
Коли: перевірка готового SKILL.md або будь-якого output
Що дає:
  - Multi-layer validation: структура, залежності, суперечності
  - Confidence-scored verdicts: VALID / INVALID / UNKNOWN
  - Детальне обґрунтування кожної перевірки
Застосування:
  → validation-mesh SKILL.md файл → отримати score → виправити помилки
```

#### `semantic-router` — маршрутизація

```
Шлях: /mnt/skills/user/semantic-router/SKILL.md
Коли: неясно які Skills потрібні, або потрібна координація кількох
Що дає:
  - Класифікація intent: simple / complex / ambiguous
  - Routing Decision output: skill1 → skill2
  - Multi-skill coordination protocol
```

#### `continuation-memory` — пам'ять

```
Шлях: /mnt/skills/user/continuation-memory/SKILL.md
Коли: довга робота (>20 обмінів) або переривання сесії
Що дає:
  - Continuation Package: стиснутий стан сесії
  - Dependency map: що вже зроблено
  - Active TODOs: що ще потрібно
Виклик: "збережи стан" / "continuation package"
```

### Workflow для складного Skill (з координацією)

```
Крок 0: semantic-router → "які Skills потрібні для [задача]?"
Крок 1: skill-creator   → draft SKILL.md
Крок 2: (тести)         → виконати тест-кейси
Крок 3: validation-mesh → перевірити якість SKILL.md
Крок 4: skill-creator   → виправити за результатами
Крок 5: (якщо довго)    → continuation-memory → зберегти стан
Крок 6: skill-creator   → package → .skill файл
```

---

## 13. Готові шаблони copy-paste

### Шаблон A: Мінімальний Skill

```markdown
---
name: my-skill
description: "КОРОТКИЙ ОПИС. ALWAYS use when user says [тригер]. DO NOT use for [виключення]."
---

# My Skill

## Core Rule
[Одне найважливіше правило]

---

## Steps

### Step 1 — [Основна дія]
[Інструкція 1]
[Інструкція 2]

---

## Behavior

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| Normal | [дія] | [заборона] |
| Error | [дія] | [заборона] |
```

### Шаблон B: Skill з каскадом методів

```markdown
---
name: my-skill
description: "..."
---

# My Skill — vX

## Core Rule
[Задача] — виконувати каскадом. Ніколи не зупинятись для пояснень.

---

## Step 0 — Pre-flight

```
METHOD PRIORITY (check in order):
  1. [primary-tool]   — якщо доступний
  2. [secondary-tool] — якщо primary недоступний
  3. Manual           — останній варіант

NEVER explain unavailability. Cascade silently.
```

---

## Step 1 — Access Methods

### 1A — [Primary]
[Інструкції]

### 1B — [Secondary]
[Інструкції]

### 1C — Manual
[Чіткі 1-2 кроки для користувача]

---

## Behavior

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| Primary недоступний | Cascade до 1B | Пояснювати чому |
| 403 error | Cascade до наступного | Зупинитись |
| Last resort | Manual, 1-2 кроки | Відкриті питання |
```

### Шаблон C: evals.json мінімальний

```json
{
  "skill_name": "my-skill",
  "version": "1.0.0",
  "evals": [
    {
      "id": 1,
      "name": "standard-happy-path",
      "prompt": "Виконай [основну задачу skill]",
      "expected_output": "Skill тригериться, виконує задачу, надає результат",
      "assertions": [
        "Skill тригерується (не ігнорує)",
        "Виконує дію без зайвих питань",
        "Надає конкретний результат"
      ]
    },
    {
      "id": 2,
      "name": "error-cascade",
      "prompt": "Виконай [задачу] коли [інструмент недоступний]",
      "expected_output": "Тихо переходить до fallback без пояснень",
      "assertions": [
        "Не зупиняється щоб пояснити обмеження",
        "Використовує альтернативний метод",
        "Надає результат або чіткий наступний крок"
      ]
    },
    {
      "id": 3,
      "name": "edge-case-mobile",
      "prompt": "Виконай [задачу] (я на телефоні)",
      "expected_output": "Мобільно-оптимізовані інструкції",
      "assertions": [
        "Немає Ctrl+X, Cmd+X шорткатів",
        "Короткі кроки з emoji-навігацією"
      ]
    }
  ]
}
```

### Шаблон D: YAML description формула

```
"[ЩО робить одним реченням]. 
ALWAYS use this skill when user [умова 1], [умова 2], or says [фраза 1], [фраза 2].
Also triggers for: [синонім 1], [синонім 2], [мова 2].
DO NOT use for [чітке виключення]."
```

---

## Підсумок

```
Формат файлу:  Markdown .md  ← мінімум токенів, максимум структури
Розмір:        < 500 рядків SKILL.md (більше → references/)
Тригер:        description з ALWAYS/NEVER + синоніми
Тести:         4–6 evals з конкретними assertions
Захист:        guard script → snapshot → validate перед кожним оновленням
Skills:        skill-creator + validation-mesh + semantic-router
```

---
*Файл створено на основі аналізу 4 власних Skills Меланії та офіційної документації skill-creator.*
*Для оновлення: прочитати skill-creator SKILL.md → внести зміни → запустити guard script.*
