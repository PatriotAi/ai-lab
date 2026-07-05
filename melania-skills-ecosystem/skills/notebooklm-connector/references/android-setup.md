# Android Setup — Повний гайд

## Як це працює на Android

```
Claude (будь-який пристрій)
    ↓ HTTP запит до MCP
Vercel Serverless Function (хмара)
    ↓ WebSocket CDP
Browserless.io (хмарний Chromium)
    ↓ cookies від твого Google акаунту
notebooklm.google.com ← повний доступ
```

**Ключ:** Google cookies витягнуті ОДИН РАЗ з Chrome на Android → збережені у Vercel як env var → сервер вставляє їх у хмарний браузер при кожному запиті. Нічого не запускається на телефоні.

---

## Крок 1 — Отримати безкоштовний Browserless.io токен

1. Зайди на [browserless.io](https://browserless.io) → Sign Up (безкоштовно)
2. Free план: **2,000 сесій/місяць** — більш ніж достатньо
3. Dashboard → API Keys → скопіювати токен
4. Твій WebSocket URL: `wss://chrome.browserless.io?token=YOUR_TOKEN`

---

## Крок 2 — Задеплоїти Vercel MCP сервер

### Через GitHub (можна з телефону)

```bash
# На комп'ютері або через GitHub web editor:
git clone <notebooklm-vercel-mcp>
cd notebooklm-vercel-mcp
git push origin main
```

1. [vercel.com](https://vercel.com) → New Project → Import Git Repository
2. Framework: Other
3. Deploy (без змін — vercel.json вже налаштований)
4. Отримаєш URL: `https://notebooklm-mcp-XXXXX.vercel.app`

### Додати env vars у Vercel

Settings → Environment Variables:

| Key | Value |
|---|---|
| `BROWSERLESS_WS_URL` | `wss://chrome.browserless.io?token=YOUR_TOKEN` |
| `GOOGLE_COOKIES` | *(витягнеш у Кроці 3)* |

---

## Крок 3 — Витягти cookies з Android Chrome

### Метод A — Cookie Editor (рекомендовано, ~5 хв)

1. Chrome на Android → `chrome://flags` → пошук "extensions" → увімкни → перезапусти
2. Встанови [Cookie Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
3. Відкрий `notebooklm.google.com` → увійди в Google → відкрий будь-який Notebook
4. Menu ⋮ → Extensions → Cookie Editor → **Export** → **Export as JSON**
5. Скопіюй весь JSON (починається з `[{"name":`)

### Метод B — USB Debugging (якщо є доступ до ПК)

```bash
# На Android: Налаштування → Розробник → USB debugging → увімкнути
# На ПК:
adb forward tcp:9222 localabstract:chrome_devtools_remote

# Відкрий у Chrome на ПК: http://localhost:9222
# → inspect notebooklm.google.com вкладка
# → Console: copy(document.cookie)
# Або Application → Cookies → Export
```

---

## Крок 4 — Зберегти cookies у Vercel

1. Vercel Dashboard → твій проект → Settings → Environment Variables
2. Key: `GOOGLE_COOKIES`
3. Value: вставити JSON array
4. **Redeploy:** Deployments → Latest → Redeploy

### Перевірка

Відкрий у браузері: `https://notebooklm-mcp-XXXXX.vercel.app/auth-status`

Побачиш інтерактивну сторінку зі статусом сесії та інструкціями.

---

## Крок 5 — Підключити до Claude

### claude.ai
Settings → Integrations → **Add MCP Server**:
```
URL:  https://notebooklm-mcp-XXXXX.vercel.app/mcp
Name: NotebookLM
```

### Claude Desktop
```json
{
  "mcpServers": {
    "notebooklm": {
      "type": "http",
      "url": "https://notebooklm-mcp-XXXXX.vercel.app/mcp"
    }
  }
}
```

### OpenClaw / cloud agents
Той самий HTTP URL в налаштуваннях агента.

---

## Автооновлення сесії (кожні ~30-60 днів)

Google session cookies живуть від 30 до 90 днів.

### Як перевірити статус

```
notebooklm_check_session {}
→ { valid: true, daysLeft: 23, ... }
```

Або відкрий: `https://your-project.vercel.app/auth-status`

### Як оновити

Коли `daysLeft < 7` або `valid: false`:

1. Chrome на Android → `notebooklm.google.com` → Cookie Editor → Export as JSON
2. Vercel → Settings → Environment Variables → `GOOGLE_COOKIES` → Edit → вставити нові cookies
3. Redeploy

### Авто-нагадування (через Claude)

Скажи Claude: *"Перевір статус сесії NotebookLM і нагадай оновити cookies якщо залишилось менше 7 днів"*

Claude викличе `notebooklm_check_session` і попередить автоматично.

---

## Troubleshooting

| Проблема | Причина | Рішення |
|---|---|---|
| `NOT_AUTHENTICATED` | Cookies скінчились | Повтори Крок 3-4 |
| `BROWSERLESS_WS_URL not set` | Змінна не додана | Додати в Vercel env vars |
| Vercel timeout | Операція >5 хв | Лише Briefing Doc та Chat — нормально |
| Cookie Editor не з'являється | Extensions не увімкнені | `chrome://flags` → enable extensions |
| `invalid JSON` для GOOGLE_COOKIES | Неправильний формат | Має бути array: `[{...}, {...}]` |

---

## Порівняння методів доступу

| | Vercel+Browserless | Python MCP (notebooklm-py) | TypeScript (Playwright) |
|---|---|---|---|
| **Android** | ✅ Так | ❌ Потрібен ПК | ❌ Потрібен ПК |
| **Логін** | Cookies 1x | Browser 1x | Browser завжди |
| **Швидкість** | 2-5 сек | 0.5-1 сек | 3-8 сек |
| **Audio/Video** | ❌ | ✅ | ❌ |
| **Безкоштовно** | ✅ | ✅ | ✅ |
| **Стабільність** | DOM (середня) | RPC (висока) | DOM (низька) |

**Рекомендація:** Vercel+Browserless для Android і мобільного доступу. Python MCP — для advanced генерації artifacts на ПК.
