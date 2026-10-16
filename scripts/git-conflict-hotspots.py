#!/usr/bin/env python3
"""git-conflict-hotspots.py — де в історії злиття насправді болять.

НАВІЩО. Рішення про структуру файлів (union для журналу, «файл на запис», рецепт
для похідних файлів) мають спиратися на виміряну частоту конфліктів, а не на
відчуття. Git зберігає всю історію злиттів, тож відповідь можна переграти.

ЯК. Кожне злиття з двома батьками переграється через `git merge-tree --write-tree`:
лише читання — робоча тека, індекс і посилання не змінюються. Атрибути злиття
задаються через `git --attr-source=<дерево>`, а не правкою .git, тож вимір:
  (типово)          СИРИЙ — без атрибутів, тобто як було в момент злиття;
  --current-attrs   з атрибутами поточної робочої теки (що болітиме тепер);
  --replay-union P  додатково: конфлікти файла P переграються з «P merge=union»,
                    і результат звіряється з тим, що людина справді закомітила.

Запуск:  python3 scripts/git-conflict-hotspots.py [-C корінь] [--revs REV ...] [--top N]
                 [--current-attrs] [--replay-union ШЛЯХ]
Код виходу: 0 — звіт надруковано · 2 — помилка виклику.
"""
from __future__ import annotations

import argparse
import collections
import subprocess
import sys


def git(repo: str, *args: str, inp: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, input=inp)


def attr_tree(repo: str, content: str) -> str:
    """Дерево з єдиним .gitattributes — джерело атрибутів для --attr-source."""
    blob = git(repo, "hash-object", "-w", "--stdin", inp=content).stdout.strip()
    return git(repo, "mktree", inp=f"100644 blob {blob}\t.gitattributes\n").stdout.strip()


def replay(repo: str, p1: str, p2: str, attrs: str | None) -> tuple[str, list[str], int]:
    pre = ["--attr-source", attrs] if attrs else []
    r = git(repo, *pre, "merge-tree", "--write-tree", "--name-only", "--no-messages", p1, p2)
    lines = r.stdout.splitlines()
    return (lines[0] if lines else ""), [l for l in lines[1:] if l.strip()], r.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Частота конфліктів злиття за історією.")
    ap.add_argument("-C", dest="repo", default=".")
    ap.add_argument("--revs", nargs="+", default=None)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--current-attrs", action="store_true")
    ap.add_argument("--replay-union", metavar="ШЛЯХ")
    a = ap.parse_args()

    if git(a.repo, "rev-parse", "--git-dir").returncode != 0:
        print("❌ не git-репозиторій", file=sys.stderr)
        return 2
    revs = a.revs or ["HEAD"] + (["origin/main"] if git(a.repo, "rev-parse", "-q", "--verify",
                                                         "origin/main").returncode == 0 else [])
    empty = git(a.repo, "hash-object", "-t", "tree", "/dev/null").stdout.strip()
    base_attrs = None if a.current_attrs else empty

    merges = sorted(set(git(a.repo, "rev-list", "--merges", *revs).stdout.split()))
    per_file: collections.Counter = collections.Counter()
    conflicted: list[tuple[str, str, str, list[str]]] = []
    for m in merges:
        ps = git(a.repo, "rev-list", "--parents", "-n1", m).stdout.split()[1:]
        if len(ps) != 2:
            continue
        _, files, rc = replay(a.repo, ps[0], ps[1], base_attrs)
        if rc == 1:
            conflicted.append((m, ps[0], ps[1], files))
            per_file.update(set(files))
        elif rc != 0:
            print(f"❌ merge-tree не відпрацював на {m[:7]}", file=sys.stderr)
            return 2

    mode = "з поточними атрибутами" if a.current_attrs else "сирий вимір, без атрибутів"
    print(f"Злиттів переграно: {len(merges)} · з конфліктами: {len(conflicted)} ({mode})")
    for f, n in per_file.most_common(a.top):
        print(f"{n:4d}  {f}")

    if a.replay_union:
        path = a.replay_union
        union_attrs = attr_tree(a.repo, f"{path} merge=union\n")
        rows = []
        for m, p1, p2, files in conflicted:
            if path not in files:
                continue
            tree, files_u, _ = replay(a.repo, p1, p2, union_attrs)
            ub = git(a.repo, "rev-parse", f"{tree}:{path}").stdout.strip()
            hb = git(a.repo, "rev-parse", f"{m}:{path}").stdout.strip()
            has = lambda rev: "\n<<<<<<<" in "\n" + git(a.repo, "show", f"{rev}:{path}").stdout
            markers = has(tree) if tree else False
            inherited = markers and (has(p1) or has(p2))
            rows.append((m[:7], path in files_u, ub == hb, markers, inherited))
        resolved = sum(not r[1] for r in rows)
        print(f"--- union для {path}: конфліктів в історії {len(rows)} · union розв'язує {resolved}/{len(rows)} · "
              f"байт-у-байт як у людини {sum(r[2] for r in rows)}/{len(rows)} · з рядками-маркерами "
              f"{sum(r[3] for r in rows)} (успадковано від батьків: {sum(r[4] for r in rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
