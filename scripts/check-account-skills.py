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
Монтування нема або все рівне канону — тиша: жодного токена в контекст сесії.

ЧЕСНА МЕЖА. Скрипт лише показує дрейф. Оновити копії може тільки власник:
`maintain.py package` готує пакети, завантаження в claude.ai — його дія.

Запуск: python3 scripts/check-account-skills.py [--mounts ГЛОБ] [--manifest ШЛЯХ]
Змінна ACCOUNT_SKILLS_GLOB перевизначає глоб монтування (для тестів).
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
DEFAULT_GLOB = "~/.claude/skills/synced/*/*/SKILL.md"
VERSION = re.compile(r"^\s*version:\s*['\"]?(\d+(?:\.\d+)+)", re.M)
H1 = re.compile(r"^#\s.*?\bv(\d+(?:\.\d+)+)", re.M)


def mounted_version(text: str) -> str | None:
    """Версія змонтованого скіла: frontmatter на будь-якому відступі, інакше H1."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        m = VERSION.search(text[3:end] if end > 0 else "")
        if m:
            return m.group(1)
    m = H1.search(text)
    return m.group(1) if m else None


def key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mounts", default=os.environ.get("ACCOUNT_SKILLS_GLOB", DEFAULT_GLOB))
    ap.add_argument("--manifest", default=str(ROOT / "melania-skills-ecosystem" / "MANIFEST.json"))
    args = ap.parse_args(argv[1:])
    try:
        skills = json.loads(Path(args.manifest).read_text(encoding="utf-8")).get("skills", {})
    except (OSError, ValueError):
        return 0                                # нема канону — нема з чим звіряти
    canon = ({name: meta.get("version") for name, meta in skills.items()}
             if isinstance(skills, dict) else {s.get("name"): s.get("version") for s in skills})
    total, older, unknown = 0, [], []
    for path in sorted(glob.glob(os.path.expanduser(args.mounts))):
        name = os.path.basename(os.path.dirname(path))
        if not canon.get(name):
            continue                            # не скіл melania — не наш канон
        total += 1
        try:
            ver = mounted_version(Path(path).read_text(encoding="utf-8"))
        except OSError:
            ver = None
        if ver is None:
            unknown.append(name)
        elif key(ver) < key(canon[name]):
            older.append((name, ver, canon[name]))
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
    raise SystemExit(main(sys.argv))
