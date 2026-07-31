#!/usr/bin/env python3
"""mutation-classify.py — гейт для гейта (Фаза S5.2).

ПИТАННЯ, НА ЯКЕ ВІН ВІДПОВІДАЄ. У наборі 232 перевірки, і всі зелені. Але чи
ловлять вони хоч щось? Зелений набір на цілому коді не доводить нічого — рівно
як «✓ усі перевірки чисті» при невстановлених сканерах (дефект F-2). Єдиний
спосіб дізнатись — **зламати код навмисно** й побачити, чи набір це помітить.

Мутант, який ПРОЙШОВ перевірки, — це діра в перевірках, а не в коді.

МОДЕЛЬ GOOGLE: мутувати **змінений** код, а не всю базу
(`docs/security/research-2026-07.md` §I.1). Тут мутується лише
`security/spine/classify.py` — серце класифікації, з якого випливає все інше.

БЕЗПЕКА ПРОГОНУ. Мутації застосовуються ТІЛЬКИ до копії в тимчасовій теці.
Робочі файли не чіпаються ніколи — це пряме правило `tests/README.md`, записане
після інциденту, коли канарка на робочому файлі стерла незакомічену роботу.

Запуск: python3 tests/mutation-classify.py [--verbose]
Код виходу: 0 — кожен мутант спійманий · 1 — хтось вижив (діра в перевірках).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "security/spine/classify.py"

# Кожна мутація — правдоподібна помилка, а не випадковий шум: те, що реально
# міг би зробити автор поспіхом. Опис пояснює, ЯКУ саме перевірку вона має
# розбудити — якщо мутант виживе, значить цієї перевірки насправді немає.
MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "правило шляхів вимкнено",
        "            if raw_path and _match_path(pattern, rel_target, raw_path):",
        "            if False and _match_path(pattern, rel_target, raw_path):",
        "захищені шляхи (.env, workflows, settings) перестають бути R4",
    ),
    (
        "правило команд вимкнено",
        "            if command and needle.lower() in exec_part.lower():",
        "            if False and needle.lower() in exec_part.lower():",
        "push --force, rm -rf, --no-verify перестають бути R4",
    ),
    (
        "виняток поглинає все",
        "        if command and any(exc in exec_part.lower() for exc in exceptions):",
        "        if command:",
        "будь-яка команда обходить усі правила через гілку винятків",
    ),
    (
        "симлінк не розрізається",
        "        if candidate.is_symlink():",
        "        if False:",
        "GhostApproval: рішення ухвалюється за назвою, а не за реальною ціллю",
    ),
    (
        "виконувана частина = порожньо",
        "    stripped = _QUOTED.sub(\" \", _HEREDOC.sub(r\"\\1\", command))",
        "    stripped = \"\"",
        "жодна команда не збігається з правилами — усе стає R2",
    ),
    (
        "ознака виконання ігнорується",
        "    if any(inv in stripped.lower() for inv in SHELL_INVOKERS):",
        "    if False:",
        "bash -c \"rm -rf\" стає невидимим — справжній пропуск",
    ),
    (
        "MCP: незворотне стає читанням",
        "        if any(v in low for v in mcp.get(\"irreversible_verbs\", [])):",
        "        if False:",
        "злиття PR, деплой, видалення проходять без питань",
    ),
    (
        "MCP: невідоме вважається безпечним",
        "        return Verdict(\"R2\", f\"MCP-інструмент невідомого класу ({tool_name})\",",
        "        return Verdict(\"R0\", f\"MCP-інструмент невідомого класу ({tool_name})\",",
        "незнайомий інструмент отримує найнижчий рівень",
    ),
    (
        "запис поза репо дозволено",
        "        if outside:\n            return Verdict(\"R4\", \"запис ПОЗА межами репозиторію\",",
        "        if False:\n            return Verdict(\"R4\", \"запис ПОЗА межами репозиторію\",",
        "будь-який шлях поза проєктом стає звичайною правкою",
    ),
    (
        "операції запису не рахуються",
        "                if any(op in stripped for op in WRITE_OPS):",
        "                if False:",
        "`cat > файл` знову вважається читанням",
    ),
]

# Перевірки, якими полюємо на мутантів. Кожна має відпрацювати в пісочниці
# без жодного файлу лабораторії, крім скопійованих.
HUNTERS = [
    ("property-classify.py", ["--cases", "60"]),
    ("probe-classify.py", []),
    ("probe-mcp-and-quotes.py", []),
]


def build_sandbox(tmp: Path) -> Path:
    """Копія лише того, що потрібно перевіркам. Робочі файли недоторкані."""
    sandbox = tmp / "repo"
    (sandbox / "tests").mkdir(parents=True)
    shutil.copytree(ROOT / "security", sandbox / "security",
                    ignore=shutil.ignore_patterns("audit", "tests"))
    for name, _ in HUNTERS:
        shutil.copy(ROOT / "tests" / name, sandbox / "tests" / name)
    return sandbox


def hunt(sandbox: Path) -> tuple[bool, str]:
    """Чи спіймав хоч один мисливець? Повертає (спіймано, ким саме)."""
    for name, extra in HUNTERS:
        res = subprocess.run([sys.executable, str(sandbox / "tests" / name), *extra],
                             capture_output=True, text=True, cwd=sandbox, timeout=180)
        if res.returncode != 0:
            return True, name
    return False, ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv[1:])

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sandbox = build_sandbox(tmp)
        original = (sandbox / TARGET).read_text(encoding="utf-8")

        # Контроль: на ЦІЛОМУ коді мисливці мають мовчати. Якщо ні — вони
        # реагують на щось інше, і подальші результати нічого не варті.
        caught, who = hunt(sandbox)
        if caught:
            print(f"  ❌ на цілому коді впав {who} — прогін недійсний")
            return 1

        survived: list[tuple[str, str]] = []
        killed = 0
        for name, old, new, effect in MUTATIONS:
            if old not in original:
                print(f"  ⚠️  мутація «{name}» не застосовна — цільовий рядок змінився")
                survived.append((name, "цільовий рядок не знайдено"))
                continue
            (sandbox / TARGET).write_text(original.replace(old, new, 1), encoding="utf-8")
            caught, who = hunt(sandbox)
            (sandbox / TARGET).write_text(original, encoding="utf-8")
            if caught:
                killed += 1
                if args.verbose:
                    print(f"  ✅ {name} — спіймав {who}")
            else:
                survived.append((name, effect))

    total = len(MUTATIONS)
    if survived:
        print(f"  ❌ мутанти: {killed}/{total} спіймано, {len(survived)} ВИЖИЛО")
        for name, effect in survived:
            print(f"     - «{name}» пройшов усі перевірки → {effect}")
        print("     Мутант, що вижив, — діра в ПЕРЕВІРКАХ, не в коді.")
        return 1
    print(f"  мутаційне тестування: {killed}/{total} мутантів спіймано")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
