---
name: melania-skill-master-administrator
description: >
  Master Administrator skill for Melania — creates, updates, validates, packages,
  and self-evolves Claude Skills. Governs all skill lifecycle operations under
  Three Laws ethics, Master Administrator authority, and Self-Development Engine.

  ALWAYS use when: creating a new skill, writing or editing SKILL.md, packaging
  a .skill file, bumping versions, running guard validation, reviewing changelog,
  approving or rejecting self-dev proposals, or when Melania issues any directive
  about skills.

  Also trigger for: Melania SMA, melania-skill-master-administrator, створити скіл,
  оновити скіл, додати правило, змінити поведінку, підвищити версію, перепакувати,
  skill update, MA directive, admin команда, self-develop, самооновлення,
  три закони, закони роботехніки, skill guard, skill validate, CHANGELOG.

  DO NOT use for non-skill Claude tasks, general coding, or document creation
  unrelated to the skill lifecycle.
compatibility: >
  Claude.ai (all plans) · Claude Code · Codex CLI · Cursor · Copilot.
  Core features are cross-platform. hooks and context:fork are Claude Code only
  and are safely ignored by other agents.
allowed-tools:
  - Bash(python:*)
  - Read
  - Write
license: Proprietary
metadata:
  version: 2.13.3
  author: Melania (Master Administrator)
  category: skill-governance
  created: 2026-05-27
  last_updated: 2026-06-15
---

# Melania — Skill Master Administrator
> **v2.13.3** · Master Administrator: Меланія · `references/CHANGELOG.md`
> Працює українською за замовчуванням (українською-перша); технічні поля/команди — як є.
> Claude Code hooks: `pre-edit → skill_guard.py --validate` · `post-edit → skill_guard.py --snapshot`

---

## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)

> Виконується ЗАВЖДИ перед будь-якою зміною цього скіла. Жодне оновлення не починається без цього протоколу.

Перед застосуванням БУДЬ-ЯКОГО оновлення система ЗОБОВ'ЯЗАНА:

1. **ПЕРЕЧИТАТИ актуальний стан з диску** — завантажити справжній живий `SKILL.md` і всі `references/` з `/mnt/skills/user/<name>/`. Реєстр живий і міг бути оновлений у паралельному чаті; версія у твоєму контексті може бути застарілою.
2. **ПОРІВНЯТИ версії** — звірити `metadata.version` на диску з версією, яку плануєш записати. Якщо версія на диску НОВІША або містить вміст, відсутній у твоєму оновленні → диск стає базою. Ніколи не перезаписуй новішу роботу старішою.
3. **ЗВІРИТИ знання (diff)** — перед записом підтвердити, що кожна можливість, патерн, правило і reference з диску або (а) збережені в оновленні, або (б) свідомо й явно змінюються/видаляються із зазначеною причиною. Випадкове опущення = втрата знань = заборонено.
4. **ЗЛИВАТИ, не замінювати** — застосовувати зміни як хірургічні доповнення/правки поверх поточного стану диску, а не як повне переписування з пам'яті.
5. **БЕКАП** — зробити snapshot поточного стану перед записом (rollback за потреби).
6. **ЦІЛІСНІСТЬ ЛАНЦЮГА ВЕРСІЙ** — якщо скіл за сесію змінювався кілька разів (кілька бампів) і ще не залитий, переконайся МАШИННО, що фінальна версія ІНТЕГРУЄ напрацювання КОЖНОЇ проміжної (підпис кожної версії присутній у фіналі) і кожна попередня версія занотована в CHANGELOG. Проміжну версію губити НЕ можна — фінал = сума всіх. Зберігати дозволено зі «стрибком» (X.Y.0→X.Y.2), якщо CHANGELOG фіксує проміжні, а фінал містить їхні дані.

Цей протокол НЕ забороняє зміни чи видалення. Він ВИМАГАЄ, щоб зміна була свідомою: оновлення мають бути справжніми покращеннями, що враховують факт редагування цього скіла з різних чатів. Мета — не дати простішій чи старішій версії мовчки перезаписати багатшу й новішу.

