---
name: semantic-router
description: >
  Analyzes user intent and routes requests to the correct skills and
  orchestration flows in the ecosystem; selects the minimal skill set
  and prevents over-activation.

  USE whenever: запит неоднозначний чи багатоскіловий, вибір скіла
  неочевидний, потрібна координація кількох скілів. Also: "який скіл
  використати", "route this request", "intent classification",
  "skill selection", "multi-agent coordination".

  ALWAYS the entry point for multi-skill workflows. Triggers match by
  MEANING (semantic intent) — синоніми й парафрази активують скіл;
  фрази в описі лише приклади, не вичерпний список.

  DO NOT use for: механіка топологій (workflow-orchestration);
  kernel/активація агентів (ai-core-runtime); мета-оркестрація важких
  процесів (rlm-harness); один очевидний скіл — активуй напряму.
license: MIT
metadata:
  author: Prompt Ingeniero Ecosystem
  version: 1.16.0
  category: routing
  last_updated: 2026-07-26
---

# Semantic Router — v1.16.0
> Працює українською за замовчуванням (українською-перша): рішення про маршрут і пояснення — українською; перемикання лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Critical Facts
- **[C] Автотригер навички часто не спрацьовує.** За даними evals, при покладанні лише на автодобір навичка в значній частці кейсів НЕ активується і не дає виграшу над baseline — тоді як завжди-завантажений компактний CORE-індекс + явні тригери дають максимальний pass-rate.
- **[C] Чат не показує точний лічильник токенів.** Платформа не надає ні точної кількості використаних токенів, ні залишку бюджету — статус-рядок може показувати лише ОЦІНКУ використаного, з явною позначкою «оцінка».
- **[C] Зміни промпту/налаштувань не діють заднім числом.** Правки преференсів застосовуються лише в НОВИХ чатах; уже відкритий чат продовжує працювати за старими налаштуваннями, доки їх не вставити повідомленням явно.
- **[C] Постійний «tappable» елемент у чаті створити не можна.** Опційний статус-віджет — це лише знімок (читання диску + оцінка на момент генерації), не жива інтроспекція рантайму й не постійний UI-компонент чату.

---

## Responsibility

Analyze user intent and select the **minimum viable set** of skills and
agents to activate. Prevent over-activation, reduce token waste, and
ensure correct skill composition for complex requests.

---

## Routing Decision Process

```
[User Input]
    ↓
[1] CLASSIFY intent
    → simple / complex / ambiguous
    ↓
[2] DISCOVER skills (динамічно, БЕЗ фіксованого списку)
    → прочитай описи доступних скілів у реєстрі на льоту;
      зістав намір користувача з їхніми тригерами.
      Нові скіли підхоплюються автоматично — список НЕ хардкодиться.
    ↓
[3] MAP to skill(s)
    → мінімальний достатній набір (економія токенів)
    ↓
[4] CHECK for conflicts
    → no contradicting activations
    ↓
[5] ACTIVATE
    → load selected skills progressively (лише потрібні, у потрібній кількості)
    ↓
[6] COORDINATE
    → будь-який скіл може співпрацювати з будь-яким; передавай виходи між ними за потреби
```

---

## Intent Classification

### Simple Tasks (single skill, direct response)
**Signal:** One clear action, one domain, no coordination needed
```
"Generate an n8n webhook workflow"     → n8n-orchestrator only
"Compress this session into a summary" → continuation-memory only
"Validate this JSON schema"            → validation-mesh only
"Design an AI runtime architecture"    → ai-core-runtime only
```

### Complex Tasks (multi-skill coordination)
**Signal:** Multiple domains, sequential or parallel skill use

```
"Build a validated n8n workflow with AI routing"
→ semantic-router → n8n-orchestrator → validation-mesh

"Design an architecture and remember our session"
→ ai-core-runtime → continuation-memory

"Create a full ecosystem with routing and validation"
→ ai-core-runtime → semantic-router → validation-mesh → continuation-memory
```

### Ambiguous Tasks (clarify first or use safest default)
**Signal:** Vague intent, multiple valid interpretations

```
"Help me with my automation"  → ask: "Is this n8n? Another platform?"
"Fix my AI system"            → ask: "What is the system? What is broken?"
"Make it better"              → ask: "Better how? Faster, cleaner, cheaper?"
```

