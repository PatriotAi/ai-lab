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

Знімок — у git-теці checkout (не в дереві репо), окремо на кожну сесію (`session_id` із входу
хука; рев'ю #154: дві сесії в одному checkout інакше перезаписували б знімок одна одній). Без
знімка check порівнює з HEAD. Тиша, якщо дрейфу нема. Лише stdlib + git.

Код хуків (рев'ю #154) — теж рівень 1: файли, на які вказують команди хуків у налаштуваннях
агента (HEAD і ref), а для хука у власній теці (`automations/<хук>/`, `security/hooks/`) — уся
тека. Межа: скрипти, які хук викликає транзитивно з теки першого рівня (напр. `scripts/*.py`
із `session-start.sh`), не відстежуються.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import tempfile
import time
import sys
from pathlib import Path

# Файл правил → рівень, з якого він починає діяти в запущеній сесії.
LEVEL2 = {"CLAUDE.md"}
PATTERNS = ["CLAUDE.md", ".claude/settings.json", ".claude/agents/*.md", "security/policy.toml",
            "melania-skills-ecosystem/skills/*/SKILL.md"]


GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true", "SSH_ASKPASS": "true",
           "GIT_SSH_COMMAND": os.environ.get("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")}


def git_raw(repo: Path, *args: str, timeout: int = 10) -> tuple[int, bytes]:
    """git без шансу повиснути (рев'ю #153/#154, P1): власна група процесів — по тайм-ауту
    вбиваємо всю групу (інакше дочірній `git-remote-https` тримає pipe і хук висить); stdin
    закрито, запит пароля вимкнено."""
    try:
        pr = subprocess.Popen(["git", "-C", str(repo), *args], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=GIT_ENV,
                              start_new_session=True)
    except OSError:
        return 127, b""
    try:
        out, _ = pr.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pr.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            pr.communicate(timeout=2)  # нащадок міг вийти з групи (setsid) і тримати pipe
        except subprocess.TimeoutExpired:
            pass
        return 124, b""
    return pr.returncode, out


def git(repo: Path, *args: str, timeout: int = 10) -> tuple[int, str]:
    rc, out = git_raw(repo, *args, timeout=timeout)
    return rc, out.decode("utf-8", "replace")


HOOK_CMD = re.compile(r'\$\{?CLAUDE_PROJECT_DIR\}?/([^\s"\'\\]+)')


def hook_targets(repo: Path, refs: list[str]) -> tuple[set[str], set[str]]:
    """Файли й теки коду хуків із налаштувань агента (PATTERNS[1]) у кожному з refs."""
    files: set[str] = set()
    dirs: set[str] = set()
    for ref in refs:
        rc, out = git(repo, "show", f"{ref}:{PATTERNS[1]}")
        for rel in HOOK_CMD.findall(out if rc == 0 else ""):
            rel = rel.strip("/")
            if ".." in rel.split("/"):
                continue
            files.add(rel)
            if rel.count("/") >= 2:  # власна тека хука — разом із допоміжними файлами
                dirs.add(rel.rsplit("/", 1)[0])
    return files, dirs


def is_rule(rel: str, hooks: tuple[set[str], set[str]] = (set(), set())) -> bool:
    """Точний збіг з шаблоном (`*` не перетинає `/`): `docs/CLAUDE.md` — не правило.
    Плюс код хуків (`hook_targets`), якщо його передано."""
    if rel in hooks[0] or any(rel.startswith(d + "/") for d in hooks[1]):
        return True
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
    rc, out = git_raw(repo, "show", f"{ref}:{rel}")
    return digest(out) if rc == 0 else None


def state_file(repo: Path, hin: dict, kind: str) -> Path:
    """Стан скрипта — у git-теці checkout (не в дереві репо), окремо на сесію."""
    _, gd = git(repo, "rev-parse", "--absolute-git-dir")
    sid = str(hin.get("session_id", ""))
    suffix = f"-{sid}" if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sid) else ""
    return Path(gd.strip() or repo / ".git") / f"ai-lab-rules-{kind}{suffix}.json"


def snap_file(repo: Path, hin: dict) -> Path:
    return state_file(repo, hin, "snapshot")


