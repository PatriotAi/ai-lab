# Model Snapshot — 2026-11 (ЗАМІННИЙ ФАЙЛ)

> **Призначення:** єдине місце конкретики моделей/цін для всієї екосистеми (DRY). SKILL.md-и скілів
> модельно-агностичні і лише посилаються сюди. Цей файл — датований знімок: застарів → заміни файл
> новим снапшотом (нова дата в назві файла й секцій), НЕ правлячи логіку скілів. **Поточний знімок —
> найновіший файл `model-snapshot-YYYY-MM.md` у цій теці**; попередні — в історії git.
> Знімок НЕ авторитетний — звіряй перед пін-ом у код. Свіжість стереже `maintain.py verify`
> (попередження, коли знімку понад 60 днів).

**Знімок 2026-11-21.** Попередній — 2026-10-16 (36 днів; за цей час вийшли Claude Fable 5.2,
GPT-6.2, сімейство Gemini 4, Qwen4-Max). Дослідження й джерела — `docs/reviews/2026-11-20-update-upgrade.md`.

**Джерела й довіра.** Claude — довідка `claude-api` (кеш 2026-11-03; першоджерело Anthropic).
Решта — агрегатори цін і вторинні огляди, бо сторінки провайдерів із середовища недоступні (W-22);
джерела між собою розходяться: **[C]**, звір на сторінці провайдера перед пін-ом у код.
xAI, DeepSeek, Kimi — нових моделей за листопад не знайдено; рядки перенесено з 2026-10 без змін.

## Матриця провайдерів (знімок 2026-11-21)

| Провайдер / модель | Ціна I/O $/1M | Ctx | Сильні сторони | Reasoning |
|---|---|---|---|---|
| Anthropic Fable 5.2 (`claude-fable-5-2`) | 8 / 40 (fast mode 16 / 80) | 1M | найсильніший загальнодоступний клас; наступник Fable 5.1 і дешевший за нього | thinking завжди увімкнено; effort low→max (почни з high) |
| Anthropic Fable 5.1 (`claude-fable-5-1`) | 10 / 50 | 1M | попереднє покоління топового класу; API ще обслуговує — нова маршрутизація на 5.2 | thinking завжди увімкнено; effort low→max |
| Anthropic Opus 5.5 (`claude-opus-5-5`) | 4 / 20 | 1M | сильний баланс; Fast Mode $8/$40 | thinking не вимикається; effort, **за замовчуванням medium** |
| Anthropic Sonnet 5.5 (`claude-sonnet-5-5`) | 2 / 10 | 1M | **середній клас**: на візуальних і агентських задачах — на рівні Opus за половину ціни | adaptive; вимкнення — `between_tools` |
| Anthropic Haiku 5.5 (`claude-haiku-5-5`) | 0.10 / 0.50 (≤100K; далі 0.50 / 2.50) | 1M | найдешевший воркер Claude | adaptive; effort за замовчуванням medium |
| OpenAI GPT-6.2 Astra | 8 / 40 [C] | — | топ-клас; наступник GPT-6 Astra (−20%) | effort |
| OpenAI GPT-6.2 Sol | 2 / 10 [C] | — | середній клас | effort |
| OpenAI GPT-6 Luna | 0.10 / 0.50 [C] | — | найдешевший; AA Cyber Index 53 (max) | effort |
| Google Gemini 4 Neon | 3 / 15 [C] | — | середній у сімействі Gemini 4 (листопад) | ✅ |
| Google Gemini 4 Hydrogen | 1.50 / 7.50 [C] | — | дешевший у сімействі Gemini 4 | ✅ |
| Google Gemini 3.1 Flash-Lite | 0.25 / 1.50 [C] | — | дешевий high-volume | ✅ |
| Qwen Qwen4-Max | 1.50 / 4.50 [C] | 1M | дешевий сильний загальний | ✅ |
| xAI Grok 4.7 | 2 / 6 [C]; від 200K токенів — 4 / 12 на весь запит | 500K | AA Cyber Index 56 (xhigh) — ділить 1-ше місце | low/medium/high/xhigh |
| Moonshot Kimi K3 | 3 / 15 [C] | — | open-weight лідер AA Intelligence (~59.7) | ✅ |
| DeepSeek V4-Pro | 0.435 / 0.87 [C] (джерела розходяться; пікові години — дорожче) | 1M | дешевий сильний код | ✅ |
| DeepSeek V4-Flash | 0.14 / 0.28 [C] | 1M | high-volume дешевий воркер | — |

