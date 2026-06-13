# security/ — конфіги безпеки

Політика безпеки лабораторії — у [`../SECURITY.md`](../SECURITY.md). Тут лежать
конфігурації сканерів.

## Що тут
- [`trivy.yaml`](trivy.yaml) — налаштування Trivy (вразливості, секрети, місконфіги).

## Як перевірити локально
```bash
# Секрети + гігієна
pre-commit run --all-files

# Вразливості / місконфіги (потрібен встановлений trivy)
trivy fs --config security/trivy.yaml .
```

> `.pre-commit-config.yaml` лежить у корені репозиторію — там його очікує `pre-commit`
> за замовчуванням. CI-воркфлоу — у `../.github/workflows/`.
