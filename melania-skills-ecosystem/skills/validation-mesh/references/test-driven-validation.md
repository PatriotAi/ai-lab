# Test-Driven Validation

## Regression Suite Pattern

Перед кожним deploy — прогон фіксованого набору перевірок:

```python
REGRESSION_CHECKS = [
    {"name": "no_hardcoded_secrets", "fn": check_secrets, "severity": "critical"},
    {"name": "all_imports_resolve",  "fn": check_imports, "severity": "critical"},
    {"name": "no_circular_deps",     "fn": check_cycles,  "severity": "high"},
    {"name": "schema_valid",         "fn": check_schema,  "severity": "high"},
    {"name": "naming_consistent",    "fn": check_naming,  "severity": "medium"},
]

def run_regression(artifact):
    results = []
    for check in REGRESSION_CHECKS:
        verdict, detail = check["fn"](artifact)
        results.append({**check, "verdict": verdict, "detail": detail})
    blockers = [r for r in results if r["verdict"]=="INVALID" and r["severity"]=="critical"]
    return {"pass": len(blockers)==0, "results": results, "blockers": blockers}
```

Critical INVALID = блок deploy. Medium = warning, не блокує.

---

## Property-Based Validation

Замість перевірки конкретних значень — перевіряй інваріанти:

```
Інваріанти що мають триматись ЗАВЖДИ:
□ Sum(parts) == total          (узгодженість агрегатів)
□ output.length > 0            (непорожній результат)
□ all(id unique for id in ids) (унікальність ключів)
□ timestamp_out >= timestamp_in (причинність)
□ no orphan references         (цілісність графа)
```

Якщо інваріант порушено на будь-яких даних → INVALID, незалежно від конкретного входу.

---

## Mutation Testing (для перевірки самих тестів)

```
Ідея: внеси навмисну помилку → тести МАЮТЬ її зловити.
Якщо тест проходить навіть з помилкою → тест нічого не перевіряє.

Приклад мутацій:
- замінити == на !=
- замінити + на -
- видалити рядок валідації
- змінити константу (threshold 0.8 → 0.0)

Якщо після мутації всі тести зелені → тест-набір недостатній.
```

---

## Semantic Consistency

Перевірка що зміст узгоджений, не лише синтаксис:

```
□ Назва функції відповідає тому що вона робить?
  (getUser() що видаляє → INVALID семантика)
□ Коментар відповідає коду? (застарілі коментарі = INVALID)
□ Версія в коді == версія в metadata == версія в CHANGELOG?
□ Error message відповідає реальній помилці?
□ Тип повернення відповідає документації?
```

---

## Validation Confidence Calibration

```
Як уникнути over-confident вердиктів:

VALID (0.9+)  лише якщо:
  - є пряме свідчення в наданому контексті
  - перевірено всі залежності
  - немає суперечностей

UNKNOWN  якщо:
  - твердження про зовнішній світ без джерела
  - "має працювати" без перевірки
  - версія/факт з памʼяті, не з контексту

Краще 10 чесних UNKNOWN ніж 1 хибний VALID.
```
