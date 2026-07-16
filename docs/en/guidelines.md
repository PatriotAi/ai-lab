# Lab conventions

> Language: [Українською](../ua/guidelines.md) · **English**

## Language
- **Ukrainian is the source of truth.** EN mirrors it, updated in the same PR.
- Work logs (`roadmap`, `learnings`, `PLAN`) are UA-canonical, no mandatory EN mirror.
- Onboarding docs (`setup`, `guidelines`, `ai-integration`) are bilingual `ua/` + `en/` pairs.

## Work cycle
Hypothesis → design → run → measure → **keep/drop** → log in `../learnings.md`.
Vertical slice first, then expand. See [`../methodology.md`](../methodology.md).

## Where things go
- Hypothesis → `experiments/`; sample project → `projects/`.
- Skill → `.claude/skills/<name>/SKILL.md`; hook/pipeline → `automations/`; utility → `scripts/`.

## Rules
- **One automation — one responsibility.** No duplicates, no noise.
- **No secrets** — env only (see [`../../SECURITY.md`](../../SECURITY.md)).
- Each skill/automation = a folder with a short README/SKILL.md and a clear trigger.
- Plan before large/irreversible changes (plan mode).
