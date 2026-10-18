# Model Snapshot — 2026-10 (ЗАМІННИЙ ФАЙЛ)

> **Призначення:** єдине місце конкретики моделей/цін для всієї екосистеми (DRY). SKILL.md-и скілів
> модельно-агностичні і лише посилаються сюди. Цей файл — датований знімок: застарів → заміни файл
> новим снапшотом (нова дата в назві файла й секцій), НЕ правлячи логіку скілів. **Поточний знімок —
> найновіший файл `model-snapshot-YYYY-MM.md` у цій теці**; попередні — в історії git.
> Знімок НЕ авторитетний — звіряй перед пін-ом у код. Свіжість стереже `maintain.py verify`
> (попередження, коли знімку понад 60 днів).

**Знімок 2026-10-16.** Попередній — 2026-07-11 (97 днів; за цей час вийшли покоління Claude 5.5,
GPT-6, Grok 4.7, Kimi K3). Знайдено дослідженням `docs/reviews/2026-10-16-tools-harvest.md`.

**Джерела й довіра.** Claude — довідка `claude-api` (кеш 2026-10-06; першоджерело Anthropic).
Решта — агрегатори цін і вторинні огляди, бо `artificialanalysis.ai` і сторінки OpenAI з
середовища недоступні (W-22): **[C]**, звір на сторінці провайдера перед пін-ом у код.

## Матриця провайдерів (знімок 2026-10-16)

| Провайдер / модель | Ціна I/O $/1M | Ctx | Сильні сторони | Reasoning |
|---|---|---|---|---|
| Anthropic Fable 5.1 (`claude-fable-5-1`) | 10 / 50 | 1M | найсильніший клас; лідер AA Intelligence Index (~65.7, вересень) | thinking завжди увімкнено; effort low→max |
| Anthropic Opus 5.5 (`claude-opus-5-5`) | 4 / 20 | 1M | сильний баланс; AA-3D 1190 (нарівні з лідером); Fast Mode $8/$40 | thinking не вимикається; effort, **за замовчуванням medium** |
| Anthropic Sonnet 5.5 (`claude-sonnet-5-5`) | 2 / 10 | 1M | **середній клас**: лідер AA-3D (1194) за половину ціни Opus | adaptive; вимкнення — `between_tools` |
| Anthropic Haiku 5.5 (`claude-haiku-5-5`) | 0.10 / 0.50 (≤100K; далі 0.50 / 2.50) | 1M | найдешевший воркер Claude | adaptive; effort за замовчуванням medium |
| OpenAI GPT-6 Astra | 10 / 50 [C] | — | топ-клас; AA-3D 1165 | effort |
| OpenAI GPT-6 Sol | 2 / 10 [C] | — | середній клас | effort |
| OpenAI GPT-6 Luna | 0.10 / 0.50 [C] | — | найдешевший; AA Cyber Index 53 (max), 3-тє місце | effort |
| Google Gemini 3.1 Pro | 2.50 / 15 [C] | 1M | мультимодальність, long-context | ✅ |
| Google Gemini 3.1 Flash-Lite | 0.25 / 1.50 [C] | — | дешевий high-volume | ✅ |
| xAI Grok 4.7 | 2 / 6 [C]; від 200K токенів — 4 / 12 на весь запит | 500K | AA Cyber Index 56 (xhigh) — ділить 1-ше місце; але ~$11.67 за задачу індексу | low/medium/high/xhigh |
| Moonshot Kimi K3 | 3 / 15 [C] | — | open-weight лідер AA Intelligence (~59.7) | ✅ |
| Zhipu GLM-5.3 | ціну не підтверджено (дані для 5.2: 1.40 / 4.40) | — | open-weight, AA Intelligence ~59.5 | ✅ |
| Xiaomi MiMo-V2.6-Pro | ціну не знайдено | — | AA Cyber Index 56 — ділить 1-ше місце | ✅ |
| DeepSeek V4-Pro | 0.435 / 0.87 [C] | 1M | дешевий сильний код | ✅ |
| DeepSeek V4-Flash | 0.14 / 0.28 [C] (пікові години — дорожче) | 1M | high-volume дешевий воркер | — |

**Що змінилось проти 2026-07 і чому це важливо для маршрутизації:**
- З'явився **середній клас Claude** (Sonnet 5.5): на візуальних і агентських задачах він
  дорівнює старшому за половину ціни (AA-3D). Правило економії «найдешевший придатний клас»
  тепер має проміжну сходинку між Haiku і Opus.
