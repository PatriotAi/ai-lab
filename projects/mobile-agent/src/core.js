// core.js — чиста логіка «Кишенькового агента» (Pocket Agent).
// Єдина відповідальність: детермінована логіка без DOM, без мережі, без глобального стану.
// Джерело істини: цей файл. UI-шаблон (app.html) + build.mjs вбудовують його в один
// самодостатній HTML для телефону. Тести: tests/mobile-agent-tests.mjs.
//
// Правило: усе, що можна перевірити без браузера, живе ТУТ.
// Усе, що потребує DOM/мережі/WebGPU — в app.html і перевіряється браузерним прогоном.

export const APP_VERSION = "0.1.0";

// Ідентифікатор моделі — це КОНФІГ застосунку, а не правило лабораторії
// (закон не-старіння: назви моделей не живуть у правилах). Змінюється в налаштуваннях.
export const DEFAULT_CLOUD_MODEL = "claude-sonnet-5";
export const NOTES_KEY = "pocket-agent.notes.v1";
export const SECRET_KEY = "pocket-agent.secret.v1";

// ── Версії / авто-оновлення ────────────────────────────────────────────────
/** Чи candidate новіший за current (X.Y.Z; нечислові хвости ігноруються). */
export function isNewerVersion(candidate, current) {
  const part = (v) => String(v ?? "").split(".").map((n) => parseInt(n, 10) || 0);
  const a = part(candidate);
  const b = part(current);
  for (let i = 0; i < 3; i++) {
    if ((a[i] || 0) > (b[i] || 0)) return true;
    if ((a[i] || 0) < (b[i] || 0)) return false;
  }
  return false;
}

// ── Вибір двигуна ──────────────────────────────────────────────────────────
// Три рівні деградації. Найнижчий (offline) працює ЗАВЖДИ — без мережі,
// без ключа, без WebGPU. Це і є гарантія «агент працює прямо зі смартфона».
/**
 * @param {{online?:boolean, hasCloudKey?:boolean, webgpu?:boolean,
 *          secureContext?:boolean, localReady?:boolean, prefer?:"auto"|"cloud"|"local"|"offline"}} ctx
 * @returns {{engine:"cloud"|"local"|"offline", reason:string, fallback:boolean}}
 */
export function pickEngine(ctx = {}) {
  const online = ctx.online !== false;
  const cloudOk = online && !!ctx.hasCloudKey;
  const localOk = !!ctx.webgpu && ctx.secureContext === true;
  const prefer = ctx.prefer || "auto";

  if (prefer === "offline") return { engine: "offline", reason: "обрано вручну", fallback: false };
  if (prefer === "cloud") {
    if (cloudOk) return { engine: "cloud", reason: "обрано вручну", fallback: false };
    const why = !online ? "нема мережі" : "нема ключа";
    return localOk
      ? { engine: "local", reason: `хмара недоступна (${why})`, fallback: true }
      : { engine: "offline", reason: `хмара недоступна (${why})`, fallback: true };
  }
  if (prefer === "local") {
    if (localOk) return { engine: "local", reason: "обрано вручну", fallback: false };
    const why = !ctx.webgpu ? "нема WebGPU" : "не secure context (потрібен HTTPS)";
    return cloudOk
      ? { engine: "cloud", reason: `локальна недоступна (${why})`, fallback: true }
      : { engine: "offline", reason: `локальна недоступна (${why})`, fallback: true };
  }
  if (cloudOk) return { engine: "cloud", reason: "є мережа і ключ", fallback: false };
  if (localOk) return { engine: "local", reason: "нема хмари, є WebGPU", fallback: true };
  return {
    engine: "offline",
    reason: !online ? "нема мережі й WebGPU" : "нема ключа й WebGPU",
    fallback: true,
  };
}

// ── Розбір вводу ───────────────────────────────────────────────────────────
const SEARCH_PREFIXES = ["/пошук ", "/search ", "пошук:", "знайди ", "find "];
const TASK_PREFIXES = ["+", "/задача ", "/task ", "задача:", "task:", "todo:"];

/**
 * Тип наміру за текстом. Порядок важливий: пошук → задача → запитання.
 * @returns {{kind:"search"|"task"|"ask", payload:string}}
 */
export function parseCommand(raw) {
  const text = String(raw ?? "").trim();
  if (!text) return { kind: "ask", payload: "" };
  const low = text.toLowerCase();
  for (const p of SEARCH_PREFIXES) {
    if (low.startsWith(p)) return { kind: "search", payload: text.slice(p.length).trim() };
  }
  for (const p of TASK_PREFIXES) {
    if (low.startsWith(p)) return { kind: "task", payload: text.slice(p.length).trim() };
  }
  return { kind: "ask", payload: text };
}

