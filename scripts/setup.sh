#!/usr/bin/env bash
# Бутстрап лабораторії / Lab bootstrap: pre-commit + git-хуки.
set -euo pipefail

echo "→ Встановлюю pre-commit / Installing pre-commit"
python3 -m pip install --user --upgrade pre-commit

echo "→ Активую git-хуки / Installing git hooks"
pre-commit install

echo "✓ Готово / Done."
echo "  За потреби: cp .env.example .env  (та заповни локально / fill in locally)"
