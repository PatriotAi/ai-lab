# session-start — підвантаження контексту сесії

SessionStart-хук: на старті кожної сесії додає в контекст робочий дайджест
лабораторії. Єдина відповідальність — контекст; бутстрап — `scripts/setup.sh`.

## Що робить
- Виводить дайджест: мова (UA-канон) + безпека, активні навички, статус
  `docs/PLAN.md` (фази), останній запис `docs/learnings.md`, нагадування про цикл.
- Якщо `pre-commit` відсутній — нагадує запустити `scripts/setup.sh` (сам не встановлює).
- **Радар розходження** (`scripts/check-main-drift.py --fetch --quiet --branches --inflight`,
  з 2026-10-09): main, що пішов уперед у файлах гілки; незлиті гілки з тими самими файлами;
  карта паралельної незлитої роботи. Друкує лише знахідки; мережа — лише на `fetch` з тайм-аутом
  (без мережі — по застарілих посиланнях, з позначкою); збій не ламає старт сесії. Навіщо —
  виміряний дубль F-17, `docs/reviews/2026-10-09-git-substrate-audit.md`.

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
