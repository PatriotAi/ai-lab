#!/usr/bin/env python3
"""g5-retrieve — авто-витяг персистованої пам'яті (друга половина G5-циклу).

Детерміновано (без AI/мережі/секретів) дістає з durable continuation-пакета компактний
resume-дайджест: STATE · OPEN THREADS · EXACT NEXT STEP. Парна до `g5-consolidate.py`
(консолідація) → разом дають повний авто-цикл G5 (🟡→✅).

Використання:
    python3 scripts/g5-retrieve.py [<файл-пакета або тека> ...]
За замовчуванням: найновіший `experiments/**/g5-package.md` (узагальнено на будь-яку теку).
"""
from __future__ import annotations
import sys, os, glob, pathlib

# заголовки секцій, які складають resume-дайджест (за ключовими словами, регістронезалежно)
WANT = ("STATE", "OPEN THREADS", "NEXT STEP")


def find_default() -> str | None:
    cands = glob.glob("experiments/**/g5-package.md", recursive=True)
    cands += glob.glob("experiments/**/NEXT-ITERATION.md", recursive=True)
    if not cands:
        return None
    return max(cands, key=lambda p: os.path.getmtime(p))


def resolve(arg: str) -> str | None:
    if os.path.isfile(arg):
        return arg
    if os.path.isdir(arg):
        for name in ("g5-package.md", "NEXT-ITERATION.md"):
            p = os.path.join(arg, name)
            if os.path.isfile(p):
                return p
    return None


def extract(md: str) -> str:
    lines = md.splitlines()
    out, keep = [], False
    for ln in lines:
        if ln.startswith("## "):
            keep = any(w in ln.upper() for w in WANT)
        if keep:
            out.append(ln)
    return "\n".join(out).strip()


def digest(path: str) -> str:
    md = pathlib.Path(path).read_text(encoding="utf-8")
    body = extract(md) or "(секції STATE/OPEN THREADS/NEXT STEP не знайдено)"
    return f"## Відновлена пам'ять G5 (авто-витяг) — `{path}`\n\n{body}\n"


def main(argv: list[str]) -> int:
    targets = [t for t in (resolve(a) for a in argv[1:]) if t]
    if not argv[1:]:
        d = find_default()
        if d:
            targets = [d]
    if not targets:
        print("g5-retrieve: durable-пакет не знайдено (немає що витягати).", file=sys.stderr)
        return 0
    for p in targets:
        print(digest(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
