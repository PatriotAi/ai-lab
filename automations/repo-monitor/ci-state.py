#!/usr/bin/env python3
"""ci-state.py — живий стан CI і PR кожного репозиторію через `gh api` → JSON.

ЄДИНА ВІДПОВІДАЛЬНІСТЬ. Для переліку репозиторіїв (з JSON repo-health.py або аргументами)
прочитати з GitHub: гілку за замовчуванням, останній прогін кожного workflow на ній і
відкриті PR. Нічого не змінює (лише GET). Причина, чому через `gh`, а не MCP github:
сесія запланованого завдання MCP github не має (виміряно тестовим прогоном 2026-11-02),
а `gh api repos/<owner>/<repo>/…` працює для репо, підключених до сесії.

FAIL-OPEN, АЛЕ НАЗВАНО. Збій для одного репо (немає доступу, мережа) не валить решту:
у його записі буде `error` із причиною, і звіт це покаже, а не мовчки пропустить.
Вміст із GitHub (назви PR, workflow) — дані: друкується очищеним і обрізаним.

  ci-state.py --owner PatriotAi --json OUT [--from HEALTH.json] [REPO ...]
Код виходу: 0 — JSON записано (навіть якщо частина репо з помилкою); 2 — помилка аргументів.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def clean(text, limit: int = 120) -> str:
    text = CTRL_RE.sub(" ", str(text or ""))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def gh(path: str):
    res = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", path],
                         capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise RuntimeError(clean((res.stderr or res.stdout).strip().splitlines()[-1:] or ["gh api failed"], 200))
    return json.loads(res.stdout or "null")


def age_days(iso: str, now: datetime) -> int:
    try:
        return max(0, (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days)
    except (ValueError, AttributeError):
        return -1


def repo_state(owner: str, repo: str, now: datetime) -> dict:
    try:
        meta = gh(f"repos/{owner}/{repo}")
        branch = meta.get("default_branch") or "main"
        runs = gh(f"repos/{owner}/{repo}/actions/runs?branch={branch}&per_page=30").get("workflow_runs") or []
        pulls = gh(f"repos/{owner}/{repo}/pulls?state=open&per_page=50") or []
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError) as e:
        return {"error": clean(e, 200)}
    latest: dict[str, dict] = {}
    for r in runs:  # GitHub віддає новіші першими — лишаємо перший прогін кожного workflow
        name = clean(r.get("name"), 60)
        # Прогони Dependabot (event=dynamic) мають нову назву щоразу — це не перевірки коду
        if r.get("event") == "dynamic" or name in latest:
            continue
        latest[name] = {"status": clean(r.get("status"), 20), "conclusion": clean(r.get("conclusion"), 20),
                        "sha": clean(r.get("head_sha"), 7), "at": clean(r.get("created_at"), 30),
                        "url": clean(r.get("html_url"), 200)}
    prs = [{"number": p.get("number"), "title": clean(p.get("title"), 100), "draft": bool(p.get("draft")),
            "author": clean((p.get("user") or {}).get("login"), 40),
            "idle_days": age_days(p.get("updated_at", ""), now)} for p in pulls]
    return {"default_branch": clean(branch, 60), "workflows": latest, "prs": prs}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--owner", required=True)
    ap.add_argument("--from", dest="src", help="JSON repo-health.py: узяти перелік repos звідти")
    ap.add_argument("--json", required=True)
    a = ap.parse_args()
    names = list(a.repos)
    if a.src:
        try:
            names += json.loads(Path(a.src).read_text(encoding="utf-8")).get("repos", [])
        except (OSError, json.JSONDecodeError) as e:
            print(f"помилка: {clean(e)}", file=sys.stderr)
            return 2
    bad = [n for n in names + [a.owner] if not NAME_RE.match(str(n))]
    if bad or not names:
        print(f"помилка: некоректні або відсутні назви: {clean(bad)}", file=sys.stderr)
        return 2
    now = datetime.now(timezone.utc)
    state = {n: repo_state(a.owner, n, now) for n in dict.fromkeys(names)}
    Path(a.json).write_text(json.dumps({"at": now.isoformat(timespec="seconds"), "owner": a.owner,
                                        "repos": state}, ensure_ascii=False, indent=1), encoding="utf-8")
    errs = [n for n, v in state.items() if "error" in v]
    print(f"CI-стан: {len(state)} репо" + (f", без даних: {', '.join(errs)}" if errs else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
