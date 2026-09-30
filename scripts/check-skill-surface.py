#!/usr/bin/env python3
"""check-skill-surface.py — підпис ВИКОНУВАНОЇ поверхні навичок.

НАВІЩО. `maintain.py verify` хешує SKILL.md і тому бачить будь-яку правку — але
штатний крок `resync` перебирає хеш як нову норму. Виміряно 2026-09-30 на повній
копії дерева: скілу з `allowed-tools: Read` дописали `Bash(*)` і `WebFetch`,
пройшли `resync` → `verify` — exit 0, у звіті жодного слова про права. Тобто
розширення того, що навичка МОЖЕ ВИКОНАТИ, стає нормою одним рутинним кроком.

Ідея з `open-gsd/gsd-core` (`docs/explanation/capability-trust-model.md`): згода
прив'язана не лише до бандла, а й до ПІДПИСУ виконуваної поверхні — додався хук чи
змінилась команда, згода анулюється. У нас поверхня навички — це:
    · `allowed-tools`  (що навичці дозволено викликати)
    · `hooks`          (блок у frontmatter, якщо є)
    · файли `scripts/` (код, який може виконатись)
    · `gates.json`     (гейти, які `scripts/run-gates.py` ЗАПУСКАЄ як команди)

ЩО РОБИТЬ. Порівнює поточну поверхню з базовою лінією
`melania-skills-ecosystem/SURFACE.json`. РОЗШИРЕННЯ поверхні — нова навичка, додані
права, зміна/додавання скрипта, зняття обмеження — без записаної згоди є
ПОМИЛКОЮ. Звуження й видалення — лише інформація. Згода — це рядок
`skill-surface` у `security/consent.md` з ЦІЛЛЮ = назва навички (та сама точкова
механіка, що для найдорожчих правил безпекового гейта).

ЧЕСНА МЕЖА. Згоду записує той самий агент, що правит навичку, тож це РЕЄСТРАТОР,
а не бар'єр: він робить розширення видимим, названим і датованим у діффі PR
(так само, як `consent.md` для решти). Справжнє закриття — рев'ю поза агентом.
Також: перевіряється поверхня, ЗАЯВЛЕНА у frontmatter і в `scripts/`; що саме
скрипт робить, ця перевірка не оцінює (це `safety-scan` у maintain.py).

РЕЖИМИ.
    (без прапорців)  звірка; код 0 / 1 (є розширення без згоди) / 2 (немає бази)
    --init           створити базову лінію (лише якщо її ще немає)
    --update         оновити базу; ВІДМОВЛЯЄ, поки є розширення без згоди —
                     інакше базу можна було б тихо «освіжити» й стерти слід
    --root DIR       корінь репозиторію (для перевірок на тимчасовому дереві)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

BASELINE_REL = Path("melania-skills-ecosystem") / "SURFACE.json"
SKILL_ROOTS = (Path("melania-skills-ecosystem") / "skills", Path(".claude") / "skills")
RULE_ID = "skill-surface"
# Імена, зарезервовані за першою стороною: навичка з таким префіксом видає себе
# за чужий продукт (у gsd-core те саме для `gsd-`/`anthropic-`).
RESERVED_PREFIXES = ("anthropic-", "claude-")
SKIP_PARTS = {".snapshots", "__pycache__"}
SKIP_SUFFIXES = {".pyc", ".jsonl", ".log"}


def frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


def _block(fm: str, key: str) -> list[str] | None:
    """Рядки блоку верхнього рівня `key:` до наступного ключа; None — ключа нема."""
    lines = fm.split("\n")
    for i, ln in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:", ln):
            body = [ln.split(":", 1)[1].strip()] if ln.split(":", 1)[1].strip() else []
            for nxt in lines[i + 1:]:
                if re.match(r"^[A-Za-z_-]+:", nxt):
                    break
                body.append(nxt)
            return body
    return None


def parse_tools(fm: str) -> list[str] | None:
    """`allowed-tools`: None — не заявлено взагалі (це НЕ те саме, що порожній список)."""
    block = _block(fm, "allowed-tools")
    if block is None:
        return None
    tools: list[str] = []
    for ln in block:
        item = re.match(r"^\s*-\s+(.*\S)\s*$", ln)
        if item:
            tools.append(item.group(1).strip("'\""))
        elif ln.strip() and not ln.startswith((" ", "\t")):
            # Рядкова форма `allowed-tools: Read, Write` — теж законна.
            tools += [t.strip().strip("'\"") for t in ln.split(",") if t.strip()]
    return sorted(set(tools))


def surface(skill_dir: Path) -> dict:
    skill_md = skill_dir / "SKILL.md"
    fm = frontmatter(skill_md.read_text(encoding="utf-8", errors="replace")) if skill_md.is_file() else ""
    hooks = _block(fm, "hooks")
    scripts: dict[str, str] = {}
    sdir = skill_dir / "scripts"
    if sdir.is_dir():
        for f in sorted(sdir.rglob("*")):
            if not f.is_file() or SKIP_PARTS & set(f.parts) or f.suffix in SKIP_SUFFIXES:
                continue
            scripts[str(f.relative_to(skill_dir))] = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
    gates_file = skill_dir / "gates.json"
    return {
        "tools": parse_tools(fm),
        "hooks": hashlib.sha256("\n".join(hooks).encode()).hexdigest()[:16] if hooks else None,
        "gates": hashlib.sha256(gates_file.read_bytes()).hexdigest()[:16] if gates_file.is_file() else None,
        "scripts": scripts,
    }


def collect(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rel in SKILL_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            # Симлінки в `.claude/skills` — це дзеркала melania-скілів: рахуємо джерело раз.
            if d.is_symlink() or not d.is_dir() or not (d / "SKILL.md").is_file():
                continue
            out[d.name] = surface(d)
    return out


def delta(cur: dict, base: dict | None) -> dict:
    """Що змінилось. `expanding` — чи стала поверхня ШИРШОЮ."""
    if base is None:
        return {"new": True, "expanding": True,
                "notes": ["нова навичка — приймання: поверхню слід переглянути"]}
    notes: list[str] = []
    expanding = False
    ct, bt = cur["tools"], base["tools"]
    if ct != bt:
        if bt is None:                       # було «без заяви», стало обмеження — звуження
            notes.append(f"allowed-tools тепер заявлено: {', '.join(ct or [])}")
        elif ct is None:                     # зняли обмеження — це РОЗШИРЕННЯ
            expanding = True
            notes.append("allowed-tools ЗНЯТО (обмеження більше не заявлене)")
        else:
            add, rem = sorted(set(ct) - set(bt)), sorted(set(bt) - set(ct))
            if add:
                expanding = True
                notes.append("allowed-tools додано: " + ", ".join(add))
            if rem:
                notes.append("allowed-tools прибрано: " + ", ".join(rem))
    if cur["hooks"] != base["hooks"]:
        expanding = True
        notes.append("змінено блок hooks")
    # `.get`: бази, знятої до появи ключа, він не відомий — це «гейтів не було».
    if cur["gates"] != base.get("gates"):
        expanding = True
        notes.append("змінено gates.json (гейти, що запускаються як команди)")
    cs, bs = cur["scripts"], base["scripts"]
    for name in sorted(set(cs) - set(bs)):
        expanding = True
        notes.append(f"додано скрипт {name}")
    for name in sorted(n for n in set(cs) & set(bs) if cs[n] != bs[n]):
        expanding = True
        notes.append(f"змінено скрипт {name}")
    for name in sorted(set(bs) - set(cs)):
        notes.append(f"прибрано скрипт {name}")
    return {"new": False, "expanding": expanding, "notes": notes}


def consented(root: Path, name: str) -> bool:
    """Чи є ЧИННИЙ рядок `skill-surface` із ціллю = назва навички.

    Логіку (дата, довжина причини, збіг цілі) беремо з `pretooluse.active_consent`,
    щоб не мати двох різних тлумачень «що таке згода». Шлях до файла підміняється
    на файл переданого кореня — так перевірки на тимчасовому дереві не читають
    справжній consent.md.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "security" / "spine"))
    try:
        import pretooluse  # noqa: WPS433 — свідомий пізній імпорт
    finally:
        sys.path.pop(0)
    pretooluse.CONSENT = root / "security" / "consent.md"
    policy = {"rules": [{"id": RULE_ID, "require_target": True}]}
    return pretooluse.active_consent(RULE_ID, name, policy) is not None


