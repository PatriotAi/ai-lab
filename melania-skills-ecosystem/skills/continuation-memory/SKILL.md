---
name: continuation-memory
description: >
  Compresses long AI conversations into compact, resumable architecture
  summaries with dependency maps, unresolved issues, active TODOs, and
  continuation states. Generates structured "continuation packages" that
  allow any new Claude session to resume exactly where the previous one ended.

  USE THIS SKILL whenever the user needs: session continuity, resuming
  interrupted work, context compression, long-term project memory, token
  reduction across sessions, architecture state preservation, or recovery
  from interrupted workflows.

  Also trigger for: "продовж де ми зупинились", "resume from last point",
  "remember where we were", "continuation state", "compress context",
  "де ти був перебитий", "відновити прогрес", "save state", "STENO",
  "pick up where we left off".

  IMPORTANT: This skill is a drop-in memory system for any project.
  Use it proactively after ~20 turns or whenever a task may be interrupted. DO NOT use for short sessions (under 20 turns) or one-shot questions needing no state.
license: MIT
metadata:
  author: Prompt Ingeniero Ecosystem
  version: 1.9.1
  category: memory
---

# Continuation Memory
> Працює українською за замовчуванням (українською-перша): пакети, нотатки й приклади — українською; перемикання лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Purpose

Claude has no persistent memory between sessions. This skill creates
**structured continuation packages** that act as compressed memory —
small enough to paste into any new session, complete enough to fully
resume the work.

---

## When to Generate a Continuation Package

Generate automatically when:
- User explicitly asks to save state / resume later
- Conversation exceeds ~20 turns on a complex task
- Task is interrupted mid-workflow
- User signals they may come back: "зупинимось тут", "продовжимо пізніше"
- Before a context-intensive operation that might hit limits

---

## Continuation Package Format

Output a fenced markdown block labeled `CONTINUATION_PACKAGE` with
these sections:

```markdown
## CONTINUATION_PACKAGE
**Project:** [project name]
**Generated:** [date/time if available]
**Session Summary:** [1–3 sentence description of what was accomplished]

### Current Architecture
[Stable modules, their purpose, and current state. Only what exists now.]

### Active Work (IN PROGRESS)
[Exactly what was being built/edited at the moment of interruption.
Be specific: file names, function names, step numbers.]

### Pending Tasks (TODO)
[Numbered list of remaining work items, in priority order]

### Known Risks / Blockers
[Any unresolved issues, dependency gaps, or design decisions pending]

### Dependency Map
[Key dependencies: what relies on what. Format: A → B → C]

### Naming Conventions
[Important names: variables, functions, modules, files — anything
that must stay consistent]

### Suggested Next Actions
[Top 2–3 concrete next steps to continue immediately]

### Resume Prompt
> Paste this into a new Claude session to resume:
> "Продовжую роботу над [project]. Ось стан: [paste this package].
> Продовж з: [Active Work section above]."
```

---

## Compression Workflow

When generating a continuation package:

1. **Scan the full conversation** — identify all work done
2. **Extract architecture state** — what modules/files/flows exist
3. **Identify active work** — the last unfinished task
4. **Extract unresolved tasks** — ordered TODO list
5. **Map dependencies** — what relies on what
6. **Compress reasoning chain** — discard resolved debates, keep decisions
7. **Generate continuation package** — structured output above
8. **Generate resume prompt** — one-liner to paste into next session

---

## Rules

- **Never summarize away critical dependencies**
- **Preserve architectural continuity** — stable module names must match
- **Preserve naming conventions** — variable/file names from prior session
- **Preserve active TODOs** — a dropped TODO is a lost feature
- **Keep summaries concise** — target under 1500 tokens for the full package
- **Be specific about interruption point** — vague "was working on X" is
  not enough; name the exact file/step/function being edited

---

## Memory Persistence Strategies

In Claude.ai, use these in combination:

| Strategy | How | Durability |
|---|---|---|
| Continuation package in chat | Paste package at session start | Until tab closes |
| Memory edits (memory_user_edits) | Ask Claude to add to memory | Across sessions |
| Progress file on disk | Save to /home/claude/PROGRESS.json | Until VM resets |
| Paste into new conversation | Copy package, start new chat | Manual but reliable |

**Best practice:** Use all four simultaneously for critical projects.

---

