---
name: auth-session-manager
description: >
  Єдиний безпечний шар авторизації для браузер- і MCP-автоматизації: видобування
  й інʼєкція cookie (десктоп/Android), OAuth, моніторинг протермінування сесій,
  зашифроване зберігання секретів (AES-GCM). Консолідує патерни, що дублювалися в
  notebooklm-connector і collaborative-browser.

  ALWAYS use when: авторизуватися у вебсервісі, оновити cookie, налаштувати OAuth,
  стежити за протерміновою сесії, безпечно зберегти токен. Користувач каже:
  "авторизуйся", "онови cookie", "сесія протермінувалась", "інʼєкція cookie",
  "збережи токен безпечно", "OAuth", "session expired", "cookie injection".

  Also: cookie extraction, browserbase authenticate, session health, days
  remaining, token refresh, AES-GCM, secrets manager, керування сесіями.

  DO NOT use for: ротацію ключів LLM-провайдерів (multi-provider-ai-orchestration),
  будування браузер-артефакту (collaborative-browser), чи конкретний NotebookLM
  (notebooklm-connector — він викликає цей скіл для авторизації).
compatibility: >
  Claude.ai (всі плани) · Claude Code · Cursor · Copilot. Патерни авторизації
  крос-платформні. AES-GCM шифрування потребує Web Crypto (браузер/артефакт);
  cookie-видобування потребує доступу до браузера користувача.
allowed-tools:
  - Bash(python:*)
  - Read
  - Write
license: Proprietary
metadata:
  version: 1.4.2
  author: Melania (Master Administrator)
  category: auth
  created: 2026-06-02
  last_updated: 2026-06-12
---

# Auth & Session Manager — v1.0
> Українською-перша: пояснення, попередження й нотатки — українською за замовчуванням;
> назви cookie, домени, токени та код лишаються як є. Перемикання мови лише слідом за користувачем.
> Деталі методів — у `references/auth-methods.md`. Захист: `scripts/skill_guard.py`.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Core Rule — безпека понад зручність
Секрети (cookie, токени, ключі, паролі) **НІКОЛИ** не логуються у відкритому вигляді,
не зашиваються у код і не зберігаються незашифрованими. При сумніві — менше виводу,
більше шифрування. Будь-яке зберігання — лише через AES-GCM (Pattern 4).

> ⚖️ Це скіл-**механіка**. Політика безпекової постави (недовірений вхід, human-confirm на write-tools, IP/публікація) — `safety-compliance-gate`.

## Мова
Працюй українською за замовчуванням; технічні значення (cookie-імена, домени, JSON)
не перекладай.

---

## Каскад авторизації (від найнадійнішого до ручного)
Пробуй методи згори вниз; падай на наступний лише коли поточний неможливий:

| # | Метод | Коли |
|---|-------|------|
| 1 | **`inject_cookies`** — готові cookie з менеджера секретів | є збережена валідна сесія |
| 2 | **`browserbase_authenticate`** — кероване хмарне логування | потрібен свіжий логін, є Browserbase |
| 3 | **OAuth React-артефакт** — потік згоди в артефакті | сервіс підтримує OAuth |
| 4 | **Guided manual** — інструкція користувачу видобути cookie | усе інше недоступне |

---

## Pattern 1 — Видобування cookie (десктоп + Android)
**Десктоп:** розширення Cookie-Editor → Export → JSON; або DevTools → Application → Cookies.
**Android (без root):** Kiwi/Yandex browser + Cookie-Editor extension, або Remote Debugging
через `chrome://inspect` з ПК. Зберегти як JSON-масив `{name,value,domain,path,expires}`.

## Pattern 2 — Інʼєкція cookie
```javascript
// cookie-масив → активна сесія (через Browserbase / Playwright context)
async function injectCookies(context, cookies){
  // валідація форми ПЕРЕД інʼєкцією
  const valid = cookies.filter(c => c.name && c.value && c.domain);
  if(!valid.length) throw new Error("Немає валідних cookie для інʼєкції");
  await context.addCookies(valid);
  return valid.length;
}
```
Ніколи не друкувати `c.value` у лог. Після інʼєкції — перевірити сесію (Pattern 3).

## Pattern 3 — Моніторинг здоровʼя сесії
```javascript
function sessionStatus(cookies){
  const now = Date.now()/1000;
  const exp = Math.min(...cookies.filter(c=>c.expires>0).map(c=>c.expires));
  const days = Math.floor((exp - now)/86400);
  return { healthy: days>0, days_remaining: days,
           warn: days<7 };   // проактивно попередити при <7 днях
}
```
Якщо `warn` — повідомити користувача завчасно; якщо `!healthy` — запустити каскад авторизації наново.

## Pattern 4 — AES-GCM Secrets Manager (зашифроване зберігання)
```javascript
// Web Crypto: шифрування секрету паролем користувача
async function encryptSecret(plain, pass){
  const enc=new TextEncoder();
  const salt=crypto.getRandomValues(new Uint8Array(16));
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const km=await crypto.subtle.importKey("raw",enc.encode(pass),"PBKDF2",false,["deriveKey"]);
  const key=await crypto.subtle.deriveKey(
    {name:"PBKDF2",salt,iterations:100000,hash:"SHA-256"},km,
    {name:"AES-GCM",length:256},false,["encrypt"]);
  const ct=await crypto.subtle.encrypt({name:"AES-GCM",iv},key,enc.encode(plain));
  return { salt:[...salt], iv:[...iv], ct:[...new Uint8Array(ct)] }; // зберігати ЦЕ, не plain
}
```
Зберігати лише `{salt, iv, ct}`. Розшифрування — симетрично, лише за вводом пароля користувачем.

