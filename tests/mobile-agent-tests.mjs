#!/usr/bin/env node
// mobile-agent-tests.mjs — регресійні тести проєкту projects/mobile-agent.
// Єдина відповідальність: довести ділом, що логіка агента, збірка одного файлу
// й PWA-інваріанти працюють як описано. Без мережі, без секретів, без залежностей понад node.
//
// Запуск локально:  node tests/mobile-agent-tests.mjs
// У складі набору:  bash tests/run-tests.sh (секція 6)
// Останній рядок виводу: TOTALS pass=N fail=M — його парсить run-tests.sh.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..");
const PROJ = join(REPO, "projects", "mobile-agent");

const core = await import(join(PROJ, "src", "core.js"));
const build = await import(join(PROJ, "build.mjs"));

let PASS = 0, FAIL = 0;
const FAILED = [];
const ok = (n) => { PASS++; console.log(`  ✅ ${n}`); };
const bad = (n, exp, got) => {
  FAIL++; FAILED.push(n);
  console.log(`  ❌ ${n}\n     очікували: ${exp}\n     отримали:  ${got}`);
};
const check = (n, exp, got) => (String(exp) === String(got) ? ok(n) : bad(n, exp, got));
const truthy = (n, v, exp = "істина") => (v ? ok(n) : bad(n, exp, JSON.stringify(v)));

// ═══════ 1. Вибір двигуна (три рівні деградації) ═══════
console.log('\n════════ 1. Вибір двигуна ════════');
const pe = core.pickEngine;
check("мережа+ключ → хмара", "cloud", pe({ online: true, hasCloudKey: true }).engine);
check("без ключа, є WebGPU+HTTPS → локальна", "local",
  pe({ online: true, hasCloudKey: false, webgpu: true, secureContext: true }).engine);
check("нічого нема → офлайн", "offline", pe({ online: false, hasCloudKey: false }).engine);
check("WebGPU без HTTPS не рахується", "offline",
  pe({ online: false, webgpu: true, secureContext: false }).engine);
check("ключ є, але мережі нема → не хмара", "offline",
  pe({ online: false, hasCloudKey: true, webgpu: false }).engine);
check("prefer=offline поважається навіть за наявності хмари", "offline",
  pe({ online: true, hasCloudKey: true, prefer: "offline" }).engine);
check("prefer=local без WebGPU → падає на хмару", "cloud",
  pe({ online: true, hasCloudKey: true, webgpu: false, prefer: "local" }).engine);
truthy("вимушена деградація позначена fallback=true",
  pe({ online: true, hasCloudKey: true, webgpu: false, prefer: "local" }).fallback === true);
truthy("свідомий вибір не позначається fallback",
  pe({ online: true, hasCloudKey: true, prefer: "cloud" }).fallback === false);

// ═══════ 2. Версії та авто-оновлення ═══════
console.log('\n════════ 2. Версії / авто-оновлення ════════');
check("0.2.0 новіше за 0.1.9", "true", String(core.isNewerVersion("0.2.0", "0.1.9")));
check("однакові — не новіше", "false", String(core.isNewerVersion("1.0.0", "1.0.0")));
check("старіше — не новіше", "false", String(core.isNewerVersion("0.9.9", "1.0.0")));
check("10 > 9 (порівняння числове, не рядкове)", "true", String(core.isNewerVersion("0.10.0", "0.9.0")));
check("сміття не ламає порівняння", "false", String(core.isNewerVersion("", "0.1.0")));

// ═══════ 3. Розбір вводу ═══════
console.log('\n════════ 3. Розбір вводу ════════');
check("звичайний текст → запитання", "ask", core.parseCommand("Як спланувати тиждень?").kind);
check("«+» → задача", "task", core.parseCommand("+ купити квитки").kind);
check("«знайди …» → пошук", "search", core.parseCommand("знайди агент").kind);
check("пошук віддає лише запит", "агент", core.parseCommand("знайди агент").payload);
check("порожній ввід не падає", "ask", core.parseCommand("   ").kind);
check("регістр префікса неважливий", "search", core.parseCommand("ЗНАЙДИ демо").kind);

// ═══════ 4. Офлайн-двигун ═══════
console.log('\n════════ 4. Офлайн-двигун (без моделі) ════════');
const off = core.offlineAnswer("Треба підготувати демо мобільного агента #ai-lab до п'ятниці", "task");
truthy("офлайн-відповідь непорожня", off.length > 20);
truthy("позначає себе як офлайн (без імітації моделі)", off.includes("Офлайн-режим"));
truthy("витягує тег", off.includes("#ai-lab"));
truthy("витягує ключові слова", off.includes("Ключові слова"));
check("детермінований (двічі — те саме)", off, core.offlineAnswer("Треба підготувати демо мобільного агента #ai-lab до п'ятниці", "task"));
check("порожній ввід → зрозуміла відмова, не виняток", true, core.offlineAnswer("").includes("Порожній"));
check("теги унікальні й у нижньому регістрі", "ai,lab", core.extractTags("#AI #lab #ai").join(","));

