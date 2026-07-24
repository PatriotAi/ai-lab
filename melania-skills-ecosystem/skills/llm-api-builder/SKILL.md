---
name: llm-api-builder
description: "Build apps with the Claude API or Anthropic SDK. TRIGGER when code imports anthropic, @anthropic-ai/sdk, or claude_agent_sdk, or user asks to use Claude API, Anthropic SDKs, or Agent SDK. Також використовуй, коли користувач хоче: збудувати застосунок на Claude API, інтегрувати Anthropic SDK, налаштувати tool use / function calling, streaming, Batch API, structured outputs чи prompt caching. DO NOT TRIGGER when code imports openai or other AI SDK, general programming, or ML/data-science tasks. НЕ використовувати для openai чи інших не-Anthropic SDK."
license: Apache-2.0 — повні умови в LICENSE.txt кореня екосистеми
metadata:
  version: 1.4.1
  author: Melania (Master Administrator)
  category: api-building
  created: 2026-06-02
  last_updated: 2026-07-19
---

# Building LLM-Powered Applications with Claude — v1.4.1
> Пояснення — українською за замовчуванням (українською-перша); код, ідентифікатори та поля API лишаються англійською. Перемикання мови лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).


## Вибір поверхні (Surface Decision)

| Завдання | Поверхня |
|---|---|
| Швидкий прототип, артефакт | API в артефакті (fetch до api.anthropic.com) |
| Production бекенд | Python SDK `anthropic` |
| Node.js/TypeScript | `@anthropic-ai/sdk` |
| Агентні workflow | Claude Agent SDK (`claude_agent_sdk`) |
| Batch 10k+ запитів | Batch API (async, знижка 50%) |

## Замовчування (Defaults)

Якщо користувач не просить інакше:

Для моделі Claude — за замовчуванням бери **найновішу доступну модель**, а не «запінений» ID: рядки моделей і ціни часто змінюються. Звіряй поточну модель через скіл `product-self-knowledge` або https://docs.claude.com; таблиця нижче — **кешований знімок**, а не джерело істини. Для будь-чого хоч трохи складного — за замовчуванням adaptive thinking (`thinking: {type: "adaptive"}`). І нарешті — за замовчуванням streaming для будь-якого запиту з потенційно довгим входом, довгим виходом чи високим `max_tokens`: це рятує від request timeouts. Щоб отримати повну відповідь, не обробляючи окремі stream-події, використовуй хелпер SDK `.get_final_message()` / `.finalMessage()`.

---

## Визначення мови (Language Detection)

Перш ніж читати приклади коду, визнач, якою мовою працює користувач:

1. **Подивись на файли проекту**, щоб вивести мову:
   * `*.py`, `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` → **Python** — читай з `python/`
   * `*.ts`, `*.tsx`, `package.json`, `tsconfig.json` → **TypeScript** — читай з `typescript/`
   * `*.js`, `*.jsx` (без `.ts`) → **TypeScript** — JS використовує той самий SDK, читай з `typescript/`
   * `*.java`, `pom.xml`, `build.gradle` → **Java** — читай з `java/`
   * `*.kt`, `*.kts`, `build.gradle.kts` → **Java** — Kotlin використовує Java SDK, читай з `java/`
   * `*.scala`, `build.sbt` → **Java** — Scala використовує Java SDK, читай з `java/`
   * `*.go`, `go.mod` → **Go** — читай з `go/`
   * `*.rb`, `Gemfile` → **Ruby** — читай з `ruby/`
   * `*.cs`, `*.csproj` → **C#** — читай з `csharp/`
   * `*.php`, `composer.json` → **PHP** — читай з `php/`

2. **Якщо виявлено кілька мов**: перевір, до якої мови стосується поточний файл чи питання користувача. Якщо досі неоднозначно — спитай, яка мова.

3. **Якщо мову не вивести**: за замовчуванням приклади Python (зазнач це).

4. **Якщо мова не підтримується** (Rust, Swift, C++ тощо): запропонуй cURL / raw HTTP приклади.

5. **Якщо потрібні cURL / raw HTTP приклади**, читай з `curl/`.

### Підтримка можливостей за мовами

| Мова | Tool Runner | Agent SDK | Нотатки |
|------|-------------|-----------|---------|
| Python | Так (beta) | Так | Повна підтримка — декоратор `@beta_tool` |
| TypeScript | Так (beta) | Так | Повна підтримка — `betaZodTool` + Zod |
| Java | Так (beta) | Ні | Beta tool use з анотованими класами |
| Go | Так (beta) | Ні | `BetaToolRunner` у пакеті `toolrunner` |
| Ruby | Так (beta) | Ні | `BaseTool` + `tool_runner` у beta |
| cURL | N/A | N/A | Raw HTTP, без можливостей SDK |
| C# | Ні | Ні | Офіційний SDK |
| PHP | Ні | Ні | Офіційний SDK |

---

## Яку поверхню обрати?

> **Починай з простого.** За замовчуванням — найпростіший рівень, що покриває потребу.

