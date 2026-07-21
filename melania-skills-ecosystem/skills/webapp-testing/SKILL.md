---
name: webapp-testing
description: "Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs. Use this skill when testing web applications, running browser automation, debugging frontend UI, or capturing screenshots of local apps. Також використовуй, коли користувач хоче: протестувати веб-застосунок, налаштувати Playwright-автоматизацію браузера, перевірити UI / доступність / мобільні вьюпорти, зробити visual regression чи скриншоти локального застосунку. НЕ використовувати для не-браузерних юніт-тестів чи бекенд-логіки без UI, ані для спільного інтерактивного веб-серфінгу з агентом (collaborative-browser) — тут лише автоматизовані Playwright-тести."
license: Apache-2.0 — повні умови в LICENSE.txt кореня екосистеми
metadata:
  version: 1.5.0
  author: Melania (Master Administrator)
  category: testing
  created: 2026-06-02
  last_updated: 2026-07-19
---

# Web Application Testing — v1.5.0
> Пояснення — українською за замовчуванням (українською-перша); код, селектори та команди лишаються англійською. Перемикання мови лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).


## Дерево рішень: вибір підходу

```text
Завдання користувача → Це статичний HTML?
    ├─ Так → Прочитай HTML-файл напряму, щоб визначити селектори
    │         ├─ Успіх → Напиши Playwright-скрипт за селекторами
    │         └─ Не вийшло/неповно → Трактуй як динамічний (нижче)
    │
    └─ Ні (динамічний webapp) → Сервер уже запущений?
        ├─ Ні → Отримай helper (нема локально — web_fetch, див. Нотатку нижче),
        │        тоді виконай: python scripts/with_server.py --help
        │        Далі використай helper + напиши спрощений Playwright-скрипт
        │
        └─ Так → Reconnaissance-then-action (розвідка → дія):
            1. Navigate і чекай networkidle
            2. Зроби screenshot або інспектуй DOM
            3. Визнач селектори з відрендереного стану
            4. Виконай дії знайденими селекторами
```

## Приклад: використання with_server.py

Щоб запустити сервер, спершу `--help`, потім helper:

**Один сервер:**
```bash
python scripts/with_server.py --server "npm run dev" --port 5173 -- python your_automation.py
```

**Кілька серверів (напр. backend + frontend):**
```bash
python scripts/with_server.py \
  --server "cd backend && python server.py" --port 3000 \
  --server "cd frontend && npm run dev" --port 5173 \
  -- python your_automation.py
```

Щоб створити скрипт автоматизації, включай лише Playwright-логіку (сервери керуються автоматично):

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)  # Always launch chromium in headless mode
    page = browser.new_page()
    page.goto('http://localhost:5173')  # Server already running and ready
    page.wait_for_load_state('networkidle')  # CRITICAL: Wait for JS to execute
    # ... your automation logic
    browser.close()
```

## Патерн Reconnaissance-Then-Action

1. **Інспектуй відрендерений DOM**:
   ```python
   page.screenshot(path='/tmp/inspect.png', full_page=True)
   content = page.content()
   page.locator('button').all()
   ```
2. **Визнач селектори** з результатів інспекції
3. **Виконай дії** знайденими селекторами

## Часта пастка

❌ **Не** інспектуй DOM до очікування `networkidle` на динамічних застосунках
✅ **Чекай** `page.wait_for_load_state('networkidle')` перед інспекцією

## Найкращі практики

* **Використовуй вбудовані скрипти як чорні скриньки** — `--help` щоб побачити usage, далі виклик напряму
* Використовуй `sync_playwright()` для синхронних скриптів
* Завжди закривай браузер по завершенні
* Описові селектори: `text=`, `role=`, CSS-селектори чи ID
* Додавай доречні очікування: `page.wait_for_selector()` або `page.wait_for_timeout()`

## Reference-файли

> ℹ️ **Нотатка:** `scripts/with_server.py` та `examples/` живуть у повному репо [`anthropics/skills/skills/webapp-testing/`](https://github.com/anthropics/skills/tree/main/skills/webapp-testing). Тягни через `web_fetch` за потреби.

* **examples/** — приклади частих патернів:
  + `element_discovery.py` — пошук кнопок, лінків та інпутів на сторінці
  + `static_html_automation.py` — використання file:// URL для локального HTML
  + `console_logging.py` — захоплення console-логів під час автоматизації

---

## Visual Regression Testing

```python
# Скриншот базовий (зберегти еталон)
page.screenshot(path="baseline/homepage.png")

# Порівняння (поточний vs еталон)
from PIL import Image, ImageChops
import numpy as np

