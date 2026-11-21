#!/usr/bin/env bash
# run-on-emulator.sh — сам «прогін» на вже ввімкненому віртуальному телефоні.
#
# Одна відповідальність: встановити/відкрити ціль, пройти сценарій, зняти
# знімки, відео й журнал, порахувати падіння — і записати все в $WORK/results.
# Завжди завершується з кодом 0: вердикт (зелений/червоний) виносить окремий
# крок за status.json, щоб результати вивантажились навіть після падіння.
#
# Вхід: $WORK/target.env (від prepare-target.sh) + змінні KIND, FLOW_PATH,
# MONKEY_EVENTS, SIM_DIR, MAESTRO_BIN, CONDITIONS (необов'язково).
set -uo pipefail

: "${WORK:?}" "${KIND:?}" "${SIM_DIR:?}"
# shellcheck disable=SC1091
source "$WORK/target.env"
R="$WORK/results"
mkdir -p "$R/shots" "$R/video" "$R/maestro"
STATUS="$R/status.env"
: > "$STATUS"
st() { printf '%s=%q\n' "$1" "$2" >> "$STATUS"; }
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

# Прибрати перепустку до сайту з файлів журналів (вона — секрет).
scrub() {
  [ -s "$WORK/launch-url.txt" ] || return 0
  python3 "$SIM_DIR/scripts/urltools.py" scrub "$WORK/launch-url.txt" "$@"
}

# Системне вікно «<чужий застосунок> isn't responding» (напр. робочий стіл
# зависає після повороту на програмній відеокарті) закриває знімок цілі.
# Закриваємо кнопкою «Wait» лише коли вікно НЕ про ціль, і пишемо це у звіт.
dismiss_foreign_anr() {
  local i xml="$WORK/ui-anr.xml"
  for i in 1 2 3; do
    adb shell uiautomator dump /sdcard/ui-anr.xml >/dev/null 2>&1 && adb pull /sdcard/ui-anr.xml "$xml" >/dev/null 2>&1 || return 0
    local title
    title="$(grep -oE "text=\"[^\"]*(isn(&apos;|.)t responding|не відповідає)[^\"]*\"" "$xml" | head -1 | sed 's/^text="//; s/"$//')"
    [ -n "$title" ] || return 0
    case "$title" in *"${APP_LABEL:-@@none@@}"*) return 0 ;; esac
    local xy; xy="$(python3 "$SIM_DIR/scripts/tap_text.py" "$xml" "Wait" "Зачекати")" || return 0
    log "закриваю чуже системне вікно: $title"
    st FOREIGN_ANR "$title"
    # shellcheck disable=SC2086
    adb shell input tap $xy
    sleep 3
  done
}

shot_n=0
shot() { # shot <назва>
  shot_n=$((shot_n + 1))
  local f; f="$R/shots/$(printf '%02d' "$shot_n")-$1.png"
  adb exec-out screencap -p > "$f" 2>/dev/null || rm -f "$f"
  log "знімок: $(basename "$f")"
  # Перший знімок цілі — доказ для умови landscape.
  if [ "$shot_n" = 1 ] && [ -f "$f" ] && grep -q '^landscape|pending' "$R/conditions.txt" 2>/dev/null; then
    R="$R" bash "$SIM_DIR/scripts/apply-conditions.sh" check-landscape "$f"
  fi
}

# ── Пристрій ────────────────────────────────────────────────────────────────
adb wait-for-device
adb shell input keyevent 82 >/dev/null 2>&1 || true       # розблокувати екран
adb shell svc power stayon true >/dev/null 2>&1 || true
adb shell settings put system screen_off_timeout 1800000 >/dev/null 2>&1 || true
# «Маленький екран»: щільність як у компактного телефона (360×640 «точок»).
if [ "${DEVICE:-}" = small ]; then
  adb shell wm density 320 >/dev/null 2>&1 || true
  sleep 3
fi
{
  echo "model=$(adb shell getprop ro.product.model | tr -d '\r')"
  echo "android=$(adb shell getprop ro.build.version.release | tr -d '\r')"
  echo "api=$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
  echo "abi=$(adb shell getprop ro.product.cpu.abilist | tr -d '\r')"
  echo "screen=$(adb shell wm size | tr -d '\r' | sed 's/.*: //')"
  echo "density=$(adb shell wm density | tr -d '\r' | tail -1 | sed 's/.*: //')"
} > "$R/device.txt"
cat "$R/device.txt"

adb logcat -b all -c >/dev/null 2>&1 || true
adb logcat -v time > "$R/logcat.txt" 2>/dev/null &
LOGCAT_PID=$!

