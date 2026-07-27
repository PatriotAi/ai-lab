# Безпека / Security

**🇺🇦 Українською** · [🇬🇧 English](#-english)

Лабораторія працює з під'єднаними сервісами (GitHub, Vercel, Canva) — тому кілька
твердих правил, щоб не створювати ризиків.

## Правила
1. **Жодних секретів у репозиторії.** Токени, ключі, паролі — лише через env-змінні.
   Усе чутливе ігнорується в `.gitignore`; зразок — `.env.example` (без значень).
2. **Мінімальні скоупи.** MCP-інтеграції та токени — з найменшими потрібними правами.
3. **Без секретів у логах/висновках.** Не вставляй ключі в `docs/learnings.md`, коміти, PR.
4. **Огляд автоматизацій.** Кожен хук/скрипт — під рев'ю; без «магічних» дій.
5. **Мережева політика.** Зважай на політику Claude Code on the web.

## Автоматичні перевірки
- **pre-commit** (локально): гігієна + `detect-private-key` + `gitleaks`. Запуск: `bash scripts/setup.sh`.
- **CI** (`.github/workflows/`): `security.yml` (gitleaks, Trivy, Semgrep), `dependencies.yml`
  (dependency-review), `code-quality.yml` (pre-commit, actionlint).
- **Dependabot** — оновлення залежностей. **CODEOWNERS** — рев'ю змін власником.
- Швидка локальна перевірка: `bash scripts/security-check.sh`.
  Вердикт має **три** стани: ПРОЙДЕНО · ВПАЛО · **НЕ ГАНЯВСЯ** (коди виходу `0`/`1`/`3`).
  «Не ганявся» ніколи не зараховується як «пройдено» — інструмент, якого немає,
  не робить репозиторій безпечним.
- **Чи ввімкнені контролі насправді:** `python3 scripts/security-drift.py`.
  Порівнює задеклароване з фактичним; те, що не видно з файлової системи
  (налаштування на боці GitHub), позначає як «не перевіряється звідси», а не як робоче.
- Стан безпеки, знахідки й план — `docs/security/`; модель загроз і реєстр
  контролів — `docs/security/threat-model.md`; сам пакет — `security/README.md`.

## Якщо секрет потрапив у git
1. Відкликати/ротувати токен негайно.
2. Видалити з історії (`git filter-repo` / BFG) і force-push.
3. Записати інцидент у `docs/learnings.md`.

---

<a id="-english"></a>
## 🇬🇧 English

[🇺🇦 Українською](#безпека--security) · **English**

The lab integrates with connected services (GitHub, Vercel, Canva), so a few hard rules apply.

### Rules
1. **No secrets in the repo.** Tokens, keys, passwords go through env vars only.
   Sensitive files are git-ignored; see `.env.example` (no values).
2. **Least privilege.** MCP integrations and tokens use the minimum scopes needed.
3. **No secrets in logs/notes.** Never paste keys into `docs/learnings.md`, commits or PRs.
4. **Review automations.** Every hook/script is reviewed; no "magic" actions.
5. **Network policy.** Mind the Claude Code on the web network policy.

### Automated checks
- **pre-commit** (local): hygiene + `detect-private-key` + `gitleaks`. Run `bash scripts/setup.sh`.
- **CI** (`.github/workflows/`): `security.yml` (gitleaks, Trivy, Semgrep), `dependencies.yml`,
  `code-quality.yml`. **Dependabot** updates dependencies; **CODEOWNERS** gates review.
- Quick local check: `bash scripts/security-check.sh`.

### If a secret reaches git
1. Revoke/rotate the token immediately.
2. Purge from history (`git filter-repo` / BFG) and force-push.
3. Record the incident in `docs/learnings.md`.
