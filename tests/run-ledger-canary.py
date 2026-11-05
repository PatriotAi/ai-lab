#!/usr/bin/env python3
"""Canary для scripts/run-ledger.py: кожна перевірка — на ЗЛАМАНОМУ стані (має спіймати)
і на чистому (має мовчати), CLAUDE.md §11. Друкує по рядку на випадок, код 1 при провалі."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "scripts" / "run-ledger.py"
T0 = "2026-11-05T10:00:00+00:00"
fails = 0


def run(*args, at=T0):
    return subprocess.run([sys.executable, "-I", str(LEDGER), *args, "--now", at],
                          capture_output=True, text=True).returncode


def expect(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(f"{'✅' if ok else '❌'} {name}: {got} (очікувано {want})")


with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp) / "ledger.json"
    expect("init", run("init", str(f), "--goal", "g", "--max-iter", "2"), 0)
    expect("init повторно — відмова", run("init", str(f)), 2)
    expect("claim A", run("claim", str(f), "t1", "--by", "A"), 0)
    expect("claim B на зайняту — дубль ловиться", run("claim", str(f), "t1", "--by", "B"), 1)
    expect("done без ітерацій — відмова", run("done", str(f), "t1", "--evidence", "x"), 1)
    run("log", str(f), "t1", "--status", "fail", "--note", "1")
    expect("done після fail — відмова", run("done", str(f), "t1", "--evidence", "x"), 1)
    run("log", str(f), "t1", "--status", "pass")
    expect("done без доказу — відмова", run("done", str(f), "t1"), 1)
    expect("done після pass з доказом", run("done", str(f), "t1", "--evidence", "tests ok"), 0)
    expect("чистий реєстр — check мовчить", run("check", str(f)), 0)
    # зламані стани, яких CLI не дає зробити, але може дати ручна правка файла
    d = json.loads(f.read_text())
    d["tasks"]["t1"]["iterations"].append({"at": T0, "status": "fail", "note": "після done"})
    f.write_text(json.dumps(d))
    expect("ручна правка: готово, але остання fail — check ловить", run("check", str(f)), 1)
    d["tasks"]["t1"]["iterations"].pop()
    f.write_text(json.dumps(d))
    run("claim", str(f), "t2", "--by", "C")
    run("log", str(f), "t2", "--status", "fail")
    expect("1 провал < бюджету 2 — мовчить", run("check", str(f)), 0)
    run("log", str(f), "t2", "--status", "fail")
    expect("2 провали поспіль = бюджет — check ловить", run("check", str(f)), 1)
    run("log", str(f), "t2", "--status", "pass")
    expect("після pass — мовчить", run("check", str(f)), 0)
    expect("прострочений lease — check ловить", run("check", str(f), at="2026-11-05T20:00:00+00:00"), 1)
    expect("прострочений lease можна перехопити", run("claim", str(f), "t2", "--by", "D",
                                                       at="2026-11-05T20:00:00+00:00"), 0)

print(f"run-ledger canary: {'усе гаразд' if not fails else f'{fails} провал(ів)'}")
sys.exit(1 if fails else 0)
