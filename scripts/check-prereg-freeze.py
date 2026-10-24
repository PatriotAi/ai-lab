#!/usr/bin/env python3
"""check-prereg-freeze.py — заморожена пре-реєстрація не правиться після заморозки.

НАВІЩО. Пре-реєстрація (`experiments/*/preregistration.md`) фіксує гіпотези, пороги й
правила аналізу ДО збору даних. Без перевірки «заморозка» — лише слово: пороги можна тихо
підігнати під дані, і в звіті цього не видно (Core Rule 15, «звіт замість доказу»).

ЩО ПЕРЕВІРЯЄТЬСЯ. Якщо в шапці стоїть `**SHA:** <коміт>`, тіло документа — від першого
заголовка `## ` до `## Журнал відхилень` — мусить збігатися з тілом у тому коміті.
Шапка (статус, рядок заморозки) і сам журнал відхилень змінюватися можуть: туди й
записуються свідомі відхилення з причиною.

Не заморожено (`**SHA:** —`) — чернетка, перевіряти нічого. Але якщо в історії git
файл УЖЕ мав коміт заморозки, а зараз рядка SHA немає чи він пошкоджений — це зняття
заморозки, а не чернетка: інакше достатньо стерти SHA, щоб правки порогів пройшли мовчки
(рев'ю Codex до PR #96). Так само SHA мусить лишатися ПЕРВІСНИМ — тим, що вперше записаний
в історії: підставити SHA пізнішого коміту, де тіло вже змінене, — це перезаморозка без
журналу відхилень (друге рев'ю Codex до PR #96).

Запуск:
    python3 scripts/check-prereg-freeze.py [корінь]
Код виходу: 0 — чисто · 1 — тіло змінено після заморозки або заморозку знято ·
2 — коміт заморозки не знайдено.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SHA = re.compile(r"\*\*SHA:\*\*\s*`?([0-9a-f]{7,40})`?")
JOURNAL = "## Журнал відхилень"


def body(text: str) -> list[str]:
    """Тіло між першим `## ` і журналом відхилень — те, що заморожується."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
    end = next((i for i, ln in enumerate(lines) if ln.startswith(JOURNAL)), len(lines))
    return lines[start:end]


def frozen_text(root: Path, sha: str, rel: str) -> str | None:
    run = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=root,
                         capture_output=True, text=True)
    return run.stdout if run.returncode == 0 else None


def original_freeze(root: Path, rel: str) -> str | None:
    """Первісний SHA заморозки: той, що стоїть у найстарішій версії файлу з рядком SHA."""
    log = subprocess.run(["git", "log", "--reverse", "--format=%H", "--", rel], cwd=root,
                         capture_output=True, text=True)
    for sha in log.stdout.split():
        old = frozen_text(root, sha, rel)
        m = SHA.search(old or "")
        if m:
            return m.group(1)
    return None


def resolve(root: Path, sha: str) -> str:
    run = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"],
                         cwd=root, capture_output=True, text=True)
    return run.stdout.strip() or sha


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    if not root.is_dir():
        print(f"check-prereg-freeze: немає такої теки: {root}", file=sys.stderr)
        return 2
    changed: list[str] = []
    missing: list[str] = []
    for path in sorted((root / "experiments").rglob("preregistration.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = SHA.search(text)
        rel = path.relative_to(root).as_posix()
        first = original_freeze(root, rel)
        if not m:
            if first:
                changed.append(f"{rel}: заморозку знято — рядок SHA відсутній чи пошкоджений, "
                               f"а історія вже мала заморозку {first}")
            continue
        if first and resolve(root, first) != resolve(root, m.group(1)):
            changed.append(f"{rel}: SHA заморозки підмінено — первісний {first}, "
                           f"зараз {m.group(1)}")
            continue
        old = frozen_text(root, m.group(1), rel)
        if old is None:
            missing.append(f"{rel}: коміт заморозки {m.group(1)} не знайдено")
            continue
        now, then = body(text), body(old)
        if now != then:
            diff = next((i for i, (a, b) in enumerate(zip(now, then)) if a != b),
                        min(len(now), len(then)))
            line = (now[diff] if diff < len(now) else "(рядок видалено)")[:90]
            changed.append(f"{rel}: тіло змінено після заморозки {m.group(1)} — «{line}»")
    for f in missing:
        print(f"  ✗ {f}")
    for f in changed:
        print(f"  ✗ {f}")
    if changed:
        print("\n  Після заморозки гіпотези, пороги й правила аналізу не правляться. "
              "Свідому зміну запиши в «Журнал відхилень», а тіло поверни як було.")
        return 1
    if missing:
        return 2
    print("✅ заморожені пре-реєстрації не змінено після заморозки")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
