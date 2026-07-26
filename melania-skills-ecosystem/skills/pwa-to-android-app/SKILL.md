---
name: pwa-to-android-app
description: "Ship a single-file HTML/JS app as an installable PWA, then path to a real Android APK. Covers self-contained inlining (manifest as data URI, icons as base64), why offline needs a same-origin sw.js (blob: registration is rejected), the content:// vs HTTPS limitation (mic/WebGPU need HTTPS), Netlify Drop for testing, one-button auto-update via version.json, and cloud APK builds via GitHub Actions when no PC is available. ALWAYS use when packaging a web app for phone install, making a PWA, building an APK, enabling auto-updates, or the user says: зробити аплікацію, інсталювати на смартфон, PWA, APK, авто-оновлення однією кнопкою, мікрофон не працює, content:// не працює, зібрати APK на телефоні, single file, self-contained HTML, Netlify, GitHub Actions build. Also triggers for: add to home screen, service worker, installable app, Capacitor, cloud build. DO NOT use for pure backend services, desktop-only apps, or iOS-native development."
license: Proprietary
metadata:
  version: 1.4.0
  author: Melania (Master Administrator)
  category: packaging
  created: 2026-06-02
  last_updated: 2026-07-25
---

# PWA → Android App — v1.4.0
> Напрацьовано на AI Gateway. Шлях від single-file HTML до інсталюваної аплікації з авто-оновленнями, включно зі збіркою APK повністю з Android-телефону (без ПК).
> Українською-перша: пояснення й приклади — українською за замовчуванням; код та технічні ідентифікатори лишаються англійською. Перемикання мови лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Core Rule
Мікрофон, WebGPU, камера працюють ТІЛЬКИ в secure context (HTTPS/localhost). `content://` та `file://` їх блокують — це обмеження браузера, не упаковки. Перший крок до робочого застосунку = HTTPS-хостинг (Netlify Drop), не Termux-сервер.

---

## Critical Facts (часта плутанина)
- **Проблема мікрофона ≠ упаковка.** Це secure-context. Netlify Drop (drag, миттєвий HTTPS, без акаунта) вирішує одразу.
- **Service worker НЕ вбудовується в один файл.** `blob:`/`data:`-URL для реєстрації SW браузер відхиляє → офлайн вимагає окремого same-origin `sw.js` (див. Pattern 1). Без нього застосунок усе одно ставиться й працює — просто без офлайн-кешу.
- **Android Studio НЕ існує для Android.** Збірка APK на самому телефоні — тільки через Termux (важко) або **хмару (GitHub Actions, реально)**.
- **PWABuilder** (TWA) — найлегший APK, але мікрофон тільки через Chrome, ламається на не-Google пристроях. **Capacitor** надійніше (нативний доступ), але потребує збірки.
- **Код браузерного JS завжди видно** (View Source). Реальний захист логіки = серверна частина, не клієнт. Мініфікація ускладнює, але не приховує.
- **Netlify free**: 100GB трафіку/міс; приватність через невгадуваний URL. **GitHub Pages free** = публічний репо (приватний тільки Pro).

---

## Pattern 1 — Self-contained single file (для роздачі)

Вбудувати все в один HTML щоб роздавати одним файлом:

```python
import base64, json
# manifest як data URI
mdu = "data:application/manifest+json;base64," + base64.b64encode(json.dumps(manifest).encode()).decode()
html = html.replace('<link rel="manifest" href="manifest.json"/>', f'<link rel="manifest" href="{mdu}"/>')
# icons як base64
html = html.replace('href="icon-192.png"', f'href="data:image/png;base64,{b64("icon-192.png")}"')
```

**⚠️ Межа «одного файлу»: service worker вбудувати НЕ можна.** Реєстрація SW із
`blob:`-URL (як і з `data:`) браузером **відхиляється**: `The URL protocol of the script
('blob:…') is not supported` (перевірено браузерним прогоном 2026-07-24, Chromium).
Скрипт SW має бути **same-origin файлом**. Отже «повністю один файл» і справжній офлайн —
несумісні: обирай свідомо.

