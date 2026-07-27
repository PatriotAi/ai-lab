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

import fnmatch
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


CONSENT = ROOT / "security" / "consent.md"


def is_self_modification(target: str, policy: dict) -> bool:
    """Чи це правка коду/конфіга самого гейта."""
    if not target:
        return False
    try:
        rel = str(Path(target).resolve().relative_to(ROOT.resolve()))
    except (ValueError, OSError):
        rel = target
    for pattern in policy.get("self_watch", {}).get("paths", []):
        if fnmatch.fnmatch(rel, pattern):
            return True
        base = pattern.rstrip("/*")
        if base and rel.startswith(base + "/"):
            return True
    return False


def active_consent(rule_id: str) -> tuple[str, str] | None:
    """Шукає ЧИННУ записану згоду для правила у `security/consent.md`.

    Повертає (до-якої-дати, причина) або None. Прострочений запис ігнорується
    мовчки — згода не має «залипати» назавжди. Порожній rule_id ніколи не
    збігається: інакше один рядок відкривав би все підряд.
    """
    if not rule_id or not CONSENT.is_file():
        return None
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        for line in CONSENT.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 3 or cells[0] != rule_id:
                continue
            until, reason = cells[1], cells[2]
            if len(until) == 10 and until >= today and len(reason) >= 20:
                return until, reason
    except OSError:
        return None
    return None


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

    # ── Аварійний вихід під запис (break-glass) ─────────────────────────────
    # НАВІЩО. Гейт без легітимного «так» не робить систему безпечнішою — він
    # робить обхід єдиним способом рухатись далі, а обхід не лишає сліду.
    # Це не теорія: 2026-07-27 гейт заблокував власного автора на зміні, яку
    # власник уже прямо схвалив, і єдиною альтернативою було тихо переписати
    # правила. Тому легітимний шлях існує — але він ІМЕННИЙ і ГУЧНИЙ.
    #
    # ЧЕСНА МЕЖА, яку треба назвати прямо: змінну оточення виставляє той самий
    # процес, що виконує дію, тож це НЕ бар'єр — це РЕЄСТРАТОР. Він перетворює
    # невидимий обхід на записаний і названий. Для лабораторії з одним власником
    # цього досить; там, де сторін кілька, перевірка має жити поза агентом.
    # Прапорець самозміни рахується ДО згоди: правка власного гейта має бути
    # видимою й тоді, коли вона дозволена — інакше найцікавіші випадки
    # (зміна політики за згодою) губилися б саме там, де важливі найбільше
    # (спіймано канаркою 2026-07-27: policy.toml виходив без прапорця).
    target_path = verdict.resolved_target or verdict.target
    self_mod = is_self_modification(target_path, policy)

    consent = active_consent(verdict.rule_id)
    if action == "deny" and consent:
        record({"tool": tool_name, "level": verdict.level, "rule": verdict.rule_id,
                "decision": "ЗГОДА-ЗАПИСАНА", "consent_until": consent[0],
                "consent_reason": consent[1], "self_modification": self_mod,
                "target": target_path[:300]})
        print(f"🔓 записана згода ({verdict.rule_id}, до {consent[0]}): {consent[1][:120]}",
              file=sys.stderr)
        return 0

    # Самозміна гейта: записуємо гучно, але не блокуємо (рішення власника).
    # Сенс не в тому, щоб зупинити — агент однаково може виписати собі згоду.
    # Сенс у тому, щоб правка власного гейта НЕ проходила тихо, як звичайна.
    record({
        "tool": tool_name,
        "level": verdict.level,
        "rule": verdict.rule_id,
        "decision": action,
        "target": target_path[:300],
        "reason": verdict.reason,
        "notes": verdict.notes,
        "self_modification": self_mod,
    })

    if self_mod and tool_name in ("Write", "Edit", "NotebookEdit"):
        print(f"🔧 САМОЗМІНА ГЕЙТА: {target_path} — записано в журнал "
              "(не блокується за рішенням власника)", file=sys.stderr)

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