/** Унікальні теги виду #слово (UA/EN), у нижньому регістрі, у порядку появи. */
export function extractTags(text) {
  const found = String(text ?? "").match(/#[\p{L}\p{N}_-]+/gu) || [];
  const seen = [];
  for (const t of found) {
    const tag = t.slice(1).toLowerCase();
    if (tag && !seen.includes(tag)) seen.push(tag);
  }
  return seen;
}

// ── Офлайн-двигун (без моделі) ─────────────────────────────────────────────
const STOPWORDS = new Set([
  "цього", "того", "щоби", "щоб", "який", "яка", "яке", "які", "тому", "було", "буде",
  "може", "потрібно", "треба", "після", "перед", "через", "разом", "дуже", "лише",
  "about", "there", "their", "would", "could", "should", "these", "those", "which",
  "because", "after", "before", "while", "with", "from", "that", "this", "have", "will",
]);

/** Слова довші за 4 літери, без стоп-слів, за спаданням частоти, потім за появою. */
export function keywords(text, limit = 5) {
  const words = String(text ?? "").toLowerCase().match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu) || [];
  const freq = new Map();
  const order = [];
  for (const w of words) {
    if (w.length <= 4 || STOPWORDS.has(w)) continue;
    if (!freq.has(w)) order.push(w);
    freq.set(w, (freq.get(w) || 0) + 1);
  }
  return order
    .sort((a, b) => freq.get(b) - freq.get(a) || order.indexOf(a) - order.indexOf(b))
    .slice(0, limit);
}

/** Перше речення, обрізане до max символів (по межі слова). */
export function firstSentence(text, max = 120) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  const m = clean.match(/^[^.!?…]+[.!?…]?/);
  let s = (m ? m[0] : clean).trim();
  if (s.length > max) s = s.slice(0, max).replace(/\s+\S*$/, "") + "…";
  return s;
}

/**
 * Детермінована відповідь без моделі: структурує ввід (суть + ключові слова + теги).
 * Не імітує «розумну» відповідь — чесно каже, що це офлайн-структурування.
 */
export function offlineAnswer(text, kind = "ask") {
  const body = String(text ?? "").trim();
  if (!body) return "Порожній запит — нема що структурувати.";
  const kw = keywords(body);
  const tags = extractTags(body);
  const head = kind === "task" ? "Задача" : "Суть";
  const lines = [`${head}: ${firstSentence(body)}`];
  if (kw.length) lines.push(`Ключові слова: ${kw.join(", ")}`);
  if (tags.length) lines.push(`Теги: ${tags.map((t) => "#" + t).join(" ")}`);
  lines.push("⚡ Офлайн-режим: структурування без моделі (нема мережі/ключа/WebGPU).");
  return lines.join("\n");
}

// ── Нотатки ────────────────────────────────────────────────────────────────
/** Нотатка з детермінованих полів. id передається ззовні (щоб тест був відтворюваний). */
export function makeNote({ input, answer, engine, kind = "ask", now = Date.now(), id }) {
  const text = String(input ?? "").trim();
  return {
    id: id || `n${now}-${Math.abs(hashString(text + now)).toString(36)}`,
    ts: now,
    kind,
    engine,
    input: text,
    answer: String(answer ?? ""),
    tags: extractTags(text),
    done: false,
  };
}

/** Стабільний 32-бітний хеш (для id та перевірок цілісності). */
export function hashString(str) {
  let h = 2166136261;
  const s = String(str ?? "");
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h | 0;
}

/**
 * Пошук: збіг за тегом важить більше за збіг у вводі, ввід — більше за відповідь.
 * Порожній запит повертає всі нотатки в порядку новизни.
 */
