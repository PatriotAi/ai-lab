# Browserbase Android Setup — Повна інструкція

## Що це дає

Після налаштування (~20 хвилин, тільки телефон):
- Claude бачить хмарний браузер і може ним керувати
- Скріншоти після кожної дії — ти завжди бачиш що відбувається
- Повний доступ до NotebookLM: читати, генерувати, завантажувати
- Сесія зберігається — повторний логін не потрібен

---

## КРОК 1 — Реєстрація Browserbase (5 хв)

1. Відкрий **[browserbase.com](https://browserbase.com)** у Chrome на Android
2. **Sign Up** → безкоштовний план (100 годин/місяць браузера)
3. Dashboard → **API Keys** → **Create new key** → скопіюй `BROWSERBASE_API_KEY`
4. Dashboard → **Projects** → скопіюй `BROWSERBASE_PROJECT_ID` (числовий ID)

> Зберегти обидва значення — знадобляться на Кроці 3.

---

## КРОК 2 — Отримати Google cookies (10 хв)

> **Мета:** Дати хмарному браузеру твою Google сесію. Робиться один раз.

### Варіант A — Cookie Editor (рекомендовано)

1. **Play Store** → встановити **"Cookie Editor"** (автор: Corvo)
2. Chrome → `notebooklm.google.com` → переконайся що залогінений
3. Chrome `⋮` → **Extensions** → **Cookie Editor** → **Export** → **Export as JSON**
4. Скопіюй весь JSON у буфер обміну

5. Відкрий Claude і напиши:
   ```
   Збережи ці Google cookies для Browserbase:
   [вставити JSON тут]
   ```
   → Claude збереже через `browserbase_authenticate` автоматично

### Варіант B — Через cookie_converter.py (якщо є ПК)

```bash
python cookie_converter.py --from-json cookies.json \
  --out storage.json --export-env
```
Скопіювати `GOOGLE_STORAGE_STATE=...` значення.

---

## КРОК 3 — Деплой на Render.com (5 хв, з телефону)

### 3.1 Завантажити код на GitHub

1. Відкрий **[github.com](https://github.com)** → **New repository**
2. Назва: `notebooklm-browserbase-mcp`
3. Відкрий **github.dev** (натисни `.` на клавіатурі у репо)
4. Завантажи файли з `notebooklm-browserbase-mcp.zip`

### 3.2 Деплой на Render

1. **[render.com](https://render.com)** → **New Web Service**
2. Connect GitHub → обери `notebooklm-browserbase-mcp`
3. Settings:
   - **Runtime:** Node
   - **Build command:** `npm install && npm run build`
   - **Start command:** `node dist/index.js`
   - **Plan:** Free
4. **Environment Variables** (додати вручну):
   ```
   BROWSERBASE_API_KEY     = <з Кроку 1>
   BROWSERBASE_PROJECT_ID  = <з Кроку 1>
   GOOGLE_STORAGE_STATE    = <JSON рядок з Cookie Editor або cookie_converter.py>
   PORT                    = 3000
   ```
5. **Create Web Service** → чекай 3-5 хвилин

### 3.3 Перевірити

Відкрий у браузері: `https://notebooklm-browserbase-mcp.onrender.com/health`
```json
{
  "status": "ok",
  "browserbase_configured": true,
  "google_cookies_loaded": true
}
```

---

## КРОК 4 — Підключити до Claude (2 хв)

1. Відкрий **[claude.ai/settings/integrations](https://claude.ai/settings/integrations)**
2. **Add Integration** або **Add MCP Server**
3. URL: `https://notebooklm-browserbase-mcp.onrender.com/mcp`
4. Назва: `Browserbase NotebookLM`
5. **Save** → статус **Connected** ✅

> Після додавання через claude.ai — автоматично доступно в Claude на Android.

---

## КРОК 5 — Одноразовий тест (2 хв)

Напиши в Claude:
```
Відкрий мій NotebookLM Notebook:
https://notebooklm.google.com/notebook/ae68f3e3-91d9-46b4-baff-4f300ed482ad

Покажи скріншот і скільки там джерел.
```

**Очікуваний результат:**
- Скріншот сторінки Notebook
- Кількість джерел
- Готовність до подальших команд

---

## Agentний режим — команди які можна давати

```
"Відкрий мій Notebook і покажи що там"
→ notebooklm_browse_open → screenshot

"Витягни всі джерела і об'єднай в документ"
→ notebooklm_browse_sources → merge

"Згенеруй Briefing Doc"
→ notebooklm_browse_studio { feature: "briefing" }

"Згенеруй Audio Overview на 5 хвилин"
→ notebooklm_browse_studio { feature: "audio", wait_seconds: 300 }

"Запитай через Chat: Яка головна тема?"
→ notebooklm_browse_chat { query: "Яка головна тема цього Notebook?" }

"Натисни кнопку Studio"
→ browserbase_click { selector: "Studio", by_text: true }

"Зроби скріншот"
→ browserbase_screenshot {}

"Прокрути вниз і подивись що ще є"
→ browserbase_scroll → browserbase_screenshot
```

---

## Оновлення сесії (раз на ~30 днів)

Коли Claude каже `needs_refresh: true`:

1. Chrome → `notebooklm.google.com` (перевір логін)
2. Cookie Editor → **Export** → скопіювати JSON
3. Claude:
   ```
   Оновити Google cookies для Browserbase:
   [вставити новий JSON]
   ```
4. Claude автоматично викличе `browserbase_authenticate`

---

## Troubleshooting

| Проблема | Рішення |
|---|---|
| Health endpoint 404 | Render ще деплоїться — зачекай 5 хв |
| `browserbase_configured: false` | Перевір env vars у Render dashboard |
| Скріншот показує login page | Cookies застарілі — Крок 2 (оновити) |
| Render cold start (~30 сек) | Безкоштовний план — перший запит повільний |
| Smithery.ai як альтернатива | smithery.ai → Browserbase → Configure → вставити API keys → отримати URL |

---

## Smithery.ai — найшвидший варіант (без деплою)

Якщо не хочеш деплоїти Render:

1. **[smithery.ai](https://smithery.ai)** → пошук "Browserbase"
2. **Configure** → вставити `BROWSERBASE_API_KEY` + `BROWSERBASE_PROJECT_ID`
3. Отримати URL: `https://server.smithery.ai/browserbase/mcp?...`
4. Цей URL → claude.ai Settings → Integrations

> Smithery хостить MCP сервер за тебе. Google cookies inject відбувається через `browserbase_authenticate` tool.
