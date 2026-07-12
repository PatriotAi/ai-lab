---
name: multi-provider-ai-orchestration
description: "Patterns for routing requests across multiple AI providers (free + paid + local) with multi-key rotation, automatic failover on rate-limits, task-based routing, group orchestration (parallel/pipeline/synthesis), and user-extensible custom providers. ALWAYS use when building an app that chains multiple LLM providers, needs failover when tokens run out, rotates multiple API keys, runs several models together, or the user says: оркестрація моделей, мульти-ключ, failover між провайдерами, кілька AI разом, ротація ключів, безперервна робота на безкоштовних лімітах, group orchestration, multiple models cooperate, провайдери ланцюгом. Also triggers for: AI gateway, provider router, key rotation, parallel models, synthesis of model outputs, custom provider config. DO NOT use for single-provider simple API calls or when only one model is involved."
license: Proprietary
metadata:
  version: 1.5.0
  author: Melania (Master Administrator)
  category: provider-orchestration
  created: 2026-06-02
  last_updated: 2026-07-11
---

# Multi-Provider AI Orchestration — v1.5.0
> Напрацьовано на AI Gateway. Дозволяє безперервну роботу AI навіть на безкоштовних лімітах: ланцюг провайдерів + ротація багатьох ключів + перемикання при вичерпанні токенів + спільна робота моделей.
> Українською-перша: пояснення й приклади — українською за замовчуванням; код та технічні ідентифікатори лишаються англійською. Перемикання мови лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Core Rule
Кожен провайдер і кожен його ключ — окремий вузол у ланцюгу. При помилці (особливо rate-limit 429/quota) переходь до наступного вузла автоматично. Це дає безперервність і безкоштовне використання через ротацію.

---

## Pattern 1 — Provider Chain з мульти-ключем

Поле ключа може містити кілька ключів (через кому/новий рядок). Кожен розгортається в окремий вузол:

```javascript
function parseKeys(raw){
  if(!raw)return[];
  return String(raw).split(/[\n,]+/).map(k=>k.trim()).filter(Boolean);
}
function buildChain(keys, overrides, localModels, customProvs){
  const nodes=[];
  const all=[...Object.values(PDEFS),...(customProvs||[]).map(buildCustomProvider)];
  all.forEach(d=>{
    if(d.browser){ /* WebLLM: треба обрану модель + WebGPU */ ... return; }
    if(d.local){ /* потрібен URL + знайдені моделі */ ... return; }
    const klist=parseKeys(keys[d.kn]||"");
    klist.forEach((key,i)=>nodes.push({pid:d.id,d,key,model:overrides[d.id]||d.dm,keyIdx:i,keyTotal:klist.length}));
  });
  return nodes.sort((a,b)=>a.d.tier-b.d.tier); // tier: менше = вищий пріоритет
}
```

## Pattern 2 — Failover з rate-limit детекцією

```javascript
for(let i=0;i<chain.length;i++){
  const entry=chain[i];
  try{
    return await entry.d.stream(entry.key, entry.model, msgs, sys, mt);
  }catch(e){
    const msg=(e.message||"").toLowerCase();
    const isRateLimit=msg.includes("429")||msg.includes("rate")||msg.includes("quota")||msg.includes("limit");
    const nextSameProvider=chain[i+1]?.pid===entry.pid;
    // isRateLimit + nextSameProvider → ротація на наступний ключ того ж провайдера
    // інакше → наступний провайдер. Просто continue.
    if(!failoverEnabled)break;
  }
}
```

## Pattern 3 — Task-based routing

```javascript
const TASK_PREF={ coding:["groq","anthropic",...], general:[...] };
function pickProv(task, chain, auto){
  if(!auto||!chain.length)return chain[0];
  for(const pid of (TASK_PREF[task]||TASK_PREF.general)){
    const f=chain.find(c=>c.pid===pid); if(f)return f;
  }
  return chain[0];
}
```

## Pattern 4 — Group Orchestration (кілька моделей разом)

Три режими співпраці:

