#!/usr/bin/env python3
"""pretooluse.py — механічний гейт дій агента (закриває F-3).

Єдина відповідальність: перед кожним викликом інструмента визначити рівень
ризику й зупинити те, що за правилами лабораторії не робиться без свіжої згоди
власника (`docs/external-proposals-protocol.md` §5).

ЧОМУ ЦЕ ПОТРІБНО. До цієї зміни в лабораторії не було жодного
`PreToolUse`-хука: усі безпекові правила виконувались лише тому, що агент їх
пам'ятає. Це рівно той клас проблеми, який лабораторія вже назвала сама —
Core Rule 15: «крок, що тримається на уважності й звітується словами, рано чи
пізно буде пропущений, і звіт лишиться чесним». Гейт не замінює правила — він
дає їм машинну опору.

КОНТРАКТ (офіційна документація Claude Code).
На stdin приходить JSON із `tool_name` і `tool_input`. Щоб заблокувати виклик,
повертаємо на stdout JSON із `hookSpecificOutput.permissionDecision = "deny"`
та полем `permissionDecisionReason`; код виходу при цьому має бути 0.
Рішення хука НЕ обходять правила дозволів із `settings.json` — вони працюють
разом, а не замість.

ПОВЕДІНКА ПРИ ВЛАСНІЙ ПОЛОМЦІ. Якщо гейт сам зламався, він не мовчить і не
пропускає: повертає `ask`. Пропустити через поломку означало б, що гейт тим
надійніший, чим гірше працює.

ЧЕСНА МЕЖА. Гейт ловить ПЕРЕЛІЧЕНІ форми небезпечних дій. Інакше сформульована
дія його обійде — так само, як скан ін'єкції є тріажем, а не бар'єром. Він
піднімає підлогу; стелю ставлять правила й згода власника.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classify import classify, load_policy, repo_root  # noqa: E402
import explain  # noqa: E402

ROOT = repo_root()
AUDIT = ROOT / "security" / "audit" / "decisions.jsonl"


def record(entry: dict) -> None:
    """Журнал рішень — лише дописування. Поломка журналу не спиняє роботу."""
    try:
        AUDIT.parent.mkdir(parents=True, exist_ok=True)
        entry["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with AUDIT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def emit(decision: str, reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    if not tool_name:
        return 0                       # нема що класифікувати — не заважаємо

    try:
        policy = load_policy(ROOT)
        verdict = classify(tool_name, tool_input, ROOT, policy)
    except Exception as exc:           # noqa: BLE001 — поломка гейта ≠ дозвіл
        fallback = str(load_safe_behaviour())
        record({"tool": tool_name, "level": "?", "decision": fallback,
                "reason": f"гейт зламався: {exc}"})
        emit(fallback, (
            "Безпековий гейт не зміг оцінити цю дію через власну помилку "
            f"({exc}). Він не пропускає дію мовчки: підтвердь її свідомо або "
            "скажи мені зупинитись."
        ))
        return 0

    behaviour = policy.get("behaviour", {})
    action = behaviour.get("on_R4", "deny") if verdict.level == "R4" else "allow"

    record({
        "tool": tool_name,
        "level": verdict.level,
        "rule": verdict.rule_id,
        "decision": action,
        "target": (verdict.resolved_target or verdict.target)[:300],
        "reason": verdict.reason,
        "notes": verdict.notes,
    })

    if action == "allow":
        # Тиша = не втручаємось. Жодного зайвого токена в контекст.
        return 0

    message = explain.render(verdict, tool_name, action)
    if action == "warn":
        print(message, file=sys.stderr)
        return 0
    emit(action, message)
    return 0


def load_safe_behaviour() -> str:
    try:
        return load_policy(ROOT).get("behaviour", {}).get("on_internal_error", "ask")
    except Exception:                  # noqa: BLE001
        return "ask"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:           # noqa: BLE001 — остання лінія: не пропускати мовчки
        emit("ask", (
            "Безпековий гейт аварійно завершився "
            f"({type(exc).__name__}: {exc}). Дію не оцінено — підтвердь її свідомо."
        ))
        raise SystemExit(0)
