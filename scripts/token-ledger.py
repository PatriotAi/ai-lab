#!/usr/bin/env python3
"""token-ledger.py — вимір витрат токенів із транскриптів сесій Claude Code.

Єдина відповідальність: перетворити транскрипти (`~/.claude/projects/<slug>/*.jsonl`)
на ЧИСЛА, які можна порівняти «до/після». Без цього будь-яка заява про економію
лишається самозвітом, а не виміром (CLAUDE.md §11, Core Rule 15).

Джерело даних — поле `message.usage` кожного запису типу `assistant`:
    input_tokens · output_tokens · cache_creation_input_tokens · cache_read_input_tokens

ЧОМУ БЕЗ ЦІН: перерахунок у гроші прив'язав би скрипт до конкретних моделей і
тарифів, тобто зробив би його старіючим (закон не-старіння). Тут — лише сирі
лічильники; мапінг «токени → гроші» живе в датованому снапшоті провайдерів.

ЧОМУ «cached» РАХУЄТЬСЯ ОКРЕМО: кеш-читання коштує інакше, ніж свіжий вхід.
Змішати їх в одне число означало б заявити економію там, де змінилась лише
структура кешу. Тому підсумок завжди показує всі чотири лічильники окремо.

Запуск:
    python3 scripts/token-ledger.py                      # усі сесії поточного проєкту
    python3 scripts/token-ledger.py --session <id>       # одна сесія
    python3 scripts/token-ledger.py --json               # машиночитний вивід
    python3 scripts/token-ledger.py --label before       # позначити зріз
    python3 scripts/token-ledger.py --compare a.json b.json
    python3 scripts/token-ledger.py --validate           # самотест на фікстурах

Код виходу: 0 — успіх · 1 — даних не знайдено або самотест упав · 2 — помилка виклику.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import tempfile

USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def project_slug(project_dir: str) -> str:
    """Слаг теки проєкту так, як його утворює Claude Code: '/home/user/x' → '-home-user-x'."""
    return project_dir.replace(os.sep, "-").replace(".", "-").replace("_", "-")


def transcripts_root() -> pathlib.Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude"
    )
    return pathlib.Path(base) / "projects"


def find_transcripts(project_dir: str | None, session: str | None) -> list[pathlib.Path]:
    root = transcripts_root()
    if not root.is_dir():
        return []
    if session:
        return sorted(root.glob(f"*/{session}.jsonl"))
    if project_dir:
        d = root / project_slug(os.path.abspath(project_dir))
        return sorted(d.glob("*.jsonl")) if d.is_dir() else []
    return sorted(root.glob("*/*.jsonl"))


def read_transcript(path: pathlib.Path) -> dict:
    """Зібрати лічильники однієї сесії. Незрозумілі рядки пропускаємо мовчки —
    транскрипт пишеться на льоту, останній рядок може бути обірваний."""
    totals = dict.fromkeys(USAGE_FIELDS, 0)
    models: dict[str, int] = {}
    efforts: dict[str, int] = {}
    versions: set[str] = set()
    turns = 0
    sidechain_turns = 0

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue
            turns += 1
            if rec.get("isSidechain"):
                sidechain_turns += 1
            for field in USAGE_FIELDS:
                value = usage.get(field)
                if isinstance(value, int):
                    totals[field] += value
            if model := msg.get("model"):
                models[model] = models.get(model, 0) + 1
            if effort := rec.get("effort"):
                efforts[effort] = efforts.get(effort, 0) + 1
            if version := rec.get("version"):
                versions.add(version)

    return {
        "session": path.stem,
        "path": str(path),
        "turns": turns,
        "sidechain_turns": sidechain_turns,
        "models": models,
        "efforts": efforts,
        "cli_versions": sorted(versions),
        **totals,
    }


def aggregate(sessions: list[dict], label: str | None) -> dict:
    totals = dict.fromkeys(USAGE_FIELDS, 0)
    turns = sidechain = 0
    models: dict[str, int] = {}
    for s in sessions:
        for field in USAGE_FIELDS:
            totals[field] += s[field]
        turns += s["turns"]
        sidechain += s["sidechain_turns"]
        for model, count in s["models"].items():
            models[model] = models.get(model, 0) + count

    # «Свіжий вхід» — те, на що впливає обсяг інструкцій у контексті. Кеш-читання
    # відображає ту саму інструкцію, вже закешовану, тому для оцінки ефекту від
    # скорочення контексту дивимось на обидва числа, а не на одну суму.
    fresh_input = totals["input_tokens"] + totals["cache_creation_input_tokens"]

    return {
        "label": label,
        "sessions": len(sessions),
        "turns": turns,
        "sidechain_turns": sidechain,
        "models": models,
        **totals,
        "fresh_input_tokens": fresh_input,
        "total_tokens": sum(totals.values()),
        "per_turn": {
            # ГОЛОВНА МЕТРИКА. Інструкції (CLAUDE.md, системний промпт, описи скілів)
            # живуть у КЕШОВАНОМУ префіксі: кожен хід перечитує їх як cache_read.
            # Емпірика цієї лабораторії: ~93% витрат — саме cache_read, а не свіжий
            # вхід. Тому «скільки контексту ми несемо на хід» = увесь вхідний бік;
            # мірити лише свіжий вхід означало б не побачити основного ефекту.
            "input_side": round((fresh_input + totals["cache_read_input_tokens"]) / turns, 1)
            if turns else 0,
            "fresh_input": round(fresh_input / turns, 1) if turns else 0,
            "output": round(totals["output_tokens"] / turns, 1) if turns else 0,
            "cache_read": round(totals["cache_read_input_tokens"] / turns, 1) if turns else 0,
        },
    }


def render(summary: dict, sessions: list[dict], verbose: bool) -> str:
    lines: list[str] = []
    head = "# Token ledger"
    if summary["label"]:
        head += f" — зріз «{summary['label']}»"
    lines.append(head)
    lines.append("")
    lines.append(f"- Сесій: **{summary['sessions']}** · ходів моделі: **{summary['turns']}**"
                 f" (з них суб-агентських: {summary['sidechain_turns']})")
    models = ", ".join(f"{m} ×{c}" for m, c in sorted(summary["models"].items())) or "—"
    lines.append(f"- Моделі: {models}")
    lines.append("")
    lines.append("| Лічильник | Токенів |")
    lines.append("|---|---:|")
    lines.append(f"| Свіжий вхід (input + cache_creation) | {summary['fresh_input_tokens']:,} |")
    lines.append(f"| — з них input | {summary['input_tokens']:,} |")
    lines.append(f"| — з них cache_creation | {summary['cache_creation_input_tokens']:,} |")
    lines.append(f"| Читання з кешу | {summary['cache_read_input_tokens']:,} |")
    lines.append(f"| Вихід | {summary['output_tokens']:,} |")
    lines.append(f"| **Разом** | **{summary['total_tokens']:,}** |")
    lines.append("")
    lines.append(f"На один хід: **вхідний бік {summary['per_turn']['input_side']:,}** "
                 f"(свіжий {summary['per_turn']['fresh_input']:,} + "
                 f"кеш {summary['per_turn']['cache_read']:,}) · "
                 f"вихід {summary['per_turn']['output']:,}")

    if verbose:
        lines.append("")
        lines.append("## Посесійно")
        lines.append("")
        lines.append("| Сесія | Ходів | Свіжий вхід | Вихід | Кеш |")
        lines.append("|---|---:|---:|---:|---:|")
        for s in sorted(sessions, key=lambda x: -x["turns"]):
            fresh = s["input_tokens"] + s["cache_creation_input_tokens"]
            lines.append(f"| `{s['session'][:8]}` | {s['turns']} | {fresh:,} | "
                         f"{s['output_tokens']:,} | {s['cache_read_input_tokens']:,} |")
    return "\n".join(lines)


def compare(before: dict, after: dict) -> str:
    """Порівняння двох зрізів. Нормалізуємо на ОДИН хід — інакше довша сесія
    виглядала б як зростання витрат, а коротша як «економія»."""
    lines = ["# Порівняння зрізів", ""]
    lines.append(f"- До:  «{before.get('label') or '—'}» — {before['turns']} ходів")
    lines.append(f"- Після: «{after.get('label') or '—'}» — {after['turns']} ходів")
    lines.append("")

    if not before["turns"] or not after["turns"]:
        lines.append("⚠️ Один зі зрізів не має ходів моделі — порівняння неможливе.")
        return "\n".join(lines)

    lines.append("| Метрика (на 1 хід) | До | Після | Зміна |")
    lines.append("|---|---:|---:|---:|")
    verdict_delta = None
    for key, title in (
        ("input_side", "**Вхідний бік (вердикт)**"),
        ("fresh_input", "— свіжий вхід"),
        ("cache_read", "— читання з кешу"),
        ("output", "Вихід"),
    ):
        b = before["per_turn"].get(key, 0)
        a = after["per_turn"].get(key, 0)
        delta = ((a - b) / b * 100) if b else 0.0
        if key == "input_side":
            verdict_delta = delta if b else None
        lines.append(f"| {title} | {b:,} | {a:,} | {delta:+.1f}% |")

    lines.append("")
    if verdict_delta is None:
        lines.append("Вердикт неможливий: у базовому зрізі вхідний бік нульовий.")
    elif verdict_delta <= -15:
        lines.append(f"**Критерій гіпотези пройдено:** вхідний бік на хід впав на "
                     f"{abs(verdict_delta):.1f}% (поріг — 15%).")
    else:
        lines.append(f"**Критерій гіпотези НЕ пройдено:** вхідний бік на хід змінився на "
                     f"{verdict_delta:+.1f}%, поріг — падіння щонайменше на 15%.")
    lines.append("")
    lines.append("> Вихід не входить у вердикт: його обсяг визначає задача, а не обсяг "
                 "інструкцій. Зарахувати його в економію означало б видати коротшу "
                 "відповідь за ефективніший контекст.")
    return "\n".join(lines)


# ── Самотест ───────────────────────────────────────────────────────────────
# Кожна перевірка будується від СПОСОБУ помилитися, а не від формулювання
# правила (Core Rule 15). Тому фікстури містять і зламані входи теж.

def _fixture(records: list[dict]) -> str:
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for rec in records:
        fh.write(json.dumps(rec) + "\n")
    fh.close()
    return fh.name


def _turn(inp=0, out=0, cc=0, cr=0, model="m", sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "effort": "high",
        "version": "9.9.9",
        "message": {
            "role": "assistant",
            "model": model,
            "usage": {
                "input_tokens": inp,
                "output_tokens": out,
                "cache_creation_input_tokens": cc,
                "cache_read_input_tokens": cr,
            },
        },
    }


def validate() -> int:
    failures: list[str] = []

    def check(name: str, expected, actual):
        if expected == actual:
            print(f"  ✅ {name}")
        else:
            failures.append(name)
            print(f"  ❌ {name}\n     очікували: {expected}\n     отримали:  {actual}")

    print("token-ledger самотест:")

    # 1. Базова арифметика.
    path = pathlib.Path(_fixture([_turn(inp=10, out=5, cc=100, cr=1000),
                                  _turn(inp=20, out=7, cc=0, cr=2000)]))
    data = read_transcript(path)
    check("сума input", 30, data["input_tokens"])
    check("сума output", 12, data["output_tokens"])
    check("сума cache_read", 3000, data["cache_read_input_tokens"])
    check("кількість ходів", 2, data["turns"])

    # 2. Записи без usage і не-assistant не мають потрапляти в лічильник ходів:
    #    інакше «ходи» роздуються службовими рядками і per-turn стане меншим,
    #    показавши фальшиву економію.
    path2 = pathlib.Path(_fixture([
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"role": "assistant", "model": "m"}},  # без usage
        _turn(inp=5, out=5),
    ]))
    data2 = read_transcript(path2)
    check("службові рядки не рахуються як ходи", 1, data2["turns"])

    # 3. Обірваний останній рядок (транскрипт пишеться на льоту) не має валити скрипт.
    broken = path2.read_text(encoding="utf-8") + '{"type":"assistant","mess'
    path3 = pathlib.Path(_fixture([]))
    path3.write_text(broken, encoding="utf-8")
    data3 = read_transcript(path3)
    check("обірваний рядок пропускається", 1, data3["turns"])

    # 4. Суб-агентські ходи рахуються окремо — інакше делегування виглядало б
    #    як економія оркестратора, хоча токени просто переїхали на суб-рівень.
    path4 = pathlib.Path(_fixture([_turn(inp=1, sidechain=True), _turn(inp=1)]))
    data4 = read_transcript(path4)
    check("суб-агентські ходи відокремлені", (2, 1),
          (data4["turns"], data4["sidechain_turns"]))

    # 5. Порожній зріз НЕ має виглядати як нуль витрат: «порожньо» і
    #    «відфільтровано» виглядають однаково, тому агрегат зобов'язаний
    #    показати sessions=0, а виклик — впасти з кодом 1 (перевірка нижче в main).
    empty = aggregate([], None)
    check("порожній зріз чесний", (0, 0), (empty["sessions"], empty["turns"]))

    # 6. Порівняння нормалізується на хід: удвічі довша сесія з тими самими
    #    витратами на хід НЕ є регресом.
    b = aggregate([read_transcript(path)], "before")
    long_path = pathlib.Path(_fixture([_turn(inp=10, out=5, cc=100, cr=1000),
                                       _turn(inp=20, out=7, cc=0, cr=2000),
                                       _turn(inp=10, out=5, cc=100, cr=1000),
                                       _turn(inp=20, out=7, cc=0, cr=2000)]))
    a = aggregate([read_transcript(long_path)], "after")
    check("подвоєна довжина не є регресом на хід",
          b["per_turn"]["fresh_input"], a["per_turn"]["fresh_input"])

    # 7. Вердикт спрацьовує на РЕАЛЬНОМУ падінні і мовчить на дрібному.
    small_drop = aggregate([read_transcript(pathlib.Path(_fixture([_turn(inp=59, cc=0)])))], "after")
    base = aggregate([read_transcript(pathlib.Path(_fixture([_turn(inp=65, cc=0)])))], "before")
    check("падіння 9% не проходить поріг", True,
          "НЕ пройдено" in compare(base, small_drop))
    big_drop = aggregate([read_transcript(pathlib.Path(_fixture([_turn(inp=50, cc=0)])))], "after")
    check("падіння 23% проходить поріг", True,
          "пройдено" in compare(base, big_drop)
          and "НЕ пройдено" not in compare(base, big_drop))

    # 8. Регрес, спійманий на живих даних 2026-07-27: інструкції лежать у
    #    КЕШОВАНОМУ префіксі, тому їх скорочення падає на cache_read, а свіжий
    #    вхід майже не рухається. Вердикт, побудований на свіжому вході, показав
    #    би «економії нема» там, де вона є. Зламаний стан: fresh незмінний,
    #    cache_read впав удвічі — вердикт ЗОБОВ'ЯЗАНИЙ це побачити.
    cached_base = aggregate([read_transcript(pathlib.Path(_fixture(
        [_turn(inp=100, cr=100_000)])))], "before")
    cached_after = aggregate([read_transcript(pathlib.Path(_fixture(
        [_turn(inp=100, cr=50_000)])))], "after")
    report = compare(cached_base, cached_after)
    check("падіння лише в кеші зараховується як економія", True,
          "пройдено" in report and "НЕ пройдено" not in report)

    # 9. Дзеркальний випадок: вихід став удвічі коротшим, вхідний бік не змінився.
    #    Це НЕ економія контексту — вердикт має мовчати.
    out_base = aggregate([read_transcript(pathlib.Path(_fixture(
        [_turn(inp=100, cr=10_000, out=2000)])))], "before")
    out_after = aggregate([read_transcript(pathlib.Path(_fixture(
        [_turn(inp=100, cr=10_000, out=1000)])))], "after")
    check("коротший вихід НЕ зараховується як економія", True,
          "НЕ пройдено" in compare(out_base, out_after))

    for p in (path, path2, path3, path4, long_path):
        p.unlink(missing_ok=True)

    print()
    if failures:
        print(f"❌ Самотест упав: {len(failures)} перевірок — {', '.join(failures)}")
        return 1
    print("✅ Самотест: усі перевірки пройшли")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Вимір витрат токенів із транскриптів Claude Code")
    ap.add_argument("--session", help="ID конкретної сесії")
    ap.add_argument("--project", help="тека проєкту (типово — поточна)")
    ap.add_argument("--all-projects", action="store_true", help="усі проєкти, не лише поточний")
    ap.add_argument("--label", help="назва зрізу (before/after)")
    ap.add_argument("--json", action="store_true", help="машиночитний вивід")
    ap.add_argument("--verbose", action="store_true", help="таблиця посесійно")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE.json", "AFTER.json"),
                    help="порівняти два збережені зрізи")
    ap.add_argument("--validate", action="store_true", help="самотест на фікстурах")
    args = ap.parse_args()

    if args.validate:
        return validate()

    if args.compare:
        try:
            before = json.loads(pathlib.Path(args.compare[0]).read_text(encoding="utf-8"))
            after = json.loads(pathlib.Path(args.compare[1]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Не вдалося прочитати зрізи: {exc}", file=sys.stderr)
            return 2
        print(compare(before, after))
        return 0

    project = None if args.all_projects else (args.project or os.getcwd())
    paths = find_transcripts(project, args.session)
    if not paths:
        # Чесна межа: не друкуємо нулі. Порожній результат і відфільтрований
        # результат виглядають однаково — тому кажемо, ДЕ саме шукали.
        where = args.session or project or "усі проєкти"
        print(f"Транскриптів не знайдено (шукали: {where}; корінь: {transcripts_root()}).",
              file=sys.stderr)
        return 1

    sessions = [read_transcript(p) for p in paths]
    summary = aggregate(sessions, args.label)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render(summary, sessions, args.verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