---

## Динамічна оркестрація (БЕЗ фіксованого списку)

**Принцип:** будь-який скіл може співпрацювати з будь-яким — теперішнім чи майбутнім.
Не покладайся на статичний перелік. Виявляй доступні скіли **на льоту** за їхніми
описами/тригерами в реєстрі; нові скіли стають доступними автоматично, без правок цього файлу.

**Економія токенів (обовʼязково):** активуй **лише потрібні** скіли в **потрібній кількості**.
Ніколи не запускай усі підряд. Якщо завдання вирішує один скіл — один і активуй. Якість
результату не знижуй: бракує охоплення → додай ще один скіл; зайве охоплення → прибери.
Мета — мінімальний достатній набір, що дає повний результат.

**Карта нижче — приклади, не вичерпний список.** Вона ілюструє типові маршрути; реальний
вибір завжди через динамічне виявлення (крок [2]).

## Доменна маршрутизація (P-28): L1 домен → L2 скіл

Екосистема = **горизонтальний CORE** (завжди на discovery-рівні) + **вертикальні
domain nodes** (вантажаться при потребі). Маршрут ЗАВЖДИ дворівневий — домен перед скілом:

**L1 — Domain routing.** Спершу визнач ДОМЕН наміру (core-only / youtube-production /
app-building / business-ops / …) динамічно за описами доменів, БЕЗ хардкод-списку (як P-26).
Завантаж **CORE-індекс + маніфест ОДНОГО обраного node**, а не всі SKILL.md.
**L2 — Skill routing.** Уже всередині node обери мінімальний достатній набір скілів.

```
[Намір] → L1: який домен? → load CORE + 1 node-manifest → L2: мін. набір у node → validation-mesh
```

- **Confidence на L1:** ≥ 0.85 → вантаж node без питань; нижче → уточни домен (одне питання).
  Кешуй рішення домену (short-circuit повторних інтентів).
- **CORE завжди доступний** усім доменам; node-скіл НЕ викликає скіли іншого node
  (shared-core only, нуль cross-node залежностей).
- **Handoff CORE↔node і між субагентами — лише typed-context-обʼєкт** (≈200–500 ток.:
  domain, stage, entities, decisions, artifacts_refs), НЕ сира історія. Стан — `continuation-memory`.
- **Формат/реєстр доменів і пакування node** — governance в `melania` (P-28).
  Безпека дистрибуції node — `safety-compliance-gate`.

## Пасивний контекст + тригерні навички (гібрид)
Не покладайся лише на автотригер навичок — евали показують, що при автодоборі навичка часто
**не активується** (значна частка кейсів) і не дає виграшу над baseline, тоді як **завжди-завантажений
компактний індекс** + явні тригери дають максимальний pass-rate.

Тому застосовуй гібрид:
- **Пасивний CORE-індекс** (завжди в контексті, ~100 токенів/навичка): name + «Use when» кожної доступної навички — горизонтальні знання, які мають бути «під рукою» завжди.
- **Тригерні навички** (вантажяться на вимогу): вертикальні дії/процедури з явним, «pushy» описом.
Правило: горизонтальне (знання-довідка) → пасивний індекс; вертикальне (багатокрокова дія) → тригерна навичка.

## Маршрутизація зовнішніх інструментів (MCP-first → CLI-fallback)
Для будь-якої зовнішньої можливості (деплой, пошта, календар, диск, дизайн тощо) дій за пріоритетом:
1. **Зареєстрований MCP-tool** конектора (структуровано, авторизовано) — найвищий пріоритет.
2. **Документований конектор-скіл** (напр. `vercel-mcp-connector`, `notebooklm-connector`) — процедурна експертиза «як ним користуватися».
3. **Офіційний MCP Registry** (`registry.modelcontextprotocol.io` — app-store / single source of truth; backed Anthropic/GitHub/MS) — якщо немає підключеного MCP-tool чи конектор-скіла ДЛЯ задачі: дискавери нового сервера й пропозиція підключення ПЕРШ ніж падати на CLI. Публікація власного MCP-сервера — теж сюди.
4. **Ad-hoc CLI/bash** — лише якщо й у реєстрі нема придатного, або tool впав/повернув помилку.

