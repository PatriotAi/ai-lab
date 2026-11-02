#!/usr/bin/env python3
"""update-page.py — оновити сторінку «Монітор репозиторіїв» новим сканом і надрукувати дельту.

ЄДИНА ВІДПОВІДАЛЬНІСТЬ. Сторінка (приватний Artifact) — і дашборд для власника, і
СХОВИЩЕ стану між прогонами: дані лежать у блоці
`<script type="application/json" id="monitor-data">`. Скрипт бере звідти попередній стан,
порівнює з новим (repo-health.py --json + ci-state.py --json), записує оновлену сторінку
і друкує markdown-дельту для звіту прогону.

ЧОМУ ТАК. Сесія запланованого завдання — свіжа щоразу й не має `list_events`, тож
попередній звіт їй недоступний (виміряно 2026-11-02). Artifact read/publish вона має.

ДЕЛЬТА. 🆕 нові знахідки (з пропозицією) · ✅ виправлені · нові/зниклі репо ·
нові заливання (HEAD змінився) з вердиктом CI на цьому коміті · червоний CI ·
PR без руху > 14 днів. Нічого нового → один рядок «без змін».

  update-page.py --page PAGE --health NOW.json [--ci CI.json] --out OUT [--md DELTA.md]
Код виходу: 0 — сторінку записано; 2 — сторінку/вхід не прочитано (сторінку НЕ записано).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BLOCK_RE = re.compile(r'(<script type="application/json" id="monitor-data">)(.*?)(</script>)', re.S)
SEV = ("high", "medium", "low", "info")
ICON = {"high": "🔴", "medium": "🟠", "low": "🟡", "info": "⚪"}
RED = {"failure", "cancelled", "timed_out", "startup_failure", "action_required"}
STALE_DAYS = 14
MAX_HISTORY = 120


def embed(data: dict) -> str:
    """JSON усередині <script>: `<`, `>` і `&` екрануються — дані з чужих репо не закриють тег."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def load(path: str, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"помилка: {what} не прочитано ({e})")