# Відео: Android пише максимум 3 хв за раз, тож пишемо шматками до 3 штук.
# Програмна відеокарта емулятора не завжди тягне запис у повному розмірі —
# пишемо в половинному. Паралельно знімаємо кадр кожні ~2 с: із них зробимо
# GIF, якщо відео не вдасться (запасний шлях).
REC_PID=""; FRAMES_PID=""
start_rec() {
  local w h size
  read -r w h < <(adb shell wm size | tr -d '\r' | sed -n 's/^Physical size: //p' | tail -1 | sed 's/x/ /')
  if [ "${w:-0}" -gt 720 ]; then size="$(( w / 2 / 2 * 2 ))x$(( h / 2 / 2 * 2 ))"; else size="${w}x${h}"; fi
  (
    for i in 1 2 3; do
      adb shell screenrecord --size "$size" --bit-rate 1200000 --time-limit 175 "/sdcard/sim-rec-$i.mp4" >> "$R/video/record.log" 2>&1 || break
      [ -f "$WORK/.stop-rec" ] && break
    done
  ) &
  REC_PID=$!
  mkdir -p "$WORK/frames"
  (
    n=0
    while [ ! -f "$WORK/.stop-rec" ] && [ "$n" -lt 400 ]; do
      n=$((n + 1))
      adb exec-out screencap -p > "$WORK/frames/f$(printf '%04d' "$n").png" 2>/dev/null || break
      sleep 1.5
    done
  ) &
  FRAMES_PID=$!
  sleep 1
}

# ── Ціль ────────────────────────────────────────────────────────────────────
installed=0; launched=0
if [ "$KIND" = web ]; then
  url="$(cat "$WORK/launch-url.txt")"
  # Chrome без вітальних екранів (працює на образах з root; інакше їх закриє сценарій).
  adb root >/dev/null 2>&1 && sleep 3 && adb wait-for-device
  adb shell 'echo "_ --disable-fre --no-default-browser-check --no-first-run --disable-signin-promo" > /data/local/tmp/chrome-command-line' >/dev/null 2>&1 || true
  adb shell am set-debug-app --persistent com.android.chrome >/dev/null 2>&1 || true
  R="$R" PACKAGE="com.android.chrome" bash "$SIM_DIR/scripts/apply-conditions.sh"
  open_url() { # open_url <url>
    if [ -n "${HAS_CHROME:-}" ]; then
      adb shell am start -a android.intent.action.VIEW -n com.android.chrome/com.google.android.apps.chrome.Main -d "'$1'" >/dev/null 2>&1
    else
      adb shell am start -a android.intent.action.VIEW -d "'$1'" >/dev/null 2>&1
    fi
  }
  adb shell pm path com.android.chrome 2>/dev/null | grep -q package: && HAS_CHROME=1
  if [ -n "${HAS_CHROME:-}" ]; then
    st BROWSER "Chrome $(adb shell dumpsys package com.android.chrome | sed -n 's/.*versionName=//p' | head -1 | tr -d '\r')"
  else
    st BROWSER "вбудований переглядач (Chrome на образі відсутній)"
  fi
  open_url "$url"
  installed=1; launched=1
  sleep 15
  # Вітальні екрани Chrome (умови, вхід в акаунт, сповіщення) — закрити, якщо є.
  for _ in 1 2 3 4; do
    adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1 && adb pull /sdcard/ui.xml "$WORK/ui.xml" >/dev/null 2>&1 || break
    xy="$(python3 "$SIM_DIR/scripts/tap_text.py" "$WORK/ui.xml" "Accept & continue" "Use without an account" \
          "No thanks" "No, thanks" "Skip" "Got it" "Not now" "Don't allow")" || break
    log "закриваю вітальний екран Chrome ($xy)"
    # shellcheck disable=SC2086
    adb shell input tap $xy
    sleep 4
  done
  # Якщо відкривали з ключем доступу — тепер (кука вже є) відкриваємо чисте
  # посилання, щоб ключ не потрапив на знімки й відео. Запис — лише після цього.
  if [ "$url" != "$DISPLAY_TARGET" ]; then
    open_url "$DISPLAY_TARGET"
    sleep 12
  fi
  start_rec
  sleep 5
  dismiss_foreign_anr
  shot opened