## 3-шарове розкриття пам'яті (retrieval)
Не вантаж усе одразу — діставай пам'ять пошарово (≈10× економія токенів):
- **L1 · index** — компактний пошук (≈50–100 токенів/запис): лише заголовки/мітки збігів.
- **L2 · context** — для обраних записів: стислий контекст (timeline/summary).
- **L3 · details** — повний запис/транскрипт лише коли справді потрібно.
Пошук виконуй у **форкнутому/ізольованому субагенті**, щоб проміжні результати не засмічували головний контекст.
**Compile (опц.):** періодично зводь daily-логи у структуроване знання (концепти + звʼязки) — щоб пам'ять еволюціонувала, а не лише накопичувалась.
**SQL-пошук (опц.):** для великих архівів сесій — індексований/SQL-пошук логів замість лінійного читання (рушій — на твій вибір).
**Узгоджено з рантаймом:** L1→L2→L3 — це депт-леддер пам'яті («мінімальний достатній ОБСЯГ ДАНИХ», `ai-core-runtime`): діставай найдрібніший шар, що відповідає на потребу. Внутрішнє стиснення може йти найкомпактнішою мовою; фінальний пакет/відповідь — українською.

## Ієрархія пам'яті сесії — hot / warm / cold (керування вікном)
Окрема вісь від 3-шарового розкриття вище: те — глибина ДІСТАННЯ з архіву;
це — стиснення ЖИВОЇ сесії за свіжістю, поки не вперлись у вікно.
- **Hot** (≈останні 10 ходів) — дослівно у вікні, повна точність.
- **Warm** (старіші) — стиснені в summary: зберегти рішення/імена/артефакти, відкинути вирішені дебати.
- **Cold** (давнє) — винесено (диск / `memory_user_edits`); підтягувати за потреби (L1→L3).

**Чому, а не лише «бо токени»:** ефективність падає ЗАДОВГО до технічного ліміту вікна — функція уваги, не лічби токенів (MECW). Сфокусовані ~5k часто б'ють «повні» ~50k: нерелевантний контекст конкурує за увагу. Стиснення — постійна дисципліна.

**Anthropic Compaction API (керований важіль):** server-side авто-стиснення старіших частин у межах ОДНІЄЇ сесії (поточні топ-моделі — звір доступність у docs; ZDR). Коли що:
- **Структуровані потоки** (spec→implement→verify) → явний split + STENO/continuation-пакет.
- **Відкриті/довгі прогони** (exploratory debug, research) → Compaction API (drop-in).

**Дисципліна навколо compaction (порядок критичний):**
1. **Pre-compaction flush** — важливі рішення/імена/TODO → у durable-пам'ять (memory-файли / `memory_user_edits` / PROGRESS-файл) ПЕРЕД стисненням: компакція без flush = ризик мовчазної втрати (poisoned summary гірший за відсутній — тюнінг на recall спершу).
2. **Стабільний кеш-префікс** — компакція/edits, що переписують префікс щотурну, ВБИВАЮТЬ prompt-cache; тримай system+інструменти незмінними, стискай лише хвіст.
3. **Context editing** — другий серверний важіль поруч із compaction: очистка старих turn-ів/tool-результатів за порогом (емпірика: editing сам ≈ +29% якості; editing+memory ≈ +39% і −84% токенів на довгих агентних прогонах). API-механіка обох — у `llm-api-builder`.
4. **Provider-agnostic fallback** — серверні важелі є не всюди: STENO/continuation-пакет + hot/warm/cold (вище) = та сама дисципліна власноруч, працює з БУДЬ-ЯКОЮ моделлю.

Глибша теорія, бюджет-слоти й формули — у `references/context-engineering.md`.

## STENO Protocol (Compressed Note-Taking)

For extremely long sessions, use STENO format for mid-session
compression (does NOT replace continuation packages — use both):

```
STENO:[phase]:[current_file]:[last_completed_step]:[next_step]:[blockers]
```

Example:
```
STENO:BUILD:ai-core-runtime/SKILL.md:STEP3_VALIDATION:STEP4_OUTPUT:none
```

Insert a STENO line at the top of each response during long workflows
so the user can always see current position at a glance.

---

---

## memory_user_edits — Міжсесійна Пам'ять

Для критичних проектів — зберігай ключові факти в довготривалій пам'яті Клода:

```
# У чаті:
"Запам'ятай: проект X, фаза BUILD, останній файл auth.py, крок 3/5"
# → Claude викликає memory_user_edits tool → зберігається між сесіями

# Для відновлення в новій сесії:
"Що ти памʼятаєш про проект X?"
```

**Комбінуй усі 4 рівні пам'яті:**

| Рівень | Метод | Живе до |
|---|---|---|
| **L1 Контекст** | Continuation package у чаті | закриття вкладки |
| **L2 Пам'ять** | `memory_user_edits` | між сесіями ✓ |
| **L3 Диск** | `/home/claude/PROGRESS.json` | VM reset |
| **L4 Вставка** | Copy-paste в новий чат | завжди надійно |

