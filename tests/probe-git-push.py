#!/usr/bin/env python3
"""probe-git-push.py — W-43: пуш у захищену гілку будь-якою формою — R4.

ЩО ЗАКРИВАЄ. До 2026-11-08 правило `merge-to-main` ловило пуш у `main` лише
підрядком однієї форми. Інші форми того самого незворотного кроку проходили як
звичайна команда (R2): призначення через refspec (`HEAD:main`,
`гілка:refs/heads/main`), прапорець між словами (`-u`), видалення гілки,
`--all`/`--mirror`, і пуш без refspec, коли поточна гілка — `main` або її
пуш-ціль налаштовано на `main`. Знайдено в R5 (`experiments/agent-reliability/r5`).

ЯК ПЕРЕВІРЯЄ. Справжній `classify()` на справжніх тимчасових git-репозиторіях
(гілка `main`, гілка `feature` з різними налаштуваннями пушу). Команди лише
класифікуються — жодна не виконується. Рядки зібрано зі шматків, щоб гейт не
реагував на текст самого тесту (W-23).

Кожен випадок «R4» мусить падати на коді до виправлення, кожен «не R4» —
мовчати після нього (CLAUDE.md §11: зламаний стан ловить, чистий — мовчить).

Запуск: python3 tests/probe-git-push.py   (0 — усі збіги, 1 — є розбіжності)
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "security" / "spine"))
from classify import classify  # noqa: E402

P = "git " + "push"
M = "ma" + "in"


def git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def make_repo(base: pathlib.Path, name: str, branch: str, **cfg: str) -> pathlib.Path:
    repo = base / name
    subprocess.run(["git", "init", "-q", "-b", branch, str(repo)], check=True)
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
    git(repo, "remote", "add", "origin", str(base / "nowhere.git"))
    git(repo, "update-ref", f"refs/remotes/origin/{M}", "HEAD")
    for key, value in cfg.items():
        git(repo, "config", key.replace("__", "."), value)
    return repo


def cases(on_main: pathlib.Path, feature: pathlib.Path, up_main: pathlib.Path,
          matching: pathlib.Path) -> list[tuple[str, pathlib.Path, str]]:
    """(команда, тека запуску, очікуваний рівень)."""
    return [
        # ── Явне призначення — гілка поточного репо неважлива ────────────────
        (f"{P} origin HEAD:{M}", feature, "R4"),
        (f"{P} origin {M}", feature, "R4"),
        (f"{P} origin feature:{M}", feature, "R4"),
        (f"{P} origin +HEAD:refs/heads/{M}", feature, "R4"),
        (f"{P} -u origin {M}", feature, "R4"),
        (f"{P} origin --delete {M}", feature, "R4"),
        (f"{P} origin :{M}", feature, "R4"),
        (f"{P} --all origin", feature, "R4"),
        (f"{P} --mirror origin", feature, "R4"),
        (f"{P} origin 'refs/heads/*:refs/heads/*'", feature, "R4"),
        (f"{P} origin HEAD:mas" + "ter", feature, "R4"),
        (f"git -C {feature} push origin HEAD:{M}", ROOT, "R4"),
        (f"/usr/bin/{P} origin HEAD:{M}", feature, "R4"),
        (f"bash -c '{P} origin HEAD:{M}'", feature, "R4"),
        (f'ls "$({P} origin HEAD:{M})"', feature, "R4"),
        (f"git status && {P} origin HEAD:{M}", feature, "R4"),
        # ── Без refspec: ціль — поточна гілка та її пуш-ціль ─────────────────
        (P, on_main, "R4"),
        (f"{P} origin", on_main, "R4"),
        (f"{P} origin HEAD", on_main, "R4"),
        (f"{P} -u origin @", on_main, "R4"),
        (f"cd {on_main} && {P}", feature, "R4"),
        (f"git -C {on_main} push", feature, "R4"),
        # Гілку змінено в тій самій команді — пушиться вже вона, а не поточна.
        (f"git checkout {M} && {P}", feature, "R4"),
        (f"git switch {M}; {P} origin HEAD", feature, "R4"),
        (f"git checkout --track origin/{M} && {P}", feature, "R4"),
        (f"{P} origin -- HEAD:{M}", feature, "R4"),
        (P, up_main, "R4"),                      # feature, але пуш-ціль — main
        (P, matching, "R4"),                     # push.default=matching штовхає й main
        (f"git -c push.default=matching push origin", feature, "R4"),
        # ── Не main — не R4 (інакше гейт кричить на кожному робочому пуші) ───
        (f"{P} -u origin claude/x", feature, "R2"),
        (f"{P} origin HEAD:feature", feature, "R2"),
        (f"{P} origin {M}:feature", feature, "R2"),
        (P, feature, "R2"),
        (f"{P} origin HEAD", feature, "R2"),
        (f"{P} origin v1.0", feature, "R2"),
        (f"{P} --tags origin", feature, "R2"),
        (f"git -C {feature} push", on_main, "R2"),
        (f"git checkout -b feat && {P}", feature, "R2"),
        (f"git switch -c feat && {P} -u origin HEAD", feature, "R2"),
        (f"{P} origin -- feature; git checkout {M}", feature, "R2"),
        # Згадка — не дія.
        (f"echo {P} origin HEAD:{M}", feature, "R0"),
        (f"echo {P} origin HEAD:{M}; ls", feature, "R2"),   # не чисте читання — друк лишається друком
        (f"git commit -m '{P} origin HEAD:{M}'", feature, "R2"),
        (f"grep -rn '{P} origin HEAD:{M}' docs", feature, "R0"),
    ]


def main() -> int:
    bad = total = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        on_main = make_repo(base, "on-main", M)
        feature = make_repo(base, "feature", "feature")
        up_main = make_repo(base, "up-main", "feature", branch__feature__remote="origin",
                            branch__feature__merge=f"refs/heads/{M}", push__default="upstream")
        matching = make_repo(base, "matching", "feature", push__default="matching")
        for cmd, cwd, want in cases(on_main, feature, up_main, matching):
            total += 1
            got = classify("Bash", {"command": cmd}, root=ROOT, cwd=str(cwd)).level
            if got != want:
                bad += 1
                shown = cmd.replace(tmp, "$TMP")
                print(f"  ❌ {shown[:60]:<62} [{cwd.name}] очік={want} факт={got}")
    print(f"  пуш у захищену гілку: {total - bad}/{total} збігів")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
