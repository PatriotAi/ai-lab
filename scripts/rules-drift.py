#!/usr/bin/env python3
"""Дрейф правил: чи діють у ЦІЙ сесії правила, що вже змінились у main — і що робити.

Навіщо (рішення власника 2026-11-28): нові правила мають діяти не лише в нових сесіях, а й у
запущених. Документація Claude Code (звірено 2026-11-28; memory, settings, skills, sub-agents,
context-window) [C]: текст навичок, суб-агенти, хуки й дозволи підхоплюються на ходу, щойно файл
змінився на диску; кореневий CLAUDE.md — лише після стиснення контексту; налаштування акаунта —
лише в новій сесії. «На диску» — це власний checkout сесії: злиття в main сюди само не доходить.

Драбина (від дешевого до дорогого):
  рівень 1 — звести main у гілку сесії: навички, суб-агенти, хуки, дозволи, політика гейта діють одразу;
  рівень 2 — змінився CLAUDE.md: рівень 1 + прочитати лише різницю (`git diff`) і діяти за нею;
             офіційно правила перезавантажаться з найближчим стисненням контексту;
  рівень 3 — нова сесія з пакетом продовження: коли рівень 2 збігся з розмовою за порогом
             контексту (перехід дешевший за подальшу довгу розмову) або змінились налаштування
             акаунта (їх скрипт не бачить — каже про це прямо).

  rules-drift.py snapshot [--hook-input -]           # знімок правил, які сесія завантажила на старті
  rules-drift.py check [--ref origin/main] [--fetch] [--threshold N] [--transcript F] [--hook-input -]

Знімок — у git-теці checkout (не в дереві репо). Без знімка check порівнює з HEAD. Тиша, якщо
дрейфу нема. Лише stdlib + git.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

# Файл правил → рівень, з якого він починає діяти в запущеній сесії.
LEVEL2 = {"CLAUDE.md"}
PATTERNS = ["CLAUDE.md", ".claude/settings.json", ".claude/agents/*.md", "security/policy.toml",
            "melania-skills-ecosystem/skills/*/SKILL.md"]


def git(repo: Path, *args: str, timeout: int = 10) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, ""
    return r.returncode, r.stdout


def is_rule(rel: str) -> bool:
    """Точний збіг з шаблоном (`*` не перетинає `/`): `docs/CLAUDE.md` — не правило."""
    parts = rel.split("/")
    return any(len(parts) == len(pat.split("/")) and
               all(fnmatch.fnmatchcase(a, b) for a, b in zip(parts, pat.split("/"))) for pat in PATTERNS)


def rule_paths(repo: Path, ref: str | None) -> set[str]:
    if ref:
        _, ls = git(repo, "ls-tree", "-r", "--name-only", ref)
        return {n for n in ls.splitlines() if is_rule(n)}
    out = set()
    for pat in PATTERNS:
        out.update(r for p in repo.glob(pat) if p.is_file() and is_rule(r := p.relative_to(repo).as_posix()))
    return out


def digest(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest()[:16] if data is not None else None


def disk(repo: Path, rel: str) -> str | None:
    p = repo / rel
    return digest(p.read_bytes()) if p.is_file() else None


def at_ref(repo: Path, ref: str, rel: str) -> str | None:
    r = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{rel}"], capture_output=True, timeout=10)
    return digest(r.stdout) if r.returncode == 0 else None


def snap_file(repo: Path) -> Path:
    _, gd = git(repo, "rev-parse", "--absolute-git-dir")
    return Path(gd.strip() or repo / ".git") / "ai-lab-rules-snapshot.json"


def hook_input(flag: str | None) -> dict:
    if flag != "-":
        return {}
    try:
        d = json.loads(sys.stdin.read() or "{}")
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def cmd_snapshot(repo: Path, hin: dict) -> int:
    src = hin.get("source", "startup")
    f = snap_file(repo)
    old = json.loads(f.read_text()) if f.is_file() else {}
    now = {rel: disk(repo, rel) for rel in rule_paths(repo, None)}
    if src == "compact" and old:
        # Стиснення перезавантажує з диска лише CLAUDE.md (і список навичок) — решту знімка не чіпаємо.
        old.update({k: v for k, v in now.items() if k in LEVEL2})
        now = old
    elif src == "resume" and old:
        return 0  # resume нічого не перезавантажує — знімок старту лишається правдою
    f.write_text(json.dumps(now, ensure_ascii=False, sort_keys=True))
    return 0


def context_tokens(transcript: str | None, hin: dict) -> int | None:
    sh = Path(__file__).resolve().parent / "session-handoff.py"
    if not sh.is_file():
        return None
    spec = importlib.util.spec_from_file_location("session_handoff", sh)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    t = mod.find_transcript(transcript, hin)
    return mod.measure(t) if t else None


def cmd_check(repo: Path, a, hin: dict) -> int:
    if a.fetch:
        git(repo, "fetch", "-q", "origin", "main", timeout=8)
    f = snap_file(repo)
    loaded = json.loads(f.read_text()) if f.is_file() else {
        rel: at_ref(repo, "HEAD", rel) for rel in rule_paths(repo, "HEAD")}
    # Лише зміни, що є в ref і ще не дійшли сюди (від спільного предка): власні правки гілки,
    # новіші за main, — не дрейф (живий прогін 2026-11-28 показав хибне спрацювання при порівнянні вмісту).
    need_merge: list[str] = []
    if git(repo, "rev-parse", "--verify", "-q", a.ref)[0] == 0:
        _, names = git(repo, "diff", "--name-only", f"HEAD...{a.ref}")
        need_merge = sorted(n for n in names.splitlines() if is_rule(n))
    read_diff = sorted(rel for rel in LEVEL2 if rel in need_merge or loaded.get(rel) != disk(repo, rel))
    if not need_merge and not read_diff:
        return 0
    lines = ["## Дрейф правил (зібрано скриптом, без моделі)"]
    if need_merge:
        shown = ", ".join(f"`{p}`" for p in need_merge[:6]) + (" …" if len(need_merge) > 6 else "")
        lines.append(f"- **Рівень 1:** у `{a.ref}` новіші правила, ніж у цій гілці ({len(need_merge)}): {shown}. "
                     f"Звести `{a.ref}` у гілку — навички, суб-агенти, хуки, дозволи й політика гейта почнуть діяти одразу.")
    level3 = False
    if read_diff:
        n = context_tokens(a.transcript, hin)
        level3 = n is not None and n >= a.threshold
        lines.append(f"- **Рівень 2:** змінився {', '.join(f'`{p}`' for p in read_diff)} — у контексті сесії стара версія. "
                     "Після зведення прочитати лише різницю (`git diff <знімок>..HEAD -- CLAUDE.md` або з main) і діяти за нею; "
                     "офіційно правила перезавантажаться з найближчим стисненням.")
        if level3:
            lines.append(f"- **Рівень 3:** розмова вже ≈{n // 1000} тис. токенів (поріг {a.threshold // 1000} тис.) — "
                         "дешевше перейти в нову сесію з новими правилами: "
                         "`python3 scripts/session-handoff.py pack --trigger rules --topic <тема>`.")
    lines.append("_Налаштування акаунта claude.ai скрипт не бачить: якщо їх змінено — діють лише в новій сесії (рівень 3)._")
    print("\n".join(lines))
    return 3 if (a.strict and (need_merge or read_diff)) else 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("snapshot", "check"):
        s = sub.add_parser(name)
        s.add_argument("--repo")
        s.add_argument("--hook-input")
    c = sub.choices["check"]
    c.add_argument("--ref", default="origin/main")
    c.add_argument("--fetch", action="store_true")
    c.add_argument("--transcript")
    c.add_argument("--strict", action="store_true")
    c.add_argument("--threshold", type=int, default=int(os.environ.get("AI_LAB_HANDOFF_THRESHOLD", 300_000)))
    a = p.parse_args(argv)
    repo = Path(a.repo or git(Path.cwd(), "rev-parse", "--show-toplevel")[1].strip() or ".").resolve()
    hin = hook_input(a.hook_input)
    return cmd_snapshot(repo, hin) if a.cmd == "snapshot" else cmd_check(repo, a, hin)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
