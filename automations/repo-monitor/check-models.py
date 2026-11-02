#!/usr/bin/env python3
"""check-models.py — models.json монітора узгоджений із датованим знімком моделей лабораторії.

НАВІЩО. Закон не-старіння: назви моделей — лише в датованому знімку. models.json монітора — похідне
від нього (роль → клас → модель). Ця перевірка ловить дрейф: знімок замінили, а models.json
лишився з моделлю, якої в знімку вже немає; або роль отримала слабший клас, ніж їй належить.

ПЕРЕВІРЯЄ. (1) файл знімка існує; (2) кожна `roles.*.model` є в знімку; (3) кожен `roles.*.class`
є в таблиці ролей знімка; (4) `agent` — відомий псевдонім і відповідає родині моделі; (5) усі моделі
ролей є в `class_order`; (6) порядок класів: home ≤ worker ≤ diagnosis.

  check-models.py [MODELS_JSON] [--root REPO]      код 0 — узгоджено; 1 — розбіжність; 2 — не прочитано
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENTS = {"haiku", "sonnet", "opus", "fable"}


def main() -> int:
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("models", nargs="?", default=str(here.parent / "models.json"))
    ap.add_argument("--root", default=str(here.parents[2]))
    a = ap.parse_args()
    try:
        cfg = json.loads(Path(a.models).read_text(encoding="utf-8"))
        snap_path = Path(a.root) / cfg["snapshot"]
        snap = snap_path.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"помилка: не прочитано ({e})", file=sys.stderr)
        return 2
    order = cfg.get("class_order", [])
    probs = []
    for role, r in (cfg.get("roles") or {}).items():
        m, cls, ag = r.get("model", ""), r.get("class", ""), r.get("agent", "")
        if f"`{m}`" not in snap:
            probs.append(f"{role}: модель {m} відсутня в знімку {snap_path.name}")
        if not cls or cls not in snap:
            probs.append(f"{role}: клас «{cls}» відсутній у таблиці ролей знімка")
        if ag not in AGENTS or ag not in m:
            probs.append(f"{role}: agent «{ag}» невідомий або не відповідає моделі {m}")
        if m not in order:
            probs.append(f"{role}: модель {m} відсутня в class_order")
    roles = cfg.get("roles") or {}
    try:
        rank = [order.index(roles[x]["model"]) for x in ("home", "worker", "diagnosis")]
        if not rank[0] <= rank[1] <= rank[2]:
            probs.append("порядок класів порушено: має бути home ≤ worker ≤ diagnosis")
    except (KeyError, ValueError):
        probs.append("немає однієї з ролей home/worker/diagnosis або її моделі в class_order")
    for p in probs:
        print(f"  ✗ {p}")
    if not probs:
        print(f"models.json узгоджено зі знімком {snap_path.name} ({len(roles)} ролі)")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
