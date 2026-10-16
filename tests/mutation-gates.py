#!/usr/bin/env python3
"""mutation-gates.py — мутаційна перевірка `scripts/run-gates.py`.

Виконавець гейтів запускає КОМАНДУ з файла навички, тож його запобіжники — це
безпека, а не косметика. Канарки секції 24 зелені; тут скрипт ЛАМАЄТЬСЯ навмисно,
і код виходу відповідного сценарію мусить змінитись. Мутант, що вижив, або
«не застосовний» (рядок змінився) — діра в ПЕРЕВІРКАХ. Принцип той самий, що в
`tests/mutation-surface.py`. Запуск: python3 tests/mutation-gates.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = (REPO / "scripts" / "run-gates.py").read_text(encoding="utf-8")


def root(work: pathlib.Path, tag: str, *, exit_code=0, blocking=True, on_error="halt", patch=None):
    d = work / tag
    (d / "melania-skills-ecosystem" / "skills" / "alpha").mkdir(parents=True)
    (d / "scripts").mkdir()
    (d / "scripts" / "chk.py").write_text(f"import sys\nsys.exit({exit_code})\n", encoding="utf-8")
    gate = {"id": "chk", "point": "verify", "command": ["python3", "scripts/chk.py"],
            "blocking": blocking, "onError": on_error, "timeout": 5,
            "why": "перевірка для мутаційного сценарію — причина достатньої довжини"}
    gate.update(patch or {})
    (d / "melania-skills-ecosystem" / "skills" / "alpha" / "gates.json").write_text(
        json.dumps({"schema": 1, "gates": [gate]}, ensure_ascii=False), encoding="utf-8")
    return d


def run(script: pathlib.Path, d: pathlib.Path) -> int:
    return subprocess.run([sys.executable, str(script), "--point", "verify", "--root", str(d)],
                          capture_output=True, text=True).returncode


# (назва, що ламаємо, на що, параметри сценарію, код справного виконавця)
MUTANTS = [
    ("onError ігнорується (halt стає попередженням)",
     '    if on_error == "skip":', "    if True:",
     dict(exit_code=2, on_error="halt"), 1),
    ("blocking ігнорується (знахідка ніколи не зупиняє)",
     "        if blocking:\n            return \"finding\"", "        if False:\n            return \"finding\"",
     dict(exit_code=1, blocking=True), 1),
    ("дозволено будь-якого виконавця",
     "    if cmd[0] not in ALLOWED_EXE:", "    if False:",
     dict(patch={"command": ["curl", "scripts/chk.py"]}), 2),
    ("шлях із «..» дозволено",
     '    if script.is_absolute() or ".." in script.parts:', "    if script.is_absolute():",
     dict(patch={"command": ["python3", "scripts/../scripts/chk.py"]}), 2),
    ("невідомі ключі мовчки ігноруються",
     "        if extra:", "        if False:",
     dict(patch={"shell": True}), 2),
    ("вихід за межі репо після симлінка не ловиться",
     "        target.relative_to(root.resolve())", "        target.relative_to(target.anchor)",
     dict(patch={"command": ["python3", "scripts/esc/hostname"]}, link=True), 2),
]


def main() -> int:
    survived = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        for i, (name, old, new, params, want) in enumerate(MUTANTS):
            if old not in SRC:
                print(f"  ⚠️  «{name}»: цільовий рядок не знайдено — НЕ застосовний (рахується як ВИЖИВ)")
                survived += 1
                continue
            link = params.pop("link", False)

            def scenario(script: pathlib.Path, tag: str) -> int:
                d = root(work, tag, **params)
                if link:
                    (d / "scripts" / "esc").symlink_to("/etc")
                return run(script, d)

            ok_dir = work / f"ok{i}"
            ok_dir.mkdir()
            ok_script = ok_dir / "run-gates.py"
            ok_script.write_text(SRC, encoding="utf-8")
            mut_dir = work / f"mut{i}"
            mut_dir.mkdir()
            mut_script = mut_dir / "run-gates.py"
            mut_script.write_text(SRC.replace(old, new, 1), encoding="utf-8")
            good, bad = scenario(ok_script, f"t-ok{i}"), scenario(mut_script, f"t-mut{i}")
            if good != want:
                print(f"  ⚠️  «{name}»: справний виконавець дав {good}, очікувалось {want} — сценарій забруднений")
                survived += 1
            elif bad == good:
                print(f"  ❌ «{name}»: ВИЖИВ (код {bad} і на справному, і на зламаному)")
                survived += 1
            else:
                print(f"  ✅ «{name}»: спіймано (справний {good} → мутант {bad})")
    total = len(MUTANTS)
    if survived:
        print(f"  ❌ мутанти: {total - survived}/{total} спіймано, {survived} ВИЖИЛО")
        return 1
    print(f"  мутаційне тестування виконавця гейтів: {total}/{total} мутантів спіймано")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
