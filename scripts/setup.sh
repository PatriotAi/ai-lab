#!/usr/bin/env bash
# Бутстрап лабораторії / Lab bootstrap: pre-commit + git-хуки.
set -euo pipefail

echo "→ Встановлюю pre-commit / Installing pre-commit"
if ! python3 -m pip install --user --upgrade pre-commit 2>/dev/null; then
  # PEP 668 (externally-managed environment): пробуємо pipx / try pipx
  if command -v pipx >/dev/null 2>&1; then
    pipx install --force pre-commit
  else
    echo "✗ pip заблоковано (PEP 668) / pip is blocked. Використай pipx або venv:" >&2
    echo "  python3 -m venv .venv && . .venv/bin/activate && pip install pre-commit" >&2
    exit 1
  fi
fi
# pip --user кладе бінарники сюди; у свіжих шелах цього шляху нема в PATH
export PATH="$HOME/.local/bin:$PATH"

echo "→ Активую git-хуки / Installing git hooks"
pre-commit install

# Stop-хук середовища Claude Code (web): оновлюємо з канону в automations/,
# щоб перевірка Unverified-комітів ухвалювала рішення індивідуально по коміту.
# Idempotent: копіюємо лише якщо базовий хук існує і відрізняється від канону.
HOOK_SRC="$(dirname "$0")/../automations/stop-git-check/stop-hook-git-check.sh"
HOOK_DST="$HOME/.claude/stop-hook-git-check.sh"
if [ -f "$HOOK_DST" ] && [ -f "$HOOK_SRC" ] && ! cmp -s "$HOOK_SRC" "$HOOK_DST"; then
  echo "→ Оновлюю Stop-хук git-перевірки / Updating stop git-check hook"
  cp "$HOOK_SRC" "$HOOK_DST" && chmod +x "$HOOK_DST"
fi

echo "✓ Готово / Done."
echo "  За потреби: cp .env.example .env  (та заповни локально / fill in locally)"
