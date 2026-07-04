# Platform Compatibility Matrix

## Method availability by device

| Method | Android | iOS | Desktop | ChromeOS | Cloud agent |
|---|---|---|---|---|---|
| Python MCP (19 tools) | ✅ via Render | ✅ via Render | ✅ local+remote | ✅ remote | ✅ |
| Browserbase MCP (12 tools) | ✅ ★ | ✅ | ✅ | ✅ | ✅ |
| Collaborative Browser Artifact | ✅ | ✅ | ✅ | ✅ | ✅ |
| React Artifact + Google OAuth | ✅ | ✅ | ✅ | ✅ | ✅ |
| TypeScript MCP (Playwright) | ❌ | ❌ | ✅ local | ❌ | ❌ |
| web_fetch direct | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cookie Editor injection | ✅ | ✅ | ✅ | ✅ | via env var |

## Android optimal path

```
Cookie Editor (Play Store) → export cookies → notebooklm_inject_cookies
+ Browserbase MCP (Smithery, no deploy) → screenshot every action
```

## Language support (Collaborative Browser)

UI: 🇺🇦 UK · 🇬🇧 EN · 🇩🇪 DE · 🇫🇷 FR · 🇵🇱 PL · 🇪🇸 ES
Page translation: any language supported by Claude API
Storage: window.storage persists language preference

## NotebookLM language support
35+ languages for content and generated features.
Chat responds in the language of the query.
Audio Overview: primarily English (UI language).

## Method selection rule

```
1. ALWAYS try Python MCP first (deepest access, downloads)
2. Android / no local install → Browserbase MCP
3. Web fetching / research → Collaborative Browser Artifact
4. Auth needed, no MCP → React Artifact OAuth
5. Manual only → Guided Manual (paste)
NEVER: require npm/terminal/extensions on user device
```