def load_baseline(root: Path) -> dict | None:
    p = root / BASELINE_REL
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_baseline(root: Path, cur: dict[str, dict]) -> None:
    doc = {
        "schema": 1,
        "about": ("Підпис виконуваної поверхні навичок (allowed-tools · hooks · scripts · gates). "
                  "Звіряє scripts/check-skill-surface.py; розширення без запису в "
                  "security/consent.md (rule=skill-surface, ціль=назва навички) — помилка."),
        "skills": cur,
    }
    (root / BASELINE_REL).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def problems(root: Path, cur: dict[str, dict], base: dict | None) -> tuple[list[str], list[str]]:
    """(помилки, інформаційні рядки)."""
    errs: list[str] = []
    info: list[str] = []
    for name in sorted(cur):
        if any(name.startswith(p) for p in RESERVED_PREFIXES):
            errs.append(f"{name}: ім'я з зарезервованим префіксом "
                        f"({'/'.join(RESERVED_PREFIXES)}) — так видають себе за чужий продукт")
        d = delta(cur[name], (base or {}).get("skills", {}).get(name))
        if not d["notes"]:
            continue
        line = f"{name}: " + "; ".join(d["notes"])
        if d["expanding"] and not consented(root, name):
            errs.append(line + "  → поверхню РОЗШИРЕНО без записаної згоди "
                        f"(rule={RULE_ID}, ціль={name})")
        elif d["expanding"]:
            info.append(line + "  → розширення СХВАЛЕНО записаною згодою")
        else:
            info.append(line + "  → звуження, згоди не потребує")
    for name in sorted(set((base or {}).get("skills", {})) - set(cur)):
        info.append(f"{name}: навичку прибрано з поверхні")
    return errs, info


