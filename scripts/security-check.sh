#!/usr/bin/env bash
# Локальні перевірки безпеки / Local security checks.
# Не падає на першій помилці — проганяє все й звітує / runs all checks, then reports.
set -uo pipefail

echo "== pre-commit (гігієна + секрети / hygiene + secrets) =="
pre-commit run --all-files || true

echo "== gitleaks =="
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-banner || true
else
  echo "  gitleaks не встановлено / not installed — пропускаю / skipping"
fi

echo "== trivy =="
if command -v trivy >/dev/null 2>&1; then
  trivy fs --config security/trivy.yaml . || true
else
  echo "  trivy не встановлено / not installed — пропускаю / skipping"
fi

echo "✓ Перевірки завершено / Checks complete"