Fallback на CLI — тільки при miss або помилці tool, не за замовчуванням. Виявлення конекторів **динамічне** (без хардкод-списку). Безпекова постава при роботі з конекторами/зовнішнім входом — `safety-compliance-gate`.

## Skill Routing Map

| User Intent Signal | Primary Skill | Secondary Skill |
|---|---|---|
| "architecture", "design system", "AI runtime" | ai-core-runtime | — |
| "n8n", "workflow", "automation", "webhook" | n8n-orchestrator | validation-mesh |
| "resume", "continue", "memory", "state" | continuation-memory | — |
| "validate", "check", "verify", "review" | validation-mesh | — |
| "route", "orchestrate", "multi-agent" | semantic-router | ai-core-runtime |
| "оркеструй", "найвищий рівень", "важкий процес", "deep research", "security audit", "перепланування", "RLM", "harness" | rlm-harness | workflow-orchestration |
| "розбий на агентів", "subagents", "agent team", "паралельно", "fan-out", вибір топології багатоагентної роботи | workflow-orchestration | ai-core-runtime |
| "створити скіл", "написати SKILL.md", "формат скіла" | skill-creation-guide | melania-skill-master-administrator |
| "оновити скіл", "підвищити версію", "затвердити/package skill" | melania-skill-master-administrator | skill-creation-guide |
| "аудит скілів", "ревізія екосистеми", "онови скіли" | skill-ecosystem-auditor | validation-mesh |
| "skill governance", "версія/CHANGELOG", "MA directive", "три закони" | melania-skill-master-administrator | skill-creation-guide |
| "публікація скіла", "монетизація", "trademark", "дисклеймер", "security gate", "недовірений вхід" | safety-compliance-gate | melania-skill-master-administrator |
| "GitHub", "PR", "pull request", "issues", "CI", "реліз", "слідкуй за PR", "щоб зміни перевірялись самі", "поверни як було", "що з репо" | github-collab | continuation-memory |
| "notebooklm", "обʼєднай джерела", "podcast з документів" | notebooklm-connector | — |
| "vercel", "deploy", "деплой", "build logs", "хостинг", "vercel mcp", "чому впав білд" | vercel-mcp-connector | safety-compliance-gate |
| "відкрий браузер", "спільний браузер", "веб-серфінг з агентом" | collaborative-browser | — |
| "Claude API", "Anthropic SDK", "Agent SDK" | llm-api-builder | — |
| "тест веб-застосунку", "playwright", "screenshot UI" | webapp-testing | — |
| "локальний AI у браузері", "WebLLM", "WebGPU AI", "офлайн модель" | browser-local-ai-webllm | multi-provider-ai-orchestration |
| "оркестрація моделей", "мульти-ключ", "failover", "ротація ключів", "AI gateway" | multi-provider-ai-orchestration | validation-mesh |
| "зробити аплікацію", "PWA", "APK", "інсталювати на смартфон", "авто-оновлення" | pwa-to-android-app | — |
| "не зламай робоче", "хірургічно", "patch not rewrite", "великий файл", "regression check" | surgical-code-refactoring | validation-mesh |
| "авторизуйся", "онови cookie", "сесія протермінувалась", "OAuth", "збережи токен безпечно" | auth-session-manager | collaborative-browser |
| "token efficiency", "compress", "optimize" | ai-core-runtime | continuation-memory |
| Complex build + memory | ai-core-runtime | continuation-memory |
| Complex build + deploy | за платформою: vercel-mcp-connector (Vercel) · n8n-orchestrator (n8n-пайплайн) | validation-mesh |

---

---

## Confidence Scoring

При неоднозначному намірі — вказуй впевненість:

```
Routing Decision:
  Intent: "зроби мені пайплайн з валідацією"
  Scores:
    n8n-orchestrator      → 0.85  ✓ (слово "пайплайн")
    ai-core-runtime       → 0.60  (загальна архітектура?)
    validation-mesh       → 0.40  (вторинна роль)
  Threshold: 0.70 → активуй n8n + validation-mesh як secondary
```

**Правила scoring:**
- ≥ 0.80 → активуй без питань
- 0.50–0.79 → активуй + коментуй вибір
- < 0.50 → уточни у користувача (одне запитання!)

---

## Паралельна Активація

Для незалежних задач — активуй скіли паралельно:

