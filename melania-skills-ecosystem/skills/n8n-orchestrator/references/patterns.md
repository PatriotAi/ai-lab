# Automation Patterns Reference

## Pattern 1: Webhook → Validate → CRM → Notification
**Use case:** Form submission, lead capture, sales automation

```
Webhook → Set (normalize) → IF (validate required fields)
  ↓ valid
HTTP Request (CRM upsert) → IF (success?)
  ↓ yes                          ↓ no
Slack/Telegram (notify)    Error Trigger → Notify failure
```

## Pattern 2: Webhook → AI → Database → Response
**Use case:** AI-powered API endpoint, chatbot backend

```
Webhook → Set (prepare prompt) → HTTP Request (Claude/OpenAI)
  → Code (parse AI response) → Postgres (save result)
  → Respond to Webhook (return JSON)
```

## Pattern 3: RSS → AI Summary → Telegram
**Use case:** Content monitoring, newsletter automation

```
Schedule Trigger (every hour) → RSS Feed Read
  → Split In Batches → IF (already processed?)
  ↓ new item
HTTP Request (AI summarize) → Telegram (send summary)
  → Set (mark as processed) → Postgres (save)
```

## Pattern 4: Stripe → Analytics → Dashboard
**Use case:** Payment event processing, revenue tracking

```
Webhook (Stripe event) → Set (parse event type)
  → Switch (payment_intent.succeeded / failed / refunded)
  ↓ succeeded
Postgres (record revenue) → HTTP Request (analytics API)
  → Slack (notify team)
```

## Pattern 5: Webhook → Queue → Worker → Database
**Use case:** Async job processing, background tasks

```
Webhook → Set (create job) → Postgres (insert job queue)
  → Respond to Webhook (202 Accepted)

[Separate workflow - Schedule Trigger every minute]
Postgres (fetch pending jobs) → Split In Batches
  → Code (process job) → Postgres (update status)
  → IF (error?) → Error handler
```

## Pattern 6: AI Agent Loop
**Use case:** Multi-step AI reasoning, autonomous agents

```
Trigger → Set (initial state) → HTTP Request (AI step 1)
  → Code (parse + decide) → IF (done?)
  ↓ no (max 5 iterations)        ↓ yes
Set (update state) ────────────→ Output formatter
↑___________________________|     → Response
```
Note: Always set max iteration limit. Never allow unbounded loops.