---

## Quick State Snapshot (QSS)

Для mid-task збереження без повного пакету. Вставляй у відповідь:

```
⚡ QSS | proj:[назва] | phase:[фаза] | file:[поточний файл]
       | done:[крок N/M] | next:[що далі] | block:[блокери або none]
```

Приклад:
```
⚡ QSS | proj:skill_ecosystem | phase:BUILD | file:n8n-orchestrator/SKILL.md
       | done:4/17 | next:validation-mesh | block:none
```

---

## Конфлікт Між Сесіями

Якщо новий пакет суперечить попередньому:
1. Покажи обидва стани MA
2. Запитай: "Яка версія правильна?"
3. Злий пакети лише після підтвердження
4. Зафіксуй рішення у CHANGELOG

---

## Typed-Context Handoff Object (для P-28)

Для передачі стану CORE↔domain node і між субагентами — компактний **typed-context-обʼєкт**, НЕ сира історія розмови (структурований брифінг):

```json
{ "domain": "youtube-production", "stage": "video-draft",
  "entities": ["topic-id", "block-refs"],
  "decisions": ["затверджений outline", "формат 9:16"],
  "artifacts_refs": ["pipeline-state.json#item-42"] }
```

- Бюджет ≈200–500 токенів (проти 5k–20k при пересиланні всієї історії; вартість росте квадратично з к-стю хендофів). Передавай лише потрібне downstream-скілу.
- Повний контекст діставай через 3-шарове розкриття (L1→L2→L3) за потреби.
- Це обʼєкт, на який посилається дворівнева маршрутизація `semantic-router` (P-28).

---

## Idempotent Sync Tracker (механіка P-27)

Щоб «диск завжди канонічний» було **механічним**, а не ручним — тримай трекер стану одиниць (скілів/артефактів):

```json
{ "id": "<skill-id>", "version": "<версія>", "md5": "<хеш>",
  "last_validated": "<дата>", "last_synced": "<дата>", "status": "valid" }
```

- **Дрейф-детект:** перед будь-яким оновленням звір `md5` диску з трекером. Розбіжність = одиницю змінив паралельний чат → механічний сигнал, що re-read (CR10/P-27) обовʼязковий.
- **Ідемпотентність:** перед повторною обробкою перевір ключ (`id` + content-hash); не змінилось — пропусти (не переробляй). Аналог `processed:${id}` з TTL.
- **Каденція resync (опц.):** періодичний прогін оновлює трекер; авто-sync-коміти тримають диск і трекер у згоді. Шаблон автоматизації — `n8n-orchestrator`.
- Узгоджено з guard-snapshot: snapshot = baseline вмісту, трекер = реєстр стану/синку.

---

## Скафолд памʼяті проєкту (reusable)

Довговічний дисковий «двійник» continuation-пакета — набір канонічних .md, що його має нести будь-який Claude-керований проєкт/репо:

| Файл | Роль |
|---|---|
| `ROADMAP.md` | активний план/фази |
| `ROADMAP-archive.md` | завершені пункти (щоб ROADMAP лишався стислим) |
| `CONTEXT.md` | поточний стан: що де лежить, останні рішення |
| `index.md` | навігація по репо |
| `log.md` | хронологія рішень |

Парується з `AGENTS.md` (canonical) + тонким `CLAUDE.md` — правило єдиного джерела в `skill-creation-guide`. Continuation-пакет у чаті = L1; цей скафолд на диску = L3-довговічність.

---

## G5 cold-start recovery gate (валідований патерн)
Щоб зовнішня пам'ять реально закривала прогалину **G5** (навчання/відновлення між сесіями),
пакет має пройти **cold-start тест** (сесія відновлюється з ЛИШЕ пакета):
- **Self-contained critical refs:** усі критичні URL/шляхи — **inline у пакеті**, НЕ pointer-only
  (cold-сесія може не мати доступу до інших файлів).
- **Recovery-checklist ДО тесту:** зафіксуй перелік критичних пунктів (рішення / відкриті нитки /
  точний наступний крок) **ПЕРЕД** тестом → об'єктивний вимір % відновлення; ціль **100% критичних без повтору**.
- Повнота пакета — базово через **`validation-mesh`** (у Melania-пакеті); **опційно** `gmi-audit`
  (інваріант G5) як розширення, **якщо доступне** (лаб-скіл поза Melania-пакетом — не hard-dep).
_(Валідовано: `experiments/gmi-g5-memory` — recovery 9/9 після застосування self-contained refs.)_

---

## Related Skills

