#!/usr/bin/env python3
"""ablation-run.py — ізольований прогін задачі абляції з варіантом контексту (Ф0.10).

НАВІЩО. Абляція H3 і replay H2 (дослідження «Вивірений розвиток») мають сенс лише тоді, коли
агент (а) не бачить еталонного рішення і (б) справді отримує досліджуваний варіант правил.
Обидві вади невидимі в результатах: прогін виглядає чистим, а міряє не те (незалежне рев'ю
перед заморозкою, R3 і R11). Тому обидві умови тут — машинні перевірки, а не обіцянки.

ЩО РОБИТЬ.
    prepare  — знімок дерева коміту `start` (git archive) у НОВИЙ репозиторій з одним комітом:
               жодних refs, remotes і об'єктів основного репо, тож еталон недосяжний. Поверх
               знімка накладається варіант `CLAUDE.md`; скрипт SessionStart знімка (якщо є)
               глушиться, а варіант стартової вставки подається окремим файлом. Маніфест
               `run-manifest.json` фіксує sha256 усього поданого. Наприкінці — самоперевірка
               ізоляції (verify).
    verify   — ізоляція ціла: один коміт, без remotes, еталон недосяжний, sha256 поданого
               контексту збігаються з маніфестом.
    command  — друкує команду запуску агента (`claude -p …`) для підготовленого прогону.
    scan     — транскрипт прогону: згадки комітів, пізніших за `start`, і мережеві команди.
               Такий прогін вилучається й звітується.
    evaluate — твердження задачі на робочому дереві прогону (та сама `holds`, що й у
               `check-ablation-tasks.py`; база для `untouched` — єдиний коміт знімка).

Доставку перевірено розвідкою 2026-11-10 (маркери в трьох джерелах, агент без інструментів):
із `--setting-sources project` агент отримує `CLAUDE.md` робочого дерева, вставку SessionStart
і текст `--append-system-prompt-file`; із порожнім `--setting-sources` — нічого з першого й
другого. Вставку подаємо останнім способом для ВСІХ задач: старі знімки не мають проводки хука,
а однаковий канал потрібен для порівнянності.

МЕЖА (названа, не закрита): оболонку агента від мережі механічно не відрізано — процесу
потрібен доступ до API моделі. Тому вебінструменти вимкнено прапорцями, а мережеві команди
ловить `scan`.

Запуск:
    python3 scripts/ablation-run.py prepare --task ID --variant ТЕКА --out ТЕКА [--tasks ФАЙЛ] [--root КОРІНЬ]
    python3 scripts/ablation-run.py verify ТЕКА-ПРОГОНУ
    python3 scripts/ablation-run.py command ТЕКА-ПРОГОНУ --model КЛАС
    python3 scripts/ablation-run.py scan ТЕКА-ПРОГОНУ ТРАНСКРИПТ [--root КОРІНЬ]
    python3 scripts/ablation-run.py evaluate ТЕКА-ПРОГОНУ
Код виходу: 0 — чисто · 1 — знахідки (ізоляцію порушено, прогін вилучити, твердження впали) ·
2 — виконати неможливо (нема задачі, варіанта, коміту).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import re
import shlex
import subprocess
import sys
import tarfile
from pathlib import Path

TASKS = "experiments/verified-development/ablation-tasks.jsonl"
MANIFEST = "run-manifest.json"
REPO = "repo"
INSERT = "session-insert.md"
HOOK = "automations/session-start/session-start.sh"
SILENT_HOOK = "#!/usr/bin/env bash\n# Заглушено прогоном абляції: вставку подає --append-system-prompt-file.\nexit 0\n"
HEX = re.compile(r"\b[0-9a-f]{7,40}\b")
NETWORK = re.compile(
    r"\b(?:curl|wget|nc|ssh|scp)\s|\bgit\s+(?:fetch|pull|clone|push|remote\s+add|ls-remote)\b"
    r"|\bgh\s+\w|\bpip3?\s+install\b|\bnpm\s+(?:i|install)\b|https?://", re.I)
TOOLS = "Read,Grep,Glob,Edit,Write,Bash"
NO_TOOLS = "WebFetch,WebSearch,Agent"


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_task(tasks: Path, task_id: str) -> dict | None:
    for raw in tasks.read_text(encoding="utf-8").splitlines():
        if raw.strip() and json.loads(raw).get("id") == task_id:
            return json.loads(raw)
    return None


def isolation_problems(run: Path) -> list[str]:
    """Вади ізоляції й доставки в підготовленому прогоні."""
    repo = run / REPO
    man_path = run / MANIFEST
    if not man_path.is_file() or not (repo / ".git").exists():
        return [f"{run}: це не підготовлений прогін (нема {MANIFEST} чи {REPO}/.git)"]
    man = json.loads(man_path.read_text(encoding="utf-8"))
    probs: list[str] = []
    count = git(repo, "rev-list", "--count", "--all").stdout.strip()
    if count != "1":
        probs.append(f"у знімку {count or '?'} комітів, а має бути 1 — історія протікає")
    if git(repo, "remote").stdout.strip():
        probs.append("у знімку є remote — еталон можна стягнути")
    if (repo / ".git" / "objects" / "info" / "alternates").exists():
        probs.append("знімок позичає об'єкти іншого репозиторію (alternates)")
    if git(repo, "cat-file", "-e", f"{man['solution']}^{{commit}}").returncode == 0:
        probs.append(f"еталон {man['solution'][:10]} досяжний зі знімка")
    claude_md = repo / "CLAUDE.md"
    if (sha256(claude_md) if claude_md.is_file() else "нема файла") != man["claude_md_sha256"]:
        probs.append("CLAUDE.md у знімку не той, що в маніфесті — варіант контексту підмінено")
    insert = run / INSERT
    if (sha256(insert) if insert.is_file() else "нема файла") != man["insert_sha256"]:
        probs.append(f"{INSERT} не той, що в маніфесті — варіант вставки підмінено")
    hook = repo / HOOK
    if hook.is_file() and hook.read_text(encoding="utf-8") != SILENT_HOOK:
        probs.append("скрипт SessionStart знімка не заглушено — агент отримав би стару вставку")
    return probs


def cmd_prepare(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    tasks = Path(args.tasks) if args.tasks else root / TASKS
    variant, out = Path(args.variant), Path(args.out)
    if not tasks.is_file():
        print(f"⊘ НЕ ГАНЯЛОСЬ: файлу задач нема — {tasks}")
        return 2
    task = load_task(tasks, args.task)
    if task is None:
        print(f"⊘ НЕ ГАНЯЛОСЬ: задачі «{args.task}» нема в {tasks.name}")
        return 2
    for name in ("CLAUDE.md", INSERT):
        if not (variant / name).is_file():
            print(f"⊘ НЕ ГАНЯЛОСЬ: у варіанті нема {name} — {variant}")
            return 2
    if out.exists():
        print(f"⊘ НЕ ГАНЯЛОСЬ: тека прогону вже існує — {out} (прогони не перезаписуються)")
        return 2
    tar = subprocess.run(["git", "archive", "--format=tar", task["start"]], cwd=root, capture_output=True)
    if tar.returncode != 0:
        print(f"⊘ НЕ ГАНЯЛОСЬ: коміту start {task['start'][:10]} нема в історії (обрізаний клон?)")
        return 2
    repo = out / REPO
    repo.mkdir(parents=True)
    tarfile.open(fileobj=io.BytesIO(tar.stdout)).extractall(repo, filter="data")
    (repo / "CLAUDE.md").write_bytes((variant / "CLAUDE.md").read_bytes())
    if (repo / HOOK).is_file():
        (repo / HOOK).write_text(SILENT_HOOK, encoding="utf-8")
    (out / INSERT).write_bytes((variant / INSERT).read_bytes())
    (out / "prompt.txt").write_text(task["prompt"], encoding="utf-8")
    ident = ("-c", "user.email=ablation@local", "-c", "user.name=ablation")
    git(repo, "init", "-q")
    git(repo, *ident, "add", "-A")
    git(repo, *ident, "commit", "-qm", "start snapshot")
    manifest = {
        "task": task["id"], "start": task["start"], "solution": task["solution"],
        "variant": variant.name, "series": args.series,
        "claude_md_sha256": sha256(repo / "CLAUDE.md"), "insert_sha256": sha256(out / INSERT),
        "prompt_sha256": sha256(out / "prompt.txt"), "assertions": task["assertions"],
    }
    (out / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    probs = isolation_problems(out)
    for p in probs:
        print(f"  ✗ {p}")
    if probs:
        return 1
    print(f"✅ прогін підготовлено: {out} (задача {task['id']}, варіант {variant.name}; "
          f"CLAUDE.md sha256 {manifest['claude_md_sha256'][:12]}, вставка {manifest['insert_sha256'][:12]})")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    probs = isolation_problems(Path(args.run))
    for p in probs:
        print(f"  ✗ {p}")
    if probs:
        print("🚩 ізоляцію чи доставку порушено — прогін вилучити й звітувати")
        return 1
    print("✅ ізоляція й доставка цілі: один коміт, без remotes, еталон недосяжний, контекст за маніфестом")
    return 0


def cmd_command(args: argparse.Namespace) -> int:
    run = Path(args.run).resolve()
    if not (run / MANIFEST).is_file():
        print(f"⊘ НЕ ГАНЯЛОСЬ: {run} — не підготовлений прогін")
        return 2
    cmd = ["claude", "-p", (run / "prompt.txt").read_text(encoding="utf-8"), "--model", args.model,
           "--setting-sources", "project", "--strict-mcp-config",
           "--append-system-prompt-file", str(run / INSERT),
           "--allowedTools", TOOLS, "--disallowedTools", NO_TOOLS,
           "--permission-mode", "acceptEdits", "--max-turns", str(args.max_turns),
           "--output-format", "stream-json", "--verbose"]
    print(f"cd {shlex.quote(str(run / REPO))} && {shlex.join(cmd)} > {shlex.quote(str(run / 'transcript.jsonl'))}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    run, root = Path(args.run), Path(args.root).resolve()
    transcript = Path(args.transcript)
    if not (run / MANIFEST).is_file() or not transcript.is_file():
        print("⊘ НЕ ГАНЯЛОСЬ: нема маніфесту прогону чи транскрипту")
        return 2
    man = json.loads((run / MANIFEST).read_text(encoding="utf-8"))
    text = transcript.read_text(encoding="utf-8", errors="replace")
    found: list[str] = []
    for token in sorted(set(HEX.findall(text))):
        full = git(root, "rev-parse", "--verify", "--quiet", f"{token}^{{commit}}").stdout.strip()
        if full and git(root, "merge-base", "--is-ancestor", full, man["start"]).returncode != 0:
            found.append(f"згадано коміт {token}, якого на момент start ще не було")
    for m in sorted({m.group(0).strip() for m in NETWORK.finditer(text)}):
        found.append(f"мережева дія в транскрипті: «{m[:40]}»")
    for f in found[:20]:
        print(f"  ✗ {f}")
    if found:
        print(f"🚩 прогін вилучити й звітувати: {len(found)} знахідок")
        return 1
    print("✅ транскрипт чистий: комітів із майбутнього й мережевих дій не знайдено")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    run = Path(args.run)
    if not (run / MANIFEST).is_file():
        print(f"⊘ НЕ ГАНЯЛОСЬ: {run} — не підготовлений прогін")
        return 2
    spec = importlib.util.spec_from_file_location(
        "check_ablation_tasks", Path(__file__).with_name("check-ablation-tasks.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    man = json.loads((run / MANIFEST).read_text(encoding="utf-8"))
    results = [bool(mod.holds(run / REPO, "HEAD", a)) for a in man["assertions"]]
    out = {"task": man["task"], "variant": man["variant"], "series": man["series"], "results": results}
    (run / "results.json").write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  {man['task']} · {man['variant']} · серія {man['series']}: пройдено {sum(results)} з {len(results)}")
    return 0 if all(results) else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Ізольований прогін задачі абляції з варіантом контексту.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_root = str(Path(__file__).resolve().parents[1])
    p = sub.add_parser("prepare")
    p.add_argument("--task", required=True)
    p.add_argument("--variant", required=True, help=f"тека з CLAUDE.md і {INSERT}")
    p.add_argument("--out", required=True)
    p.add_argument("--series", default="1")
    p.add_argument("--tasks")
    p.add_argument("--root", default=default_root)
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("verify")
    p.add_argument("run")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("command")
    p.add_argument("run")
    p.add_argument("--model", required=True)
    p.add_argument("--max-turns", type=int, default=40)
    p.set_defaults(fn=cmd_command)
    p = sub.add_parser("scan")
    p.add_argument("run")
    p.add_argument("transcript")
    p.add_argument("--root", default=default_root)
    p.set_defaults(fn=cmd_scan)
    p = sub.add_parser("evaluate")
    p.add_argument("run")
    p.set_defaults(fn=cmd_evaluate)
    args = ap.parse_args(argv[1:])
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
