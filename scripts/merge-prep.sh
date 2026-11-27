#!/usr/bin/env bash
# merge-prep.sh — уся механічна підготовка злиття PR за ОДИН виклик, без «обдумування» моделлю.
#
# Навіщо: після «Погоджую злиття X#N» рішення вже ухвалене власником, а кроки до злиття
# щоразу ті самі (worktree → підтягнути main → append-only конфлікти → запис згоди →
# verify → push → гейт). Модель робила їх 8–12 викликами з міркуваннями і помилялась
# у дрібницях (гейт із чужої копії, гілка з upstream на main — 2026-11-27). Скрипт робить
# їх детерміновано; моделі лишаються два дешеві кроки: живе читання CI/mergeable і саме
# злиття з expectedHeadSha=NEW_HEAD (канон — github-collab § «Рутина за згодою»).
#
#   merge-prep.sh --branch B --pr N --repo owner/name --quote "слова власника" \
#                 [--dir REPO_DIR] [--trailer "рядок"]...
#
# Вихід 0 — готово: друкує NEW_HEAD=<sha> і GATE=<стан>; 3 — конфлікт поза append-only
# файлами (нічого не відправлено, потрібне рішення); 2 — помилка виклику/перевірки.
# Межі: НЕ зливає PR і НЕ читає CI — це робить модель після зеленого CI на NEW_HEAD.
set -euo pipefail

BRANCH="" PR="" REPO="" QUOTE="" DIR="$PWD"; TRAILERS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --branch) BRANCH="$2"; shift 2 ;;
    --pr) PR="$2"; shift 2 ;;
    --repo) REPO="$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')"; shift 2 ;;
    --quote) QUOTE="$2"; shift 2 ;;
    --dir) DIR="$2"; shift 2 ;;
    --trailer) TRAILERS+=("$2"); shift 2 ;;
    *) echo "merge-prep: невідомий аргумент $1" >&2; exit 2 ;;
  esac
done
[ -n "$BRANCH" ] && [ -n "$PR" ] && [ -n "$REPO" ] && [ ${#QUOTE} -ge 5 ] \
  || { echo "merge-prep: потрібні --branch --pr --repo --quote" >&2; exit 2; }
case "$BRANCH" in main|master) echo "merge-prep: гілка PR не може бути $BRANCH" >&2; exit 2 ;; esac

# Append-only файли: обидві сторони лише дописують рядки, тож об'єднання = зняти маркери.
# WINDOWS.md сюди НЕ входить — у ньому лічильник, який об'єднання зламало б.
UNION_OK="security/consent.md docs/learnings.md"

cd "$DIR"
git fetch -q origin main "$BRANCH"
WT="$(mktemp -d)"; trap 'git -C "$DIR" worktree remove --force "$WT" >/dev/null 2>&1 || true; rm -rf "$WT"' EXIT
# Відокремлена голова + явний push HEAD:гілка — без локальної гілки, чий upstream міг
# вказувати на main (пастка 2026-11-27).
git worktree add -q --detach "$WT" "origin/$BRANCH"
cd "$WT"
c=(-c user.email="${GIT_AUTHOR_EMAIL:-$(git -C "$DIR" config user.email || echo bot@local)}" \
   -c user.name="${GIT_AUTHOR_NAME:-$(git -C "$DIR" config user.name || echo bot)}")
OLD="$(git rev-parse --short HEAD)"

if ! git merge-base --is-ancestor origin/main HEAD; then
  if ! git "${c[@]}" merge -q --no-edit origin/main >/dev/null 2>&1; then
    bad=""
    for f in $(git diff --name-only --diff-filter=U); do
      case " $UNION_OK " in *" $f "*) sed -i '/^<<<<<<< /d;/^=======$/d;/^>>>>>>> /d' "$f"; git add "$f" ;;
        *) bad="$bad $f" ;; esac
    done
    if [ -n "$bad" ]; then
      git merge --abort; echo "КОНФЛІКТ поза append-only файлами:$bad — нічого не відправлено"; exit 3
    fi
    git "${c[@]}" commit -q --no-edit
  fi
  MERGED="main зведено в гілку"
else
  MERGED="main уже в гілці"
fi

TOKEN="mcp-merge_pull_request@$REPO#$PR"
if [ -f security/consent.md ] && ! grep -qF "| $TOKEN |" security/consent.md; then
  until="$(date -u -d '+1 day' +%F 2>/dev/null || date -u -v+1d +%F)"
  printf '| %s | %s | Власник %s у чаті: «%s». Запис скриптом merge-prep: голова до запису %s, %s; злиття — лише після зеленого CI на новій голові. Ціль — лише цей PR; строк — до завтра. |\n' \
    "$TOKEN" "$until" "$(date -u +%F)" "$QUOTE" "$OLD" "$MERGED" >> security/consent.md
  msg="consent: злиття $REPO#$PR за словом власника ($(date -u +%F))"
  [ ${#TRAILERS[@]} -gt 0 ] && msg="$msg"$'\n\n'"$(printf '%s\n' "${TRAILERS[@]}")"
  git "${c[@]}" commit -q -am "$msg"
fi

if [ -f melania-skills-ecosystem/scripts/maintain.py ]; then
  python3 melania-skills-ecosystem/scripts/maintain.py verify >/dev/null 2>&1 \
    || { echo "verify впав — нічого не відправлено"; exit 2; }
fi
if [ -f scripts/check-windows.py ]; then
  python3 scripts/check-windows.py >/dev/null 2>&1 || { echo "check-windows впав — нічого не відправлено"; exit 2; }
fi

NEW="$(git rev-parse HEAD)"
if [ "$NEW" != "$(git rev-parse "origin/$BRANCH")" ]; then git push -q origin "HEAD:$BRANCH"; fi

# Гейт — із ЦІЄЇ копії: він читає consent.md поряд із собою, а не з робочої теки виклику.
GATE="нема гейта в репо"
if [ -f security/spine/pretooluse.py ]; then
  owner="${REPO%%/*}"; name="${REPO#*/}"
  out="$(printf '{"tool_name":"mcp__github__merge_pull_request","tool_input":{"owner":"%s","repo":"%s","pullNumber":%s},"cwd":"%s"}' \
        "$owner" "$name" "$PR" "$WT" | CLAUDE_PROJECT_DIR="$WT" python3 -I security/spine/pretooluse.py 2>/dev/null || true)"
  case "$out" in *'"deny"'*) GATE="ВІДМОВА";; *"записана згода"*) GATE="дозволено записаною згодою";; *) GATE="без рішення: ${out:0:80}";; esac
fi
echo "NEW_HEAD=$NEW"
echo "GATE=$GATE"
echo "ДАЛІ: дочекатися зеленого CI на $NEW, тоді merge_pull_request з expectedHeadSha=$NEW"
[ "$GATE" = "ВІДМОВА" ] && exit 2 || exit 0
