# Advanced WebLLM

## Function Calling у браузері

```javascript
const engine = new mlc.MLCEngine();
await engine.reload("Llama-3.1-8B-Instruct-q4f32_1-MLC");

const tools = [{
  type: "function",
  function: {
    name: "get_weather",
    description: "Get weather for a city",
    parameters: {
      type: "object",
      properties: { city: { type: "string" } },
      required: ["city"]
    }
  }
}];

const reply = await engine.chat.completions.create({
  messages: [{ role: "user", content: "Погода в Києві?" }],
  tools,
  tool_choice: "auto"
});
const toolCall = reply.choices[0].message.tool_calls?.[0];
if (toolCall) {
  const args = JSON.parse(toolCall.function.arguments);
  const result = await getWeather(args.city);  // виконай локально
  // передай результат назад моделі...
}
```

Підтримка function calling залежить від моделі (Llama 3.1+, Qwen2.5 — так).

---

## Embeddings у браузері (для RAG offline)

```javascript
// Окремий embedding-движок
const embEngine = new mlc.MLCEngine();
await embEngine.reload("snowflake-arctic-embed-m-q0f32-MLC-b4");

const embeddings = await embEngine.embeddings.create({
  input: ["текст 1", "текст 2", "текст 3"]
});
// embeddings.data[i].embedding → вектор для семантичного пошуку

// Cosine similarity для пошуку:
function cosineSim(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { dot += a[i]*b[i]; na += a[i]**2; nb += b[i]**2; }
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}
```

Повний RAG offline: embeddings + cosine search + local LLM — без жодного сервера.

---

## Multi-Model Loading

```javascript
// Тримай кілька моделей — перемикайся за задачею
const engines = {};
async function getEngine(modelId) {
  if (!engines[modelId]) {
    engines[modelId] = new mlc.MLCEngine();
    await engines[modelId].reload(modelId);
  }
  return engines[modelId];
}
// Маленька модель для класифікації, велика для генерації
const classifier = await getEngine("Llama-3.2-1B-Instruct-q4f16_1-MLC");
const generator  = await getEngine("Llama-3.1-8B-Instruct-q4f32_1-MLC");
```

⚠️ Увага на VRAM — дві великі моделі можуть не поміститись. Вивантажуй: `engine.unload()`.

---

## Structured Generation (JSON schema)

```javascript
const reply = await engine.chat.completions.create({
  messages: [{ role: "user", content: "Витягни ім'я та вік: Іван, 30 років" }],
  response_format: {
    type: "json_object",
    schema: JSON.stringify({
      type: "object",
      properties: { name: {type:"string"}, age: {type:"integer"} },
      required: ["name", "age"]
    })
  }
});
const data = JSON.parse(reply.choices[0].message.content);  // гарантований JSON
```

---

## WebGPU Feature Detection (повна перевірка)

```javascript
async function checkWebGPU() {
  if (!navigator.gpu) return { ok: false, reason: "WebGPU not supported" };
  if (!window.isSecureContext) return { ok: false, reason: "Need HTTPS/localhost" };
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) return { ok: false, reason: "No GPU adapter" };
  const device = await adapter.requestDevice();
  const limits = device.limits;
  return {
    ok: true,
    maxBufferSize: limits.maxBufferSize,
    maxStorageBufferBinding: limits.maxStorageBufferBindingSize,
    canRunLargeModels: limits.maxBufferSize > 2e9  // >2GB
  };
}
```

---

## Memory Pressure Handling

```javascript
// Слідкуй за пам'яттю, вивантажуй якщо критично
if (performance.memory) {
  const used = performance.memory.usedJSHeapSize;
  const limit = performance.memory.jsHeapSizeLimit;
  if (used / limit > 0.9) {
    await engine.unload();  // звільни модель
    showWarning("Недостатньо пам'яті — модель вивантажено");
  }
}
```
