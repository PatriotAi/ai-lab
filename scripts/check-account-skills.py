#!/usr/bin/env python3
"""check-account-skills.py — чи не старші скіли, змонтовані в акаунті, за канон.

НАВІЩО. Скіли, які claude.ai монтує в сесію (`~/.claude/skills/synced/…`), — копії,
колись завантажені власником. Канон — `melania-skills-ecosystem/MANIFEST.json` на
диску. 2026-10-17 виміряно: 28 із 28 змонтованих скілів melania старші за канон
(`pre-delivery-gate` 1.1.0 → 1.5.0), і цього не бачила жодна перевірка — дрейф
тримався лише на уважності агента (Core Rule 15). Скрипт робить його видимим одним
рядком на старті сесії.

ПЕРЕЛІК ІНЦИДЕНТІВ, які він закриває (а не число канарок):
1. старша копія мовчала — тепер рядок із числом і прикладами;
2. перший підрахунок дав хибний нуль: у змонтованих скілах версія лежить у
   вкладеному `metadata.version`, а читалось лише `^version:` — тепер версія
   береться з frontmatter на будь-якому відступі;
3. фільтр пропускав скіли, у яких версія лише в H1 (`# Назва — vX.Y.Z`) — тепер
   H1 теж джерело;
4. скіл без версії рахувався «свіжим» — тепер його названо, а не сховано.
5. (рев'ю Codex, PR #93) монтування буває у двох розкладках — Claude Code
   (`~/.claude/skills/synced/<група>/<назва>/`) і claude.ai (`/mnt/skills/user/<назва>/`,
   так його описує канон melania) — шукаємо в обох; prerelease-копія `1.5.0-alpha.1`
   старша за реліз `1.5.0`; файл із невалідним UTF-8 не обриває обхід решти скілів;
   (друге рев'ю) кожна копія перевіряється — рівна не ховає застарілу; порядок
   prerelease — повний за SemVer; маніфест іншої структури — облік, а не збій;
   (третє рев'ю) версія канону не за SemVer — скіл пропускається, а не обриває скрипт.
   Три рев'ю поспіль знаходили новий вхід, що ламав «код виходу 0», тому клас закрито
   й загалом: непередбачена помилка дає рядок «перевірку не виконано» і код 0.
6. (власне рев'ю, коли Codex вичерпав ліміт) версія з H1 — лише з першого заголовка поза
   блоками коду, а не з коментаря `# … v9.0.0`; у frontmatter — верхній `version:` чи
   `metadata.version`, а не перший-ліпший вкладений (версія залежності); копія без версії
   не ховає застарілу сусідню; `1.5` = `1.5.0`; файл із BOM не губить frontmatter.
Монтування нема або все рівне канону — тиша: жодного токена в контекст сесії.

ЧЕСНА МЕЖА. Скрипт лише показує дрейф. Оновити копії може тільки власник:
`maintain.py package` готує пакети, завантаження в claude.ai — його дія.

Запуск: python3 scripts/check-account-skills.py [--mounts ГЛОБ] [--manifest ШЛЯХ]
Змінна ACCOUNT_SKILLS_GLOB перевизначає глоби монтування (через `:`, для тестів).
Код виходу — завжди 0 (облік, не блок); рядок у stdout — лише коли є що сказати.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Дві розкладки монтування: Claude Code і claude.ai.
DEFAULT_GLOBS = "~/.claude/skills/synced/*/*/SKILL.md:/mnt/skills/user/*/SKILL.md"
SEMVER = r"(\d+(?:\.\d+)+(?:-[0-9A-Za-z.-]+)?)"
VERSION_TOP = re.compile(r"^version:\s*['\"]?" + SEMVER, re.M)
VERSION_META = re.compile(r"^metadata:[^\n]*\n(?:[ \t]+[^\n]*\n)*?[ \t]+version:\s*['\"]?" + SEMVER, re.M)
FENCE = re.compile(r"^```.*?^```", re.M | re.S)
H1 = re.compile(r"^#\s[^\n]*", re.M)
H1_VERSION = re.compile(r"\bv" + SEMVER)


def mounted_version(text: str) -> str | None:
    """Версія змонтованого скіла: верхній `version:` чи `metadata.version` у frontmatter,
    інакше перший заголовок поза блоками коду."""
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        fm = text[3:end] + "\n" if end > 0 else ""
        for rx in (VERSION_TOP, VERSION_META):
            m = rx.search(fm)
            if m:
                return m.group(1)
        body = text[end + 4:] if end > 0 else text
    body = FENCE.sub("", body)                  # `# … v9.0.0` у блоці коду — не заголовок
    h1 = H1.search(body)
    m = H1_VERSION.search(h1.group(0)) if h1 else None
    return m.group(1) if m else None


def key(version: str) -> tuple:
    """Ключ порівняння за SemVer: числа; реліз вище за prerelease (`1.5.0-alpha.1` < `1.5.0`);
    між prerelease — поштучно, числа як числа (`alpha.2` < `alpha.10`), числові нижче за текстові."""
    core, _, pre = version.partition("-")
    nums = tuple(int(part) for part in core.split("."))
    while len(nums) > 1 and nums[-1] == 0:      # `1.5` = `1.5.0`
        nums = nums[:-1]
    if not pre:
        return nums, 1, ()
    return nums, 0, tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mounts", default=os.environ.get("ACCOUNT_SKILLS_GLOB", DEFAULT_GLOBS))
    ap.add_argument("--manifest", default=str(ROOT / "melania-skills-ecosystem" / "MANIFEST.json"))
    args = ap.parse_args(argv[1:])
    try:
        skills = json.loads(Path(args.manifest).read_text(encoding="utf-8")).get("skills", {})
        canon = ({name: meta.get("version") for name, meta in skills.items()}
                 if isinstance(skills, dict) else {s.get("name"): s.get("version") for s in skills})
    except (OSError, ValueError, AttributeError, TypeError):
        return 0                                # нема канону чи інша структура — облік, не збій
    # Кожна змонтована копія: той самий скіл у двох розкладках — дві копії, і
    # рівна канону не має ховати застарілу (друге рев'ю Codex, PR #93).
    copies: dict[str, list[str | None]] = {}
    paths = sorted({p for g in args.mounts.split(":") if g for p in glob.glob(os.path.expanduser(g))})
    for path in paths:
        name = os.path.basename(os.path.dirname(path))
        if not isinstance(canon.get(name), str) or not re.fullmatch(SEMVER, canon[name]):
            continue                            # не скіл melania чи версія канону не SemVer
        try:
            # Невалідний UTF-8 в одному файлі не має обривати обхід решти.
            ver = mounted_version(Path(path).read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            ver = None
        copies.setdefault(name, []).append(ver)
    total, older, unknown = len(copies), [], []
    for name, versions in copies.items():
        known = [v for v in versions if v is not None]
        if len(known) < len(versions):
            unknown.append(name)                # копія без версії не ховає застарілу сусідню
        oldest = min(known, key=key, default=None)
        if oldest and key(oldest) < key(canon[name]):
            older.append((name, oldest, canon[name]))
    if not older and not unknown:
        return 0
    parts = []
    if older:
        sample = ", ".join(f"{n} {a} → {b}" for n, a, b in older[:3])
        parts.append(f"{len(older)} із {total} старші за канон ({sample}"
                     f"{', …' if len(older) > 3 else ''})")
    if unknown:
        parts.append(f"версію не знайдено: {', '.join(unknown[:5])}")
    print("⚠️ Скіли акаунта: " + "; ".join(parts) + ". Працюю за каноном із диска; "
          "оновити копії — `maintain.py package` і завантаження в claude.ai (дія власника).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as exc:                    # контракт «код 0» тримається й на непередбаченому вході
        print(f"⚠️ Скіли акаунта: перевірку не виконано ({type(exc).__name__}: {exc}). "
              "Детектор — scripts/check-account-skills.py; канон — на диску.")
        raise SystemExit(0)
