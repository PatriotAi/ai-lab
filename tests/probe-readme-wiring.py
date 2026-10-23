#!/usr/bin/env python3
"""probe-readme-wiring.py — стенд для перевірки тверджень README (W-16, 2026-10-18).

Навіщо: README `g5-consolidate` два місяці описував Stop-хук, знятий 2026-07-31
(F-12), а парний README `g5-retrieve` досі звав «повним авто-циклом» пару з уже
знятою Stop-консолідацією. Перевірка шапки скрипта (`check_unwired_hooks`) цього
не бачить — неправду казала проза.

Покриття — перелік інцидентів і меж (Core Rule 15), по випадку на кожен:
  твердження про себе без реєстрації (інцидент g5-consolidate) · про себе на
  ІНШІЙ події · про ІНШУ автоматизацію (інцидент g5-retrieve) · пара в одному
  рядку, де бреше лише одна · реєстрація середовища зараховується · минуле,
  заперечення (і ДО, і ПІСЛЯ події), інструкція і `[?]` — не твердження · чинне
  твердження ДО маркера минулого — твердження · слово «stop» з малої — не
  подія · чистий корпус мовчить І щось перевіряє (не порожньо).

Усе в тимчасовій теці — справжні README й налаштування не чіпаються.
Запуск: python3 tests/probe-readme-wiring.py   (0 — усі випадки збігаються)
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sd", REPO / "scripts" / "security-drift.py")
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)

POLICY = """
[[wiring.environment_wired]]
script = "envhook.sh"
event = "Stop"
"""


def build(tmp: pathlib.Path, readmes: dict[str, str], hooks: dict[str, list[str]]) -> pathlib.Path:
    """readmes: тека → текст README; hooks: подія → теки, чиї скрипти зареєстровано."""
    root = tmp / "repo"
    (root / "security").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / "security" / "policy.toml").write_text(POLICY, encoding="utf-8")
    for name in ("a", "b", "env"):
        (root / "automations" / name).mkdir(parents=True)
    (root / "automations" / "env" / "envhook.sh").write_text("# envhook.sh — Stop-хук\n", encoding="utf-8")
    for name, text in readmes.items():
        (root / "automations" / name / "README.md").write_text(text, encoding="utf-8")
    settings = {"hooks": {ev: [{"hooks": [{"type": "command",
                                           "command": f"$CLAUDE_PROJECT_DIR/automations/{d}/{d}.sh"}]}
                                for d in dirs]
                          for ev, dirs in hooks.items()}}
    (root / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return root


def drift_lines(root: pathlib.Path) -> list[str]:
    return [r[1] for r in sd.check_readme_claims(root) if r[0] == sd.DRIFT]


# (назва, README-и, реєстрації, очікувані рядки з тривогою — «тека:рядок»)
CASES = [
    ("інцидент g5-consolidate: «Тригер: Stop» без реєстрації → тривога",
     {"a": "# a\n- **Тригер:** `Stop`\n"}, {}, ["a/README.md:2"]),
    ("про себе — і справді зареєстровано → тихо",
     {"a": "# a\n- **Тригер:** `Stop`\n"}, {"Stop": ["a"]}, []),
    ("про себе на ІНШІЙ події → тривога",
     {"a": "# a\n**Подія:** `Stop`\n"}, {"SessionStart": ["a"]}, ["a/README.md:2"]),
    ("інцидент g5-retrieve: про ІНШУ автоматизацію, якої нема на події → тривога",
     {"b": "# b\nпарна до `automations/a` — консолідація на Stop.\n"}, {"SessionStart": ["b"]},
     ["b/README.md:2"]),
    ("пара в одному рядку: бреше лише одна → тривога лише на одну",
     {"b": "# b\n**Разом:** `a` (Stop) + `b` (SessionStart)\n"}, {"SessionStart": ["b"]},
     ["b/README.md:2"]),
    ("пара в одному рядку: обидві правдиві → тихо",
     {"b": "# b\n**Разом:** `a` (Stop) + `b` (SessionStart)\n"}, {"Stop": ["a"], "SessionStart": ["b"]},
     []),
    ("назва з ДВОМА подіями: правдива лише одна → тривога",
     {"b": "# b\n`a` працює на SessionStart і Stop\n"}, {"SessionStart": ["a"]}, ["b/README.md:2"]),
    ("реєстрація середовища зараховується → тихо",
     {"env": "# env\n- **Тригер:** `Stop`\n"}, {}, []),
    ("реєстрація середовища на іншій події не зараховується → тривога",
     {"env": "# env\n- **Тригер:** `SessionStart`\n"}, {}, ["env/README.md:2"]),
    ("минуле («історично», «знято») — не твердження → тихо",
     {"a": "# a\n- **Тригер (історично, до 2026-07-31):** `Stop`\nStop-реєстрацію знято.\n"}, {}, []),
    ("заперечення й інструкція — не твердження → тихо",
     {"a": "# a\nЩе **не зареєстрована** на `SessionStart`.\nПовністю — зняти реєстрацію `Stop`.\n"},
     {}, []),
    ("рев'ю #94: чинне твердження ДО маркера минулого → тривога",
     {"a": "# a\n- **Тригер:** `Stop` (раніше `SessionEnd`)\n"}, {}, ["a/README.md:2"]),
    ("рев'ю #94: «найраніше» — не маркер минулого (межа слова) → тривога",
     {"a": "# a\n- **Тригер:** найраніше з усіх — `Stop`\n"}, {}, ["a/README.md:2"]),
    ("рев'ю 2026-10-23: зняття ПІСЛЯ події («`X` — знято») — не твердження → тихо",
     {"a": "# a\n- **Тригер:** `SessionEnd` — знято 2026-10-01\n"}, {}, []),
    ("рев'ю 2026-10-23: заперечення ПІСЛЯ події про іншу — не твердження → тихо",
     {"b": "# b\n`a` на `Stop` більше не підключено\n"}, {"SessionStart": ["b"]}, []),
    ("`[?]` — відкрите питання, не твердження → тихо",
     {"a": "# a\n- **[?]** Чи `a` виконується на Stop?\n"}, {}, []),
    ("«stop» з малої — не подія → тихо",
     {"a": "# a\n- **Тригер:** ручний запуск; stop вручну\n"}, {}, []),
]


def main() -> int:
    bad = 0
    for name, readmes, hooks, want in CASES:
        with tempfile.TemporaryDirectory() as td:
            root = build(pathlib.Path(td), readmes, hooks)
            got = sorted(line.rsplit("automations/", 1)[-1] for line in drift_lines(root))
        if got != sorted(want):
            bad += 1
            print(f"  ❌ {name}\n     очікували: {want}\n     отримали:  {got}")
    # Чистий корпус мовчить І перевіряє щось (не порожньо): інакше «тихо» нічого не доводить.
    with tempfile.TemporaryDirectory() as td:
        root = build(pathlib.Path(td), {"a": "# a\n- **Тригер:** `Stop`\n"}, {"Stop": ["a"]})
        rows = sd.check_readme_claims(root)
    nonempty = rows and rows[0][0] == sd.OK and "перевірено 1" in rows[0][2]
    if not nonempty:
        bad += 1
        print(f"  ❌ чистий корпус: очікували «перевірено 1, усі правдиві», отримали {rows}")
    total = len(CASES) + 1
    print(f"  твердження README: {total - bad}/{total} випадків збігаються")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
