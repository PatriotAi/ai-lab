#!/usr/bin/env python3
"""mutation-surface.py — мутаційна перевірка `scripts/check-skill-surface.py`.

НАВІЩО. 20 канарок секції 23 набору були зелені з першого разу — а це стан, якому
без доказу вірити не можна: зелений набір доводить рівно стільки, скільки в ньому
перевірок, що здатні червоніти. Тут скрипт ЛАМАЄТЬСЯ навмисно (мутант), і для кожного
мутанта відтворюється сценарій відповідної канарки: код виходу мусить ЗМІНИТИСЬ
відносно справного скрипта. Мутант, що вижив, — діра в ПЕРЕВІРКАХ, не в коді.

Мутант «не застосовний» (цільовий рядок у скрипті змінився) рахується як ВИЖИВ, а не
успіх: інакше рефакторинг тихо вимикав би перевірку, не залишаючи сліду
(так саме сталось у Фазі S5 — і харнес того разу повівся чесно).

Кожен мутант — окрема КОПІЯ скрипта в тимчасовій теці; оригінал не чіпається.
Запуск: python3 tests/mutation-surface.py   (код 0 — усі спіймані)
"""
from __future__ import annotations

import datetime
import os
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = (REPO / "scripts" / "check-skill-surface.py").read_text(encoding="utf-8")
TOMORROW = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()


def make_script(work: pathlib.Path, name: str, text: str) -> pathlib.Path:
    """Мутант живе у власному корені зі симлінком на справжню security/, щоб працював імпорт згоди."""
    d = work / name
    (d / "scripts").mkdir(parents=True)
    os.symlink(REPO / "security", d / "security")
    path = d / "scripts" / "check-skill-surface.py"
    path.write_text(text, encoding="utf-8")
    return path


def tree(work: pathlib.Path, tag: str, consent_rows: str = ""):
    d = work / f"tree-{tag}"
    sk = d / "melania-skills-ecosystem" / "skills" / "alpha"
    (sk / "scripts").mkdir(parents=True)
    (d / "security").mkdir()
    (sk / "SKILL.md").write_text("---\nname: alpha\nallowed-tools:\n  - Read\n---\n# a\n", encoding="utf-8")
    (sk / "scripts" / "guard.py").write_text("print(1)\n", encoding="utf-8")
    (d / "security" / "consent.md").write_text(
        "| rule | until | причина | ціль |\n|---|---|---|---|\n" + consent_rows, encoding="utf-8")
    return d, sk


def run(script: pathlib.Path, root: pathlib.Path, *args: str) -> int:
    return subprocess.run([sys.executable, str(script), "--root", str(root), *args],
                          capture_output=True, text=True).returncode


def added_script(work, script, tag):
    d, sk = tree(work, tag)
    run(script, d, "--init")
    (sk / "scripts" / "new.py").write_text("print(2)\n", encoding="utf-8")
    return run(script, d)


def consent_other_skill(work, script, tag):
    d, sk = tree(work, tag, consent_rows=(
        f"| skill-surface | {TOMORROW} | Згода на інший скіл beta, не на alpha, у пробі | beta |\n"))
    run(script, d, "--init")
    (sk / "scripts" / "new.py").write_text("print(2)\n", encoding="utf-8")
    return run(script, d)


def snapshots_noise(work, script, tag):
    d, sk = tree(work, tag)
    run(script, d, "--init")
    (sk / "scripts" / ".snapshots").mkdir()
    (sk / "scripts" / ".snapshots" / "latest.json").write_text('{"x":1}', encoding="utf-8")
    return run(script, d)


def widen_tools(work, script, tag):
    d, sk = tree(work, tag)
    run(script, d, "--init")
    (sk / "SKILL.md").write_text(
        "---\nname: alpha\nallowed-tools:\n  - Read\n  - Bash(*)\n---\n# a\n", encoding="utf-8")
    return run(script, d)


def update_without_consent(work, script, tag):
    """`--update` мусить відмовити (код 1) і не змінити базу; мутант, що дозволяє, дає 0."""
    d, sk = tree(work, tag)
    run(script, d, "--init")
    (sk / "scripts" / "new.py").write_text("print(2)\n", encoding="utf-8")
    return run(script, d, "--update")


# (назва, що ламаємо, на що міняємо, сценарій, код справного скрипта)
MUTANTS = [
    ("нові скрипти більше не є розширенням",
     '        expanding = True\n        notes.append(f"додано скрипт',
     '        notes.append(f"додано скрипт', added_script, 1),
    ("згода діє на БУДЬ-ЯКУ ціль (ціль не звіряється)",
     '"require_target": True}]}', '"require_target": False}]}', consent_other_skill, 1),
    (".snapshots рахується поверхнею",
     'SKIP_PARTS = {".snapshots", "__pycache__"}', "SKIP_PARTS = set()", snapshots_noise, 0),
    ("нові права більше не є розширенням",
     "            if add:\n                expanding = True",
     "            if add:\n                expanding = False", widen_tools, 1),
    ("--update оновлює базу попри розширення без згоди",
     "    if errs:\n        print(f\"🚩 поверхня розширена без згоди",
     "    if errs and not update:\n        print(f\"🚩 поверхня розширена без згоди",
     update_without_consent, 1),
]


def main() -> int:
    survived = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        for i, (name, old, new, scenario, want) in enumerate(MUTANTS):
            if old not in SRC:
                print(f"  ⚠️  «{name}»: цільовий рядок не знайдено — мутант НЕ застосовний "
                      f"(рахується як ВИЖИВ: перевірка могла тихо перестати щось міряти)")
                survived += 1
                continue
            good = scenario(work, make_script(work, f"ok{i}", SRC), f"ok{i}")
            if good != want:
                print(f"  ⚠️  «{name}»: справний скрипт дав {good}, очікувалось {want} — сценарій забруднений")
                survived += 1
                continue
            bad = scenario(work, make_script(work, f"mut{i}", SRC.replace(old, new, 1)), f"mut{i}")
            if bad == good:
                print(f"  ❌ «{name}»: ВИЖИВ (код {bad} і на справному, і на зламаному)")
                survived += 1
            else:
                print(f"  ✅ «{name}»: спіймано (справний {good} → мутант {bad})")
    total = len(MUTANTS)
    if survived:
        print(f"  ❌ мутанти: {total - survived}/{total} спіймано, {survived} ВИЖИЛО")
        return 1
    print(f"  мутаційне тестування поверхні: {total}/{total} мутантів спіймано")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
