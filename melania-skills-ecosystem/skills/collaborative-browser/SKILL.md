---
name: collaborative-browser
description: >
  Запускає повноцінний браузерний артефакт Chrome-стилю v2.7.1 де користувач і Claude-агент
  працюють разом у реальному часі. Агент завантажує сторінки через Anthropic API, аналізує
  контент, пропонує дії, генерує застосунки (AI Code Builder), виконує автономний Autopilot-ресерч,
  підтримує мультиплеєр, Secrets Manager (AES-GCM), Firebase Sync, Google Maps, список читання,
  PiP-агент, пошук, split view, нотатки, закладки, командну палітру (Ctrl+K), голосовий ввід,
  safe-action-gate, кеш сторінок, dual-runtime (артефакт/standalone), Autopilot v2, mobile drawer.
  Використовуй цей skill коли: "відкрий браузер", "collaborative browser", "спільний браузер",
  "агент у браузері", "веб-серфінг з агентом", "досліди сайт", "відкрий сторінку", "AI браузер",
  потрібен автономний ресерч у вебі, генерація mini-app, або спільна веб-сесія з агентом. DO NOT use for plain web search without an interactive browser, or backend scraping scripts.
license: Proprietary
metadata:
  version: 3.0.1
  author: Melania (Master Administrator)
  category: browser
  created: 2026-05-27
  last_updated: 2026-07-16
---

# Collaborative Browser Skill v3.0.1
> Українською-перша: весь UI, пояснення й приклади — українською за замовчуванням (артефакт має перемикач 🇺🇦/🇬🇧/🇩🇪/🇫🇷/🇵🇱/🇪🇸); перемикання лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## При активації

1. Скопіюй `browser-artifact.html` → `/mnt/user-data/outputs/collaborative-browser.html`
2. Запусти `present_files` з цим шляхом
3. Стисло поясни: Ctrl+K для команд, адресний рядок для навігації, ⋯ для всіх інструментів

---

## Layout

```
┌── TABS BAR ──────────────────────────────────────────┐
│  [✨ Нова вкладка ×] [+]                              │
├── MULTIPLAYER BAR (якщо активний) ───────────────────┤
│  🟢 Сесія: ABCD1234  👥 [аватари]  [🔗 Поділитись]   │
├── AUTOPILOT BAR (якщо активний) ─────────────────────┤
│  ⚡ Крок 2/5: Аналіз  ████░░  [■ Стоп]               │
├── TOOLBAR ───────────────────────────────────────────┤
│  ← → ↻  [G▾ адресний рядок ▶]  ☆ 🔍 ⚡ ⌘  ⋯  ●AI⚬  │
├── FIND BAR (Ctrl+F) ──────────────────────────────── │
│  [пошук...]  3/12  ↑ ↓  Aa  ✕                        │
├─────────────────────────┬──── AGENT PANEL ───────────┤
│  📊 progress bar        │  🤖 Claude Агент         • │
│                         ├── Чат │ Ресерч │ Нотатки ──┤
│  КОНТЕНТ СТОРІНКИ       │  [Запит агенту...] 🎤  ▶   │
│  (через Anthropic API)  │  📊Аналіз  🔗Посил  📋Дані│
│                         │  🌐Переклад  ✓Факти  💾CSV │
│  🔒 безпека badge       │  ─────────────────────────│
│  посилання клікабельні  │  повідомлення агента       │
│  таблиці → CSV          │  пропозиції з кнопками     │
│  адреси → Maps          │  ─────────────────────────│
│                         │  [лог сесії ▼]             │
├─────────────────────────┴───────────────────────────┤
│  DOWNLOAD BAR (при завантаженні файлів)              │
├── STATUS BAR ────────────────────────────────────────┤
│  Завантажено: ...   🛡 🔖  v3.0.0   Агент: активний    │
└──────────────────────────────────────────────────────┘
[PiP агент — плаваюче перетягуване вікно]
```

---

## Критичні правила — ОБОВ'ЯЗКОВО читати

### ⛔ Три заборони які ламають артефакт

