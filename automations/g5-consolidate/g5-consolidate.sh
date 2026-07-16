#!/usr/bin/env bash
# Stop-hook: авто-консолідація стану пам'яті (експеримент gmi-g5-auto, G5 🟡→✅).
# Детерміновано, без AI/мережі/секретів. Ніколи не блокує Stop (|| true).
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"
python3 scripts/g5-consolidate.py experiments/gmi-g5-auto >/dev/null 2>&1 || true