def read_json(f: Path) -> dict:
    """Битий чи порожній файл стану = його немає (рев'ю P1: traceback у хуку щоповідомлення)."""
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(f: Path, data: dict) -> None:
    """Атомарно: tmp у тій самій теці + os.replace — обірваний запис не лишає битого знімка."""
    fd, tmp = tempfile.mkstemp(dir=str(f.parent), prefix=f.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, sort_keys=True))
        os.replace(tmp, f)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def fetch_due(repo: Path, minutes: int) -> bool:
    """`fetch` не частіше ніж раз на N хв на checkout (мітка в git-теці): щоходовий хук не має
    ходити в мережу щоповідомлення (рев'ю P1)."""
    stamp = state_file(repo, {}, "fetch-stamp")
    try:
        if time.time() - stamp.stat().st_mtime < minutes * 60:
            return False
    except OSError:
        pass
    try:
        stamp.touch()
    except OSError:
        pass
    return True


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
    f = snap_file(repo, hin)
    old = read_json(f)
    now = {rel: disk(repo, rel) for rel in rule_paths(repo, None)}
    if src == "compact" and old:
        # Стиснення перезавантажує з диска лише CLAUDE.md (і список навичок) — решту знімка не чіпаємо.
        old.update({k: v for k, v in now.items() if k in LEVEL2})
        now = old
    elif src == "resume" and old:
        return 0  # resume нічого не перезавантажує — знімок старту лишається правдою
    write_json(f, now)
    state_file(repo, hin, "notified").unlink(missing_ok=True)  # нове завантаження — повідомити знову
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
    if a.fetch and fetch_due(repo, a.fetch_every):
        git(repo, "fetch", "-q", "origin", "main", timeout=8)
    f = snap_file(repo, hin)
    # Битий/порожній знімок = знімка нема → звірка від HEAD (не «усе змінилось»).
    loaded = read_json(f) or {rel: at_ref(repo, "HEAD", rel) for rel in rule_paths(repo, "HEAD")}
    # Лише зміни, що є в ref і ще не дійшли сюди (від спільного предка): власні правки гілки,
    # новіші за main, — не дрейф (живий прогін 2026-11-28 показав хибне спрацювання при порівнянні вмісту).
    need_merge: list[str] = []
    if git(repo, "rev-parse", "--verify", "-q", a.ref)[0] == 0:
        _, names = git(repo, "diff", "--name-only", f"HEAD...{a.ref}")
        hooks = hook_targets(repo, ["HEAD", a.ref])
        need_merge = sorted(n for n in names.splitlines() if is_rule(n, hooks))
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
    # Щоходовий хук повідомляє лише ЗМІНУ стану (рев'ю P1: ≈150 токенів щоходу). Ключ — склад
    # дрейфу, не текст (число токенів у рівні 3 росте щоходу). SessionStart друкує завжди.
    # + вершина ref: нова зміна тих самих файлів у main — теж новина (рев'ю).
    key = digest(json.dumps([need_merge, read_diff, level3, git(repo, "rev-parse", "-q", "--verify", a.ref)[1].strip()]).encode())
    nf = state_file(repo, hin, "notified")
    if hin.get("hook_event_name") == "UserPromptSubmit" and read_json(nf).get("key") == key:
        return 3 if a.strict else 0
    print("\n".join(lines))
    try:
        write_json(nf, {"key": key})
    except OSError:
        pass
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
    c.add_argument("--threshold", type=int, default=env_int("AI_LAB_HANDOFF_THRESHOLD", 300_000))
    c.add_argument("--fetch-every", type=int, default=env_int("AI_LAB_DRIFT_FETCH_MIN", 10),
                   help="хвилин між fetch (мітка в git-теці)")
    a = p.parse_args(argv)
    hin = hook_input(a.hook_input)
    try:
        repo = Path(a.repo or git(Path.cwd(), "rev-parse", "--show-toplevel")[1].strip() or ".").resolve()
        return cmd_snapshot(repo, hin) if a.cmd == "snapshot" else cmd_check(repo, a, hin)
    except Exception as e:  # хук не має падати traceback'ом у розмову (рев'ю P1); слід — у stderr
        if os.environ.get("AI_LAB_DEBUG"):
            raise
        print(f"rules-drift: пропущено ({type(e).__name__})", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