else
  start_rec
  log "Встановлюю $PACKAGE ($INSTALL_MODE)"
  if [ "$INSTALL_MODE" = apks ]; then
    java -jar "$WORK/bundletool.jar" install-apks --apks="$WORK/app/app.apks" > "$R/install.txt" 2>&1 && installed=1
  else
    mapfile -t files < <(ls "$WORK"/app/*.apk)
    if [ ${#files[@]} -gt 1 ]; then
      adb install-multiple -r -g "${files[@]}" > "$R/install.txt" 2>&1 && installed=1
    else
      adb install -r -g "${files[0]}" > "$R/install.txt" 2>&1 && installed=1
    fi
  fi
  cat "$R/install.txt"
  if [ "$installed" = 1 ]; then
    R="$R" PACKAGE="$PACKAGE" bash "$SIM_DIR/scripts/apply-conditions.sh"
    adb shell monkey -p "$PACKAGE" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 && launched=1
    sleep 12
    dismiss_foreign_anr
    shot launched
  else
    st INSTALL_ERROR "$(grep -o 'INSTALL_[A-Z_]*' "$R/install.txt" | head -1)"
  fi
fi
st INSTALLED "$installed"
st LAUNCHED "$launched"

# ── Сценарій (Maestro) ─────────────────────────────────────────────────────
if [ "$installed" = 1 ] && [ -n "${FLOW_PATH:-}" ] && [ -n "${MAESTRO_BIN:-}" ]; then
  log "Сценарій: $FLOW_PATH"
  ( cd "$R/maestro" && "$MAESTRO_BIN" test "$FLOW_PATH" \
      --format junit --output "$R/maestro/report.xml" \
      --test-output-dir "$R/maestro" \
      -e "SIM_URL=$( [ "$KIND" = web ] && echo "$DISPLAY_TARGET")" \
      -e "SIM_PACKAGE=$PACKAGE" ) > "$R/maestro/maestro.log" 2>&1
  rc=$?
  scrub "$R/maestro/maestro.log"
  tail -40 "$R/maestro/maestro.log"
  st FLOW_RC "$rc"
  shot after-flow
fi

# ── Сайт: прокрутка вниз (якщо сценарію нема) ──────────────────────────────
if [ "$KIND" = web ] && [ -z "${FLOW_PATH:-}" ]; then
  read -r W H < <(adb shell wm size | tr -d '\r' | sed 's/.*: //; s/x/ /')
  for i in 1 2; do
    adb shell input swipe $((W / 2)) $((H * 3 / 4)) $((W / 2)) $((H / 4)) 400
    sleep 3
    shot "scroll-$i"
  done
fi

# ── Випадкові дотики (пошук падінь) ────────────────────────────────────────
if [ "$KIND" = app ] && [ "$installed" = 1 ] && [ "${MONKEY_EVENTS:-0}" -gt 0 ]; then
  log "Випадкові дотики: $MONKEY_EVENTS"
  adb shell monkey -p "$PACKAGE" -s 42 --throttle 250 --pct-syskeys 0 --pct-anyevent 0 \
    --ignore-security-exceptions -v "$MONKEY_EVENTS" > "$R/monkey.txt" 2>&1
  st MONKEY_RC "$?"
  sleep 3
  shot after-random-taps
fi

# ── Чи живий застосунок наприкінці ─────────────────────────────────────────
if [ "$KIND" = app ] && [ "$installed" = 1 ]; then
  if adb shell pidof "$PACKAGE" >/dev/null 2>&1; then st ALIVE 1; else st ALIVE 0; fi
fi

# ── Зупинити запис і зібрати файли ─────────────────────────────────────────
touch "$WORK/.stop-rec"
adb shell pkill -INT screenrecord >> "$R/video/record.log" 2>&1 || true
# Дати запису дописати файл: чекаємо, поки процес запису сам завершиться (до 20 с).
for _ in $(seq 1 20); do
  [ -n "$REC_PID" ] && kill -0 "$REC_PID" 2>/dev/null || break
  sleep 1
done
[ -n "$REC_PID" ] && kill "$REC_PID" >/dev/null 2>&1 || true
[ -n "$FRAMES_PID" ] && wait "$FRAMES_PID" 2>/dev/null || true
for i in 1 2 3; do
  adb pull "/sdcard/sim-rec-$i.mp4" "$R/video/part-$i.mp4" >/dev/null 2>&1 || true
  [ -s "$R/video/part-$i.mp4" ] || rm -f "$R/video/part-$i.mp4"
done
log "відео: $(ls "$R/video" | tr '\n' ' '); кадрів для GIF: $(ls "$WORK/frames" 2>/dev/null | wc -l)"
adb logcat -d -b crash > "$R/crash.txt" 2>/dev/null || true
kill "$LOGCAT_PID" >/dev/null 2>&1 || true
scrub "$R/logcat.txt" "$R/crash.txt"
log "Готово"
exit 0