---

## Pattern 5 — Schema-замість-значень + маскування
Працюй зі **схемою**, не зі значеннями секретів:
- Читай `.env.schema` (структура, типи, обовʼязковість), **ніколи не читай і не вантаж `.env`** із реальними значеннями. Анотації: `@sensitive` / `@required` / `@type`.
- Показуючи, що секрет існує — **маскуй**: `API_KEY = ▒▒▒▒▒▒` (не значення).
- Інʼєктуй секрети в команду без друку (напр. `run -- <cmd>`), не виводячи їх у лог/відповідь.
- **Відмова:** на прохання показати/змінити значення секрету — «Я не показую і не редагую значення секретів напряму; працюю лише зі схемою та маскованими посиланнями.»
- Скануй **вихідні** відповіді/виводи на випадковий витік секретів перед поверненням користувачу.

## Pattern 6 — Мульті-MCP авторизація (механіка)
Коли підключено кілька MCP-конекторів одночасно:
- **Per-client OAuth consent:** кожен MCP-клієнт проходить ОКРЕМИЙ потік згоди; не переноси токен одного конектора на інший (механічний захист від confused-deputy).
- **Ізоляція креденшіалів:** зберігай токени по-конекторно (окремий ключ у менеджері секретів на кожен сервіс); не змішуй scope між конекторами.
- **Session-health на конектор:** застосовуй Pattern 3 до КОЖНОГО MCP окремо; протермінування одного не валить інші; re-auth точково.
- **Scope-мінімізація:** запитуй лише потрібні scope на під'єднання; зайві дозволи = ширша поверхня атаки.
> Це МЕХАНІКА. Рішення «чи можна виконувати дію / чи довіряти виводу» — політика `safety-compliance-gate` (Блок A).

## Behavior (security gates)
| ✓ Роби | ✗ Ніколи |
|--------|----------|
| Шифруй усі секрети через AES-GCM перед збереженням | Не зберігай cookie/токен у відкритому тексті |
| Попереджай про протермінування при <7 днях | Не друкуй значення секрету в лог/відповідь |
| Валідуй форму cookie перед інʼєкцією | Не зашивай ключі/паролі у код чи JSON |
| Падай по каскаду при невдачі методу | Не передавай секрети третім сервісам без згоди |
| Питай пароль користувача для розшифрування | Не зберігай пароль шифрування разом із даними |
| Працюй зі `.env.schema`, маскуй значення (▒▒▒▒) | Не читай/не вантаж `.env` із реальними значеннями |
| Відмовляй на показ/зміну значення секрету | Не виводь секрет навіть на пряме прохання |

## Verify before integrating
- форма cookie валідна (`name+value+domain`)?
- секрет зашифровано (є `salt/iv/ct`, немає plain)?
- сесія перевірена після інʼєкції?
- у виводі немає відкритих значень секретів?
- працювали зі `.env.schema`, не з реальними значеннями; вихід просканований на витік?

---

## Координація
| Skill | Звʼязок |
|-------|---------|
| `notebooklm-connector` | ВИКЛИКАЄ цей скіл для авторизації NotebookLM (замість власної копії) |
| `collaborative-browser` | ВИКЛИКАЄ для cookie-інʼєкції та секретів у браузер-артефакті |
| `multi-provider-ai-orchestration` | сусідній домен (ключі LLM-провайдерів) — НЕ перетинається, лише примітив шифрування |
| `validation-mesh` | перевірка, що в артефакті немає відкритих секретів перед deploy |
| `safety-compliance-gate` | задає ПОЛІТИКУ постави; цей скіл — МЕХАНІКА (гейт делегує сюди auth/сесії/секрети) |

Читай `references/auth-methods.md` КОЛИ: потрібні повні кроки видобування cookie на конкретній
платформі, схема OAuth-артефакту, або деталі PBKDF2/AES-GCM.


## 📎 Advanced Patterns (v4)

Read `references/oauth-flows.md` WHEN you need: OAuth PKCE, refresh rotation, device flow, token introspection, AES-GCM storage.
Load only on demand — not proactively.

---

## Зміни
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (артефакт злиттів). Усі записи збережено; нумерацію НЕ переписано без верифікації джерел._
- **v1.4.2** (2026-06-26) — Stage 3 S-2: примітка про дубль v1.2.0 у changelog (вміст збережено, нумерацію не переписано). Лише додавання примітки.
- **v1.4.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.2.0** (2026-06-02) — JWT management, multi-service health check, rate limit backoff.

- **v1.2.0** (2026-06-02) — Pre-Update Preservation Protocol; oauth-flows reference (PKCE, refresh rotation, device flow, AES-GCM).
- **v1.3.0** (2026-06-10) — Фаза 1 безпеки: Pattern 5 (schema-замість-значень + маскування ▒▒▒▒ + відмова показувати/міняти секрет + скан вихідного витоку); 2 Behavior-гейти + Verify. _(план I-6)_
- **v1.4.0** (2026-06-12) — Pattern 6: механіка мульті-MCP авторизації (per-client OAuth consent, ізоляція креденшіалів, session-health на конектор, scope-мінімізація) + тонкий покажчик на `safety-compliance-gate` (політика↔механіка). _(Harvest Vercel MCP → Proposal #3.)_
