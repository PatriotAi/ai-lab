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
    "handoff":    {"path": "docs/continuation/....md", "ref": "origin/<гілка>"},  # лише origin/…
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
  A7 пакет продовження є у віддаленій гілці (`origin/…`) і називає кандидата окремим словом;
  A8 наступник працює: RUNNING/IDLE, з'єднаний, не FAILED, створений пізніше;
  A9 обидві сесії мають мітку лінії.

Запуск:  python3 scripts/check-archive-ready.py <bundle.json> [--append]
  --append — дописати рядок згоди в таблицю «Активні згоди» security/consent.md (лише при всіх ✅).
  Відсутні поля й незнайомі формати — НЕ ГОТОВА або код 2, ніколи не «готова».
Код виходу: 0 — готова (рядок надруковано); 1 — не готова; 2 — поганий вхід.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSENT = ROOT / "security" / "consent.md"
SESSION_RE = re.compile(r"^session_[A-Za-z0-9]{8,64}$")
SAFE_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
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


def _ts(v) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else None
    except ValueError:
        return None


def _branch(head) -> str:
    """`head` буває рядком гілки, міткою GitHub `owner:гілка` або об'єктом `{ref}`."""
    if isinstance(head, dict):
        head = head.get("ref", "")
    head = str(head or "")
    return head.split(":", 1)[1] if ":" in head else head


def check(b: dict, repo: Path = ROOT) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    cand, succ = b.get("candidate") or {}, b.get("successor") or {}
    cid, sid = cand.get("id", ""), succ.get("id", "")
    meta = cand.get("external_metadata") or {}

    out.append(("A1 кандидат ≠ наступник, перевіряє наступник",
                bool(SESSION_RE.match(cid)) and bool(SESSION_RE.match(sid))
                and cid.lower() != sid.lower() and b.get("self_id") == sid,
                f"кандидат={cid or '?'} наступник={sid or '?'} self={b.get('self_id') or '?'}"))

    st, bucket = cand.get("session_status"), cand.get("status_bucket")
    out.append(("A2 кандидат стоїть",
                st == "SESSION_STATUS_IDLE" and bucket == "SESSION_STATUS_BUCKET_COMPLETED"
                and cand.get("foreground_active") is False,
                f"{st} · {bucket} · foreground={cand.get('foreground_active')}"))

    out.append(("A3 немає незапушеної роботи", meta.get("unpushed_work") is False,
                f"unpushed_work={meta.get('unpushed_work')!r}"))

    trig = b.get("triggers")
    bound = [t.get("id", "?") for t in (trig if isinstance(trig, list) else [])
             if str(t.get("persistent_session_id", "")).lower() == cid.lower()
             and t.get("enabled", True) is not False]
    out.append(("A4 немає активних запланованих задач на кандидата",
                isinstance(trig, list) and not bound,
                "перелік задач не передано" if not isinstance(trig, list)
                else (", ".join(bound) or "жодної")))

    branches = set((meta.get("current_branches") or {}).values())
    for s in (cand.get("session_context") or {}).get("sources") or []:
        rev = (s.get("git_repository") or {}).get("revision")
        if rev:
            branches.add(rev)
    watches = {w.lower() for w in b.get("successor_watches") or []}
    prs = b.get("open_prs")
    orphan = [str(p.get("ref", "?")) for p in (prs if isinstance(prs, list) else [])
              if _branch(p.get("head")) in branches
              and str(p.get("ref", "")).lower() not in watches]
    ok5 = isinstance(prs, list) and bool(branches) and not orphan
    out.append(("A5 відкриті PR кандидата мають спостерігача", ok5,
                "перелік відкритих PR не передано" if not isinstance(prs, list)
                else "гілки кандидата невідомі" if not branches
                else ("без спостерігача: " + ", ".join(orphan)) if orphan
                else f"гілки {sorted(branches)} — нічого не осиротіло"))

    needs = [(src.get("post_turn_summary") or {}).get("needs_action") for src in (cand, meta)]
    evs = [e for e in (b.get("candidate_events") or []) if _kind(e)[0]]
    evs.sort(key=lambda e: e.get("created_at", ""))
    last_result = max((i for i, e in enumerate(evs) if _kind(e)[0] == "result"), default=-1)
    pending_owner = any(_kind(e)[0] == "user" and _is_owner_message(_kind(e)[1])
                        for e in evs[last_result + 1:])
    res_ok = last_result >= 0 and not (_kind(evs[last_result])[1].get("is_error")
                                       or (_kind(evs[last_result])[1].get("internal_anthropic_catchall") or {}).get("is_error"))
    last_owner = max((i for i, e in enumerate(evs)
                      if _kind(e)[0] == "user" and _is_owner_message(_kind(e)[1])), default=-1)
    last_tool = ""
    for e in evs[last_owner + 1:]:
        if _kind(e)[0] == "assistant":
            for c in _content(_kind(e)[1]):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    last_tool = c.get("name", "")
    ok6 = not any(needs) and res_ok and not pending_owner and last_tool != "AskUserQuestion"
    out.append(("A6 немає незакритого питання чи повідомлення", ok6,
                f"needs_action={[n for n in needs if n]!r} · подій={len(evs)} · останній result "
                f"{'успішний' if res_ok else 'відсутній/помилка'} · повідомлення після нього="
                f"{pending_owner} · останній виклик={last_tool or '—'}"))

    h = b.get("handoff") or {}
    text = ""
    ref, path = str(h.get("ref") or ""), str(h.get("path") or "")
    # Лише віддалена гілка (запушено, а не локальний HEAD) і безпечні символи:
    # ref на «-» git прочитав би як опцію, а `|` чи перенос зламав би рядок згоди.
    ref_ok = (ref.startswith("origin/")
              and SAFE_RE.match(ref) and SAFE_RE.match(path) and ".." not in path)
    if ref_ok:
        r = subprocess.run(["git", "-C", str(repo), "show", "--end-of-options", f"{ref}:{path}"],
                           capture_output=True, text=True)
        text = r.stdout if r.returncode == 0 else ""
    named = bool(cid) and re.search(rf"(?<![A-Za-z0-9_]){re.escape(cid)}(?![A-Za-z0-9])",
                                    text, re.IGNORECASE) is not None
    out.append(("A7 пакет продовження запушено й називає кандидата",
                bool(text) and named,
                f"{h.get('ref')}:{h.get('path')} — " + ("є" if text else "не знайдено"
                                                   if ref_ok else "ref не `origin/…` чи недопустимі символи")))

    sst = succ.get("session_status")
    out.append(("A8 наступник працює",
                sst in ("SESSION_STATUS_RUNNING", "SESSION_STATUS_IDLE")
                and succ.get("connection_status") == "connected"
                and succ.get("status_bucket") != "SESSION_STATUS_BUCKET_FAILED"
                and None not in (_ts(succ.get("created_at")), _ts(cand.get("created_at")))
                and _ts(succ.get("created_at")) > _ts(cand.get("created_at")),
                f"{sst} · {succ.get('connection_status')} · {succ.get('status_bucket')}"))

    tag = b.get("line_tag") or ""
    out.append(("A9 мітка лінії в обох",
                bool(tag) and all(isinstance(x.get("tags"), list) and tag in x["tags"] for x in (cand, succ)),
                f"«{tag}»"))
    return out


