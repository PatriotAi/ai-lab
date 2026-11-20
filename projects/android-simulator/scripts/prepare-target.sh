#!/usr/bin/env bash
# prepare-target.sh — дістає ціль і готує її до запуску на віртуальному телефоні.
#
# Одна відповідальність: з посилання / F-Droid / артефакту зробити набір
# APK-файлів, готових до встановлення (або посилання на сайт), і записати
# опис у $WORK/target.env. Емулятор тут НЕ запускається.
#
# Вхід (змінні оточення; у shell не підставляються):
#   KIND=app|web  SOURCE=url|fdroid|artifact  TARGET (без перепустки)
#   VERCEL_BYPASS (необов'язковий секрет)  ARTIFACT_DIR  WORK  SIM_DIR
#   BUNDLETOOL_VERSION  BUNDLETOOL_SHA256 (необов'язково)
set -euo pipefail

: "${KIND:?}" "${SOURCE:?}" "${TARGET:?}" "${WORK:?}" "${SIM_DIR:?}"
mkdir -p "$WORK/in" "$WORK/app" "$WORK/results"
ENV_OUT="$WORK/target.env"
: > "$ENV_OUT"

note() { printf '%s\n' "$*"; }
fail() { printf '::error::%s\n' "$*"; printf 'PREPARE_ERROR=%q\n' "$*" >> "$ENV_OUT"; exit 1; }

# ── Сайт ───────────────────────────────────────────────────────────────────
if [ "$KIND" = web ]; then
  launch="$TARGET"
  if [ -n "${VERCEL_BYPASS:-}" ]; then
    case "$launch" in *\?*) sep='&' ;; *) sep='?' ;; esac
    launch="${launch}${sep}x-vercel-protection-bypass=${VERCEL_BYPASS}&x-vercel-set-bypass-cookie=true"
  fi
  # Посилання запуску — лише у файлі, не в журналі.
  printf '%s' "$launch" > "$WORK/launch-url.txt"
  {
    printf 'DISPLAY_TARGET=%q\n' "$TARGET"
    printf 'PACKAGE=%q\n' "com.android.chrome"
  } >> "$ENV_OUT"
  note "Сайт підготовлено: $TARGET"
  exit 0
fi

# ── Застосунок: дістати файл ───────────────────────────────────────────────
fetch() { # fetch <url> <файл>
  curl --fail --location --silent --show-error --retry 3 --max-filesize 1500000000 -o "$2" "$1"
}

case "$SOURCE" in
  fdroid)
    pkg="${TARGET#fdroid:}"
    fetch "https://f-droid.org/api/v1/packages/$pkg" "$WORK/in/fdroid.json" \
      || fail "F-Droid не знає пакета $pkg"
    vc="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["suggestedVersionCode"])' "$WORK/in/fdroid.json")"
    [[ "$vc" =~ ^[0-9]+$ ]] || fail "F-Droid повернув дивну версію: $vc"
    note "F-Droid: $pkg, версія $vc"
    fetch "https://f-droid.org/repo/${pkg}_${vc}.apk" "$WORK/in/app.apk" || fail "Не вдалося завантажити APK з F-Droid"
    ;;
  url)
    name="$(basename "${TARGET%%[?#]*}")"
    case "$name" in *.apk|*.aab|*.apks|*.xapk|*.zip) ;; *) name="app.apk" ;; esac
    fetch "$TARGET" "$WORK/in/$name" || fail "Не вдалося завантажити файл за посиланням"
    ;;
  artifact)
    [ -d "${ARTIFACT_DIR:-}" ] || fail "Артефакт не знайдено"
    find "$ARTIFACT_DIR" -type f \( -name '*.apk' -o -name '*.aab' -o -name '*.apks' -o -name '*.xapk' -o -name '*.zip' \) \
      -exec cp {} "$WORK/in/" \;
    ;;
  *) fail "невідоме джерело $SOURCE" ;;
esac

# ── Інструменти ────────────────────────────────────────────────────────────
BT="$WORK/bundletool.jar"
get_bundletool() {
  [ -f "$BT" ] && return 0
  fetch "https://github.com/google/bundletool/releases/download/${BUNDLETOOL_VERSION}/bundletool-all-${BUNDLETOOL_VERSION}.jar" "$BT"
  actual="$(sha256sum "$BT" | cut -d' ' -f1)"
  note "bundletool ${BUNDLETOOL_VERSION} sha256=$actual"
  if [ -n "${BUNDLETOOL_SHA256:-}" ] && [ "$actual" != "$BUNDLETOOL_SHA256" ]; then
    fail "bundletool: контрольна сума не збігається — файл підмінено або пошкоджено"
  fi
  # Ключ для підпису згенерованих APK (тестовий, одноразовий).
  if [ ! -f "$HOME/.android/debug.keystore" ]; then
    mkdir -p "$HOME/.android"
    keytool -genkeypair -keystore "$HOME/.android/debug.keystore" -storepass android -keypass android \
      -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 3650 -dname "CN=Android Debug,O=Android,C=US" >/dev/null 2>&1
  fi
}
bt() { java -jar "$BT" "$@"; }

