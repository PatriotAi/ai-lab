# Update Protocol — skill-creation-guide
> Детальний протокол для Master Administrator та Self-Development Engine  
> Читати коли: виконується MA-директива або обробляється Self-Dev пропозиція

---

## Part 1 — Master Administrator Commands (деталі)

### Повна таблиця MA-команд

| Команда | Синтаксис | Дія |
|---------|-----------|-----|
| Додати правило | `додати правило: [текст]` | Append до відповідної секції Behavior або Core Rules |
| Змінити секцію | `змінити [назва секції]: [новий текст]` | Replace секції після diff+підтвердження |
| Видалити елемент | `видалити [елемент/секцію]` | Remove після підтвердження |
| Версія | `версія → X.Y.Z` | Bump metadata.version + CHANGELOG |
| Self-dev тригер | `самооновлення: [тема]` | Запустити Assessment на конкретну тему |
| Changelog | `переглянути changelog` | Вивести references/CHANGELOG.md |
| Затвердити | `затвердити пропозицію #N` | Apply Proposal #N → CHANGELOG.md |
| Відхилити | `відхилити пропозицію #N [причина]` | Move до Rejected з причиною |
| Репакування | `перепакувати skill` | Запустити package_skill.py → новий .skill |
| Показати diff | `показати diff [секція]` | Вивести до/після без застосування |
| Скинути версію | `rollback до v[X.Y.Z]` | Відновити зі snapshot (якщо є) |

### Правила безпеки MA Protocol

```
ЗАБОРОНЕНО без підтвердження MA:
  ✗ Застосовувати будь-яку зміну до SKILL.md
  ✗ Видаляти canonical terms (guard script їх захищає)
  ✗ Скорочувати Behavior таблицю нижче мінімуму
  ✗ Змінювати name у frontmatter (порушить встановлений skill)
  ✗ Видаляти MA Protocol або Self-Development Engine секції

ОБОВ'ЯЗКОВО при кожній зміні:
  ✓ Показати diff (до/після) перед застосуванням
  ✓ Оновити CHANGELOG.md
  ✓ Bump version (patch мінімум)
  ✓ Оновити metadata.last_updated
  ✓ Перепакувати .skill після підтвердження
```

### Version Bump Rules

```
patch (X.Y.Z → X.Y.Z+1):
  - Виправлення формулювання
  - Додавання прикладу
  - Оновлення посилань

minor (X.Y.Z → X.Y+1.0):
  - Нове правило або патерн
  - Новий reference файл
  - Нова Self-Dev пропозиція затверджена

major (X.Y.Z → X+1.0.0):
  - Breaking change (перейменування секцій)
  - Зміна Core Rules
  - Зміна MA Protocol
  - Повна переробка архітектури
```

---

## Part 2 — Self-Development Engine (деталі)

### Post-Use Assessment Checklist

Після кожного виконання задачі запустити внутрішньо:

```
GAP CHECK (1–2 хв внутрішньо):
  □ Чи запитала людина щось що SKILL.md не покриває?
  □ Чи довелось відповідати поза рамками skill?
  □ Чи виникла двозначність у правилах?
  □ Чи reference файл мав бути але відсутній?

PATTERN CHECK:
  □ Яка секція використовувалась?
  □ Яка секція не знадобилась (потенційно зайва)?
  □ Чи є правило яке спрацювало несподівано добре?
  □ Чи є правило яке ускладнило виконання?

DECISION:
  □ Немає проблем → нічого не генерувати
  □ Є gap/pattern issue → генерувати Proposal
  □ Критична проблема → генерувати Proposal + повідомити MA одразу
```

### Автоматичні тригери (завжди перевіряти)

```python
# Псевдокод перевірок
if question_not_covered_by_skill:
    generate_proposal(type="gap", section="Behavior or new section")

if rule_applied_incorrectly:
    generate_proposal(type="optimization", section=affected_rule)

if reference_needed_but_missing:
    generate_proposal(type="new-pattern", action="create reference file")

if pattern_used_3_plus_times_unchanged:
    generate_proposal(type="optimization", action="move to references/")

if skill_md_lines > 450:
    generate_proposal(type="optimization", action="refactor to references/")

if new_claude_api_feature_detected:
    generate_proposal(type="update", action="update documentation")
```

### Приклад повного Proposal

```markdown
## 🔄 Self-Dev Proposal #1
**Дата:** 2026-05-27
**Тип:** gap
**Причина:** Користувач запитав як мігрувати skill між проектами —
  цього сценарію немає в SKILL.md.
**Пропозиція:**
  Секція: Нова секція "## Migration" після "## Core Rules"
  Зараз: відсутня
  Пропоную: 
    ## Migration
    Копіювати skill-folder → новий проект
    Зберегти name у frontmatter незмінним
    Оновити references/ посилання
    Запустити: python skill_guard.py --validate
**Вплив:** Покриває gap для multi-project workflows. Ризик: +10 рядків.
**Статус:** ⏳ Очікує рішення MA
```

---