```javascript
const GroupOrchestrator={
  // ПАРАЛЕЛЬНО: усі відповідають одночасно (порівняння)
  async parallel(nodes, msg, history, onEach){
    return (await Promise.allSettled(nodes.map(async n=>{
      const text=await n.d.call(n.key,n.model,history.concat({role:"user",content:msg}),roleSys,900);
      onEach?.({node:n,text}); return {node:n,text,ok:true};
    }))).map((r,i)=>r.status==="fulfilled"?r.value:{node:nodes[i],err:r.reason?.message,ok:false});
  },
  // КОНВЕЄР: вузол[i] з роллю[i], вихід→вхід наступного
  async pipeline(steps, msg, history, onStep){ /* послідовно, ctx=prev output */ },
  // СИНТЕЗ: паралельні відповіді → один синтезатор об'єднує
  async synthesize(nodes, synthNode, msg, history){
    const parts=await this.parallel(nodes,msg,history);
    const combined=parts.filter(p=>p.ok).map((p,i)=>`[${i+1} ${p.node.d.short}]:\n${p.text}`).join("\n---\n");
    return this.callOne(synthNode, SYNTH_SYS, `Запит: ${msg}\n\nВідповіді:\n${combined}\n\nОб'єднай:`, history, 1400);
  },
};
```

Ролі: researcher 🔍, analyst 📊, critic 🛡, creative 💡, synthesizer ⚗️, coder 💻. Кожна — свій system prompt.

## Pattern 5 — User-Extensible Providers (як "знання" в GPT)

Користувач описує провайдер JSON-конфігом, система робить робочий провайдер БЕЗ eval():

```javascript
function getByPath(obj,path){ // "choices.0.message.content"
  return path.split(".").reduce((o,k)=>o==null?undefined:o[/^\d+$/.test(k)?+k:k], obj);
}
function buildCustomProvider(cfg){
  // format:"openai" (default) | "raw"; авто call+stream; auth header опційний
  // обов'язкові: name, endpoint(https). responsePath дефолт "choices.0.message.content"
}
function validateCustomCfg(raw){ /* JSON parse + name + endpoint http(s) перевірка */ }
```

---

---

## Provider Matrix (модельно-агностична)

> **Конкретні моделі/ціни/ctx НЕ живуть тут** — вони в датованому замінному файлі
> `references/model-snapshot-YYYY-MM.md` (поточний: `model-snapshot-2026-07.md`). Снапшот застарів →
> заміни файл, SKILL.md не чіпай. Це гарантує роботу скіла з будь-якими майбутніми/невідомими моделями.

Структура рядка матриці: **провайдер/модель · ціна I/O $/1M · ctx · сильні сторони · reasoning-тип**.
Класи вузлів у ланцюгу (стабільні, незалежні від конкретних моделей):
frontier-reasoning · балансний флагман-tier · дешевий флагман-tier · frontier-adjacent дешевий ·
open-weight сильний · high-volume воркер · локальний (privacy/offline).

**Tier order (default):** frontier(0) → балансні(1) → open-weight сильні(2) → дешеві воркери(3) → custom(5) → local(9-12)

### Anthropic-сумісні endpoints (3-рядкова інтеграція)
Низка провайдерів приймає **Anthropic-формат** запитів — існуючий Anthropic-клієнт працює зі зміною `base_url` + ключа:
```javascript
const client = new Anthropic({ baseURL: PROVIDER_ANTHROPIC_URL, apiKey: KEY });
```
Це робить сумісні воркери drop-in замінюваними у ланцюгу без адаптера. Хто саме сумісний + URL —
у `references/model-snapshot-YYYY-MM.md` (звір docs провайдера).

---

## Reasoning / Thinking Cross-Provider (агностично)

Провайдери експонують reasoning різними полями (adaptive / effort-рівні / thinking-budget). Конкретні
поля по провайдерах — у `references/model-snapshot-YYYY-MM.md` (звіряй docs: поля мігрують).
Механізм автовибору стабільний:

```javascript
// reasoning-capability — атрибут вузла зі снапшоту, не хардкод назв провайдерів
function selectThinkingProvider(chain) {
  return chain.find(n => n.caps?.reasoning) ?? chain[0];
}
```

## Cost Estimation

```javascript
// COSTS заповнюється з датованого снапшоту references/model-snapshot-YYYY-MM.md —
// НЕ хардкодь тут: конкретні моделі/ціни змінюються, механізм — ні.
const COSTS = loadFromSnapshot(); // { "model-id": { in: $/1M, out: $/1M }, ... }
function estimateCost(model, inTokens, outTokens) {
  const c = COSTS[model]; if(!c) return null;
  return (inTokens/1e6)*c.in + (outTokens/1e6)*c.out;
}
```

---

## Behavior

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| Токени провайдера вичерпані | автоматичний failover на наступний вузол | зупинятись з помилкою |
| Користувач дав кілька ключів | розгорнути кожен в окремий вузол, ротувати | використати тільки перший |
| Rate-limit (429) | розпізнати, ротувати ключ/провайдер | трактувати як фатальну помилку |
| Кілька моделей разом | parallel/pipeline/synthesis за вибором | завжди одна модель |
| Custom провайдер від юзера | JSON-конфіг → buildCustomProvider | eval() довільного коду |
| Локальні + хмарні разом | усі у спільному ланцюгу за tier | розділяти штучно |

---

## Tier convention (порядок у ланцюгу)
Платні якісні (0) → безкоштовні швидкі (1-3) → custom (5) → браузерний WebLLM (9) → локальні Ollama/LMStudio (10-12). Менший tier = вищий пріоритет, але task-routing може перевизначити.

## Coordinates with
- `browser-local-ai-webllm` — браузерний AI як вузол ланцюга (tier 9)
- `surgical-code-refactoring` — інтеграція цих патернів у існуючий код
- `validation-mesh` — перевірка коректності ланцюга перед deploy
- `rlm-harness` — per-role model-fit ПОЛІТИКА (профіль кроку → клас моделі) живе там; цей скіл — рантайм-матриця/ціни/ротація/failover (джерело істини рантайму).

---

## Конектори дій vs LLM-провайдери (failover-принцип)
Цей скіл маршрутизує **LLM-провайдерів**. Конектори **дій** — не LLM-провайдери, тож їх оркеструє інший шар.
Але failover-принцип **переноситься**: якщо конектор-дія падає (rate-limit/auth) —
**не роби тихий деструктивний ретрай**; поверни помилку, дай альтернативу/паузу.

## 📎 Advanced Patterns (v4)

Read `references/advanced-orchestration.md` WHEN you need: streaming aggregation, semantic caching, deduplication, latency routing, health monitoring.
Load only on demand — not proactively.

---

## Зміни
- **v1.5.0** (2026-07-11) — Frontier-research harvest + принцип модельної агностичності: **(A)** НОВИЙ замінний файл `references/model-snapshot-2026-07.md` — ЄДИНЕ місце конкретики (матриця 15 моделей із верифікованими цінами, COSTS-конфіг з фіксом Opus 4.8 15/75→5/25, reasoning-поля по провайдерах, Anthropic-сумісні endpoints, per-role приклади для rlm-harness). **(B)** SKILL.md де-пінований: матриця→структура+класи вузлів, COSTS→loadFromSnapshot(), reasoning→capability-атрибут вузла, endpoints→патерн без URL. Скіл працює з будь-якими майбутніми моделями; застарівання = заміна снапшот-файлу. **(C)** Фікс розсинхрону заголовка (v1.0→актуальна). Знання старої матриці збережені в CHANGELOG-історії; merge-not-replace. _(Джерело: дослідницький звіт 2026-07-11 + правило агностичності MA.)_
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (артефакт злиттів). Усі записи збережено; нумерацію НЕ переписано без верифікації джерел._
- **v1.4.2** (2026-06-26) — Stage 3: **S-1** застарілу модель оновлено (`claude-opus-4-5`→`claude-opus-4-8`, ×2; ціни звіряти в docs). **S-2** примітка про дубль v1.2.0 (вміст збережено). Корекція + примітка.
- **v1.4.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.2.0** (2026-06-02) — додано `metadata`/`license`-frontmatter + явну директиву «українською-перша»; додано в Routing Map семантичного роутера. _(аудит Кластер 4: metadata + P9 + P-23)_

- **v1.1.0** (2026-06-02) — provider matrix 2026, extended thinking cross-provider, cost estimation, DeepSeek/Gemini 2.5 patterns.

- **v1.2.0** (2026-06-02) — Pre-Update Preservation Protocol; advanced-orchestration reference (streaming aggregation, caching, health monitoring).
- **v1.3.0** (2026-06-10) — Фаза 5: I-9: failover-принцип переноситься на конектори дій (без тихого деструктивного ретраю; оркестрація — в іншому шарі).

- **v1.4.0** (2026-06-14) — P-01: межовий покажчик — per-role model-fit ПОЛІТИКА у rlm-harness; цей скіл = рантайм-матриця/ціни/failover. _(SKILL-AUDIT-LEDGER, harvest RLM Harness.)_
