# Advanced n8n Workflows

## Sub-Workflows (модульність)

Виноси повторювану логіку в окремі workflow, викликай через Execute Workflow node:

```
Main Workflow:
  Trigger → [Execute Workflow: "validate-input"] → [Execute Workflow: "process"] → Response

"validate-input" (окремий workflow):
  Workflow Trigger → IF (valid?) → Set (normalized) / Stop And Error
```

**Переваги:** DRY, легше тестувати, можна перевикористати в кількох workflow.

---

## Queue Mode (висока пропускна здатність)

```
Для обробки тисяч завдань:
- n8n у queue mode (EXECUTIONS_MODE=queue)
- Redis як черга
- Кілька worker-процесів
- Main process лише приймає webhook, кладе в чергу
- Workers обробляють паралельно

Webhook → Redis Queue → [Worker 1, Worker 2, ... Worker N] → Results
```

---

## Webhook Security (HMAC)

Перевіряй що webhook справді від довіреного джерела:

```javascript
// Code node після Webhook
const crypto = require('crypto');
const signature = $input.first().headers['x-signature'];
const payload = JSON.stringify($input.first().body);
const expected = crypto
  .createHmac('sha256', $env.WEBHOOK_SECRET)
  .update(payload)
  .digest('hex');

if (signature !== expected) {
  throw new Error('Invalid signature — rejected');
}
return $input.all();
```

Без HMAC будь-хто може викликати твій webhook. Завжди перевіряй для production.

---

## Error Workflows

```
Налаштування глобального обробника помилок:
1. Створи окремий workflow з "Error Trigger" node
2. У Settings основного workflow → Error Workflow → вибери його
3. При будь-якій помилці n8n автоматично запускає error workflow

Error Workflow:
  Error Trigger → Set (format error) → Slack/Telegram (alert team)
                                     → Postgres (log to errors table)
```

---

## Retry & Backoff

```
На кожному HTTP Request node:
- Settings → Retry On Fail → ON
- Max Tries: 3
- Wait Between Tries: 1000ms (exponential через expression)

Для складнішого backoff — Code node:
```

```javascript
const attempt = $runIndex || 0;
const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
await new Promise(r => setTimeout(r, delay));
return $input.all();
```

---

## Batch Processing з Rate Limiting

```
Loop Over Items (batchSize: 10)
  → HTTP Request (API call)
  → Wait (200ms)              ← поважай rate limit API
  → (loop back)

Обробка 1000 items по 10 за раз з паузами = не перевищиш rate limit.
```

---

## Idempotency у Workflow

```
Перед обробкою — перевір чи вже оброблено:
Webhook → Postgres (SELECT WHERE event_id = X)
       → IF (exists?) → Stop (already processed)
                     → continue + INSERT event_id

Це захищає від дублів коли джерело надсилає webhook двічі.
```
