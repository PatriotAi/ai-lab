# automations/g5-retrieve

**Одна відповідальність:** авто-**витяг** персистованої пам'яті на старті сесії (SessionStart-хук) —
друга половина G5-циклу (парна до `automations/g5-consolidate` — консолідація на Stop).

- **Тригер:** `SessionStart` (реєстрація в `.claude/settings.json`, окремим записом — не чіпає базовий digest).
- **Дія:** `g5-retrieve.sh` → `scripts/g5-retrieve.py` → дістає з durable continuation-пакета
  (`experiments/**/g5-package.md`, узагальнено) секції **STATE · OPEN THREADS · NEXT STEP**
  і віддає їх у контекст сесії (`additionalContext`).
- **Властивості:** детерміновано, **без AI/мережі/секретів**, ніколи не блокує старт.

**Разом:** `g5-consolidate` (Stop) + `g5-retrieve` (SessionStart) = **повний авто-цикл G5** →
нова сесія автоматично «пам'ятає, де ми», без ручного вставляння пакета. Узагальнено на будь-яку
теку з `g5-package.md`.
