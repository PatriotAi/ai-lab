#!/usr/bin/env bash
# publish-results.sh — кладе знімки/відео прогону в окрему гілку-«фотоальбом»,
# щоб звіт міг показати картинки прямо на сторінці (і на телефоні).
#
# Одна відповідальність: скопіювати теку результатів у гілку $RESULTS_BRANCH
# репозиторію $REPO (теку runs/<RUN_KEY>/) і надрукувати базову адресу картинок.
# Гілка тримає лише останні $KEEP_RUNS прогонів і завжди складається з одного
# коміта — щоб репозиторій не розростався від старих відео.
#
# Вхід: REPO, RESULTS_BRANCH, RUN_KEY, SRC (тека з підтеками прогонів),
#       GH_TOKEN, KEEP_RUNS (за замовчуванням 30), SERVER_URL.
set -euo pipefail
: "${REPO:?}" "${RESULTS_BRANCH:?}" "${RUN_KEY:?}" "${SRC:?}" "${GH_TOKEN:?}"
KEEP_RUNS="${KEEP_RUNS:-30}"
SERVER_URL="${SERVER_URL:-https://github.com}"
MAX_FILE_MB=40

dir="$(mktemp -d)"
auth="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
remote="$SERVER_URL/$REPO.git"
git -C "$dir" init -q
git -C "$dir" config user.name "android-simulator"
git -C "$dir" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
if git -C "$dir" -c http.extraheader="$auth" fetch -q --depth 1 "$remote" "$RESULTS_BRANCH" 2>/dev/null; then
  git -C "$dir" checkout -q FETCH_HEAD -- . 2>/dev/null || true
fi

mkdir -p "$dir/runs/$RUN_KEY"
cp -R "$SRC"/. "$dir/runs/$RUN_KEY/"
# Завеликі файли (довгі відео) лишаються лише в архіві запуску.
find "$dir/runs/$RUN_KEY" -type f -size +"${MAX_FILE_MB}"M -print -delete | sed 's/^/завеликий, пропущено: /'

# Лишити тільки останні KEEP_RUNS прогонів.
mapfile -t old < <(ls -1t "$dir/runs" | tail -n +"$((KEEP_RUNS + 1))")
for o in "${old[@]}"; do rm -rf "${dir:?}/runs/$o"; done

cat > "$dir/README.md" <<'EOF'
# Результати віртуального смартфона

Службова гілка: знімки екрана, відео й журнали прогонів
`projects/android-simulator`. Зберігаються лише останні прогони; гілку
перезаписує робот. Вручну тут нічого не змінюйте.
EOF

git -C "$dir" checkout -q --orphan "tmp-$RUN_KEY"
git -C "$dir" add -A
git -C "$dir" commit -q -m "Результати прогону $RUN_KEY"
git -C "$dir" -c http.extraheader="$auth" push -q --force "$remote" "HEAD:refs/heads/$RESULTS_BRANCH"
echo "$SERVER_URL/$REPO/raw/$RESULTS_BRANCH/runs/$RUN_KEY"
