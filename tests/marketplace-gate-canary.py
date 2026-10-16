#!/usr/bin/env python3
"""Канарки гейта маркетплейсу: доводять, що verify-marketplace.py ЛОВИТЬ поломки.

Правило 11 лабораторії: перевірка, яка лише проходить на чистому корпусі, не доводить
нічого. Тому кожен сценарій ламає копію репозиторію конкретним способом і вимагає,
щоб гейт впав саме на цьому.

ПЕРЕЛІК ІНЦИДЕНТІВ, які цей набір обіцяє закрити (не число, а список):
  1. битий симлінк скіла всередині плагіна
  2. скіл-сирота: є на диску, не входить у жоден плагін
  3. дубль: один скіл у двох плагінах
  4. розбіжність версії каталог ↔ plugin.json
  5. похідний лічильник в описі ≠ фактичній кількості скілів
  6. відсутній plugin.json у плагіна
  7. неіснуючий source плагіна
  8. зарезервоване Anthropic ім'я маркетплейсу
  9. схемна помилка манифеста (ловить claude plugin validate --strict)
 10. ціль симлінка поза межами маркетплейсу (Claude Code її мовчки пропустить)
 11. не-MIT ліцензія в SKILL.md
 12. не-MIT файл LICENSE
 13. не-MIT license у plugin.json
 14. відсутнє поле license у frontmatter скіла — навіть коли рядок «license: MIT»
     є в ТІЛІ (приклад шаблону не є метаданими скіла)
 15. симлінк скіла замінено копією каталогу (тихо ламає «єдине джерело правди»)
 16. --publish без claude CLI: схемна валідація неможлива, реліз не дозволено

КОНТРОЛІ (мусять ПРОХОДИТИ — інакше гейт просто завжди червоний):
  · чиста копія репозиторію;
  · без claude CLI і без --publish: попередження, а не помилка (так працює CI).

Сценарій 9 потребує claude CLI. Якщо його немає на машині, сценарій чесно
позначається «не ганявся», а не зараховується: без CLI він нічого б не довів.

Запуск: python3 tests/marketplace-gate-canary.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = "scripts/verify-marketplace.py"
HAVE_CLAUDE = shutil.which("claude") is not None
SCHEMA_SKIPPED_MARK = "схемну валідацію пропущено"  # той самий текст, що в гейті


def run_gate(root: Path, publish: bool = False, no_claude: bool = False) -> tuple[int, str]:
    """no_claude: гейт запускається з PATH без claude — імітація CI/релізної машини без CLI.

    Сам python викликається за абсолютним шляхом, тож PATH впливає лише на пошук `claude`.
    """
    cmd = [sys.executable, GATE] + (["--publish"] if publish else [])
    env = dict(os.environ)
    empty_bin = None
    if no_claude:
        empty_bin = tempfile.mkdtemp(prefix="no-claude-")
        env["PATH"] = empty_bin
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=300, env=env)
    finally:
        if empty_bin:
            shutil.rmtree(empty_bin, ignore_errors=True)
    return proc.returncode, proc.stdout + proc.stderr


def fresh_copy(dst: Path) -> Path:
    """Копія репо зі збереженням симлінків, без .git та кешів."""
    shutil.copytree(
        REPO, dst, symlinks=True,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"),
    )
    return dst


def edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --- сценарії поломок ---

def break_symlink(root: Path) -> None:
    link = root / "plugins" / "melania-build" / "skills" / "llm-api-builder"
    link.unlink()
    link.symlink_to("../../../melania-skills-ecosystem/skills/skill-that-does-not-exist")


def break_orphan(root: Path) -> None:
    (root / "plugins" / "melania-connect" / "skills" / "n8n-orchestrator").unlink()
    edit_json(
        root / ".claude-plugin" / "marketplace.json",
        lambda d: [
            e.update(description=e["description"].replace("(5 скілів)", "(4 скілів)"))
            for e in d["plugins"] if e["name"] == "melania-connect"
        ],
    )


def break_duplicate(root: Path) -> None:
    (root / "plugins" / "melania-build" / "skills" / "semantic-router").symlink_to(
        "../../../melania-skills-ecosystem/skills/semantic-router"
    )


def break_version(root: Path) -> None:
    edit_json(
        root / "plugins" / "melania-knowledge" / ".claude-plugin" / "plugin.json",
        lambda d: d.update(version="9.9.9"),
    )


def break_count(root: Path) -> None:
    edit_json(
        root / ".claude-plugin" / "marketplace.json",
        lambda d: [
            e.update(description=e["description"].replace("(7 скілів)", "(99 скілів)"))
            for e in d["plugins"] if e["name"] == "ai-lab-workflows"
        ],
    )


def break_missing_manifest(root: Path) -> None:
    (root / "plugins" / "melania-governance" / ".claude-plugin" / "plugin.json").unlink()


def break_missing_source(root: Path) -> None:
    shutil.rmtree(root / "plugins" / "melania-build")


def break_reserved_name(root: Path) -> None:
    edit_json(
        root / ".claude-plugin" / "marketplace.json",
        lambda d: d.update(name="anthropic-plugins"),
    )


def break_schema(root: Path) -> None:
    edit_json(
        root / "plugins" / "melania-connect" / ".claude-plugin" / "plugin.json",
        lambda d: d.update(keywords="не-масив"),
    )


def break_outside_target(root: Path) -> None:
    outside = root.parent / "outside-skill"
    outside.mkdir(exist_ok=True)
    (outside / "SKILL.md").write_text("---\nname: outside\n---\n", encoding="utf-8")
    link = root / "plugins" / "melania-build" / "skills" / "webapp-testing"
    link.unlink()
    link.symlink_to(outside)


def break_skill_license(root: Path) -> None:
    p = root / "melania-skills-ecosystem" / "skills" / "semantic-router" / "SKILL.md"
    p.write_text(p.read_text(encoding="utf-8").replace("license: MIT", "license: Proprietary", 1),
                 encoding="utf-8")


def break_license_file(root: Path) -> None:
    (root / "LICENSE").write_text("Apache License\nVersion 2.0\n", encoding="utf-8")


def break_manifest_license(root: Path) -> None:
    edit_json(
        root / "plugins" / "melania-knowledge" / ".claude-plugin" / "plugin.json",
        lambda d: d.update(license="Apache-2.0"),
    )


def break_missing_license(root: Path) -> None:
    """Поле прибрано з frontmatter, але «license: MIT» лишається В ТІЛІ (приклад).

    Найважчий випадок у межах твердження «кожен скіл декларує MIT»: наївний пошук по всьому
    файлу цю поломку пропустив би, бо знайшов би рядок у прикладі.
    """
    p = root / ".claude" / "skills" / "experiment" / "SKILL.md"
    text = p.read_text(encoding="utf-8")
    text, n = re.subn(r"^license: MIT\n", "", text, count=1, flags=re.M)
    assert n == 1, "канарка: у frontmatter experiment немає license — нічого ламати"
    p.write_text(text + "\n## Приклад\n\n```yaml\nlicense: MIT\n```\n", encoding="utf-8")


def break_symlink_replaced_by_copy(root: Path) -> None:
    link = root / "plugins" / "melania-build" / "skills" / "llm-api-builder"
    real = link.resolve()
    link.unlink()
    shutil.copytree(real, link)  # справжня копія замість симлінка


def break_nothing(root: Path) -> None:
    """Порожня поломка: сценарій ламає лише СЕРЕДОВИЩЕ (немає claude), не файли."""


# (назва, ламач, очікуваний фрагмент, --publish, без claude у PATH, потребує claude)
SCENARIOS = [
    ("1. битий симлінк", break_symlink, "битий симлінк", False, False, False),
    ("2. скіл-сирота", break_orphan, "не входять у жоден плагін", False, False, False),
    ("3. дубль скіла", break_duplicate, "дубльовано", False, False, False),
    ("4. дрейф версії", break_version, "версія в каталозі", False, False, False),
    ("5. дрейф лічильника", break_count, "опис обіцяє", False, False, False),
    ("6. немає plugin.json", break_missing_manifest, "немає .claude-plugin/plugin.json", False, False, False),
    ("7. немає source", break_missing_source, "не існує", False, False, False),
    ("8. зарезервоване ім'я", break_reserved_name, "зарезервоване", False, False, False),
    ("9. схемна помилка", break_schema, "validate --strict впав", False, False, True),
    ("10. ціль поза маркетплейсом", break_outside_target, "поза маркетплейсом", False, False, False),
    ("11. не-MIT у SKILL.md", break_skill_license, "політика MIT порушена", False, False, False),
    ("12. не-MIT файл LICENSE", break_license_file, "LICENSE: не MIT", False, False, False),
    ("13. не-MIT у plugin.json", break_manifest_license, "license у plugin.json", False, False, False),
    ("14. немає license у frontmatter", break_missing_license, "'<відсутнє>' у experiment", False, False, False),
    ("15. симлінк замінено копією", break_symlink_replaced_by_copy, "не симлінк", False, False, False),
    ("16. --publish без claude CLI", break_nothing, "у режимі публікації це помилка", True, True, False),
]


def main() -> int:
    failures: list[str] = []
    skipped: list[str] = []
    controls = 0

    with tempfile.TemporaryDirectory() as tmp:
        control = fresh_copy(Path(tmp) / "control")

        # Контроль 1: чиста копія проходить. Без claude гейт лише попереджає (це нормально),
        # тож вимога до контролю — exit 0, а не відсутність попереджень.
        rc, out = run_gate(control)
        if rc != 0:
            failures.append(f"КОНТРОЛЬ 1: чиста копія не пройшла гейт (exit={rc})\n{out}")
            print("✗ контроль 1: чиста копія має проходити — не пройшла")
        else:
            controls += 1
            print("✓ контроль 1: чиста копія проходить (exit 0)")

        # Контроль 2: без claude і без --publish — попередження, НЕ помилка. Без цього
        # контролю виправлення №16 могло б непомітно зробити гейт червоним у CI.
        rc, out = run_gate(control, publish=False, no_claude=True)
        if rc == 0 and SCHEMA_SKIPPED_MARK in out:
            controls += 1
            print("✓ контроль 2: без claude і без --publish — видиме попередження, exit 0")
        else:
            failures.append(
                f"КОНТРОЛЬ 2: очікували exit 0 + попередження «{SCHEMA_SKIPPED_MARK}», "
                f"маємо exit={rc}\n{out}")
            print("✗ контроль 2: без claude звичайний прогін мусить лише попереджати")

    for label, breaker, expect, publish, no_claude, needs_claude in SCENARIOS:
        if needs_claude and not HAVE_CLAUDE:
            skipped.append(label)
            print(f"⊘ {label}: не ганявся — claude CLI відсутній на цій машині "
                  "(без нього сценарій нічого б не довів)")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            root = fresh_copy(Path(tmp) / "repo")
            breaker(root)
            rc, out = run_gate(root, publish=publish, no_claude=no_claude)
            if rc == 0:
                failures.append(f"{label}: гейт ПРОПУСТИВ поломку (exit 0)")
                print(f"✗ {label}: гейт пропустив поломку")
            elif expect not in out:
                failures.append(f"{label}: гейт впав, але не на очікуваному ({expect!r})\n{out}")
                print(f"✗ {label}: впав не на тому — очікували {expect!r}")
            else:
                print(f"✓ {label}: спіймано")

    print()
    caught = len(SCENARIOS) - len(skipped)
    if failures:
        print(f"КАНАРКИ НЕ ПРОЙДЕНО: {len(failures)} проблем(и)")
        for f in failures:
            print(f"  — {f}")
        return 1
    tail = f" · НЕ ГАНЯЛОСЬ: {len(skipped)} ({'; '.join(skipped)})" if skipped else ""
    print(f"КАНАРКИ ПРОЙДЕНО: {caught} поломок спіймано + {controls} контролі чисті{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
