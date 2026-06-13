# Налаштування лабораторії

> Мова: **Українською** · [English](../en/setup.md)

## Передумови
- `git`, `python3` (для `pre-commit`).
- Опційно: `trivy`, `gitleaks` для локальних сканувань.

## Кроки
1. Клонуй репозиторій і перейди в теку.
2. Встанови перевірки: `bash scripts/setup.sh` (поставить `pre-commit` і git-хуки).
3. За потреби скопіюй `.env.example` → `.env` і заповни **локально** (не комітиться).
4. Перевір усе перед комітом: `pre-commit run --all-files`.
5. Локальна безпека: `bash scripts/security-check.sh`.

## Далі
- Конвенції — [`guidelines.md`](guidelines.md).
- Робота з AI — [`ai-integration.md`](ai-integration.md).
- Методологія — [`../methodology.md`](../methodology.md); план — [`../PLAN.md`](../PLAN.md).
