#!/usr/bin/env python3
"""g5-consolidate — авто-консолідація стану пам'яті (експеримент gmi-g5-auto).

Детерміновано (без AI/мережі/секретів) регенерує `AUTO-STATE.md` для теки з
git-історії: HEAD, гілка, останні коміти, що торкались теки, і список файлів.
Прибирає ручний крок «редагування пакета» → рух G5 🟡→✅.

Використання:
    python3 scripts/g5-consolidate.py [<тека> ...]
За замовчуванням: experiments/gmi-g5-auto
"""
from __future__ import annotations
import subprocess, sys, os, datetime, pathlib


def git(*args: str, cwd: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=True).stdout.strip()


def repo_root(start: str) -> str:
    return git("rev-parse", "--show-toplevel", cwd=start)


def consolidate(target: str) -> str:
    target = os.path.abspath(target)
    root = repo_root(os.path.dirname(target) or ".")
    rel = os.path.relpath(target, root)
    head = git("rev-parse", "--short", "HEAD", cwd=root)
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commits = git("log", "-n", "10", "--pretty=- %h · %s", "--", rel, cwd=root) or "- (немає комітів для теки)"
    # AUTO-STATE.md — сам згенерований артефакт: не перелічуємо його в списку файлів,
    # інакше вміст різниться між 1-м і 2-м прогоном (втрата ідемпотентності)
    files = sorted(p.name for p in pathlib.Path(target).iterdir()
                   if p.is_file() and p.name != "AUTO-STATE.md") if os.path.isdir(target) else []
    files_md = "\n".join(f"- `{f}`" for f in files) or "- (порожньо)"
    return (
        f"# AUTO-STATE — {rel} (авто-консолідація)\n\n"
        f"> Згенеровано `scripts/g5-consolidate.py` детерміновано з git. **Не редагувати вручну.**\n\n"
        f"- **Час:** {now}\n- **Гілка:** {branch}\n- **HEAD:** {head}\n\n"
        f"## Останні коміти теки\n{commits}\n\n"
        f"## Файли теки\n{files_md}\n"
    )


def main(argv: list[str]) -> int:
    targets = argv[1:] or ["experiments/gmi-g5-auto"]
    for t in targets:
        if not os.path.isdir(t):
            print(f"g5-consolidate: пропущено (не тека): {t}", file=sys.stderr)
            continue
        try:
            body = consolidate(t)
        except subprocess.CalledProcessError:
            # тека поза git-репозиторієм (або git недоступний) — керована відмова,
            # а не сирий трейсбек: хук не має валити сесію через це
            print(f"g5-consolidate: пропущено (поза git-репозиторієм): {t}", file=sys.stderr)
            continue
        out = os.path.join(t, "AUTO-STATE.md")
        pathlib.Path(out).write_text(body, encoding="utf-8")
        print(f"g5-consolidate: оновлено {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