# Розпакувати архіви (.xapk/.zip) — усередині можуть бути APK/AAB/APKS.
for z in "$WORK"/in/*.xapk "$WORK"/in/*.zip; do
  [ -f "$z" ] || continue
  unzip -q -o "$z" -d "$WORK/in/unz" '*.apk' '*.aab' '*.apks' 2>/dev/null || true
done
[ -d "$WORK/in/unz" ] && find "$WORK/in/unz" -type f -exec mv {} "$WORK/in/" \;

mode=""
shopt -s nullglob
aabs=("$WORK"/in/*.aab); apkss=("$WORK"/in/*.apks); apks=("$WORK"/in/*.apk)
if [ ${#aabs[@]} -gt 0 ]; then
  get_bundletool
  note "AAB → універсальний APK (bundletool)"
  bt build-apks --bundle="${aabs[0]}" --output="$WORK/in/u.apks" --mode=universal \
    --ks="$HOME/.android/debug.keystore" --ks-pass=pass:android --ks-key-alias=androiddebugkey --key-pass=pass:android \
    || fail "bundletool не зміг перетворити AAB"
  unzip -q -o "$WORK/in/u.apks" universal.apk -d "$WORK/app"
  mode=apk
elif [ ${#apkss[@]} -gt 0 ]; then
  get_bundletool
  cp "${apkss[0]}" "$WORK/app/app.apks"
  unzip -q -o "$WORK/app/app.apks" -d "$WORK/in/apks" || fail "Пошкоджений .apks"
  probe="$(find "$WORK/in/apks" -name 'base-master.apk' -o -name 'universal.apk' -o -name '*standalone*.apk' | head -1)"
  [ -n "$probe" ] && cp "$probe" "$WORK/app/probe.apk"
  mode=apks
elif [ ${#apks[@]} -gt 0 ]; then
  cp "${apks[@]}" "$WORK/app/"
  mode=apk
else
  fail "Не знайдено жодного APK/AAB/APKS у цілі"
fi

# ── Хто це: назва пакета, архітектури коду ─────────────────────────────────
BUILD_TOOLS="$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)"
AAPT2="$BUILD_TOOLS/aapt2"
probe_apk=""
for f in "$WORK"/app/*.apk; do
  if "$AAPT2" dump badging "$f" 2>/dev/null | grep -q "^launchable-activity:\|^package:"; then
    # базовий APK має launchable-activity; split-и — ні
    if "$AAPT2" dump badging "$f" 2>/dev/null | grep -q "^launchable-activity:"; then probe_apk="$f"; break; fi
    [ -z "$probe_apk" ] && probe_apk="$f"
  fi
done
[ -n "$probe_apk" ] || fail "Не вдалося прочитати APK (файл пошкоджений або це не APK)"
badging="$("$AAPT2" dump badging "$probe_apk" 2>/dev/null || true)"
package="$(printf '%s\n' "$badging" | sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -1)"
version="$(printf '%s\n' "$badging" | sed -n "s/^package: .*versionName='\([^']*\)'.*/\1/p" | head -1)"
label="$(printf '%s\n' "$badging" | sed -n "s/^application-label:'\([^']*\)'.*/\1/p" | head -1)"
abis="$(printf '%s\n' "$badging" | sed -n "s/^native-code: //p" | tr -d "'" | head -1)"
[ -n "$package" ] || fail "У APK не знайдено назви пакета"
[ "$probe_apk" = "$WORK/app/probe.apk" ] && rm -f "$WORK/app/probe.apk"

{
  printf 'INSTALL_MODE=%q\n' "$mode"
  printf 'PACKAGE=%q\n' "$package"
  printf 'APP_VERSION=%q\n' "$version"
  printf 'APP_LABEL=%q\n' "$label"
  printf 'NATIVE_ABIS=%q\n' "$abis"
  printf 'DISPLAY_TARGET=%q\n' "$TARGET"
} >> "$ENV_OUT"
note "Застосунок: ${label:-?} ($package) ${version:-}; код під: ${abis:-будь-який процесор}"
