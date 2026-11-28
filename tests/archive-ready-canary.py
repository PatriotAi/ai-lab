#!/usr/bin/env python3
"""archive-ready-canary.py — стенд для scripts/check-archive-ready.py.

Перевірка, що лише проходить на чистому, не доводить нічого (CLAUDE.md §11):
стенд будує чистий пакет (має бути ГОТОВА, код 0) і по одному зламаному на
КОЖНУ умову A1–A9 (має бути НЕ ГОТОВА, код 1, і впасти саме ця умова), плюс
поганий вхід (код 2). Нічого не пише в репо: `--append` не викликається.

Запуск: python3 tests/archive-ready-canary.py   Код виходу: 0 — усе спіймано.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-archive-ready.py"
CAND, SUCC = "session_01Tu38bs4YUEsPVoS1BYrTwa", "session_01Tu38bpUgiDV7NzppHZ9awv"
HANDOFF = "docs/continuation/2026-11-28-harness-handoff-4.md"


def ev(kind: str, ts: str, content: list, **extra) -> dict:
    return {"created_at": ts, kind: {"internal_anthropic_catchall": {"message": {"content": content}, **extra}}}


CLEAN = {
    "self_id": SUCC,
    "candidate": {
        "id": CAND, "session_status": "SESSION_STATUS_IDLE",
        "status_bucket": "SESSION_STATUS_BUCKET_COMPLETED", "foreground_active": False,
        "created_at": "2026-11-28T09:33:35Z", "tags": ["harness-research"],
        "session_context": {"sources": [{"git_repository": {"revision": "claude/harness-rules-drift"}}]},
        "external_metadata": {"unpushed_work": False, "current_branches": {"": "claude/harness-bridge"},
                              "post_turn_summary": {"needs_action": ""}},
    },
    "successor": {
        "id": SUCC, "session_status": "SESSION_STATUS_RUNNING", "connection_status": "connected",
        "status_bucket": "SESSION_STATUS_BUCKET_WORKING", "created_at": "2026-11-28T13:21:51Z",
        "tags": ["harness-research"],
    },
    "candidate_events": [
        ev("user", "2026-11-28T13:20:00Z", [{"type": "text", "text": "питання"}]),
        ev("assistant", "2026-11-28T13:21:00Z", [{"type": "tool_use", "name": "Bash", "input": {}}]),
        ev("user", "2026-11-28T13:21:30Z", [{"type": "tool_result", "content": "ok"}]),
        ev("result", "2026-11-28T13:22:18Z", [], is_error=False),
    ],
    "triggers": [{"id": "trig_other", "persistent_session_id": "session_x", "enabled": True},
                 {"id": "trig_done", "persistent_session_id": CAND, "enabled": False}],
    "open_prs": [{"ref": "patriotai/ai-lab#200", "head": "claude/harness-bridge"},
                 {"ref": "patriotai/ai-lab#201", "head": "claude/elsewhere"}],
    "successor_watches": ["patriotai/ai-lab#200"],
    "handoff": {"path": HANDOFF, "ref": "HEAD"},
    "line_tag": "harness-research",
}


def mut(f):
    b = copy.deepcopy(CLEAN)
    f(b)
    return b


MUTANTS = {
    "A1": lambda b: b.update(self_id=CAND),
    "A2": lambda b: b["candidate"].update(session_status="SESSION_STATUS_RUNNING"),
    "A3": lambda b: b["candidate"]["external_metadata"].update(unpushed_work=True),
    "A4": lambda b: b["triggers"].append({"id": "trig_live", "persistent_session_id": CAND, "enabled": True}),
    "A5": lambda b: b.update(successor_watches=[]),
    "A6": lambda b: b["candidate_events"].append(
        ev("user", "2026-11-28T13:30:00Z", [{"type": "text", "text": "ще питання"}])),
    "A7": lambda b: b["handoff"].update(path="docs/continuation/README.md"),
    "A8": lambda b: b["successor"].update(connection_status="disconnected"),
    "A9": lambda b: b["candidate"].update(tags=[]),
}
# Додаткові форми A6: питання власнику через AskUserQuestion і needs_action.
EXTRA = {
    "A6/ask": lambda b: b["candidate_events"].insert(3, ev(
        "assistant", "2026-11-28T13:22:00Z", [{"type": "tool_use", "name": "AskUserQuestion", "input": {}}])),
    "A6/needs": lambda b: b["candidate"]["external_metadata"]["post_turn_summary"].update(needs_action="злиття"),
    "A6/err": lambda b: b["candidate_events"][3]["result"]["internal_anthropic_catchall"].update(is_error=True),
    "A2/fg": lambda b: b["candidate"].update(foreground_active=True),
}


def run(bundle) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(bundle if isinstance(bundle, str) else json.dumps(bundle))
    r = subprocess.run([sys.executable, str(SCRIPT), f.name], capture_output=True, text=True)
    Path(f.name).unlink()
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    fails = []
    rc, out = run(CLEAN)
    if rc != 0 or "mcp-archive_session@session_id=" + CAND.lower() not in out:
        fails.append(f"чистий пакет: очікували 0 і рядок згоди, отримали {rc}\n{out}")
    for name, f in {**MUTANTS, **EXTRA}.items():
        rc, out = run(mut(f))
        cond = name.split("/")[0]
        hit = any(l.startswith("❌ " + cond) for l in out.splitlines())
        if rc != 1 or not hit or "mcp-archive_session@" in out:
            fails.append(f"мутант {name}: очікували 1 і ❌ {cond}, отримали {rc}\n{out}")
    rc, _ = run("[1, 2]")
    if rc != 2:
        fails.append(f"поганий вхід: очікували 2, отримали {rc}")
    total = 1 + len(MUTANTS) + len(EXTRA) + 1
    for f in fails:
        print("❌", f)
    print(f"archive-ready: {total - len(fails)}/{total}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
