#!/usr/bin/env python3
"""native-instructions.py — корпус НАТИВНИХ інструкцій робочого харнесу (B2).

Єдина відповідальність: відповісти на питання «що виконавцю сказано БЕЗ нас» —
самостійно, без мережі й без поданих ззовні статей.

НАВІЩО. Правила лабораторії конкурують із тим, що харнес уже говорить моделі.
Щоб не дублювати, треба бачити нативний текст. Подавати його вручну (статтею,
скріншотом, посиланням) не масштабується: моделі й версії харнесу змінюються
постійно. Бінарник, що зараз виконується, — джерело, яке оновлюється саме.

ЩО ЦЕЙ СКРИПТ РОБИТЬ І ЧОГО НЕ РОБИТЬ
    Робить:   витягує нативні інструкції, нормалізує, робить знімок за версією
              харнесу і показує ДЕЛЬТУ між знімками.
    НЕ робить: не оголошує наші правила дублікатами й нічого не пропонує видалити.

ЧОМУ САМЕ ДЕЛЬТА, А НЕ АВТОМАТИЧНИЙ ПОШУК ДУБЛІВ (звірено 2026-07-27):
нативний корпус — англійський і перемішаний із рядками UI та описами
інструментів, а наші правила — українські. Лексичне зіставлення між мовами дає
або нуль збігів, або випадковий шум; «схоже за словами» й «те саме за змістом» —
різні речі, а протилежні за полярністю фрази («always write comments» /
«never write comments») лексично майже тотожні. Тому семантичне зіставлення
робиться ОДИН раз людиною або моделлю і зберігається; далі щоразу переглядається
лише те, що ЗМІНИЛОСЬ у нативному корпусі. Дельта мала — рев'ю дешеве.

Запуск:
    python3 scripts/native-instructions.py --snapshot out.json   # знімок
    python3 scripts/native-instructions.py --diff old.json       # що змінилось
    python3 scripts/native-instructions.py --stats               # огляд
    python3 scripts/native-instructions.py --validate            # самотест

Код виходу: 0 — успіх (для --diff: змін нема) · 1 — харнес не впізнано,
самотест упав, або --diff знайшов зміни · 2 — помилка виклику.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _load_capability_scan():
    """Переуживаємо пошук харнесу з capability-scan.py — та сама перевірка
    «дивимось на те, що ВИКОНУЄТЬСЯ», а не на випадкову копію на диску."""
    spec = importlib.util.spec_from_file_location("cs", HERE / "capability-scan.py")
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Маркери інструкції, адресованої МОДЕЛІ (а не користувачу інтерфейсу).
RULE_RE = re.compile(
    r"(IMPORTANT|CRITICAL|NEVER|ALWAYS|Do NOT|DO NOT|You MUST|You should|Never |Always |Avoid )"
    r"[A-Za-z0-9 ,;:'\"()./`\-]{25,200}"
)

# Рядки з коду/UI, що випадково проходять маркер. Фільтр евристичний — тому
# скрипт завжди друкує і сирий, і відфільтрований лічильник: «порожньо» і
# «відфільтровано» виглядають однаково, і плутати їх не можна (Core Rule 15).
NOISE_RE = re.compile(
    r"(:\(\)=>|value:|description:\"|\",|\{|\}|=>|__|\bprops\b|\bconst\b|\blet\b)"
)


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip().rstrip(".,;:")
    return text


def extract(binary: str) -> dict:
    """Один прохід по бінарнику. Повертає сирі й відфільтровані інструкції."""
    try:
        proc = subprocess.run(["grep", "-aoE", RULE_RE.pattern, binary],
                              capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return {"raw": [], "rules": [], "dropped": 0}

    raw = sorted({normalize(line) for line in proc.stdout.splitlines() if line.strip()})
    rules = [r for r in raw if not NOISE_RE.search(r)]
    return {"raw": raw, "rules": rules, "dropped": len(raw) - len(rules)}


def snapshot(model: str | None = None) -> dict:
    cs = _load_capability_scan()
    harness = cs.find_harness(dict(__import__("os").environ)) if cs else {"trusted": False}

    if not harness.get("trusted"):
        # Невпізнаний харнес — знімок робити НЕ можна: він зафіксував би
        # інструкції не тієї збірки і тихо став би хибним еталоном.
        return {"harness": harness, "trusted": False, "rules": [], "raw_count": 0,
                "dropped": 0, "corpus_sha": None,
                "note": "харнес не впізнано — знімок не робиться (fail-closed)"}

    data = extract(harness["path"])
    corpus = "\n".join(data["rules"])
    return {
        "harness": harness,
        "trusted": True,
        "model": model or "unknown",
        "raw_count": len(data["raw"]),
        "dropped": data["dropped"],
        "rules": data["rules"],
        "corpus_sha": hashlib.sha256(corpus.encode()).hexdigest()[:16],
    }


def diff(old: dict, new: dict) -> dict:
    old_set, new_set = set(old.get("rules") or []), set(new.get("rules") or [])
    return {
        "added": sorted(new_set - old_set),
        "removed": sorted(old_set - new_set),
        "old_version": (old.get("harness") or {}).get("version_running"),
        "new_version": (new.get("harness") or {}).get("version_running"),
    }


def render_diff(d: dict) -> str:
    lines = [f"# Зміни нативних інструкцій: "
             f"`{d['old_version'] or '?'}` → `{d['new_version'] or '?'}`", ""]
    if not d["added"] and not d["removed"]:
        lines.append("Змін нема — рев'ю не потрібне.")
        return "\n".join(lines)
    lines.append(f"**Додано {len(d['added'])} · прибрано {len(d['removed'])}.** "
                 "Переглянути треба лише це, а не весь корпус.")
    for title, items in (("Додано", d["added"]), ("Прибрано", d["removed"])):
        if not items:
            continue
        lines += ["", f"## {title}", ""]
        lines += [f"- {i}" for i in items[:40]]
        if len(items) > 40:
            lines.append(f"- …та ще {len(items) - 40}")
    lines += ["", "> Це зміни в тому, що харнес говорить моделі САМ. Збіг із нашим "
              "правилом за змістом визначає рев'ю, не цей скрипт: лексична "
              "подібність не доводить тотожності, а протилежні за полярністю "
              "фрази виглядають майже однаково."]
    return "\n".join(lines)


def validate() -> int:
    failures: list[str] = []
    skipped: list[str] = []

    def check(name, expected, actual):
        if expected == actual:
            print(f"  ✅ {name}")
        else:
            failures.append(name)
            print(f"  ❌ {name}\n     очікували: {expected}\n     отримали:  {actual}")

    def skip(name, why):
        """Гучний, іменований, порахований пропуск — див. пояснення в
        capability-scan.py. «Не змогли перевірити» ≠ «перевірили й добре»."""
        skipped.append(name)
        print(f"  ⏭️  {name} — ПРОПУЩЕНО: {why}")

    print("native-instructions самотест:")

    # 1. Шумовий фільтр мусить різати саме код/UI, а не інструкції.
    check("рядок коду відсіюється", True,
          bool(NOISE_RE.search('Always copy full response",value:"always"')))
    check("справжня інструкція лишається", False,
          bool(NOISE_RE.search("IMPORTANT: Keep PR titles short (under 70 characters)")))

    # 2. Дельта: однакові корпуси → тиша; різні → названі саме зміни.
    a = {"rules": ["A", "B"], "harness": {"version_running": "1"}}
    b = {"rules": ["A", "B"], "harness": {"version_running": "1"}}
    d = diff(a, b)
    check("однакові корпуси не дають змін", ([], []), (d["added"], d["removed"]))
    c = {"rules": ["A", "C"], "harness": {"version_running": "2"}}
    d2 = diff(a, c)
    check("дельта називає додане", ["C"], d2["added"])
    check("дельта називає прибране", ["B"], d2["removed"])

    # 3. НАЙВАЖЛИВІШЕ (canary C8): скрипт не має жодного стану «це дубль нашого
    #    правила». Протилежні за полярністю фрази лексично майже тотожні —
    #    автоматичне рішення тут неминуче було б хибним.
    text = render_diff(diff({"rules": ["Never write comments"],
                             "harness": {"version_running": "1"}},
                            {"rules": ["Always write comments"],
                             "harness": {"version_running": "2"}}))
    check("дельта не оголошує дублів", True,
          "рев'ю" in text and "дубл" not in text.lower().replace("дубль", "дубл"))
    check("обидві полярності показані окремо", True,
          "Never write comments" in text and "Always write comments" in text)

    # 4. Невпізнаний харнес → знімок не робиться (той самий fail-closed, що в
    #    capability-scan: хибний еталон гірший за відсутній).
    import os
    saved = os.environ.get("PATH", "")
    os.environ["PATH"] = "/nonexistent"
    try:
        snap = snapshot(model="x")
    finally:
        os.environ["PATH"] = saved
    check("невпізнаний харнес → знімок порожній", (False, []),
          (snap["trusted"], snap["rules"]))

    # 5. Живий прогін: корпус має бути непорожнім, а лічильники — чесними
    #    (сирий ≥ відфільтрований, інакше фільтр рахує не те).
    #    Ці три читають РЕАЛЬНИЙ бінарник. На раннері CI його немає, тому там
    #    вони неперевірні, а не хибні — пропускаємо гучно. Уся логіка вище
    #    (фільтр, дельта, полярність, fail-closed) від харнесу не залежить.
    live = snapshot(model="claude-opus-5")
    if live["trusted"]:
        check("живий корпус непорожній", True, len(live["rules"]) > 50)
        check("сирий лічильник не менший за відфільтрований", True,
              live["raw_count"] >= len(live["rules"]))
        check("корпус має хеш", True, bool(live["corpus_sha"]))
    else:
        for name in ("живий корпус непорожній",
                     "сирий лічильник не менший за відфільтрований",
                     "корпус має хеш"):
            skip(name, "харнес недоступний")

    print()
    if skipped:
        print(f"⏭️  Пропущено {len(skipped)} (харнес недоступний): {', '.join(skipped)}")
    if failures:
        print(f"❌ Самотест упав: {len(failures)} перевірок — {', '.join(failures)}")
        return 1
    print(f"✅ Самотест: перевірки пройшли"
          f"{f' ({len(skipped)} пропущено)' if skipped else ''}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Корпус нативних інструкцій харнесу")
    ap.add_argument("--snapshot", metavar="OUT.json", help="зберегти знімок корпусу")
    ap.add_argument("--diff", metavar="OLD.json", help="показати зміни щодо знімка")
    ap.add_argument("--stats", action="store_true", help="огляд корпусу")
    ap.add_argument("--model", help="ID моделі для запису у знімок")
    ap.add_argument("--validate", action="store_true", help="самотест")
    args = ap.parse_args()

    if args.validate:
        return validate()

    snap = snapshot(args.model)
    if not snap["trusted"]:
        print(f"Харнес не впізнано — знімок не робиться. {snap.get('note','')}",
              file=sys.stderr)
        return 1

    if args.diff:
        try:
            old = json.loads(pathlib.Path(args.diff).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Не вдалося прочитати знімок: {exc}", file=sys.stderr)
            return 2
        d = diff(old, snap)
        print(render_diff(d))
        return 1 if (d["added"] or d["removed"]) else 0

    if args.snapshot:
        # Завершальний перевід рядка обов'язковий: `end-of-file-fixer` у
        # pre-commit інакше валить CI на згенерованому знімку.
        pathlib.Path(args.snapshot).write_text(
            json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Знімок збережено: {args.snapshot} "
              f"({len(snap['rules'])} інструкцій, sha {snap['corpus_sha']})")
        return 0

    h = snap["harness"]
    print(f"# Нативні інструкції харнесу `{h.get('version_running')}`\n")
    print(f"- Інструкцій після фільтра: **{len(snap['rules'])}**")
    print(f"- Сирих збігів: {snap['raw_count']} · відсіяно як код/UI: {snap['dropped']}")
    print(f"- Хеш корпусу: `{snap['corpus_sha']}`\n")
    print("> Лічильники подані обидва навмисне: «мало інструкцій» і «багато "
          "відсіяно фільтром» виглядають однаково, а це різні речі.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
