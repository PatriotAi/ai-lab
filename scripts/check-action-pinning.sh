#!/usr/bin/env bash
# check-action-pinning.sh — кожна GitHub-дія і кожен віддалений хук pre-commit
# мають бути закріплені хешем коміта.
#
# Одна відповідальність: перевірити, що жоден `uses:` у .github/workflows/ і
# жоден `rev:` віддаленого репо в .pre-commit-config.yaml не вказує на рухоме
# посилання (тег або гілку). Хуки додано 2026-11-03 (W-39): тег хука можна
# перепризначити так само, як тег дії, а виконується він на машині розробника.
#
# НАВІЩО. Тег і гілку можна перепризначити на інший коміт — хеш коміта ні.
# Компрометація `tj-actions/changed-files` (CVE-2025-30066, березень 2025)
# зачепила ~23 000 репозиторіїв саме так: зловмисник перепризначив теги на
# шкідливий коміт, і всі, хто стояв на `@v45`, підхопили його автоматично.
# Закріплення хешем — єдиний контроль, що це зупиняє.
#
# Цей файл викликають І CI (.github/workflows/dependencies.yml), І людина
# локально — щоб перевірка була одна, а не дві розбіжні копії.
#
# Запуск: bash scripts/check-action-pinning.sh
# Код виходу: 0 — усі закріплені · 1 — є рухомі · 2 — немає що перевіряти.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
WF_DIR="$ROOT/.github/workflows"

if [ ! -d "$WF_DIR" ]; then
  echo "немає теки $WF_DIR — нічого перевіряти" >&2
  exit 2
fi

bad=0
total=0

while IFS= read -r ref; do
  [ -z "$ref" ] && continue
  # Локальні дії (./…) і докерні (docker://…) закріплювати нічим.
  case "$ref" in ./*|docker://*) continue ;; esac
  total=$((total + 1))
  case "$ref" in
    *@*) sha="${ref##*@}" ;;
    *)
      echo "::error::дія взагалі без версії: $ref"
      bad=$((bad + 1)); continue ;;
  esac
  if printf '%s' "$sha" | grep -qE '^[0-9a-f]{40}$'; then
    echo "  ✓ $ref"
  else
    echo "::error::рухоме посилання замість SHA: $ref"
    bad=$((bad + 1))
  fi
done < <(grep -rhE '^[[:space:]]*-?[[:space:]]*uses:' "$WF_DIR"/*.yml 2>/dev/null \
         | sed -E 's/.*uses:[[:space:]]*//; s/[[:space:]]*#.*//')

# Хуки pre-commit: `rev:` належить останньому `repo:` вище. `local` і `meta`
# коду ззовні не тягнуть і `rev:` не мають.
PC="$ROOT/.pre-commit-config.yaml"
if [ -f "$PC" ]; then
  while IFS=$'\t' read -r repo rev; do
    [ -z "$repo" ] && continue
    total=$((total + 1))
    if printf '%s' "$rev" | grep -qE '^[0-9a-f]{40}$'; then
      echo "  ✓ pre-commit $repo@$rev"
    else
      echo "::error::рухомий rev хука pre-commit замість SHA: $repo@${rev:-<нема rev>}"
      bad=$((bad + 1))
    fi
  done < <(awk '
    /^[[:space:]]*-[[:space:]]*repo:/ {
      if (repo != "" && repo != "local" && repo != "meta" && !seen) print repo "\t"
      r = $0; sub(/.*repo:[[:space:]]*/, "", r); sub(/[[:space:]]*#.*/, "", r); gsub(/["\047]/, "", r)
      repo = r; seen = 0; next
    }
    /^[[:space:]]*rev:/ && repo != "" {
      v = $0; sub(/.*rev:[[:space:]]*/, "", v); sub(/[[:space:]]*#.*/, "", v); gsub(/["\047[:space:]]/, "", v)
      if (repo != "local" && repo != "meta") print repo "\t" v
      seen = 1
    }
    END { if (repo != "" && repo != "local" && repo != "meta" && !seen) print repo "\t" }
  ' "$PC")
fi

if [ "$total" -eq 0 ]; then
  echo "у воркфлоу немає жодного uses: і хуків pre-commit — перевіряти нічого" >&2
  exit 2
fi

echo
if [ "$bad" -gt 0 ]; then
  echo "❌ рухомих посилань: $bad із $total"
  echo "   Тег і гілку можна перепризначити на інший коміт — хеш коміта ні."
  echo "   Резолв: git ls-remote https://github.com/OWNER/REPO 'refs/tags/TAG^{}'"
  echo "   (для анотованого тега — рядок із ^{}; у pre-commit: rev: <SHA>  # frozen: TAG)"
  exit 1
fi
echo "✅ усі $total посилань (дії й хуки pre-commit) закріплені повним SHA коміта"
