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
 11. розбіжність ліцензій у режимі --publish

Запуск: python3 tests/marketplace-gate-canary.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = "scripts/verify-marketplace.py"


def run_gate(root: Path, publish: bool = False) -> tuple[int, str]:
    cmd = [sys.executable, GATE] + (["--publish"] if publish else [])
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=300)
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


# --- сценарії поломок: (назва, функція-ламач, очікуваний фрагмент у виводі, --publish) ---

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


def break_nothing(root: Path) -> None:
    """Контроль: чиста копія має проходити (інакше гейт просто завжди червоний)."""


SCENARIOS = [
    ("1. битий симлінк", break_symlink, "битий симлінк", False),
    ("2. скіл-сирота", break_orphan, "не входять у жоден плагін", False),
    ("3. дубль скіла", break_duplicate, "дубльовано", False),
    ("4. дрейф версії", break_version, "версія в каталозі", False),
    ("5. дрейф лічильника", break_count, "опис обіцяє", False),
    ("6. немає plugin.json", break_missing_manifest, "немає .claude-plugin/plugin.json", False),
    ("7. немає source", break_missing_source, "не існує", False),
    ("8. зарезервоване ім'я", break_reserved_name, "зарезервоване", False),
    ("9. схемна помилка", break_schema, "validate --strict впав", False),
    ("10. ціль поза маркетплейсом", break_outside_target, "поза маркетплейсом", False),
    ("11. дрейф ліцензій (--publish)", break_nothing, "ліцензії скілів розходяться", True),
]


def main() -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        control = fresh_copy(Path(tmp) / "control")
        rc, out = run_gate(control)
        if rc != 0:
            failures.append(f"КОНТРОЛЬ: чиста копія не пройшла гейт (exit={rc})\n{out}")
            print("✗ контроль: чиста копія має проходити — не пройшла")
        else:
            print("✓ контроль: чиста копія проходить (exit 0)")

    for label, breaker, expect, publish in SCENARIOS:
        with tempfile.TemporaryDirectory() as tmp:
            root = fresh_copy(Path(tmp) / "repo")
            breaker(root)
            rc, out = run_gate(root, publish=publish)
            if rc == 0:
                failures.append(f"{label}: гейт ПРОПУСТИВ поломку (exit 0)")
                print(f"✗ {label}: гейт пропустив поломку")
            elif expect not in out:
                failures.append(f"{label}: гейт впав, але не на очікуваному ({expect!r})\n{out}")
                print(f"✗ {label}: впав не на тому — очікували {expect!r}")
            else:
                print(f"✓ {label}: спіймано")

    print()
    if failures:
        print(f"КАНАРКИ НЕ ПРОЙДЕНО: {len(failures)} з {len(SCENARIOS) + 1}")
        for f in failures:
            print(f"  — {f}")
        return 1
    print(f"КАНАРКИ ПРОЙДЕНО: {len(SCENARIOS)} поломок спіймано + контроль чистий")
    return 0


if __name__ == "__main__":
    sys.exit(main())
