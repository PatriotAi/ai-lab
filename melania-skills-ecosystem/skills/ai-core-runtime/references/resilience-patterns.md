# Resilience & Observability Patterns

## Circuit Breaker

Захист від каскадних збоїв при виклику зовнішніх сервісів:

```python
class CircuitBreaker:
    def __init__(self, fail_threshold=5, reset_timeout=60):
        self.failures = 0
        self.threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.state = "CLOSED"   # CLOSED → OPEN → HALF_OPEN
        self.opened_at = None

    async def call(self, fn):
        if self.state == "OPEN":
            if time.time() - self.opened_at > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit OPEN — fail fast")
        try:
            result = await fn()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"; self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state = "OPEN"; self.opened_at = time.time()
            raise
```

**Стани:** CLOSED (норма) → OPEN (fail fast після N помилок) → HALF_OPEN (пробний запит).

---

## Retry з Idempotency Key

```python
async def retry_idempotent(fn, key, max_attempts=3):
    """Безпечний retry — однаковий key гарантує що операція не дублюється."""
    for attempt in range(max_attempts):
        try:
            return await fn(idempotency_key=key)
        except TransientError as e:
            if attempt == max_attempts - 1:
                raise
            delay = min(2 ** attempt + random.random(), 30)  # jitter
            await asyncio.sleep(delay)
```

**Правило:** мутуючі операції (POST/PUT) завжди з idempotency key, щоб retry не створив дублікат.

---

## State Machine для Складних Workflow

```python
TRANSITIONS = {
    "idle":       {"start": "running"},
    "running":    {"pause": "paused", "complete": "done", "fail": "error"},
    "paused":     {"resume": "running", "cancel": "cancelled"},
    "error":      {"retry": "running", "abort": "cancelled"},
    "done":       {},  # terminal
    "cancelled":  {},  # terminal
}

def transition(state, event):
    nxt = TRANSITIONS.get(state, {}).get(event)
    if nxt is None:
        raise ValueError(f"Invalid: {state} --{event}--> ?")
    return nxt
```

Явні переходи унеможливлюють невалідні стани. Термінальні стани (done/cancelled) не мають виходів.

---

## Observability — Structured Logging

```python
import json, time

def log_event(stage, **fields):
    print(json.dumps({
        "ts": time.time(),
        "stage": stage,          # intent / route / validate / output
        "skill": fields.pop("skill", None),
        **fields
    }))

# Приклад трасування pipeline:
log_event("intent", skill="ai-core-runtime", classified="architecture", confidence=0.9)
log_event("route", activated=["architect","validator"], tokens_est=1200)
log_event("validate", verdict="VALID", checks_passed=4)
```

**Що логувати на кожному кроці:** stage, активовані скіли/агенти, оцінка токенів, вердикт валідації, тривалість. Це дає повну трасу для дебагу.

---

## Graceful Degradation

| Збій | Fallback |
|---|---|
| Extended thinking timeout | Перейти на звичайну відповідь без thinking |
| MCP server недоступний | Працювати без нього, повідомити що частина даних відсутня |
| Validation inconclusive | Повернути UNKNOWN + часткові результати, не блокувати все |
| Один агент впав | Решта продовжує; позначити прогалину в output |

Принцип: часткова відповідь з чесним позначенням прогалин краща за повну відмову.