def compare_screenshots(baseline_path, current_path, threshold=0.01):
    base = Image.open(baseline_path).convert("RGB")
    curr = Image.open(current_path).convert("RGB")
    diff = ImageChops.difference(base, curr)
    pct_diff = np.array(diff).mean() / 255
    return pct_diff < threshold, pct_diff

page.screenshot(path="current/homepage.png")
ok, diff = compare_screenshots("baseline/homepage.png", "current/homepage.png")
print(f"Visual diff: {diff:.2%} — {'PASS' if ok else 'FAIL'}")
```

---

## API Testing (через Playwright)

```python
# Playwright має вбудований API client
response = page.request.get("https://api.example.com/users")
assert response.status == 200
data = response.json()
assert len(data) > 0

# POST з auth
response = page.request.post("/api/login",
    data={"email": "test@test.com", "password": "pass"},
    headers={"Content-Type": "application/json"}
)
token = response.json()["token"]
```

---

## Accessibility Testing

```python
# Базова перевірка a11y через axe-playwright
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("http://localhost:3000")
    
    # Перевірка ARIA labels
    buttons = page.locator("button:not([aria-label]):not([aria-labelledby])")
    unlabeled = buttons.count()
    assert unlabeled == 0, f"{unlabeled} кнопок без aria-label"
    
    # Tab order
    page.keyboard.press("Tab")
    focused = page.locator(":focus").get_attribute("data-testid")
    print(f"Перший фокус: {focused}")
```

---

## Mobile Viewport Testing

```python
# Тестуй на різних розмірах екрану
VIEWPORTS = [
    {"name": "mobile", "width": 375, "height": 812},    # iPhone 14
    {"name": "tablet", "width": 768, "height": 1024},   # iPad
    {"name": "desktop","width": 1440,"height": 900},    # Full HD
]
for vp in VIEWPORTS:
    page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
    page.goto("http://localhost:3000")
    page.screenshot(path=f"screenshots/{vp['name']}.png")
    # Перевірка що hamburger-меню видно на мобільному
    if vp["width"] < 768:
        assert page.locator("[data-testid=mobile-menu]").is_visible()
```

---

## Pairwise-тести + статичний аналіз
**Pairwise (комбінаторне покриття пар) — мінімум кейсів, максимум покриття:** замість усіх комбінацій
параметрів генеруй мінімальний набір, що покриває всі **пари** значень (більшість багів — від взаємодії двох факторів).
Корисно для форм, фільтрів, матриць конфігів — десятки кейсів замість сотень.

**Статичний аналіз (rule-based) перед/поряд із UI-тестами:** цикл правила —
застосовність → тест-перш (вразливий + безпечний приклади) → правило → валідація.
Лови небезпечні патерни (інʼєкційні sink-и, небезпечне вставляння HTML, відкриті редіректи) до рантайму.

## 📎 Advanced Patterns (v4)

Читай `references/e2e-patterns.md`, КОЛИ потрібні: повні user flows, network mocking, test factories, паралельне виконання, anti-flaky waits, performance.
Вантаж лише на вимогу — не проактивно.

---

## Зміни
- **v1.5.0** (2026-07-19) — Self-Dev Wave 2 (аудит 2026-07-18): Decision Tree більше не вдає локальний `with_server.py` — явний крок web_fetch перед викликом (файл живе в anthropics/skills; Нотатка була, дерево їй суперечило) [#43]; сирітських/мертвих references не виявлено — `e2e-patterns.md` підключений [#15 перевірено]; межа з `collaborative-browser` у описі [#41]; ліцензійний покажчик на корінь екосистеми [#25/#44]; H1 з версією. Лише документація/межі.
- **v1.4.0** (2026-06-26) — Повна UA-локалізація (Task 1): ранню прозу (Decision Tree, with_server, Reconnaissance, Common Pitfall, Best Practices, Reference-файли) перекладено українською; код / селектори / команди лишаються англійською. +власні `evals/` (5, канон-схема). **S-2:** дубль v1.2.0 у changelog консолідовано + впорядковано (вміст збережено). Переклад + додавання; функціонал не змінено.
- **v1.3.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна.
- **v1.3.0** (2026-06-10) — Фаза 5: I-11: pairwise (комбінаторне покриття пар) + rule-based статичний аналіз.
- **v1.2.0** (2026-06-02) — `metadata`-блок, директива «українською-перша», власні `evals/` (5); Pre-Update Preservation Protocol; `e2e-patterns` reference (full flows, mocking, factories, performance). _(аудит Кластер 3: P9 + Core Rule 4)_
- **v1.1.0** (2026-06-02) — visual regression, API testing, accessibility checks, mobile viewport testing.
