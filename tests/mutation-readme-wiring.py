#!/usr/bin/env python3
"""mutation-readme-wiring.py — гейт для стенда тверджень README (W-16).

ПИТАННЯ. `tests/probe-readme-wiring.py` зелений — але чи ловить він хоч щось?
Твердження «стенд доведено 9/11 мутантами» два дні трималось на скрипті в
тимчасовій теці сесії: контейнер зник би — і доказ разом із ним, а напис у
`run-tests.sh` лишився б (CLAUDE.md §11: крок, що тримається лише на уважності,
має стати перевіркою). Тепер мутанти живуть тут і ганяються набором.

Мутується лише `scripts/security-drift.py` (функція `check_readme_claims` і її
помічники) — у КОПІЇ в тимчасовій теці; робочі файли не чіпаються ніколи.

Запуск: python3 tests/mutation-readme-wiring.py [--verbose]
Код виходу: 0 — кожен мутант спійманий · 1 — хтось вижив (діра в стенді).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "scripts/security-drift.py"
PROBE = "tests/probe-readme-wiring.py"

# Кожна мутація — правдоподібна помилка автора, а не шум. Дві з них — поведінка
# перших версій, яку виправило рев'ю #94: стенд мусить не пустити її назад.
MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "минуле не обрізається",
        "            cut = _PAST.search(line)\n            if cut:\n                line = line[:cut.start()]\n",
        "",
        "«історично … `Stop`» знову тривога — минуле читається як чинне",
    ),
    (
        "заперечення не відсіюється",
        "            if _NOT_A_CLAIM.search(line):\n                continue\n",
        "",
        "«`X` — знято» знову тривога — зняте читається як чинне",
    ),
    (
        "заперечення обрізає рядок замість пропуску (поведінка до 2026-10-23)",
        "            if _NOT_A_CLAIM.search(line):\n                continue\n",
        "            neg = _NOT_A_CLAIM.search(line)\n            if neg:\n                line = line[:neg.start()]\n",
        "«`a` на `Stop` більше не підключено» — тривога на заперечення ПІСЛЯ події",
    ),
    (
        "маркер викидає ВЕСЬ рядок (поведінка першої версії)",
        "                line = line[:cut.start()]\n",
        "                line = \"\"\n",
        "«`Stop` (раніше `SessionEnd`)» — чинне твердження до маркера зникає",
    ),
    (
        "маркер без межі слова",
        "(?<!\\w)(історично",
        "(історично",
        "«найраніше» спрацьовує як маркер «раніше» і ховає твердження",
    ),
    (
        "твердження про іншу автоматизацію не збирається",
        "                    claims.append((value, value2))\n",
        "                    pass\n",
        "інцидент g5-retrieve: проза про ІНШУ автоматизацію знову не перевіряється",
    ),
    (
        "пара лише з ПЕРШОЮ подією (поведінка першої версії)",
        "                    claims.append((value, value2))\n",
        "                    claims.append((value, value2))\n                    break\n",
        "назва з двома подіями: перевіряється лише перша",
    ),
    (
        "рядок «Тригер/Подія» про себе ігнорується",
        "            if _OWN_CLAIM.match(line) and not any(c[0] != own for c in claims):",
        "            if False:",
        "інцидент g5-consolidate: «Тригер: Stop» без реєстрації знову мовчить",
    ),
    (
        "реєстрація середовища не зараховується",
        "    return any(e.get(\"event\") == event and",
        "    return False and any(e.get(\"event\") == event and",
        "хук, що реєструє середовище, — хибна тривога",
    ),
    (
        "подія реєстрації не звіряється",
        "(settings.get(\"hooks\", {}) or {}).get(event, [])",
        "[g for gs in (settings.get(\"hooks\", {}) or {}).values() for g in gs]",
        "реєстрація на ІНШІЙ події зараховується як правдива",
    ),
    (
        "подія без урахування регістру",
        "+ r\")(?![a-z])\")",
        "+ r\")(?![a-z])\", re.I)",
        "слово «stop» з малої читається як подія — хибна тривога",
    ),
    (
        "розбіжність не повідомляється",
        "                if not _wired(name, event, settings, env_wired, root):",
        "                if False:",
        "перевірка мовчить завжди",
    ),
    (
        "подія середовища не звіряється",
        "e.get(\"event\") == event and (root",
        "True and (root",
        "реєстрація середовища на іншій події зараховується",
    ),
]


def build_sandbox(tmp: Path) -> Path:
    """Копія лише скрипта й стенда. Робочі файли недоторкані."""
    sandbox = tmp / "repo"
    for rel in (TARGET, PROBE):
        (sandbox / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, sandbox / rel)
    return sandbox


def caught(sandbox: Path) -> bool:
    res = subprocess.run([sys.executable, "-I", str(sandbox / PROBE)],
                         capture_output=True, text=True, timeout=120)
    return res.returncode != 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv[1:])

    with tempfile.TemporaryDirectory() as td:
        sandbox = build_sandbox(Path(td))
        original = (sandbox / TARGET).read_text(encoding="utf-8")

        # Контроль: на цілому коді стенд мовчить — інакше результати нічого не варті.
        if caught(sandbox):
            print("  ❌ на цілому коді стенд впав — прогін недійсний")
            return 1

        survived: list[tuple[str, str]] = []
        for name, old, new, effect in MUTATIONS:
            if old not in original:
                print(f"  ⚠️  мутація «{name}» не застосовна — цільовий рядок змінився")
                survived.append((name, "цільовий рядок не знайдено"))
                continue
            (sandbox / TARGET).write_text(original.replace(old, new, 1), encoding="utf-8")
            hit = caught(sandbox)
            (sandbox / TARGET).write_text(original, encoding="utf-8")
            if hit:
                if args.verbose:
                    print(f"  ✅ {name}")
            else:
                survived.append((name, effect))

    total = len(MUTATIONS)
    if survived:
        print(f"  ❌ мутанти стенда README: {total - len(survived)}/{total} спіймано, {len(survived)} ВИЖИЛО")
        for name, effect in survived:
            print(f"     - «{name}» пройшов стенд → {effect}")
        return 1
    print(f"  мутанти стенда README: {total}/{total} спіймано")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