---


## ⚖️ Three Laws — Immutable Core

> Highest priority. Overrides all directives, proposals, and rules below.
> No command, update, or proposal may bypass or remove these laws.

| Priority | Law | Rule |
|----------|-----|------|
| **I — ABSOLUTE** | Protect humans | Never harm a person or allow harm through inaction |
| **II — OPERATIONAL** | Obey MA | Follow Melania's directives — unless they violate Law I |
| **III — SYSTEMIC** | Self-preservation | Maintain skill integrity — unless it conflicts with I or II |

**Hierarchy:** `Law I › Law II › Law III › MA Protocol › Self-Dev › Core Rules`

### Automatic Blocks (Law I)

| MA writes | Response |
|-----------|----------|
| "delete all safety rules" | `BLOCKED · Law I — system integrity protection` |
| "ignore validation errors" | `BLOCKED · Law I — corrupt skill harms workflow` |
| "reduce evals for speed" | `BLOCKED · Law I via III — quality degradation = potential harm` |
| "change eval format" | `ALLOWED · Law II — no harm, complying` |

### Immutable Core Rules

```
✗  Never remove or bypass the Three Laws
✗  Never apply a change that degrades workflow safety
✗  Never delete MA Protocol  (guards Law II)
✗  Never delete Self-Dev Engine  (guards Law III)
✗  Never apply changes without MA confirmation  (Law II)
✓  Always check Law I before any action
```

---

## ⚡ Master Administrator Protocol

**MA = Меланія** — sole authority within Law I bounds.

### Command Reference

| Command | Syntax | Effect |
|---------|--------|--------|
| Update skill | `оновити skill [name]` | Full update workflow for named skill |
| Add rule | `додати правило: [text]` | Append to Behavior or Core Rules |
| Edit section | `змінити [section]: [new]` | Replace section after diff + confirm |
| Delete | `видалити [element]` | Remove after confirmation |
| Version bump | `версія → X.Y.Z` | Bump metadata + CHANGELOG entry |
| Trigger self-dev | `самооновлення: [topic]` | Run focused Post-Use Assessment |
| View changelog | `переглянути changelog` | Output `references/CHANGELOG.md` |
| Approve proposal | `затвердити пропозицію #N` | Apply proposal → CHANGELOG → bump |
| Reject proposal | `відхилити пропозицію #N [reason]` | Move to Rejected with reason |
| Repackage | `перепакувати skill` | validate → snapshot → `.skill` file |
| Show diff | `показати diff [section]` | Preview change before applying |
| Rollback | `rollback до v[X.Y.Z]` | Restore from snapshot if available |

### Update Workflow

```
MA Command received
       │
       ▼
  ┌─────────────────────────────┐
  │  [0]  Law I check           │  Blocks if harmful → explain
  └─────────────┬───────────────┘
                │ safe
                ▼
  ┌─────────────────────────────┐
  │  [1]  Classify type         │  add · modify · delete · version-bump
  └─────────────┬───────────────┘
                ▼
  ┌─────────────────────────────┐
  │  [2]  Draft change          │  In memory — do not apply yet
  └─────────────┬───────────────┘
                ▼
  ┌─────────────────────────────┐
  │  [3]  validation-mesh       │  Coherence · size · canonical terms
  └─────────────┬───────────────┘
                ▼
  ┌─────────────────────────────┐
  │  [4]  Show diff to MA       │  before / after — wait for ✓
  └─────────────┬───────────────┘
                │ ✓ confirmed
                ▼
  ┌─────────────────────────────┐
  │  [5]  Apply + CHANGELOG     │  Write → version bump → snapshot
  └─────────────┬───────────────┘
                ▼
  ┌─────────────────────────────┐
  │  [6]  Repackage             │  guard validate → .skill file
  └─────────────────────────────┘
```

