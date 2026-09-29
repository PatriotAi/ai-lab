// core.js — чиста логіка «Кишенькового агента» (Pocket Agent).
// Єдина відповідальність: детермінована логіка без DOM, без мережі, без глобального стану.
// Джерело істини: цей файл. UI-шаблон (app.html) + build.mjs вбудовують його в один
// самодостатній HTML для телефону. Тести: tests/mobile-agent-tests.mjs.
//
// Правило: усе, що можна перевірити без браузера, живе ТУТ.
// Усе, що потребує DOM/мережі/WebGPU — в app.html і перевіряється браузерним прогоном.

export const APP_VERSION = "0.2.0";

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
    // «Тільки локальна» — це обіцянка про дані: запит не залишає пристрій. Тому
    // без локального двигуна ми НЕ йдемо в хмару, навіть якщо ключ відкритий
    // (рев'ю Codex до PR #74: чіп казав «локальна», а запит летів у хмару).
    const why = !ctx.webgpu ? "нема WebGPU" : "не secure context (потрібен HTTPS)";
    return { engine: "offline", reason: `локальна недоступна (${why}); хмару не використовую — обрано «тільки локальна»`, fallback: true };
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

// ── Резервний контур: черга, повтори, ланцюг провайдерів ──────────────────
// Навіщо: до цього падіння хмари НЕ затримувало роботу, а знищувало її —
// єдина спроба, catch → офлайн-заглушка замість справжньої відповіді, і жодного
// повтору. Контур міняє це: завдання не втрачається, а чекає й повторюється.
// Уся логіка тут — чиста й детермінована (час і випадковість передаються ззовні),
// тому перевіряється без браузера й без мережі.

export const QUEUE_KEY = "pocket-agent.queue.v1";
export const MAX_ATTEMPTS = 5;

/**
 * Класифікація збою: що це було і що з цим робити.
 * Розрізняємо ТРИ різні речі, які легко сплутати:
 *   retryable      — має сенс повторити те саме пізніше (ліміт, 5xx, нема мережі);
 *   switchProvider — цьому провайдеру не допоможе повтор, потрібен наступний вузол;
 *   fatal          — зламаний наш власний запит, повтор ніде не допоможе.
 * @param {{status?:number, message?:string, retryAfter?:string|number|null, offline?:boolean}} o
 */
export function classifyFailure(o = {}) {
  const status = Number(o.status) || 0;
  const msg = String(o.message ?? "").toLowerCase();
  const retryAfterMs = parseRetryAfter(o.retryAfter);

  if (o.offline === true || (!status && /failed to fetch|networkerror|network request|load failed/.test(msg))) {
    return { kind: "offline", retryable: true, switchProvider: false, retryAfterMs };
  }
  if (status === 429 || /\b429\b|rate.?limit|quota|too many requests/.test(msg)) {
    return { kind: "rate-limit", retryable: true, switchProvider: true, retryAfterMs };
  }
  if (status === 408 || status === 425 || (status >= 500 && status <= 599) || /timeout|timed out|overloaded/.test(msg)) {
    return { kind: "transient", retryable: true, switchProvider: status === 503, retryAfterMs };
  }
  if (status === 401 || status === 403) {
    // Ключ не той — повторювати марно, але інший провайдер може спрацювати.
    return { kind: "auth", retryable: false, switchProvider: true, retryAfterMs: null };
  }
  if (status === 404) {
    return { kind: "not-found", retryable: false, switchProvider: true, retryAfterMs: null };
  }
  return { kind: "fatal", retryable: false, switchProvider: false, retryAfterMs: null };
}

/** Retry-After: секунди або HTTP-дата → мілісекунди. Сміття → null. */
export function parseRetryAfter(value, now = Date.now()) {
  if (value === null || value === undefined || value === "") return null;
  const secs = Number(value);
  if (Number.isFinite(secs)) return secs >= 0 ? Math.round(secs * 1000) : null;
  const when = Date.parse(String(value));
  if (Number.isNaN(when)) return null;
  return Math.max(0, when - now);
}

/**
 * Пауза перед наступною спробою: експонента + рівний джитер.
 * Джитер обов'язковий — без нього всі клієнти повертаються одночасно і кладуть
 * провайдера вдруге («громовий табун»). Половина паузи детермінована,
 * половина випадкова, тому очікування ніколи не менше базового.
 * Retry-After від провайдера має пріоритет над нашою формулою.
 */
