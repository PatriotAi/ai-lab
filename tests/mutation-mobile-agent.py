#!/usr/bin/env python3
"""mutation-mobile-agent.py — гейт для гейта резервного контуру (projects/mobile-agent).

ПИТАННЯ, НА ЯКЕ ВІН ВІДПОВІДАЄ. Набір тестів контуру зелений — але чи ловить він
ХОЧ ЩО-НЕБУДЬ? Зелений набір на цілому коді не доводить нічого: єдиний спосіб дізнатись —
зламати код навмисно й побачити, чи набір це помітить. Мутант, що ПРОЙШОВ перевірки, —
це діра в перевірках, а не в коді.

Чому окремо від tests/mutation-classify.py: той мутує security/spine/classify.py (Python),
а контур — це JS (core.js + app.html). Ідея та сама, мова інша.

Два рівні (різна ціна, різне питання):
  ядро     мутанти core.js → юніт-тести (секунди). Чи тримається ЛОГІКА диспетчера.
  браузер  мутанти app.html → реальний Chromium (хвилини, потрібен playwright).
           Чи тримається ПРОВОДКА, яку юніт-тести не бачать: новий Notification(...),
           pruneQueue перед збереженням, пробудження на старті. Перший прогін контуру
           показав, що саме там ховаються дефекти, які проходять усі юніт-тести.

ЧЕСНІСТЬ ПРОГОНУ (два запобіжники, яких бракувало першому, одноразовому прогону):
  1. БАЗА. Спершу ганяємо НЕмутований код: якщо він не проходить, «спіймано» означало б
     «усе зламано», а не «перевірки кусаються».
  2. «НЕ ГАНЯЛОСЬ» ≠ «ПРОЙШЛО». Браузерний набір без playwright виходить з кодом 0 і
     друкує skipped=1 — без цього розрізнення кожен мутант «вижив би» або, гірше,
     «був би спійманий» через порожній прогін.
Якір, що зсунувся (після рефакторингу зустрічається не рівно раз), — теж провал: мутант,
який не застосувався, виглядав би як мутант, що вижив, або як «спійманий».

БЕЗПЕКА ПРОГОНУ. Мутації застосовуються ТІЛЬКИ до копії у тимчасовій теці, яку Python
сам прибирає. Робочі файли не чіпаються ніколи (правило tests/README.md: канарка на
робочому файлі колись стерла незакомічену роботу).

Запуск:
  python3 tests/mutation-mobile-agent.py                   # ядро (юніт) + якорі app.html
  python3 tests/mutation-mobile-agent.py --check-anchors   # лише якорі, без виконання
  python3 tests/mutation-mobile-agent.py --browser         # + мутанти app.html у браузері
Код виходу: 0 — усе спіймано · 1 — мутант вижив / якір зсунувся / база не зелена ·
            2 — середовище не дозволяє (нема node; для --browser — нема playwright).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJ = "projects/mobile-agent"

# (назва, файл відносно проєкту, що замінити, на що, яку перевірку це має розбудити)
# Кожен мутант — правдоподібна помилка, а не випадковий шум.
CORE = "src/core.js"
APP = "src/app.html"
Mutant = tuple[str, str, str, str, str]

CORE_MUTANTS: list[Mutant] = [
    ("бекоф без джитера", CORE,
     "return Math.round(exp / 2 + rand() * (exp / 2));", "return exp;",
     "усі клієнти повертаються одночасно й кладуть провайдера вдруге"),
    ("429 визнано фатальним", CORE,
     'return { kind: "rate-limit", retryable: true, switchProvider: true, retryAfterMs };',
     'return { kind: "rate-limit", retryable: false, switchProvider: false, retryAfterMs };',
     "ліміт провайдера більше не повторюється й не веде на запасний вузол"),
    ("Retry-After ігнорується", CORE,
     "if (o.retryAfterMs !== null && o.retryAfterMs !== undefined) {", "if (false) {",
     "пауза перестає слухатись провайдера"),
    ("вичерпані спроби зникають як done", CORE,
     'return { ...t, status: "failed", attempts, tried, lastError: outcome.error || f.kind, finishedAt: now };',
     'return { ...t, status: "done", attempts, tried, finishedAt: now };',
     "невдале завдання тихо зникає замість видимого failed із ручним повтором"),
    ("повтор без паузи", CORE,
     "nextAttemptAt: now + pause };", "nextAttemptAt: now };",
     "нескінченний цикл спроб без інтервалу"),
    ("cooldown вузла не діє", CORE,
     "if (until > now) { cooling.push(until); continue; }", "",
     "провайдера б'ють без перерви, поки він на паузі"),
    ("офлайн «з'їдає» завдання після першого збою проходу", CORE,
     'return o.lastChance === true ? { action: "run", node: offlineNode } : { action: "exhausted" };',
     'return { action: "run", node: offlineNode };',
     "повернення дефекту 2026-09-28: затримка знову стає втратою відповіді"),
    ("замкнений ключ ігнорується", CORE,
     "if (!has) { if (locked && wantsCloud) lockedBlocked = true; continue; }", "if (!has) { continue; }",
     "перезапуск тихо перетворює хмарне завдання на офлайн-заглушку (P1-1)"),
    ("намір «хмара» ігнорується", CORE,
     "if (locked && wantsCloud) lockedBlocked = true;", "if (locked) lockedBlocked = true;",
     "свіжі завдання за офлайн-чіпа теж змушені чекати ключа, якого не відкриватимуть"),
    ("очікування cooldown прибрано", CORE,
     'if (cooling.length) return { action: "wait", reason: "cooldown", untilMs: Math.min(...cooling) };', "",
     "чекання cooldown знову витрачає спробу (P1-2)"),
    ("очікування мережі прибрано", CORE,
     'if (networkBlocked) return { action: "wait", reason: "network" };', "",
     "хмарне завдання без мережі деградує замість чекати"),
    ("«тільки локальна» не звужує ланцюг", CORE,
     'if (prefer === "local") return chain.filter((n) => n.kind === "local");',
     'if (prefer === "local") return chain;',
     "запит іде в хмару всупереч «тільки локальна» (P1-3, витік даних)"),
    ("чіп «тільки локальна» знову веде в хмару", CORE,
     'return { engine: "offline", reason: `локальна недоступна (${why}); хмару',
     'return cloudOk ? { engine: "cloud", reason: "x", fallback: true } : { engine: "offline", reason: `локальна недоступна (${why}); хмару',
     "чіп і диспетчер знову читають різні правила"),
    ("deferTask витрачає спробу", CORE,
     "return { ...t, waiting: undefined, nextAttemptAt:",
     "return { ...t, attempts: t.attempts + 1, waiting: undefined, nextAttemptAt:",
     "чекання знову вважається невдачею"),
    ("nextRunnable ігнорує прапорець очікування", CORE,
     't.status === "pending" && !t.waiting && t.nextAttemptAt <= now',
     't.status === "pending" && t.nextAttemptAt <= now',
     "завдання, що чекає подію, лишається «готовим» — холостий цикл"),
    ("сповіщення містить текст завдання", CORE,
     'body: "Завдання не вдалося виконати. Відкрий застосунок, щоб повторити.",',
     'body: "Не вдалося: " + (_task?.input ?? ""),',
     "текст завдання світиться на екрані блокування"),
]

APP_MUTANTS: list[Mutant] = [
    ("pruneQueue не викликається", APP,
     "    state.queue = pruneQueue(state.queue, { keepDone: 0 });\n    saveQueue();\n    render();",
     "    saveQueue();\n    render();",
     "завершені завдання ростуть у localStorage до вичерпання квоти"),
    ("проводка сповіщення бере текст завдання", APP,
     'const n = failureNotification(task);   // тексту завдання тут немає навмисно\n'
     '      new Notification(n.title, { body: n.body, tag: "pocket-agent-failure" });',
     'new Notification("Кишеньковий агент", { body: `Не вдалося: ${task.input.slice(0, 60)}`, tag: "pocket-agent-failure" });',
     "чиста функція правильна, а застосунок її обходить"),
    ("диспетчер не передає намір «хмара»", APP,
     'wantsCloud: task.intent === "cloud"', "wantsCloud: false",
     "відновлене хмарне завдання не чекає ключа"),
    ("розблокування не будить чергу", APP,
     'toast("Ключ відкрито"); renderEngine(); wakeAndDrain("locked");',
     'toast("Ключ відкрито"); renderEngine();',
     "завдання, що чекало ключа, не відновлюється після розблокування"),
    ("старт не будить застарілі очікування", APP,
     "state.queue = wakeWaiting(pruneQueue(state.queue, { keepDone: 0 }));",
     "state.queue = pruneQueue(state.queue, { keepDone: 0 });",
     "прапорець очікування зберігся, а подія online не прийде — завдання застрягло назавжди"),
]


# Мутант має бути спійманий САМЕ тією перевіркою, заради якої його придумано. Інакше «спіймано» може
# означати випадковий збій: так мутант «розблокування не будить чергу» колись «вбила» нестабільна
# перевірка про таймер, а не про розблокування (2026-09-30). Значення — уривок назви перевірки.
EXPECT: dict[str, str] = {
    "бекоф без джитера": "перша спроба ≈ базова",
    "429 визнано фатальним": "429 → перемкнути провайдера",
    "Retry-After ігнорується": "Retry-After має пріоритет над формулою",
    "вичерпані спроби зникають як done": "вичерпані спроби → failed",
    "повтор без паузи": "наступна спроба відсунута на Retry-After",
    "cooldown вузла не діє": "основна в cooldown → запасна",
    "офлайн «з'їдає» завдання після першого збою проходу": "exhausted, а не тихий офлайн",
    "замкнений ключ ігнорується": "замкнений ключ + намір «хмара»",
    "намір «хмара» ігнорується": "замкнений ключ без наміру",
    "очікування cooldown прибрано": "усі справжні вузли в паузі",
    "очікування мережі прибрано": "мережі нема, намір «хмара»",
    "«тільки локальна» не звужує ланцюг": "ланцюг лише з локальної",
    "чіп «тільки локальна» знову веде в хмару": "prefer=local без WebGPU → офлайн",
    "deferTask витрачає спробу": "deferTask НЕ витрачає спробу",
    "nextRunnable ігнорує прапорець очікування": "в стані очікування події не «готове»",
    "сповіщення містить текст завдання": "текст завдання НЕ потрапляє",
    "pruneQueue не викликається": "не лишаються в localStorage",
    "проводка сповіщення бере текст завдання": "НЕМАЄ тексту завдання",
    "диспетчер не передає намір «хмара»": "після перезапуску завдання чекає відкриття ключа",
    "розблокування не будить чергу": "розблокування будить чергу",
    "старт не будить застарілі очікування": "застарілий прапорець очікування",
}


def anchors_ok(base: Path, mutants: list[Mutant]) -> list[str]:
    """Кожен якір мусить існувати рівно раз. Повертає список проблем."""
    problems = []
    for name, rel, old, _new, _why in mutants:
        text = (base / PROJ / rel).read_text(encoding="utf-8")
        n = text.count(old)
        if n != 1:
            problems.append(f"якір мутанта «{name}» зустрічається {n}× у {rel} (потрібно рівно 1)")
        if name not in EXPECT:
            problems.append(f"для мутанта «{name}» не задано очікувану перевірку (EXPECT)")
    for name in EXPECT:
        if name not in {m[0] for m in mutants}:
            problems.append(f"EXPECT має запис «{name}», якого нема серед мутантів")
    return problems


def sh(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def failed_names(out: str) -> list[str]:
    return [l.replace("  - ", "").strip() for l in out.splitlines() if l.startswith("  - ")]


def run_level(title: str, tmp: Path, mutants: list[Mutant], script: str, timeout: int) -> tuple[int, int, list[str]]:
    """Ганяє мутанти одного рівня. Повертає (спіймано, вижило, рядки звіту)."""
    caught = survived = 0
    rows: list[str] = []
    for name, rel, old, new, why in mutants:
        target = tmp / PROJ / rel
        original = target.read_text(encoding="utf-8")
        target.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            built = sh(["node", str(tmp / PROJ / "build.mjs")], tmp, 120)
            if built.returncode != 0:
                # Мутант має бути валідним JS. Інакше «спійманий» лише тому, що не зібрався.
                survived += 1
                rows.append(f"  ⚠️  [{title}] НЕДІЙСНИЙ мутант (не зібрався): {name}")
                continue
            if rel.endswith(".js"):
                # build.mjs синтаксис не розбирає; без цього зламаний мутант «ловиться» падінням імпорту.
                probe = tmp / "mutant-syntax.mjs"
                probe.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
                if sh(["node", "--check", str(probe)], tmp, 30).returncode != 0:
                    survived += 1
                    rows.append(f"  ⚠️  [{title}] НЕДІЙСНИЙ мутант (синтаксична помилка): {name}")
                    continue
            r = sh(["node", str(tmp / "tests" / script)], tmp, timeout)
            names = failed_names(r.stdout)
            hit = [n for n in names if EXPECT[name] in n]
            if r.returncode != 0 and hit:
                caught += 1
                rows.append(f"  ✅ [{title}] {name}\n       → {hit[0][:92]}")
            elif r.returncode != 0 and names:
                # Впало, але не тим, що мало: доказом «тест бачить цю поведінку» це не є.
                survived += 1
                rows.append(f"  ⚠️  [{title}] спіймано НЕ тією перевіркою: {name}\n"
                            f"       очікувалась: …{EXPECT[name]}…\n       упало: {names[0][:92]}")
            elif r.returncode != 0:
                # Впало без жодної названої перевірки = аварія прогону, а не доказ, що тест бачить поведінку.
                survived += 1
                rows.append(f"  ⚠️  [{title}] прогін впав БЕЗ названої перевірки (аварія, не доказ): {name}")
            else:
                survived += 1
                rows.append(f"  ❌ [{title}] ВИЖИВ — діра в перевірках: {name}\n       (мав розбудити: {why})")
        finally:
            target.write_text(original, encoding="utf-8")
            # dist збирається з джерел: без перезбирання в ньому лишився б останній мутант,
            # і наступний рівень (браузер) стартував би з отруєною «базою».
            sh(["node", str(tmp / PROJ / "build.mjs")], tmp, 120)
    return caught, survived, rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check-anchors", action="store_true", help="лише перевірити якорі, нічого не виконуючи")
    ap.add_argument("--browser", action="store_true", help="додати мутанти app.html (реальний браузер, повільно)")
    args = ap.parse_args()

    problems = anchors_ok(ROOT, CORE_MUTANTS + APP_MUTANTS)
    if problems:
        print("❌ якорі мутантів зсунулись (мутант, що не застосувався, нічого не доводить):")
        for p in problems:
            print("  ✗", p)
        return 1
    total = len(CORE_MUTANTS) + len(APP_MUTANTS)
    print(f"✅ якорі на місці: {total} мутантів ({len(CORE_MUTANTS)} у ядрі, {len(APP_MUTANTS)} в app.html)")
    if args.check_anchors:
        return 0

    if shutil.which("node") is None:
        print("⊘ НЕ ГАНЯЛОСЬ: node не встановлено — мутації контуру не виконано (це не «пройшло»)")
        return 2

    with tempfile.TemporaryDirectory(prefix="mut-mobile-agent-") as d:
        tmp = Path(d)
        shutil.copytree(ROOT / PROJ, tmp / PROJ, ignore=shutil.ignore_patterns("screenshots"))
        (tmp / "tests").mkdir()
        for f in ("mobile-agent-tests.mjs", "mobile-agent-browser.mjs"):
            shutil.copy(ROOT / "tests" / f, tmp / "tests" / f)

        # 1. БАЗА: немутований код має пройти. Інакше «спіймано» = «усе зламано».
        if sh(["node", str(tmp / PROJ / "build.mjs")], tmp, 120).returncode != 0:
            print("❌ база не збирається — мутації безглузді")
            return 1
        base = sh(["node", str(tmp / "tests" / "mobile-agent-tests.mjs")], tmp, 180)
        if base.returncode != 0:
            print("❌ база (немутований код) НЕ проходить юніт-тести — «спіймано» нічого б не означало")
            return 1
        print("✅ база зелена: немутований код проходить юніт-тести")

        rows: list[str] = []
        caught, survived, r = run_level("ядро", tmp, CORE_MUTANTS, "mobile-agent-tests.mjs", 180)
        rows += r

        if args.browser:
            b = sh(["node", str(tmp / "tests" / "mobile-agent-browser.mjs")], tmp, 300)
            if "skipped=1" in b.stdout:
                print("⊘ НЕ ГАНЯЛОСЬ: playwright/Chromium недоступні — браузерні мутанти не виконано")
                print("\n".join(rows))
                return 2
            if b.returncode != 0:
                print("❌ база НЕ проходить браузерний набір — браузерні мутанти безглузді")
                print("\n".join(l for l in (b.stdout + b.stderr).splitlines() if "✅" not in l)[-1500:])
                return 1
            print("✅ база зелена: немутований код проходить браузерний набір")
            c2, s2, r2 = run_level("браузер", tmp, APP_MUTANTS, "mobile-agent-browser.mjs", 300)
            caught += c2
            survived += s2
            rows += r2

    print("\n".join(rows))
    level = "ядро + браузер" if args.browser else "ядро"
    print(f"\nмутантів ({level}): {caught + survived} · спіймано: {caught} · вижило: {survived}")
    if survived:
        print("Вижив мутант = діра в перевірках, а не в коді: додай тест, який його вб'є.")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
