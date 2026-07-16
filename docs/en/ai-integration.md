# Working with AI assistants

> Language: [Українською](../ua/ai-integration.md) · **English**

The lab is built for AI-assisted work: Claude / Claude Code, Codex and other services.

## Context for the assistant
- Primary context — [`../../CLAUDE.md`](../../CLAUDE.md): language, structure, conventions.
- Methodology — [`../methodology.md`](../methodology.md); plan — [`../PLAN.md`](../PLAN.md).

## Claude Code capabilities
- **Skills** — `.claude/skills/<name>/SKILL.md`; create new ones via `/skill-new`.
- **Hooks** — session events (`SessionStart`, `Stop`) via `settings.json`.
- **Subagents**, **slash commands**, **plan mode**, background tasks.

## MCP integrations
- **GitHub** — code, PRs, issues.
- **Vercel** — deploy/preview.
- **Canva** — design assets.

## Security with AI
- No secrets in prompts, skills or commits — env only.
- Least-privilege tokens. Plan and confirm before irreversible actions.
