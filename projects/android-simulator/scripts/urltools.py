#!/usr/bin/env python3
"""urltools.py — відокремлює «перепустку» до закритого сайту від самого посилання.

Тестові копії сайтів на Vercel закриті входом. Пройти можна з перепусткою:
`_vercel_share=…` (тимчасове посилання для перегляду) або
`x-vercel-protection-bypass=…` (ключ для автоматики). Перепустка — секрет:
вона не має потрапити ні в журнали, ні в назви файлів, ні в звіт.

Використання:
  urltools.py strip   <url>  → посилання без перепустки (для звіту/журналу)
  urltools.py secrets <url>  → значення перепусток, по одному в рядку (для ::add-mask::)
  urltools.py scrub <файл-з-url> <файл>...  → замінити перепустки у файлах на ***
"""
from __future__ import annotations

import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECRET_PARAMS = {"_vercel_share", "x-vercel-protection-bypass"}


def strip(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in SECRET_PARAMS and k.lower() != "x-vercel-set-bypass-cookie"]
    return urlunsplit(parts._replace(query=urlencode(kept)))


def secrets(url: str) -> list[str]:
    parts = urlsplit(url)
    return [v for k, v in parse_qsl(parts.query) if k.lower() in SECRET_PARAMS and v]


def scrub(url_file: str, paths: list[str]) -> None:
    with open(url_file, encoding="utf-8") as f:
        found = secrets(f.read().strip())
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except FileNotFoundError:
            continue
        for s in found:
            text = text.replace(s, "***")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "scrub":
        scrub(sys.argv[2], sys.argv[3:])
        sys.exit(0)
    if len(sys.argv) != 3 or sys.argv[1] not in {"strip", "secrets"}:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    if sys.argv[1] == "strip":
        print(strip(sys.argv[2]))
    else:
        for s in secrets(sys.argv[2]):
            print(s)
