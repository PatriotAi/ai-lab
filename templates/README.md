# templates/ — шаблони

Шаблони для швидкого, консистентного старту. Копіюй і заповнюй.

| Шаблон | Для чого |
|--------|----------|
| [`experiment.md`](experiment.md) | Новий експеримент у `experiments/<назва>/README.md` |
| [`skill.md`](skill.md) | Нова навичка у `skills/<name>/SKILL.md` |
| [`nextjs-app.md`](nextjs-app.md) | Чек-лист якості Next.js-застосунку з LLM API (новий чи успадкований репо) |
| [`ci/repo-check.yml`](ci/repo-check.yml) | Перевірка при заливанні (push/PR) для будь-якого репо: секрети + Node lint/build/test + Python-канарки — копія в `.github/workflows/repo-check.yml` (рядок `sync` звіряє монітор, RH14) |
