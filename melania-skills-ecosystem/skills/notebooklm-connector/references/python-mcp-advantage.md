# Python MCP vs TypeScript MCP — Вибір і можливості

## Порівняльна таблиця

| Критерій | Python MCP (notebooklm-py) | TypeScript MCP (Playwright DOM) |
|---|---|---|
| **Метод доступу** | Google RPC batchexecute | DOM scraping через Playwright |
| **Браузер** | Тільки для першого логіну | Постійно запущений |
| **Швидкість** | ~0.5-1 сек/операція | ~2-5 сек/операція |
| **Пам'ять** | ~50MB | ~300MB (браузер) |
| **Стабільність** | Вища (API рівень) | Ламається при UI-змінах |
| **Audio Overview** | ✅ Повна генерація + .mp3 | ⚠️ Лише запуск |
| **Video Overview** | ✅ Повна генерація + .mp4 | ❌ |
| **Quiz/Flashcards** | ✅ + завантаження файлів | ❌ |
| **Mind Map** | ✅ JSON структура | ❌ |
| **Slide Deck** | ✅ + .pdf | ❌ |
| **Data Table** | ✅ + .csv | ❌ |
| **Список ноутбуків** | ✅ | ❌ |
| **CI/CD** | ✅ через env var | ⚠️ Потрібен запущений браузер |
| **Cloud deploy** | Легко (httpx) | Важко (headless Chromium) |

**Висновок:** Python MCP є пріоритетним. TypeScript — fallback.

---

## Завантаження артефактів — Python MCP

### Audio Overview → .mp3
```
1. notebooklm_generate_audio { notebook_id: "...", prompt: "make it engaging" }
2. Зачекати 2-5 хв (--wait автоматично)
3. notebooklm_download { notebook_id: "...", artifact_type: "audio" }
→ Файл: ~/.notebooklm/downloads/<id>_audio.mp3
```

### Video Overview → .mp4
```
1. notebooklm_generate_video { notebook_id: "...", prompt: "whiteboard" }
2. Зачекати 5-10 хв
3. notebooklm_download { notebook_id: "...", artifact_type: "video" }
→ Файл: ~/.notebooklm/downloads/<id>_video.mp4
```

### Quiz → .md (Markdown)
```
1. notebooklm_generate_quiz { notebook_id: "...", difficulty: "hard" }
2. notebooklm_download { notebook_id: "...", artifact_type: "quiz" }
→ Файл: ~/.notebooklm/downloads/<id>_quiz.md
```

### Flashcards → .json
```
1. notebooklm_generate_flashcards { notebook_id: "...", quantity: "more" }
2. notebooklm_download { notebook_id: "...", artifact_type: "flashcards" }
→ Файл: ~/.notebooklm/downloads/<id>_flashcards.json
```

### Slide Deck → .pdf
```
1. notebooklm_generate_slide_deck { notebook_id: "..." }
2. notebooklm_download { notebook_id: "...", artifact_type: "slide-deck" }
→ Файл: ~/.notebooklm/downloads/<id>_slide-deck.pdf
⚠️ Free план: watermark. Plus/Ultra: без водяного знаку.
```

---

## Встановлення Python MCP

### Локально (найшвидше)
```bash
pip install "notebooklm-py[browser]" fastmcp uvicorn
playwright install chromium
notebooklm login          # відкриває браузер один раз
python server.py          # запускає MCP сервер
```

### Render.com (хмара, безкоштовно)
```
1. Push notebooklm-python-mcp/ на GitHub
2. Render → New Web Service → Docker → обрати repo
3. Environment → NOTEBOOKLM_AUTH_JSON = <вміст storage_state.json>
4. Deploy → отримати URL
```

### CI/CD (GitHub Actions)
```yaml
- name: Setup NotebookLM auth
  run: |
    mkdir -p ~/.notebooklm
    echo "${{ secrets.NOTEBOOKLM_AUTH_JSON }}" > ~/.notebooklm/storage_state.json
```

---

## Сесія і оновлення токена

- Google session cookie живе ~30 днів
- Автооновлення CSRF токенів під час API запитів
- При закінченні: `notebooklm login` або оновити `NOTEBOOKLM_AUTH_JSON` secret

---

## Попередження щодо стабільності

`notebooklm-py` використовує недокументовані Google RPC методи з обфускованими ID.
Google може змінити ці ID без попередження.

При зламаному API:
1. `pip install --upgrade notebooklm-py` — зазвичай оновлення виходить протягом тижня
2. Тимчасово перейти на TypeScript MCP (DOM scraping)
3. Відстежити: https://github.com/teng-lin/notebooklm-py/releases
