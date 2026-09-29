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
// Регрес 2026-07-24 (спіймано власним падінням у CI): відсутній файл давав сирий
// ENOENT і вбивав увесь прогін разом з рештою перевірок. Тепер — керована відмова.
function readOrFail(path, name) {
  try {
    return readFileSync(path, "utf8");
  } catch (e) {
    bad(name, `файл ${path} існує`, e.code || String(e));
    return null;
  }
}

const built = build.buildHtml();
const dist = readOrFail(build.DIST_FILE, "dist/mobile-agent.html присутній у репозиторії");
if (dist === null) {
  console.log("  ⚠️  зібраного файлу нема — перевірки збірки й PWA пропущено (запусти build.mjs)");
  console.log(`\nTOTALS pass=${PASS} fail=${FAIL}`);
  console.log("Впали:\n" + FAILED.map((f) => "  - " + f).join("\n"));
  process.exit(1);
}
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
const swFile = readOrFail(build.SW_FILE, "dist/sw.js присутній у репозиторії") ?? "";
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

// ═══════ 11. Резервний контур: класифікація збою ═══════
console.log('\n════════ 11. Резервний контур: класифікація збою ════════');
const cf = core.classifyFailure;
check("429 → ліміт, повторюваний", "rate-limit", cf({ status: 429 }).kind);
check("429 → перемкнути провайдера", true, cf({ status: 429 }).switchProvider);
check("503 → тимчасовий, повторюваний", true, cf({ status: 503 }).retryable);
check("500 → повторюваний", true, cf({ status: 500 }).retryable);
check("401 → повтор марний", false, cf({ status: 401 }).retryable);
check("401 → але інший провайдер варто спробувати", true, cf({ status: 401 }).switchProvider);
check("400 → фатально, нікуди не перемикати", false, cf({ status: 400 }).switchProvider);
check("нема мережі → повторюваний", "offline", cf({ offline: true }).kind);
check("«Failed to fetch» без статусу → нема мережі", "offline", cf({ message: "TypeError: Failed to fetch" }).kind);
check("rate limit у тексті без статусу", "rate-limit", cf({ message: "Error: rate limit exceeded" }).kind);
check("Retry-After у секундах", 30000, cf({ status: 429, retryAfter: "30" }).retryAfterMs);
check("Retry-After сміття → null", null, cf({ status: 429, retryAfter: "скоро" }).retryAfterMs);
check("Retry-After як HTTP-дата", 5000,
  core.parseRetryAfter(new Date(Date.parse("2026-01-01T00:00:05Z")).toUTCString(), Date.parse("2026-01-01T00:00:00Z")));

// ═══════ 12. Пауза між спробами ═══════
console.log('\n════════ 12. Пауза між спробами (backoff + джитер) ════════');
const half = () => 0.5;
check("перша спроба ≈ базова", 750, core.nextBackoffMs(1, { baseMs: 1000, rand: half }));
check("зростає експоненційно", 1500, core.nextBackoffMs(2, { baseMs: 1000, rand: half }));
check("обмежена стелею", 45000, core.nextBackoffMs(10, { baseMs: 1000, capMs: 60000, rand: half }));
truthy("джитер розводить клієнтів (rand=0 і rand=1 дають різне)",
  core.nextBackoffMs(3, { baseMs: 1000, rand: () => 0 }) !== core.nextBackoffMs(3, { baseMs: 1000, rand: () => 1 }));
truthy("пауза ніколи не менша за половину експоненти",
  core.nextBackoffMs(3, { baseMs: 1000, rand: () => 0 }) >= 2000);
check("Retry-After має пріоритет над формулою", 7000, core.nextBackoffMs(1, { retryAfterMs: 7000, rand: half }));
check("Retry-After теж обмежений стелею", 60000, core.nextBackoffMs(1, { retryAfterMs: 999999, rand: half }));

