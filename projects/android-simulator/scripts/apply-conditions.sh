#!/usr/bin/env bash
# apply-conditions.sh — поставити віртуальний телефон у «неідеальні» умови.
#
# Одна відповідальність: увімкнути кожну умову зі списку CONDITIONS і ПЕРЕВІРИТИ,
# що вона справді діє (зчитати назад із пристрою). Результат — рядки
# `назва|ok|що зчитано` або `назва|fail|чому` у $R/conditions.txt. Звіт показує їх
# людині, тож «умову ввімкнено» — це перевірений факт, а не обіцянка.
#
# Вхід: CONDITIONS (через кому), PACKAGE (для мови застосунку), R (тека результатів).
# Умови: offline · slow-net · dark · big-font · landscape · low-battery · locale-uk · locale-en
set -uo pipefail
: "${R:?}"
OUT="$R/conditions.txt"
: > "$OUT"
[ -n "${CONDITIONS:-}" ] || exit 0

sh_() { adb shell "$@" 2>/dev/null | tr -d '\r'; }
rec() { printf '%s|%s|%s\n' "$1" "$2" "$3" >> "$OUT"; echo "умова $1: $2 ($3)"; }
api="$(sh_ getprop ro.build.version.sdk)"

IFS=',' read -r -a list <<< "$CONDITIONS"
for c in "${list[@]}"; do
  case "$c" in
    offline)
      sh_ cmd connectivity airplane-mode enable >/dev/null
      sh_ svc wifi disable >/dev/null; sh_ svc data disable >/dev/null
      v="$(sh_ settings get global airplane_mode_on)"
      [ "$v" = 1 ] && rec offline ok "режим польоту увімкнено" || rec offline fail "airplane_mode_on=$v" ;;
    slow-net)
      a="$(adb emu network speed gsm 2>&1 | tr -d '\r' | tail -1)"
      b="$(adb emu network delay gprs 2>&1 | tr -d '\r' | tail -1)"
      [ "$a" = OK ] && [ "$b" = OK ] && rec slow-net ok "швидкість GSM, затримка GPRS" || rec slow-net fail "консоль емулятора: $a / $b" ;;
    dark)
      sh_ cmd uimode night yes >/dev/null
      v="$(sh_ cmd uimode night)"
      case "$v" in *yes*) rec dark ok "$v" ;; *) rec dark fail "$v" ;; esac ;;
    big-font)
      sh_ settings put system font_scale 1.3
      v="$(sh_ settings get system font_scale)"
      [ "$v" = 1.3 ] && rec big-font ok "масштаб шрифту 1.3" || rec big-font fail "font_scale=$v" ;;
    landscape)
      sh_ settings put system accelerometer_rotation 0
      sh_ settings put system user_rotation 1
      v="$(sh_ settings get system user_rotation)"
      [ "$v" = 1 ] && rec landscape ok "альбомна орієнтація" || rec landscape fail "user_rotation=$v" ;;
    low-battery)
      sh_ dumpsys battery unplug >/dev/null
      sh_ dumpsys battery set level 5 >/dev/null
      v="$(sh_ dumpsys battery | sed -n 's/^ *level: //p' | head -1)"
      [ "$v" = 5 ] && rec low-battery ok "заряд 5%, без зарядки" || rec low-battery fail "level=$v" ;;
    locale-uk|locale-en)
      tag="uk-UA"; [ "$c" = locale-en ] && tag="en-US"
      if [ "${api:-0}" -lt 33 ]; then
        rec "$c" fail "мова окремого застосунку — лише Android 13+ (API 33+), тут API $api"
      elif [ -z "${PACKAGE:-}" ]; then
        rec "$c" fail "невідомий застосунок"
      else
        sh_ cmd locale set-app-locales "$PACKAGE" --user 0 --locales "$tag" >/dev/null
        v="$(sh_ cmd locale get-app-locales "$PACKAGE" --user 0)"
        case "$v" in *"${tag%%-*}"*) rec "$c" ok "мова $tag для $PACKAGE" ;; *) rec "$c" fail "$v" ;; esac
      fi ;;
    *) rec "$c" fail "невідома умова" ;;
  esac
done
exit 0
