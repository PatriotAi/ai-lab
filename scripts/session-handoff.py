#!/usr/bin/env python3
"""Перехід у нову сесію: коли переходити й що лишити — без жодного токена моделі.

Навіщо: довга розмова дорожчає з кожною відповіддю, а стиснення контексту губить подробиці.
Поріг «≈300 тис. токенів → пакет продовження й нова сесія» тримався на дисципліні (W-53).
Цей скрипт робить три машинні кроки, а моделі лишає тільки те, чого машина не знає (рішення,
наміри) і MCP-виклики переходу. Протокол — `continuation-memory` § «Автоперехід у нову сесію».

  session-handoff.py measure [--transcript F]            # розмір контексту зараз, токенів
  session-handoff.py check   [--transcript F] [--threshold N] [--hook-input -]
                                                          # мовчить нижче порогу; вище — попередження
  session-handoff.py pack    --trigger context|compact|wave [--topic T] [--repo D] [--hook-input -]
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
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=10)
    return r.stdout.strip() if r.returncode == 0 else ""


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
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    root = Path.home() / ".claude" / "projects"
    files = sorted(root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if root.is_dir() else []
    for p in files:  # спершу журнал саме цієї сесії
        if sid and p.stem == sid:
            return p
    return files[0] if files else None


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


def cmd_check(a, hin) -> int:
    t = find_transcript(a.transcript, hin)
    n = measure(t) if t else None
    if n is None or n < a.threshold:
        return 0  # нижче порогу або невідомо — мовчимо (хук не має шуміти)
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
    out = repo / "docs" / "continuation" / f"{today}-{topic}.md"
    if out.exists() and not a.force:
        print(f"пакет уже є: {out.relative_to(repo)} (не затираю; --force, щоб переписати)")
        return 0
    sid = (os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "").replace("cse_", "session_", 1)
           or hin.get("session_id") or "невідомо")
    branch = git(repo, "branch", "--show-current") or "(detached)"
    head = git(repo, "rev-parse", "--short", "HEAD")
    behind = git(repo, "rev-list", "--count", "HEAD..refs/remotes/origin/main") or "?"
    # --untracked-files=all: інакше showUntrackedFiles=no ховає нові файли (рев'ю #153).
    dirty = len([l for l in git(repo, "status", "--porcelain", "--untracked-files=all").splitlines() if l])
    branches = [b for b in git(repo, "branch", "-r", "--no-merged", "origin/main",
                               "--format=%(refname:short)").splitlines() if "/claude/" in b or b.startswith("origin/claude")]
    t = find_transcript(None, hin)
    used = measure(t) if t else None
    trig = {"context": f"поріг контексту (≈{(used or 0) // 1000} тис. токенів)",
            "compact": f"стиснення контексту ({hin.get('trigger', 'auto')})",
            "wave": "завершена хвиля робіт"}[a.trigger]
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
        # Вивід PreCompact стає інструкцією для підсумку стиснення (не окремим ходом моделі), тож
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
                                      default=int(os.environ.get("AI_LAB_HANDOFF_THRESHOLD", DEFAULT_THRESHOLD)))
    sub.choices["check"].add_argument("--strict", action="store_true")
    pk = sub.choices["pack"]
    pk.add_argument("--trigger", required=True, choices=["context", "compact", "wave"])
    pk.add_argument("--topic")
    pk.add_argument("--repo")
    pk.add_argument("--force", action="store_true")
    sub.add_parser("validate").add_argument("file")
    a = p.parse_args(argv)
    hin = hook_input(getattr(a, "hook_input", None))
    return {"measure": cmd_measure, "check": cmd_check, "pack": cmd_pack, "validate": cmd_validate}[a.cmd](a, hin)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
