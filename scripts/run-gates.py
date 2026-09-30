#!/usr/bin/env python3
"""run-gates.py — декларативні гейти навичок: навичка сама заявляє, що перевіряти і коли.

НАВІЩО. Кроки на кшталт «гейт перед видачею називає відкриті вікна» існували лише
як проза в SKILL.md — тобто тримались на уважності (Core Rule 15). Тепер навичка
кладе поруч із SKILL.md файл `gates.json`, а цей виконавець запускає заявлені
перевірки в заявленій точці. Ідея — `capability.json` з `open-gsd/gsd-core`
(точка циклу · предикат · blocking · onError); рішення власника 2026-09-30 («Так»).

СХЕМА `gates.json` (версія 1; невідомий ключ — помилка, а не мовчазне ігнорування):
    {"schema": 1, "gates": [
      {"id": "windows", "point": "delivery",
       "command": ["python3", "scripts/check-windows.py"],
       "blocking": true, "onError": "halt", "timeout": 30,
       "why": "чому цей гейт існує — не менше 20 символів"}]}
ТОЧКИ (перелік закритий; нова точка = зміна коду, бо це контракт):
    verify    — перевірка цілісності репозиторію (`maintain.py verify`, набір тестів)
    delivery  — перед видачею готового (`pre-delivery-gate`)

ДВОКРОКОВИЙ КОНТРАКТ (як у gsd-core, з нашими кодами виходу):
    крок 1 — чи відпрацювала САМА перевірка: код 0/1 — так; 2, інший код, таймаут,
             помилка запуску — ні → дія за `onError` (halt = зупинка, skip = попередження);
    крок 2 — якщо відпрацювала: код 1 — знахідка; `blocking:true` → зупинка,
             `false` → попередження; код 0 — пройдено.

БЕЗПЕКА — бо гейт виконує КОМАНДУ з файла навички, тобто це виконувана поверхня:
    · `command` — список (argv), ніколи рядок: оболонки нема, ін'єкція через склейку неможлива;
    · argv[0] ∈ {python3, bash}; argv[1] — ВІДНОСНИЙ шлях до файла, що існує й лежить
      усередині репозиторію (після розрізу симлінків);
    · `timeout` 1..120 с; `why` обов'язкове (гейт без причини — театр);
    · `gates.json` входить у підпис поверхні (`check-skill-surface.py`): новий чи змінений
      гейт без записаної згоди — помилка.
ЧЕСНА МЕЖА: це реєстратор і виконавець, а не пісочниця — команда виконується з правами
користувача. Запобіжники звужують, що можна заявити, але не ізолюють виконання.

Запуск:
    python3 scripts/run-gates.py --point verify|delivery [--root DIR] [--list]
Код виходу: 0 — усе гаразд · 1 — блокуюча знахідка чи зупинка за onError ·
            2 — зламаний gates.json (схема/заборонена команда) або невідома точка
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

POINTS = ("verify", "delivery")
SKILL_ROOTS = (Path("melania-skills-ecosystem") / "skills", Path(".claude") / "skills")
ALLOWED_EXE = ("python3", "bash")
GATE_KEYS = {"id", "point", "command", "blocking", "onError", "timeout", "why"}
REQUIRED = {"id", "point", "command", "why"}
MIN_WHY = 20
MAX_TIMEOUT = 120


def validate(doc: object, skill_dir: Path, root: Path) -> tuple[list[dict], list[str]]:
    """Повертає (гейти, помилки схеми). Помилка — це зупинка, не попередження."""
    errs: list[str] = []
    gates: list[dict] = []
    if not isinstance(doc, dict) or set(doc) - {"schema", "gates"}:
        return [], ["корінь має бути {schema, gates} без сторонніх ключів"]
    if doc.get("schema") != 1:
        errs.append(f"schema має бути 1, є {doc.get('schema')!r}")
    raw = doc.get("gates")
    if not isinstance(raw, list) or not raw:
        return [], errs + ["gates має бути непорожнім списком"]
    seen: set[str] = set()
    for i, g in enumerate(raw):
        tag = f"gates[{i}]"
        if not isinstance(g, dict):
            errs.append(f"{tag}: має бути об'єктом")
            continue
        extra, missing = set(g) - GATE_KEYS, REQUIRED - set(g)
        if extra:
            errs.append(f"{tag}: невідомі ключі {sorted(extra)}")
        if missing:
            errs.append(f"{tag}: бракує {sorted(missing)}")
            continue
        gid = g["id"]
        if not isinstance(gid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", gid):
            errs.append(f"{tag}: id має бути kebab-case")
        elif gid in seen:
            errs.append(f"{tag}: дубль id «{gid}»")
        else:
            seen.add(gid)
        if g["point"] not in POINTS:
            errs.append(f"{tag}: невідома точка {g['point']!r} (дозволені {list(POINTS)})")
        if g.get("onError", "halt") not in ("halt", "skip"):
            errs.append(f"{tag}: onError має бути halt або skip")
        if not isinstance(g.get("blocking", True), bool):
            errs.append(f"{tag}: blocking має бути true/false")
        t = g.get("timeout", 30)
        if not isinstance(t, int) or isinstance(t, bool) or not 1 <= t <= MAX_TIMEOUT:
            errs.append(f"{tag}: timeout має бути цілим 1..{MAX_TIMEOUT}")
        if not isinstance(g["why"], str) or len(g["why"].strip()) < MIN_WHY:
            errs.append(f"{tag}: why ≥{MIN_WHY} символів — гейт без причини це театр")
        errs += [f"{tag}: {e}" for e in check_command(g["command"], root)]
        gates.append(g)
    return gates, errs


def check_command(cmd: object, root: Path) -> list[str]:
    if not isinstance(cmd, list) or len(cmd) < 2 or not all(isinstance(c, str) for c in cmd):
        return ["command має бути списком рядків [виконавець, скрипт, …] — не рядком"]
    if cmd[0] not in ALLOWED_EXE:
        return [f"виконавець «{cmd[0]}» заборонений (дозволені {list(ALLOWED_EXE)})"]
    script = Path(cmd[1])
    if script.is_absolute() or ".." in script.parts:
        return [f"шлях «{cmd[1]}» має бути відносним і без «..»"]
    target = (root / script).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return [f"шлях «{cmd[1]}» виходить за межі репозиторію (після розрізу симлінків)"]
    if not target.is_file():
        return [f"скрипт «{cmd[1]}» не існує — гейт, що не може запуститись, не гейт"]
    return []


def discover(root: Path) -> tuple[list[tuple[str, dict]], list[str]]:
    """Усі гейти всіх навичок: [(навичка, гейт)], помилки."""
    found: list[tuple[str, dict]] = []
    errs: list[str] = []
    for rel in SKILL_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            f = d / "gates.json"
            if d.is_symlink() or not f.is_file():
                continue
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errs.append(f"{d.name}/gates.json: нечитабельний ({exc})")
                continue
            gates, e = validate(doc, d, root)
            errs += [f"{d.name}/gates.json: {x}" for x in e]
            found += [(d.name, g) for g in gates]
    return found, errs


def run_gate(root: Path, skill: str, g: dict, verbose: bool) -> tuple[str, str]:
    """(статус, рядок): pass | finding | warn | fail."""
    label = f"{skill}/{g['id']}"
    blocking, on_error = g.get("blocking", True), g.get("onError", "halt")
    try:
        p = subprocess.run(g["command"], cwd=root, capture_output=True, text=True,
                           timeout=g.get("timeout", 30))
        code, out = p.returncode, (p.stdout or p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        code, out = -1, f"таймаут {g.get('timeout', 30)} с"
    except OSError as exc:
        code, out = -1, f"не вдалося запустити: {exc}"
    first = out.splitlines()[0][:110] if out else ""
    text = out if verbose else first
    if code == 0:
        return "pass", f"✅ {label} — {text}" if text else f"✅ {label}"
    if code == 1:                                       # перевірка відпрацювала й знайшла
        if blocking:
            return "finding", f"❌ {label} — знахідка (blocking): {text}"
        return "warn", f"⚠️  {label} — знахідка (не блокує): {text}"
    why = f"перевірка сама не відпрацювала (код {code}): {text}"   # крок 1 контракту
    if on_error == "skip":
        return "warn", f"⚠️  {label} — {why} [onError=skip]"
    return "fail", f"❌ {label} — {why} [onError=halt]"


def main(argv: list[str]) -> int:
    args = argv[1:]
    root = Path(__file__).resolve().parents[1]
    if "--root" in args:
        i = args.index("--root")
        root = Path(args[i + 1]).resolve()
        del args[i:i + 2]
    verbose, listing = "--verbose" in args, "--list" in args
    point = args[args.index("--point") + 1] if "--point" in args and args.index("--point") + 1 < len(args) else None
    if not listing and point not in POINTS:
        print(f"run-gates: потрібно --point {'|'.join(POINTS)}", file=sys.stderr)
        return 2

    found, errs = discover(root)
    if errs:
        print(f"🚩 gates.json зламано — {len(errs)}:")
        for e in errs:
            print(f"  ✗ {e}")
        return 2
    if listing:
        for skill, g in found:
            print(f"{g['point']:9} {skill}/{g['id']}  {' '.join(g['command'])}")
        print(f"гейтів: {len(found)}")
        return 0

    mine = [(s, g) for s, g in found if g["point"] == point]
    if not mine:
        print(f"гейтів у точці «{point}» немає")
        return 0
    worst = 0
    for skill, g in mine:
        status, line = run_gate(root, skill, g, verbose)
        print(f"  {line}")
        if status in ("finding", "fail"):
            worst = 1
    print(f"точка «{point}»: {'є зупинка' if worst else 'усе гаразд'} ({len(mine)} гейтів)")
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
