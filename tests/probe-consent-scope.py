#!/usr/bin/env python3
"""probe-consent-scope.py — стенд: записана згода прив'язана до ЦІЛІ (F-17).

НАВІЩО. Гейт шукав записану згоду лише за ідентифікатором правила
(`mcp-merge_pull_request`). Рядок у `security/consent.md`, написаний «лише на
PR #45», відкривав злиття БУДЬ-ЯКОГО PR, доки не спливе строк: слова «лише на
#45» читала людина, а не код. Тепер рядок може називати ціль —
`mcp-merge_pull_request@owner/repo#N`, — і для дії, ціль якої відома, рядок без
цілі або з іншою ціллю не діє (закрито за замовчуванням).

W-12 (2026-10-16). `require_target` у політиці не читав жоден рядок коду: ціль
мали лише злиття PR через MCP, а правка налаштувань, запис воркфлоу чи `gh api`
відкривались рядком без цілі. Тепер ціль має кожне правило з `require_target`
(шлях, `метод шлях`, `ключ=значення`), а дію, ціль якої не визначено, не
відкриває жоден рядок.

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
WF = ".github/" + "workflows/x.yml"
ENV = "." + "env"
SEND = "mcp__Slack__" + "slack_send_message"
GH = "gh " + "api -X PUT repos/patriotai/ai-lab/pulls/"
API = "github-api-" + "write"


def merge(owner: str, repo: str, number: int) -> tuple[str, dict]:
    return MERGE, {"owner": owner, "repo": repo, "pullNumber": number,
                   "merge_method": "merge"}


def bash(command: str) -> tuple[str, dict]:
    return "Bash", {"command": command}


def push(owner: str, repo: str, path: str) -> tuple[str, dict]:
    return "mcp__github__" + "push_files", {
        "owner": owner, "repo": repo, "branch": "b", "message": "m",
        "files": [{"path": path, "content": "x"}]}


def delete(owner: str, repo: str, path: str, branch: str) -> tuple[str, dict]:
    return "mcp__github__" + "delete_file", {
        "owner": owner, "repo": repo, "path": path, "branch": branch, "message": "m"}


WRITE_SETTINGS = ("Write", {"file_path": SETTINGS})

# (назва, рядки згоди [(правило, до)], дія, очікуване рішення)
CASES: list[tuple[str, list[tuple[str, str]], tuple, str]] = [
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
    # Свідома зміна W-12: до 2026-10-16 тут чекали «allow» — рядок без цілі
    # відкривав правку налаштувань, хоча правило вимагає цілі.
    ("рядок без цілі не відкриває правку налаштувань (W-12)",
     [("agent-settings", T)], WRITE_SETTINGS, "deny"),
    ("згода з чужою ціллю не відкриває правку налаштувань",
     [("agent-settings@patriotai/ai-lab#1", T)], WRITE_SETTINGS, "deny"),
    ("ціль-шлях відкриває свій файл",
     [(f"agent-settings@{SETTINGS}", T)], WRITE_SETTINGS, "allow"),
    ("ціль-шлях не відкриває інший файл того ж правила",
     [(f"agent-settings@{SETTINGS}", T)],
     ("Write", {"file_path": ".claude/" + "settings.local.json"}), "deny"),
    ("ціль-шлях відкриває той самий запис оболонкою",
     [(f"agent-settings@{SETTINGS}", T)], bash(f"echo x > {SETTINGS}"), "allow"),
    ("ціль команди перелічує кожен захищений шлях",
     [(f"agent-settings@{SETTINGS}", T)], bash(f"echo x > {SETTINGS}; cat {ENV}"), "deny"),
    ("`gh api`: згода на #86 відкриває #86",
     [(f"{API}@put repos/patriotai/ai-lab/pulls/86/merge", T)], bash(GH + "86/merge"), "allow"),
    ("`gh api`: згода на #86 не відкриває #87",
     [(f"{API}@put repos/patriotai/ai-lab/pulls/86/merge", T)], bash(GH + "87/merge"), "deny"),
    ("згода на MCP-злиття не відкриває те саме злиття через `gh api`",
     [(f"{R}@patriotai/ai-lab#86", T)], bash(GH + "86/merge"), "deny"),
    ("MCP-дію без цілі не відкриває рядок без цілі (W-12)",
     [("mcp-slack_send_message", T)], (SEND, {"text": "x"}), "deny"),
    ("MCP-дію відкриває ціль за ключем аргументів",
     [("mcp-slack_send_message@channel_id=c1", T)], (SEND, {"channel_id": "C1", "text": "x"}),
     "allow"),
    ("файл іншого репо через MCP: ціль несе owner/repo",
     [(f"workflows@o/r:{WF}", T)], push("o", "r", WF), "allow"),
    ("згода на локальний файл не відкриває файл в іншому репо",
     [(f"workflows@{WF}", T)], push("o", "r", WF), "deny"),
    # ── Рев'ю #91 (2026-10-18) ──────────────────────────────────────────────
    # 3. Згода на одну дію не відкриває складену команду з ІНШОЮ незворотною
    # дією: вердикт за першим правилом ховав решту.
    ("згода на файл не відкриває складену команду з примусовим пушем",
     [(f"agent-settings@{SETTINGS}", T)],
     bash(f"echo x > {SETTINGS} && git push --force origin main"), "deny"),
    ("згода на `gh api` не відкриває складену команду з видаленням",
     [(f"{API}@put repos/patriotai/ai-lab/pulls/86/merge", T)],
     bash(GH + "86/merge && rm -rf build"), "deny"),
    ("контроль: згода на файл відкриває команду з безпечним хвостом",
     [(f"agent-settings@{SETTINGS}", T)], bash(f"echo x > {SETTINGS} && git status"), "allow"),
    # 15. Ціль MCP — усі ключі: згода на гілку `feature` не відкриває `main`.
    ("ціль MCP розрізняє гілки",
     [("mcp-delete_file@o/r:path=docs/a.md,branch=feature", T)],
     delete("o", "r", "docs/a.md", "main"), "deny"),
    ("ціль MCP з усіма ключами відкриває саме цю дію",
     [("mcp-delete_file@o/r:path=docs/a.md,branch=main", T)],
     delete("o", "r", "docs/a.md", "main"), "allow"),
    # Плейсхолдер `{owner}/{repo}` не прив'язує репо — такої цілі нема.
    ("`gh api` із плейсхолдером репо не відкривається",
     [(API + "@put repos/{owner}/{repo}/pulls/86/merge", T)],
     bash("gh " + "api -X PUT repos/{owner}/{repo}/pulls/86/merge"), "deny"),
    # Інший хост — інша ціль.
    ("згода на github.com не відкриває той самий шлях на іншому хості",
     [(f"{API}@put repos/patriotai/ai-lab/pulls/86/merge", T)],
     bash("gh " + "api --hostname ghe.example.com -X PUT repos/patriotai/ai-lab/pulls/86/merge"),
     "deny"),
    # 8. Тека, з якої виконується команда (`cwd` у вході хука), — частина цілі.
    ("відносний запис із теки `.claude` ловиться за `cwd` хука",
     [], ("Bash", {"command": "echo x > settings.json"}, ".claude"), "deny"),
    ("контроль: той самий запис із кореня — звичайний файл",
     [], ("Bash", {"command": "echo x > settings.json"}, "."), "allow"),
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
     'scope=_mcp_scope(tool_input, mcp.get("target_keys", [])),',
     'scope="",'),
    ("`require_target` ігнорується (поведінка до W-12)",
     "security/spine/pretooluse.py",
     "if verdict.require_target and not verdict.scope:",
     "if False:"),
    # Цілі трьох мутантів нижче оновлено 2026-10-18: вердикт будує спільний
    # помічник `verdict(…)`, ціль передається йому останнім аргументом.
    ("шлях інструмента не стає ціллю",
     "security/spine/classify.py",
     "raw_path or tool_hit[1], resolved or tool_hit[1], tool_targets)",
     'raw_path or tool_hit[1], resolved or tool_hit[1], "")'),
    ("шлях команди не стає ціллю",
     "security/spine/classify.py",
     "command, command, bash_targets)",
     'command, command, "")'),
    ("ціль `gh api` не передається",
     "security/spine/classify.py",
     'command, command, "" if "" in writes else "+".join(writes))',
     'command, command, "")'),
    # ── Рев'ю #91 (2026-10-18) ──────────────────────────────────────────────
    ("складену команду відкриває згода на одну її дію (поведінка до рев'ю)",
     "security/spine/pretooluse.py",
     "if verdict.combined:",
     "if False:"),
    ("класифікатор не позначає складену команду",
     "security/spine/classify.py",
     "if len(rule_ids) > 1:",
     "if False:"),
    ("ціль MCP — лише перший ключ (поведінка до рев'ю)",
     "security/spine/classify.py",
     'parts.append(f"{key}={text}")',
     'return f"{prefix}{key}={text}".lower()'),
    ("`cwd` хука не передається в класифікатор",
     "security/spine/pretooluse.py",
     'classify(tool_name, tool_input, ROOT, policy, cwd=payload.get("cwd"))',
     "classify(tool_name, tool_input, ROOT, policy)"),
    ("плейсхолдер `{owner}/{repo}` стає ціллю",
     "security/spine/classify.py",
     'scope = "" if "{" in path else f"{verb} {where}{path}".lower()',
     'scope = f"{verb} {where}{path}".lower()'),
    ("хост не входить у ціль `gh api`",
     "security/spine/classify.py",
     'where = f"{host.lower()}/" if host else ""',
     'where = ""'),
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


def decide(sandbox: Path, tool: str, tool_input: dict, cwd: str | None = None) -> str:
    message = {"tool_name": tool, "tool_input": tool_input}
    if cwd is not None:                 # тека, з якої харнес виконує команду
        (sandbox / cwd).mkdir(parents=True, exist_ok=True)
        message["cwd"] = str((sandbox / cwd).resolve())
    payload = json.dumps(message)
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
    for name, rows, action, want in CASES:
        write_consent(sandbox, rows)
        got = decide(sandbox, *action)
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
