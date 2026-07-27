#!/usr/bin/env python3
"""Гейт цілісності маркетплейсу плагінів patriotai-lab.

Read-only. Exit 0 — усе зійшлося; exit 1 — є розбіжність.
Перевіряє те, що інакше трималося б лише на уважності автора:
джерела плагінів, резолв симлінків, покриття скілів, похідні лічильники,
збіг версій, збіг ліцензій (з --publish — блокує).

Використання:
    python3 scripts/verify-marketplace.py            # структурний гейт
    python3 scripts/verify-marketplace.py --publish  # + гейт готовності до публікації
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
MELANIA_SKILLS = ROOT / "melania-skills-ecosystem" / "skills"
LAB_SKILLS = ROOT / ".claude" / "skills"

# Зарезервовані Anthropic імена маркетплейсів (docs/en/plugin-marketplaces).
RESERVED = {
    "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
    "claude-plugins-community", "claude-community", "anthropic-marketplace",
    "anthropic-plugins", "agent-skills", "anthropic-agent-skills",
    "knowledge-work-plugins", "life-sciences", "claude-for-legal",
    "claude-for-financial-services", "financial-services-plugins",
    "first-party-plugins", "healthcare",
}

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def load_marketplace() -> dict:
    if not MARKETPLACE.exists():
        err(f"немає {MARKETPLACE.relative_to(ROOT)}")
        return {}
    try:
        return json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(f"marketplace.json не парситься: {exc}")
        return {}


def check_marketplace_head(mp: dict) -> None:
    for field in ("name", "owner", "plugins"):
        if field not in mp:
            err(f"marketplace.json: немає обов'язкового поля '{field}'")
    name = mp.get("name", "")
    if name in RESERVED:
        err(f"marketplace.json: ім'я '{name}' зарезервоване Anthropic — маркетплейс не завантажиться")
    if name and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        err(f"marketplace.json: ім'я '{name}' не kebab-case")
    owner = mp.get("owner")
    if isinstance(owner, dict) and not owner.get("name"):
        err("marketplace.json: owner.name обов'язковий")


def declared_skills(entry: dict, pdir: Path) -> list[str]:
    """Скіли, які плагін реально віддає: симлінки/теки в skills/."""
    sk = pdir / "skills"
    if not sk.is_dir():
        return []
    return sorted(p.name for p in sk.iterdir() if not p.name.startswith("."))


def check_plugin(entry: dict, seen: dict[str, str]) -> None:
    name = entry.get("name", "<без-імені>")
    source = entry.get("source")
    if not isinstance(source, str) or not source.startswith("./"):
        # github/url/npm-джерела цей гейт не резолвить локально — перевіряє лише те, що в репо
        warn(f"{name}: зовнішнє джерело {source!r} — локально не перевіряється")
        return
    pdir = (ROOT / source[2:]).resolve()
    if not pdir.is_dir():
        err(f"{name}: source '{source}' не існує")
        return
    if ROOT not in pdir.parents and pdir != ROOT:
        err(f"{name}: source '{source}' виходить за корінь маркетплейсу")
        return

    manifest_path = pdir / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        err(f"{name}: немає .claude-plugin/plugin.json")
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(f"{name}: plugin.json не парситься: {exc}")
        return

    if manifest.get("name") != name:
        err(f"{name}: plugin.json name='{manifest.get('name')}' ≠ ім'я в каталозі '{name}'")
    if entry.get("version") and manifest.get("version") != entry.get("version"):
        err(f"{name}: версія в каталозі {entry.get('version')} ≠ версія в plugin.json {manifest.get('version')}")

    skills = declared_skills(entry, pdir)
    if not skills:
        err(f"{name}: жодного скіла в skills/")
    for s in skills:
        link = pdir / "skills" / s
        target = link.resolve()
        if not target.exists():
            err(f"{name}/{s}: битий симлінк → {os.readlink(link) if link.is_symlink() else '?'}")
            continue
        if ROOT not in target.parents:
            err(f"{name}/{s}: ціль поза маркетплейсом ({target}) — Claude Code пропустить її при встановленні")
            continue
        if not (target / "SKILL.md").is_file():
            err(f"{name}/{s}: немає SKILL.md")
            continue
        if s in seen:
            err(f"скіл '{s}' дубльовано: {seen[s]} і {name}")
        else:
            seen[s] = name

    # похідний лічильник у описі: «(N скілів)» мусить дорівнювати фактові
    desc = entry.get("description", "")
    m = re.search(r"\((\d+)\s+скіл", desc)
    if m and int(m.group(1)) != len(skills):
        err(f"{name}: опис обіцяє {m.group(1)} скілів, фактично {len(skills)}")


def check_coverage(seen: dict[str, str]) -> None:
    available: set[str] = set()
    if MELANIA_SKILLS.is_dir():
        available |= {p.name for p in MELANIA_SKILLS.iterdir() if (p / "SKILL.md").is_file()}
    if LAB_SKILLS.is_dir():
        available |= {
            p.name for p in LAB_SKILLS.iterdir()
            if not p.is_symlink() and (p / "SKILL.md").is_file()
        }
    orphans = sorted(available - set(seen))
    if orphans:
        err(f"скіли є на диску, але не входять у жоден плагін: {', '.join(orphans)}")
    ghosts = sorted(set(seen) - available)
    if ghosts:
        err(f"плагіни віддають скіли, яких немає в джерелі: {', '.join(ghosts)}")


def check_cli_validate(mp: dict) -> None:
    """Офіційний валідатор — джерело істини щодо схеми."""
    claude = None
    for candidate in ("claude",):
        try:
            subprocess.run([candidate, "--version"], capture_output=True, check=True, timeout=60)
            claude = candidate
            break
        except (OSError, subprocess.SubprocessError):
            pass
    if claude is None:
        warn("claude CLI недоступний — схемну валідацію пропущено")
        return
    targets = [ROOT] + [
        ROOT / e["source"][2:]
        for e in mp.get("plugins", [])
        if isinstance(e.get("source"), str) and e["source"].startswith("./")
    ]
    for t in targets:
        proc = subprocess.run(
            [claude, "plugin", "validate", str(t), "--strict"],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip().splitlines()
            err(f"claude plugin validate --strict впав на {t.name}: {tail[-1] if tail else '?'}")


def check_licenses(publish: bool) -> None:
    """Ліцензії скілів мусять бути однорідні до публікації."""
    values: dict[str, list[str]] = {}
    for base in (MELANIA_SKILLS, LAB_SKILLS):
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.is_symlink() or not (p / "SKILL.md").is_file():
                continue
            m = re.search(r"^license:\s*(.+)$", (p / "SKILL.md").read_text(encoding="utf-8"), re.M)
            if m:
                values.setdefault(m.group(1).strip(), []).append(p.name)
    if len(values) > 1:
        summary = "; ".join(f"{k!r}×{len(v)}" for k, v in sorted(values.items()))
        msg = f"ліцензії скілів розходяться ({summary}) — публікація маркетплейсу вимагає одного рішення власника"
        (err if publish else warn)(msg)


def main() -> int:
    publish = "--publish" in sys.argv
    mp = load_marketplace()
    if mp:
        check_marketplace_head(mp)
        seen: dict[str, str] = {}
        for entry in mp.get("plugins", []):
            check_plugin(entry, seen)
        check_coverage(seen)
        check_cli_validate(mp)
        check_licenses(publish)
        print(f"маркетплейс: {mp.get('name')} · плагінів: {len(mp.get('plugins', []))} · скілів: {len(seen)}")

    for w in warnings:
        print(f"  ⚠ {w}")
    for e in errors:
        print(f"  ✗ {e}")
    if errors:
        print(f"ГЕЙТ НЕ ПРОЙДЕНО: {len(errors)} помилк(и)")
        return 1
    print("ГЕЙТ ПРОЙДЕНО" + (" (режим публікації)" if publish else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
