# ai-lab · ШІ-лаб

**🇺🇦 Українською** · [🇬🇧 English](#-english)

> Центральне сховище для опрацювання багатомовних проєктів з AI-допомогою.
> Особиста **лабораторія продуктивності**: створюємо, покращуємо, спрощуємо й винаходимо
> автоматизації, навички (skills) і робочі процеси. Напрацювання зберігаються як зразки
> в `projects/` і згодом можуть виноситися в самостійні репозиторії.

## Принципи
1. **Експеримент понад усе** — гіпотеза → запуск → вимір → висновок.
2. **Українська завжди присутня** — UA-канон, EN — дзеркало з перемиканням.
3. **Автоматизації як код** — версіонуються, рев'юяться, тестуються.
4. **Одна автоматизація — одна задача** (без шуму).
5. **Безпека за замовчуванням** — жодних секретів у репо, автоматичні перевірки.
6. **Знання накопичуються** — журнал висновків компаундиться.

## Структура
| Шлях | Призначення |
|------|-------------|
| `docs/` | Методологія, дорожня карта, план, журнал висновків, глосарій |
| `docs/ua/`, `docs/en/` | Білінгвальний онбординг (setup, guidelines, ai-integration) |
| `projects/` | Самостійні проєкти-зразки (з `project-template/`) |
| `experiments/` | Маленькі експерименти-гіпотези |
| `skills/`, `.claude/skills/` | Навички Claude Code (індекс / канонічні активні) |
| `melania-skills-ecosystem/` | Бібліотека 27 AI-навичок (активні через симлінки в `.claude/skills/`) |
| `automations/`, `scripts/` | Хуки, пайплайни, утиліти |
| `security/`, `.github/` | Конфіги безпеки, CI/CD, CODEOWNERS, шаблони |

## Швидкий старт
1. `bash scripts/setup.sh` — встановити `pre-commit` і хуки.
2. Прочитай [`docs/ua/setup.md`](docs/ua/setup.md) і [`docs/ua/guidelines.md`](docs/ua/guidelines.md).
3. Глянь план [`docs/PLAN.md`](docs/PLAN.md) і беклог [`docs/roadmap.md`](docs/roadmap.md).
4. Створи навичку (`/skill-new`), експеримент ([`templates/experiment.md`](templates/experiment.md))
   або проєкт ([`projects/project-template/`](projects/project-template/)).

## Безпека та якість
Жодних секретів у репо. CI: **gitleaks** (секрети), **Trivy** (вразливості/місконфіги),
**Semgrep** (SAST), **dependency-review**; локально — **pre-commit**; залежності — **Dependabot**.
Деталі — [`SECURITY.md`](SECURITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Melania Skills Ecosystem
Бібліотека [`melania-skills-ecosystem/`](melania-skills-ecosystem/README-FOR-HUMANS.md) —
27 AI-навичок (керування навичками, валідація, оркестрація, браузерна автоматизація,
деплой, тестування, пам'ять між сесіями тощо) під master-протоколом
`melania-skill-master-administrator`. Підключені як активні проєктні навички через
симлінки в `.claude/skills/`, тож підхоплюються в цьому проєкті автоматично.
Деталі: [README-FOR-HUMANS](melania-skills-ecosystem/README-FOR-HUMANS.md) (для людей) ·
[README-FOR-AI](melania-skills-ecosystem/README-FOR-AI.md) (для AI-асистентів).

## Інструменти
Claude Code (навички, субагенти, хуки, slash-команди, plan mode) + MCP:
**GitHub**, **Vercel**, **Canva**. AI-помічники: Claude / Claude Code, Codex, інші.

## Ліцензія
Apache License 2.0 — див. [`LICENSE`](LICENSE).

---

<a id="-english"></a>
## 🇬🇧 English

[🇺🇦 Українською](#ai-lab--ші-лаб) · **English**

> Central repository for multilingual, AI-assisted work. A personal **productivity lab**:
> we create, improve, simplify and invent automations, skills and workflows. Work is stored
> as samples in `projects/` and may later be spun out into standalone repositories.

### Principles
1. **Experiment first** — hypothesis → run → measure → conclusion.
2. **Ukrainian always present** — UA is canonical, EN mirrors it with switching.
3. **Automations as code** — versioned, reviewed, tested.
4. **One automation — one job** (no noise).
5. **Secure by default** — no secrets in the repo, automated checks.
6. **Knowledge compounds** — the learnings log grows over time.

### Structure
| Path | Purpose |
|------|---------|
| `docs/` | Methodology, roadmap, plan, learnings, glossary |
| `docs/ua/`, `docs/en/` | Bilingual onboarding (setup, guidelines, ai-integration) |
| `projects/` | Standalone sample projects (with `project-template/`) |
| `experiments/` | Small hypothesis experiments |
| `skills/`, `.claude/skills/` | Claude Code skills (index / canonical active) |
| `melania-skills-ecosystem/` | Library of 27 AI skills (active via symlinks in `.claude/skills/`) |
| `automations/`, `scripts/` | Hooks, pipelines, utilities |
| `security/`, `.github/` | Security configs, CI/CD, CODEOWNERS, templates |

### Quick start
1. `bash scripts/setup.sh` — install `pre-commit` and hooks.
2. Read [`docs/en/setup.md`](docs/en/setup.md) and [`docs/en/guidelines.md`](docs/en/guidelines.md).
3. See the plan [`docs/PLAN.md`](docs/PLAN.md) and backlog [`docs/roadmap.md`](docs/roadmap.md).
4. Create a skill (`/skill-new`), an experiment, or a project from the template.

### Security & quality
No secrets in the repo. CI: **gitleaks**, **Trivy**, **Semgrep** (SAST), **dependency-review**;
locally — **pre-commit**; dependencies — **Dependabot**. See [`SECURITY.md`](SECURITY.md).

### Melania Skills Ecosystem
The [`melania-skills-ecosystem/`](melania-skills-ecosystem/README-FOR-HUMANS.md) library —
27 AI skills (skill management, validation, orchestration, browser automation, deployment,
testing, cross-session memory, etc.) governed by the `melania-skill-master-administrator`
protocol. Wired as active project skills via symlinks in `.claude/skills/`, so they are
picked up automatically in this project.
Details: [README-FOR-HUMANS](melania-skills-ecosystem/README-FOR-HUMANS.md) (for humans) ·
[README-FOR-AI](melania-skills-ecosystem/README-FOR-AI.md) (for AI assistants).

### License
Apache License 2.0 — see [`LICENSE`](LICENSE).
