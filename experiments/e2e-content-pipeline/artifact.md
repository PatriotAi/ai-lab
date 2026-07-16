# SessionStart-хуки Claude Code: робочий контекст щосесії

> 🇺🇦 Українською (канон) · [🇬🇧 English ▸](#claude-code-sessionstart-hooks-working-context-in-every-session)

**Теза:** хук (hook) — це детермінований контроль: потрібний контекст
підвантажується **щосесії гарантовано**, а не «якщо модель згадає».

## Що це
`SessionStart` — подія життєвого циклу Claude Code. Хук на неї спрацьовує на
`startup` (нова сесія), `resume` (продовження), `clear` (`/clear`) і `compact`
(стискання контексту). Тобто контекст повертається навіть після очищення чи
компакції — саме тоді він і губиться найчастіше.

## Як віддати контекст
Два способи:
1. **Plain stdout** — увесь вивід додається в контекст сесії.
2. **JSON** — `hookSpecificOutput.additionalContext`: текст обгортається
   системним нагадуванням і потрапляє в розмову перед першим промптом.

## Конфігурація і межі
- Реєстрація: `.claude/settings.json` (проєктний) або `~/.claude/settings.json`
  (користувацький); тип `command`.
- Хук **синхронний** — блокує старт сесії; таймаут за замовчуванням 600 с.
  Рекомендація з документації: «SessionStart runs on every session, so keep
  these hooks fast» — тримай хук швидким.

## Кейс ai-lab
`automations/session-start/` — ~50 рядків bash: дайджест (мова UA-канон,
правила безпеки, активні навички, статус фаз `PLAN`, останній запис журналу
висновків); якщо `pre-commit` відсутній — нагадує про `scripts/setup.sh`
(єдина відповідальність — контекст). Результат: кожна сесія стартує
вже «в темі», без ручного переказування контексту.

## Висновок
Один маленький хук закриває «холодний старт»: конвенції, стан плану і пам'ять
лабораторії присутні з першої секунди сесії. Мінімум коду — максимум
детермінованості.

**Джерела:** [Hooks reference](https://code.claude.com/docs/en/hooks) ·
[Hooks guide](https://code.claude.com/docs/en/hooks-guide) ·
кейс `automations/session-start/` (цей репозиторій).

---

# Claude Code SessionStart hooks: working context in every session

> [🇺🇦 Українською ▸](#sessionstart-хуки-claude-code-робочий-контекст-щосесії) · 🇬🇧 English

**Thesis:** a hook is deterministic control: the context you need is loaded
**reliably in every session**, not "if the model remembers to".

## What it is
`SessionStart` is a Claude Code lifecycle event. A hook on it fires on
`startup` (new session), `resume`, `clear` (`/clear`), and `compact` (context
compaction). So the context comes back even after clearing or compaction —
exactly when it usually gets lost.

## Returning context
Two ways:
1. **Plain stdout** — everything printed is added to the session context.
2. **JSON** — `hookSpecificOutput.additionalContext`: the text is wrapped in a
   system reminder and injected into the conversation before the first prompt.

## Configuration and limits
- Registered in `.claude/settings.json` (project) or `~/.claude/settings.json`
  (user); type `command`.
- The hook is **synchronous** — it blocks session start; default timeout is
  600 s. The docs advise: "SessionStart runs on every session, so keep these
  hooks fast."

## The ai-lab case
`automations/session-start/` — ~50 lines of bash: a digest (UA-canon language
rule, security rules, active skills, `PLAN` phase statuses, the latest
learnings log entry); if `pre-commit` is missing it points to
`scripts/setup.sh` (single responsibility — context only). Result: every
session starts already "in context", with no manual recap.

## Takeaway
One small hook closes the "cold start": conventions, plan state, and the lab's
memory are present from the first second of a session. Minimal code — maximal
determinism.

**Sources:** [Hooks reference](https://code.claude.com/docs/en/hooks) ·
[Hooks guide](https://code.claude.com/docs/en/hooks-guide) ·
the `automations/session-start/` case (this repository).