export function nextBackoffMs(attempt, o = {}) {
  const base = o.baseMs ?? 1000;
  const cap = o.capMs ?? 60000;
  const rand = o.rand ?? Math.random;
  if (o.retryAfterMs !== null && o.retryAfterMs !== undefined) {
    return Math.min(Math.max(0, Math.round(o.retryAfterMs)), cap);
  }
  const exp = Math.min(cap, base * 2 ** Math.max(0, attempt - 1));
  return Math.round(exp / 2 + rand() * (exp / 2));
}

// ── Ланцюг провайдерів зі здоров'ям ────────────────────────────────────────
/** Ланцюг за замовчуванням: хмара → запасна хмара → локальна → офлайн. */
export function defaultChain(settings = {}) {
  const chain = [{ id: "cloud", kind: "cloud" }];
  if (settings.backupProvider) chain.push({ id: "cloud-backup", kind: "cloud", backup: true });
  chain.push({ id: "local", kind: "local" }, { id: "offline", kind: "offline" });
  return chain;
}

/**
 * Перший вузол ланцюга, який зараз доступний: не в cooldown, не вичерпаний
 * у цьому проході й підтриманий можливостями пристрою.
 *
 * ВАЖЛИВО (спіймано браузерним прогоном 2026-09-28): офлайн НЕ береться, поки
 * лишається шанс на справжню відповідь. Інакше перший же 429 закривав завдання
 * деградованою заглушкою — тобто «затримка» знову ставала втратою. Офлайн
 * дозволяється лише явно: остання спроба, вибір користувача або коли інших
 * вузлів у пристрою просто немає.
 */
export function pickProvider(chain, o = {}) {
  const now = o.now ?? Date.now();
  const health = o.health || {};
  const caps = o.caps || {};
  const tried = new Set(o.tried || []);
  for (const node of chain) {
    if (tried.has(node.id)) continue;
    if (node.kind === "offline" && o.allowOffline !== true) continue;
    if ((health[node.id]?.cooldownUntil || 0) > now) continue;
    if (node.kind === "cloud" && !(node.backup ? caps.hasBackupKey : caps.hasCloudKey)) continue;
    if (node.kind === "cloud" && caps.online === false) continue;
    if (node.kind === "local" && !caps.localReady) continue;
    return node;
  }
  return null;
}

/** Невдача вузла: рахуємо поспіль і відсуваємо його на паузу. */
export function markFailure(health, id, o = {}) {
  const now = o.now ?? Date.now();
  const prev = health[id] || { fails: 0, cooldownUntil: 0 };
  const fails = prev.fails + 1;
  const pause = nextBackoffMs(fails, { retryAfterMs: o.retryAfterMs, rand: o.rand ?? (() => 0.5) });
  return { ...health, [id]: { fails, cooldownUntil: now + pause, lastKind: o.kind || "unknown" } };
}

/** Успіх вузла стирає його історію: одна невдача не карає провайдера назавжди. */
export function markSuccess(health, id) {
  if (!health[id]) return health;
  const next = { ...health };
  delete next[id];
  return next;
}

// ── Рішення диспетчера (чиста функція) ─────────────────────────────────────
// Раніше ця логіка жила лише в app.html — і саме тому три P1 із рев'ю Codex
// (PR #74) пройшли повз усі unit-тести: тестувати було нічого. Тепер кожен крок
// обходу ланцюга — чиста функція від вхідних даних.

/**
 * Явний вибір користувача звужує ланцюг, а не лише підпис на чіпі.
 * «Тільки локальна» — обіцянка про дані: запит не залишає пристрій.
 */
export function constrainChain(chain, prefer) {
  if (prefer === "local") return chain.filter((n) => n.kind === "local");
  return chain;
}

/**
 * Що робити з завданням ЗАРАЗ. Повертає одне з:
 *   {action:"run", node}                          — виконати цим вузлом;
 *   {action:"wait", reason:"cooldown", untilMs}   — справжні вузли на паузі: чекати, НЕ витрачаючи спробу;
 *   {action:"wait", reason:"locked"}              — ключ збережено, але ще не відкрито: чекати людину;
 *   {action:"wait", reason:"network"}             — ключ є, мережі нема: чекати мережу;
 *   {action:"exhausted"}                          — у цьому проході справжніх вузлів не лишилось.
 *
 * Три інваріанти (кожен — окреме зауваження Codex, кожен має регрес-тест):
 *  1. Збережений, але замкнений ключ — це СТАН ОЧІКУВАННЯ, а не «ключа нема»:
 *     інакше перезапуск тихо перетворює хмарне завдання на офлайн-заглушку.
 *  2. Чекання cooldown не є невдачею й не витрачає спроб: інакше друге завдання
 *     вичерпує всі спроби й іде в офлайн задовго до кінця вікна провайдера.
 *  3. Явно обраний двигун обмежує ланцюг: «тільки локальна» ніколи не веде в хмару.
 */
