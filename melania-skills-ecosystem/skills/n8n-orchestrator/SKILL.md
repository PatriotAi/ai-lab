---
name: n8n-orchestrator
description: >
  Designs and generates valid, production-ready n8n workflows with full
  architecture design, node mapping, connection schemas, exportable JSON,
  validation, debugging guidance, and performance optimization.

  USE THIS SKILL whenever the user asks to: create automation workflows,
  build AI pipelines in n8n, design webhooks, connect APIs, automate CRM
  processes, build notification systems, create routing logic, orchestrate
  multi-step automations, or export/import n8n workflow JSON.

  Also trigger for: "зроби автоматизацію в n8n", "n8n workflow",
  "automation pipeline", "webhook trigger", "побудуй пайплайн",
  "connect APIs automatically", "AI automation", "CRM automation",
  "Telegram bot workflow", "n8n JSON", "workflow nodes".

  ALWAYS use this skill for anything n8n-related, even if it seems simple. DO NOT use for non-n8n automation, plain code scripts, or single API calls without a workflow.
license: MIT
metadata:
  author: Prompt Ingeniero Ecosystem
  version: 2.8.3
  category: automation
---

# N8N Orchestrator
> Працює українською за замовчуванням (українською-перша): пояснення, нотатки й приклади — українською; перемикання лише слідом за користувачем.
>
> **Неофіційний.** Не пов'язаний з, не схвалений і не спонсорований n8n GmbH. «n8n» — торгова марка n8n GmbH; назва вжита суто референційно (опис сумісності).


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Design Methodology

Always follow this sequence. Never jump straight to JSON.

```
1. UNDERSTAND  → clarify trigger, goal, integrations needed
2. ARCHITECTURE → draw the high-level flow in text
3. NODE LIST    → enumerate every node with its role
4. CONNECTIONS  → define the edge map (A→B→C)
5. JSON         → generate the exportable workflow
6. VALIDATE     → check dependencies, credentials, edge cases
7. OPTIMIZE     → simplify, add error handling, suggest improvements
```

---

## Standard Workflow Pattern

Most n8n workflows follow this spine — adapt as needed:

```
[Trigger]
    ↓
[Normalize / Parse]    → standardize incoming data format
    ↓
[Validate Input]       → check required fields, reject bad data
    ↓
[Decode / Classify]    → understand what the trigger wants
    ↓
[Router / IF]          → branch to correct path
    ↓
[Action Nodes]         → execute the work (API call, DB write, AI, etc.)
    ↓
[Validation / Check]   → confirm success, catch errors
    ↓
[Merge / Aggregate]    → combine parallel branches
    ↓
[Response / Notify]    → send result to user or system
```

---

## Node Reference

### Trigger Nodes
| Node | Use Case |
|---|---|
| Webhook | HTTP-triggered workflows |
| Schedule Trigger | Time-based automation |
| Telegram Trigger | Bot message handling |
| Email Trigger | IMAP inbox monitoring |
| RSS Feed Trigger | Content monitoring |

### Processing Nodes
| Node | Use Case |
|---|---|
| Set | Define / transform variables |
| Code | Custom JavaScript/Python logic |
| IF | Boolean branching |
| Switch | Multi-path routing |
| Merge | Combine parallel branches |
| Split In Batches | Process arrays in chunks |
| Loop Over Items | Iterate over collections |

### Integration Nodes
| Node | Use Case |
|---|---|
| HTTP Request | Any REST API |
| Postgres / MySQL | Database operations |
| Slack | Team notifications |
| Telegram | Bot messages |
| Gmail / SMTP | Email sending |
| Google Sheets | Spreadsheet operations |
| OpenAI / Anthropic | AI model calls |

### Utility Nodes
| Node | Use Case |
|---|---|
| Wait | Delay / retry logic |
| Error Trigger | Global error catching |
| Respond to Webhook | Return HTTP response |
| No Operation | Placeholder / debugging |

---

## JSON Workflow Template

Use this minimal skeleton for all generated workflows:

```json
{
  "name": "Workflow Name",
  "nodes": [
    {
      "id": "node_id_unique",
      "name": "Node Display Name",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [250, 300],
      "parameters": {}
    }
  ],
  "connections": {
    "Node Display Name": {
      "main": [
        [{ "node": "Next Node Name", "type": "main", "index": 0 }]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

**Rules for valid JSON output:**
- Every `id` must be unique (use UUID format or short unique string)
- `position` values: start at [250, 300], increment by [250, 0] per node
- Always include `typeVersion` (check n8n docs for current version)
- Use environment variables for all credentials: `{{ $env.MY_SECRET }}`
- Never hardcode API keys, tokens, or passwords

---

## Error Handling Requirements

Every production workflow MUST include:

1. **Error Trigger node** — catches unhandled errors globally
2. **Try/Catch with Code node** — for critical operations
3. **IF node after HTTP Request** — check `{{ $response.statusCode }}`
4. **Notification on error** — Slack/Telegram alert with error details
5. **Fallback path** — graceful degradation, never silent failure

---

## Common Automation Patterns

See `references/patterns.md` for detailed implementations of:
- Webhook → Validate → CRM → Notification
- Webhook → AI → Database → Response
- RSS → AI Summary → Telegram
- Stripe Event → Analytics → Dashboard
- Webhook → Queue → Worker → Database
- AI Agent Loop → Validation → Output

---

## Scheduled Resync Pattern (каденція P-27)

Періодичний воркфлоу, що тримає диск і трекер стану в згоді («диск завжди канонічний»):

```
[Schedule Trigger]        ← фікс. каденція (напр. щогодини на :07)
  ↓
[Read state]              ← поточний md5/версія одиниць (скіли/артефакти)
  ↓