def main(argv: list[str]) -> int:
    args = argv[1:]
    root = Path(__file__).resolve().parents[1]
    if "--root" in args:
        i = args.index("--root")
        root = Path(args[i + 1]).resolve()
        del args[i:i + 2]
    update, init = "--update" in args, "--init" in args
    cur = collect(root)
    try:
        base = load_baseline(root)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check-skill-surface: базова лінія нечитабельна: {exc}", file=sys.stderr)
        return 2

    if init:
        if base is not None:
            print("check-skill-surface: базова лінія вже є — --init її не перезаписує "
                  "(для оновлення — --update)", file=sys.stderr)
            return 2
        write_baseline(root, cur)
        print(f"базову лінію створено: {len(cur)} навичок, "
              f"{sum(len(s['scripts']) for s in cur.values())} скриптів")
        return 0

    if base is None:
        print("check-skill-surface: базової лінії немає — спершу --init", file=sys.stderr)
        return 2

    errs, info = problems(root, cur, base)
    for line in info:
        print(f"  ℹ {line}")
    if errs:
        print(f"🚩 поверхня розширена без згоди — {len(errs)}:")
        for e in errs:
            print(f"  ✗ {e}")
        return 1
    if update:
        write_baseline(root, cur)
        print("базову лінію оновлено (розширень без згоди немає)")
        return 0
    print(f"✅ поверхня навичок збігається з базовою лінією ({len(cur)} навичок)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