```javascript
// ❌ 1. AbortController в fetch → "AbortSignal object could not be cloned"
// Claude artifacts у sandboxed iframe: fetch() проксується через postMessage().
// AbortSignal не підтримує structured clone → краш при КОЖНОМУ API виклику.
const ctrl = new AbortController();
fetch(url, { signal: ctrl.signal }); // ← ЗАБОРОНЕНО

// ❌ 2. CSP meta тег → блокує всі fetch до api.anthropic.com
// <meta http-equiv="Content-Security-Policy" content="default-src 'self' ...">
// В iframe 'self' = null origin → api.anthropic.com заблокований нашим же CSP

// ❌ 3. isLoading без finally → вічне блокування навігації
S.isLoading = true;
try { ... } catch { S.isLoading = false; } // якщо catch падає → stuck forever
```

### ✅ Правильні замінники

```javascript
// ✅ 1. Timeout через Promise.race (без AbortSignal)
const timeout = new Promise((_,rej) =>
  setTimeout(() => rej(new Error('Timeout 45s')), 45000)
);
const result = await Promise.race([
  fetch(API_URL, { method:'POST', headers, body }), // ← без signal:
  timeout
]);

// ✅ 2. Без CSP meta — платформа Claude.ai вже забезпечує sandbox

// ✅ 3. isLoading завжди через finally
async function loadPage(url) {
  if (S.isLoading) return;
  S.isLoading = true;
  try {
    const data = await agentFetch(url);
    // ... обробка
  } catch(err) {
    // ... відображення помилки
  } finally {
    S.isLoading = false;  // ЗАВЖДИ виконується
    hideLoading();
  }
}
```

---

## API виклики

```javascript
const API_URL = 'https://api.anthropic.com/v1/messages';
const MODEL   = 'claude-sonnet-4-6'; // v3: перекривається Runtime.model() з налаштувань

async function callApi(system, userContent, maxTokens=1000, useSearch=true) {
  const body = {
    model: MODEL,
    max_tokens: maxTokens,
    system,
    messages: [{ role:'user', content: String(userContent).substring(0, 4000) }]
  };
  if (useSearch) body.tools = [{ type:'web_search_20250305', name:'web_search' }];

  const timeout = new Promise((_,rej) =>
    setTimeout(() => rej(new Error('Timeout 45s')), 45000)
  );
  const req = fetch(API_URL, {
    method:'POST',
    headers: { 'Content-Type':'application/json' },
    body: JSON.stringify(body)
    // НЕ додавати signal: — AbortSignal не серіалізується через postMessage
  }).then(async r => {
    if (!r.ok) throw new Error(`API ${r.status}`);
    const d = await r.json();
    return (d.content||[]).filter(b=>b.type==='text').map(b=>b.text).join('');
  });
  return Promise.race([req, timeout]);
}
```

---

## Парсинг JSON відповідей (safeJson — 3 стратегії)

Модель іноді повертає текст + JSON. Fragile `indexOf('{')` ламається.

