# Android Cookie Extraction — Повна інструкція

## Чому це єдиний шлях на Android

Google NotebookLM захищений через session cookies, які видаються при логіні.
На Android Chrome зберігає ці cookies в захищеному сховищі — root доступ не потрібен.
Cookie Editor зчитує cookies через Chrome Extension API (легально, без root).

---

## Метод 1 — Cookie Editor (рекомендовано, 3 хвилини)

### Крок 1: Встановити Cookie Editor
- Play Store → пошук **"Cookie Editor"** (автор: Corvo, 4.5★)
- Або пряме посилання: `play.google.com/store/apps/details?id=com.sec.cookieeditor`

### Крок 2: Відкрити NotebookLM
- Chrome → `notebooklm.google.com`
- Переконайся що ти залогінений у свій Google акаунт

### Крок 3: Відкрити Cookie Editor
- Chrome → три крапки `⋮` → Extensions або More Tools
- Або: вручну відкрити Cookie Editor з Drawer

### Крок 4: Відфільтрувати Google cookies
- Cookie Editor покаже список cookies для поточного сайту
- Важливі cookies (зеленим): `__Secure-1PSID`, `__Secure-3PSID`, `SSID`, `HSID`
- Натисни **Export** → **Export as JSON**

### Крок 5: Передати JSON до сервера

**Варіант A — через Claude (найшвидше):**
```
Скопіювати exported JSON → вставити в Claude:
"Оновити сесію: [вставити JSON]"

Claude автоматично викличе notebooklm_inject_cookies
```

**Варіант B — через cookie_converter.py:**
```bash
# Зберегти JSON у файл, потім:
python cookie_converter.py --from-json cookies.json --out ~/.notebooklm/storage_state.json
python cookie_converter.py --verify ~/.notebooklm/storage_state.json
```

**Варіант C — оновити env var на сервері:**
```bash
python cookie_converter.py --from-json cookies.json --out /tmp/new_storage.json --export-env
# Скопіювати значення NOTEBOOKLM_AUTH_JSON → Render/Vercel dashboard
```

---

## Метод 2 — Chrome Remote Debugging (для технічних)

> Потрібен USB кабель і ПК

### Крок 1: Увімкнути Developer Options
```
Settings → About Phone → Build Number (тапнути 7 разів)
Settings → Developer Options → USB Debugging ✓
```

### Крок 2: USB Debugging + Chrome Inspect
```bash
# На ПК:
adb devices           # підтвердити на телефоні
adb forward tcp:9222 tcp:9222

# Chrome на Android: chrome://inspect
# Або на ПК: chrome://inspect → Remote Target → ваш телефон
```

### Крок 3: Витягти cookies через DevTools Console
```javascript
// В DevTools Console (Remote Target):
copy(document.cookie)

// АБО через CDP (Chrome DevTools Protocol):
// Network → All → Headers → Cookie header
```

### Крок 4: Конвертувати у потрібний формат
```bash
# Якщо отримали рядок "name=value; name2=value2":
python3 -c "
import json
cookie_str = 'PASTE_HERE'
cookies = []
for pair in cookie_str.split(';'):
    pair = pair.strip()
    if '=' in pair:
        n, _, v = pair.partition('=')
        cookies.append({'name': n.strip(), 'value': v.strip(),
                        'domain': '.google.com', 'path': '/',
                        'expires': -1, 'httpOnly': False, 'secure': True, 'sameSite': 'Lax'})
print(json.dumps({'cookies': cookies, 'origins': []}, indent=2))
" > storage_state.json
```

---

## Метод 3 — через ПК (одноразово)

Найнадійніший варіант — зробити один раз на комп'ютері:

```bash
# На будь-якому ПК (навіть Windows через WSL):
pip install "notebooklm-py[browser]" playwright
playwright install chromium
notebooklm login    # відкриє браузер → залогінитись

# Скопіювати storage_state.json на сервер:
cat ~/.notebooklm/storage_state.json
# → скопіювати вміст → Render/Vercel/Render dashboard → NOTEBOOKLM_AUTH_JSON
```

---

## Автооновлення сесії — моніторинг

### Claude автоматично перевіряє сесію

Skill `notebooklm_session_status` повертає:
- Скільки днів залишилось до закінчення
- Які cookies відсутні або прострочені
- Покрокову інструкцію для Android

### Коли оновлювати

| Попередження | Дія |
|---|---|
| `days_remaining < 30` | Запланувати оновлення |
| `days_remaining < 7` | Оновити зараз (Cookie Editor) |
| `days_remaining < 0` | Терміново: сесія закінчилась |

### Нагадування в Skill

При будь-якій помилці автентифікації Skill автоматично:
1. Викличе `notebooklm_session_status`
2. Якщо `needs_refresh: true` → покаже Android-інструкцію
3. Запропонує вставити cookies напряму через `notebooklm_inject_cookies`

---

## Troubleshooting

| Проблема | Причина | Рішення |
|---|---|---|
| Cookie Editor не бачить cookies | Chrome блокує extension на деяких Android | Спробуй Firefox + Cookie Editor для Firefox |
| Cookies є, але логін не спрацьовує | Пропущені критичні cookies | Перевір наявність `__Secure-1PSID` і `__Secure-3PSID` |
| `python cookie_converter.py` не знайдено | Python не встановлено | Використай Варіант A (через Claude безпосередньо) |
| Cookies тривають 30 хвилин | Витягнуто session cookies замість persistent | Переконайся "Remember me" увімкнено при логіні |

---

## Формат cookies для `notebooklm_inject_cookies`

Claude приймає два формати напряму:

**Формат 1 — Chrome DevTools Array (від Cookie Editor):**
```json
[
  {"name": "__Secure-1PSID", "value": "...", "domain": ".google.com", "path": "/", "httpOnly": true, "secure": true},
  {"name": "__Secure-3PSID", "value": "...", "domain": ".google.com", "path": "/", "httpOnly": true, "secure": true},
  {"name": "HSID", "value": "...", "domain": ".google.com"},
  {"name": "SSID", "value": "...", "domain": ".google.com"}
]
```

**Формат 2 — Playwright storageState (якщо вже є):**
```json
{
  "cookies": [...],
  "origins": []
}
```
