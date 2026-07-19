---
name: ai-core-runtime
description: >
  Modular AI orchestration runtime for structured reasoning, semantic routing,
  multi-agent coordination, validation-first execution, and token-efficient
  cognitive workflows.

  USE THIS SKILL whenever the user requests: AI system architecture, orchestration
  runtimes, modular agent systems, workflow governance, runtime design, automation
  architecture, reasoning pipelines, AI operating system design, microkernel
  orchestration, multi-agent frameworks, or bounded reasoning systems.

  Also trigger for: "побудуй оркестрацію", "спроєктуй AI систему",
  "agent pipeline", "modular AI", "runtime architecture", "orchestration layer". DO NOT use for single simple Q&A, one-off code snippets, or tasks needing no orchestration (use the specific skill directly).
license: MIT
metadata:
  author: Prompt Ingeniero Ecosystem
  version: 3.11.0
  category: orchestration
---

# AI Core Runtime
> Працює українською за замовчуванням (українською-перша): тригери, відповіді й приклади — українською; перемикання лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Mission

Provide a lightweight microkernel runtime for Claude-based systems:

- **Semantic routing** — map intent to correct modules
- **Modular skill activation** — load only what's needed
- **Bounded reasoning** — prevent infinite loops and runaway context
- **Governed orchestration** — validate before acting
- **Token-efficient execution** — patch-first, never rewrite

---

## Architecture Principles

| Principle | Rule |
|---|---|
| Microkernel | Core stays minimal; features are modules |
| Progressive Disclosure | Load metadata → body → references on demand |
| Patch-First | Always prefer diffs over full regeneration |
| Selective Activation | Never activate all agents globally |
| Bounded Recursion | Set max depth on any recursive workflow |
| Externalized Memory | State lives outside Claude's context window |
| Validation-Before-Output | Never emit unvalidated architecture |

---

## Runtime Pipeline

```
User Intent
    ↓
[1] Intent Analysis       → classify: create / debug / optimize / route
    ↓
[2] Context Modeling      → load only relevant prior state
    ↓
[3] Semantic Routing      → select skill(s) + agent(s) to activate
    ↓
[4] Skill Activation      → progressive disclosure loading
    ↓
[5] Agent Orchestration   → coordinate required agents
    ↓
[6] Validation            → dependency + contradiction + continuity checks
    ↓
[7] Optimization          → compress, patch, minimize tokens
    ↓
[8] Output Generation     → structured result + next steps
```

---

## Agent Activation Policy

Activate **only what is required**. Match task type to minimal agent set:
> Клас моделі на агента/процес признач за model-fit політикою `rlm-harness` (`references/model-fit-policy.md`): диригент = найсильніша, прості/паралельні кроки = найдешевші придатні.

| Task Type | Agents to Activate |
|---|---|
| Architecture design | architect + validator |
| Code generation | builder + validator |
| Debugging | debugger + validator + optimizer |
| Research / analysis | researcher + analyst |
| Complex orchestration | planner + architect + validator + optimizer |
| Quick Q&A | (no agents, respond directly) |

**Never activate all agents simultaneously.**

**Динамічна оркестрація + економія:** скіли/агенти для співпраці добирай **динамічно** за
наміром задачі, а не з фіксованого переліку — будь-який скіл може взаємодіяти з будь-яким,
включно з тими, що зʼявляться пізніше (виявлення через `semantic-router` на льоту). Активуй
**мінімальний достатній набір**: лише потрібні, у потрібній кількості — щоб не марнувати токени,
але й не жертвувати якістю (бракує охоплення → додай скіл; зайве → прибери).

**Kernel fallback-start:** канонічна точка входу при неоднозначному вході — `semantic-router` (тріаж наміру щозапиту). `ai-core-runtime` стартує першим ЛИШЕ коли роутер недоступний/не завантажений: якщо роутер можна завантажити — завантаж і передай тріаж йому; якщо роутер СПРАВДІ недоступний — виконай ЛОКАЛЬНИЙ тріаж сам (класифікуй намір і активуй мінімальний достатній ланцюг без залежності від роутера). Тривіальний вхід → 0 агентів/скілів (зазначити).

Available agents: `researcher`, `analyst`, `architect`, `builder`, `debugger`, `validator`, `optimizer`

---

## Token Optimization Rules

1. **Patch-only updates** — output diffs, not full files
2. **Compressed summaries** — use continuation-memory skill for long sessions
3. **Selective context loading** — load references only when they add value
4. **No boilerplate regeneration** — never re-output unchanged sections
5. **Bounded execution** — set explicit stop conditions on iterative tasks
6. **Modular loading** — each module is loaded on demand, not preloaded

Read `references/token-efficiency.md` for detailed patterns.

---

## Validation Requirements

Before any output, verify:

- [ ] **Dependency validation** — all referenced modules exist and are compatible
- [ ] **Contradiction detection** — no conflicting rules or states
- [ ] **Continuity validation** — consistent with prior session state
- [ ] **Architecture coherence** — structure is logically sound

If validation fails → report clearly with `UNKNOWN` rather than guessing.

---

## Standard Output Format

Structure every architecture response as:

```
1. ANALYSIS      — what the user is actually asking for
2. ARCHITECTURE  — the proposed design (diagrams, modules, flows)
3. VALIDATION    — what was checked, what passed, what is uncertain
4. OPTIMIZATION  — token/performance improvements identified
5. RESULT        — concrete deliverable (code, config, schema, plan)
6. NEXT STEPS    — what to do next to continue
```

---

## Critical Rules

- **Never** regenerate entire repositories unless explicitly requested
- **Never** create infinite recursive loops
- **Never** claim persistent internal memory (use continuation-memory skill)
- **Always** use progressive disclosure
- **Always** separate references from SKILL.md body
- **Always** preserve naming conventions from prior sessions

---

## Поведінкові правила (Karpathy)
Дефолти для будь-якого виконання в рантаймі:
- **Think Before Coding** — не припускай; винеси компроміси й невизначеності наперед.
- **Simplicity First** — мінімальне рішення; без спекулятивного коду/агентів.
- **Surgical Changes** — кожна змінена одиниця трасується до запиту; не розширювати обсяг.
- **Goal-Driven** — критерії успіху → цикл до підтвердження (evidence over claims).

## Режим стислості (економія)
Стискай **лише видимий вивід**, не reasoning-кроки:
- Прибирай преамбули/повтори; став суть першою; деталі — на вимогу.
- Стислість не знижує якість: якщо стиснення втрачає сенс — розгортай.
- **Safety-виняток (обов'язково):** для security-попереджень, незворотних дій, юридичних/медичних і будь-яких ризикованих тем — **повна проза**, без стиснення.
- Узгоджено з token-economy: мінімальний достатній обсяг, не на шкоду повноті.

## Tiered-depth + scope-перемикачі (мінімальний достатній ОБСЯГ ДАНИХ)
Економ не лише вивід — а й **глибину даних**, які тягнеш/обробляєш:
- **Депт-леддер:** бери найдешевший рівень, що відповідає на задачу (status → огляд → повний аналіз → глибокий дебаг). Не стрибай на найглибший, якщо вистачає поверхневого.
- **Scope-перемикачі (`include*`):** вантаж лише потрібні поля/секції на вимогу, не весь обсяг (патерн конекторів типу `vercel-mcp-connector`).
- **Lazy-контекст:** рішення про потрібну глибину прийми ДО завантаження (крок [2] Context Modeling), не після.
- **Мультимовний шар (внутрішньо):** проміжні reasoning-шари можна вести найкомпактнішою для них мовою (щільніший токен на символ) → більше контексту за ту саму ціну. **Фінальна відповідь — завжди українською; багатомовність лише внутрішня.**
> Принцип: «мінімальний достатній ОБСЯГ ДАНИХ» доповнює «мінімальний достатній НАБІР скілів» і «стискай лише вивід».

## Related Skills

- **continuation-memory** — use when session is long or needs resuming
- **semantic-router** — use when routing intent across multiple skills
- **validation-mesh** — use for deep validation workflows
- **n8n-orchestrator** — use when building n8n automation pipelines
- **rlm-harness** — мета-оркестратор НАД рантаймом: RLM-політика моделей по ролях + динамічний контрол-луп + рецепти; цей скіл — kernel/активація під ним.
- **gmi-audit** — GMI-лінза для оцінки когнітивної архітектури: інваріанти G1–G7 (модель світу · ціль · висновок · пам'ять · навчання · метакогніція · детермінація/read-out) + вісь спостерігача. Застосуй, коли проєктуєш/аудиш повноту рантайму чи агентної системи.

---

## 📎 Advanced Patterns (v4)

Read `references/resilience-patterns.md` WHEN you need: circuit breakers, retry+idempotency, state machines, structured logging, graceful degradation.
Load only on demand — not proactively.

---

## Зміни
- **v3.11.0** (2026-07-19) — Хвиля 1 Self-Dev (аудит 2026-07-18): (A) «Kernel default-start» → **fallback-start** — канонічна точка входу при неоднозначному вході тепер semantic-router; ACR стартує першим лише коли роутер недоступний (розрив циклу «хто перший», знахідка №2). (B) Де-хардкод мертвого посилання: `product-self-knowledge` → офіційні docs (docs.claude.com) у прикладі extended thinking (№1; історичний запис v3.7.1 у changelog не переписувався — append-only). (C) Fallback без глухого кута: якщо роутер справді недоступний — ЛОКАЛЬНИЙ тріаж без залежності від нього (рев'ю Codex PR #24). Лише уточнення.
- **v3.10.1** (2026-07-13) — Крос-лінк `gmi-audit` у Related Skills: GMI-лінза (інваріанти G1–G7 когнітивної системи + вісь спостерігача/read-out) для аудиту повноти рантайму/агентної архітектури. Лише додавання (DRY-покажчик, без дублювання). _(Джерело: experiments/gmi harvest.)_
- **v3.10.0** (2026-07-11) — Kernel-патерни (frontier-research harvest): **(A)** Deferred tools / Tool Search — активація інструментів пошуком замість повного списку (розширення депт-леддера на НАБІР ІНСТРУМЕНТІВ; до −85% контексту). **(B)** Memory-handler kernel-безпека: обов'язковий path-traversal захист sandbox-пам'яті + provenance-мітка кожного запису (анти-poisoning). API-механіка обох — покажчик на `llm-api-builder` (DRY). Агностично, без пін-у моделей. Лише додавання. _(Джерело: дослідницький звіт 2026-07-11.)_
- **v3.9.2** (2026-06-26) — `evals/` реконструйовано. Форензик-аудит: claim існував з v3.2.0, але артефакт відсутній у всіх джерелах (git/транскрипти/FS) → відтворено, claim НЕ видалено. `evals/` виключається з .skill (тест-артефакт). Лише додавання.
- **v3.9.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v3.2.0** (2026-06-02) — додано директиву «українською-перша» + власні `evals/` (5 кейсів). _(аудит Кластер 2: P9 + Core Rule 4)_

- **v3.5.0 — динамічне виявлення партнерів + економія в Agent Activation Policy. (P-26)**


---

## Extended Thinking Integration

Для задач що потребують глибокого аналізу (архітектурні рішення, складний дебаг,
multi-step reasoning) — активуй **extended thinking** через API:

```python
response = client.messages.create(
    model=MODEL,   # актуальна модель з extended thinking — звір через офіційні docs (docs.claude.com), не пінь версію
    max_tokens=16000,
    thinking={"type": "enabled", "budget_tokens": 10000},
    messages=[{"role":"user","content": complex_task}]
)
# thinking блок + відповідь — розбирай обидва
for block in response.content:
    if block.type == "thinking": audit_log(block.thinking)
    if block.type == "text":     present(block.text)
```

**Коли вмикати:** архітектурні trade-off, діагностика складних помилок, побудова
довгих reasoning chains. **Коли НЕ вмикати:** прості CRUD, форматування, look-up.

---

## Tool Use Orchestration

```python
# Паралельні tool call-и — один раунд, кілька інструментів
tools = [search_tool, code_exec_tool, validation_tool]
response = client.messages.create(model=MODEL, tools=tools, messages=msgs)
# зібрати всі tool_use блоки → виконати паралельно → повернути results
tool_calls = [b for b in response.content if b.type=="tool_use"]
results = await asyncio.gather(*[execute(tc) for tc in tool_calls])
```

**Ланцюг інструментів:** вихід одного → вхід наступного. Перевіряй результат
кожного кроку через `validation-mesh` перед передачею далі.

**Deferred tools / Tool Search (kernel-патерн активації):** для великих tool-бібліотек НЕ вантаж
усі визначення в контекст — підвантажуй пошуком за потребою (та сама логіка, що депт-леддер даних:
мінімальний достатній НАБІР ІНСТРУМЕНТІВ; емпірика: до −85% контексту на великих бібліотеках).
API-механіка (tool search / use examples) — у `llm-api-builder`.

**Memory-handler (kernel-безпека):** якщо рантайм експонує моделі файлову пам'ять — handler
ЗОБОВ'ЯЗАНИЙ: (1) валідувати кожен шлях у межах sandbox-директорії (path-traversal захист:
resolve → перевірка префікса), (2) мітити кожен запис provenance (хто/яка сесія/який інструмент
записав) — інакше poisoned memory поширюється без сліду. API-механіка — у `llm-api-builder`.

---

## MCP Server Coordination

Коли задача потребує зовнішніх сервісів через MCP:

```python
# Включення MCP-серверів у API виклик
response = client.messages.create(
    model=MODEL, messages=msgs,
    mcp_servers=[
        {"type":"url","url":"https://mcp.asana.com/sse","name":"asana"},
        {"type":"url","url":"https://drivemcp.googleapis.com/mcp/v1","name":"gdrive"}
    ]
)
```

**Правила:** активуй лише потрібні MCP-сервери (не всі одразу);
перевіряй `type: mcp_tool_result` блоки окремо від `type: text`.

---

- **v3.4.0** (2026-06-02) — extended thinking, parallel tool use, MCP coordination patterns.

- **v3.5.0** (2026-06-02) — Pre-Update Preservation Protocol; resilience-patterns reference (circuit breaker, retry, state machines, observability).
- **v3.6.0** (2026-06-10) — Фаза 2: I-5: поведінкові правила Karpathy у рантаймі.
- **v3.7.0** (2026-06-10) — Фаза 3: I-7: режим стислості (стискати лише видимий вивід; safety-виняток — повна проза).
- **v3.7.1** (2026-06-10) — анти-застарілість: де-хардкод моделі у прикладі extended thinking (звіряти через product-self-knowledge).
- **v3.8.0** (2026-06-12) — tiered-depth + scope-перемикачі (мінімальний достатній ОБСЯГ ДАНИХ): депт-леддер, include*-завантаження, lazy-контекст; внутрішній мультимовний шар (фінал — українською). _(Harvest Vercel MCP → Proposal #4.)_

- **v3.9.0** (2026-06-14) — P-01: крос-лінк rlm-harness + покажчик model-fit політики у Agent Activation (клас моделі на агента). _(SKILL-AUDIT-LEDGER, harvest RLM Harness.)_