```javascript
// Роздача теки (є офлайн): sw.js лежить поруч; один файл — просто без офлайн-кешу.
const secureOrigin = location.protocol==="https:" || ["localhost","127.0.0.1"].includes(location.hostname);
if("serviceWorker" in navigator && secureOrigin){
  const probe = await fetch("./sw.js",{method:"HEAD",cache:"no-store"});   // нема — не помилка
  if(probe.ok){
    await navigator.serviceWorker.register("./sw.js");
    await navigator.serviceWorker.ready;
    // Інакше сторінка потрапить у кеш лише з ДРУГОГО відкриття:
    // перше завантаження відбувається до того, як SW почав контролювати клієнта.
    (await caches.open(`app-${APP_VERSION}`)).add(location.href).catch(()=>{});
  }
}
```
> SW не повинен кешувати API-виклики (/v1/, api., localhost, esm.run) і `version.json`
> (інакше оновлення не буде видно) — тільки app shell.

## Pattern 2 — One-button auto-update (як професійні сервіси)

```javascript
const APP_VERSION="9.4.0";
const UpdateChecker={
  getUrl(){return localStorage.getItem("updateUrl")||"";}, // Netlify/GitHub version.json
  isNewer(a,b){const pa=a.split(".").map(Number),pb=b.split(".").map(Number);
    for(let i=0;i<3;i++){if((pa[i]||0)>(pb[i]||0))return true;if((pa[i]||0)<(pb[i]||0))return false;}return false;},
  async check(){const u=this.getUrl();if(!u)return{available:false};
    const d=await(await fetch(u+"?t="+Date.now(),{cache:"no-store"})).json();
    return{available:this.isNewer(d.version,APP_VERSION),latest:d.version,notes:d.notes};},
  async apply(){ // очистити SW кеші + hard reload
    if("caches"in window){const k=await caches.keys();await Promise.all(k.map(x=>caches.delete(x)));}
    location.reload(true);},
};
// При старті: check() → банер "Доступне оновлення" → кнопка → apply()
```
`version.json`: `{"version":"9.5.0","notes":"що нового","url":"..."}`
> Робочий процес оновлення: змінив файл на Netlify + бампнув version.json → у всіх банер → одна кнопка.

## Pattern 3 — Шлях до APK (вибір за можливостями)

| Можливість користувача | Рекомендований шлях |
|------------------------|---------------------|
| Має ПК | Capacitor + Android Studio локально |
| Тільки телефон, є GitHub | **GitHub Actions хмарна збірка** (код у репо → Actions збирає APK → качаєш) |
| Тільки телефон, без хмари | Termux + JDK + Android SDK CLI + Gradle (важко, повільно, але локально) |
| Не готовий до APK | PWA "Додати на головний екран" (працює зараз) |

**GitHub Actions** = єдиний реальний шлях зібрати APK повністю з телефону: пишеш код у браузері → push у репо → workflow збирає → завантажуєш готовий .apk.

---

## Behavior

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| Мікрофон не працює на content:// | пояснити secure-context, направити на Netlify Drop | радити Termux-сервер як перше рішення |
| Користувач хоче APK на телефоні | GitHub Actions хмарна збірка | обіцяти Android Studio на телефоні |
| Роздати одним файлом | inline manifest+icons; сказати, що офлайну не буде без `sw.js` | обіцяти офлайн з вбудованим blob-SW |
| Потрібен офлайн | віддавати теку: HTML + `sw.js` поруч (same-origin) | вбудовувати SW у blob/data-URL — браузер відхилить |
| Авто-оновлення | version.json + one-button apply | вимагати ручного перевстановлення |
| Питання захисту коду | чесно: клієнт видно, секрет на сервері | обіцяти повний захист мініфікацією |
| Тестування зараз | PWA на Netlify (швидкі оновлення) | блокувати на APK перед тестом |

---

## Генерація UI (дизайн)
При генерації інтерфейсу застосунку:
- Обери **сміливий, цілісний напрям** (не дефолтний шаблон); спирайся на наявний дизайн-скіл, якщо є.
- **Без заглушок/placeholder'ів** і «доробимо потім» — повний робочий вивід.
- Уникай generic дефолтних шрифтів — обирай свідомо під задачу.

## Deployment quickstart (для користувача)
1. Перетягнути файл(и) на **app.netlify.com/drop** → миттєвий HTTPS
2. Відкрити посилання в Chrome → меню ⋮ → «Додати на головний екран»
3. Мікрофон/WebGPU/встановлення працюють
4. Оновлення: перетягнув новий файл + version.json → у всіх одна кнопка

## Coordinates with
- `browser-local-ai-webllm` — WebGPU запрацює після HTTPS
- `surgical-code-refactoring` — інтеграція inline-збірки в білд-процес
- `n8n-orchestrator` / `multi-provider-ai-orchestration` — фічі що пакуються в застосунок

