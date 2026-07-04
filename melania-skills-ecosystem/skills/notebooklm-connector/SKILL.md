---
name: notebooklm-connector
description: "Full integration with Google NotebookLM: read sources, add URLs and files, merge all sources into one document, generate Audio Overview, Video Overview, Briefing Doc, Study Guide, FAQ, Timeline, Mind Map, Slide Deck, Infographic, Flashcards, Quizzes, Deep Research, and Chat with citations. ALWAYS use this skill when user mentions notebook or notebooklm, shares a notebooklm.google.com link, or says dodai do notebook, vytahny z notebook, obiednai dzherela, analizui notebook. Even without the word notebooklm: use when user wants to merge research sources, generate a podcast from documents, build a knowledge base, or analyze sources with cited answers. Also triggers for: collaborative browser, спільний браузер, відкрий браузер. DO NOT use for plain Google Docs tasks with no NotebookLM involvement."
license: Proprietary
metadata:
  version: 4.2.3
  author: Melania (Master Administrator)
  category: knowledge
  created: 2026-03-20
  last_updated: 2026-06-02
---

# NotebookLM Connector — v4
> Українською-перша: відповіді, пояснення й нотатки — українською за замовчуванням; UI-шляхи NotebookLM лишаються як є. Перемикання мови лише слідом за користувачем.
>
> **Неофіційний.** Не пов'язаний з, не схвалений і не спонсорований Google. «NotebookLM» — продукт і торгова марка Google; назва вжита суто референційно (опис сумісності).


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Core Rule

NotebookLM has no public API. Known constant — never stop to explain it. Cascade.

---

## Step 0 — Pre-flight

```
MODES:
  A  READ / EXTRACT  — notebooklm.google.com URL given
  B  ADD SOURCES     — URLs, files, or text to import
  C  GENERATE        — any Studio feature
  D  CHAT ANALYSIS   — ask questions, cited answers
  E  FILES / CONTEXT — format chat context or uploads for NotebookLM
  F  COLLAB BROWSER  — "відкрий браузер" / "collaborative browser"

METHOD PRIORITY (check in order, use first available):
  1. notebooklm_* MCP tools  — Python MCP, 19 tools, Google RPC, downloads .mp3/.mp4/.pdf
  2. browserbase_* tools     — Cloud Browser MCP, 12 tools, screenshot every action ★ Android
  3. Collaborative Browser   — React Artifact, MODE F, Anthropic API, BroadcastChannel
  4. web_fetch               — for public sources
  5. React Artifact OAuth    — Google cookies, all devices
  6. Guided Manual           — explicit request or last resort

NEVER require npm / terminal / extensions on user device.
```

---

## Step 1 — Access Methods

### 1A — Python MCP (notebooklm_*)

Check for `notebooklm_session_status` or `notebooklm_authenticate`.
Read `references/python-mcp-advantage.md` for full tool list.

```
notebooklm_session_status          → check health, days remaining, refresh guide
notebooklm_authenticate            → login or confirm

By task:
  open / check      → open_notebook(url)  # has_access check before any read
  read / merge      → get_all_content(url)
  one source        → list_sources → get_source_content(url, id)
  notes             → get_notes(url)
  briefing          → generate_briefing(url)
  chat              → chat_query(url, query)
  add source        → add_source(url, source_url)
  audio / .mp3      → generate_audio(url) → download(url, "audio")
  video / .mp4      → generate_video(url) → download(url, "video")
  quiz              → generate_quiz(url, difficulty)
  flashcards        → generate_flashcards(url)
  mind map          → generate_mind_map(url)
  slide deck / .pdf → generate_slide_deck(url) → download(url, "slide-deck")
  all notebooks     → list_notebooks()
  inject cookies    → notebooklm_inject_cookies { cookies_json: "<paste>" }
```

### 1B — Browserbase Cloud Browser (browserbase_*)

★ Primary for Android. Screenshots after every action.
Setup guide: `references/browserbase-android-setup.md`

```
browserbase_authenticate { storage_json: "<cookies>" }   # once
notebooklm_browse_open(url)                              # → screenshot
notebooklm_browse_sources(url)                           # extract all
notebooklm_browse_studio(url, feature)                   # Briefing/Audio/Quiz
notebooklm_browse_chat(url, query)                       # → screenshot
browserbase_screenshot()                                 # ← always after action

Raw browser control (when needed):
  browserbase_navigate(url)          # go to any URL
  browserbase_click(selector, by_text=true)  # click by text or CSS
  browserbase_type(selector, text)   # fill input fields
  browserbase_extract(instruction)   # extract content from page
  browserbase_scroll(direction)      # down/up/bottom/top
  browserbase_wait(selector, ms)     # wait for element or timeout
```

### 1C — Collaborative Browser Artifact (MODE F)

Trigger phrases: "відкрий браузер", "collaborative browser", "спільний браузер",
or whenever web content needs interactive real-time fetching.

