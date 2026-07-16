#!/usr/bin/env bash
# Локальні перевірки безпеки / Local security checks.
# Не падає на першій помилці — проганяє все, звітує і повертає ненульовий exit,
# якщо будь-яка перевірка знайшла проблему / runs all checks, then reports;
# exits non-zero if any check failed (callers can rely on the exit code).
set -uo pipefail

fails=0

echo "== pre-commit (гігієна + секрети / hygiene + secrets) =="
if ! pre-commit run --all-files; then
  fails=$((fails + 1))
fi

echo "== gitleaks =="
if command -v gitleaks >/dev/null 2>&1; then
  if ! gitleaks detect --no-banner; then
    fails=$((fails + 1))
  fi
else
  echo "  gitleaks не встановлено / not installed — пропускаю / skipping"
fi

echo "== trivy =="
if command -v trivy >/dev/null 2>&1; then
  if ! trivy fs --config security/trivy.yaml .; then
    fails=$((fails + 1))
  fi
else
  echo "  trivy не встановлено / not installed — пропускаю / skipping"
fi

if [ "$fails" -gt 0 ]; then
  echo "✗ Провалених перевірок / failed checks: $fails"
  exit 1
fi
echo "✓ Усі перевірки чисті / All checks clean"
