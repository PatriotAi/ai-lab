#!/usr/bin/env node
// mobile-agent-browser.mjs — РЕАЛЬНИЙ прогін застосунку в мобільному браузері.
// Єдина відповідальність: довести, що зібраний один файл справді працює як застосунок
// на телефоні (емуляція Pixel 7, Chromium): ввід → відповідь → нотатка → пошук →
// перезапуск → PWA (manifest + service worker) → шифрування ключа.
//
// Запуск: node tests/mobile-agent-browser.mjs
// Потребує playwright + Chromium. Якщо їх нема — тест ПРОПУСКАЄТЬСЯ (exit 0),
// бо базовий набір tests/run-tests.sh не має мережевих/бінарних залежностей.

import { createServer } from "node:http";
import { readFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIST = join(REPO, "projects", "mobile-agent", "dist", "mobile-agent.html");
const SHOTS = join(REPO, "projects", "mobile-agent", "dist", "screenshots");

let pw = null;
for (const path of ["playwright", "/opt/node22/lib/node_modules/playwright/index.js"]) {
  try {
    const mod = await import(path);
    pw = mod.chromium ? mod : mod.default;   // CJS-збірка приходить у .default
    if (pw?.chromium) break;
    pw = null;
  } catch {}
}
if (!pw) {
  console.log("⏭  playwright недоступний — браузерний прогін пропущено (це не падіння)");
  console.log("TOTALS pass=0 fail=0 skipped=1");
  process.exit(0);
}

let PASS = 0, FAIL = 0;
const FAILED = [];
const ok = (n) => { PASS++; console.log(`  ✅ ${n}`); };
const bad = (n, exp, got) => { FAIL++; FAILED.push(n); console.log(`  ❌ ${n}\n     очікували: ${exp}\n     отримали:  ${got}`); };
const check = (n, exp, got) => (String(exp) === String(got) ? ok(n) : bad(n, exp, got));
const truthy = (n, v, exp = "істина") => (v ? ok(n) : bad(n, exp, JSON.stringify(v)));

// Локальний сервер: localhost — secure origin, тому працюють service worker і
// WebCrypto так само, як на HTTPS-хостингу (Netlify Drop) на реальному телефоні.
const html = readFileSync(DIST);
const sw = readFileSync(join(REPO, "projects", "mobile-agent", "dist", "sw.js"));
const server = createServer((req, res) => {
  if (req.url.startsWith("/version.json")) {
    res.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" });
    return res.end(JSON.stringify({ version: "99.0.0", notes: "тестове оновлення" }));
  }
  if (req.url.startsWith("/sw.js")) {
    res.writeHead(200, { "content-type": "text/javascript; charset=utf-8" });
    return res.end(req.method === "HEAD" ? undefined : sw);
  }
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(req.method === "HEAD" ? undefined : html);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://localhost:${server.address().port}/`;

const browser = await pw.chromium.launch();
const context = await browser.newContext({ ...pw.devices["Pixel 7"], locale: "uk-UA" });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

try {
  console.log(`\n════════ Браузерний прогін (Pixel 7 · Chromium · ${base}) ════════`);
  await page.goto(base, { waitUntil: "networkidle" });

  check("сторінка завантажилась", "Кишеньковий агент", await page.title());
  check("помилок у консолі нема", 0, errors.length ? errors.join(" | ") : 0);
  truthy("застосунок ініціалізувався", await page.evaluate(() => !!window.PocketAgent));

  const chip = (await page.textContent("#engineChip")).trim();
  check("без ключа й WebGPU двигун — офлайн", true, chip.includes("офлайн"));
  truthy("порожній стан пояснює, що робити", (await page.textContent("#list")).includes("Порожньо"));

  // ── Наскрізний зріз: ввід → відповідь → нотатка ──
  await page.fill("#input", "Спланувати демо мобільного агента #ai-lab");
  await page.click("#send");
  await page.waitForSelector(".note");
  check("зʼявилась рівно одна нотатка", 1, await page.locator(".note").count());
  truthy("нотатка містить відповідь офлайн-двигуна",
    (await page.textContent(".note .a")).includes("Офлайн-режим"));
  truthy("тег розпізнано", (await page.textContent(".note .tags")).includes("#ai-lab"));
  check("поле вводу очистилось", "", await page.inputValue("#input"));

  // ── Задача ──
  await page.fill("#input", "+ купити квитки на #конференцію");
  await page.click("#send");
  await page.waitForFunction(() => document.querySelectorAll(".note").length === 2);
  check("задача позначена окремо", 1, await page.locator(".note.task").count());

  // ── Пошук ──
  await page.fill("#search", "квитки");
  await page.waitForFunction(() => document.querySelectorAll(".note").length === 1);
  truthy("пошук знайшов саме задачу", (await page.textContent(".note .q")).includes("квитки"));
  await page.fill("#search", "кит-якого-нема");
  await page.waitForFunction(() => document.body.innerText.includes("Нічого не знайдено"));
  ok("пошук без збігів показує зрозумілий стан");
  await page.fill("#search", "");

  // ── Перезапуск: дані переживають закриття застосунку ──
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".note");
  check("після перезапуску нотатки на місці", 2, await page.locator(".note").count());

  // ── Секрети: ключ шифрується на пристрої ──
  await page.click("#openSettings");
  await page.waitForSelector("#settings[open]");
  ok("налаштування відкриваються");
  const FAKE = "sk-ant-test-" + "z".repeat(20);
  await page.fill("#apikey", FAKE);
  await page.fill("#passphrase", "моя-фраза");
  await page.click("#saveKey");
  await page.waitForFunction(() => !!localStorage.getItem("pocket-agent.secret.v1"));
  const stored = await page.evaluate(() => localStorage.getItem("pocket-agent.secret.v1"));
  truthy("ключ у сховищі зашифрований (відкритого тексту нема)", !stored.includes(FAKE));
  truthy("конверт має сіль та IV", stored.includes('"salt"') && stored.includes('"iv"'));
  const dump = await page.evaluate(() => JSON.stringify(localStorage));
  truthy("відкритого ключа нема НІДЕ в localStorage", !dump.includes(FAKE));
  check("з ключем двигун перемикається на хмару", true,
    (await page.textContent("#engineChip")).includes("хмара"));

  // Після перезапуску ключ лишається закритим, доки не введено фразу
  await page.reload({ waitUntil: "networkidle" });
  check("після перезапуску ключ замкнений (двигун знову офлайн)", true,
    (await page.textContent("#engineChip")).includes("офлайн"));
  await page.click("#openSettings");
  await page.fill("#passphrase", "не-та-фраза");
  await page.click("#unlockKey");
  await page.waitForFunction(() => document.getElementById("keyHint").textContent.includes("Хибна"));
  ok("хибна пароль-фраза відхиляється");
  await page.fill("#passphrase", "моя-фраза");
  await page.click("#unlockKey");
  await page.waitForFunction(() => document.getElementById("engineChip").textContent.includes("хмара"));
  ok("правильна пароль-фраза відкриває ключ");

  // ── Авто-оновлення ──
  await page.fill("#updateUrl", base + "version.json");
  await page.dispatchEvent("#updateUrl", "change");
  await page.click("#checkUpdate");
  await page.waitForSelector("#banner.on");
  truthy("новіша версія показує банер оновлення",
    (await page.textContent("#bannerText")).includes("99.0.0"));
  await page.click("#closeSettings");

  // ── PWA ──
  const manifest = await page.evaluate(async () => {
    const href = document.querySelector('link[rel="manifest"]').href;
    return JSON.parse(atob(href.split("base64,")[1]));
  });
  check("манифест читається браузером", "standalone", manifest.display);
  check("іконка вантажиться як зображення", "192x192", await page.evaluate((src) => new Promise((res) => {
    const i = new Image();
    i.onload = () => res(`${i.naturalWidth}x${i.naturalHeight}`);
    i.onerror = () => res("не завантажилась");
    i.src = src;
  }), manifest.icons[0].src));
  const swState = await page.evaluate(async () => {
    const r = await navigator.serviceWorker.getRegistration();
    return r ? "зареєстровано" : "нема";
  });
  check("service worker зареєстровано на secure origin", "зареєстровано", swState);

  // ── Офлайн: застосунок відкривається без мережі ──
  await context.setOffline(true);
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector(".note");
  check("без мережі застосунок відкривається з кешу", 2, await page.locator(".note").count());
  await page.fill("#input", "думка без мережі");
  await page.click("#send");
  await page.waitForFunction(() => document.querySelectorAll(".note").length === 3);
  ok("без мережі агент однаково приймає й обробляє запис");
  await context.setOffline(false);

  // ── Резервний контур: падіння API має ЗАТРИМАТИ, а не втратити роботу ──
  // Перевіряємо саме обіцянку, а не її частини: кладемо провайдера, дивимось,
  // що завдання лишилось у черзі, і що після відновлення відповідь реальна.
  let cloudCalls = 0;
  await page.route("**/api.anthropic.com/**", async (route) => {
    cloudCalls++;
    if (cloudCalls === 1) {
      return route.fulfill({ status: 429, headers: { "retry-after": "1" }, contentType: "application/json",
        body: JSON.stringify({ error: { message: "rate limit" } }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ content: [{ type: "text", text: "справжня відповідь після повтору" }] }) });
  });
  await page.evaluate(() => {
    window.PocketAgent.state.apiKey = "test-key";
    window.PocketAgent.state.notes = [];
    window.PocketAgent.state.queue = [];
    localStorage.removeItem("pocket-agent.queue.v1");
    window.PocketAgent.render();
  });

  await page.fill("#input", "завдання під час падіння API");
  await page.click("#send");
  await page.waitForFunction(() => document.querySelectorAll("#queue .qitem").length === 1);
  ok("завдання одразу стало в чергу, а не зникло");
  check("поле вводу звільнилось одразу (можна писати далі)", "", await page.inputValue("#input"));
  // Стан «чекає повтору» триває лише ≈1 с (базова пауза). Одноразове читання після кількох раундтрипів
  // програвало гонку під навантаженням (спіймано мутаційним прогоном 2026-09-30: 1 із 3 запусків), тому
  // чекаємо САМУ появу стану, а не знімаємо його наосліп. Збій дає реальний текст, а не голий виняток.
  let waitText;
  try {
    waitText = await (await page.waitForFunction(() => {
      const t = document.getElementById("queueStatus").textContent;
      return t.includes("черзі") && /через \d+ с/.test(t) ? t : false;
    }, null, { polling: "raf", timeout: 8000 })).jsonValue();
  } catch {
    waitText = await page.textContent("#queueStatus");
  }
  truthy("після 429 завдання чекає на повтор, а не провалилось", waitText.includes("черзі"), waitText);
  truthy("видно, коли буде наступна спроба", /через \d+ с/.test(waitText), waitText);

  await page.waitForFunction(() => document.querySelectorAll(".note").length === 1, null, { timeout: 15000 });
  truthy("після повтору прийшла СПРАВЖНЯ відповідь, не офлайн-заглушка",
    (await page.textContent(".note .a")).includes("справжня відповідь після повтору"));
  check("провайдера викликано двічі: падіння + успішний повтор", 2, cloudCalls);
  check("черга спорожніла після успіху", 0, await page.locator("#queue .qitem").count());
  // P2 (рев'ю Codex): рядок у черзі зникає з екрана, але лишався б у localStorage
  const persisted = await page.evaluate(() => JSON.parse(localStorage.getItem("pocket-agent.queue.v1") || "[]"));
  check("завершені завдання не лишаються в localStorage (квота)", 0, persisted.filter((x) => x.status === "done").length);
  truthy("відповідь не дублюється в збереженій черзі",
    !JSON.stringify(persisted).includes("справжня відповідь після повтору"));

  // Вичерпання ланцюга: запис усе одно лишається, завдання видиме й повторюване
  await page.unroute("**/api.anthropic.com/**");
  await page.route("**/api.anthropic.com/**", (route) =>
    route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ error: { message: "bad request" } }) }));
  await page.evaluate(() => { window.PocketAgent.state.caps.webgpu = false; });
  await page.fill("#input", "завдання з фатальним збоєм");
  await page.click("#send");
  await page.waitForFunction(() => document.querySelectorAll("#queue .qitem.failed").length === 1, null, { timeout: 15000 });
  ok("фатальний збій → завдання позначене як невдале, а не зникло");
  truthy("є кнопка ручного повтору", await page.locator(".qretry").count() === 1);
  truthy("стан прямо каже, що потрібна дія людини",
    (await page.textContent("#queueStatus")).includes("ручний повтор"));
  truthy("запис усе одно збережено (робота не втрачена)",
    (await page.textContent(".note .a")).includes("Провайдери недоступні"));

  // Черга переживає перезапуск застосунку — інакше «затримка» перетворюється на втрату
  await page.evaluate(() => {
    window.PocketAgent.state.queue = [{ id: "survivor", input: "пережити перезапуск", kind: "ask",
      status: "pending", attempts: 0, nextAttemptAt: Date.now() + 600000, createdAt: Date.now(), tried: [], lastError: null }];
    localStorage.setItem("pocket-agent.queue.v1", JSON.stringify(window.PocketAgent.state.queue));
  });
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelectorAll("#queue .qitem").length >= 1);
  truthy("незавершене завдання пережило перезапуск застосунку",
    (await page.textContent("#queue .qitem .qtext")).includes("пережити перезапуск"));

  // ── Рев'ю Codex (PR #74): три P1 у реальному браузері ──
  // Кожен із них пройшов усі unit-тести, доки логіка жила лише в app.html.
  const reset = (extra = "") => page.evaluate(`(() => { const s = window.PocketAgent.state;
    s.queue = []; s.notes = []; s.health = {}; s.settings.prefer = "auto"; ${extra}
    localStorage.setItem("pocket-agent.queue.v1", "[]"); localStorage.setItem("pocket-agent.notes.v1", "[]");
    window.PocketAgent.render(); })()`);
  const okAnswer = (text) => (route) => route.fulfill({ status: 200, contentType: "application/json",
    body: JSON.stringify({ content: [{ type: "text", text }] }) });
  // Очікування стану З ІМЕНЕМ: голий таймаут Playwright дає «прогін завершився винятком» без вказівки,
  // ЩО саме не настало, і мутаційний прогін не може відрізнити влучний збій від випадкового.
  const until = async (name, fn, timeout = 15000) => {
    try { await page.waitForFunction(fn, null, { timeout }); }
    catch { bad(name, "стан настав", `не настав за ${timeout} мс`); throw new Error(`не настало: ${name}`); }
  };

  // P1-1: замкнений ключ після перезапуску — очікування, а не тиха деградація
  await page.unroute("**/api.anthropic.com/**");
  let lockedCalls = 0;
  await page.route("**/api.anthropic.com/**", (route) => { lockedCalls++; return okAnswer("відповідь після розблокування")(route); });
  await page.evaluate(async () => {
    const env = await window.PocketAgent.core.encryptSecret("real-key", "фраза-розблокування");
    localStorage.setItem("pocket-agent.secret.v1", JSON.stringify(env));
    localStorage.setItem("pocket-agent.notes.v1", "[]");
    localStorage.setItem("pocket-agent.queue.v1", JSON.stringify([{
      id: "locked1", input: "відновлене хмарне завдання", kind: "ask", intent: "cloud", status: "pending",
      attempts: 0, nextAttemptAt: Date.now() - 1000, createdAt: Date.now() - 2000, tried: [], lastError: null }]));
  });
  await page.reload({ waitUntil: "networkidle" });   // ключ у пам'яті сесії порожній: він замкнений
  await until("P1-1: після перезапуску завдання чекає відкриття ключа",
    () => document.getElementById("queueStatus").textContent.includes("відкрий ключ"));
  ok("P1-1: після перезапуску завдання чекає відкриття ключа");
  await page.waitForTimeout(1500);                    // тиша не є доказом — даємо шанс деградувати
  check("P1-1: завдання не деградувало в офлайн-нотатку", 0, await page.locator(".note").count());
  check("P1-1: у хмару без ключа нічого не пішло", 0, lockedCalls);
  truthy("P1-1: у списку названо причину очікування",
    (await page.textContent("#queue .qmeta")).includes("чекає ключа"));
  await page.click("#openSettings");
  await page.fill("#passphrase", "фраза-розблокування");
  await page.click("#unlockKey");
  await until("P1-1: розблокування будить чергу — завдання виконалось без ручного повтору",
    () => document.querySelectorAll(".note").length === 1);
  truthy("P1-1: після розблокування прийшла СПРАВЖНЯ відповідь",
    (await page.textContent(".note .a")).includes("відповідь після розблокування"));
  check("P1-1: хмару викликано рівно раз", 1, lockedCalls);
  await page.click("#closeSettings");

  // Retry-After у РЕАЛЬНОМУ браузері читається лише якщо провайдер розкриває його через
  // Access-Control-Expose-Headers. Без цього fetch повертає null — і «Retry-After має
  // пріоритет» лишається мертвим кодом (доведено прямо 2026-09-29). Контур мусить
  // лишатись справним в обох випадках, тому перевіряємо обидва.
  await page.unroute("**/api.anthropic.com/**");
  await page.route("**/api.anthropic.com/**", (route) =>
    route.fulfill({ status: 429, headers: { "retry-after": "30" }, contentType: "application/json",
      body: JSON.stringify({ error: { message: "rate limit" } }) }));
  await reset(`s.apiKey = "k";`);
  await page.fill("#input", "завдання без розкритого Retry-After");
  await page.click("#send");
  await page.waitForFunction(() => window.PocketAgent.state.queue.some((x) => x.attempts === 1));
  const hiddenCd = await page.evaluate(() => window.PocketAgent.state.health.cloud.cooldownUntil - Date.now());
  truthy("Retry-After без CORS-дозволу браузер не віддає → контур падає на експоненту (пауза коротка), а не ламається",
    hiddenCd < 3000, "пауза < 3 с");

  // P1-2: cooldown не з'їдає спроб і не б'є провайдера, що ще на паузі
  await page.unroute("**/api.anthropic.com/**");
  let coolCalls = 0;
  await page.route("**/api.anthropic.com/**", (route) => { coolCalls++;
    return route.fulfill({ status: 429, contentType: "application/json",
      headers: { "retry-after": "30", "access-control-expose-headers": "retry-after" },
      body: JSON.stringify({ error: { message: "rate limit" } }) }); });
  await reset(`s.apiKey = "k";`);
  await page.fill("#input", "перше завдання кладе провайдера");
  await page.click("#send");
  await page.waitForFunction(() => window.PocketAgent.state.queue.some((x) => x.attempts === 1));
  const shownCd = await page.evaluate(() => window.PocketAgent.state.health.cloud.cooldownUntil - Date.now());
  truthy("Retry-After, розкритий через CORS, реально керує паузою (~30 с)", shownCd > 25000, "пауза > 25 с");
  await page.fill("#input", "друге завдання під час cooldown");
  await page.click("#send");
  await page.waitForFunction(() => {
    const b = window.PocketAgent.state.queue.find((x) => x.input.startsWith("друге"));
    return b && b.nextAttemptAt > Date.now() + 10000;
  });
  const second = await page.evaluate(() => window.PocketAgent.state.queue.find((x) => x.input.startsWith("друге")));
  check("P1-2: друге завдання чекає, спробу НЕ витрачено", 0, second.attempts);
  check("P1-2: воно лишилось у черзі, а не пішло в офлайн", "pending", second.status);
  check("P1-2: провайдера, що на паузі, не било (лише перший виклик)", 1, coolCalls);
  check("P1-2: офлайн-нотаток нема — роботу не підмінено", 0, await page.locator(".note").count());

  // P1-3: «Тільки локальна» не відправляє запит у хмару
  await page.unroute("**/api.anthropic.com/**");
  let leakCalls = 0;
  await page.route("**/api.anthropic.com/**", (route) => { leakCalls++; return okAnswer("НЕ МАЛО ПРИЛЕТІТИ")(route); });
  await reset(`s.apiKey = "k"; s.settings.prefer = "local";`);
  await page.fill("#input", "приватний запит лише для локальної моделі");
  await page.click("#send");
  await page.waitForFunction(() => document.querySelectorAll(".note").length === 1, null, { timeout: 15000 });
  check("P1-3: у хмару НІЧОГО не пішло попри відкритий ключ і мережу", 0, leakCalls);
  truthy("P1-3: відповідь не від хмари", !(await page.textContent(".note .a")).includes("НЕ МАЛО ПРИЛЕТІТИ"));
  truthy("P1-3: чіп чесно каже «офлайн», а не «хмара»", (await page.textContent("#engineChip")).includes("офлайн"));
  await reset();

  // Застарілий прапорець очікування після перезапуску не має «заморозити» завдання назавжди:
  // прапорець зберігається в localStorage, а подія `online`, що його будить, уже не прийде.
  await page.unroute("**/api.anthropic.com/**");
  await page.evaluate(() => {
    localStorage.removeItem("pocket-agent.secret.v1");
    localStorage.setItem("pocket-agent.notes.v1", "[]");
    localStorage.setItem("pocket-agent.queue.v1", JSON.stringify([{
      id: "stale1", input: "завдання із застарілим очікуванням мережі", kind: "ask", intent: "any",
      status: "pending", waiting: "network", attempts: 0, nextAttemptAt: Date.now() - 1000,
      createdAt: Date.now() - 2000, tried: [], lastError: null }]));
  });
  await page.reload({ waitUntil: "networkidle" });
  await until("застарілий прапорець очікування після перезапуску не заморозив завдання",
    () => document.querySelectorAll(".note").length === 1);
  ok("застарілий прапорець очікування після перезапуску не заморозив завдання");
  await reset();

  // P2-2: проводка сповіщення. Чиста failureNotification вже перевірена юніт-тестом, але
  // саме `new Notification(...)` в app.html міг би знову взяти текст завдання — тому
  // підміняємо Notification і читаємо, що застосунок справді передав ОС.
  await page.unroute("**/api.anthropic.com/**");
  await page.route("**/api.anthropic.com/**", (route) =>
    route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ error: { message: "bad" } }) }));
  await reset(`s.apiKey = "k";`);
  await page.evaluate(() => {
    window.__osNotes = [];
    window.Notification = class { constructor(title, opts) { window.__osNotes.push({ title, ...opts }); }
      static get permission() { return "granted"; } };
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
  });
  await page.fill("#input", "мій діагноз і пароль SuperSecret777");
  await page.click("#send");
  await page.waitForFunction(() => window.__osNotes.length === 1, null, { timeout: 15000 });
  const osNote = await page.evaluate(() => window.__osNotes[0]);
  truthy("P2-2: системне сповіщення про збій справді показано, коли застосунок згорнуто", osNote.body.length > 0);
  truthy("P2-2: у сповіщенні (видно на екрані блокування) НЕМАЄ тексту завдання",
    !JSON.stringify(osNote).includes("SuperSecret777") && !JSON.stringify(osNote).includes("діагноз"));
  await page.evaluate(() => { delete document.visibilityState; });
  await reset();

  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: join(SHOTS, "pixel7-offline.png"), fullPage: false });
  ok("знімок екрана збережено (dist/screenshots/pixel7-offline.png)");

  // Мережеві відмови під час офлайн-частини — очікувані (проба sw.js і version.json
  // не мають мережі й обробляються застосунком). Усе інше — справжня помилка.
  // 429 і 400 створені цим же тестом навмисно (падіння провайдера й фатальний
  // запит) — це очікуваний шум, а не дефект. Усе інше лишається помилкою.
  const unexpected = errors.filter((e) =>
    !/ERR_INTERNET_DISCONNECTED|ERR_NETWORK_CHANGED|429 \(Too Many Requests\)|400 \(Bad Request\)/.test(e));
  check("наприкінці прогону несподіваних помилок нема", 0, unexpected.length ? unexpected.join(" | ") : 0);
} catch (e) {
  bad("прогін завершився винятком", "без винятків", String(e).split("\n")[0]);
} finally {
  await browser.close();
  server.close();
}

console.log(`\nTOTALS pass=${PASS} fail=${FAIL}`);
if (FAIL) {
  console.log("Впали:\n" + FAILED.map((f) => "  - " + f).join("\n"));
  process.exit(1);
}