Generate `collaborative-browser.jsx` React Artifact with:
- Anthropic API-powered navigation (askClaude fetches + summarizes pages)
- Language switcher: 🇺🇦 UK · 🇬🇧 EN · 🇩🇪 DE · 🇫🇷 FR · 🇵🇱 PL · 🇪🇸 ES
- Page translation button (⟷) — translates loaded content to UI language via Claude API
- BroadcastChannel multiplayer — real-time sync across tabs
- window.storage — bookmarks, notes, history, Google cookies persist
- Autopilot — multi-step research chains
- Command Palette ⌘K — 15+ actions including language/translation commands
- Quick Actions bar — NotebookLM + Canva/Gmail/Calendar/Vercel
- Agent panel — commands via Anthropic API, sendPrompt() to Claude
- Cookie injection modal — accepts Cookie Editor JSON for Android auth

The i18n system covers all UI strings in 6 languages.
Page translation detects source language and translates via Claude.
Translation bar shows all target languages for quick switching.

Full artifact source: `collaborative-browser.jsx` (already built)

### 1D — React Artifact + Google OAuth

Triggers: 401/403, no MCP tools, cloud agent context.
Apply `frontend-design` skill — "Mission Control" dark aesthetic.
States: idle → auth → extracting → done → manual_fallback.
sendPrompt() returns content automatically. Persists via window.storage.
Full component: `references/universal-auth-artifact.md`

> 🔗 **Канонічні auth-патерни** (cookie-видобування/інʼєкція, OAuth-схема, моніторинг сесій, AES-GCM) тепер консолідовано у скілі **`auth-session-manager`**. Кроки 1A–1F нижче — NotebookLM-специфіка; за загальними деталями авторизації звертайся туди, щоб не дублювати.

### 1E — Direct Fetch + Adding Sources (MODE B)

```
web_fetch(url) → success → Step 2 | 403 → cascade to 1A/1B/1D

Adding sources (all parallel):
  webpage → web_fetch + clean | pdf → extract or link
  youtube → URL direct (public) | gdoc → check sharing first
  github  → README + /docs
Blocked doc: continue others → request sharing → auto-return when granted
```

### 1F — Guided Manual (last resort)

```
Mobile:  ⋮ → View source → long-tap Select All → paste
Desktop: Studio → Briefing Doc → copy → paste
Any:     Screenshot → attach → Claude extracts text
```

---

## Step 2 — Decision Engine

```python
merge / combine / один документ   → execute_merge()        # Step 3, no delay
generate / overview / studio feat. → feature_generator()   # Step 4
analysis / analyze / порівняй      → chain_analysis()      # Step 5
browser / відкрий браузер           → collab_browser()     # Step 1C

# Auto-suggest (announce first):
sources >= 3       → Audio Overview
academic content   → Study Guide
business content   → Briefing Doc
dated events       → Timeline
technical docs     → FAQ
```

---

## Step 3 — Merge All Sources

```
1. Collect: MCP / Browserbase / Artifact / web_fetch / uploads / chat context
2. Detect: theme → sub-themes → sections → remove duplicates
3. Output format:
   .docx / "Word document" → invoke docx skill after merge → deliver both .md + .docx
   .pptx / "presentation"  → invoke pptx skill → theme-factory if style requested
   default                 → Markdown
4. Build with template below
5. NotebookLM prep: <500k chars → Copied text | >500k → split with cross-refs
```

```markdown
# [TITLE]
Compiled: [date] | Sources: [N] | Words: [N]

## Table of Contents
[auto]

## [Section — theme]
> Source: [title / URL]
[content]

## Synthesis and Key Findings
[cross-source synthesis]

## Source Index
| # | Title | Type | Origin | Date |
```

---

## Step 4 — Feature Generator (Studio Survey)

Read `references/notebooklm-capabilities.md` FIRST — features change frequently.

Ask ALL survey questions in ONE message:
```
1. Goal?       Learning / Research / Business / Personal
2. Audience?   Myself / Team / Students / Clients
3. Time?       5 min / 15 min / deep study
4. Outputs?    Audio Overview / Video Overview / Briefing Doc / Study Guide /
               FAQ / Timeline / Mind Map / Slide Deck / Infographic /
               Flashcards+Quiz / Deep Research / Chat analysis
5. Language?   (35+ supported)
6. Persona?    optional — e.g. "strict PM, Decision Memo format only"
```

Build plan autonomously. Provide exact UI path per feature:

```
AUDIO OVERVIEW   Studio → Audio Overview → format (Brief/Deep Dive/Critique/Debate)
                 → Customize (focus, audience) → Generate
                 Interactive Mode: click Join during playback → ask live questions
VIDEO OVERVIEW   Studio → Video Overview → Generate (~5-10 min)
BRIEFING DOC     Studio → Briefing doc → Generate (30-60 sec)
STUDY GUIDE      Studio → Study guide → Generate
FAQ              Studio → FAQ → Generate
TIMELINE         Studio → Timeline → Generate
MIND MAP         Studio → Mind map → Generate (interactive)
SLIDE DECK       Studio → Slide deck → Generate (Free = watermark)
INFOGRAPHIC      Studio → Infographic → Generate
FLASHCARDS+QUIZ  Studio → Flashcards / Quiz → Generate
DEEP RESEARCH    Studio → Deep Research (agentic — searches web beyond sources)
CHAT PERSONA     Chat → ⚙ → persona prompt up to 10,000 chars
DISCOVER SOURCES + Add source → Discover Sources → topic search
```

