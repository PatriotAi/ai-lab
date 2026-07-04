# Collaborative Browser Artifact — Reference

## When to generate

Trigger: "відкрий браузер", "collaborative browser", "спільний браузер",
or any task requiring interactive web research with real-time feedback.

## File: collaborative-browser.jsx (already in outputs)

## Features

### i18n — 6 languages
- Language switcher button in topbar: flag + code + ▾
- Dropdown: 🇺🇦 Українська / 🇬🇧 English / 🇩🇪 Deutsch / 🇫🇷 Français / 🇵🇱 Polski / 🇪🇸 Español
- All 40+ UI strings translated per language (T.uk, T.en, T.de, T.fr, T.pl, T.es)
- Persisted: window.storage key "cb:lang"
- BroadcastChannel synced across tabs: { type: "lang", code }

### Page translation
- Button ⟷ Translate appears after page loads
- Calls askClaude() to translate pageContent to UI language
- Translation bar shows: status + all other language flags for quick switch
- Original detected language shown as badge (e.g. "EN")
- Restore original: click ✕ in translation bar or re-click ⟷

### Navigation
- URL bar + Enter / ↺ refresh button
- askClaude() fetches + summarizes: returns TITLE / LANG / CONTENT
- Source language auto-detected in LANG field

### Multiplayer (BroadcastChannel)
- Channel: "nlm-collab-browser-v3"
- Syncs: navigate, agent messages, language switch
- Peer count badge shows connected tabs

### Persistent storage (window.storage)
- bookmarks (cb:bookmarks), notes (cb:notes), history (cb:history)
- cookies (cb:google-cookies), lang (cb:lang)

### Quick Actions bar
N Notebook | M Merge | B Briefing | A Audio | Q Quiz
C Canva | G Gmail | K Calendar

Each → sendPrompt(command + page content)

### Command Palette ⌘K
15 commands + all translate/language commands per language

### Autopilot
- prompt() for task → Claude builds 3-5 step plan → executes → sendPrompt(synthesis)

### Agent panel
- Commands via askClaude() → agent log → sendPrompt() if needed
- Shows peer count, agent busy state

### Cookie modal
- Paste Cookie Editor JSON → saved to window.storage + sent to notebooklm_inject_cookies

## Design system (frontend-design)
Dark navy #0c0e14, topbar #141720, glassmorphism panels
Google Blue #4285F4, Emerald #10b981, Amber #f59e0b, Rose #ef4444
Minimal 1px borders, system font, 4px scrollbars
