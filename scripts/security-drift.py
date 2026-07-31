#!/usr/bin/env python3
"""security-drift.py — чи справді ввімкнені контролі, які документи називають активними.

Єдина відповідальність: порівняти ЗАДЕКЛАРОВАНИЙ стан безпекових контролів
із ФАКТИЧНИМ і показати розбіжність. Нічого не виправляє, нічого не вмикає.

НАВІЩО (не теорія — зафіксований дефект):
    `SECURITY.md` описує pre-commit як активний локальний контроль. Зріз
    2026-07-27 показав, що в робочому середовищі не встановлено ні pre-commit,
    ні gitleaks, ні trivy, ні semgrep, а тека `.git/hooks/` порожня — тобто
    весь локальний шар не працював, доки про це ніхто не питав.
    Це «Control Effectiveness» із наданого Master-документа в масштабі
    лабораторії: недостатньо, щоб контроль ІСНУВАВ — треба, щоб він ПРАЦЮВАВ.

ЧЕСНА МЕЖА:
    Перевіряється лише те, що видно з файлової системи. Стан на боці GitHub
    (чи ввімкнено Dependency graph, чи проходять воркфлоу) звідси не видно —
    такі контролі позначаються як «не перевіряється звідси», а НЕ як робочі.

Запуск:
    python3 scripts/security-drift.py          # звіт для людини
    python3 scripts/security-drift.py --quiet  # лише рядки з розбіжністю

Код виходу: 0 — розбіжностей немає · 1 — є розбіжності · 2 — помилка виклику.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

OK, DRIFT, UNKNOWN = "✅", "⚠️", "❓"


def repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def stale_limit(root: Path) -> int:
    """Скільки днів контроль лишається підтвердженим. Джерело — та сама політика."""
    try:
        pol = tomllib.loads((root / "security" / "policy.toml").read_text(encoding="utf-8"))
        return int(pol.get("levels", {}).get("R3", {}).get("stale_after_days", 30))
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return 30


def check_tool(name: str, why: str) -> tuple[str, str, str]:
    if shutil.which(name):
        return OK, name, "встановлено"
    return DRIFT, name, f"НЕ встановлено — {why}"


def check_git_hooks(root: Path) -> tuple[str, str, str]:
    hooks = root / ".git" / "hooks"
    if not hooks.is_dir():
        return DRIFT, "git-хуки", "теки .git/hooks немає"
    live = [p.name for p in hooks.iterdir() if not p.name.endswith(".sample")]
    if live:
        return OK, "git-хуки", f"встановлено: {', '.join(sorted(live))}"
    return DRIFT, "git-хуки", "жодного активного — запусти scripts/setup.sh"


def check_claude_hooks(root: Path) -> list[tuple[str, str, str]]:
    """Чи зареєстровані хуки й чи існують файли, на які вони вказують."""
    settings = root / ".claude" / "settings.json"
    if not settings.is_file():
        return [(DRIFT, "хуки Claude Code", ".claude/settings.json відсутній")]
    try:
        cfg = json.loads(settings.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [(DRIFT, "хуки Claude Code", f".claude/settings.json не читається: {exc}")]

    rows: list[tuple[str, str, str]] = []
    events = cfg.get("hooks", {})
    if not events:
        rows.append((DRIFT, "хуки Claude Code", "жодного не зареєстровано"))
    for event, groups in events.items():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                # Хук може посилатись на $CLAUDE_PROJECT_DIR — резолвимо на корінь репо.
                rel = cmd.replace("$CLAUDE_PROJECT_DIR/", "").replace("${CLAUDE_PROJECT_DIR}/", "")
                target = root / rel
                if target.is_file():
                    rows.append((OK, f"хук {event}", rel))
                else:
                    rows.append((DRIFT, f"хук {event}", f"файл не знайдено: {rel}"))
    return rows


def check_pretooluse(root: Path) -> tuple[str, str, str]:
    """Механічний гейт дій — окремо, бо його відсутність це дефект F-3."""
    settings = root / ".claude" / "settings.json"
    text = settings.read_text(encoding="utf-8") if settings.is_file() else ""
    if "PreToolUse" in text:
        return OK, "механічний гейт дій (PreToolUse)", "зареєстровано"
    return (
        DRIFT,
        "механічний гейт дій (PreToolUse)",
        "відсутній — незворотні дії тримаються лише на дисципліні (F-3)",
    )


def check_action_pinning(root: Path) -> tuple[str, str, str]:
    """Дії GitHub закріплені хешем чи рухомим тегом (F-5)."""
    wf = root / ".github" / "workflows"
    if not wf.is_dir():
        return UNKNOWN, "закріплення дій GitHub", "теки воркфлоу немає"
    tagged = 0
    for path in wf.glob("*.yml"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("- uses:", "uses:")):
                ref = stripped.split("@", 1)[1].split()[0] if "@" in stripped else ""
                # Повний SHA коміту — 40 шістнадцяткових символів.
                if not (len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower())):
                    tagged += 1
    if tagged:
        return DRIFT, "закріплення дій GitHub", f"{tagged} закріплено рухомим тегом, не хешем (F-5)"
    return OK, "закріплення дій GitHub", "усі закріплені хешем коміту"


def check_last_verified(root: Path, limit_days: int) -> tuple[str, str, str]:
    """Коли контролі востаннє підтверджували ділом (S3.3).

    Контроль, який давно не прогоняли, — НЕ робочий контроль, а непідтверджений.
    Різниця та сама, що між «чисто» і «не перевіряли»: виглядає однаково,
    означає протилежне. Мітку пише `tests/run-tests.sh` при успішному прогоні.
    """
    marker = root / "security" / "audit" / "last-verified.json"
    if not marker.is_file():
        return (
            DRIFT, "підтвердження контролів",
            "НІКОЛИ не прогонялось у цьому середовищі — статус контролів "
            "нижче не підтверджений. Прогін: bash tests/run-tests.sh",
        )
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        stamp = datetime.fromisoformat(data["ts"].replace("Z", "+00:00"))
        passed = data.get("passed", "?")
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        return DRIFT, "підтвердження контролів", f"мітка не читається ({exc})"

    days = (datetime.now(timezone.utc) - stamp).days
    when = stamp.strftime("%Y-%m-%d %H:%M UTC")
    if days > limit_days:
        return (
            DRIFT, "підтвердження контролів",
            f"НЕПІДТВЕРДЖЕНО — останній прогін {when} ({days} дн. тому, "
            f"межа {limit_days}). Прогін: bash tests/run-tests.sh",
        )
    return OK, "підтвердження контролів", f"{when} · {passed} перевірок · {days} дн. тому"


def check_self_modification(root: Path) -> tuple[str, str, str]:
    """Скільки разів агент правив код власного гейта (рішення власника: записувати, не блокувати)."""
    log = root / "security" / "audit" / "decisions.jsonl"
    if not log.is_file():
        return UNKNOWN, "самозміни гейта", "журнал порожній — записів немає"
    count = 0
    try:
        for line in log.read_text(encoding="utf-8").splitlines():
            if '"self_modification": true' in line or '"self_modification":true' in line:
                count += 1
    except OSError as exc:
        return UNKNOWN, "самозміни гейта", f"журнал не читається ({exc})"
    if count:
        return (
            OK, "самозміни гейта",
            f"{count} у журналі цього середовища — це НЕ помилка, а видимість: "
            "правки власного гейта не блокуються, але й не проходять тихо",
        )
    return OK, "самозміни гейта", "жодної в журналі цього середовища"


def check_remote_only() -> list[tuple[str, str, str]]:
    return [
        (UNKNOWN, "Dependency graph на GitHub", "не перевіряється звідси — лише в налаштуваннях репо"),
        (UNKNOWN, "захист гілок", "недоступний на приватному репо безкоштовного плану (рішення «варіант C»)"),
    ]


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv[1:]
    unknown_args = [a for a in argv[1:] if a not in ("--quiet",)]
    if unknown_args:
        print(f"security-drift: невідомі аргументи: {' '.join(unknown_args)}", file=sys.stderr)
        return 2

    root = repo_root()
    rows: list[tuple[str, str, str]] = [
        check_tool("pre-commit", "локальний гейт гігієни й секретів не працює"),
        check_tool("gitleaks", "локальний скан секретів не працює (у CI є)"),
        check_tool("trivy", "локальний скан вразливостей не працює (у CI є)"),
        check_git_hooks(root),
    ]
    rows += check_claude_hooks(root)
    rows.append(check_pretooluse(root))
    rows.append(check_action_pinning(root))
    rows.append(check_last_verified(root, stale_limit(root)))
    rows.append(check_self_modification(root))
    rows += check_remote_only()

    drifted = [r for r in rows if r[0] == DRIFT]

    if not quiet:
        print("Дрейф безпекових контролів — задекларовано проти фактично\n")
        for mark, name, detail in rows:
            print(f"  {mark} {name}: {detail}")
        print()

    if drifted:
        print(f"⚠️  Розбіжностей: {len(drifted)}")
        if quiet:
            for _, name, detail in drifted:
                print(f"  - {name}: {detail}")
        print("   «Контроль існує» ≠ «контроль працює». Виправ або свідомо прийми.")
        return 1

    print("✅ Розбіжностей немає: усе, що задекларовано, справді ввімкнено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