---

---

## Share Target API — Отримання файлів з Android Share

```json
// manifest.json
{
  "share_target": {
    "action": "/share",
    "method": "POST",
    "enctype": "multipart/form-data",
    "params": {
      "title": "title",
      "text": "text",
      "url": "url",
      "files": [{"name": "media", "accept": ["image/*", ".pdf"]}]
    }
  }
}
```

```javascript
// /share route у Service Worker
self.addEventListener('fetch', event => {
  if (event.request.url.endsWith('/share') && event.request.method === 'POST') {
    event.respondWith((async () => {
      const data = await event.request.formData();
      const files = data.getAll('media');
      // обробка файлів...
      return Response.redirect('/?shared=1', 303);
    })());
  }
});
```

---

## Web Push Notifications

```javascript
// Реєстрація
const reg = await navigator.serviceWorker.ready;
const sub = await reg.pushManager.subscribe({
  userVisibleOnly: true,
  applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
});
// Відправ sub на сервер → збережи → push звідти

// У SW — отримання
self.addEventListener('push', e => {
  const data = e.data?.json() ?? {};
  e.waitUntil(self.registration.showNotification(data.title, {
    body: data.body, icon: '/icon-192.png', badge: '/badge-72.png'
  }));
});
```

---

## Background Sync — Офлайн Черга

```javascript
// Черга дій поки офлайн
async function queueAction(action) {
  const db = await openDB(); // IndexedDB
  await db.put('sync-queue', { id: Date.now(), action });
  if ('SyncManager' in window) {
    await navigator.serviceWorker.ready.then(r => r.sync.register('action-queue'));
  }
}
// SW обробляє при відновленні зʼєднання
self.addEventListener('sync', e => {
  if (e.tag === 'action-queue') e.waitUntil(flushQueue());
});
```

---

## 📎 Advanced Patterns (v4)

Read `references/play-store.md` WHEN you need: TWA, Bubblewrap APK, Digital Asset Links, app signing, Play submission, Capacitor, iOS limits.
Load only on demand — not proactively.

---

## Зміни
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (артефакт злиттів). Усі записи збережено; нумерацію НЕ переписано без верифікації джерел._
- **v1.4.0** (2026-07-25) — **Виправлено Pattern 1: реєстрація SW із `blob:`-URL браузером відхиляється** (`The URL protocol of the script ('blob:…') is not supported`) — попередній фрагмент не працював. Джерело: реальний браузерний прогін (Chromium, емуляція Pixel 7) у `projects/mobile-agent` лабораторії ai-lab, 2026-07-24. Замість blob — same-origin `sw.js` із HEAD-пробою (нема файлу → застосунок працює далі без офлайн-кешу) + явний precache `location.href` (інакше сторінка кешується лише з другого відкриття). Зафіксовано межу: «повністю один файл» і справжній офлайн несумісні. Синхронізовано `description`, Critical Facts і Behavior (2 рядки); +заборона кешувати `version.json`. Виправлення хибного патерну, тіло інших патернів незмінне.
- **v1.3.3** (2026-07-19) — Self-Dev Wave 2 (аудит 2026-07-18): Core Rule secure-context підтверджено як КАНОН правила для екосистеми (дубль у webllm v1.2.4 замінено покажчиком сюди) [#46]; синхрон H1-банера (був v1.0 при 1.3.2) + `last_updated` [#21/#45]. Лише метадані; тіло незмінне.
- **v1.3.2** (2026-06-26) — Ре-верифікація: +примітка про дубль v1.2.0 (вміст збережено). Лише примітка.
- **v1.3.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.2.0** (2026-06-02) — додано `metadata`/`license`-frontmatter + явну директиву «українською-перша»; додано в Routing Map семантичного роутера. _(аудит Кластер 4: metadata + P9 + P-23)_

- **v1.1.0** (2026-06-02) — Share Target API, Web Push, Background Sync patterns.

- **v1.2.0** (2026-06-02) — Pre-Update Preservation Protocol; play-store reference (TWA, Bubblewrap, signing, Capacitor, iOS).
- **v1.3.0** (2026-06-10) — Фаза 5: I-10: правило генерації UI (сміливий напрям, без placeholder'ів/generic дефолтних шрифтів; спирається на наявний дизайн-скіл).
