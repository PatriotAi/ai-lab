# Безключова CORS-проба провайдерів (2026-10-24)

**Навіщо.** `projects/mobile-agent` кличе хмарні API прямо з браузера телефона. Два питання
залежали від того, що відповідає справжній сервер, а не мок у тестах (W-33):

1. Чи бачить браузер `Retry-After` (EN: *exposed response headers*)? Без
   `Access-Control-Expose-Headers` `fetch` повертає `null`, і контур працює на експоненті.
2. Чи пропускає CORS-preflight заголовок `anthropic-beta`? Від цього залежить, чи можна
   ввімкнути серверний `fallbacks: "default"`: якби preflight його відхилив, падала б кожна
   хмарна відповідь.

**Згода.** Власник 2026-10-24 («Погоджую далі виконувати всі відкриті та заплановані»);
рядок `remote-code-execution` у `security/consent.md`, строк один день.

**Як.** `curl` з фіктивним ключем (у репо — змінна `$FAKE_KEY`, щоб сканер секретів не брав приклад за ключ) і заголовком `Origin: https://pocket-agent.example`;
тіло відповіді відкидалось (`-o /dev/null`), читались лише заголовки. Нічого не завантажувалось
і не виконувалось. Вихід проскановано `scripts/scan-external-input.py` — чисто.

```bash
FAKE_KEY=x   # навмисно фіктивний ключ; справжнього в пробі не було
# 1. Anthropic: preflight із тими заголовками, які шле застосунок
curl -sS -o /dev/null -D - -X OPTIONS https://api.anthropic.com/v1/messages \
  -H "Origin: https://pocket-agent.example" -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-api-key,anthropic-version,anthropic-dangerous-direct-browser-access,anthropic-beta"
# 2. Anthropic: POST із фіктивним ключем (очікувано 401)
curl -sS -o /dev/null -D - -X POST https://api.anthropic.com/v1/messages \
  -H "Origin: https://pocket-agent.example" -H "content-type: application/json" \
  -H "x-api-key: $FAKE_KEY" -H "anthropic-version: 2026-10-21" \
  -H "anthropic-dangerous-direct-browser-access: true" \
  --data '{"model":"claude-sonnet-5-5","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}'
# 3. Контроль: preflight із вигаданим заголовком
curl -sS -o /dev/null -D - -X OPTIONS https://api.anthropic.com/v1/messages \
  -H "Origin: https://pocket-agent.example" -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: x-api-key,x-made-up-probe-header"
# 4–5. OpenAI: preflight і POST із фіктивним Bearer (очікувано 401)
curl -sS -o /dev/null -D - -X OPTIONS https://api.openai.com/v1/chat/completions \
  -H "Origin: https://pocket-agent.example" -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: authorization,content-type"
curl -sS -o /dev/null -D - -X POST https://api.openai.com/v1/chat/completions \
  -H "Origin: https://pocket-agent.example" -H "content-type: application/json" \
  -H "authorization: Bearer $FAKE_KEY" \
  --data '{"model":"gpt-6-luna","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}'
```

## Що відповіли сервери (лише заголовки CORS)

| # | Запит | Статус | Ключові заголовки |
|---|---|---|---|
| 1 | Anthropic OPTIONS (заголовки застосунку + `anthropic-beta`) | 200 | `access-control-allow-headers: content-type,x-api-key,anthropic-version,anthropic-dangerous-direct-browser-access,anthropic-beta` · `access-control-allow-origin: *` |
| 2 | Anthropic POST, фіктивний ключ | 401 | `access-control-allow-origin: *` · **`access-control-expose-headers: *`** |
| 3 | Anthropic OPTIONS із вигаданим заголовком | **400** | заголовок віддзеркалено, але статус не 2xx — браузер такий preflight відхиляє |
| 4 | OpenAI OPTIONS | 200 | `access-control-allow-headers: authorization,content-type` · `access-control-expose-headers: CF-Ray` |
| 5 | OpenAI POST, фіктивний ключ | 401 | `access-control-allow-origin: *` · **`access-control-expose-headers: CF-Ray`** (і лише він) |

## Висновки

- **[E] Anthropic пропускає `anthropic-beta` у preflight** — рядок 1. Рядок 3 показує, що це
  справжня перевірка: невідомий заголовок дає 400, тобто сервер не просто віддзеркалює список.
  Тому серверний `fallbacks: "default"` у v0.3.1 увімкнено (`supportsServerFallback`).
- **[E] Anthropic розкриває браузеру всі заголовки відповіді** (`expose-headers: *`) — рядок 2.
  Зірочка діє лише для запитів без облікових даних. Наш `fetch` саме такий, і браузерний тест
  перевіряє, що за такої відповіді `Retry-After` справді керує паузою (`tests/mobile-agent-browser.mjs`).
  **[C]** Що на відповіді 429 ті самі заголовки, що на 401: це той самий шар CORS, але 429 без
  справжнього ключа не викликати.
- **[E] OpenAI розкриває лише `CF-Ray`** — рядок 5. `Retry-After` браузер там не бачить; для
  запасного OpenAI-сумісного провайдера контур працює на експоненті (так і задумано).

Знімок стану серверів на 2026-10-24. Провайдери можуть змінити CORS будь-коли; це не гарантія.