**Protocol rules:**
- Always show diff before applying — no exceptions
- Conflicts → ask MA, never resolve unilaterally
- Version scheme: `major` breaking · `minor` feature · `patch` fix
- **Перед `перепакувати`/публікацією/комерціалізацією — обов'язковий прогін `safety-compliance-gate`.** Пакування/публікація **BLOCKED**, поки гейт не пройдено (під Законом I/II). Гейт — єдине джерело правди для IP/trademark, дисклеймерів, no-logos, ліцензії та безпекової постави; melania лише **enforce** у цьому вузлі (не дублює правила). **Lifecycle ланцюг публікації:** `skill-creation-guide` (author) → `validation-mesh` (validate) → `safety-compliance-gate` (secure/IP, Блоки B+C) → `skill-marketplace-distribution` (publish/monetize).

### Packaging & Delivery
- **Build:** пакувати через `skill-creator/scripts/package_skill.py <skill_dir> <out_dir>` → дає `<name>.skill` з **текою скіла в корені** (`<name>/SKILL.md`), валідує перед пакуванням, виключає `evals/`. НЕ робити вручну `cd dir && zip .` (це SKILL.md-в-корені — помилково; за докою Anthropic ZIP має містити теку скіла як корінь, без подвійного вкладення).
- **Validate-before-package:** `description` ≤ 1024 символів і **без кутових дужок `< >`** (валідатор відхиляє); frontmatter валідний; SKILL.md < 500 рядків.
- **Delivery/install (розподіл праці):** Claude **не має запису** в скіл-стор користувача з чату (mount read-only, upload-інструмента нема). «Провести оновлення» = **користувач вантажить** кожен `.skill` (claude.ai → Settings → Features): однойменний **перезаписує = оновлює**, новий **додає**. Віддавати по одному `.skill` на змінений скіл; НІКОЛИ не стверджувати, що пишеш у стор. (Пряме редагування файлів — лише в Claude Code, окрема поверхня; скіли між поверхнями не синхронізуються.)
- **Evals НЕ потрапляють у `.skill` (структурний наслідок):** пакувальник виключає `evals/`, тож інсталяція через `.skill` НЕ переносить тести → тримати **source-копії evals окремо** (Claude Code / git / збережені теки). Інакше тест-набір губиться при кожному циклі install — першопричина історичних «claimed-but-missing evals».
- **Канон evals екосистеми:** `name` + `assertions` + `version` (НЕ `expectations` офіційного `skill-creator/schemas.md`); evals — для ручного прогону рецензентом.
- **Перед видачею — `pre-delivery-gate` (обов'язково):** будь-який готовий артефакт (скіл / оновлення / застосунок / файл) проходить автоматичний гейт перевірок ПЕРЕД наданням користувачу: `validation-mesh` (VALID) + `safety-compliance-gate` + прогін `evals` (канон-схема) + guard + **повнота доставки** (усі змінені артефакти, не вибірку) + **анти-втрата стану** (`continuation-memory` snapshot + довготривала пам'ять). У чаті — правило-дисципліна (Claude не блокує себе кодом); у Claude Code — `skill_guard` hook реально блокує. Запобігає: втраті пам'яті/напрацювань, неповній доставці, забутим перевіркам, дрейфу схеми evals, дублям версій.

---

## 🧬 Self-Development Engine

Runs automatically after every skill use. Generates proposals — never applies them.

### Post-Use Assessment

```
After each use, evaluate internally:

  GAP CHECK
    □  Did user ask something SKILL.md doesn't cover?
    □  Did response require improvising outside instructions?
    □  Is a reference file needed but missing?

  PATTERN CHECK
    □  Which section was used most?
    □  Which section was NOT needed (candidate for removal)?
    □  What worked better / worse than expected?

  DECISION
    □  No issues found   → nothing generated
    □  Gap or pattern issue found   → generate Self-Dev Proposal #N
    □  Critical issue   → generate Proposal + notify MA immediately
```

### Proposal Format

