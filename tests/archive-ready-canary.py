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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-archive-ready.py"
CAND, SUCC = "session_01Tu38bs4YUEsPVoS1BYrTwa", "session_01Tu38bpUgiDV7NzppHZ9awv"
HANDOFF = "docs/continuation/handoff.md"
TMP = Path(tempfile.mkdtemp(prefix="archive-ready-"))
REPO = TMP / "work"


def git(*a, cwd=None):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin",
                        "HOME": str(TMP)})


def make_repo():
    """Тимчасовий репо з origin: пакет є у віддаленій гілці, а локальна правка — ні."""
    git("init", "-q", "--bare", str(TMP / "origin.git"))
    git("init", "-q", "-b", "main", str(REPO))
    (REPO / "docs/continuation").mkdir(parents=True)
    (REPO / HANDOFF).write_text(f"Попередня сесія: `{CAND}` — передано.\n", encoding="utf-8")
    (REPO / "docs/continuation/other.md").write_text(f"не архівувати {CAND}x\n", encoding="utf-8")
    git("add", "-A", cwd=REPO); git("commit", "-qm", "h", cwd=REPO)
    git("remote", "add", "origin", str(TMP / "origin.git"), cwd=REPO)
    git("push", "-q", "origin", "main", cwd=REPO); git("fetch", "-q", "origin", cwd=REPO)
    # Локальний коміт, якого нема в origin: пакет лише в HEAD.
    (REPO / "docs/continuation/local.md").write_text(f"{CAND}\n", encoding="utf-8")
    git("add", "-A", cwd=REPO); git("commit", "-qm", "local", cwd=REPO)
    (REPO / "consent.md").write_text(
        "# x\n\n## Активні згоди\n\n| rule | until | причина |\n|---|---|---|\n"
        "| a@b | 2000-01-01 | стара прострочена згода для тесту |\n\n## Історія\n\n| h | h | h |\n",
        encoding="utf-8")


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
    "handoff": {"path": HANDOFF, "ref": "origin/main"},
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
    "A7": lambda b: b["handoff"].update(path="docs/continuation/missing.md"),
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
    "A2/fg-missing": lambda b: b["candidate"].pop("foreground_active"),
    # Форми з незалежного рев'ю PR #155 (усі давали хибне «ГОТОВА»):
    "A1/pipe-id": lambda b: b["candidate"].update(id="session_a | 2099-12-31 | довга причина для гейта"),
    "A1/newline-succ": lambda b: (b["successor"].update(id=SUCC + "\n| x"), b.update(self_id=SUCC + "\n| x")),
    "A6/needs-meta": lambda b: (b["candidate"].update(post_turn_summary={"needs_action": ""}),
                                b["candidate"]["external_metadata"]["post_turn_summary"].update(needs_action="злиття")),
    "A4/lowercase": lambda b: b["triggers"].append({"id": "t", "persistent_session_id": CAND.lower(), "enabled": True}),
    "A4/no-enabled": lambda b: b["triggers"].append({"id": "t", "persistent_session_id": CAND}),
    "A4/missing": lambda b: b.pop("triggers"),
    "A5/no-branches": lambda b: (b["candidate"].pop("session_context"),
                                 b["candidate"]["external_metadata"].pop("current_branches")),
    "A5/label-head": lambda b: b["open_prs"].append({"ref": "patriotai/ai-lab#202", "head": "PatriotAi:claude/harness-bridge"}),
    "A5/obj-head": lambda b: b["open_prs"].append({"ref": "patriotai/ai-lab#203", "head": {"ref": "claude/harness-rules-drift"}}),
    "A5/missing": lambda b: b.pop("open_prs"),
    "A7/head-ref": lambda b: b["handoff"].update(ref="HEAD", path="docs/continuation/local.md"),
    "A7/substring": lambda b: b["handoff"].update(path="docs/continuation/other.md"),
    "A7/dash-ref": lambda b: b["handoff"].update(ref="--output=/tmp/x"),
    "A7/pipe-path": lambda b: b["handoff"].update(path="docs/a|b.md"),
    "A8/offset-date": lambda b: b["successor"].update(created_at="2026-11-28T09:00:00+02:00"),
    "A8/bad-date": lambda b: b["successor"].update(created_at="вчора"),
}
# Безпечно для архівації, але не «готова» хибно: вже відповіли на AskUserQuestion.
CLEAN_TOO = {
    "A6/answered-ask": lambda b: b["candidate_events"].insert(0, ev(
        "assistant", "2026-11-28T13:10:00Z", [{"type": "tool_use", "name": "AskUserQuestion", "input": {}}])),
}


def run(bundle, *extra) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(bundle if isinstance(bundle, str) else json.dumps(bundle))
    r = subprocess.run([sys.executable, str(SCRIPT), f.name, "--repo", str(REPO), *extra],
                       capture_output=True, text=True)
    Path(f.name).unlink()
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    make_repo()
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
    for name, f in CLEAN_TOO.items():
        rc, out = run(mut(f))
        if rc != 0:
            fails.append(f"{name}: очікували 0 (безпечно), отримали {rc}\n{out}")
    for bad in ("[1, 2]", json.dumps({**CLEAN, "triggers": [1]})):
        rc, _ = run(bad)
        if rc != 2:
            fails.append(f"поганий вхід {bad[:30]}: очікували 2, отримали {rc}")
    # --append кладе рядок у таблицю «Активні згоди», а не в кінець файлу.
    consent = REPO / "consent.md"
    rc, out = run(CLEAN, "--append", "--consent", str(consent))
    lines = consent.read_text(encoding="utf-8").splitlines()
    i_row = next((i for i, l in enumerate(lines) if "mcp-archive_session@" in l), -1)
    i_hist = lines.index("## Історія")
    if rc != 0 or not (0 < i_row < i_hist) or lines[i_row - 1] != "| a@b | 2000-01-01 | стара прострочена згода для тесту |":
        fails.append(f"--append: рядок не в таблиці активних згод (rc={rc}, рядок {i_row}, історія {i_hist})\n{out}")
    shutil.rmtree(TMP, ignore_errors=True)
    total = 1 + len(MUTANTS) + len(EXTRA) + len(CLEAN_TOO) + 2 + 1
    for f in fails:
        print("❌", f)
    print(f"archive-ready: {total - len(fails)}/{total}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