[Compare to tracker]      ← звірка з .skill-sync-tracker.json (idempotency: id+hash)
  ↓
[IF drift]                ← різниця → синхронізувати/позначити; немає → No-Op
  ↓
[Update tracker + notify] ← оновити last_synced/md5; алерт у Telegram за потреби
```

- Ідемпотентність: незмінне — пропускай (не переробляй); деталі — `references/advanced-workflows.md`.
- Узгоджено з `continuation-memory` (Idempotent Sync Tracker) — n8n тут лише виконавець каденції.

---

## AI Agent Nodes (n8n v1.x+)

n8n має нативні AI вузли. Використовуй їх замість HTTP Request до LLM де можливо:

```
AI Agent Node
├── Chat Model: @n8n/n8n-nodes-langchain.lmChatAnthropic
│   └── model: claude-opus-4-8, temperature: 0.3
├── Memory: @n8n/n8n-nodes-langchain.memoryBufferWindow
│   └── contextWindow: 10  ← останні 10 повідомлень
├── Tools:
│   ├── Calculator
│   ├── HTTP Request Tool ← будь-який REST API як інструмент
│   ├── Vector Store Tool ← пошук у базі знань
│   └── Code Tool ← виконання JS/Python
└── Output Parser: JSON / Structured Output
```

**Коли AI Agent Node замість HTTP Request:**
- Потрібна multi-step reasoning (агент сам вирішує скільки кроків)
- Треба пам'ять між повідомленнями в чаті
- Інструменти викликаються динамічно

---

## RAG Workflow Pattern

```
Trigger
  ↓
[Split In Batches]        ← документи/чанки
  ↓
[Embeddings Node]         ← @n8n/n8n-nodes-langchain.embeddingsOpenAi
  ↓                          або embeddingsAnthropic
[Vector Store Insert]     ← Pinecone / Supabase / Qdrant / In-Memory
  ↓
[Webhook — Query]
  ↓
[Embeddings Node]         ← той самий провайдер!
  ↓
[Vector Store Retrieval]  ← top_k: 5, threshold: 0.7
  ↓
[AI Agent]                ← context з retrieved docs
  ↓
[Response]
```

---

## Structured Output Node

Для надійного JSON з LLM (замість ручного парсингу):

```json
{
  "type": "@n8n/n8n-nodes-langchain.outputParserStructured",
  "parameters": {
    "schemaType": "fromJson",
    "inputSchema": "{"type":"object","properties":{"action":{"type":"string"},"params":{"type":"object"}},"required":["action"]}"
  }
}
```

---

---

## Output Format

For every workflow request, output exactly:

```
### Architecture
[Text diagram of the flow]

### Node List
[Table: Node | Type | Purpose]

### Connections
[Edge map: NodeA → NodeB → NodeC]

### JSON Workflow
[Complete importable JSON]

### Validation Notes
[What to check before deploying]

### Optimization Suggestions
[Improvements to consider]
```

---

## Конектори дій (оркеструй НАЯВНЕ)
Перш ніж будувати інтеграцію — перевір, чи дію вже покрито **наявним конектором/інструментом середовища**.
Виявляй їх **на льоту**, не покладайся на фіксований перелік (склад конекторів змінюється з часом і середовищем).
- **Не вводь новий конектор-шар**, якщо наявний уже покриває дію.
- **Нормалізуй схеми дій**: однаковий формат вход/вихід незалежно від конектора (адаптер на межі).
- **Авторизаційний lifecycle**: scoped-доступ, оновлення/протермінування токенів (делегуй відповідному скілу).
- Розділяй шари: **доступ** / **нормалізовані дії** / **поведінка** — не змішуй.

## Security Rules

- **Always** use `$env.VARIABLE_NAME` for secrets
- **Never** expose API keys, tokens, passwords in workflow JSON
- **Always** validate webhook inputs before processing
- **Use** n8n credential manager for OAuth/API key storage
- **Document** required credentials in Validation Notes section

---

## 📎 Advanced Patterns (v4)

Read `references/advanced-workflows.md` WHEN you need: sub-workflows, queue mode, HMAC webhook security, error workflows, retry/backoff, idempotency.
Load only on demand — not proactively.

---

## Зміни
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (артефакт злиттів). Усі записи збережено; нумерацію НЕ переписано без верифікації джерел._
- **v2.8.3** (2026-06-26) — Stage 3: **S-1** `claude-opus-4-5`→`claude-opus-4-8` у прикладі. **S-2** примітка про дубль v2.6.0. **S-3** +власні `evals/` (5, канон-схема). Корекція + додавання.
- **v2.8.2** (2026-06-15) — B2 (safety-compliance-gate): дисклеймер неприналежності — n8n (n8n GmbH).
- **v2.8.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v2.8.0** (2026-06-13) — A1: Scheduled Resync Pattern (каденція P-27: звірка з sync-tracker, ідемпотентність, оновлення стану). _(Реструктуризація CORE+nodes, Фаза A.)_
- **v2.6.0** (2026-06-02) — додано директиву «українською-перша» + власні `evals/` (5 кейсів). _(аудит Кластер 2: P9 + Core Rule 4)_

- **v2.5.0** (2026-06-02) — AI Agent nodes, RAG workflow, Vector Store, Structured Output patterns.

- **v2.6.0** (2026-06-02) — Pre-Update Preservation Protocol; advanced-workflows reference (sub-workflows, queue mode, HMAC, error workflows).
- **v2.7.0** (2026-06-10) — Фаза 5: I-9: оркестрація наявних конекторів дій (виявлення на льоту без фіксованого переліку, нормалізація схем, авторизаційний lifecycle, розділення шарів).
