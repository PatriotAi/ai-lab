#!/usr/bin/env python3
"""probe-wiring.py — стенд для реверсивної перевірки підключеності хуків.

Навіщо: перша версія перевірки (Фаза S5) читала лише `.claude/settings.json`
і назвала `stop-hook-git-check.sh` непідключеним (F-13). Хук насправді працював:
його реєструє СЕРЕДОВИЩЕ, а проєктний `sync.sh` тримає копію рівною канону.
Знахідка була хибною, і «лікування» — друга реєстрація в проєкті — запускало б
ту саму перевірку двічі на кожному завершенні ходу.

Покриття — перелік способів, якими хук середовища може ТИХО не працювати,
по випадку на кожен (Core Rule 15: перелік інцидентів, а не число):
  синхронізатор не підключений · файла середовища нема · середовище не реєструє ·
  активної копії нема · копія ≠ канон · налаштування середовища зіпсовані ·
  схожа назва синхронізатора (`async.sh`) не зараховується за справжній.
І два випадки старої поведінки, яку розширення не має зламати: сирота → тривога,
свідомо не підключений із причиною → ✅.

Усе в тимчасовій теці з підміненим HOME — справжній ~/.claude не чіпається.

Запуск: python3 tests/probe-wiring.py   (0 — усі збіги, 1 — є розбіжності)
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import shutil
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sd", REPO / "scripts" / "security-drift.py")
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)

HOOK = "-" + "хук"          # маркер самооголошення; зі шматків — щоб стенд не оголошував хуком сам себе
POLICY = """
[wiring]
scan_dirs = ["automations"]
hook_markers = ["-хук"]
intentionally_unwired = ["allowed.sh: свідомо вимкнено для стенду"]

[[wiring.environment_wired]]
script = "envhook.sh"
env_settings = "~/.claude/launcher-settings.json"
active_copy = "~/.claude/envhook.sh"
synced_by = "sync.sh"
"""
CANON = f"#!/bin/bash\n# envhook.sh — Stop{HOOK}: канон\nexit 0\n"


def build(tmp: pathlib.Path, *, env_settings: str | None = "ok", copy: str | None = "same",
          synced: str = "sync.sh") -> pathlib.Path:
    root, home = tmp / "root", tmp / "home"
    for d in ("security", "automations/a", "automations/b", "automations/c", ".claude"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "security" / "policy.toml").write_text(POLICY, encoding="utf-8")
    (root / "automations/a/envhook.sh").write_text(CANON, encoding="utf-8")
    (root / "automations/a/sync.sh").write_text(f"# sync.sh — SessionStart{HOOK}\n", encoding="utf-8")
    (root / "automations/b/allowed.sh").write_text(f"# allowed.sh — SessionStart{HOOK}\n", encoding="utf-8")
    (root / "automations/c/orphan.sh").write_text(f"# orphan.sh — Stop{HOOK}\n", encoding="utf-8")
    cmd = "$CLAUDE_PROJECT_DIR/automations/a/" + synced
    settings = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": cmd}]}]}}
    (root / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    env_file = home / ".claude" / "launcher-settings.json"
    if env_settings == "ok":
        env = {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "~/.claude/envhook.sh"}]}]}}
        env_file.write_text(json.dumps(env), encoding="utf-8")
    elif env_settings == "other":
        env = {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "~/.claude/base.sh"}]}]}}
        env_file.write_text(json.dumps(env), encoding="utf-8")
    elif env_settings == "broken":
        env_file.write_text("{ не json", encoding="utf-8")

    active = home / ".claude" / "envhook.sh"
    if copy == "same":
        active.write_text(CANON, encoding="utf-8")
    elif copy == "old":
        active.write_text(CANON.replace("канон", "стара базова версія"), encoding="utf-8")

    os.environ["HOME"] = str(home)
    return root


def rows_for(root: pathlib.Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for mark, name, detail in sd.check_unwired_hooks(root):
        for script in ("envhook.sh", "allowed.sh", "orphan.sh"):
            if script in name:
                if script in out:
                    out[script + "#дубль"] = (mark, name)
                out[script] = (mark, detail)
    return out


# (назва, параметри build, скрипт, очікуваний стан)
CASES = [
    ("усе на місці → ✅", {}, "envhook.sh", sd.OK),
    ("файла середовища нема → ❓, не ✅", {"env_settings": None}, "envhook.sh", sd.UNKNOWN),
    ("налаштування середовища зіпсовані → ❓", {"env_settings": "broken"}, "envhook.sh", sd.UNKNOWN),
    ("середовище реєструє інше → тривога", {"env_settings": "other"}, "envhook.sh", sd.DRIFT),
    ("активної копії нема → тривога", {"copy": None}, "envhook.sh", sd.DRIFT),
    ("копія ≠ канон → тривога", {"copy": "old"}, "envhook.sh", sd.DRIFT),
    ("синхронізатор не підключений → тривога", {"synced": "other.sh"}, "envhook.sh", sd.DRIFT),
    ("`async.sh` ≠ `sync.sh` → тривога", {"synced": "async.sh"}, "envhook.sh", sd.DRIFT),
    ("стара поведінка: сирота → тривога", {}, "orphan.sh", sd.DRIFT),
    ("стара поведінка: свідомо вимкнений → ✅", {}, "allowed.sh", sd.OK),
]


def main() -> int:
    saved_home = os.environ.get("HOME")
    bad = 0
    try:
        for label, params, script, want in CASES:
            tmp = pathlib.Path(tempfile.mkdtemp(prefix="probe-wiring-"))
            try:
                got_rows = rows_for(build(tmp, **params))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            got = got_rows.get(script, ("—", "рядка немає"))[0]
            if script + "#дубль" in got_rows:
                bad += 1
                print(f"  ❌ {label}: скрипт звітовано двічі")
            elif got != want:
                bad += 1
                print(f"  ❌ {label}: очік={want} факт={got} ({got_rows.get(script, ('', ''))[1][:70]})")
    finally:
        if saved_home is not None:
            os.environ["HOME"] = saved_home
    print(f"  підключеність: {len(CASES) - bad}/{len(CASES)} збігів")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
