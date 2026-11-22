#!/usr/bin/env python3
"""redact_logs.py — прибрати з текстових журналів значення, схожі на секрети.

Одна відповідальність: перед публікацією в гілку-альбом замінити на `***`
значення після слів key/token/secret/password/auth (напр. DHCP-рядок
`l2key: W3…` у журналі Android). Справжніх секретів там немає, але сканер
секретів (gitleaks) бачить їх як ключі й червоніє (W-52). Ширше правило
надійніше, ніж виняток у сканері: картинки й журнали альбому — публічні.

Використання: redact_logs.py <тека>   (усі *.txt і *.log рекурсивно, на місці)
Друкує, скільки значень замасковано.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SECRET_RE = re.compile(
    r"(?i)(\b[\w.-]*(?:key|token|secret|passw(?:or)?d|pwd|auth|credential)s?\b)"
    r"(\s*[:=]\s*)"
    r"([\"']?)([A-Za-z0-9+/_\-.=]{12,})"
)


def _looks_secret(value: str) -> bool:
    # Значення лише з літер (enable_feature, alert_window) — назви, не секрети.
    return bool(re.search(r"\d", value)) and bool(re.search(r"[A-Za-z]", value))


def redact_text(text: str) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        if not _looks_secret(m.group(4)):
            return m.group(0)
        count += 1
        return f"{m.group(1)}{m.group(2)}{m.group(3)}***"

    return SECRET_RE.sub(repl, text), count


def redact_dir(root: Path) -> int:
    total = 0
    for p in list(root.rglob("*.txt")) + list(root.rglob("*.log")):
        text = p.read_text(encoding="utf-8", errors="replace")
        new, n = redact_text(text)
        if n:
            p.write_text(new, encoding="utf-8")
            total += n
    return total


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    print(f"замасковано значень, схожих на секрети: {redact_dir(Path(sys.argv[1]))}")
