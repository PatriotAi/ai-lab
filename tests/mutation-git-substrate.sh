#!/usr/bin/env bash
# mutation-git-substrate.sh — мутаційна перевірка секції 27 набору (Git як субстрат).
# Єдина відповідальність: довести, що тести секції 27 ПАДАЮТЬ, коли ламається те, що
# вони обіцяють охороняти (Core Rule 15: перевірка, що лише проходить на чистому, не
# доводить нічого). Кожен мутант — копія файлів у тимчасовій теці, робочий репо не
# змінюється. Мутант, що не застосувався (sed нічого не змінив), рахується як ВИЖИВ.
# Код виходу: 0 — усі мутанти спіймані · 1 — хоч один вижив.
set -uo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT

# Секція 27 разом зі спільними хелперами набору; межа — рядок-маркер у run-tests.sh,
# щоб сам виклик цієї перевірки не потрапив у вирізку (інакше — рекурсія).
first=$(grep -n '^echo "════════ 1\.' "$R/tests/run-tests.sh" | head -1 | cut -d: -f1)
s=$(grep -n '════════ 27\.' "$R/tests/run-tests.sh" | cut -d: -f1)
m=$(grep -n 'кінець перевірок секції 27' "$R/tests/run-tests.sh" | cut -d: -f1)
[[ -n "$first" && -n "$s" && -n "$m" ]] || { echo "❌ не знайдено меж секції 27 у run-tests.sh"; exit 1; }
{ sed -n "1,$((first-1))p" "$R/tests/run-tests.sh"
  sed -n "$((s-1)),$((m-1))p" "$R/tests/run-tests.sh"
  printf 'printf "пройдено: %%d · впало: %%d\\n" "$PASS" "$FAIL"\n'; } > "$W/sec27.sh"

survived=0; total=0
copy_tree() { # копія файлів, які читає секція 27, у нову тимчасову теку; друкує шлях
  local T; T=$(mktemp -d "$W/m.XXXX")
  mkdir -p "$T/scripts" "$T/automations/session-start" "$T/docs"
  cp "$R/scripts/check-main-drift.py" "$R/scripts/check-union-journal.py" "$R/scripts/git-conflict-hotspots.py" "$T/scripts/"
  cp "$R/.gitattributes" "$T/"; cp "$R/docs/learnings.md" "$T/docs/"
  cp "$R/automations/session-start/session-start.sh" "$T/automations/session-start/"
  git -C "$T" init -q; echo "$T"
}
# Контроль: без мутації секція мусить пройти чисто. Інакше «спіймано» на кожному
# мутанті означало б лише зламане тимчасове оточення, а не силу тестів.
C=$(copy_tree); sed "s#^REPO=.*#REPO=$C#" "$W/sec27.sh" > "$C/run.sh"
ctl=$(bash "$C/run.sh" 2>&1 | grep -E "пройдено:" | tail -1)
[[ "$ctl" == *"впало: 0"* ]] || { echo "❌ контроль без мутації не чистий (${ctl:-немає підсумку}) — мутанти нічого не доводять"; exit 1; }
echo "  контроль без мутації: ${ctl}"

mutate() { # mutate <id> <файл відносно кореня> <sed-вираз>
  local id=$1 rel=$2 expr=$3 T; T=$(copy_tree); total=$((total+1))
  cp "$T/$rel" "$T/$rel.orig"; sed -i "$expr" "$T/$rel"
  if cmp -s "$T/$rel" "$T/$rel.orig"; then
    echo "  ВИЖИВ (не застосовний): $id"; survived=$((survived+1)); return; fi
  rm "$T/$rel.orig"
  sed "s#^REPO=.*#REPO=$T#" "$W/sec27.sh" > "$T/run.sh"
  local res; res=$(bash "$T/run.sh" 2>&1 | grep -E "пройдено:" | tail -1)
  if [[ "$res" == *"впало: 0"* || -z "$res" ]]; then
    echo "  ВИЖИВ: $id (${res:-немає підсумку})"; survived=$((survived+1))
  else echo "  спіймано: $id (${res})"; fi
}
mutate "радар не бачить конфліктів"            scripts/check-main-drift.py    's/conflicts = names(r.stdout)\[1:\]/conflicts = []/'
mutate "dependabot потрапляє в карту"          scripts/check-main-drift.py    's/if "dependabot\/" in ref:/if False:/'
mutate "паралельні гілки без перетину файлів"  scripts/check-main-drift.py    's/overlap = sorted(mine \& set(/overlap = sorted(set() \& set(/'
mutate "рядок «Дія» не рахується"              scripts/check-union-journal.py 's/\^- Дія:/^- NEVER:/'
mutate "дозволено будь-який атрибут"           scripts/check-union-journal.py 's/\\s+merge=union\\s\*\$/\\s+.*$/'
mutate "атрибут union прибрано"                .gitattributes                 '/^docs\/learnings.md merge=union/d'
mutate "повтор union без атрибута"             scripts/git-conflict-hotspots.py 's/replay(a.repo, p1, p2, union_attrs)/replay(a.repo, p1, p2, None)/'
mutate "радар не підключено до SessionStart"   automations/session-start/session-start.sh '/check-main-drift.py/d'

echo "Мутантів: $total · вижило: $survived"
(( survived == 0 ))
