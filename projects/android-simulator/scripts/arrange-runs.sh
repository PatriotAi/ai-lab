#!/usr/bin/env bash
# arrange-runs.sh — розкласти завантажені архіви прогонів по теках <label>/.
#
# Одна відповідальність: привести теку з архівами до вигляду runs/<label>/results.
# Кілька архівів GitHub кладе як runs/sim-<label>/…, а один-єдиний — прямо в runs/
# (без підтеки); тоді назву беремо з плану ($MATRIX). Повторний запуск — безпечний.
set -euo pipefail
root="${1:?тека з архівами}"
for d in "$root"/sim-*; do
  [ -d "$d" ] && mv "$d" "$root/${d#"$root"/sim-}"
done
if [ -d "$root/results" ]; then
  label="$(python3 -c 'import json,os; print(json.loads(os.environ["MATRIX"])["include"][0]["label"])' 2>/dev/null || echo run)"
  mkdir -p "$root/$label"
  mv "$root/results" "$root/$label/"
  [ -f "$root/target.env" ] && mv "$root/target.env" "$root/$label/"
fi
exit 0