```
"Побудуй n8n workflow І збережи стан сесії"
→ n8n-orchestrator  ║  continuation-memory  (паралельно)
→ validation-mesh  (після обох)
```

**Умова паралельності:** задачі не залежать одна від одної AND
кожна чітко відображається на свій скіл. Якщо є залежність — послідовно.

---

## Critical Rule

**Never activate all skills simultaneously.**

Each active skill consumes context. Activate the minimum required set.
If uncertain — роутер САМ виконує тріаж (він і є канонічна точка входу);
`ai-core-runtime` стартує першим ЛИШЕ як fallback, коли роутер
недоступний/не завантажений.

**Роутер — точка входу щозапиту:** на будь-який змістовний запит роутинг відпрацьовує ПЕРШИМ (тріаж наміру) і піднімає мінімальний достатній ланцюг скілів; тривіальний запит → 0 скілів (зазначити причину). Звіт про активний набір — поіменно (див. P-LS). Щоходовий гарант тріажу — у налаштуваннях MA (читаються щохід); цей скіл робить ланцюг міцним, коли вантажиться.

**Тригери — за значенням (semantic match):** роутер зіставляє НАМІР запиту зі скілами за змістом, не за дослівним збігом; фрази в описах — приклади, не вичерпний список. Користувач не мусить знати «правильні слова» (директива власника, 2026-07-19).

---

## Multi-Skill Coordination Protocol

When two or more skills are needed, use this handoff structure:

```
Skill A: completes its work
    ↓
Router: packages output as input for Skill B
    ↓
Skill B: receives structured context, continues
    ↓
[repeat as needed]
    ↓
validation-mesh: validates final combined output
```

**Never pass raw conversation history between skills.**
Use structured summaries or continuation packages instead.

---

## Routing Output Format

When routing a request, output a brief routing declaration:

```
### Routing Decision
**Intent:** [classified intent in one line]
**Complexity:** Simple / Complex / Ambiguous
**Skills Activated:** [skill1], [skill2]
**Coordination Plan:** [A → B, or parallel]
**Proceeding with:** [primary skill]
```

Then immediately proceed with the primary skill's workflow.

---

## Related Skills

- **ai-core-runtime** — the default runtime; semantic-router coordinates it
- **continuation-memory** — always pair with for long multi-skill sessions
- **validation-mesh** — always pair with for any output that will be deployed
- **n8n-orchestrator** — specific routing for automation workflows
- **skill-creation-guide / melania / skill-ecosystem-auditor** — skill-governance domain (створення, керування, аудит скілів)
- **notebooklm-connector / collaborative-browser / llm-api-builder / webapp-testing** — листові скіли, тепер у Routing Map

---

## 📎 Advanced Patterns (v4)

Read `references/routing-optimization.md` WHEN you need: decision caching, fallback chains, context-aware routing, short-circuit, dependency resolution.
Load only on demand — not proactively.

---

## 📡 Статус-тулбар (реальний час) + виявлення змін (P-LS)

> Робить роботу роутера видимою і ловить зміни в реальному часі. **Увесь статус — українською** (усе, що можна показати UA, показуй UA). НЕ створює постійного UI: лише текст-рядок або згенерований знімок-віджет.

**Кожна змістовна відповідь** починається з компактного статус-рядка (≤1 рядок, ~15–30 ток.):

```
◎ Активні: <скілА, скілБ | 0 — причина> · Доступно: N · Намір: <простий|складний|неоднозн.> · Маршрут: <ланцюг або «прямо»> · Модель: <активна> · ~ток.: <оцінка> · Δ: нема
```

Поля (усі підписи українською):
- **Активні:** ПОІМЕННО скіли, що РЕАЛЬНО виконуються в цьому запиті (мінімальний достатній набір) — НЕ скільки змонтовано. Жоден не потрібен → `0` + причина («поведінковий», «тривіальний»). Головне поле.
- **Доступно: N** — кількість змонтованих скілів (другорядний контекст, лістинг на льоту). `ВИМК` замість N → скіли не змонтовані на цій поверхні (крос-поверхневе правило, не вдавати успіх).
- **Намір:** `простий` / `складний` / `неоднозначний`.
- **Маршрут:** активований МІНІМАЛЬНИЙ набір скілів (ланцюг).
- **Модель:** активна модель, що відповідає. Якщо ввімкнено оркестрацію (`rlm-harness`) — показати мапу «роль → модель» (диригент + виконавці). Модель НЕ хардкодити — звіряти з актуальним станом.
- **~ток.:** ГРУБА оцінка використаного контексту, завжди з позначкою «оцінка». **Точного лічильника й залишку бюджету токенів чат не дає** — показуємо лише оцінку використаного, не «доступні».
- **Зміни (Δ):** дельта проти попереднього знімка в ЦЬОМУ чаті (нові/оновлені/прибрані скіли). Нема → `нема`.

