---
name: browser-local-ai-webllm
description: "Run local LLMs directly in the browser via WebLLM (WebGPU) with NO middleware app — no Ollama, no PocketPal, no PC. Covers lazy-loading the ESM lib, WebGPU/HTTPS requirements, device analysis (RAM/VRAM), model-fit ranking, the Chrome 8GB deviceMemory cap, and OpenAI-compatible call/stream. ALWAYS use when adding in-browser local AI, running models client-side without a server, or the user says: локальний AI у браузері, WebLLM, без посередників, модель прямо в застосунку, WebGPU AI, браузерний AI, офлайн модель у браузері, run model in browser, on-device browser inference. Also triggers for: device analysis for model fit, VRAM detection, prebuiltAppConfig, MLCEngine. DO NOT use for server-side inference, native mobile inference, or when Ollama/LM Studio is the intended runtime (those are external providers)."
license: Proprietary
metadata:
  version: 1.2.3
  author: Melania (Master Administrator)
  category: browser-ai
  created: 2026-06-02
  last_updated: 2026-06-02
---

# Browser-Local AI via WebLLM — v1.0
> Напрацьовано на AI Gateway. Реальне рішення локального AI БЕЗ посередників: модель працює прямо в браузері/застосунку через WebGPU. Підтверджено тестуванням @mlc-ai/web-llm v0.2.84 (163 моделі, OpenAI-сумісний API).
> Українською-перша: пояснення й приклади — українською за замовчуванням; код та технічні ідентифікатори лишаються англійською. Перемикання мови лише слідом за користувачем.
>
> **Неофіційний.** Не пов'язаний з, не схвалений відкритим проєктом WebLLM / MLC AI. «WebLLM» — назва відкритого проєкту (MLC AI, Apache-2.0); вжита суто референційно (опис сумісності).


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Core Rule
WebLLM працює ТІЛЬКИ в secure context (HTTPS або localhost) бо потребує WebGPU. На `content://`/`file://` НЕ запуститься — це обмеження браузера, не коду. Завжди перевіряй `navigator.gpu && window.isSecureContext` перед спробою.

---

## Critical Facts (підтверджено, не припущення)
- **PocketPal НЕ має локального API-сервера** (open feature request) — не може бути middleware. WebLLM — реальна альтернатива.
- **window.ai / Gemini Nano НЕ працює на Android** (desktop/ChromeOS only).
- **Chrome навмисне обмежує `navigator.deviceMemory` до МАКС 8GB** (приватність). Це НЕ баг. Дай користувачу ручне коригування. У нативному APK буде справжнє значення.
- Список моделей фіксований версією WebLLM (тільки MLC-конвертовані). Довільну модель додати НЕ можна — для широкого вибору потрібні зовнішні Ollama/LM Studio або нативний застосунок.

---

## Pattern 1 — Engine wrapper (ізольований для майбутньої заміни)

```javascript
const WebLLMEngine={
  _engine:null,_loadedModel:null,_lib:null,
  CDN:"https://esm.run/@mlc-ai/web-llm@0.2.84",
  isSupported(){return !!navigator.gpu && window.isSecureContext===true;},
  async _loadLib(){ // динамічний import щоб Babel не чіпав
    if(this._lib)return this._lib;
    const imp=new Function("u","return import(u)");
    return this._lib=await imp(this.CDN);
  },
  async getModels(){ const lib=await this._loadLib();
    return (lib.prebuiltAppConfig?.model_list||[]).map(m=>({id:m.model_id,vram:m.vram_required_MB,lowRes:!!m.low_resource_required}));
  },
  async load(modelId,onProgress){ const lib=await this._loadLib();
    const cb=p=>onProgress?.(p.progress||0,p.text||"");
    if(this._engine) await this._engine.reload(modelId);
    else this._engine=await lib.CreateMLCEngine(modelId,{initProgressCallback:cb});
    this._loadedModel=modelId; return this._engine;
  },
  async isCached(id){ try{const lib=await this._loadLib();return await lib.hasModelInCache(id);}catch{return false;} },
  async chat(modelId,msgs,sys,mt){ const e=await this.load(modelId);
    const r=await e.chat.completions.create({messages:sys?[{role:"system",content:sys},...msgs]:msgs,max_tokens:mt,stream:false});
    return {text:r.choices[0].message.content,tok:r.usage?.completion_tokens||0};
  },
  async *chatStream(modelId,msgs,sys,mt){ const e=await this.load(modelId);
    const ch=await e.chat.completions.create({messages:sys?[{role:"system",content:sys},...msgs]:msgs,max_tokens:mt,stream:true});
    for await(const c of ch){const t=c.choices?.[0]?.delta?.content;if(t)yield t;}
  },
};
```
> API `engine.chat.completions.create` ІДЕНТИЧНИЙ OpenAI — інтеграція в існуючий провайдер-ланцюг тривіальна.

