#!/usr/bin/env python3
"""Гейт цілісності маркетплейсу плагінів patriotai-lab.

Read-only. Exit 0 — усе зійшлося; exit 1 — є розбіжність.
Перевіряє те, що інакше трималося б лише на уважності автора:
джерела плагінів, резолв симлінків (бандл МУСИТЬ бути симлінком на джерело правди,
не копією), покриття скілів, похідні лічильники, збіг версій, політика MIT
(кожен SKILL.md декларує MIT у frontmatter; відсутнє поле — теж порушення).

Схемна валідація (`claude plugin validate --strict`) потребує claude CLI. Без нього:
у звичайному прогоні — видиме попередження (структурні перевірки лишаються корисними,
так працює CI), у режимі --publish — ПОМИЛКА.

Використання:
    python3 scripts/verify-marketplace.py            # звичайний гейт
    python3 scripts/verify-marketplace.py --publish  # + claude CLI обов'язковий
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
        if not link.is_symlink():
            # Копія каталогу замість симлінка тихо ламає «єдине джерело правди»: resolve()
            # повертає її саму, усі подальші перевірки (покриття за іменем, SKILL.md) проходять,
            # а зміни в справжньому скілі перестають доходити до бандла.
            err(f"{name}/{s}: не симлінк — бандл мусить вказувати на джерело правди, а не тримати копію")
            continue
        target = link.resolve()
        if not target.exists():
            err(f"{name}/{s}: битий симлінк → {os.readlink(link)}")
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


# Мітка, за якою tests/run-tests.sh розпізнає, що схемна валідація НЕ ганялась, і
# показує це як «не ганялось», а не як зелене. Змінюєш текст — змінюй і там.
SCHEMA_SKIPPED_MARK = "схемну валідацію пропущено"


def check_cli_validate(mp: dict, publish: bool = False) -> None:
    """Офіційний валідатор — джерело істини щодо схеми.

    Плагіни перевіряються на РОЗІМЕНОВАНІЙ копії (`cp -rL`). Починаючи з Claude Code
    v2.1.283 `plugin validate` не йде за симлінками і сам радить «validate the real
    paths separately»; на копії з реальними файлами `--strict` лишається строгим і
    жодне попередження не доводиться пробачати.

    Без `claude` CLI схемна валідація неможлива. У звичайному прогоні це ВИДИМЕ
    попередження (структурні перевірки лишаються корисними на машині без CLI — так
    працює CI). У режимі `--publish` це ПОМИЛКА: реліз без схемної перевірки міг би
    випустити зламаний маніфест, а гейт готовності до публікації мав би саме цьому
    запобігати.
    """
    claude = None
    try:
        subprocess.run(["claude", "--version"], capture_output=True, check=True, timeout=60)
        claude = "claude"
    except (OSError, subprocess.SubprocessError):
        msg = f"claude CLI недоступний — {SCHEMA_SKIPPED_MARK}"
        if publish:
            err(msg + " (у режимі публікації це помилка: без схемної перевірки реліз не дозволено)")
        else:
            warn(msg)
        return

    def run(target: Path, label: str) -> None:
        proc = subprocess.run([claude, "plugin", "validate", str(target), "--strict"],
                              capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            lines = [l.strip() for l in (proc.stdout + proc.stderr).splitlines() if l.strip()]
            detail = next((l for l in lines if l.startswith(">")), lines[-1] if lines else "?")
            err(f"claude plugin validate --strict впав на {label}: {detail}")

    run(ROOT, "каталог маркетплейсу")
    with tempfile.TemporaryDirectory() as tmp:
        for entry in mp.get("plugins", []):
            source = entry.get("source")
            if not (isinstance(source, str) and source.startswith("./")):
                continue
            src = ROOT / source[2:]
            if not src.is_dir():
                continue
            dst = Path(tmp) / src.name
            try:
                shutil.copytree(src, dst, symlinks=False)  # розіменовує симлінки
            except (OSError, shutil.Error) as exc:
                # найчастіша причина — битий симлінк, який уже названо вище;
                # головне не впасти трасбеком, бо тоді решта звіту не друкується
                err(f"{entry.get('name', src.name)}: не вдалося зібрати копію для валідації ({exc})")
                continue
            run(dst, entry.get("name", src.name))



def frontmatter_license(text: str) -> str | None:
    """Значення `license:` із YAML-frontmatter (між першою парою `---`), або None."""
    fm = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not fm:
        return None
    m = re.search(r"^license:[ \t]*(.+?)[ \t]*$", fm.group(1), re.M)
    return m.group(1).strip() if m else None


def check_licenses() -> None:
    """Політика лабораторії: MIT скрізь, однаково на кожному рівні.

    Це вже не «попередження перед публікацією», а інваріант: рішення власника від
    2026-09-28. Тому будь-яке відхилення — помилка, а не warning: інакше наступний
    скіл тихо принесе іншу ліцензію, як це вже сталося (чотири різні значення у 28 файлах).
    """
    # 1. файли ліцензій
    for lic in (ROOT / "LICENSE", ROOT / "melania-skills-ecosystem" / "LICENSE.txt"):
        if not lic.exists():
            err(f"{lic.relative_to(ROOT)}: файл ліцензії відсутній")
        elif not lic.read_text(encoding="utf-8").lstrip().startswith("MIT License"):
            err(f"{lic.relative_to(ROOT)}: не MIT")

    # 2. поле license: у frontmatter кожного SKILL.md. Відсутнє поле — теж порушення:
    #    політика «MIT скрізь» вимагає, щоб КОЖЕН скіл її декларував, а не лише щоб
    #    ті, що декларують, не суперечили. Читаємо саме frontmatter: рядок «license: MIT»
    #    у тілі (приклад шаблону, цитата) не є метаданими скіла.
    offenders: dict[str, list[str]] = {}
    for base in (MELANIA_SKILLS, LAB_SKILLS):
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.is_symlink() or not (p / "SKILL.md").is_file():
                continue
            value = frontmatter_license((p / "SKILL.md").read_text(encoding="utf-8"))
            if value != "MIT":
                offenders.setdefault(value if value is not None else "<відсутнє>", []).append(p.name)
    if offenders:
        summary = "; ".join(f"{k!r} у {', '.join(sorted(v))}" for k, v in sorted(offenders.items()))
        err(f"політика MIT порушена — ліцензія не MIT або не задекларована: {summary}")

    # 3. маніфести плагінів і записи каталогу
    try:
        mp = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for entry in mp.get("plugins", []):
        if entry.get("license") != "MIT":
            err(f"{entry.get('name')}: license у каталозі = {entry.get('license')!r}, очікували 'MIT'")
        source = entry.get("source")
        if isinstance(source, str) and source.startswith("./"):
            pj = ROOT / source[2:] / ".claude-plugin" / "plugin.json"
            if pj.exists():
                try:
                    if json.loads(pj.read_text(encoding="utf-8")).get("license") != "MIT":
                        err(f"{entry.get('name')}: license у plugin.json ≠ 'MIT'")
                except json.JSONDecodeError:
                    pass



def main() -> int:
    publish = "--publish" in sys.argv
    mp = load_marketplace()
    if mp:
        check_marketplace_head(mp)
        seen: dict[str, str] = {}
        for entry in mp.get("plugins", []):
            check_plugin(entry, seen)
        check_coverage(seen)
        check_cli_validate(mp, publish)
        check_licenses()
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
