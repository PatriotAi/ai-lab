#!/usr/bin/env python3
"""R1/R1b: стискає сирий JSON `claude plugin eval --json` у `runs/<назва>.json` і друкує таблицю.

Стиснутий формат — як у `runs/cheap-class.json`: на прогін лише ходи, вартість, помилка й
«оцінювач → пройдено». Сирий JSON (з трасами в /tmp) у репо не кладемо.

Запуск: python3 summarize_runs.py <сирий.json> [<назва для runs/>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def condense(raw: dict) -> dict:
    # `--model` пише перевизначення в `suite.modelOverride`; поле `model` кейсу — із frontmatter.
    override = (raw.get("suite") or {}).get("modelOverride")
    cases = []
    for c in raw["cases"]:
        arms = {}
        for arm, runs in c.get("arms", {}).items():
            arms[arm] = [{"turns": r.get("turns"), "costUsd": r.get("costUsd"), "error": r.get("error"),
                          "graders": {g["name"]: g["passed"] for g in r.get("graders", [])}}
                         for r in runs]
        cases.append({"name": c["name"], "model": override or c.get("model"),
                      "delta": (c.get("aggregates") or {}).get("delta"), "arms": arms})
    return {"claudeVersion": raw.get("claudeVersion"), "costUsd": raw.get("costUsd"),
            "partial": raw.get("partial"), "aggregates": raw.get("aggregates"), "cases": cases}


def count(runs: list[dict], grader: str) -> str:
    vals = [r["graders"][grader] for r in runs if grader in r["graders"]]
    return f"{sum(vals)}/{len(vals)}" if vals else "—"


def main(argv: list[str]) -> int:
    data = condense(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
    if len(argv) > 2:
        out = HERE / "runs" / f"{argv[2]}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"записано {out.relative_to(HERE)}")
    print(f"claude {data['claudeVersion']} · вартість ${data['costUsd'] or 0:.2f}"
          + (" · ЧАСТКОВИЙ" if data.get("partial") else ""))
    print(f"{'кейс':12} {'клас':7} {'обрано':7} {'не-обрано':10} {'результат з':12} {'без':5} Δ")
    for c in data["cases"]:
        w, wo = c["arms"].get("with", []), c["arms"].get("without", [])
        errs = sum(1 for r in w + wo if r.get("error"))
        print(f"{c['name']:12} {c['model'] or '':7} {count(w, 'skill-fired'):7} {count(w, 'no-skill'):10} "
              f"{count(w, 'result'):12} {count(wo, 'result'):5} {c['delta']}"
              + (f"  помилок: {errs}" if errs else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