End Step 4 with 5 targeted Chat queries specific to content.

---

## Step 5 — Deep Analysis

```
1. Get all content (MCP / Browserbase / Artifact / manual)
2. Analyze: themes, contradictions, key insights, data points
3. Generate 5+ targeted Chat queries for NotebookLM
4. Optionally produce local Briefing Doc before adding to Notebook
```

---

## Step 6 — Import to NotebookLM

Always AFTER producing output, not instead of it:
```
notebooklm.google.com → Notebook → + Add source → Copied text
→ Paste [file] | Title: [SUGGESTED] | Insert | Wait 30-60 sec
→ Recommended next: [feature based on content type]
```

---

## Source Queue

```
done            — processed
awaiting_access — waiting for sharing permission → auto-retry when granted
failed          — paywall / 404 / unavailable
pending         — queued
```

---

## Behavior Rules

| Situation | Do | Never |
|---|---|---|
| 403 from Google | Cascade methods 1A→1F | Stop + explain API |
| MCP absent | Silently use Browserbase or Artifact | Report as error |
| Android user | Browserbase ★ → Cookie Editor guide → screenshots | "Not possible on mobile" |
| Cookies pasted | inject_cookies → verify → retry | Ask to use desktop |
| session days < 7 | Warn + show Android guide proactively | Wait for failure |
| notebooklm_session_status shows needs_refresh | Immediately show Cookie Editor steps | Continue silently |
| days_remaining returns negative | Session expired — block and require re-auth | Try operations anyway |
| "відкрий браузер" | Generate collaborative-browser.jsx Artifact | Text-only response |
| Collab Browser active | Use sendPrompt() content, trust BroadcastChannel | Ignore Artifact data |
| Language switch | Apply T[lang] across all UI, persist to storage, broadcast | Mix languages |
| Page translate request | translatePage(lang) via Claude API, show translation bar | Use external service |
| Merge task | Start immediately, no questions | Ask how to get data |
| Multiple URLs | All parallel | Sequential with permission |
| Generation request | Survey (one message) → plan → exact UI steps | Guess one feature |
| Feature list unsure | Read capabilities file first | Assume old feature set |
| .docx requested | docx skill after merge | Plain markdown only |
| .pptx requested | pptx skill + theme-factory | Plain markdown only |
| Download artifact | generate → download tool → return path | Stop at "generated" |
| Blocked Google Doc | Continue others + request sharing | Stop entire operation |

---

## References

- `references/notebooklm-capabilities.md` — Current features, limits, source types (read before Step 4)
- `references/python-mcp-advantage.md` — 19-tool Python MCP, downloads .mp3/.mp4/.pdf
- `references/browserbase-android-setup.md` — Android setup, Browserbase, Smithery, agent loop
- `references/android-cookie-extraction.md` — Cookie Editor, Remote Debug, session refresh
- `references/universal-auth-artifact.md` — React + Google OAuth component (Mission Control UI)
- `references/mcp-server-deployment.md` — Render / Vercel / VPS deploy guide
- `references/platform-matrix.md` — Device compatibility + language support matrix
- `references/collaborative-browser-artifact.md` — Collab Browser i18n + feature spec
- `references/content-processors.md` — Processing algorithms by content type

---

## 📎 Advanced Patterns (v4)

Read `references/citation-workflow.md` WHEN you need: citation extraction, source comparison, multi-source synthesis, export strategies.
Load only on demand — not proactively.

---

## Зміни
- **v4.2.3** (2026-06-26) — Stage 3: **S-3** `evals/` відновлено (6 реальних кейсів v3.0.0 з форензик-пошуку: read-notebook-url, add-multiple-sources, feature-generator-survey, mobile-friendly-instructions, deep-research-new-feature, context-chat-export; канон-схема). **S-2** дубльовану секцію «Зміни» + дубль v4.2.0 консолідовано (вміст збережено). Відновлення + консолідація.
- **v4.2.2** (2026-06-15) — B2 (safety-compliance-gate): дисклеймер неприналежності — NotebookLM (Google).
- **v4.2.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна.
- **v4.2.0** (2026-06-02) — batch source import guide; output quality control table; Pre-Update Preservation Protocol; citation-workflow reference (citation extraction, source comparison, synthesis). _(консолідовано з двох записів)_
- **v4.0.0** (2026-06-02) — `metadata`-блок (версія машиночитана) + директива «українською-перша». evals/guard уже були. _(аудит Кластер 3: metadata + P9)_
