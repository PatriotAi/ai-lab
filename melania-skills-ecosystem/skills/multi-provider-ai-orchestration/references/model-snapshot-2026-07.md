# Model Snapshot — 2026-07 (ЗАМІННИЙ ФАЙЛ)

> **Призначення:** єдине місце конкретики моделей/цін для всієї екосистеми (DRY). SKILL.md-и скілів
> модельно-агностичні і лише посилаються сюди. Цей файл — датований знімок: застарів → заміни файл
> новим снапшотом (нова дата в назві секцій), НЕ правлячи логіку скілів. Джерело оновлення:
> дослідження + офіційні docs провайдерів. Знімок НЕ авторитетний — звіряй перед пін-ом у код.

## Матриця провайдерів (знімок 2026-07-11)

| Провайдер / модель | Ціна I/O $/1M | Ctx | Сильні сторони | Reasoning |
|---|---|---|---|---|
| Anthropic Fable 5 (`claude-fable-5`) | 10 / 50 | 1M | найглибший reasoning, SWE-bench Pro 80% | adaptive |
| Anthropic Opus 4.8 | 5 / 25 | 1M beta | сильний баланс, Fast Mode | adaptive |
| Anthropic Haiku 4.5 | 1 / 5 | 200K | дешевий швидкий воркер | — |
| OpenAI GPT-5.6 Sol | 5 / 30 | 1.05M | топ agentic per-dollar; `ultra` = мульти-агент | effort none→max, ultra |
| OpenAI GPT-5.6 Terra | 2.50 / 15 | 1.05M | балансний флагман-tier | effort none→max |
| OpenAI GPT-5.6 Luna | 1 / 6 | 1.05M | найдешевша флагман-tier | effort none→max |
| Google Gemini 3.1 Pro | 2 / 12 | 1M | найдешевша frontier, мультимодальність | ✅ |
| xAI Grok 4.5 | 2 / 6 | 500K | токен-ефективна (~14K tok/задачу) | ✅ |
| xAI Grok 4.1 Fast | 0.20 / 0.50 | 2M | найдешевша frontier-adjacent | — |
| DeepSeek V4-Pro | 0.435 / 0.87 | 1M | SWE-bench Verified 80.6%; cache-hit $0.0036 | ✅ |
| DeepSeek V4-Flash | 0.14 / 0.28 | 1M | high-volume дешевий воркер | — |
| Zhipu GLM-5.2 | ~1.40 / 4.40 | 1M | open-weight лідер (MIT), agentic coding | ✅ |
| Moonshot Kimi K2.7 | ~0.95 in | ~256K | agentic stability: 4000+ tool calls/сесію | ✅ |
| Qwen 3.7 Max | ~2.50 / 7.50 | 1M | наука, multilingual (201 мова, вкл. UA) | ✅ |
| Mistral Large 3 | open-weight | 256K | Apache 2.0, EU compliance | — |

## COSTS-конфіг (для estimateCost; знімок 2026-07-11)

```javascript
const COSTS = {
  "claude-fable-5":   { in: 10,   out: 50   },
  "claude-opus-4-8":  { in: 5,    out: 25   },
  "claude-haiku-4-5": { in: 1,    out: 5    },
  "gpt-5.6-sol":      { in: 5,    out: 30   },
  "gpt-5.6-terra":    { in: 2.5,  out: 15   },
  "gpt-5.6-luna":     { in: 1,    out: 6    },
  "gemini-3.1-pro":   { in: 2,    out: 12   },
  "grok-4.5":         { in: 2,    out: 6    },
  "grok-4.1-fast":    { in: 0.20, out: 0.50 },
  "deepseek-v4-pro":  { in: 0.435,out: 0.87 },
  "deepseek-v4-flash":{ in: 0.14, out: 0.28 },
  "glm-5.2":          { in: 1.40, out: 4.40 },
};
```

## Reasoning-поля по провайдерах (знімок 2026-07)

```javascript
// Anthropic (поточні флагмани): adaptive; budget_tokens deprecated на них
body = { thinking: { type: "adaptive" } }
// OpenAI GPT-5.x: рівні effort (none..max, +ultra) — звір поле в docs
body = { reasoning: { effort: "high" } }
// Gemini
body = { generationConfig: { thinkingConfig: { thinkingBudget: 8000 } } }
```

## Anthropic-сумісні endpoints (знімок 2026-07)
DeepSeek: `https://api.deepseek.com/anthropic`; Grok: див. docs xAI. Патерн drop-in — у SKILL.md.

## Per-role приклади для rlm-harness (клас → модель; знімок 2026-07-11)
Політика роль→клас→техніки — канон у `rlm-harness/references/model-fit-policy.md`. Тут — лише мапінг клас→приклад:

| Клас (з політики) | Приклад моделі (2026-07) |
|---|---|
| топовий reasoning (диригент/judge/synthesis) | GPT-5.6 Sol · Fable 5 |
| сильний код-генератор | DeepSeek V4-Pro (fallback GPT-5.6 Terra) |
| дешевий reasoning (рев'ю/validation) | GLM-5.2 · Kimi K2.7 |
| long-context research | Gemini 3.1 Pro |
| швидкий дешевий (extraction/classify) | Haiku 4.5 · DeepSeek V4-Flash |
| creative | Opus 4.8 (Sonnet 5 — звірити доступність) |
| multilingual/UA translation | Qwen 3.7 Max · Gemini 3.1 Pro |

## Модель-нотатки (2026-07)
- Anthropic Sonnet 5 анонсований 2026-06-30 (introductory $2/$10 до 31.08) — ID/API-доступність звірити.
- Fable 5: Mythos-class, 128K output, adaptive thinking only.
- Економіка прогону: диригент 5-15% токенів, воркери 85-95% на дешевих → економія 25-180× на воркер-токенах.