export function planDispatch(o = {}) {
  const now = o.now ?? Date.now();
  const caps = o.caps || {};
  const health = o.health || {};
  const tried = new Set(o.tried || []);
  const prefer = o.prefer || "auto";
  const wantsCloud = o.wantsCloud === true;
  const offlineNode = { id: "offline", kind: "offline" };

  if (prefer === "offline") return { action: "run", node: offlineNode };

  const real = constrainChain(o.chain || [], prefer).filter((n) => n.kind !== "offline" && !tried.has(n.id));
  const cooling = [];
  let available = null, lockedBlocked = false, networkBlocked = false;

  for (const node of real) {
    if (node.kind === "cloud") {
      const has = node.backup ? caps.hasBackupKey : caps.hasCloudKey;
      const locked = node.backup ? caps.backupKeyLocked : caps.keyLocked;
      // Чекати ключа чи мережі мають лише завдання з наміром «хмара». Решта (створені
      // за офлайн-чіпа) не блокуються тим, чого людина не збиралась чекати.
      if (!has) { if (locked && wantsCloud) lockedBlocked = true; continue; }
      if (caps.online === false) { if (wantsCloud) networkBlocked = true; continue; }
    } else if (node.kind === "local") {
      if (!caps.localReady) continue;
    }
    const until = health[node.id]?.cooldownUntil || 0;
    if (until > now) { cooling.push(until); continue; }
    if (!available) available = node;
  }

  if (available) return { action: "run", node: available };

  // Уже щось пробували в цьому проході й нічого не лишилось: ланцюг вичерпано.
  // Офлайн — лише як остання ланка на останній спробі.
  if (tried.size > 0) {
    return o.lastChance === true ? { action: "run", node: offlineNode } : { action: "exhausted" };
  }

  // Нічого не пробували, але справжні вузли існують — просто зараз недоступні.
  if (cooling.length) return { action: "wait", reason: "cooldown", untilMs: Math.min(...cooling) };
  if (lockedBlocked) return { action: "wait", reason: "locked" };
  if (networkBlocked) return { action: "wait", reason: "network" };

  // Справжніх вузлів нема взагалі — офлайн-структурування єдине, що можна дати.
  return { action: "run", node: offlineNode };
}

/**
 * Системне сповіщення про збій. Текст завдання туди НЕ потрапляє ніколи: тіло
 * сповіщення видно на екрані блокування, а застосунок в усьому іншому тримає дані
 * на пристрої (рев'ю Codex до PR #74). Приймає завдання лише щоб тест міг довести,
 * що воно ігнорується.
 */
export function failureNotification(_task) {
  return {
    title: "Кишеньковий агент",
    body: "Завдання не вдалося виконати. Відкрий застосунок, щоб повторити.",
  };
}

// ── Черга завдань ──────────────────────────────────────────────────────────
/** Завдання з детермінованих полів; id ззовні, щоб тест був відтворюваний. */
export function makeTask({ input, kind = "ask", now = Date.now(), id, intent = "any" }) {
  const text = String(input ?? "").trim();
  return {
    id: id || `t${now}-${Math.abs(hashString(text + now)).toString(36)}`,
    input: text,
    kind,
    // Намір фіксується при створенні: якщо чіп казав «хмара», завдання має право
    // ЧЕКАТИ ключа чи мережі. Якщо чіп казав «офлайн», людина очікує офлайн-відповіді
    // одразу — змушувати її чекати ключа, якого вона не збиралась відкривати, помилка.
    intent: intent === "cloud" ? "cloud" : "any",
    status: "pending",
    attempts: 0,
    nextAttemptAt: now,
    createdAt: now,
    tried: [],
    lastError: null,
  };
}

/** Найстаріше завдання, якому вже час виконуватись. */
export function nextRunnable(queue, now = Date.now()) {
  return (queue || [])
    .filter((t) => t.status === "pending" && !t.waiting && t.nextAttemptAt <= now)
    .sort((a, b) => a.createdAt - b.createdAt)[0] || null;
}

/**
 * Результат спроби → новий стан черги (чиста функція, вхідну чергу не мутує).
 * Правила: успіх → done · вичерпані спроби → failed (НЕ зникає, лишається видимим
 * і придатним до ручного повтору) · інакше → pending з розрахованою паузою.
 */
