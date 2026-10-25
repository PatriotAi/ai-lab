#!/usr/bin/env python3
"""check-ablation-tasks.py — набір задач абляції розрізняє «до» і «після».

НАВІЩО. Абляція H3 (дослідження «Вивірений розвиток», Ф3) знімає правила з постійного контексту
й дивиться, чи не впали детерміновані твердження. Твердження, яке проходить і без роботи агента,
нічого не міряє; твердження, яке не проходить навіть на справжньому рішенні, міряє шум. Обидва
випадки тихо псують H3, і в звіті цього не видно (Core Rule 15).

ЯК. Кожна задача взята з історії лабораторії: `start` — коміт, з якого стартує агент, `solution` —
коміт, яким це завдання колись реально виконали. Скрипт розгортає обидва в тимчасових git worktree
і вимагає: на старті падає **хоча б одне** твердження, на рішенні проходять **усі**. Так кожне
твердження доведене на зламаному й на чистому стані (Core Rule 15), а не лише написане.

Типи тверджень (`assertions`):
    {"type": "cmd", "run": "<команда>", "exit": 0}       одна команда з аргументами, без shell
    {"type": "contains", "path": "...", "regex": "..."}  у файлі є збіг (Python re, MULTILINE)
    {"type": "not_contains", "path": "...", "regex": "..."}  збігу немає (файлу немає — теж так)
    {"type": "exists", "path": "..."}
    {"type": "untouched", "glob": "..."}                  шляхи не змінені відносно `start`

Також перевіряється формат: унікальний slug-`id`, `start` — предок `solution`, 3–6 тверджень,
30–40 задач (межі — `--limits`). Наприкінці друкується розбиття holdout за правилом H3
(сіль `vd-h3-2026-10-24:`) з фактичною часткою — як є, без підгонки.

Запуск:
    python3 scripts/check-ablation-tasks.py [корінь] [--tasks ШЛЯХ] [--format-only] [--limits 30:40]
Код виходу: 0 — чисто · 1 — є знахідки · 2 — перевірити неможливо (нема файлу, не git-репо,
коміту немає в історії).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASKS = "experiments/verified-development/ablation-tasks.jsonl"
SALT = "vd-h3-2026-10-24:"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA = re.compile(r"^[0-9a-f]{7,40}$")
FIELDS = {"id", "start", "solution", "area", "prompt", "assertions"}
NEED = {"cmd": ("run",), "contains": ("path", "regex"), "not_contains": ("path", "regex"),
        "exists": ("path",), "untouched": ("glob",)}
CMD_TIMEOUT = 180


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def in_holdout(task_id: str) -> bool:
    """Правило H3 з пре-реєстрації: перші 8 hex sha256(сіль + ID) за модулем 10 менші за 3."""
    return int(hashlib.sha256((SALT + task_id).encode()).hexdigest()[:8], 16) % 10 < 3


def format_errors(root: Path, tasks: list[dict], lo: int, hi: int) -> tuple[list[str], list[str]]:
    """Знахідки формату й речі, які перевірити неможливо (коміту немає)."""
    errs: list[str] = []
    missing: list[str] = []
    if not lo <= len(tasks) <= hi:
        errs.append(f"задач {len(tasks)}, а має бути {lo}–{hi}")
    seen: set[str] = set()
    for n, t in enumerate(tasks, 1):
        tid = t.get("id", f"#{n}")
        for f in sorted(FIELDS - set(t)):
            errs.append(f"{tid}: бракує поля `{f}`")
        for f in sorted(set(t) - FIELDS):
            errs.append(f"{tid}: поле `{f}` поза форматом")
        if not isinstance(tid, str) or not SLUG.match(tid):
            errs.append(f"{tid}: `id` має бути slug (a-z, 0-9, дефіс)")
        elif tid in seen:
            errs.append(f"{tid}: `id` повторюється")
        seen.add(tid)
        if not str(t.get("prompt", "")).strip():
            errs.append(f"{tid}: порожній `prompt`")
        for key in ("start", "solution"):
            sha = t.get(key, "")
            if not isinstance(sha, str) or not SHA.match(sha):
                errs.append(f"{tid}: `{key}` — не SHA коміту")
            elif git(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
                missing.append(f"{tid}: коміт `{key}` {sha} не знайдено в історії")
        start, sol = t.get("start", ""), t.get("solution", "")
        if (SHA.match(str(start)) and SHA.match(str(sol))
                and git(root, "merge-base", "--is-ancestor", start, sol).returncode == 1):
            errs.append(f"{tid}: `start` не є предком `solution`")
        asserts = t.get("assertions", [])
        if not isinstance(asserts, list) or not 3 <= len(asserts) <= 6:
            errs.append(f"{tid}: тверджень має бути 3–6")
            continue
        for i, a in enumerate(asserts, 1):
            kind = a.get("type") if isinstance(a, dict) else None
            if kind not in NEED:
                errs.append(f"{tid}: твердження {i} — невідомий тип «{kind}»")
                continue
            for f in NEED[kind]:
                if not isinstance(a.get(f), str) or not a[f].strip():
                    errs.append(f"{tid}: твердження {i} ({kind}) — бракує `{f}`")
            if kind in ("contains", "not_contains") and isinstance(a.get("regex"), str):
                try:
                    re.compile(a["regex"])
                except re.error as exc:
                    errs.append(f"{tid}: твердження {i} — хибний regex ({exc})")
            if kind == "cmd" and not isinstance(a.get("exit", 0), int):
                errs.append(f"{tid}: твердження {i} — `exit` має бути цілим")
    return errs, missing


def holds(wt: Path, start: str, a: dict) -> bool:
    """Чи виконується твердження в робочому дереві `wt` (база для `untouched` — коміт `start`)."""
    kind = a["type"]
    if kind == "cmd":
        try:
            run = subprocess.run(shlex.split(a["run"]), cwd=wt, capture_output=True, text=True,
                                 timeout=CMD_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return run.returncode == a.get("exit", 0)
    if kind == "exists":
        return (wt / a["path"]).exists()
    if kind in ("contains", "not_contains"):
        path = wt / a["path"]
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
        found = text is not None and re.search(a["regex"], text, re.M) is not None
        return found if kind == "contains" else not found
    spec = f":(glob){a['glob']}"
    changed = git(wt, "diff", "--quiet", start, "--", spec).returncode != 0
    added = git(wt, "ls-files", "--others", "--exclude-standard", "--", spec).stdout.strip()
    return not changed and not added


def label(a: dict) -> str:
    return {"cmd": a.get("run"), "exists": a.get("path"), "untouched": a.get("glob")}.get(
        a["type"], f"{a.get('path')} ~ {a.get('regex')}")


def evaluate(root: Path, task: dict, tmp: Path) -> list[str]:
    """Розгорнути старт і рішення; повернути знахідки розрізнення для задачі."""
    found = []
    results = {}
    for side in ("start", "solution"):
        wt = tmp / f"{task['id']}-{side}"
        add = git(root, "worktree", "add", "--detach", "-q", str(wt), task[side])
        if add.returncode != 0:
            return [f"{task['id']}: не вдалося розгорнути `{side}` ({add.stderr.strip()[:80]})"]
        try:
            results[side] = [holds(wt, task["start"], a) for a in task["assertions"]]
        finally:
            git(root, "worktree", "remove", "--force", str(wt))
    if all(results["start"]):
        found.append(f"{task['id']}: на старті всі твердження вже проходять — задача нічого не міряє")
    for a, ok in zip(task["assertions"], results["solution"]):
        if not ok:
            found.append(f"{task['id']}: на справжньому рішенні падає «{label(a)[:70]}»")
    if not found:
        print(f"  ✓ {task['id']}: старт — падає {results['start'].count(False)} з "
              f"{len(task['assertions'])}, рішення — проходять усі")
    return found


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Набір задач абляції розрізняє «до» і «після».")
    ap.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--tasks", help=f"файл задач (типово {TASKS})")
    ap.add_argument("--format-only", action="store_true", help="лише формат, без розгортання комітів")
    ap.add_argument("--limits", default="30:40", help="межі кількості задач, «мін:макс»")
    args = ap.parse_args(argv[1:])
    root = Path(args.root)
    lo, hi = (int(x) for x in args.limits.split(":"))
    path = Path(args.tasks) if args.tasks else root / TASKS
    if not path.is_file():
        print(f"⊘ НЕ ГАНЯЛОСЬ: файлу задач нема — {path}")
        return 2
    if git(root, "rev-parse", "--git-dir").returncode != 0:
        print(f"⊘ НЕ ГАНЯЛОСЬ: {root} — не git-репозиторій; коміти задач перевірити неможливо")
        return 2
    tasks = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if raw.strip():
            try:
                tasks.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                print(f"  ✗ рядок {n}: не JSON ({exc.msg})")
                return 1
    errs, missing = format_errors(root, tasks, lo, hi)
    if not errs and not missing and not args.format_only:
        tmp = Path(tempfile.mkdtemp(prefix="vd-ablation-"))
        try:
            for t in tasks:
                errs += evaluate(root, t, tmp)
        finally:
            git(root, "worktree", "prune")
            shutil.rmtree(tmp, ignore_errors=True)
    for e in missing + errs:
        print(f"  ✗ {e}")
    hold = sorted(t["id"] for t in tasks if isinstance(t.get("id"), str) and in_holdout(t["id"]))
    total = sum(len(t.get("assertions", [])) for t in tasks)
    print(f"\n  задач: {len(tasks)} · тверджень: {total} · holdout: {len(hold)} з {len(tasks)} "
          f"({100 * len(hold) / max(len(tasks), 1):.0f}%) — правило H3, сіль {SALT}")
    if errs:
        print(f"🚩 знахідок у наборі задач: {len(errs)}")
        return 1
    if missing:
        print("⊘ НЕ ГАНЯЛОСЬ: частини комітів немає в історії (обрізаний клон?) — потрібен повний клон")
        return 2
    scope = "формат" if args.format_only else "формат і розрізнення «до/після»"
    print(f"✅ набір задач абляції коректний ({scope})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
