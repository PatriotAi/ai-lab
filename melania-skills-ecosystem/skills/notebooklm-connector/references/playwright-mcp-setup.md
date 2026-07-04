# Playwright MCP — Встановлення та інтеграція

## Чому потрібен Playwright MCP

| Проблема | Причина | Рішення |
|---|---|---|
| NotebookLM → 403 | Google OAuth 2.0 + активна браузерна сесія | Playwright зберігає cookies/session |
| robots.txt блокує | Всі не-браузерні HTTP запити заблоковані | Playwright — справжній Chromium |
| Немає REST API | NotebookLM без публічного API | Playwright читає DOM напряму |
| web_fetch stateless | Не зберігає токени між запитами | Playwright зберігає стан сесії |

---

## Встановлення (5 хвилин)

### Крок 1: Встановити пакет
```bash
npm install -g @playwright/mcp@latest
```

### Крок 2: Встановити браузер Chromium
```bash
npx playwright install chromium
```

### Крок 3: Додати до конфігурації Claude Desktop

Відкрити файл конфігурації:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Додати (або оновити) секцію `mcpServers`:
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--browser", "chromium",
        "--headed"
      ],
      "env": {}
    }
  }
}
```

> `--headed` означає що браузер відкривається видимо — потрібно для ручного Google логіну.
> Для повністю автоматичного режиму (якщо сесія збережена): замінити на `--headless`.

### Крок 4: Перезапустити Claude Desktop
Повністю закрити і відкрити знову — MCP сервери завантажуються лише при старті.

---

## Перевірка роботи

Після перезапуску в Claude мають з'явитись інструменти:
- `browser_navigate`
- `browser_click`
- `browser_type`
- `browser_snapshot`
- `browser_screenshot`
- `browser_wait_for`
- `browser_select_option`

**Тест:** `browser_navigate("https://google.com")` → `browser_snapshot()` → має повернути DOM.

---

## Збереження Google сесії

### Перший запуск (ручний логін)
```
1. browser_navigate("https://accounts.google.com")
2. Виконати логін вручну у відкритому вікні Chromium
3. Playwright автоматично зберігає cookies після логіну
4. Наступні запити до Google сервісів — автоматично авторизовані
```

### Зберегти сесію між перезапусками
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--browser", "chromium",
        "--headed",
        "--user-data-dir", "/Users/[USERNAME]/.playwright-chrome-profile"
      ]
    }
  }
}
```
`--user-data-dir` зберігає профіль браузера → логін потрібен лише один раз.

---

## Взаємодія з NotebookLM через Playwright

### Отримати список усіх джерел
```
browser_navigate("https://notebooklm.google.com/notebook/<ID>")
browser_snapshot()
# Шукати елементи: [data-testid="source-list"] або .sources-panel
```

### Відкрити конкретне джерело
```
browser_click(element="[назва джерела у списку]")
browser_snapshot()
# Читати .source-content або [role="document"]
```

### Запустити Briefing Doc
```
browser_click(element="Notebook Guide")
browser_click(element="Briefing doc")
browser_wait_for(selector=".briefing-doc-content")
browser_snapshot()
```

### Зробити скріншот при проблемах
```
browser_screenshot()
# Повертає PNG — показати користувачу для діагностики
```

---

## Альтернатива: Claude in Chrome (beta)

Якщо встановлення npm неможливе:

1. Встановити розширення **Claude in Chrome** (beta від Anthropic)
2. Відкрити NotebookLM у Chrome
3. Активувати Claude in Chrome (іконка в тулбарі)
4. Claude отримує доступ до вмісту активної вкладки
5. Команда: *"Витягни всі джерела з цього NotebookLM і об'єднай в документ"*

> Claude in Chrome — продукт Anthropic в бета-стані. Функціональність може відрізнятись.

---

## Troubleshooting

| Проблема | Причина | Рішення |
|---|---|---|
| `command not found: npx` | Node.js не встановлено | Встановити Node.js 18+ з nodejs.org |
| MCP сервер не з'являється | Не перезапущено Claude | Повністю закрити і відкрити знову |
| Браузер не відкривається | `--headed` відсутній | Перевірити args у config |
| Логін скидається | Немає `--user-data-dir` | Додати параметр збереження профілю |
| `browser_snapshot` порожній | Сторінка не завантажилась | Додати `browser_wait_for` перед snapshot |