```javascript
function safeJson(str, fallback={}) {
  const raw = String(str);
  // Стратегія 1: видалити markdown fences → прямий parse
  try { return JSON.parse(raw.replace(/```json\s*/gi,'').replace(/```\s*/g,'').trim()); } catch {}
  // Стратегія 2: знайти збалансований {} блок
  try {
    let depth=0, start=-1;
    for (let i=0; i<raw.length; i++) {
      if (raw[i]==='{') { if(depth===0) start=i; depth++; }
      else if (raw[i]==='}') {
        depth--;
        if (depth===0 && start>=0) {
          try { return JSON.parse(raw.slice(start, i+1)); } catch {}
          start=-1;
        }
      }
    }
  } catch {}
  // Стратегія 3: regex всіх {...} блоків
  const blocks = raw.match(/\{[^{}]{10,}(?:\{[^{}]*\}[^{}]*)*\}/g) || [];
  for (const b of blocks) { try { return JSON.parse(b); } catch {} }
  return fallback;
}
```

---

## Auth-wall детектор

Перед API викликом перевіряє чи сайт потребує авторизації.
При auth-wall → показує інформативну сторінку з альтернативами.

```javascript
const AUTH_WALL_DOMAINS = [
  'notebooklm.google.com','mail.google.com','drive.google.com','docs.google.com',
  'notion.so','figma.com','miro.com','airtable.com','slack.com','discord.com',
  'twitter.com/i/','x.com/i/','instagram.com','netflix.com','spotify.com', ...
];

function detectPageType(url) {
  try {
    const host = new URL(url).hostname + new URL(url).pathname;
    if (AUTH_WALL_DOMAINS.some(d => host.includes(d))) return 'authwall';
  } catch {}
  return 'normal';
}

// agentFetch повертає без API виклику:
if (detectPageType(url) === 'authwall') return {
  authWall: true, authDomain: hostname,
  suggestion: `${domain} потребує авторизації`
};
```

---

## addMsg — правильний рендер

```javascript
function addMsg(content, type='', trustedHtml=false) {
  const d = document.createElement('div');
  d.className = 'msg' + (type?' '+type:'');
  // Автодетекція: якщо є HTML теги — рендерити як HTML (після санітизації)
  const hasHtml = /<[a-z][^>]*>/i.test(String(content));
  if (trustedHtml || hasHtml) {
    d.innerHTML = _sanitizeMsgHtml(String(content)); // whitelist тегів
  } else {
    d.textContent = String(content); // безпечно для plain text
  }
  container.appendChild(d);
  container.scrollTop = container.scrollHeight;
}
```

---

## Toolbar — overflow pattern

Максимум 7-8 видимих кнопок. Решта в dropdown `⋯`.

```html
<!-- Primary: nav + address + 4 key actions + overflow + toggle -->
<button id="btnBack">←</button>
<button id="btnFwd">→</button>
<button id="btnRefresh">↻</button>
<div class="address-bar">
  <button id="seBtn">G▾</button> <!-- пошуковик -->
  <input id="addressInput" ...>
  <button onclick="navigateFromBar()">▶</button>
</div>
<button id="btnBookmark">☆</button>
<button id="btnFind">🔍</button>
<button id="btnBuilder">⚡</button>
<button onclick="openCmd()">⌘</button>

<!-- Overflow: ВСІ вторинні інструменти -->
<div style="position:relative">
  <button id="overflowBtn" onclick="toggleOverflow()">⋯</button>
  <div class="overflow-dropdown" id="overflowMenu">
    <!-- Reader, Reading List, Split, PiP, Autopilot,
         Secrets, Multiplayer, Firebase, Settings, Audit -->
  </div>
</div>

<div class="agent-wrap">
  <label>AI <toggle /></label>
</div>
```

---

## Builder iframe — sandbox

```javascript
// ✅ Правильно: allow-scripts, allow-forms — але НЕ allow-same-origin
const iframe = document.createElement('iframe');
iframe.sandbox = 'allow-scripts allow-forms';
// Без allow-same-origin → генерований код ізольований від батьківського документа

// ✅ Відкрити в новій вкладці браузера:
iframe.contentDocument.open();
iframe.contentDocument.write(generatedHtml);
iframe.contentDocument.close();
```

---

## Модулі (повний список)

| Модуль | Тип | Призначення |
|--------|-----|-------------|
| `Security` | IIFE | XSS, URL validation, sanitization, safeJson |
| `Crypto` | IIFE | AES-GCM шифрування для Secrets |
| `SecretsManager` | IIFE | Зберігання API ключів (localStorage encrypted) || `MP` | IIFE | Мультиплеєр через BroadcastChannel |
| `FirebaseSync` | IIFE | Синхронізація між пристроями |
| `Maps` | IIFE | Детекція адрес + embed Google Maps |
| `Animations` | IIFE | skeleton, pageIn, ripple |
| `ReadingList` | IIFE | Список читання + прогрес |
| `PiP` | IIFE | Плаваюча панель агента (drag) |
| `Builder` | IIFE | AI Code Builder (generate/improve/deploy) |
| `Autopilot` | IIFE | Автономний multi-step ресерч |
| `Monitor` | IIFE | Детекція змін сторінки між візитами |
| `SE` | object | Пошуковик (Google/Bing/DDG/Brave/Perplexity/You) |
| `Runtime` | IIFE | **v3**: dual-mode (артефакт/standalone), headers, feature-matrix, auth-fallback |
| `Gate` | IIFE | **v3**: класифікатор збоїв + jittered backoff + verify-after-action |
| `PageCache` | IIFE | **v3**: кеш сторінок TTL 10хв, LRU 30 (назад/вперед без API) |
| `AppLibrary` | IIFE | **v3**: збережені застосунки Builder (localStorage) |

---

> 🔗 **Канонічні auth-патерни** (cookie-інʼєкція, OAuth, моніторинг сесій, AES-GCM-сховище) консолідовано у скілі **`auth-session-manager`**. Модулі `Crypto`/`SecretsManager` нижче — браузер-специфіка; за загальною логікою авторизації звертайся туди.

## Keyboard shortcuts

| Shortcut | Дія |
|----------|-----|
| Ctrl+K | Командна палітра |
| Ctrl+F | Пошук по сторінці |
| Ctrl+D | Закладка |
| Ctrl+T | Нова вкладка |
| Ctrl+W | Закрити вкладку |
| Ctrl+L | Фокус адресного рядка |
| Ctrl+R | Оновити |
| Ctrl+Shift+R | Reader mode |
| Ctrl+Shift+B | Закладки |
| Ctrl+H | Історія |
| Ctrl+Shift+A | Autopilot |
| Ctrl+Shift+E | AI Code Builder |
| Ctrl+Shift+L | Reading List |
| Ctrl+= / Ctrl+- | Zoom |
| Alt+← / Alt+→ | Назад/Вперед |
| F5 | Оновити |

---

## Персистентність

```javascript
// window.storage (Claude artifacts API) — основне
await window.storage?.set('cb-state', JSON.stringify({
  bookmarks, historyItems, notes, agentMemory, sessionLearnings, settings
}));

// localStorage — для Secrets і Reading List (не через window.storage)
localStorage.setItem('cb-secrets-v1', JSON.stringify(encryptedList));
localStorage.setItem('cb-rl-v1', JSON.stringify(readingList));

// Sandbox mode: відключає всі збереження
if (S.settings.sandbox) return; // в persistSave()
```

---

## Відомі обмеження

| Тип | Статус |
|-----|--------|
| Wikipedia, BBC, GitHub, arXiv, HN | ✅ Працює |
| Google, Bing пошук | ✅ Працює |
| Auth-wall сайти (NotebookLM, Gmail...) | 🔒 Показує інфо + альтернативи |
| React/Vue SPA без SSR | ⚠️ Частковий контент |
| Captcha-захищені сайти | ❌ Недоступно |
| Firebase sync | 🔧 Потребує Firebase config |
| Мультиплеєр cross-device | 🔧 Потребує Firebase config |
| Мультиплеєр same-device | ✅ BroadcastChannel |

---

## Чеклист деплою

**Security:**
- [ ] Немає `<meta Content-Security-Policy>` в HTML
- [ ] Немає `AbortController` / `signal:` в fetch
- [ ] `S.isLoading = false` в `finally` блоці
- [ ] `Security.escHtml()` на всіх зовнішніх даних
- [ ] `_sanitizeMsgHtml()` на HTML від агента
- [ ] `Security.validateUrl()` перед navigate
- [ ] Builder iframe без `allow-same-origin`
- [ ] `'use strict'` на початку JS

**UX:**
- [ ] Toolbar не переповнений (≤8 кнопок видимо)
- [ ] Overflow menu містить решту інструментів
- [ ] Auth-wall → інформативна сторінка (не помилка)
- [ ] Мережева помилка → зрозуміле повідомлення
- [ ] Dark mode: всі елементи читабельні

**Функціональність:**
- [ ] Навігація: Enter в адресному рядку → loadPage
- [ ] Агент відповідає на запити в чаті
- [ ] Ctrl+K відкриває палітру
- [ ] Quick-links на новій вкладці клікабельні

---

Версія: **v3.0.0** | ~238KB | ~4321 рядків | Модель: claude-sonnet-4-6 (перекривається в налаштуваннях)

---


---

## Autopilot Research — Покращені Патерни

При дослідженні теми агентом:

```
Команда: "Дослідж тему X — зберери 5 джерел, підсумуй ключові факти"

Autopilot flow:
1. search(X) → топ 10 результатів
2. fetch(url1), fetch(url2)... паралельно (max 3 одночасно)
3. extract_key_facts(page_content) для кожного
4. synthesize(facts[]) → структурований звіт
5. validate(report) через validation-mesh

Ліміти: max 20 сторінок / сесія; max 5 рівнів глибини
```

---

## Генерація UI (дизайн)
Для артефактів/міні-застосунків з AI Code Builder:
- Сміливий цілісний напрям, не дефолтний шаблон; спирайся на наявний дизайн-скіл, якщо є.
- **Без placeholder'ів/«доробимо потім»** — повний робочий вивід.
- Уникай generic дефолтних шрифтів — обирай свідомо під задачу.

## 📎 Advanced Patterns (v4)

Read `references/agent-patterns.md` WHEN you need: autonomous research loop, multi-tab coordination, AI code builder, screenshot analysis.
Load only on demand — not proactively.

---

## Зміни
- **v3.0.1** (2026-07-16) — Security-фікс (повний аудит екосистеми): з `browser-artifact.html` прибрано захардкоджений Google Maps API-ключ у `Maps.embedUrl()` (мертвий шлях `renderEmbed`; живий шлях `showMapEmbed` уже був безключовим `output=embed`) — embedUrl переведено на той самий безключовий варіант; ключ Embed API v1 за потреби — лише з SecretsManager (`google-maps-api-key`). Функціональність не змінена. Лише артефакт; SKILL.md — тільки цей запис і bump.
- **v3.0.0** (2026-07-03) — «Maximum Power». **Фаза 0** ремонт цілісності: версію синхронізовано всюди (title/footer/UI/frontmatter з v2.5.1/v2.3 → v3.0.0), модель у коді → `claude-sonnet-4-6`; виправлено 3 латентні синтакс-баги (незаекрановані апострофи `з'єднання`, вкладені лапки `sendCmd`) з v2.7.1. **Фаза 1** safe-action-gate: `Gate` (класифікатор 429/401/5xx/timeout/network/contract + jittered backoff ≤3 + verify-after-action на JSON-контрактах), `PageCache` (TTL 10хв). **Фаза 2** Autopilot v2: динамічні підтеми (depth≤5), бюджетний губернатор (стеля → чесний частковий звіт, Принцип #0), пауза, звіт з джерелами+впевненістю, експорт .md. **Фаза 3** Builder v2: `AppLibrary` (save/open/delete). **Фаза 4** `Runtime` dual-mode (артефакт/standalone з власним ключем через Secrets `ANTHROPIC_API_KEY`/auto-fallback при 401), матриця середовища, експорт/імпорт профілю (merge-not-replace). **Фаза 5** mobile-first: агент-панель → нижній drawer ≤768px. Верифіковано: Playwright smoke 37/37, регресія 22/22 функцій, 88/88 HTML-обробників, deploy-чеклист 15/15, JS-синтаксис чистий. Merge-not-replace: усі 13 модулів v2.7.1 збережено. **Evals**: відновлено 4 кейси з ZIP-екосистеми (source-копії губилися між сесіями) + додано 4 нові під v3 (safe-action-gate-backoff, dual-runtime-standalone, page-cache-no-refetch, builder-app-library) = 8 кейсів, схема v3.0.0.
- **v2.7.2** (2026-06-26) — Stage 3: **S-1** застарілий рядок моделі (`claude-sonnet-4-20250514`→`claude-sonnet-4-6`; хардкод лишається — легітимний для artifact-API). **S-4** внутрішню версію в тілі (заголовок/опис/футер/UI) синхронізовано з frontmatter (v2.5→v2.7.1; changelog v2.5.0 збережено). **S-3** +власні `evals/` (5). Корекція + додавання.
- **v2.7.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v2.5.0** (2026-06-02) — додано `metadata`/`license`-frontmatter, явну директиву «українською-перша», власні `evals/` (5). Хардкод моделі sonnet лишено (легітимний для artifact-API). _(аудит Кластер 3: P9 + Core Rule 4)_

- **v2.6.0** (2026-06-02) — Pre-Update Preservation Protocol; agent-patterns reference (autonomous research, multi-tab, code builder).
- **v2.7.0** (2026-06-10) — Фаза 5: I-10: правило генерації UI для AI Code Builder (без placeholder'ів/generic дефолтних шрифтів).
