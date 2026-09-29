#!/usr/bin/env bash
# check-action-pinning.sh — кожна GitHub-дія має бути закріплена хешем коміта.
#
# Одна відповідальність: перевірити, що жоден `uses:` у .github/workflows/
# не вказує на рухоме посилання (тег або гілку).
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

if [ "$total" -eq 0 ]; then
  echo "у воркфлоу немає жодного uses: — перевіряти нічого" >&2
  exit 2
fi

echo
if [ "$bad" -gt 0 ]; then
  echo "❌ рухомих посилань: $bad із $total"
  echo "   Тег і гілку можна перепризначити на інший коміт — хеш коміта ні."
  echo "   Резолв: git ls-remote https://github.com/OWNER/REPO 'refs/tags/TAG^{}'"
  exit 1
fi
echo "✅ усі $total дій закріплені повним SHA коміта"