export function searchNotes(notes, query) {
  const list = Array.isArray(notes) ? notes : [];
  const q = String(query ?? "").trim().toLowerCase();
  if (!q) return [...list].sort((a, b) => b.ts - a.ts);
  const terms = q.split(/\s+/).filter(Boolean);
  const scored = [];
  for (const n of list) {
    let score = 0;
    const input = String(n.input ?? "").toLowerCase();
    const answer = String(n.answer ?? "").toLowerCase();
    const tags = (n.tags || []).map((t) => String(t).toLowerCase());
    for (const t of terms) {
      const bare = t.replace(/^#/, "");
      if (tags.includes(bare)) score += 5;
      if (input.includes(t)) score += 3;
      if (answer.includes(t)) score += 1;
    }
    if (score > 0) scored.push({ n, score });
  }
  return scored.sort((a, b) => b.score - a.score || b.n.ts - a.n.ts).map((x) => x.n);
}

// ── Локальна модель: придатність пристрою ──────────────────────────────────
// Chrome навмисне обмежує navigator.deviceMemory максимумом 8 ГБ (приватність),
// тому оцінка консервативна, а ручне коригування — обов'язкове.
/** Оцінка доступної VRAM у МБ (≈45% RAM — консервативно для мобільних). */
export function estimateVramMB(deviceMemoryGB, webgpu) {
  if (deviceMemoryGB) return Math.round(Number(deviceMemoryGB) * 1024 * 0.45);
  return webgpu ? 2048 : 0;
}

/** Чи влазить модель у пам'ять (з запасом 5%). null — невідомо. */
export function modelFits(vramRequiredMB, estVramMB) {
  if (!vramRequiredMB || !estVramMB) return null;
  return vramRequiredMB <= estVramMB * 0.95;
}

/**
 * Впорядкування моделей WebLLM: спершу ті, що влазять, далі — менші за розміром.
 * Беремо лише q4f16 (оптимальний баланс якість/пам'ять).
 */
export function rankLocalModels(models, estVramMB) {
  const sizeOf = (id) => parseFloat((String(id).match(/(\d+(?:\.\d+)?)B/i) || [])[1] || "999");
  return (models || [])
    .filter((m) => /q4f16/i.test(String(m.id)))
    .map((m) => ({ ...m, fits: modelFits(m.vram, estVramMB), size: sizeOf(m.id) }))
    .sort((a, b) => {
      const af = a.fits === true ? 1 : 0;
      const bf = b.fits === true ? 1 : 0;
      if (af !== bf) return bf - af;
      return a.size - b.size || String(a.id).localeCompare(String(b.id));
    });
}

// ── Хмарний запит (побудова, БЕЗ виконання) ────────────────────────────────
/**
 * Формує {url, headers, body} для хмарного провайдера. Ключ іде ЛИШЕ в заголовку,
 * ніколи в URL (URL потрапляє в логи/історію).
 * @param {{provider:"anthropic"|"openai", apiKey:string, model?:string,
 *          messages:Array<{role:string,content:string}>, system?:string, maxTokens?:number}} o
 */
export function buildCloudRequest(o = {}) {
  const provider = o.provider || "anthropic";
  const apiKey = String(o.apiKey ?? "");
  if (!apiKey) throw new Error("buildCloudRequest: порожній ключ");
  const model = o.model || DEFAULT_CLOUD_MODEL;
  const messages = (o.messages || []).map((m) => ({ role: m.role, content: m.content }));
  const maxTokens = o.maxTokens || 1024;

  if (provider === "anthropic") {
    return {
      url: "https://api.anthropic.com/v1/messages",
      headers: {
        "content-type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        // Без цього заголовка браузерний виклик Anthropic API блокується CORS.
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: { model, max_tokens: maxTokens, system: o.system || undefined, messages },
    };
  }
  // OpenAI-сумісний (у т.ч. локальні шлюзи й більшість провайдерів)
  return {
    url: (o.baseUrl || "https://api.openai.com/v1").replace(/\/$/, "") + "/chat/completions",
    headers: { "content-type": "application/json", authorization: `Bearer ${apiKey}` },
    body: {
      model,
      max_tokens: maxTokens,
      messages: o.system ? [{ role: "system", content: o.system }, ...messages] : messages,
    },
  };
}

/** Витяг тексту відповіді з формату будь-якого з двох провайдерів. */
export function readCloudReply(provider, data) {
  if (!data || typeof data !== "object") return "";
  if (provider === "anthropic") {
    const blocks = Array.isArray(data.content) ? data.content : [];
    return blocks.filter((b) => b && b.type === "text").map((b) => b.text).join("").trim();
  }
  return String(data?.choices?.[0]?.message?.content ?? "").trim();
}

// ── Секрети: AES-GCM + пароль-фраза (WebCrypto) ────────────────────────────
const KDF_ITERATIONS = 210000;

function b64encode(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}
function b64decode(str) {
  const bin = atob(String(str ?? ""));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function deriveKey(subtle, passphrase, salt) {
  const material = await subtle.importKey(
    "raw",
    new TextEncoder().encode(String(passphrase ?? "")),
    "PBKDF2",
    false,
    ["deriveKey"],
  );
  return subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: KDF_ITERATIONS, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

/** Шифрує секрет паролем-фразою. Повертає самоописний конверт (JSON-придатний). */
export async function encryptSecret(plaintext, passphrase, cryptoImpl) {
  const c = cryptoImpl || globalThis.crypto;
  if (!passphrase) throw new Error("encryptSecret: потрібна пароль-фраза");
  const salt = c.getRandomValues(new Uint8Array(16));
  const iv = c.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(c.subtle, passphrase, salt);
  const ct = await c.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    new TextEncoder().encode(String(plaintext ?? "")),
  );
  return {
    v: 1,
    kdf: "PBKDF2-SHA256",
    iterations: KDF_ITERATIONS,
    salt: b64encode(salt),
    iv: b64encode(iv),
    ct: b64encode(new Uint8Array(ct)),
  };
}

/** Розшифровує конверт. Хибна пароль-фраза → виняток (AES-GCM автентифікований). */
export async function decryptSecret(envelope, passphrase, cryptoImpl) {
  const c = cryptoImpl || globalThis.crypto;
  if (!envelope || envelope.v !== 1) throw new Error("decryptSecret: невідомий формат");
  const salt = b64decode(envelope.salt);
  const iv = b64decode(envelope.iv);
  const key = await deriveKey(c.subtle, passphrase, salt);
  const plain = await c.subtle.decrypt({ name: "AES-GCM", iv }, key, b64decode(envelope.ct));
  return new TextDecoder().decode(plain);
}

/** Маскує ключі у тексті перед показом/логуванням. */
export function redactSecrets(text) {
  return String(text ?? "")
    .replace(/\b(sk-[A-Za-z0-9_-]{8,})/g, "sk-***")
    .replace(/\b(xai-|gsk_|AIza)[A-Za-z0-9_-]{8,}/g, "$1***");
}
