#!/usr/bin/env python3
"""mutation-probe-wiring.py — гейт для стенда підключеності хуків середовища (W-31).

ПИТАННЯ. `tests/probe-wiring.py` зелений — але чи ловить він хоч щось?
Напис «стенд доведено 11 мутантами (0 вижило) — 2026-09-29» півтора місяця
стояв у `run-tests.sh` і `tests/README.md`, а самих мутантів у репо не було:
прогін робився в тимчасовій теці сесії й зник разом із контейнером. Той самий
клас, що закрито 2026-10-23 для стенда README (`mutation-readme-wiring.py`):
доказ, якого не відтворити, — не доказ (CLAUDE.md §11). Тепер мутанти живуть
тут і ганяються набором.

Мутується лише `scripts/security-drift.py` (`check_unwired_hooks`,
`check_env_wired` і помічники `_env_commands`, `_runs_file`) — у КОПІЇ в
тимчасовій теці; робочі файли не чіпаються ніколи.

Запуск: python3 tests/mutation-probe-wiring.py [--verbose]
Код виходу: 0 — кожен мутант спійманий · 1 — хтось вижив (діра в стенді).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "scripts/security-drift.py"
PROBE = "tests/probe-wiring.py"

# (назва, що замінити, на що, який інцидент знову пройшов би)
MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "нема файла середовища → ✅ (урок F-13 навпаки)",
        "    if not env_file.is_file():\n        return (UNKNOWN,",
        "    if not env_file.is_file():\n        return (OK,",
        "локальна машина чи CI звітує «підключено», нічого не довівши",
    ),
    (
        "зіпсований файл середовища → ✅",
        "    if commands is None:\n        return (UNKNOWN,",
        "    if commands is None:\n        return (OK,",
        "нечитабельний JSON читається як доказ підключеності",
    ),
    (
        "форма кореня не перевіряється",
        "    if not isinstance(data, dict) or not isinstance(data.get(\"hooks\", {}), dict):\n        return None\n",
        "",
        "корінь-список валить увесь звіт (рев'ю PR #73)",
    ),
    (
        "форма події не перевіряється",
        "        if not isinstance(groups, list):\n            return None\n",
        "",
        "подія-число валить увесь звіт",
    ),
    (
        "форма групи не перевіряється",
        "            if not isinstance(group, dict) or not isinstance(group.get(\"hooks\", []), list):\n                return None\n",
        "",
        "група-рядок валить увесь звіт",
    ),
    (
        "реєстрація за ім'ям файла, не за шляхом",
        "if _runs_file(cmd, active)})",
        "if active.name in cmd})",
        "`/opt/other/envhook.sh` на потрібній події зараховується (рев'ю PR #73)",
    ),
    (
        "подія реєстрації не звіряється",
        "    if event not in events:",
        "    if not events:",
        "реєстрація на SessionStart зараховується за Stop",
    ),
    (
        "`~` не розкривається",
        "os.path.realpath(os.path.expanduser(os.path.expandvars(w)))",
        "os.path.realpath(os.path.expandvars(w))",
        "звичайна реєстрація `~/.claude/…` — хибна тривога",
    ),
    (
        "`$HOME` не розкривається",
        "os.path.realpath(os.path.expanduser(os.path.expandvars(w)))",
        "os.path.realpath(os.path.expanduser(w))",
        "легітимний запис `\"$HOME/…\"` — хибна тривога",
    ),
    (
        "команда ріжеться пробілами, а не як оболонка",
        "        words = shlex.split(cmd)",
        "        words = cmd.split()",
        "лапки лишаються в слові — `\"$HOME/…\"` не збігається",
    ),
    (
        "активна копія не перевіряється на існування",
        "    if not active.is_file():\n        return (DRIFT,",
        "    if False:\n        return (DRIFT,",
        "зникла копія дає ❓ замість тривоги",
    ),
    (
        "копія не звіряється з каноном",
        "    if not same:",
        "    if False:",
        "працює стара базова версія, а звіт каже «копія = канон»",
    ),
    (
        "синхронізатор шукається підрядком",
        "not re.search(rf\"(^|[/\\s\\\"']){re.escape(synced_by)}([\\s\\\"']|$)\", registered, re.M)",
        "synced_by not in registered",
        "`async.sh` зараховується за `sync.sh`",
    ),
    (
        "синхронізатор не перевіряється взагалі",
        "    if not synced_by or not re.search(",
        "    if not synced_by or False and not re.search(",
        "після рестарту контейнера працює стара версія — мовчки",
    ),
    (
        "хук середовища не відрізняється від сироти",
        "            if name in env_wired:",
        "            if False:",
        "інцидент F-13: хук середовища знову «НЕ ПІДКЛЮЧЕНО»",
    ),
    (
        "свідома причина не зараховується",
        "            if reason:",
        "            if False:",
        "свідомо вимкнений хук — хибна тривога",
    ),
    (
        "сирота не повідомляється",
        "                    DRIFT, f\"НЕ ПІДКЛЮЧЕНО: {shown}\",",
        "                    OK, f\"НЕ ПІДКЛЮЧЕНО: {shown}\",",
        "інцидент F-12: самооголошений хук без реєстрації знову мовчить",
    ),
]


def build_sandbox(tmp: Path) -> Path:
    """Копія лише скрипта й стенда. Робочі файли недоторкані."""
    sandbox = tmp / "repo"
    for rel in (TARGET, PROBE):
        (sandbox / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, sandbox / rel)
    return sandbox


def caught(sandbox: Path) -> bool:
    res = subprocess.run([sys.executable, "-I", str(sandbox / PROBE)],
                         capture_output=True, text=True, timeout=120)
    return res.returncode != 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv[1:])

    with tempfile.TemporaryDirectory() as td:
        sandbox = build_sandbox(Path(td))
        original = (sandbox / TARGET).read_text(encoding="utf-8")

        # Контроль: на цілому коді стенд мовчить — інакше результати нічого не варті.
        if caught(sandbox):
            print("  ❌ на цілому коді стенд впав — прогін недійсний")
            return 1

        survived: list[tuple[str, str]] = []
        for name, old, new, effect in MUTATIONS:
            if old not in original:
                print(f"  ⚠️  мутація «{name}» не застосовна — цільовий рядок змінився")
                survived.append((name, "цільовий рядок не знайдено"))
                continue
            (sandbox / TARGET).write_text(original.replace(old, new, 1), encoding="utf-8")
            hit = caught(sandbox)
            (sandbox / TARGET).write_text(original, encoding="utf-8")
            if hit:
                if args.verbose:
                    print(f"  ✅ {name}")
            else:
                survived.append((name, effect))

    total = len(MUTATIONS)
    if survived:
        print(f"  ❌ мутанти стенда підключеності: {total - len(survived)}/{total} спіймано, "
              f"{len(survived)} ВИЖИЛО")
        for name, effect in survived:
            print(f"     - «{name}» пройшов стенд → {effect}")
        return 1
    print(f"  мутанти стенда підключеності: {total}/{total} спіймано")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