## Pattern 2 — Device Analysis (за замовчуванням, для підбору моделі)

```javascript
const DeviceAnalyzer={
  _cache:null,
  async analyze(){
    if(this._cache)return this._cache;
    const info={deviceMemoryGB:navigator.deviceMemory||null,cores:navigator.hardwareConcurrency||null,webgpu:false,estVramMB:null};
    if(navigator.gpu){ try{ const a=await navigator.gpu.requestAdapter();
      if(a){info.webgpu=true; info.maxStorageMB=a.limits?.maxStorageBufferBindingSize?Math.round(a.limits.maxStorageBufferBindingSize/1048576):null;}
    }catch{} }
    info.ramCapped=info.deviceMemoryGB===8; // Chrome cap signal
    const manual=localStorage.getItem("manualRamGB");
    if(manual){info.deviceMemoryGB=+manual;info.manual=true;info.estVramMB=Math.round(+manual*1024*0.45);}
    else if(info.deviceMemoryGB) info.estVramMB=Math.round(info.deviceMemoryGB*1024*0.45);
    else info.estVramMB=info.webgpu?2048:0;
    return this._cache=info;
  },
  clearCache(){this._cache=null;},
  fits(vramMB,estVramMB){return (vramMB&&estVramMB)?vramMB<=estVramMB*0.95:null;},
};
```
> estVRAM ≈ 45% RAM (консервативно для мобільних). Завжди дай кнопки ручного коригування RAM (4/6/8/12/16/24GB) бо браузер бреше про 8GB.

## Pattern 3 — Model ranking (найновіші + придатні вгорі)

```javascript
const MODEL_FAMILY_RANK={"Qwen3.5":100,"Qwen3":95,"Llama-3.2":90,"Phi-4":88,"gemma3":86,"Qwen2.5":82,...};
function rankModels(models, estVramMB){
  return models.map(m=>({...m, fam:familyOf(m.id), fits:DeviceAnalyzer.fits(m.vram,estVramMB), sizeB:parseFloat((m.id.match(/(\d+(?:\.\d+)?)B/)||[])[1]||999)}))
    .filter(m=>m.fam!=="other" && /q4f16/.test(m.id)) // q4f16 = оптимальний баланс
    .sort((a,b)=> (a.fits!==b.fits ? (b.fits?1:0)-(a.fits?1:0) : b.famRank-a.famRank || b.sizeB-a.sizeB));
}
```

---

## Behavior

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| WebGPU/HTTPS відсутній | сховати браузерний AI, чітко пояснити «потрібен HTTPS» | мовчки дати обрати і не завантажити |
| RAM показує рівно 8GB | позначити ramCapped, дати ручне коригування | вірити що це справжній максимум |
| Користувач хоче будь-яку модель | пояснити: браузер обмежений MLC-форматом; для широкого вибору → Ollama/нативний | обіцяти довільні моделі в браузері |
| Завантаження моделі | показати прогрес (initProgressCallback) + кеш-статус | мовчазне очікування ~6GB |
| Перша спроба моделі | перевірити isCached → попередити про розмір | качати без попередження |
| Інтеграція в ланцюг | tier 9, OpenAI-сумісний call/stream | окремий несумісний інтерфейс |

---

## Verify before integrating (завжди)
```bash
npm install @mlc-ai/web-llm@0.2.84
node -e "const w=require('@mlc-ai/web-llm');console.log('models:',w.prebuiltAppConfig.model_list.length);const e=new w.MLCEngine();console.log('OpenAI-compat:',typeof e.chat.completions.create);"
```

