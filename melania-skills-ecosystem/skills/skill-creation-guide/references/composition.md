# Skill Composition & Organization

## Single Responsibility Principle

```
Один скіл = одна чітка відповідальність.

✗ "ai-helper" — робить все (роутинг + валідація + пам'ять + код)
✓ Розбий на: semantic-router + validation-mesh + continuation-memory

Сигнали що скіл робить забагато:
- description має 3+ незв'язані домени
- SKILL.md > 500 рядків навіть після виносу в references
- назва містить "and" / "та" / "helper" / "manager-of-everything"
```

---

## Reference File Organization

```
skill-name/
├── SKILL.md                    ← ядро: workflow + коли що читати (<500 рядків)
└── references/
    ├── advanced-patterns.md    ← глибокі патерни (читати за потреби)
    ├── examples.md             ← повні приклади
    ├── troubleshooting.md      ← типові проблеми + рішення
    └── domain-X.md             ← специфіка домену X
```

**Правило виносу:** якщо секція потрібна не щоразу → references/. SKILL.md містить лише ВКАЗІВКУ коли її читати.

---

## Multi-Domain Skills

```
Коли скіл підтримує кілька варіантів (AWS/GCP/Azure):

cloud-deploy/
├── SKILL.md              ← вибір + спільний workflow
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md

SKILL.md: "Визнач провайдера → читай references/{provider}.md"
Claude читає ЛИШЕ потрібний → економія токенів.
```

---

## Skill Coordination Patterns

```
1. PIPELINE   — A → B → C (вихід одного = вхід наступного)
   semantic-router → ai-core-runtime → validation-mesh

2. PARALLEL   — A ║ B (незалежні, одночасно)
   n8n-orchestrator ║ continuation-memory

3. HUB        — центральний координує листові
   ai-core-runtime → {усі за потреби}

4. GATE       — один валідує всіх
   будь-що → validation-mesh (перед deploy)
```

Описуй координацію в секції "Coordinates with" / "Related Skills".

---

## Progressive Disclosure Levels

```
L1 Metadata (завжди в контексті, ~100 слів)
   → name + description. Єдине що бачить роутер.

L2 SKILL.md body (коли скіл активовано, <500 рядків)
   → workflow, правила, вказівники на references.

L3 References (за потреби, без ліміту)
   → глибокі патерни, приклади, edge cases.

L4 Scripts (виконуються, не читаються)
   → guard, validators, helpers.
```

Кожен рівень завантажується лише коли потрібен. Не клади L3-контент у L2.

---

## Eval Design

```json
// evals/evals.json — 4-6 кейсів що ПЕРЕВІРЯЮТЬ тригеринг + поведінку
{
  "evals": [
    {
      "query": "реалістичний запит користувача",
      "should_trigger": true,
      "assertions": [
        "output містить X",
        "output НЕ містить Y",
        "формат = JSON"
      ]
    },
    {
      "query": "запит що НЕ має тригерити цей скіл",
      "should_trigger": false
    }
  ]
}
```

Включай негативні кейси (should_trigger: false) — інакше не зловиш over-triggering.

---

## Guard Script Pattern

```python
# scripts/skill_guard.py — захист від регресій
CANONICAL_TERMS = ["term1", "term2", ...]  # що МАЄ бути в SKILL.md

def validate(skill_md_path):
    text = open(skill_md_path).read()
    missing = [t for t in CANONICAL_TERMS if t not in text]
    assert not missing, f"Regression: missing {missing}"
    assert len(text.splitlines()) < 500, "SKILL.md too long"
    # перевір frontmatter, версію, тощо
```