export function applyOutcome(queue, id, outcome, o = {}) {
  const now = o.now ?? Date.now();
  const maxAttempts = o.maxAttempts ?? MAX_ATTEMPTS;
  return (queue || []).map((t) => {
    if (t.id !== id) return t;
    if (outcome.ok) {
      return { ...t, status: "done", answer: outcome.answer, engine: outcome.engine, finishedAt: now, lastError: null };
    }
    const f = outcome.failure || { retryable: false, kind: "fatal" };
    const attempts = t.attempts + 1;
    const tried = outcome.tried || (outcome.engine ? [outcome.engine] : []);
    const exhausted = !f.retryable || attempts >= maxAttempts;
    if (exhausted) {
      return { ...t, status: "failed", attempts, tried, lastError: outcome.error || f.kind, finishedAt: now };
    }
    // Новий раунд — чистий список: cooldown уже стримує щойно впалий вузол,
    // а постійний «чорний список» назавжди відрізав би найкращого провайдера
    // через одну тимчасову помилку.
    // Новий раунд — чистий список: обхід ланцюга вже відбувся в межах проходу,
    // а постійний «чорний список» назавжди відрізав би найкращого провайдера
    // через одну тимчасову помилку (спіймано браузерним прогоном 2026-09-28).
    const pause = nextBackoffMs(attempts, { retryAfterMs: f.retryAfterMs, rand: o.rand });
    return { ...t, status: "pending", attempts, tried, lastError: outcome.error || f.kind, nextAttemptAt: now + pause };
  });
}

/**
 * Відкласти завдання БЕЗ витрати спроби. Чекання — не невдача: спробу з'їдає лише
 * справжній виклик, що відмовив. Дві форми:
 *   {untilMs}  — таймерне чекання (cooldown провайдера): пробудиться саме;
 *   {waiting}  — чекання події («locked» — відкрий ключ, «network» — мережа):
 *                таймера нема, будить `wakeWaiting`. Без цього спорожнення крутилось
 *                би в холосту, бо завдання лишалось би «готовим» щоразу.
 */
export function deferTask(queue, id, o = {}) {
  return (queue || []).map((t) => {
    if (t.id !== id) return t;
    if (o.waiting) return { ...t, waiting: o.waiting };
    return { ...t, waiting: undefined, nextAttemptAt: Math.max(t.nextAttemptAt, o.untilMs ?? t.nextAttemptAt) };
  });
}

/** Розбудити завдання, що чекали подію (усі або лише за причиною). */
export function wakeWaiting(queue, reason) {
  return (queue || []).map((t) =>
    t.waiting && (!reason || t.waiting === reason) ? { ...t, waiting: undefined } : t,
  );
}

/** Ручний повтор завдання, що вичерпало спроби: лічильник і історія — з нуля. */
export function requeue(queue, id, now = Date.now()) {
  return (queue || []).map((t) =>
    t.id === id && t.status === "failed"
      ? { ...t, status: "pending", attempts: 0, tried: [], nextAttemptAt: now, lastError: null }
      : t,
  );
}

/** Прибрати завершені — черга не має рости вічно. */
export function pruneQueue(queue, o = {}) {
  const keep = o.keepDone ?? 0;
  const done = (queue || []).filter((t) => t.status === "done").sort((a, b) => b.finishedAt - a.finishedAt);
  const keepIds = new Set(done.slice(0, keep).map((t) => t.id));
  return (queue || []).filter((t) => t.status !== "done" || keepIds.has(t.id));
}

/**
 * Зведення для сповіщення: що показати людині одним рядком.
 * Головне — НЕ мовчати: якщо щось чекає або впало, це має бути видно без пошуку.
 */
export function queueSummary(queue, now = Date.now()) {
  const list = queue || [];
  const pending = list.filter((t) => t.status === "pending");
  const failed = list.filter((t) => t.status === "failed");
  const parkedLocked = pending.filter((t) => t.waiting === "locked");
  const parkedNet = pending.filter((t) => t.waiting === "network");
  const timed = pending.filter((t) => !t.waiting && t.nextAttemptAt > now);
  const nextAt = timed.length ? Math.min(...timed.map((t) => t.nextAttemptAt)) : null;
  let text = "";
  if (failed.length) text = `${failed.length} не вдалося — потрібен ручний повтор`;
  else if (parkedLocked.length) text = `${parkedLocked.length} чекає: відкрий ключ (⚙ → «Відкрити»)`;
  else if (parkedNet.length) text = `${parkedNet.length} чекає на мережу`;
  else if (timed.length) text = `${pending.length} у черзі · наступна спроба через ${Math.max(1, Math.round((nextAt - now) / 1000))} с`;
  else if (pending.length) text = `${pending.length} у черзі · виконується`;
  return {
    pending: pending.length,
    failed: failed.length,
    done: list.filter((t) => t.status === "done").length,
    nextAttemptIn: nextAt === null ? null : Math.max(0, nextAt - now),
    needsAttention: failed.length > 0 || parkedLocked.length > 0,
    text,
  };
}