## Coordinates with
- `multi-provider-ai-orchestration` — WebLLM як вузол ланцюга (tier 9)
- `pwa-to-android-app` — WebGPU запрацює після HTTPS-розгортання
- `surgical-code-refactoring` — інтеграція движка в існуючий код

---

---

## Рекомендовані Моделі 2026

| Модель | VRAM | Швидкість | Якість | Use case |
|---|---|---|---|---|
| `Llama-3.2-1B-Instruct-q4f16_1-MLC` | ~1GB | ⚡⚡⚡ | добра | тригери, класифікація |
| `Llama-3.2-3B-Instruct-q4f16_1-MLC` | ~2GB | ⚡⚡ | краща | чат, короткі відповіді |
| `Phi-3.5-mini-instruct-q4f16_1-MLC` | ~2.5GB | ⚡⚡ | відмінна | розуміння коду |
| `Qwen2.5-7B-Instruct-q4f16_1-MLC` | ~5GB | ⚡ | дуже добра | загальне завдання |
| `Llama-3.1-8B-Instruct-q4f32_1-MLC` | ~6GB | ⚡ | відмінна | best for quality |
| `Llama-3.3-70B` | ~40GB | — | найкраща | лише в серверних браузерах |

**Авто-вибір по deviceMemory:**
```javascript
const mem = navigator.deviceMemory || 4; // GB RAM
const model = mem >= 8  ? "Llama-3.1-8B-Instruct-q4f32_1-MLC"
            : mem >= 4  ? "Qwen2.5-7B-Instruct-q4f16_1-MLC"
            : mem >= 2  ? "Phi-3.5-mini-instruct-q4f16_1-MLC"
            :             "Llama-3.2-1B-Instruct-q4f16_1-MLC";
```

---

## Streaming з Progress

```javascript
const engine = new mlc.MLCEngine();

// Прогрес завантаження
await engine.reload(model, {
  initProgressCallback: (p) => {
    updateUI(`⬇ ${(p.progress*100).toFixed(0)}% — ${p.text}`);
  }
});

// Streaming відповідь
const chunks = await engine.chat.completions.create({
  messages: conversation,
  stream: true,
  temperature: 0.7,
  max_tokens: 512
});
let reply = "";
for await (const chunk of chunks) {
  const delta = chunk.choices[0]?.delta?.content || "";
  reply += delta;
  appendToChat(delta);        // live update UI
}
```

---

## Service Worker — Кешування Ваг

```javascript
// sw.js — кеш model weights між сесіями
self.addEventListener('fetch', event => {
  if (event.request.url.includes('mlc-ai/web-llm')) {
    event.respondWith(
      caches.open('webllm-v1').then(cache =>
        cache.match(event.request).then(cached =>
          cached || fetch(event.request).then(res => {
            cache.put(event.request, res.clone());
            return res;
          })
        )
      )
    );
  }
});
```
Після першого завантаження моделі — наступні запуски offline ✓

---

## 📎 Advanced Patterns (v4)

Read `references/advanced-webllm.md` WHEN you need: function calling, browser embeddings (RAG offline), multi-model, structured generation.
Load only on demand — not proactively.

---

## Зміни
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (артефакт злиттів). Усі записи збережено; нумерацію НЕ переписано без верифікації джерел._
- **v1.2.3** (2026-06-26) — Stage 3 S-2: примітка про дубль v1.2.0 у changelog (вміст збережено, нумерацію не переписано). Лише додавання примітки.
- **v1.2.2** (2026-06-15) — B2 (safety-compliance-gate): дисклеймер неприналежності — WebLLM (MLC AI).
- **v1.2.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.2.0** (2026-06-02) — додано `metadata`/`license`-frontmatter + явну директиву «українською-перша»; додано в Routing Map семантичного роутера. _(аудит Кластер 4: metadata + P9 + P-23)_

- **v1.1.0** (2026-06-02) — model matrix 2026, auto-select by deviceMemory, streaming+progress, SW caching.

- **v1.2.0** (2026-06-02) — Pre-Update Preservation Protocol; advanced-webllm reference (function calling, embeddings, multi-model).