def red_runs(ci: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for repo, st in (ci.get("repos") or {}).items():
        names = [n for n, w in (st.get("workflows") or {}).items() if w.get("conclusion") in RED]
        if names:
            out[repo] = sorted(names)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--page", required=True)
    ap.add_argument("--health", required=True)
    ap.add_argument("--ci")
    ap.add_argument("--out", required=True)
    ap.add_argument("--md")
    a = ap.parse_args()

    try:
        page = Path(a.page).read_text(encoding="utf-8")
    except OSError as e:
        print(f"помилка: сторінку не прочитано ({e})", file=sys.stderr)
        return 2
    m = BLOCK_RE.search(page)
    if not m:
        print("помилка: на сторінці немає блоку monitor-data — це не сторінка монітора", file=sys.stderr)
        return 2
    try:
        prev = json.loads(m.group(2).strip() or "{}")
    except json.JSONDecodeError:
        prev = {}
        print("увага: попередні дані зіпсовані — дельта від нуля", file=sys.stderr)
    try:
        health = load(a.health, "скан")
        ci = load(a.ci, "CI-стан") if a.ci else {}
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    first = not prev.get("findings") and not prev.get("repos")
    findings = health.get("findings", [])
    old_ids = {f["id"] for f in prev.get("findings", [])}
    new_ids = {f["id"] for f in findings}
    added = [f for f in findings if f["id"] not in old_ids]
    gone = [f for f in prev.get("findings", []) if f["id"] not in new_ids]
    repos, prev_repos = health.get("repos", []), prev.get("repos", [])
    repos_new = [r for r in repos if prev_repos and r not in prev_repos]
    repos_gone = [r for r in prev_repos if r not in repos]
    no_ci = {f["repo"] for f in findings if f["rule"] == "RH01"}

    heads, prev_heads = health.get("heads", {}), prev.get("heads", {})
    pushes = []
    for repo, h in heads.items():
        old = (prev_heads.get(repo) or {}).get("sha")
        if not old or old == h.get("sha"):
            continue
        wf = ((ci.get("repos") or {}).get(repo) or {}).get("workflows") or {}
        on_sha = {n: (w.get("conclusion") or w.get("status")) for n, w in wf.items() if w.get("sha") == h.get("sha")}
        # Фактичний прогін на цьому коміті — прямий доказ, тож він важить більше за статичну RH01
        if on_sha and all(v == "success" for v in on_sha.values()):
            verdict = "CI зелений"
        elif on_sha:
            verdict = "CI: " + ", ".join(f"{n} — {v}" for n, v in sorted(on_sha.items()))
        elif repo in no_ci or not wf:
            verdict = "не перевірено — у репо немає CI"
        else:
            verdict = "прогону CI на цьому коміті немає"
        pushes.append({"repo": repo, "from": old, "to": h.get("sha"), "verdict": verdict})

    red, prev_red = red_runs(ci), prev.get("red", {})
    red_new = {r: v for r, v in red.items() if set(v) - set(prev_red.get(r, []))}
    stale = [{"repo": r, "number": p.get("number"), "title": p.get("title"), "idle_days": p.get("idle_days")}
             for r, st in (ci.get("repos") or {}).items() for p in (st.get("prs") or [])
             if (p.get("idle_days") or 0) > STALE_DAYS]
    ci_errors = {r: st["error"] for r, st in (ci.get("repos") or {}).items() if "error" in st}

    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEV}
    history = (prev.get("history") or [])[-(MAX_HISTORY - 1):] + [{
        "at": now, **counts, "new": len(added), "gone": len(gone), "red": sum(len(v) for v in red.values())}]
    data = {"updated": now, "first_run": first, "repos": repos, "heads": heads, "findings": findings,
            "waived": health.get("waived", 0), "ci": ci.get("repos", {}), "red": red,
            "delta": {"new": [f["id"] for f in added] if not first else [], "gone": gone,
                      "repos_new": repos_new, "repos_gone": repos_gone, "pushes": pushes,
                      "red_new": red_new, "stale": stale, "ci_errors": ci_errors},
            "history": history}
    Path(a.out).write_text(BLOCK_RE.sub(lambda mm: mm.group(1) + embed(data) + mm.group(3), page, count=1),
                           encoding="utf-8")

    # --- markdown-дельта для звіту прогону ---
    total = " ".join(f"{ICON[s]}{counts[s]}" for s in SEV if counts[s])
    head = f"🩺 {len(repos)} репо · знахідок: {total or '0'}"
    changed = (not first) and (added or gone or repos_new or repos_gone or pushes or red_new)
    lines = []
    if first:
        lines.append(f"{head} · перший прогін: база збережена на сторінці, далі — лише дельта.")
    elif not changed:
        lines.append(f"{head} · без змін.")
    else:
        lines.append(f"{head} · 🆕 {len(added)} · ✅ {len(gone)}")
    if repos_new or repos_gone:
        lines.append(f"- Репозиторії: нові {', '.join(repos_new) or '—'}; зникли {', '.join(repos_gone) or '—'}")
    for p in pushes:
        lines.append(f"- ⬆️ `{p['repo']}` нове заливання {p['from']}→{p['to']}: {p['verdict']}")
    for r, v in sorted(red_new.items()):
        lines.append(f"- ❌ `{r}` червоний CI на гілці за замовчуванням: {', '.join(v)}")
    for f in sorted(added if not first else [], key=lambda x: (SEV.index(x["severity"]), x["repo"])):
        where = f" `{f['path']}`" if f.get("path") else ""
        lines.append(f"- 🆕 {ICON[f['severity']]} `{f['repo']}` **{f['rule']}** {f['title']}{where}\n"
                     f"  → {f.get('proposal', '')}  `[{f['id']}]`")
    for f in gone if not first else []:
        lines.append(f"- ✅ `{f['repo']}` {f['rule']} — {f['title']}")
    if ci_errors:
        lines.append(f"- ⚠️ CI-стан не прочитано: {', '.join(sorted(ci_errors))} (див. сторінку)")
    md = "\n".join(lines) + "\n"
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")
    print(md, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
