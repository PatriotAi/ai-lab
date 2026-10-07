#!/usr/bin/env python3
"""probe-consent-scope.py — стенд: записана згода прив'язана до ЦІЛІ (F-17).

НАВІЩО. Гейт шукав записану згоду лише за ідентифікатором правила
(`mcp-merge_pull_request`). Рядок у `security/consent.md`, написаний «лише на
PR #45», відкривав злиття БУДЬ-ЯКОГО PR, доки не спливе строк: слова «лише на
#45» читала людина, а не код. Тепер рядок може називати ціль —
`mcp-merge_pull_request@owner/repo#N`, — і для дії, ціль якої відома, рядок без
цілі або з іншою ціллю не діє (закрито за замовчуванням).

ЯК ПЕРЕВІРЯЄ. Будує копію `security/` у тимчасовій теці (робочі файли не
чіпаються — правило `tests/README.md`), для кожного випадку пише туди власний
`consent.md` і запускає справжній `pretooluse.py` так, як це робить харнес:
JSON на stdin, рішення — з stdout (порожньо = дозволено).

РЕЖИМ --mutants. Вносить у копію правдоподібні поломки й вимагає, щоб стенд
кожну спіймав. Мутант, що вижив, — діра в стенді, а не в коді. Мутант «ціль не
передається» відтворює саме ту поведінку, яка була до виправлення, тож це і є
фальсифікація на нерухомому стані: вона не залежить від історії git.

Запуск: python3 tests/probe-consent-scope.py [--mutants] [--verbose]
Код виходу: 0 — усі випадки збігаються (і всі мутанти спіймані); 1 — ні.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = datetime.now(timezone.utc).date()
T = TODAY.isoformat()
Y = (TODAY - timedelta(days=1)).isoformat()
WHY = "тестова причина, довша за двадцять символів"

# Назви збираються зі шматків: стенд не має тригерити те, що вимірює.
MERGE = "mcp__github__" + "merge_pull_request"
R = "mcp-" + "merge_pull_request"
SETTINGS = ".claude/" + "settings.json"


def merge(owner: str, repo: str, number: int) -> tuple[str, dict]:
    return MERGE, {"owner": owner, "repo": repo, "pullNumber": number,
                   "merge_method": "merge"}


WRITE_SETTINGS = ("Write", {"file_path": SETTINGS})

# (назва, рядки згоди [(правило, до)], дія, очікуване рішення)
CASES: list[tuple[str, list[tuple[str, str]], tuple[str, dict], str]] = [
    ("без згоди merge блокується", [], merge("patriotai", "ai-lab", 46), "deny"),
    ("згода на #45 відкриває #45",
     [(f"{R}@patriotai/ai-lab#45", T)], merge("patriotai", "ai-lab", 45), "allow"),
    ("згода на #45 НЕ відкриває #46",
     [(f"{R}@patriotai/ai-lab#45", T)], merge("patriotai", "ai-lab", 46), "deny"),
    ("регістр owner/repo не важить",
     [(f"{R}@PatriotAi/AI-Lab#45", T)], merge("patriotai", "ai-lab", 45), "allow"),
    ("рядок без цілі НЕ відкриває merge (закрито за замовчуванням)",
     [(R, T)], merge("patriotai", "ai-lab", 46), "deny"),
    ("прострочена згода з ціллю не діє",
     [(f"{R}@patriotai/ai-lab#45", Y)], merge("patriotai", "ai-lab", 45), "deny"),
    ("той самий номер в іншому репо не відкривається",
     [(f"{R}@patriotai/other#45", T)], merge("patriotai", "ai-lab", 45), "deny"),
    ("контроль: без згоди запис у налаштування агента блокується",
     [], WRITE_SETTINGS, "deny"),
    ("правило без цілі працює як досі", [("agent-settings", T)], WRITE_SETTINGS, "allow"),
    ("згода з ціллю не відкриває дію без цілі",
     [("agent-settings@patriotai/ai-lab#1", T)], WRITE_SETTINGS, "deny"),
]

# (назва, файл у копії, що було, що стало)
MUTANTS: list[tuple[str, str, str, str]] = [
    ("ціль не передається в пошук згоди (поведінка до F-17)",
     "security/spine/pretooluse.py",
     "consent = active_consent(verdict.rule_id, verdict.scope)",
     "consent = active_consent(verdict.rule_id)"),
    ("ціль рядка не порівнюється",
     "security/spine/pretooluse.py",
     "if row_scope != scope:",
     "if False:"),
    ("класифікатор не визначає ціль злиття",
     "security/spine/classify.py",
     "scope=_mcp_scope(tool_input),",
     'scope="",'),
]


def build_sandbox(tmp: Path) -> Path:
    sandbox = tmp / "repo"
    shutil.copytree(ROOT / "security", sandbox / "security",
                    ignore=shutil.ignore_patterns("audit", "tests", "consent.md"))
    return sandbox


def write_consent(sandbox: Path, rows: list[tuple[str, str]]) -> None:
    lines = ["# Згода (стенд)", "", "| rule | until | причина |", "|---|---|---|"]
    lines += [f"| {rule} | {until} | {WHY} |" for rule, until in rows]
    (sandbox / "security" / "consent.md").write_text("\n".join(lines) + "\n",
                                                     encoding="utf-8")


def decide(sandbox: Path, tool: str, tool_input: dict) -> str:
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
    res = subprocess.run([sys.executable, str(sandbox / "security" / "spine" / "pretooluse.py")],
                         input=payload, capture_output=True, text=True, cwd=sandbox,
                         timeout=60)
    out = res.stdout.strip()
    if not out:
        return "allow"
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError, TypeError):
        return "?"


def run_cases(sandbox: Path, verbose: bool) -> int:
    bad = 0
    for name, rows, (tool, tool_input), want in CASES:
        write_consent(sandbox, rows)
        got = decide(sandbox, tool, tool_input)
        if got != want:
            bad += 1
            if verbose:
                print(f"  ❌ {name}: очік={want} факт={got}")
        elif verbose:
            print(f"  ✅ {name}")
    return bad


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutants", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv[1:])

    with tempfile.TemporaryDirectory() as td:
        sandbox = build_sandbox(Path(td))
        bad = run_cases(sandbox, args.verbose and not args.mutants)
        total = len(CASES)
        if not args.mutants:
            print(f"  згода й ціль: {total - bad}/{total} випадків збігаються")
            return 1 if bad else 0

        # Контроль: на цілому коді стенд мовчить, інакше мутанти нічого не доводять.
        if bad:
            print(f"  ❌ на цілому коді {bad}/{total} випадків не збігаються — прогін недійсний")
            return 1
        survived: list[str] = []
        for name, rel, old, new in MUTANTS:
            path = sandbox / rel
            original = path.read_text(encoding="utf-8")
            if old not in original:
                survived.append(f"{name} (цільовий рядок не знайдено)")
                continue
            path.write_text(original.replace(old, new, 1), encoding="utf-8")
            caught = run_cases(sandbox, False) > 0
            path.write_text(original, encoding="utf-8")
            if not caught:
                survived.append(name)
            elif args.verbose:
                print(f"  ✅ мутант спіймано: {name}")
        if survived:
            print(f"  ❌ мутанти: {len(MUTANTS) - len(survived)}/{len(MUTANTS)} спіймано; вижили:")
            for name in survived:
                print(f"     - {name}")
            return 1
        print(f"  мутанти згоди: {len(MUTANTS)}/{len(MUTANTS)} спіймано")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