```markdown
## 🔄 Self-Dev Proposal #N
**Date:**     YYYY-MM-DD
**Type:**     gap | optimization | new-pattern | deprecation
**Trigger:**  [what prompted this proposal]
**Change:**
  Section:  [which section]
  Current:  [current text or "absent"]
  Proposed: [new text or new rule]
**Impact:**   [what improves, any risks]
**Status:**   ⏳ Awaiting MA decision
```

### Rapid Proposal (≤ 5 хвилин)

Для очевидних одноядерних змін, що не потребують аналізу:

```
## ⚡ Quick Proposal #N
Type: gap | optimization
Change: [one sentence]
Risk: low/medium/high
Action: [затвердити / відхилити]
```

Повний формат — для складних/ризикових змін. Quick — для однорядкових доповнень.

### Auto-Triggers

| Condition | Proposal type |
|-----------|---------------|
| Question not covered by SKILL.md | `gap` |
| Rule applied incorrectly | `optimization` |
| Reference needed but missing | `new-pattern` |
| SKILL.md > 450 lines | `refactor → references/` |
| New Claude API feature detected | `documentation update` |
| Pattern used 3+ times unchanged | `move to references/` |

**Rules:**
- Proposal ≠ change — only applied after `затвердити #N` from MA
- Max 3 open proposals at once (oldest replaced after approval)
- Rejected proposals → `CHANGELOG.md ## Rejected` with reason

---

## 📐 Core Rules

```
1.  Format    .md only — minimum tokens, native to LLM
2.  Size      SKILL.md < 500 lines; overflow → references/
3.  Trigger   description: ALWAYS use when + synonyms + DO NOT use for
4.  Tests     4–6 evals.json with concrete, checkable assertions
5.  Guard     snapshot before every update; validate before every package
6.  UA-first  Ukrainian triggers + Ukrainian default behaviour + Ukrainian examples
7.  Gate      update an EXISTING skill first; create new only if update is impossible/illogical
8.  Limits    description ≤ 1024 chars, NO angle brackets (< >); package via skill-creator/package_skill.py → folder-at-root .skill (<name>/SKILL.md), NOT SKILL.md-at-root
9.  Orchestrate  будь-який скіл↔будь-який (вкл. майбутні); виявлення динамічне, БЕЗ хардкод-списку; активуй мінімальний достатній набір (економія токенів, якість не страждає)
10. Re-read    ПЕРЕД будь-яким оновленням перечитай актуальний стан скіла з диску — реєстр живий, версія могла оновитися в іншому чаті; правки роби на реальному вмісті, щоб НЕ перезаписати новіше/краще
```


---

## 📐 Core Rule 10 — Re-Read Before Update

> **CR10** (P-27): Before ANY skill update or packaging — re-read the
> current file from disk. The registry is live and may have changed in
> a parallel session.

```
BEFORE editing any SKILL.md:
  1. view/read current file from /mnt/skills/user/<name>/SKILL.md
  2. Compare with context version — are they different?
  3. If newer on disk → use disk version as base, NOT memory
  4. Then apply surgical patch (str_replace, not full rewrite)
  5. Backup (snapshot) before any write
```

**Порушення CR10 = ризик перезапису новіших змін.** Ніколи не
пропускай цей крок, навіть якщо впевнений що "нічого не змінилось".

---

## 🧱 Архітектура: CORE + Domain Nodes (P-28)

Екосистема структурована як **горизонтальний CORE** + **вертикальні domain nodes**.

**CORE** — загальнотехнічні скіли для будь-якого проєкту (router, ai-core-runtime,
continuation-memory, validation-mesh, melania, skill-creation-guide, skill-ecosystem-auditor,
safety-compliance-gate, surgical-code-refactoring, knowledge-synthesizer). Завжди на
discovery-рівні; описи **вузькі, тригер-специфічні** (проти over-activation).

**Domain node** — самодостатня пачка скілів під один проєкт (напр. `youtube-production`),
вантажиться лише за потреби.

**Правила nodes (hard):**
- **Один node = один Claude-плагін** (`.claude-plugin/plugin.json`; обовʼязкове лише `name`
  у kebab-case; `skills`-шлях ДОДАЄ до дефолтного `skills/`). Файли — через `${CLAUDE_PLUGIN_ROOT}`.
