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

  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: join(SHOTS, "pixel7-offline.png"), fullPage: false });
  ok("знімок екрана збережено (dist/screenshots/pixel7-offline.png)");

  // Мережеві відмови під час офлайн-частини — очікувані (проба sw.js і version.json
  // не мають мережі й обробляються застосунком). Усе інше — справжня помилка.
  const unexpected = errors.filter((e) => !/ERR_INTERNET_DISCONNECTED|ERR_NETWORK_CHANGED/.test(e));
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