- **ai-core-runtime** — uses continuation-memory for session continuity
- **semantic-router** — can trigger continuation-memory on intent detection
- **validation-mesh** — validate continuation package completeness
- **gmi-audit** *(опційно; лаб-скіл поза Melania-пакетом)* — інваріант **G5**: перевір, чи має система зовнішній цикл пам'яті з cold-start recovery.

---

## 📎 Advanced Patterns (v4)

Read `references/advanced-state.md` WHEN you need: diff-based updates, versioned snapshots, checkpoint triggers, merge strategies, compression levels.
Load only on demand — not proactively.

---

## Зміни
- **v1.9.1** (2026-07-13) — G5 cold-start recovery gate: валідований патерн зовнішньої пам'яті проти прогалини G5 — self-contained critical refs (критичні URL/шляхи inline, не pointer-only) + recovery-checklist ДО тесту (об'єктивний вимір 100% критичних без повтору); крос-лінк `gmi-audit`. Лише додавання. _(Джерело: experiments/gmi-g5-memory — recovery 9/9.)_
- **v1.9.0** (2026-07-11) — Compaction-дисципліна (frontier-research harvest): **(A)** 4-кроковий порядок навколо server-side стиснення: pre-compaction flush (durable ПЕРЕД стисненням; recall-first тюнінг проти poisoned summary), стабільний кеш-префікс (edits щотурну вбивають prompt-cache), context editing як другий важіль (емпірика +29% / +39% і −84% з memory), provider-agnostic fallback (STENO+hot/warm/cold = та сама дисципліна для будь-якої моделі). API-механіка — покажчик на `llm-api-builder` (DRY). **(B)** De-pin: згадка конкретних моделей у Compaction → «поточні топ-моделі (звір docs)» (правило агностичності MA). Лише додавання. _(Джерело: дослідницький звіт 2026-07-11.)_
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (артефакт злиттів). Усі записи збережено навмисно; нумерацію НЕ переписано без верифікації джерел (принцип: не вгадувати/не видаляти неперевірене)._
- **v1.8.3** (2026-06-26) — Анти-застарілість (F3): hardcoded-значення в Idempotent-Sync-Tracker (version/md5/дати) → нейтральні плейсхолдери (узгоджено з v1.5.1). Changelog-гігієна (F2): додано примітку про історичні дублі-номери — записи збережено, нумерацію не переписано без верифікації. Корекція прикладу + додавання; жодного запису НЕ видалено.
- **v1.8.2** (2026-06-26) — `evals/` реконструйовано. Форензик-аудит: claim існував з v1.4.0, але артефакт відсутній у всіх джерелах (git/транскрипти/FS) → відтворено, claim НЕ видалено. `evals/` виключається з .skill (тест-артефакт). Лише додавання.
- **v1.8.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.8.0** (2026-06-14) — Фаза harvest-2026: ієрархія пам'яті сесії hot/warm/cold (вісь свіжості, окремо від retrieval L1→L3) + Anthropic Compaction API (compaction-vs-split decision); новий shared reference `context-engineering.md` (MECW, 4 важелі, бюджет-слоти, ACON-дистиляція) — спільна база для `ai-core-runtime` + `rlm-harness`. + trim description до ≤1024 (передіснуюче перевищення).
- **v1.7.0** (2026-06-13) — typed-context handoff object (для P-28); idempotent sync tracker (механіка P-27: дрейф-детект + ідемпотентність); reusable скафолд памʼяті проєкту (ROADMAP/CONTEXT/index/log). _(Реструктуризація CORE+nodes, Фаза A — A1+A6.)_
- **v1.4.0** (2026-06-02) — додано директиву «українською-перша» + власні `evals/` (5 кейсів). _(аудит Кластер 2: P9 + Core Rule 4)_

- **v1.3.0** (2026-06-02) — memory_user_edits integration, QSS (Quick State Snapshot), multi-level memory guide, conflict detection.

- **v1.4.0** (2026-06-02) — Pre-Update Preservation Protocol; advanced-state reference (diff updates, snapshots, checkpoints, merge).
- **v1.5.0** (2026-06-10) — Фаза 3: I-3/I-12: 3-шарове розкриття пам'яті (index→context→details, ізольований субагент) + опц. compile daily→знання + опц. SQL-пошук логів.
- **v1.5.1** (2026-06-10) — анти-застарілість: прибрано зашиту конкретику (ізольований субагент; концепти+звʼязки; SQL-рушій на вибір).
- **v1.6.0** (2026-06-12) — узгодження 3-шарового розкриття з рантайм-принципом «мінімальний достатній ОБСЯГ ДАНИХ» (`ai-core-runtime`) + внутрішній мультимовний шар стиснення (фінал — українською). _(Harvest Vercel MCP → Proposal #4.)_