## Part 3 — Guard Script (повний код)

```python
#!/usr/bin/env python3
"""skill_guard.py — захист skill-creation-guide від регресій"""
import json, hashlib, sys, re
from pathlib import Path
from datetime import datetime, timezone

SKILL_PATH = Path(__file__).parent.parent / "SKILL.md"
SNAP_PATH = Path(__file__).parent / ".snapshots" / "latest.json"
CHANGELOG_PATH = Path(__file__).parent.parent / "references" / "CHANGELOG.md"

# Канонічні терміни — ОБОВ'ЯЗКОВО присутні в SKILL.md
CANONICAL_TERMS = [
    "Master Administrator",
    "Self-Development Engine",
    "Update Workflow",
    "Post-Use Assessment",
    "GAP CHECK",
    "PATTERN CHECK",
    "IMPROVEMENT PROPOSAL",
    "validation-mesh",
    "CHANGELOG",
    "Core Rules",
    "Behavior",
    "skill-creator",
    "continuation-memory",
]

MIN_BEHAVIOR_ROWS = 5

def get_behavior_rows(text):
    rows = 0
    in_table = False
    for line in text.splitlines():
        if "| Ситуація" in line or "| Умова" in line:
            in_table = True
        elif in_table and line.startswith("|") and "---" not in line:
            rows += 1
        elif in_table and not line.startswith("|"):
            in_table = False
    return rows

def snapshot():
    text = SKILL_PATH.read_text()
    lines = text.splitlines()
    snap = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "md5": hashlib.md5(text.encode()).hexdigest(),
        "total_lines": len(lines),
        "terms": {t: (t in text) for t in CANONICAL_TERMS},
        "behavior_rows": get_behavior_rows(text),
    }
    SNAP_PATH.parent.mkdir(exist_ok=True)
    SNAP_PATH.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
    print(f"✅ Snapshot збережено: {snap['total_lines']} рядків · {snap['behavior_rows']} Behavior рядків")
    print(f"   MD5: {snap['md5']}")

def validate():
    if not SNAP_PATH.exists():
        print("❌ Snapshot відсутній. Запусти: python skill_guard.py --snapshot")
        sys.exit(1)
    snap = json.loads(SNAP_PATH.read_text())
    text = SKILL_PATH.read_text()
    errors, warnings = [], []

    # Перевірка канонічних термінів
    for term, was_present in snap["terms"].items():
        if was_present and term not in text:
            errors.append(f"ВІДСУТНІЙ ТЕРМІН: '{term}'")

    # Перевірка розміру
    current_lines = len(text.splitlines())
    if current_lines < snap["total_lines"] * 0.82:
        errors.append(f"Значне скорочення: {snap['total_lines']} → {current_lines} рядків (>18%)")
    if current_lines > 520:
        warnings.append(f"SKILL.md > 520 рядків ({current_lines}) — розглянь рефакторинг")

    # Перевірка Behavior таблиці
    current_rows = get_behavior_rows(text)
    if current_rows < MIN_BEHAVIOR_ROWS:
        errors.append(f"Behavior таблиця: мінімум {MIN_BEHAVIOR_ROWS} рядків, є {current_rows}")

    # Перевірка MA Protocol
    if "Master Administrator" not in text:
        errors.append("MA Protocol видалено — критична регресія")
    if "Self-Development Engine" not in text:
        errors.append("Self-Dev Engine видалено — критична регресія")

    score = 100 - (len(errors) * 10) - (len(warnings) * 3)
    score = max(0, score)

    if errors:
        print(f"❌ ЗАБЛОКОВАНО — score: {score}/100 — {len(errors)} помилок:")
        for e in errors: print(f"   ✗ {e}")
        if warnings:
            for w in warnings: print(f"   ⚠ {w}")
        sys.exit(1)
    else:
        print(f"✅ Валідація пройшла — score: {score}/100")
        if warnings:
            for w in warnings: print(f"   ⚠ {w}")
        print(f"   Рядків: {current_lines} · Behavior: {current_rows} · Всі canonical terms присутні")

if __name__ == "__main__":
    if "--snapshot" in sys.argv:
        snapshot()
    elif "--validate" in sys.argv:
        validate()
    else:
        print("Використання: --snapshot | --validate")
        print(f"  SKILL.md: {SKILL_PATH}")
        print(f"  Snapshot: {SNAP_PATH}")
```

### Команди guard script

```bash
# Перед редагуванням — завжди:
python scripts/skill_guard.py --validate

# Після завершення редагування:
python scripts/skill_guard.py --snapshot

# При CI/CD або автоматичному оновленні:
python scripts/skill_guard.py --validate || exit 1
```

---

## Part 4 — Packaging

```bash
# Перепакування після оновлення (з кореня workspace):
PYTHONPATH=/path/to/skill-creation-guide-workspace \
python -m scripts.package_skill \
  /path/to/skill-creation-guide/ \
  /output/directory/

# Результат: skill-creation-guide.skill
# Включає: SKILL.md + references/ (без evals/)
```
