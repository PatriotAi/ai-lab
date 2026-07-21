# Дорожня карта основ GitHub (GitHub Essentials) — UA-конспект

> Джерело: серія GitHub Blog «GitHub for Beginners» (зокрема оглядова стаття
> «Your roadmap to mastering the GitHub essentials»). Прямий доступ до github.blog
> із цього середовища може блокуватись (403/egress) — зміст відновлено пошуком
> 2026-07-21; за потреби звіряй за посиланнями нижче.
> Використання: витягай ЛИШЕ потрібний модуль для пояснення користувачу (економно).

## Логіка прогресії
Від «що таке репозиторій?» → до співпраці на реальних проєктах і внеску в open source.
Кожен модуль самодостатній: можна читати послідовно або стрибнути в потрібний.

## Модулі дорожньої карти

### 1. Версійний контроль і Git (version control)
- Версійний контроль = система, що відстежує зміни файлів у часі; Git — найпоширеніша.
- Ключові поняття: commit (знімок змін), history (історія), diff (різниця).
- Побутове пояснення: «зберігання гри» — можна повернутись до будь-якого збереження.

### 2. Репозиторії (repositories)
- Repo = простір, де живуть файли проєкту + вся історія + налаштування співпраці.
- Створення першого репо, README, .gitignore, ліцензія, публічний/приватний.
- Стаття: «Beginner's guide to GitHub repositories».

### 3. Ключові git-команди
- Мінімальний набір: clone, status, add, commit, push, pull, branch, checkout/switch,
  merge, log, diff, revert.
- Побутове пояснення: push = «відправити зміни на сервер», pull = «забрати свіже».

### 4. Гілки та злиття (branches & merge)
- Гілка = паралельна лінія роботи, main = канонічна.
- Потік: гілка → зміни → PR → рев'ю → merge. Merge-конфлікти: що це і як розв'язати.

### 5. Pull Requests (PR)
- PR = пропозиція злити зміни + місце обговорення/рев'ю + прогін CI.
- Хороший PR: маленький, з описом «що і навіщо», прив'язаний до issue.

### 6. Markdown
- Мова розмітки GitHub: README, issues, PR, коментарі, профіль.
- Стаття: «Getting started with Markdown».

### 7. Issues та Projects
- Issue = одиниця роботи/проблеми; Projects = дошка для відстеження (канбан).
- Створення issue, синхронізація з дошкою Projects, шаблони issue.
- Стаття: «Getting started with GitHub Issues and Projects».

### 8. GitHub Actions (CI/CD)
- Автоматичні перевірки/збірки на кожен push/PR (workflow-файли в `.github/workflows/`).
- Побутове пояснення: «робот, що сам перевіряє зміни й каже зелене/червоне».

### 9. GitHub Pages
- Безкоштовний сайт прямо з репозиторію (документація, портфоліо).
- Стаття: «Getting started with GitHub Pages».

### 10. Безпека (security)
- Захист профілю (2FA), секрети НЕ в коді, secret scanning, Dependabot (оновлення
  залежностей), branch protection (захист main).

### 11. Copilot та AI-помічники
- Copilot Chat, code review від AI — прискорення, але рев'ю людини лишається.

### 12. Profile README та внесок у open source (OSS)
- Профіль-візитівка; перший внесок: fork → гілка → PR у чужий проєкт.
- Стаття: «Getting started with OSS contributions».

## Посилання (звіряти за потреби)
- Оглядова: https://github.blog/developer-skills/github/github-for-beginners-your-roadmap-to-mastering-the-github-essentials/
- Тег серії: https://github.blog/tag/github-for-beginners/
- Репозиторії: https://github.blog/developer-skills/github/beginners-guide-to-github-repositories-how-to-create-your-first-repo/
- Issues & Projects: https://github.blog/developer-skills/github/github-for-beginners-getting-started-with-github-issues-and-projects/
- Markdown: https://github.blog/developer-skills/github/github-for-beginners-getting-started-with-markdown/
- Pages: https://github.blog/developer-skills/github/github-for-beginners-getting-started-with-github-pages/
- OSS: https://github.blog/developer-skills/github/github-for-beginners-getting-started-with-oss-contributions/