| Сценарій | Рівень | Рекомендована поверхня | Чому |
|----------|--------|------------------------|------|
| Класифікація, summarization, extraction, Q&A | Single LLM call | **Claude API** | Один запит, одна відповідь |
| Batch-обробка чи embeddings | Single LLM call | **Claude API** | Спеціалізовані endpoint'и |
| Багатокрокові пайплайни з логікою в коді | Workflow | **Claude API + tool use** | Ти оркеструєш цикл |
| Кастомний агент з власними інструментами | Agent | **Claude API + tool use** | Максимум гнучкості |
| AI-агент з доступом до файлів/веб/терміналу | Agent | **Agent SDK** | Вбудовані інструменти, safety, MCP |
| Агентний кодувальний асистент | Agent | **Agent SDK** | Створено саме для цього |
| Потрібні вбудовані дозволи й guardrails | Agent | **Agent SDK** | Safety-можливості включено |

### Дерево рішень

```text
Що потрібно твоєму застосунку?

1. Один LLM-виклик (класифікація, summarization, extraction, Q&A)
   └── Claude API — один запит, одна відповідь

2. Чи потрібно Claude читати/писати файли, ходити в веб або виконувати shell-команди?
   └── Так → Agent SDK — вбудовані інструменти

3. Workflow (багатокроковий, оркестрований кодом, з власними інструментами)
   └── Claude API з tool use — ти контролюєш цикл

4. Відкритий агент (модель сама обирає траєкторію, твої інструменти)
   └── Claude API agentic loop (максимум гнучкості)
```

---

## Архітектура

Усе йде через `POST /v1/messages`. Інструменти й обмеження виводу — це можливості цього єдиного endpoint'а.

**User-defined tools** — ти визначаєш інструменти (через декоратори, Zod-схеми чи raw JSON), а tool runner SDK сам викликає API, виконує твої функції й крутить цикл, доки Claude не завершить.

**Server-side tools** — інструменти, що хостяться Anthropic і виконуються на її інфраструктурі.

**Structured outputs** — `output_config: {format: {...}}` на `messages.create()`. Рекомендований підхід — `client.messages.parse()`.

**Допоміжні endpoint'и** — Batches (`POST /v1/messages/batches`), Files (`POST /v1/files`), Token Counting.

---

## Поточні моделі (агностично)

> **Конкретні model ID/ціни/ctx НЕ живуть тут.** Датований знімок — у спільному замінному файлі
> `multi-provider-ai-orchestration/references/model-snapshot-YYYY-MM.md` (DRY, поточний: 2026-07).
> Авторитет — `product-self-knowledge` / https://docs.claude.com. **За замовчуванням — найновіша
> доступна модель**; пінь конкретну старішу лише коли користувач явно її називає.

## Thinking & Effort (швидка довідка)

**Поточні флагмани — adaptive thinking (рекомендовано):** `thinking: {type: "adaptive"}`. На поточних флагманах `budget_tokens` deprecated.

**Effort-параметр (GA):** `output_config: {effort: "low"|"medium"|"high"|"max"}`. Замовчування — `high`. `max` — лише для топ-Opus.

**Adaptive thinking** підтримується поточними Sonnet/Opus; `budget_tokens` на них deprecated.

**Старіші моделі (лише за явним запитом):** `thinking: {type: "enabled", budget_tokens: N}`. `budget_tokens` має бути менший за `max_tokens` (мінімум 1024).
> ⚠️ `budget_tokens` валідний **лише для старіших поколінь** (межу звір у docs). Не використовуй із поточними флагманами — звір актуальну поведінку в docs.

---

## Compaction (швидка довідка)

**Beta, поточні топ-моделі (звір docs, які саме).** Потребує beta-хедер `compact-2026-01-12`. API автоматично підсумовує ранній контекст при наближенні до порога. Ключі: `context_management.edits` (конфігурація), trigger threshold конфігурується (від ~50K), `pause_after_compaction` — зупинка після компакції для інспекції. Додавай `response.content` (не лише текст) назад у messages щоходу. Компакція, що переписує префікс щотурну, ВБИВАЄ prompt-cache — тримай стабільний кеш-префікс. (Звір поточну доступність/умови в docs.)

## Memory Tool (швидка довідка)

**GA на поточних поколіннях (звір docs).** Client-side tool `memory_20250818`: модель читає/пише файли в sandbox-директорії `/memories` через твій handler. ОБОВ'ЯЗКОВО: path-traversal захист у handler (валідація що шлях лишається в `/memories`). Емпірика Anthropic: context editing + memory tool = **+39% якості проти baseline, −84% токенів** на 100-turn агентних задачах; context editing сам = +29%. Патерн: pre-compaction memory flush (важливе → у memory ПЕРЕД компакцією). Деталі — docs memory-tool.

## Advanced Tool Use (швидка довідка)

Три beta-можливості для агентів з великими наборами інструментів (звір хедери в docs):
- **Programmatic Tool Calling** — модель викликає інструменти з code-execution середовища, фільтруючи проміжні дані: **−37% токенів** на складних research-задачах (43.6K→27.3K).
- **Tool Search Tool** — інструменти підвантажуються пошуком замість усіх визначень у контексті: **−85% контексту** (77K→8.7K) для великих tool-бібліотек.
- **Tool Use Examples** — приклади викликів у визначенні інструмента: parameter accuracy **72%→90%**.

