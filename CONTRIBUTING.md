# Внесок / Contributing

**🇺🇦 Українською** · [🇬🇧 English](#-english)

Тут працюють і люди, і AI-помічники (Claude / Claude Code, Codex, інші). Детальні
конвенції — у [`docs/ua/guidelines.md`](docs/ua/guidelines.md).

## Робочий процес
1. Працюй у гілці (не в `main`).
2. Один логічний крок — один коміт; повідомлення описове.
3. Перед комітом: `pre-commit run --all-files` (встанови: `bash scripts/setup.sh`).
4. PR за шаблоном; зв'яжи з issue/експериментом.
5. Що лишаємо — виносимо в `skills/`/`automations/` і пишемо висновок у `docs/learnings.md`.

## Куди що класти
- Маленька гіпотеза → `experiments/<назва>/`
- Проєкт-зразок → `projects/<назва>/` (зі `projects/project-template/`)
- Навичка → `.claude/skills/<name>/SKILL.md` (каталог — `skills/`)
- Хук/пайплайн → `automations/`; утиліта → `scripts/`

## Мова
**Українська — канон.** EN — дзеркало, оновлюється в тому ж PR (не розходяться).
Документи й комунікація — українською; ключові терміни дублюй EN.

## Безпека
Жодних секретів у репо. CI ганяє gitleaks, Trivy, Semgrep — не обходь. Деталі — [`SECURITY.md`](SECURITY.md).

---

<a id="-english"></a>
## 🇬🇧 English

[🇺🇦 Українською](#внесок--contributing) · **English**

Both people and AI assistants (Claude / Claude Code, Codex, others) work here. Detailed
conventions live in [`docs/en/guidelines.md`](docs/en/guidelines.md).

### Workflow
1. Work on a branch (not `main`).
2. One logical step — one commit; descriptive message.
3. Before committing: `pre-commit run --all-files` (setup: `bash scripts/setup.sh`).
4. Open a PR using the template; link an issue/experiment.
5. What we keep — promote into `skills/`/`automations/` and log it in `docs/learnings.md`.

### Where things go
- Small hypothesis → `experiments/<name>/`
- Sample project → `projects/<name>/` (from `projects/project-template/`)
- Skill → `.claude/skills/<name>/SKILL.md` (catalog in `skills/`)
- Hook/pipeline → `automations/`; utility → `scripts/`

### Language
**Ukrainian is canonical.** EN mirrors it and is updated in the same PR (no drift).

### Security
No secrets in the repo. CI runs gitleaks, Trivy, Semgrep — don't bypass. See [`SECURITY.md`](SECURITY.md).