def consent_row(b: dict, n: int) -> str:
    until = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    cid, sid, path = b["candidate"]["id"], b["successor"]["id"], b["handoff"]["path"]
    # Друга лінія після A1/A7: у рядок таблиці не потрапляє нічого, що зламало б її розбір.
    if not (SESSION_RE.match(cid) and SESSION_RE.match(sid) and SAFE_RE.match(path)):
        raise ValueError("недопустимі символи в id чи шляху — рядок згоди не видається")
    return (f"| mcp-archive_session@session_id={cid.lower()} | {until} | Постійне правило "
            f"архівації попередниць (власник 2026-11-28: {OWNER_QUOTE}). Рядок видав "
            f"`scripts/check-archive-ready.py`: {n}/{n} умов виконано; наступник "
            f"{sid}, пакет `{path}`. Лише ця одна сесія. |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--consent", default=str(CONSENT), help="файл згод (для тестів)")
    ap.add_argument("--repo", default=str(ROOT), help="git-репозиторій для A7 (для тестів)")
    a = ap.parse_args()
    try:
        b = json.loads(Path(a.bundle).read_text(encoding="utf-8"))
        if not isinstance(b, dict):
            raise ValueError("пакет — не об'єкт")
    except (OSError, ValueError) as e:
        print(f"поганий вхід: {e}", file=sys.stderr)
        return 2
    try:
        res = check(b, Path(a.repo))
    except (AttributeError, TypeError, KeyError) as e:
        print(f"поганий вхід: структура пакета не та ({type(e).__name__}: {e})", file=sys.stderr)
        return 2
    for name, ok, detail in res:
        print(f"{'✅' if ok else '❌'} {name} — {detail}")
    if not all(ok for _, ok, _ in res):
        print("НЕ ГОТОВА: архівацію не виконувати.")
        return 1
    row = consent_row(b, len(res))
    print("ГОТОВА. Рядок згоди:\n" + row)
    if a.append:
        consent = Path(a.consent)
        lines = consent.read_text(encoding="utf-8").splitlines(True)
        start = next((i for i, l in enumerate(lines) if l.strip() == "## Активні згоди"), None)
        end = next((i for i, l in enumerate(lines)
                    if start is not None and i > start and l.startswith("## ")), len(lines))
        rows = [i for i in range(start + 1, end) if lines[i].startswith("|")] if start is not None else []
        if not rows:
            print("не знайдено таблиці «## Активні згоди» — рядок не дописано", file=sys.stderr)
            return 2
        lines.insert(rows[-1] + 1, row + "\n")
        consent.write_text("".join(lines), encoding="utf-8")
        print(f"дописано в таблицю «Активні згоди»: {consent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