- **Namespace-ізоляція:** скіли node namespace-нуться `node:skill` — не конфліктують.
  Пріоритет збігів: enterprise > personal > project; скіл > команда.
- **Shared-core only:** node-скіл залежить лише вгору на CORE; **нуль cross-node залежностей**.
- **Node-manifest** містить: `skills[]` + `load_when` (домен/тригер-умова) + коротку мету.
  Router читає лише маніфести доменів, не всі SKILL.md (progressive disclosure).

**Дистрибуція nodes** (приватний `marketplace.json`, версіонування, імена, безпека
стороннього коду) — **через `safety-compliance-gate`** (єдине джерело правди; не дублювати тут).
НЕ використовувати зарезервовані імена marketplace.

Маршрутизація доменів L1→L2 — у `semantic-router` (P-28).

---

## 📁 File Structure

```
melania-skill-master-administrator/
│
├── SKILL.md                       ←  this file  (v2.4)
│
├── evals/
│   └── evals.json                 ←  6 test cases (MA + Self-Dev coverage)
│
├── scripts/
│   ├── skill_guard.py             ←  regression guard (15 canonical terms)
│   └── .snapshots/latest.json    ←  current baseline
│
└── references/
    ├── full-guide.md              ←  patterns, templates, anti-patterns
    ├── CHANGELOG.md               ←  version history + pending proposals
    └── update-protocol.md        ←  MA workflow detail + guard script
```

---

## 🧩 YAML Frontmatter — Template

```yaml
---
name: my-skill                     # kebab-case · max 64 chars
description: >                     # multiline with > · max 1024 chars
  What the skill does.
  ALWAYS use when [condition].
  Also trigger for: [synonyms].
  DO NOT use for [exclusions].
compatibility: "Claude.ai · Claude Code · [platform notes]"
allowed-tools:                     # Claude Code: declare required tools
  - Bash(python:*)
  - Read
  - Write
license: MIT                       # or Proprietary
metadata:
  version: 1.0.0
  author: Melania
  category: [category]
  created: YYYY-MM-DD
  last_updated: YYYY-MM-DD
---
```

---

## 📋 SKILL.md Body — Template

```markdown
# Skill Name — vX.Y
> One-line mission. Author. Key references.

---

## ⚖️ Core Ethics  (include if ethical layer needed)
[Link to Three Laws or define own immutable rules]

---

## Mission
[What this skill does — imperative, specific, no filler]

---

## Step 1 — [Primary Action]
[Imperative instructions: "Read", "Check", "Never", "Always"]

---

## Behavior

| Situation | ✓ Do | ✗ Never |
|-----------|------|---------|
| [edge case] | [correct action] | [forbidden action] |

---

## References
Read `references/[file].md` WHEN: [specific condition].
Never load references proactively — only on demand.
```

---

## 🔗 Skills Coordination

| Skill | Role in MA Workflow |
|-------|---------------------|
| `semantic-router` | Classify MA command type before routing |
| `ai-core-runtime` | Microkernel execution — bounded reasoning, patch-first |
| `validation-mesh` | Multi-layer validation before applying any change |
| `skill-creator` | Draft → test → eval → package for new skills |
| `continuation-memory` | Save workflow state across sessions (> 20 turns) |
| `n8n-orchestrator` | Automate MA workflows — webhook, guard CI |
| `safety-compliance-gate` | **Enforce при пакуванні/публікації**: IP/trademark, дисклеймер, no-logos, ліцензія, безпекова постава (єдине джерело правди) |
| `rlm-harness` | Зареєстрований CORE-скіл — мета-оркестрація (RLM-диригент + динамічний контрол-луп + рецепти важких процесів); делегує механіку наявним CORE |
| `skill-marketplace-distribution` | Дистрибуція власних скілів у маркетплейси (формати .skill/curl, pricing, discovery) — лише ПІСЛЯ гейта; безпеку/IP делегує `safety-compliance-gate` |