// ═══════ 5. Нотатки й пошук ═══════
console.log('\n════════ 5. Нотатки й пошук ════════');
const n1 = core.makeNote({ input: "Ідея про #агента у телефоні", answer: "коротко", engine: "offline", now: 1000 });
const n2 = core.makeNote({ input: "Купити каву", answer: "нагадування про #агента", engine: "offline", kind: "task", now: 2000 });
check("нотатка має id", true, !!n1.id);
check("теги збережено", "агента", n1.tags.join(","));
check("id різні для різних нотаток", true, n1.id !== n2.id);
check("пошук за тегом знаходить обидві", 2, core.searchNotes([n1, n2], "агента").length);
check("збіг у вводі важить більше за збіг у відповіді", n1.id, core.searchNotes([n1, n2], "агента")[0].id);
check("порожній запит → усі, найновіші перші", n2.id, core.searchNotes([n1, n2], "")[0].id);
check("нема збігу → порожньо", 0, core.searchNotes([n1, n2], "кит").length);
check("пошук не падає на порожньому списку", 0, core.searchNotes(null, "щось").length);

// ═══════ 6. Придатність локальної моделі ═══════
console.log('\n════════ 6. Локальна модель: придатність ════════');
check("оцінка VRAM ≈ 45% RAM", 1843, core.estimateVramMB(4, true));
check("без даних про RAM, але з WebGPU → консервативно", 2048, core.estimateVramMB(null, true));
const ranked = core.rankLocalModels(
  [{ id: "Big-7B-q4f16_1-MLC", vram: 6000 }, { id: "Small-1.5B-q4f16_1-MLC", vram: 1200 }, { id: "Other-3B-q4f32_1-MLC", vram: 1500 }],
  2048,
);
check("не-q4f16 відсіяно", 2, ranked.length);
check("першою — та, що влазить", "Small-1.5B-q4f16_1-MLC", ranked[0].id);
check("завелика позначена як «не влазить»", false, ranked[1].fits);

// ═══════ 7. Секрети: шифрування ключа ═══════
console.log('\n════════ 7. Секрети (AES-GCM + пароль-фраза) ════════');
const SAMPLE_KEY = "sk-ant-" + "x".repeat(24);
const env = await core.encryptSecret(SAMPLE_KEY, "пароль-фраза");
check("формат конверта версійований", 1, env.v);
check("KDF задокументовано в конверті", "PBKDF2-SHA256", env.kdf);
truthy("ітерацій KDF ≥ 100000", env.iterations >= 100000, "≥100000");
check("розшифровується правильною фразою", SAMPLE_KEY, await core.decryptSecret(env, "пароль-фраза"));
let rejected = false;
try { await core.decryptSecret(env, "не та фраза"); } catch { rejected = true; }
truthy("хибна фраза → відмова (автентифіковане шифрування)", rejected);
truthy("шифротекст не містить ключа у відкритому вигляді", !JSON.stringify(env).includes(SAMPLE_KEY));
truthy("сіль щоразу нова (два конверти різні)",
  (await core.encryptSecret(SAMPLE_KEY, "п")).salt !== (await core.encryptSecret(SAMPLE_KEY, "п")).salt);
truthy("маскування ключів у тексті помилки", core.redactSecrets(`помилка з ${SAMPLE_KEY}`).includes("sk-***"));
truthy("маскований текст не містить ключа", !core.redactSecrets(`помилка з ${SAMPLE_KEY}`).includes(SAMPLE_KEY));

// ═══════ 8. Хмарний запит ═══════
console.log('\n════════ 8. Хмарний запит (побудова) ════════');
const areq = core.buildCloudRequest({ provider: "anthropic", apiKey: "K", messages: [{ role: "user", content: "привіт" }] });
check("Anthropic: правильний endpoint", "https://api.anthropic.com/v1/messages", areq.url);
check("Anthropic: версія API у заголовку", "2023-06-01", areq.headers["anthropic-version"]);
check("Anthropic: заголовок прямого браузерного доступу (інакше CORS)", "true",
  areq.headers["anthropic-dangerous-direct-browser-access"]);
truthy("ключ у заголовку, а НЕ в URL", !areq.url.includes("K") && areq.headers["x-api-key"] === "K");
const oreq = core.buildCloudRequest({ provider: "openai", apiKey: "K2", system: "s", messages: [{ role: "user", content: "hi" }] });
check("OpenAI-сумісний: Bearer-авторизація", "Bearer K2", oreq.headers.authorization);
check("OpenAI-сумісний: system у messages", "system", oreq.body.messages[0].role);
let threw = false;
try { core.buildCloudRequest({ apiKey: "", messages: [] }); } catch { threw = true; }
truthy("порожній ключ → явна помилка, не мовчазний запит", threw);
check("Anthropic: відповідь читається", "текст",
  core.readCloudReply("anthropic", { content: [{ type: "text", text: "текст" }] }));
check("OpenAI: відповідь читається", "текст",
  core.readCloudReply("openai", { choices: [{ message: { content: "текст" } }] }));
check("зіпсована відповідь → порожній рядок, не виняток", "", core.readCloudReply("anthropic", null));