**Активне виконання, не лічильник:** статус звітує про скіли, що ДІЮТЬ у цьому запиті, а не про змонтовані. Роутинг — щозапиту індивідуально: кожен корисний скіл піднімається саме під потребу цього запиту, зайві — ні. Це поведінка за замовчуванням, без нагадувань MA.

**Виявлення змін у реальному часі (in-flight):**
- Перед кожною задачею ПЕРЕЧИТУЙ стан з диску (Протокол Збереження вище / канон `melania`). Зміни у скілах з паралельного чату підхоплюються одразу й позначаються в `Зміни`.
- Знімок {набір скілів + версії} тримай у контексті; звіряй щотурно. Між сесіями — читай попередній знімок з `continuation-memory`.
- **Зміни промпту/налаштувань НЕ застосовуються до вже відкритих чатів** (правки преференсів діють лише в НОВИХ чатах). Чекаєш ефекту в поточному → нагадай: новий чат або вставити зміну повідомленням.

**Розгорнутий статус on-demand** — тригер `статус` / `status` → повний readout (теж українською):
- таблиця: кожен активний/доступний скіл → версія (з frontmatter) · роль · ~ток. (оцінка) · останнє Δ;
- поверхня (застосунок / Cowork / Code / API) і чи змонтовані скіли;
- моделі за ролями (якщо оркестрація);
- доступні MCP-конектори / tools;
- застереження: числа — ОЦІНКИ, не live-телеметрія.

**Опційний візуальний віджет** — на запит згенеруй інтерактивну HTML-панель (українською, згортувані секції, кнопка «Повний статус» → `sendPrompt('статус')`). Віджет — ЗНІМОК (читання диску + оцінка), не інтроспекція рантайму, без live-лічильника токенів. Постійного «tappable» елемента в чаті промптом/скілом створити НЕ можна.

**Економія:** статус-рядок компактний; повний readout і віджет — лише on-demand. Видимість не має коштувати багато токенів.

---

