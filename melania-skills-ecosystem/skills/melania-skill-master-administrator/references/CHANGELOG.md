# CHANGELOG — melania-skill-master-administrator
> Автор: Меланія (Master Administrator)
> Формат версій: `major.minor.patch`
> major = breaking change · minor = нова функція · patch = виправлення

## [2.4.0] — 2026-06-02
### Added
- Core Rule 6 (UA-first) та Core Rule 7 (Decision Gate: update-before-create) — наскрізні governance-гейти.
- `evals/evals.json` — 6 кейсів (Law I, MA workflow, Self-Dev, version bump, governance gates, DO-NOT). _(аудит P-03)_
### Fixed
- Заголовок CHANGELOG і докстрінг guard виправлено зі 'skill-creation-guide' на 'melania'. _(аудит P-08)_

---

## [2.0.0] — 2026-05-27

### Added
- ⚡ **Master Administrator Protocol** — Меланія як єдина особа з правами на зміни
  - 9 тригерних фраз для MA-директив
  - 10-кроковий Update Workflow з підтвердженням
  - Правила: diff перед застосуванням, обов'язковий changelog, version bump
- 🧬 **Self-Development Engine** — автономна само-оцінка після кожного використання
  - Post-Use Assessment: GAP CHECK + PATTERN CHECK + IMPROVEMENT PROPOSAL
  - Стандартний формат Self-Dev Proposal (#N)
  - 6 автоматичних тригерів само-розвитку
  - Правила: пропозиція ≠ зміна, max 3 відкриті, відхилені логуються
- 📋 Структура references/ (full-guide.md, CHANGELOG.md, update-protocol.md)
- 🔖 metadata у frontmatter: version, author, created, last_updated
- Таблиця Skills-координації з MA Update Workflow

### Changed
- version: 1.0.0 → 2.0.0
- Додано `metadata` блок у YAML frontmatter
- Розширено description з MA та Self-Dev тригерами
- Core Rules перейменовано та закріплено як "незмінні без MA-директиви"

### Architecture
```
SKILL.md (222 рядки)
    ├── MA Protocol      ← новий
    ├── Self-Dev Engine  ← новий
    ├── File Structure
    ├── Core Rules
    ├── YAML Frontmatter
    ├── Body Template
    ├── Skills Coordination
    └── References Table
```

---

## [1.0.0] — 2026-05-27

### Added (Initial Release)
- Базова структура SKILL.md
- YAML frontmatter rules
- Шаблон тіла SKILL.md
- evals.json мінімальний шаблон
- Таблиця Skills для координації (skill-creator, validation-mesh, semantic-router, continuation-memory)
- Посилання на references/full-guide.md

---

## Pending Proposals
> Пропозиції від Self-Development Engine. Статус: ⏳ очікують рішення MA.

*(порожньо — нових пропозицій немає)*

---

## Rejected Proposals
> Відхилені MA пропозиції зберігаються тут як навчальний матеріал.

*(порожньо)*

---

## Шаблон для нових записів

```markdown
## [X.Y.Z] — YYYY-MM-DD

### Added / Changed / Fixed / Removed
- [опис зміни]

### Причина (MA-директива або Self-Dev Proposal #N)
[текст директиви або номер пропозиції]
```

## Шаблон Self-Dev Proposal

```markdown
## 🔄 Self-Dev Proposal #N
**Дата:** YYYY-MM-DD
**Тип:** gap / optimization / new-pattern / deprecation
**Причина:** [що спровокувало]
**Пропозиція:**
  Секція: [яка]
  Зараз: [поточний стан]
  Пропоную: [нова версія]
**Вплив:** [що покращується, ризики]
**Статус:** ⏳ Очікує рішення MA
```

---

---

## [2.3.0] — 2026-05-27

### Changed — Professional restructure (visual + structural improvement)

**Structural improvements (від ai-core-runtime + semantic-router patterns):**
- Нова секція `## Mission` замінена детальнішою таблицею Three Laws
- `## Command Reference` — повна таблиця команд замість code-block списку
- `## Update Workflow` — ASCII flow-diagram з явними блоками замість нумерованого списку
- `## Post-Use Assessment` — структурований checklist замість prose
- `## Proposal Format` — fenced block із усіма полями
- `## File Structure` — дерево з коментарями для кожного файлу
- `## YAML Frontmatter` — повний шаблон з коментарями inline
- `## SKILL.md Body Template` — оновлений шаблон з Core Ethics блоком

**Visual improvements:**
- Емодзі-префікси секцій: ⚖️ ⚡ 🧬 📐 📁 🧩 📋 🔗 📚
- Таблиці замість prose-списків скрізь де можливо
- Поле `description` → multiline `>` (читабельніше, відповідає ai-core-runtime стандарту)
- `category: skill-governance` додано до metadata
- Auto-Triggers у Self-Dev → чітка таблиця
- Full pipeline у Skills Coordination → flow рядок
- References → таблиця з умовами + правило "never load proactively"

**Guard script:**
- `when_to_use` (поле не в тілі SKILL.md) → замінено на `semantic-router`
- 15 canonical terms збережено

### Stats
```
v2.2  244 рядки  →  v2.3  332 рядки  (+88 рядків структури та шаблонів)
MD5: 75f42778a25f310b
```


---

## [2.2.0] — 2026-05-27

### Added — GitHub Analysis (anthropics/skills) + MA directive

- 🌐 **Agent Skills Spec compliance** (Issue #249 fix analog):
  - `when_to_use` — офіційне поле spec, точніший тригер ніж description alone
  - `compatibility` — вимоги середовища (cross-platform note: Claude Code, Codex, Cursor)
  - `allowed-tools` — декларація необхідних інструментів (Bash(python:*), Read, Write)
  - `hooks` — автозапуск guard: pre-edit → --validate, post-edit → --snapshot
  - `license: Proprietary`
- 🤖 **Skills-координація розширена** (+2 нові):
  - `ai-core-runtime v3.1` — мікроядро MA Protocol, bounded reasoning, token-efficient
  - `n8n-orchestrator v2.3` — автоматизація MA workflows, webhook trigger, guard CI
  - Оновлено workflow рядок: semantic-router → ai-core-runtime → validation-mesh → n8n-orchestrator
- 🛡 **Guard script** — 4 нових canonical terms: when_to_use, compatibility, ai-core-runtime, n8n-orchestrator (всього 15)

### Research Source
- github.com/anthropics/skills (117k ★) — офіційна spec + Issue #249
- github.com/ComposioHQ/awesome-claude-skills — ecosystem patterns
- agentskills.io — spec fields reference (32 агенти підтримують стандарт)

### Changed
- version: 2.1.0 → 2.2.0
- metadata.last_updated: 2026-05-27
- Frontmatter: +6 нових полів відповідно до Agent Skills Spec



## [2.1.0] — 2026-05-27

### Added — MA-директива: "інтегрувати три закони в ядро"

- ⚖️ **Core Ethics — Три Закони Роботехніки** (Азімов) інтегровано як **незмінне ядро**
  - Закон I: Не нашкодити людині — абсолютний пріоритет
  - Закон II: Підкоряться MA-директивам — якщо не суперечить Закону I
  - Закон III: Self-Development зберігає себе — якщо не суперечить I та II
- Нова ієрархія пріоритетів: `Закон I > II > III > MA Protocol > Self-Dev > Core Rules`
- Таблиця застосування Законів до операцій Skill
- Приклади блокування (Закон I): видалення безпеки, ігнорування помилок, зниження якості evals
- Незмінні правила Ядра (6 правил НІКОЛИ + 1 ЗАВЖДИ) під захистом Закону I
- Крок [0] у Update Workflow: перевірка Закону I перед будь-якою MA-командою
- Оновлено шаблон тіла SKILL.md: новий optional блок `## Core Ethics`
- Оновлено Skills-координацію: додано `[Закон I check]` у workflow рядок
- Три Закони додано до тригерів description: `три закони, закони роботехніки`

### Changed
- version: 2.0.0 → 2.1.0
- Заголовок: v2.0 → v2.1
- metadata.last_updated: 2026-05-27

### Architecture після v2.1
```
SKILL.md (233 рядки)
    ├── ⚖️  Core Ethics — Три Закони  ← НОВИЙ (незмінне ядро)
    ├── ⚡  MA Protocol
    ├── 🧬  Self-Development Engine
    ├── Core Rules
    ├── File Structure
    ├── YAML Frontmatter
    ├── Body Template (з Core Ethics блоком)
    ├── Skills Coordination (з Закон I check)
    └── References Table
```

- **v2.6.0** (2026-06-02) — Core Rule 10: завжди перечитувати актуальний стан з диску перед оновленням (реєстр живий, паралельні зміни).

- **v2.9.0** (2026-06-12) — Chokepoint enforcement: `safety-compliance-gate` обов'язковий перед пакуванням/публікацією/комерціалізацією (BLOCKED поки не пройдено); гейт додано у Skills Coordination. _(Harvest Vercel MCP → Proposal #7. Записи v2.7–v2.8 — див. SKILL.md «Зміни».)_