---

## Гайд читання (Reading Guide)

> ℹ️ **Нотатка:** Цей SKILL.md — точка входу. Мовно-специфічні reference-файли (`{lang}/claude-api/README.md`, `shared/tool-use-concepts.md` тощо) живуть у повному GitHub-репо [`anthropics/skills/skills/claude-api/`](https://github.com/anthropics/skills/tree/main/skills/claude-api). Тягни їх через `web_fetch` за потреби.

Після визначення мови читай релевантні файли:

- **Один text classification/summarization/extraction/Q&A:** `{lang}/claude-api/README.md`
- **Chat UI чи real-time показ відповіді:** `README.md` + `streaming.md`
- **Function calling / tool use / агенти:** `README.md` + `shared/tool-use-concepts.md` + `tool-use.md`
- **Batch-обробка:** `README.md` + `batches.md`
- **File uploads через кілька запитів:** `README.md` + `files-api.md`
- **Агент із вбудованими інструментами:** `{lang}/agent-sdk/README.md` + `patterns.md`

---

## Часті пастки (Common Pitfalls)

* Не обрізай вхід, передаючи файли чи контент в API.
* **Thinking на поточних флагманах:** `thinking: {type: "adaptive"}` — НЕ використовуй `budget_tokens`.
* **Prefill:** на найновіших Opus assistant-prefill може повертати 400 — звір у docs перед використанням prefill.
* **128K output tokens:** `.stream()` з `.get_final_message()` / `.finalMessage()`.
* **Batch API до 300K output:** beta-хедер `output-300k-2026-03-24` (звір docs) — для довгих batch-генерацій.
* **Structured outputs:** `output_config: {format: {...}}` замість deprecated `output_format`.
* **Не визначай власні типи для структур даних SDK:** використовуй `Anthropic.MessageParam`, `Anthropic.Tool` тощо.
* **Звіти й документи на виході:** code-execution sandbox має передвстановлені `python-docx`, `python-pptx`, `matplotlib`, `pillow`, `pypdf`.

---

## 📎 Advanced Patterns (v4)

Читай `references/advanced-api.md`, КОЛИ потрібні: prompt caching (до 90% економії), citations, vision, PDF, Files API, structured output, batch+tools.
Вантаж лише на вимогу — не проактивно.

---

## Зміни
- **v1.4.1** (2026-07-19) — Self-Dev Wave 2 (аудит 2026-07-18): ліцензійний покажчик виправлено на корінь екосистеми (локального LICENSE.txt не існувало) [#25/#44]; H1-банер з версією [#21/#45-клас]. Лише метадані.
- **v1.4.0** (2026-07-11) — Frontier-research harvest + принцип модельної агностичності: **(A)** Секцію «Поточні моделі» де-піновано: таблиця конкретних ID/цін → покажчик на спільний датований снапшот у `multi-provider` (DRY) + правило «найновіша доступна». **(B)** Compaction розширено (агностично): `context_management.edits`, конфігурований поріг, `pause_after_compaction`, попередження про кеш-префікс. **(C)** НОВА секція Memory Tool: sandbox-патерн, path-traversal захист, емпірика +39%/−84%, pre-compaction flush — без прив'язки до поколінь. **(D)** НОВА секція Advanced Tool Use: Programmatic Tool Calling (−37% токенів), Tool Search Tool (−85% контексту), Tool Use Examples (72→90%). **(E)** Pitfalls: +Batch довгий output (beta, звір хедер у docs). Лише додавання/де-пін; API-ідентифікатори (tool-типи, beta-хедери) збережені — це документація API, не пін моделей. _(Джерело: дослідницький звіт 2026-07-11 + правило агностичності MA.)_
- **v1.3.0** (2026-06-26) — Повна UA-локалізація (Task 1): технічну прозу (Defaults, Language Detection, Architecture, Reading Guide, Pitfalls, таблиці) перекладено українською; код / API / ідентифікатори лишаються англійською. +власні `evals/` (5, канон-схема). **S-1:** знімок моделей оновлено (Opus 4.6→4.8, `claude-opus-4-8`); version-tied claims генералізовано на «поточні флагмани» + verify-нота (без вигадування цін 4.8). **S-2:** дубльовану секцію «Зміни» + дубль v1.2.0 консолідовано (вміст збережено). Переклад + додавання; функціонал не змінено.
- **v1.2.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна.
- **v1.2.0** (2026-06-02) — `metadata`-блок, директива «українською-перша», власні `evals/` (5); де-хардкод моделей (найновіша + звірка з product-self-knowledge/docs); Pre-Update Preservation Protocol; `advanced-api` reference (prompt caching, citations, vision, PDF, Files API). _(аудит Кластер 3: P5 + P9 + Core Rule 4)_
- **v1.1.0** (2026-06-02) — extended thinking API, streaming+tools, Batch API, token counting, surface decision table.
