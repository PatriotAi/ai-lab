# session-start — підвантаження контексту сесії

SessionStart-хук: на старті кожної сесії додає в контекст робочий дайджест
лабораторії й best-effort активує `pre-commit`.

## Що робить
- Виводить дайджест: мова (UA-канон) + безпека, активні навички, статус
  `docs/PLAN.md` (фази), останній запис `docs/learnings.md`, нагадування про цикл.
- Якщо `pre-commit` доступний — `pre-commit install` (тихо, best-effort).
- Якщо `pre-commit` відсутній — нагадує запустити `scripts/setup.sh`.

## На що реагує
- Подія `SessionStart` (start / resume / clear / compact).

## Як активовано
- Через `.claude/settings.json` → `hooks.SessionStart` →
  `$CLAUDE_PROJECT_DIR/automations/session-start/session-start.sh`.

## Як вимкнути
- Прибрати блок `SessionStart` у `.claude/settings.json`.

## Нотатки
- Ідемпотентний, неінтерактивний; контекст віддається через
  `hookSpecificOutput.additionalContext` (fallback — звичайний stdout).
- **Не** чіпає платформні хуки в `~/.claude` (`session-start-git-identity` тощо) —
  він додатковий, не заміна.
- Одна автоматизація — одна відповідальність (підвантаження контексту).
