#!/usr/bin/env python3
"""sarif-gate.py — безпекова перевірка падає, якщо сканер знайшов серйозне.

НАВІЩО (W-38). Джоби Semgrep і Trivy у `.github/workflows/security.yml` писали
знахідки лише у звіт SARIF і завжди лишались зеленими: крок Semgrep мав
`continue-on-error: true`, Trivy — типовий `exit-code` 0. Обов'язкова перевірка
`SAST (Semgrep)` за побудовою не могла впасти на знахідці — зелена галочка без
перевірки (той самий клас, що F-6 у `dependencies.yml`).

ЩО ПЕРЕВІРЯЄТЬСЯ. У звіті SARIF рахуються результати рівня `error`: рівень
береться з самого результату, а якщо його нема — з `defaultConfiguration` правила
(за стандартом SARIF типово `warning`). Semgrep дає `error` правилам рівня ERROR,
Trivy — знахідкам HIGH і CRITICAL. `warning` і `note` не валять перевірку, лише
лишаються у звіті й code scanning.

«НЕ ПЕРЕВІРЯЛИ» ≠ «ЧИСТО». Нема файла, не JSON чи нема `runs` — код 2: сканер не
відпрацював, і мовчати про це не можна.

Запуск:
    python3 scripts/sarif-gate.py <звіт.sarif> [ще.sarif ...]
Код виходу: 0 — серйозних знахідок нема · 1 — є · 2 — звіт не прочитати.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def error_results(report: dict) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for run in report["runs"]:
        driver = run.get("tool", {}).get("driver", {})
        tool = driver.get("name", "?")
        defaults = {
            rule.get("id"): rule.get("defaultConfiguration", {}).get("level", "warning")
            for rule in driver.get("rules", []) or []
        }
        for result in run.get("results", []) or []:
            level = result.get("level") or defaults.get(result.get("ruleId"), "warning")
            if level == "error":
                found.append((tool, result.get("ruleId", "?")))
    return found


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("помилка: вкажи хоча б один звіт SARIF", file=sys.stderr)
        return 2
    total: list[tuple[str, str]] = []
    for name in argv[1:]:
        try:
            report = json.loads(Path(name).read_text(encoding="utf-8"))
            if not isinstance(report.get("runs"), list):
                raise ValueError("нема списку runs")
            found = error_results(report)
        except (OSError, ValueError, KeyError, AttributeError) as exc:
            print(f"помилка: звіт {name} не прочитати ({exc}) — сканер не відпрацював, це не «чисто»", file=sys.stderr)
            return 2
        print(f"{name}: серйозних знахідок (рівень error) — {len(found)}")
        for tool, rule in found[:20]:
            print(f"  ✗ {tool}: {rule}")
        total += found
    if total:
        print(f"❌ серйозних знахідок: {len(total)} — деталі у вкладці Security (code scanning)")
        return 1
    print("✅ серйозних знахідок нема")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
