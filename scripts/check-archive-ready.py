#!/usr/bin/env python3
"""check-archive-ready.py — машинна перевірка готовності сесії-попередниці до архівації.

НАВІЩО. Власник 2026-11-28 дозволив архівувати попередниць лінії автономно,
«дотримуючись усіх правил». Слова «усіх правил» читає людина, а не код: без
перевірки модель архівувала б «на око», і помилка (недоставлене повідомлення,
PR без спостерігача, питання власнику без відповіді) зникала б разом із сесією.
Цей скрипт перетворює правила на перелік умов; лише коли ВСІ виконані, він видає
рядок згоди для `security/consent.md` під ОДНУ сесію (гейт звіряє ціль точно:
`mcp-archive_session@session_id=<id>`). Сама архівація — окремий крок моделі.

ВХІД — JSON-пакет, зібраний моделлю з MCP-результатів дослівно (скрипт нічого не
викликає в мережі; git — лише читання):
  {
    "self_id":    "<id сесії, що запускає перевірку>",
    "candidate":  <get_session(candidate).ccr>,
    "successor":  <get_session(без id).ccr>,        # наступник = та, що перевіряє
    "candidate_events": [<події list_events(candidate, kinds=[user,result,assistant])>],
    "triggers":   [<записи list_triggers>],
    "open_prs":   [{"ref": "owner/repo#N", "head": "<гілка>"}],   # відкриті PR репо
    "successor_watches": ["owner/repo#N", ...],     # PR, на які підписано наступника
    "handoff":    {"path": "docs/continuation/....md", "ref": "origin/<гілка>"},
    "line_tag":   "harness-research"
  }

УМОВИ (кожна — окремий рядок звіту):
  A1 кандидат ≠ наступник, і перевіряє сам наступник;
  A2 кандидат стоїть: IDLE, кошик COMPLETED, без активного foreground;
  A3 немає незапушеної роботи (`unpushed_work: false`);
  A4 немає увімкнених запланованих задач, прив'язаних до кандидата;
  A5 кожен відкритий PR з гілок кандидата має спостерігача-наступника;
  A6 немає незакритого питання: `needs_action` порожній, остання подія — успішний
     `result` (не повідомлення без відповіді), останній виклик — не AskUserQuestion;
  A7 пакет продовження закомічено у вказаному ref і він називає кандидата;
  A8 наступник працює: RUNNING/IDLE, з'єднаний, не FAILED, створений пізніше;
  A9 обидві сесії мають мітку лінії.

Запуск:  python3 scripts/check-archive-ready.py <bundle.json> [--append]
  --append — дописати рядок згоди в security/consent.md (лише при всіх ✅).
Код виходу: 0 — готова (рядок надруковано); 1 — не готова; 2 — поганий вхід.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSENT = ROOT / "security" / "consent.md"
OWNER_QUOTE = "«Архівувати автономно дотримуючись усіх правил»"


def _kind(ev: dict) -> tuple[str, dict]:
    for k in ("result", "user", "assistant"):
        if isinstance(ev.get(k), dict):
            return k, ev[k]
    return "", {}


def _content(body: dict) -> list:
    msg = (body.get("internal_anthropic_catchall") or {}).get("message") or body.get("message") or {}
    c = msg.get("content") if isinstance(msg, dict) else None
    return c if isinstance(c, list) else []


def _is_owner_message(body: dict) -> bool:
    """Повідомлення людини, а не tool_result і не системне сповіщення."""
    for c in _content(body):
        if isinstance(c, dict) and c.get("type") == "tool_result":
            return False
    if (body.get("internal_anthropic_catchall") or {}).get("isSynthetic") or body.get("isSynthetic"):
        return False
    return True


def check(b: dict) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    cand, succ = b.get("candidate") or {}, b.get("successor") or {}
    cid, sid = cand.get("id", ""), succ.get("id", "")
    meta = cand.get("external_metadata") or {}

    out.append(("A1 кандидат ≠ наступник, перевіряє наступник",
                bool(cid) and bool(sid) and cid != sid and b.get("self_id") == sid,
                f"кандидат={cid or '?'} наступник={sid or '?'} self={b.get('self_id') or '?'}"))

    st, bucket = cand.get("session_status"), cand.get("status_bucket")
    out.append(("A2 кандидат стоїть",
                st == "SESSION_STATUS_IDLE" and bucket == "SESSION_STATUS_BUCKET_COMPLETED"
                and not cand.get("foreground_active"),
                f"{st} · {bucket} · foreground={cand.get('foreground_active')}"))

    out.append(("A3 немає незапушеної роботи", meta.get("unpushed_work") is False,
                f"unpushed_work={meta.get('unpushed_work')!r}"))

    bound = [t.get("id", "?") for t in (b.get("triggers") or [])
             if t.get("persistent_session_id") == cid and t.get("enabled")]
    out.append(("A4 немає активних запланованих задач на кандидата", not bound,
                ", ".join(bound) or "жодної"))

    branches = set((meta.get("current_branches") or {}).values())
    for s in (cand.get("session_context") or {}).get("sources") or []:
        rev = (s.get("git_repository") or {}).get("revision")
        if rev:
            branches.add(rev)
    watches = {w.lower() for w in b.get("successor_watches") or []}
    orphan = [p["ref"] for p in b.get("open_prs") or []
              if p.get("head") in branches and p.get("ref", "").lower() not in watches]
    out.append(("A5 відкриті PR кандидата мають спостерігача", not orphan,
                ("без спостерігача: " + ", ".join(orphan)) if orphan
                else f"гілки {sorted(branches)} — нічого не осиротіло"))

    pts = cand.get("post_turn_summary") or meta.get("post_turn_summary") or {}
    evs = [e for e in (b.get("candidate_events") or []) if _kind(e)[0]]
    evs.sort(key=lambda e: e.get("created_at", ""))
    last_result = max((i for i, e in enumerate(evs) if _kind(e)[0] == "result"), default=-1)
    pending_owner = any(_kind(e)[0] == "user" and _is_owner_message(_kind(e)[1])
                        for e in evs[last_result + 1:])
    res_ok = last_result >= 0 and not (_kind(evs[last_result])[1].get("is_error")
                                       or (_kind(evs[last_result])[1].get("internal_anthropic_catchall") or {}).get("is_error"))
    last_tool = ""
    for e in evs:
        if _kind(e)[0] == "assistant":
            for c in _content(_kind(e)[1]):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    last_tool = c.get("name", "")
    ok6 = (not pts.get("needs_action")) and res_ok and not pending_owner and last_tool != "AskUserQuestion"
    out.append(("A6 немає незакритого питання чи повідомлення", ok6,
                f"needs_action={pts.get('needs_action')!r} · подій={len(evs)} · останній result "
                f"{'успішний' if res_ok else 'відсутній/помилка'} · повідомлення після нього="
                f"{pending_owner} · останній виклик={last_tool or '—'}"))

    h = b.get("handoff") or {}
    text = ""
    if h.get("path") and h.get("ref"):
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{h['ref']}:{h['path']}"],
                           capture_output=True, text=True)
        text = r.stdout if r.returncode == 0 else ""
    out.append(("A7 пакет продовження закомічено й називає кандидата",
                bool(text) and bool(cid) and cid in text,
                f"{h.get('ref')}:{h.get('path')} — " + ("є" if text else "не знайдено")))

    sst = succ.get("session_status")
    out.append(("A8 наступник працює",
                sst in ("SESSION_STATUS_RUNNING", "SESSION_STATUS_IDLE")
                and succ.get("connection_status") == "connected"
                and succ.get("status_bucket") != "SESSION_STATUS_BUCKET_FAILED"
                and succ.get("created_at", "") > cand.get("created_at", "~"),
                f"{sst} · {succ.get('connection_status')} · {succ.get('status_bucket')}"))

    tag = b.get("line_tag") or ""
    out.append(("A9 мітка лінії в обох",
                bool(tag) and tag in (cand.get("tags") or []) and tag in (succ.get("tags") or []),
                f"«{tag}»"))
    return out


def consent_row(b: dict, n: int) -> str:
    until = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    cid = b["candidate"]["id"]
    return (f"| mcp-archive_session@session_id={cid.lower()} | {until} | Постійне правило "
            f"архівації попередниць (власник 2026-11-28: {OWNER_QUOTE}). Рядок видав "
            f"`scripts/check-archive-ready.py`: {n}/{n} умов виконано; наступник "
            f"{b['successor']['id']}, пакет `{b['handoff']['path']}`. Лише ця одна сесія. |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("--append", action="store_true")
    a = ap.parse_args()
    try:
        b = json.loads(Path(a.bundle).read_text(encoding="utf-8"))
        if not isinstance(b, dict):
            raise ValueError("пакет — не об'єкт")
    except (OSError, ValueError) as e:
        print(f"поганий вхід: {e}", file=sys.stderr)
        return 2
    res = check(b)
    for name, ok, detail in res:
        print(f"{'✅' if ok else '❌'} {name} — {detail}")
    if not all(ok for _, ok, _ in res):
        print("НЕ ГОТОВА: архівацію не виконувати.")
        return 1
    row = consent_row(b, len(res))
    print("ГОТОВА. Рядок згоди:\n" + row)
    if a.append:
        text = CONSENT.read_text(encoding="utf-8").rstrip("\n") + "\n" + row + "\n"
        CONSENT.write_text(text, encoding="utf-8")
        print(f"дописано в {CONSENT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