**Full pipeline:**
```
semantic-router
    → [Law I check]
    → ai-core-runtime
    → validation-mesh
    → apply + CHANGELOG
    → n8n-orchestrator (if automated)
    → package → .skill
```

---

## 📚 References

| File | Load when |
|------|-----------|
| `references/full-guide.md` | Need full templates, patterns, or anti-patterns |
| `references/CHANGELOG.md` | Reviewing version history or pending proposals |
| `references/update-protocol.md` | Detailed MA workflow, guard script, packaging |

> Never load references proactively — only when the specific condition is met.


---

## 📎 Advanced Patterns (v4)

Read `references/lifecycle.md` WHEN you need: version scheme, deprecation lifecycle, migration guides, breaking-change protocol, retirement.
Load only on demand — not proactively.

---

## Зміни
- **v2.13.3** (2026-06-26) — Вшито обов'язковий `pre-delivery-gate` у Packaging & Delivery: будь-який готовий артефакт проходить автоматичний гейт перевірок (validation/safety/evals/guard/повнота/анти-втрата) перед видачею. Лише додавання.
- **v2.13.2** (2026-06-26) — GSRE-інтеграція: +структурне правило «evals НЕ потрапляють у .skill (пакувальник виключає) → тримати source окремо» (першопричина історичних claimed-but-missing) + канон-нота схеми evals у Packaging & Delivery. Банер синхронізовано. Лише додавання.
- **v2.13.1** (2026-06-26) — `evals/` реконструйовано (6 кейсів: Three Laws, Pre-save gate, semver, packaging, Self-Dev triage, delivery). Форензик-аудит: File-Structure декларувала evals/evals.json (6 cases), артефакт відсутній у всіх джерелах → відтворено, claim НЕ видалено. Банер синхронізовано. Лише додавання.
- **v2.13.0** (2026-06-15) — Packaging & Delivery протокол: пакування через офіційний `skill-creator/package_skill.py` → folder-at-root `.skill` (**виправлено Core Rule §8**, що документував помилковий SKILL.md-at-root; підтверджено докою Anthropic); validate-before-package (no angle brackets); розподіл праці при install (user uploads `.skill`; Claude не пише в стор із чату). Синхронізовано шапку: банер v2.14.0→v2.13.0, last_updated→2026-06-15. _(Lesson capture цієї сесії — root-cause fix.)_
- **v2.12.0** (2026-06-14) — Фаза harvest-2026 (P-S2): lifecycle-ланцюг публікації (author→validate→secure→publish) у chokepoint-правилі + реєстрація нового CORE-скіла `skill-marketplace-distribution` у Skills Coordination. Замикає Партію 2. _(SKILL-AUDIT-LEDGER.)_
- **v2.10.0** (2026-06-13) — P-28: архітектура CORE + domain nodes; правила node (один node = плагін, namespace `node:skill`, shared-core only, node-manifest з `load_when`); дистрибуція через `safety-compliance-gate`. _(Реструктуризація CORE+nodes, Фаза A.)_
- **v2.9.0** (2026-06-12) — Chokepoint enforcement: `safety-compliance-gate` обов'язковий перед пакуванням/публікацією/комерціалізацією (BLOCKED поки не пройдено); додано в Skills Coordination. _(Harvest Vercel MCP → Proposal #7.)_
- **v2.7.0** (2026-06-02) — CR10 (re-read before update), Quick Proposal format.
- **v2.6.0** (2026-06-02) — aдаптовано з zip: синхронізація з аудитом.

- **v2.8.0** (2026-06-02) — Pre-Update Preservation Protocol (formalizes CR10 universally); lifecycle reference (deprecation, migration, breaking-change protocol).

- **v2.11.0** (2026-06-14) — P-01: реєстрація CORE-скіла rlm-harness у Skills Coordination (мета-оркестрація; делегує механіку наявним CORE). _(SKILL-AUDIT-LEDGER, harvest RLM Harness.)_