## Changelog
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (v1.6.0 двічі — артефакт злиттів). Усі записи збережено; нумерацію НЕ переписано без верифікації джерел._
- **v1.16.0** (2026-07-26) — Секція **Critical Facts**: фактичні твердження скіла винесено окремо й протеговано [C] за Core Rule 14 (claim-evidence). Лише додавання.
- **v1.15.0** (2026-07-19) — Self-Dev Wave 2 (аудит 2026-07-18): Routing Map — додано primary-рядок для `workflow-orchestration` («розбий на агентів»/subagents/agent team/топологія; був лише secondary при rlm-harness) [#4]; легасі-рядок «Complex build + deploy» роздвоєно за платформою (Vercel → vercel-mcp-connector; n8n-пайплайн → n8n-orchestrator; був беззастережний n8n) [#7]; H1-банер з версією + `last_updated` [#21/#45]. Лише Routing Map/метадані. _(Merge-reconcile: рядок `github-collab` з v1.14.1 main збережено в Routing Map.)_
- **v1.14.1** (2026-07-21) — Routing Map: +рядок `github-collab` (нова навичка GitHub-автоматизації та співпраці; болі своїми словами: PR/CI/issues/«поверни як було»; secondary — continuation-memory для циклу compact). Лише додавання рядка, семантичний принцип без змін.
- **v1.14.0** (2026-07-19) — Хвиля 1 Self-Dev (аудит 2026-07-18): (A) **семантичні тригери** — маршрутизація за ЗНАЧЕННЯМ наміру, не за дослівними фразами (директива власника; принцип у тілі + description). (B) Розрив циклу «хто перший»: uncertain → роутер сам виконує тріаж (канонічна точка входу); ai-core-runtime — лише fallback, коли роутер недоступний (закриває аудит-знахідку №2). (C) +DO NOT-межі в description: топології→workflow-orchestration, kernel→ai-core-runtime, мета-оркестрація→rlm-harness (№3). (D) Routing Map: рядок «створити/оновити скіл» розділено за governance-межею — створити→skill-creation-guide, оновити/версія/затвердити→SMA (рев'ю Codex PR #24). (E) Description ужато до ≤1024 симв. (packaging-ліміт; рев'ю Codex PR #24).
- **v1.13.2** (2026-06-26) — Changelog-гігієна (F2): примітка про історичні дублі-номери (v1.6.0 двічі). Усі записи збережено; нумерацію НЕ переписано без верифікації (форензик: git/історія відсутні → не вгадуємо). Лише додавання примітки.
- **v1.13.1** (2026-06-26) — `evals/` реконструйовано. Форензик-аудит: claim існував з v1.2.1, але артефакт відсутній у всіх джерелах (git/транскрипти/FS) → відтворено, claim НЕ видалено. `evals/` виключається з .skill (тест-артефакт). Лише додавання.
- **v1.13.0** (2026-06-15) — Активне виконання у статусі: статус-рядок веде ПОІМЕННИМ набором скілів, що реально діють у запиті (не лічильником змонтованих); 0-активних → з причиною. Додано правило «роутер = точка входу щозапиту, піднімає мінімальний ланцюг». Реалізує вимогу MA: бачити активне виконання + щозапитову економну активацію.
- **v1.12.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.12.0** (2026-06-15) — P-LS: Статус-тулбар (UA, реальний час) (компактний статус-рядок щотурно: Skills ON/OFF · count · intent · route · ~tok est · Δ) + in-flight change detection (re-read диску, snapshot-diff, settings-not-retroactive caveat) + on-demand `статус` readout + опційний знімок-віджет. Робить роутинг видимим у реальному часі.
- **v1.11.0** (2026-06-14) — P-U4 (harvest-2026): крок «Офіційний MCP Registry» у MCP-first ladder (дискавери НЕ-підключених серверів + публікація через registry.modelcontextprotocol.io) між конектор-скілом і CLI-fallback.
- **v1.9.0** (2026-06-13) — P-28: доменна маршрутизація L1→L2; CORE + domain nodes; завантаження одного node-manifest замість усіх SKILL.md; typed-context handoff. _(Реструктуризація CORE+nodes, Фаза A.)_
- **v1.2.0** (2026-06-02) — Routing Map розширено з 5 до 12 скілів (додано skill-creation-guide, melania, skill-ecosystem-auditor, notebooklm-connector, collaborative-browser, llm-api-builder, webapp-testing); додано домени governance/browser/api/notebook/testing. _(аудит P-04, поглинає P-01)_
- **v1.3.1** (2026-06-02) — додано auth-session-manager у Routing Map. _(P-19)_
- **v1.3.0** (2026-06-02) — додано 4 паралельні скіли в Routing Map (browser-local-ai-webllm, multi-provider-ai-orchestration, pwa-to-android-app, surgical-code-refactoring) + домени. _(аудит P-23)_
- **v1.2.1** (2026-06-02) — додано власні `evals/` (5 кейсів). _(аудит: Core Rule 4)_
- **v1.1.0** — попередня версія.

- **v1.6.0 — динамічна оркестрація: виявлення скілів на льоту замість фіксованого списку; Routing Map = приклади; принцип економії токенів. (P-26)**

- **v1.5.0** (2026-06-02) — confidence scoring, parallel activation, threshold rules.

- **v1.6.0** (2026-06-02) — Pre-Update Preservation Protocol; routing-optimization reference (caching, fallback chains, context-aware routing).
- **v1.7.0** (2026-06-10) — Фаза 2: I-4: пасивний CORE-індекс + тригерні навички (гібрид, за евал-даними).
- **v1.8.0** (2026-06-12) — маршрутизація зовнішніх інструментів (MCP-first → конектор-скіл → CLI-fallback); Routing Map +vercel-mcp-connector +safety-compliance-gate. _(Harvest Vercel MCP → Proposal #2.)_

- **v1.10.0** (2026-06-14) — P-01: Routing Map +rlm-harness (intents: оркеструй / найвищий рівень / важкий процес / deep research / security audit / перепланування). _(SKILL-AUDIT-LEDGER, harvest RLM Harness.)_