// ═══════ 9. Збірка: dist синхронний з джерелами ═══════
console.log('\n════════ 9. Збірка одного файлу ════════');
const built = build.buildHtml();
const dist = readFileSync(build.DIST_FILE, "utf8");
check("dist/mobile-agent.html збігається з поточними джерелами (перезібрано після правок)",
  true, dist === built.html);
truthy("логіка core.js реально вбудована (не посилання на файл)",
  dist.includes(readFileSync(join(PROJ, "src", "core.js"), "utf8").replace(/^export /gm, "").trimEnd()));
const verJson = JSON.parse(readFileSync(build.VERSION_FILE, "utf8"));
check("version.json збігається з APP_VERSION", core.APP_VERSION, verJson.version);
check("версія у зібраному файлі", true, dist.includes(`APP_VERSION = "${core.APP_VERSION}"`));
truthy("незаповнених маркерів не лишилось", !/__[A-Z0-9_]+__/.test(dist));

// ═══════ 10. PWA-інваріанти зібраного файлу ═══════
console.log('\n════════ 10. PWA-інваріанти ════════');
truthy("манифест вбудовано як data URI", dist.includes('rel="manifest" href="data:application/manifest+json;base64,'));
const manifestB64 = (dist.match(/manifest\+json;base64,([A-Za-z0-9+/=]+)"/) || [])[1];
const manifest = JSON.parse(Buffer.from(manifestB64 || "", "base64").toString("utf8"));
check("манифест: display=standalone (інсталюється)", "standalone", manifest.display);
check("манифест: дві іконки", 2, manifest.icons.length);
truthy("манифест: є maskable-іконка (Android-адаптивна)",
  manifest.icons.some((i) => String(i.purpose).includes("maskable")));
for (const icon of manifest.icons) {
  const png = Buffer.from(icon.src.split(",")[1], "base64");
  const sig = png.subarray(0, 8).toString("hex") === "89504e470d0a1a0a";
  const w = png.readUInt32BE(16), h = png.readUInt32BE(20);
  const expected = parseInt(icon.sizes, 10);
  truthy(`іконка ${icon.sizes}: справжній PNG правильного розміру`, sig && w === expected && h === expected,
    `PNG ${expected}×${expected}`);
}
truthy("service worker реєструється лише на secure origin (HTTPS/localhost)",
  dist.includes('location.protocol === "https:"') && dist.includes("localhost"));
// Регрес 2026-07-24: реєстрація SW з blob:-URL заборонена браузером — має бути
// окремий same-origin файл, а не Blob.
truthy("SW підключається файлом sw.js, а не blob:-URL",
  dist.includes('register("./sw.js")') && !dist.includes("createObjectURL(new Blob([swCode]"));
truthy("відсутній sw.js не ламає застосунок (перевірка HEAD перед реєстрацією)",
  dist.includes('fetch("./sw.js", { method: "HEAD"'));
const swFile = readFileSync(build.SW_FILE, "utf8");
check("dist/sw.js синхронний зі збіркою", true, swFile === built.sw);
check("кеш SW прив'язаний до версії (оновлення чистить старий)", true,
  swFile.includes(`pocket-agent-${core.APP_VERSION}`));
// Перевіряємо не наявність рядка, а ПОВЕДІНКУ: беремо регулярку пропуску з sw.js
// і проганяємо на реальних URL.
const skipSrc = (swFile.match(/const SKIP = \/(.+?)\/;/) || [])[1];
const skipRe = skipSrc ? new RegExp(skipSrc) : null;
truthy("service worker НЕ кешує виклики API", skipRe && skipRe.test("https://api.anthropic.com/v1/messages"));
truthy("service worker НЕ кешує ваги локальної моделі", skipRe && skipRe.test("https://esm.run/@mlc-ai/web-llm"));
truthy("service worker НЕ кешує version.json (інакше оновлення не видно)",
  skipRe && skipRe.test("https://site.example/version.json"));
truthy("service worker кешує саму оболонку застосунку", skipRe && !skipRe.test("https://site.example/index.html"));
truthy("самодостатній: нема зовнішніх <script src>", !/<script[^>]+src=/i.test(dist));
truthy("самодостатній: нема зовнішніх стилів", !/<link[^>]+stylesheet/i.test(dist));
truthy("єдине зовнішнє джерело коду — CDN локальної моделі (ліниво)",
  (dist.match(/https:\/\/(?!api\.anthropic|api\.openai)[a-z0-9.-]+/g) || []).every((u) => u.includes("esm.run")));
truthy("у зібраному файлі нема секретів",
  !/sk-[A-Za-z0-9]{16,}|xai-[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_-]{20,}/.test(dist));
truthy("WebGPU перевіряється перед використанням", dist.includes("navigator.gpu"));
truthy("є мова інтерфейсу uk", dist.includes('<html lang="uk">'));

console.log(`\nTOTALS pass=${PASS} fail=${FAIL}`);
if (FAIL) {
  console.log("Впали:\n" + FAILED.map((f) => "  - " + f).join("\n"));
  process.exit(1);
}
