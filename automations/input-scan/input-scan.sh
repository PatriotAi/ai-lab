#!/usr/bin/env bash
# PostToolUse-хук: тріаж зовнішнього тексту в момент його потрапляння в контекст.
# Одна відповідальність: передати подію в гейт `security/spine/input_guard.py`.
#
# НАВІЩО. Скан зовнішнього входу існував із 2026-07, але викликався руками —
# автоматичним був лише шлях пам'яті між сесіями (`memory_guard.py`, дефект F-1).
# Веб і читання файлів лишались непокритими. Це та сама конструкція, що дала F-1:
# перевірка існує, але не стоїть на шляху, яким текст реально заходить.
#
# НЕ ЛАМАЄ РОБОТУ. Хук ніколи не блокує читання: за замовчуванням він лише
# додає попередження в контекст (`input_scan_blocking = false` у policy.toml).
# Будь-яка власна поломка — тиха: код виходу завжди 0.
set -uo pipefail
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
GUARD="$PROJECT_DIR/security/spine/input_guard.py"

[ -f "$GUARD" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

python3 "$GUARD" 2>/dev/null || true
exit 0
