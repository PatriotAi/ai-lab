# Advanced Multi-Provider Orchestration

## Streaming Aggregation (кілька моделей паралельно, live)

```javascript
async function* streamAll(nodes, msg) {
  const streams = nodes.map(n => n.d.streamGen(n.key, n.model, msg));
  const readers = streams.map((s, i) => ({ id: nodes[i].d.short, gen: s[Symbol.asyncIterator]() }));
  const pending = readers.map(r => r.gen.next().then(res => ({ r, res })));

  while (pending.some(p => p)) {
    const { r, res } = await Promise.race(pending.filter(Boolean));
    const idx = readers.indexOf(r);
    if (res.done) { pending[idx] = null; continue; }
    yield { provider: r.id, chunk: res.value };
    pending[idx] = r.gen.next().then(result => ({ r, res: result }));
  }
}
// → інтерлівиш токени від усіх моделей у реальному часі
```

---

## Response Caching (семантичний кеш)

```javascript
// Кешуй за нормалізованим хешем запиту
const cache = new Map();

function semanticKey(msg) {
  return msg.toLowerCase().replace(/\s+/g, ' ').trim();
}

async function cachedCall(node, msg) {
  const key = semanticKey(msg);
  if (cache.has(key)) {
    const { value, ts } = cache.get(key);
    if (Date.now() - ts < 3600_000) return value;  // 1 год TTL
  }
  const result = await node.d.call(node.key, node.model, msg);
  cache.set(key, { value: result, ts: Date.now() });
  return result;
}
```

Ідентичні/близькі запити → один виклик API замість багатьох.

---

## Semantic Deduplication (synthesis)

При об'єднанні відповідей кількох моделей — прибирай дублі:

```
Synthesis з дедуплікацією:
1. Збери N відповідей
2. Розбий кожну на твердження (claims)
3. Згрупуй семантично близькі твердження
4. Для кожної групи — одне формулювання + позначка консенсусу
   "✓ 3/3 моделі згодні" / "⚠ 1/3 — суперечність"
5. Фінал: унікальні твердження + рівень згоди
```

Дає чистіший результат ніж проста конкатенація.

---

## Latency-Based Routing

```javascript
// Відстежуй p50/p95 latency кожного провайдера
const latency = {};  // pid → [тривалості]

function recordLatency(pid, ms) {
  (latency[pid] ??= []).push(ms);
  if (latency[pid].length > 100) latency[pid].shift();  // sliding window
}

function p95(pid) {
  const arr = [...(latency[pid]||[])].sort((a,b)=>a-b);
  return arr[Math.floor(arr.length * 0.95)] || Infinity;
}

// Для latency-критичних задач — вибирай найшвидший вузол
function fastestNode(chain) {
  return [...chain].sort((a,b) => p95(a.pid) - p95(b.pid))[0];
}
```

---

## Provider Health Monitoring

```javascript
const health = {};  // pid → { fails, lastFail, status }

function markHealth(pid, ok) {
  const h = health[pid] ??= { fails: 0, status: 'healthy' };
  if (ok) { h.fails = 0; h.status = 'healthy'; }
  else {
    h.fails++; h.lastFail = Date.now();
    if (h.fails >= 3) h.status = 'degraded';
    if (h.fails >= 10) h.status = 'down';
  }
}

// Пропускай 'down' провайдери в роутингу (поки не відновляться)
function healthyChain(chain) {
  return chain.filter(n => health[n.pid]?.status !== 'down');
}
```

---

## Cost-Aware Routing

```
Стратегія "найдешевший достатній":
1. Класифікуй складність задачі (simple/medium/hard)
2. simple → найдешевша модель (gemini-flash, deepseek)
3. medium → середня (sonnet, gemini-pro)
4. hard   → найкраща (opus з extended thinking)

Не плати за opus там де flash впорається.
```
