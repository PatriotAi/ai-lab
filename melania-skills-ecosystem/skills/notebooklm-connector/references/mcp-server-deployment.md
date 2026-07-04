# MCP Server Deployment — Quick Reference

## Three servers, one goal: Claude accesses NotebookLM from any device

| Server | Lang | Tools | Best for | Deploy |
|---|---|---|---|---|
| `notebooklm-python-mcp` | Python | 19 | Desktop, CI/CD, .mp3/.mp4/.pdf | Render / local |
| `notebooklm-browserbase-mcp` | TypeScript | 12 | Android ★, screenshots | Render / Smithery |
| `notebooklm-mcp-server` | TypeScript | 10 | Local Playwright, headless | Local only |

---

## Option 1 — Python MCP (recommended, 19 tools)

```bash
# Local
pip install "notebooklm-py[browser]" fastmcp uvicorn
playwright install chromium
notebooklm login     # browser opens once
python server.py     # stdio for Claude Desktop
```

Claude Desktop `claude_desktop_config.json`:
```json
{ "mcpServers": { "notebooklm": { "command": "python", "args": ["/path/to/server.py"] } } }
```

Render.com (cloud): push `notebooklm-python-mcp/` to GitHub → Render → Docker.
Env vars: `NOTEBOOKLM_AUTH_JSON` = contents of `~/.notebooklm/storage_state.json`

---

## Option 2 — Browserbase MCP (Android ★, screenshots)

1. Register at browserbase.com → get `BROWSERBASE_API_KEY` + `BROWSERBASE_PROJECT_ID`
2. Push `notebooklm-browserbase-mcp/` to GitHub → Render → Node runtime
3. Env vars: `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`, `GOOGLE_STORAGE_STATE`

OR via Smithery (no deploy needed):
- smithery.ai → search Browserbase → Configure → enter API keys → get URL

Connect to claude.ai: Settings → Integrations → Add MCP → paste URL/mcp

---

## Option 3 — TypeScript MCP (local Playwright)

```bash
cd notebooklm-mcp-server
npm install && npx playwright install chromium
npm run dev       # local only, requires headless Chromium
```

---

## Authentication — all servers

**First login:**
```
notebooklm_authenticate → returns login_url
→ open in browser → sign in to Google
notebooklm_authenticate { confirm: true } → session saved (~30 days)
```

**Android refresh (when cookies expire):**
```
Cookie Editor app → notebooklm.google.com → Export JSON
notebooklm_inject_cookies { cookies_json: "<paste>" }
```

**Health check:**
```
GET https://your-server.onrender.com/health
→ {"status":"ok","server":"...","version":"1.0.0"}
```

**Render free plan cold start:** ~30 sec after 15 min idle.
Fix: UptimeRobot → ping /health every 10 min (free).