// ═══════ 13. Ланцюг провайдерів ═══════
console.log('\n════════ 13. Ланцюг провайдерів і cooldown ════════');
const chain = core.defaultChain({ backupProvider: "openai" });
check("ланцюг: хмара → запасна → локальна → офлайн", "cloud,cloud-backup,local,offline", chain.map((n) => n.id).join(","));
const capsAll = { online: true, hasCloudKey: true, hasBackupKey: true, localReady: true };
check("за нормальних умов — основна хмара", "cloud", core.pickProvider(chain, { caps: capsAll }).id);
check("основна в cooldown → запасна", "cloud-backup",
  core.pickProvider(chain, { caps: capsAll, now: 1000, health: { cloud: { cooldownUntil: 9999 } } }).id);
check("обидві хмари в cooldown → локальна", "local",
  core.pickProvider(chain, { caps: capsAll, now: 1000, health: { cloud: { cooldownUntil: 9999 }, "cloud-backup": { cooldownUntil: 9999 } } }).id);
check("нема мережі → одразу локальна", "local", core.pickProvider(chain, { caps: { ...capsAll, online: false } }).id);
// Регрес на дефект, спійманий браузерним прогоном 2026-09-28: офлайн «з'їдав»
// завдання після першого ж 429, і затримка знову ставала втратою відповіді.
check("офлайн НЕ береться, поки лишається шанс на справжню відповідь", null,
  core.pickProvider(chain, { caps: { online: true, hasCloudKey: false, hasBackupKey: false, localReady: false } }));
check("офлайн береться, коли його явно дозволено (остання спроба)", "offline",
  core.pickProvider(chain, { allowOffline: true, caps: { online: true, hasCloudKey: false, hasBackupKey: false, localReady: false } }).id);
check("усі справжні вузли в паузі → чекаємо, а не деградуємо", null,
  core.pickProvider(chain, { caps: capsAll, now: 1000,
    health: { cloud: { cooldownUntil: 9999 }, "cloud-backup": { cooldownUntil: 9999 }, local: { cooldownUntil: 9999 } } }));
check("вузол, який уже пробували в цьому проході, пропускається", "cloud-backup",
  core.pickProvider(chain, { caps: capsAll, tried: ["cloud"] }).id);
const h1 = core.markFailure({}, "cloud", { now: 1000, kind: "rate-limit" });
truthy("невдача ставить вузол на паузу", h1.cloud.cooldownUntil > 1000);
const h2 = core.markFailure(h1, "cloud", { now: 1000 });
truthy("друга поспіль невдача подовжує паузу", h2.cloud.cooldownUntil > h1.cloud.cooldownUntil);
check("успіх стирає історію вузла", undefined, core.markSuccess(h2, "cloud").cloud);
check("Retry-After керує паузою вузла", 1000 + 30000,
  core.markFailure({}, "cloud", { now: 1000, retryAfterMs: 30000 }).cloud.cooldownUntil);

// ═══════ 14. Черга завдань ═══════
console.log('\n════════ 14. Черга завдань (падіння = затримка, не втрата) ════════');
const t1 = core.makeTask({ input: "перше завдання", now: 1000, id: "a" });
check("нове завдання одразу готове до виконання", "pending", t1.status);
check("готове зараз, не потім", 1000, t1.nextAttemptAt);
let q = [t1, core.makeTask({ input: "друге", now: 2000, id: "b" })];
check("першим береться найстаріше", "a", core.nextRunnable(q, 3000).id);
check("час іще не настав → нічого не беремо", null, core.nextRunnable([{ ...t1, nextAttemptAt: 9999 }], 1000));
const fail429 = { retryable: true, switchProvider: true, kind: "rate-limit", retryAfterMs: 5000 };
q = core.applyOutcome(q, "a", { ok: false, failure: fail429, engine: "cloud", error: "429" }, { now: 3000 });
const a1 = q.find((x) => x.id === "a");
check("після збою завдання ЛИШАЄТЬСЯ в черзі", "pending", a1.status);
check("лічильник спроб зріс", 1, a1.attempts);
check("наступна спроба відсунута на Retry-After", 8000, a1.nextAttemptAt);
check("провайдер, що впав, занотований у цьому проході", "cloud", a1.tried.join(","));
// Другий регрес того ж дефекту: постійний «чорний список» назавжди відрізав
// найкращого провайдера через одну тимчасову помилку.
check("список спробуваних — журнал ОСТАННЬОГО проходу, не вічний чорний список", "cloud-backup",
  core.applyOutcome([{ ...t1, tried: ["cloud"], attempts: 1 }], "a",
    { ok: false, failure: fail429, engine: "cloud-backup" }, { now: 3000 })[0].tried.join(","));
