#!/usr/bin/env python3
"""Перехід у нову сесію: коли переходити й що лишити — без жодного токена моделі.

Навіщо: довга розмова дорожчає з кожною відповіддю, а стиснення контексту губить подробиці.
Поріг «≈300 тис. токенів → пакет продовження й нова сесія» тримався на дисципліні (W-53).
Цей скрипт робить три машинні кроки, а моделі лишає тільки те, чого машина не знає (рішення,
наміри) і MCP-виклики переходу. Протокол — `continuation-memory` § «Автоперехід у нову сесію».

  session-handoff.py measure [--transcript F]            # розмір контексту зараз, токенів
  session-handoff.py check   [--transcript F] [--threshold N] [--hook-input -]
                                                          # мовчить нижче порогу; вище — попередження
  session-handoff.py pack    --trigger context|compact|wave|rules [--topic T] [--repo D] [--hook-input -]
                                                          # пише скелет пакета з живого стану git
  session-handoff.py validate FILE                       # exit 1, якщо пакет неповний

Розмір контексту = input + cache_read + cache_creation останньої відповіді основного ланцюжка
журналу розмови (`transcript_path` із входу хука; інакше — найсвіжіший *.jsonl проєкту). Документація
Claude Code (звірено 2026-11-28): жоден хук не отримує розміру контексту напряму, тож журнал —
єдине офлайн-джерело. Лише stdlib + git.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_THRESHOLD = 300_000
PLACEHOLDER = "<!-- ДОПИСУЄ МОДЕЛЬ"
# Обов'язкові ознаки пакета: без них нова сесія або не знайде стару, або «прибере» її.
REQUIRED = {
    # Справжній id: хмарний `session_…` або локальний UUID — заглушка «невідомо» не проходить.
    "id попередньої сесії": re.compile(
        r"Попередня сесія:\s*`(session_[A-Za-z0-9]{8,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})`"),
    "застереження «не видаляти»": re.compile(r"НЕ видал", re.I),
    "наступний крок": re.compile(r"^Далі:\s*\S", re.M),
    "ціль": re.compile(r"^Ціль:\s*\S", re.M),
}


def git(repo: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=10,
                           stdin=subprocess.DEVNULL, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


SAFE_REF = re.compile(r"^[\w./-]{1,200}$")


def safe_ref(name: str) -> str:
    """Назва гілки в пакеті — лише безпечні символи (рев'ю P2): пакет читає модель."""
    return name if SAFE_REF.fullmatch(name) else "(назва з недозволеними символами)"


def hook_input(flag: str | None) -> dict:
    if flag != "-":
        return {}
    try:
        data = json.loads(sys.stdin.read() or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def find_transcript(explicit: str | None, hin: dict) -> Path | None:
    for cand in (explicit, hin.get("transcript_path")):
        if cand and Path(cand).is_file():
            return Path(cand)
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "") or str(hin.get("session_id", ""))
    root = Path.home() / ".claude" / "projects"
    if not root.is_dir():
        return None
    if sid:  # спершу журнал саме цієї сесії
        for p in root.glob(f"*/{glob_escape(sid)}.jsonl"):
            return p
    # Фолбек — лише тека ЦЬОГО проєкту (рев'ю P2: найсвіжіший журнал чужого проєкту давав хибний поріг).
    proj = root / re.sub(r"[^A-Za-z0-9]", "-", os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    files = sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if proj.is_dir() else []
    return files[0] if files else None


def glob_escape(s: str) -> str:
    return re.sub(r"([*?\[\]])", r"[\1]", s)


def measure(transcript: Path) -> int | None:
    """Останнє повідомлення моделі основного ланцюжка (не суб-агента) — його usage = поточний контекст."""
    last = None
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(d, dict) or d.get("isSidechain") or d.get("type") != "assistant":
                continue
            msg = d.get("message")
            u = msg.get("usage") if isinstance(msg, dict) else None
            if isinstance(u, dict):
                last = sum(int(u.get(k) or 0) for k in
                           ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return last


def cmd_measure(a, hin) -> int:
    t = find_transcript(a.transcript, hin)
    n = measure(t) if t else None
    print(n if n is not None else "unknown")
    return 0 if n is not None else 2


NOTIFY_STEP = 50_000  # щоходовий хук повторює попередження лише після такого приросту


def notified_file(hin: dict) -> Path | None:
    sid = str(hin.get("session_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sid):
        return None
    gd = git(Path(os.environ.get("CLAUDE_PROJECT_DIR") or "."), "rev-parse", "--absolute-git-dir")
    return Path(gd) / f"ai-lab-handoff-notified-{sid}.json" if gd else None


def already_warned(hin: dict, n: int) -> bool:
    """UserPromptSubmit: те саме попередження не друкуємо щоходу (рев'ю P1, ≈150 токенів/хід) —
    лише перше за порогом і далі кожні NOTIFY_STEP токенів приросту. SessionStart — завжди."""
    f = notified_file(hin) if hin.get("hook_event_name") == "UserPromptSubmit" else None
    if f is None:
        return False
    try:
        last = int(json.loads(f.read_text(encoding="utf-8")).get("n", 0))
    except (OSError, ValueError, AttributeError, TypeError):
        last = 0
    if last and 0 <= n - last < NOTIFY_STEP:  # n < last — контекст стиснули: новий відлік (рев'ю)
        return True
    try:
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_text(json.dumps({"n": n}), encoding="utf-8")
        os.replace(tmp, f)
    except OSError:
        pass
    return False


def cmd_check(a, hin) -> int:
    t = find_transcript(a.transcript, hin)
    n = measure(t) if t else None
    if n is None or n < a.threshold:
        if n is not None and (f := notified_file(hin)) is not None:
            f.unlink(missing_ok=True)  # нижче порогу — наступне перевищення знову попередить (рев'ю)
        return 0  # нижче порогу або невідомо — мовчимо (хук не має шуміти)
    if already_warned(hin, n):
        return 3 if a.strict else 0
    print(f"⚠️ Контекст розмови ≈{n // 1000} тис. токенів (поріг {a.threshold // 1000} тис.): "
          "кожна відповідь тепер дорожча. Перехід у нову сесію: "
          "`python3 scripts/session-handoff.py pack --trigger context --topic <тема>` → дописати "
          "рішення/наміри → `validate` → коміт і пуш → `create_session` з пакетом → перенести підписки PR. "
          "Стару сесію НЕ видаляти й не архівувати (continuation-memory § «Автоперехід»).")
    return 3 if a.strict else 0


def open_windows(repo: Path) -> str:
    w = repo / "docs" / "WINDOWS.md"
    m = re.search(r"ВІДКРИТИХ ВІКОН:\s*(\d+)", w.read_text(encoding="utf-8")) if w.is_file() else None
    return m.group(1) if m else "?"


def cmd_pack(a, hin) -> int:
    repo = Path(a.repo or git(Path.cwd(), "rev-parse", "--show-toplevel") or ".").resolve()
    today = dt.date.today().isoformat()
    # \w — з кирилицею: українська тема не має схлопуватись у спільне «handoff» (рев'ю #153).
    topic = re.sub(r"[^\w-]+", "-", (a.topic or "handoff").lower()).strip("-_") or "handoff"
    # compact: час і сесія в імені — друге стиснення дня не мовчить «пакет уже є» (рев'ю P2).
    if a.trigger == "compact":
        sid_part = re.sub(r"[^A-Za-z0-9]", "", str(hin.get("session_id", "")))[:8]
        topic += f"-{dt.datetime.now().strftime('%H%M')}" + (f"-{sid_part}" if sid_part else "")
    out = repo / "docs" / "continuation" / f"{today}-{topic}.md"
    if out.exists() and not a.force:
        print(f"пакет уже є: {out.relative_to(repo)} (не затираю; --force, щоб переписати)")
        return 0
    sid = (os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "").replace("cse_", "session_", 1)
           or hin.get("session_id") or "невідомо")
    branch = safe_ref(git(repo, "branch", "--show-current") or "(detached)")
    head = git(repo, "rev-parse", "--short", "HEAD")
    behind = git(repo, "rev-list", "--count", "HEAD..refs/remotes/origin/main") or "?"
    # --untracked-files=all: інакше showUntrackedFiles=no ховає нові файли (рев'ю #153).
    dirty = len([l for l in git(repo, "status", "--porcelain", "--untracked-files=all").splitlines() if l])
    branches = [b for b in git(repo, "branch", "-r", "--no-merged", "origin/main",
                               "--format=%(refname:short)").splitlines() if "/claude/" in b or b.startswith("origin/claude")]
    branches = [safe_ref(b) for b in branches]
    t = find_transcript(None, hin)
    used = measure(t) if t else None
    trig = {"context": f"поріг контексту (≈{(used or 0) // 1000} тис. токенів)",
            "compact": f"стиснення контексту ({hin.get('trigger', 'auto')})",
            "wave": "завершена хвиля робіт",
            "rules": "нові правила, що не діють у цій сесії (rules-drift, рівень 3)"}[a.trigger]
    body = f"""# Продовження: {a.topic or 'передача'} — перехід у нову сесію {today}

Ціль: {PLACEHOLDER}: одне речення — заради чого вся лінія роботи -->
Далі: {PLACEHOLDER}: перший конкретний крок нової сесії -->
Попередня сесія: `{sid}` — НЕ видалена й не архівована [C: стан на момент запису пакета; звірити `get_session`]; дочитувати її лише найдешевшим виконавцем-читачем (`list_events` з `kinds`), підсумок ≤500 токенів. Архівація — лише рішенням власника.
Привід переходу: {trig}.

## Живий стан (зібрано скриптом, без моделі)
- гілка `{branch}` @ `{head}` · main попереду на {behind} · незбережених файлів: {dirty}
- незлиті гілки claude/*: {', '.join(f'`{b}`' for b in branches[:12]) or 'немає'}
- відкритих вікон боргу: {open_windows(repo)} (`docs/WINDOWS.md`)

## Рішення й наміри
{PLACEHOLDER}: що вирішено й чому; що чекає згоди власника (дослівні готові фрази) -->

## Відкриті PR і підписки
{PLACEHOLDER}: номери, голови, стан CI/рев'ю. Підписки: у старій — unsubscribe, у новій — subscribe (події PR ідуть лише в одну сесію) -->

## Перехід (робить модель, MCP)
1. `validate` цього файлу → коміт і пуш.
2. `create_session` (та сама гілка/репо) з промптом: «прочитай цей пакет першим кроком».
3. Перенести підписки PR; у старій сесії — останнє повідомлення з посиланням на нову.
4. Ланцюг нащадків обмежений (`get_session` → `lineage.limit`): біля межі — нову сесію відкриває власник.
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    rel = out.relative_to(repo)
    if a.trigger == "compact":
        # [C] Вивід PreCompact потрапляє до моделі як контекст стиснення (не окремим ходом), тож
        # пакет тут лише скелет: просимо підсумок зберегти те, чого скелет не містить (рев'ю #153).
        print(f"Під час стиснення збережи в підсумку дослівно: шлях пакета продовження `{rel}` "
              "(записано лише скелет — живий стан git); усі ухвалені рішення з причинами; відкриті "
              "наміри й наступний крок; номери PR і фрази згоди, що чекають власника. Першим кроком "
              "після стиснення — дописати цей пакет і `validate`.")
    else:
        print(f"скелет пакета: {rel} — допиши позначені місця, потім `validate`")
    return 0


def validate_text(text: str) -> list[str]:
    errs = [f"бракує: {name}" for name, rx in REQUIRED.items() if not rx.search(text)]
    left = text.count(PLACEHOLDER)
    if left:
        errs.append(f"не дописано місць моделі: {left}")
    return errs


def cmd_validate(a, _hin) -> int:
    errs = validate_text(Path(a.file).read_text(encoding="utf-8"))
    for e in errs:
        print(f"❌ {e}")
    if not errs:
        print("✅ пакет повний")
    return 1 if errs else 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("measure", "check", "pack"):
        s = sub.add_parser(name)
        s.add_argument("--hook-input")
        if name != "pack":
            s.add_argument("--transcript")
    sub.choices["check"].add_argument("--threshold", type=int,
                                      default=env_int("AI_LAB_HANDOFF_THRESHOLD", DEFAULT_THRESHOLD))
    sub.choices["check"].add_argument("--strict", action="store_true")
    pk = sub.choices["pack"]
    pk.add_argument("--trigger", required=True, choices=["context", "compact", "wave", "rules"])
    pk.add_argument("--topic")
    pk.add_argument("--repo")
    pk.add_argument("--force", action="store_true")
    sub.add_parser("validate").add_argument("file")
    a = p.parse_args(argv)
    hin = hook_input(getattr(a, "hook_input", None))
    fn = {"measure": cmd_measure, "check": cmd_check, "pack": cmd_pack, "validate": cmd_validate}[a.cmd]
    if a.cmd == "validate" or not getattr(a, "hook_input", None):
        return fn(a, hin)
    try:  # у ролі хука — жодного traceback у розмову (рев'ю P1)
        return fn(a, hin)
    except Exception as e:
        if os.environ.get("AI_LAB_DEBUG"):
            raise
        print(f"session-handoff: пропущено ({type(e).__name__})", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
