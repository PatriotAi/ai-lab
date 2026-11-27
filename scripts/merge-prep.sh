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
# Вихід 0 — готово: друкує NEW_HEAD=<sha> і GATE=<стан>; 3 — потрібне рішення людини
# (конфлікт, який не є чистим дописуванням; конфлікт у consent.md); 2 — помилка/відмова.
# Межі: НЕ зливає PR і НЕ читає CI — це робить модель після зеленого CI на NEW_HEAD.
#
# Модель довіри (рев'ю #150): ЖОДНОГО коду з гілки PR скрипт не виконує. Перевірки репо
# (verify, check-windows) ганяє CI в ізольованому раннері — на його зелене модель і так чекає.
# Гейт запускається з довіреної копії origin/main і бачить лише рядок згоди, записаний
# зі слів власника (--quote); рядки згоди, принесені самою гілкою, гейт не бачить.
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

# Автоматично об'єднується лише docs/learnings.md і лише ЧИСТЕ дописування: у кожному блоці
# конфлікту базова частина порожня (нічого не видалено й не змінено). security/consent.md —
# НІКОЛИ автоматично: union воскресив би відкликану згоду (W-14, рішення лабораторії).
UNION_OK="docs/learnings.md"

cd "$DIR"
git fetch -q origin main "$BRANCH"
WT="$(mktemp -d)"; TR="$(mktemp -d)"
trap 'cd "$DIR"; for d in "$WT" "$TR"; do git -C "$DIR" worktree remove --force "$d" >/dev/null 2>&1 || true; rm -rf "$d"; done' EXIT
# Відокремлена голова + явний push HEAD:гілка — без локальної гілки, чий upstream міг
# вказувати на main (пастка 2026-11-27).
git worktree add -q --detach "$WT" "origin/$BRANCH"
cd "$WT"
c=(-c user.email="${GIT_AUTHOR_EMAIL:-$(git -C "$DIR" config user.email || echo bot@local)}" \
   -c user.name="${GIT_AUTHOR_NAME:-$(git -C "$DIR" config user.name || echo bot)}")
OLD="$(git rev-parse --short HEAD)"

if ! git merge-base --is-ancestor origin/main HEAD; then
  # diff3 — свідомо: базова частина блоку показує, чи сторона щось видалила/змінила.
  if ! git "${c[@]}" -c merge.conflictStyle=diff3 merge -q --no-edit origin/main >/dev/null 2>&1; then
    bad=""
    for f in $(git diff --name-only --diff-filter=U); do
      case " $UNION_OK " in
        *" $f "*)
          if [ -L "$f" ] || ! python3 -I - "$f" <<'PY'
import sys
p = sys.argv[1]
lines = open(p, encoding="utf-8").read().split("\n")
out, i = [], 0
while i < len(lines):
    if not lines[i].startswith("<<<<<<< "):
        out.append(lines[i]); i += 1; continue
    ours, base, theirs, part = [], [], [], "ours"
    i += 1
    while i < len(lines) and not lines[i].startswith(">>>>>>> "):
        l = lines[i]
        if l.startswith("||||||| "): part = "base"
        elif l == "=======": part = "theirs"
        else: {"ours": ours, "base": base, "theirs": theirs}[part].append(l)
        i += 1
    if i >= len(lines) or any(x.strip() for x in base):
        sys.exit(1)  # незакритий блок або сторона щось видалила/змінила — не дописування
    out += ours + theirs; i += 1
open(p, "w", encoding="utf-8").write("\n".join(out))
PY
          then bad="$bad $f"; else git add "$f"; fi ;;
        *) bad="$bad $f" ;;
      esac
    done
    if [ -n "$bad" ]; then
      git merge --abort; echo "КОНФЛІКТ, що потребує рішення людини:$bad — нічого не відправлено"; exit 3
    fi
    git "${c[@]}" commit -q --no-edit
  fi
  MERGED="main зведено в гілку"
else
  MERGED="main уже в гілці"
fi

if [ -L security ] || [ -L security/consent.md ]; then
  echo "security/consent.md — посилання: запис заборонено"; exit 2
fi

TOKEN="mcp-merge_pull_request@$REPO#$PR"
until="$(date -u -d '+1 day' +%F 2>/dev/null || date -u -v+1d +%F)"
ROW=""
if [ -f security/consent.md ]; then
  # Повторний виклик з тими самими словами власника не дублює запис (ключ: ціль + строк + цитата).
  ROW="$(grep -F "| $TOKEN | $until | Власник " security/consent.md | grep -F "«$QUOTE»" | head -1 || true)"
  if [ -z "$ROW" ]; then
    ROW="$(printf '| %s | %s | Власник %s у чаті: «%s». Запис скриптом merge-prep: голова до запису %s, %s; злиття — лише після зеленого CI на новій голові. Ціль — лише цей PR; строк — до завтра. |' \
      "$TOKEN" "$until" "$(date -u +%F)" "$QUOTE" "$OLD" "$MERGED")"
    printf '%s\n' "$ROW" >> security/consent.md
    msg="consent: злиття $REPO#$PR за словом власника ($(date -u +%F))"
    [ ${#TRAILERS[@]} -gt 0 ] && msg="$msg"$'\n\n'"$(printf '%s\n' "${TRAILERS[@]}")"
    git "${c[@]}" commit -q -am "$msg"
  fi
fi

NEW="$(git rev-parse HEAD)"
if [ "$NEW" != "$(git rev-parse "origin/$BRANCH")" ]; then git push -q origin "HEAD:$BRANCH"; fi

# Гейт — із ДОВІРЕНОЇ копії origin/main; consent.md у ній = main + лише рядок зі слів власника.
GATE="нема гейта в репо"
git -C "$DIR" worktree add -q --detach "$TR" origin/main
if [ -f "$TR/security/spine/pretooluse.py" ]; then
  if [ -n "$ROW" ]; then printf '%s\n' "$ROW" >> "$TR/security/consent.md"; fi
  owner="${REPO%%/*}"; name="${REPO#*/}"
  out="$(printf '{"tool_name":"mcp__github__merge_pull_request","tool_input":{"owner":"%s","repo":"%s","pullNumber":%s},"cwd":"%s"}' \
        "$owner" "$name" "$PR" "$TR" | (cd "$TR" && CLAUDE_PROJECT_DIR="$TR" python3 -I security/spine/pretooluse.py 2>&1) || true)"
  case "$out" in *'"deny"'*) GATE="ВІДМОВА";; *"записана згода"*) GATE="дозволено записаною згодою";; *) GATE="без рішення: ${out:0:80}";; esac
fi
echo "NEW_HEAD=$NEW"
echo "GATE=$GATE"
echo "ДАЛІ: дочекатися зеленого CI на $NEW (verify і тести — там), тоді merge_pull_request з expectedHeadSha=$NEW"
# Код 0 — лише за явного дозволу або коли гейта в репо нема; «ask», помилка, порожньо — не успіх.
case "$GATE" in "дозволено записаною згодою"|"нема гейта в репо") exit 0 ;; *) exit 2 ;; esac