truthy("список спробуваних не росте нескінченно між раундами",
  core.applyOutcome([{ ...t1, tried: ["cloud", "cloud-backup", "local"], attempts: 2 }], "a",
    { ok: false, failure: fail429, engine: "cloud" }, { now: 3000 })[0].tried.length === 1);
q = core.applyOutcome(q, "a", { ok: true, answer: "готово", engine: "local" }, { now: 9000 });
check("успіх закриває завдання", "done", q.find((x) => x.id === "a").status);
check("відповідь збережена", "готово", q.find((x) => x.id === "a").answer);
let q2 = [core.makeTask({ input: "впаде", now: 0, id: "c" })];
for (let i = 0; i < 5; i++) q2 = core.applyOutcome(q2, "c", { ok: false, failure: fail429, engine: "cloud" }, { now: 0, maxAttempts: 3 });
check("вичерпані спроби → failed, а не тихе зникнення", "failed", q2[0].status);
truthy("failed-завдання лишається в черзі видимим", q2.length === 1);
check("фатальний збій не повторюється марно", "failed",
  core.applyOutcome([core.makeTask({ input: "x", now: 0, id: "d" })], "d",
    { ok: false, failure: { retryable: false, kind: "fatal" } }, { now: 0 })[0].status);
check("ручний повтор повертає failed у роботу", "pending", core.requeue(q2, "c", 100)[0].status);
check("ручний повтор скидає лічильник спроб", 0, core.requeue(q2, "c", 100)[0].attempts);
check("applyOutcome не мутує вхідну чергу", "pending", [core.makeTask({ input: "x", now: 0, id: "e" })]
  .map((x) => { core.applyOutcome([x], "e", { ok: true, answer: "1" }, { now: 1 }); return x.status; })[0]);
check("prune прибирає завершені", 0, core.pruneQueue([{ id: "z", status: "done", finishedAt: 1 }]).length);
check("prune не чіпає активні", 1, core.pruneQueue([{ id: "z", status: "pending" }]).length);

// ═══════ 15. Сповіщення про стан ═══════
console.log('\n════════ 15. Сповіщення про стан черги ════════');
const sEmpty = core.queueSummary([], 1000);
check("порожня черга → нічого не кричить", "", sEmpty.text);
check("порожня черга не потребує уваги", false, sEmpty.needsAttention);
const sWait = core.queueSummary([{ status: "pending", nextAttemptAt: 6000 }], 1000);
truthy("черга з паузою показує, скільки чекати", sWait.text.includes("5 с"));
const sFail = core.queueSummary([{ status: "failed" }], 1000);
check("збій вимагає уваги", true, sFail.needsAttention);
truthy("текст збою прямо каже про ручний повтор", sFail.text.includes("ручний повтор"));
check("збій має пріоритет над очікуванням у тексті", true,
  core.queueSummary([{ status: "failed" }, { status: "pending", nextAttemptAt: 9000 }], 1000).text.includes("не вдалося"));

console.log(`\nTOTALS pass=${PASS} fail=${FAIL}`);
if (FAIL) {
  console.log("Впали:\n" + FAILED.map((f) => "  - " + f).join("\n"));
  process.exit(1);
}