**Що змінилось проти 2026-10 і чому це важливо для маршрутизації:**
- Топовий клас подешевшав на 20%: Fable 5.2 — $8 / $40 (Fable 5.1 був $10 / $50); так само
  GPT-6.2 Astra. Диригент на найсильнішому класі коштує менше, ніж місяць тому.
- Fable 5.2 перевіряє незмінність історії розмови для **всіх** акаунтів, а його блоки мислення не
  читає жодна раніша модель: харнес, що редагує історію, або перемикання на старішу модель
  посеред розмови — тепер помилка або втрата міркувань (деталі — довідка `claude-api`).
- У Google — нове сімейство Gemini 4 з кількома цінами; ранг моделей у ньому за якістю не звірено.
- З переліку прибрано GLM-5.3 і MiMo-V2.6-Pro: ціни так і не підтвердились (див. знімок 2026-10 в історії git).

## COSTS-конфіг (для estimateCost; знімок 2026-11-21)

```javascript
const COSTS = {
  "claude-fable-5-2":  { in: 8,    out: 40   },
  "claude-fable-5-1":  { in: 10,   out: 50   },
  "claude-opus-5-5":   { in: 4,    out: 20   },
  "claude-sonnet-5-5": { in: 2,    out: 10   },
  "claude-haiku-5-5":  { in: 0.10, out: 0.50 },  // ≤100K вхідних; далі 0.50 / 2.50
  "gpt-6.2-astra":     { in: 8,    out: 40   },  // [C]
  "gpt-6.2-sol":       { in: 2,    out: 10   },  // [C]
  "gpt-6-luna":        { in: 0.10, out: 0.50 },  // [C]
  "gemini-4-neon":     { in: 3,    out: 15   },  // [C]
  "gemini-4-hydrogen": { in: 1.50, out: 7.50 },  // [C]
  "qwen4-max":         { in: 1.50, out: 4.50 },  // [C]
  "grok-4.7":          { in: 2,    out: 6    },  // [C]; ≥200K токенів — 4 / 12
  "kimi-k3":           { in: 3,    out: 15   },  // [C]
  "deepseek-v4-pro":   { in: 0.435,out: 0.87 },  // [C]
  "deepseek-v4-flash": { in: 0.14, out: 0.28 },  // [C]
};
```

## Reasoning-поля по провайдерах (знімок 2026-11)

```javascript
// Anthropic (покоління 5.x): adaptive; budget_tokens → 400; глибину керує effort
body = { thinking: { type: "adaptive" }, output_config: { effort: "high" } }
// Fable 5.2: thinking не налаштовується (лише adaptive або без поля); почни з effort high
// Opus 5.5: thinking не вимикається, effort за замовчуванням medium — став явно
// Sonnet 5.5: вимкнути thinking — { type: "between_tools" } (лише при effort ≤ high)
// OpenAI GPT-6.x: рівні effort — звір поле в docs
body = { reasoning: { effort: "high" } }
// Gemini
body = { generationConfig: { thinkingConfig: { thinkingBudget: 8000 } } }
```

## Anthropic-сумісні endpoints (знімок 2026-11)
DeepSeek: `https://api.deepseek.com/anthropic`; Grok: див. docs xAI. Патерн drop-in — у SKILL.md.

## Per-role приклади для rlm-harness (клас → модель; знімок 2026-11-21)
Політика роль→клас→техніки — канон у `rlm-harness/references/model-fit-policy.md`. Тут — лише мапінг клас→приклад:

| Клас (з політики) | Приклад моделі (2026-11) |
|---|---|
| топовий reasoning (диригент/judge/synthesis) | Fable 5.2 · GPT-6.2 Astra |
| сильний код-генератор | Opus 5.5 · Sonnet 5.5 (дешевше — DeepSeek V4-Pro) |
| дешевий reasoning (рев'ю/validation) | Sonnet 5.5 · Kimi K3 · GPT-6.2 Sol · Qwen4-Max |
| long-context research | Gemini 4 Neon [C] · будь-яка модель Claude 5.5 (1M) |
| швидкий дешевий (extraction/classify) | Haiku 5.5 · GPT-6 Luna · DeepSeek V4-Flash |
| creative / візуальні та 3D-артефакти | Sonnet 5.5 · Opus 5.5 |
| безпековий аудит власного коду | Grok 4.7 (xhigh) · GPT-6 Luna (max) — за AA Cyber Index; агент не замінює людський security review |
| multilingual/UA translation | Gemini 4 Neon [C] · модель Claude 5.5 (звір на власних прикладах) |

## Модель-нотатки (2026-11)
- Попередні покоління (Fable 5.1, Opus 4.8, Haiku 4.5, Fable 5, Sonnet 5) API ще обслуговує, але
  нова маршрутизація — на 5.5/5.2: дешевше й сильніше.
- Fable 5.2 / 5.1: forced `tool_choice` (`any`/`tool`) → 400; потрібна 30-денна політика зберігання
  даних. Claude Mythos 5.2 — те саме, що Fable 5.2, лише для верифікованих організацій.
- OpenAI GPT-6 Cyber ($20 / $100 [C]) — лише для схвалених організацій, у маршрутизацію не входить.
- Економіка прогону: диригент 5-15% токенів, воркери 85-95% на дешевих; найдешевший клас — у 40×
  дешевший за Opus 5.5 на вході.

## WebLLM: локальні моделі за класом пристрою (знімок 2026-10; перенесено з `browser-local-ai-webllm` 2026-11-17)
Класи для правила «RAM → клас» навички `browser-local-ai-webllm`: `quality` = `Llama-3.1-8B-Instruct-q4f32_1-MLC` ·
`general` = `Qwen2.5-7B-Instruct-q4f16_1-MLC` · `compact` = `Phi-3.5-mini-instruct-q4f16_1-MLC` ·
`micro` = `Llama-3.2-1B-Instruct-q4f16_1-MLC`.
`familyRank`: `{"Qwen3.5":100,"Qwen3":95,"Llama-3.2":90,"Phi-4":88,"gemma3":86,"Qwen2.5":82}`.
Embedding-модель для RAG у браузері: `snowflake-arctic-embed-m-q0f32-MLC-b4`.
Окремий вхід «текст + аудіо» — `gemma-4-E2B-it-q4f16_1-MLC` / `…q4f32_1-MLC` (з WebLLM 0.2.86).
Вбудований AI браузера (`window.ai`) — Gemini Nano, лише desktop/ChromeOS.
Розміри (звірено за `src/config.ts` WebLLM v0.2.87, 2026-11-07): Gemma 4 E2B q4f16 ≈ 3387 МБ, q4f32 ≈ 3863 МБ.

| Модель | VRAM | Швидкість | Якість | Use case |
|---|---|---|---|---|
| `Llama-3.2-1B-Instruct-q4f16_1-MLC` | ~1GB | ⚡⚡⚡ | добра | тригери, класифікація |
| `Llama-3.2-3B-Instruct-q4f16_1-MLC` | ~2GB | ⚡⚡ | краща | чат, короткі відповіді |
| `Phi-3.5-mini-instruct-q4f16_1-MLC` | ~2.5GB | ⚡⚡ | відмінна | розуміння коду |
| `Qwen2.5-7B-Instruct-q4f16_1-MLC` | ~5GB | ⚡ | дуже добра | загальне завдання |
| `gemma-4-E2B-it-q4f16_1-MLC` / `…q4f32_1-MLC` | ~3.4 / ~3.9GB | ⚡⚡ | добра | текст + аудіо-вхід (з 0.2.86) |
| `Llama-3.1-8B-Instruct-q4f32_1-MLC` | ~6GB | ⚡ | відмінна | best for quality |
| `Llama-3.3-70B` | ~40GB | — | найкраща | лише в серверних браузерах |