- Ціни нижнього класу впали на порядок: Haiku 5.5 і GPT-6 Luna — $0.10 / $0.50
  (Haiku 4.5 був $1 / $5).
- Opus подешевшав: 5.5 — $4 / $20 (4.8 був $5 / $25).
- Безпекові задачі отримали окремий рейтинг (AA Cyber Index). Місце моделей Claude в ньому
  не з'ясовано: сайт недоступний.

## COSTS-конфіг (для estimateCost; знімок 2026-10-16)

```javascript
const COSTS = {
  "claude-fable-5-1":  { in: 10,   out: 50   },
  "claude-opus-5-5":   { in: 4,    out: 20   },
  "claude-sonnet-5-5": { in: 2,    out: 10   },
  "claude-haiku-5-5":  { in: 0.10, out: 0.50 },  // ≤100K вхідних; далі 0.50 / 2.50
  "gpt-6-astra":       { in: 10,   out: 50   },  // [C]
  "gpt-6-sol":         { in: 2,    out: 10   },  // [C]
  "gpt-6-luna":        { in: 0.10, out: 0.50 },  // [C]
  "gemini-3.1-pro":    { in: 2.50, out: 15   },  // [C]
  "grok-4.7":          { in: 2,    out: 6    },  // [C]; ≥200K токенів — 4 / 12
  "kimi-k3":           { in: 3,    out: 15   },  // [C]
  "deepseek-v4-pro":   { in: 0.435,out: 0.87 },  // [C]
  "deepseek-v4-flash": { in: 0.14, out: 0.28 },  // [C]
};
```

## Reasoning-поля по провайдерах (знімок 2026-10)

```javascript
// Anthropic (покоління 5.x): adaptive; budget_tokens → 400; глибину керує effort
body = { thinking: { type: "adaptive" }, output_config: { effort: "high" } }
// Opus 5.5: thinking не вимикається, effort за замовчуванням medium — став явно
// Sonnet 5.5: вимкнути thinking — { type: "between_tools" } (лише при effort ≤ high)
// OpenAI GPT-6: рівні effort — звір поле в docs
body = { reasoning: { effort: "high" } }
// Gemini
body = { generationConfig: { thinkingConfig: { thinkingBudget: 8000 } } }
```

## Anthropic-сумісні endpoints (знімок 2026-10)
DeepSeek: `https://api.deepseek.com/anthropic`; Grok: див. docs xAI. Патерн drop-in — у SKILL.md.

## Per-role приклади для rlm-harness (клас → модель; знімок 2026-10-16)
Політика роль→клас→техніки — канон у `rlm-harness/references/model-fit-policy.md`. Тут — лише мапінг клас→приклад:

| Клас (з політики) | Приклад моделі (2026-10) |
|---|---|
| топовий reasoning (диригент/judge/synthesis) | Fable 5.1 · GPT-6 Astra |
| сильний код-генератор | Opus 5.5 · Sonnet 5.5 (дешевше — DeepSeek V4-Pro) |
| дешевий reasoning (рев'ю/validation) | Sonnet 5.5 · Kimi K3 · GPT-6 Sol |
| long-context research | Gemini 3.1 Pro · будь-яка модель Claude 5.5 (1M) |
| швидкий дешевий (extraction/classify) | Haiku 5.5 · GPT-6 Luna · DeepSeek V4-Flash |
| creative / візуальні та 3D-артефакти | Sonnet 5.5 (лідер AA-3D) · Opus 5.5 |
| безпековий аудит власного коду | Grok 4.7 (xhigh) · MiMo-V2.6-Pro · GPT-6 Luna (max) — за AA Cyber Index; агент не замінює людський security review |
| multilingual/UA translation | Gemini 3.1 Pro · модель Claude 5.5 (звір на власних прикладах) |

## Модель-нотатки (2026-10)
- Попередні покоління (Opus 4.8, Haiku 4.5, Fable 5, Sonnet 5) API ще обслуговує, але нова
  маршрутизація — на 5.5/5.1: дешевше й сильніше.
- Fable 5.1: forced `tool_choice` (`any`/`tool`) → 400; потрібна 30-денна політика зберігання даних.
- Економіка прогону: диригент 5-15% токенів, воркери 85-95% на дешевих → економія на воркер-токенах
  зросла: найдешевший клас тепер у 40× дешевший за Opus 5.5 на вході.
