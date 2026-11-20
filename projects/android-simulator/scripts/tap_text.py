#!/usr/bin/env python3
"""tap_text.py — знайти на екрані кнопку з одним із текстів і вивести її центр «x y».

Одна відповідальність: розібрати знімок інтерфейсу (uiautomator dump, XML) і
повернути координати першого збігу. Сам дотик робить виклик `adb shell input tap`.
Використання: tap_text.py <dump.xml> "Текст 1" "Текст 2" ...   (код 1 — нема збігу)
"""
import html
import re
import sys

# Без XML-парсера: знімок інтерфейсу приходить із пристрою, де працює чужий
# застосунок, тож розбираємо лише атрибути тегів <node …> регулярним виразом
# (жодних сутностей і зовнішніх посилань — нема чим зловживати).
NODE_RE = re.compile(r"<node\b([^>]*)>")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def nodes(xml_text: str):
    for m in NODE_RE.finditer(xml_text):
        yield {k: html.unescape(v) for k, v in ATTR_RE.findall(m.group(1))}


def find(xml_text: str, wanted: list[str]) -> tuple[int, int] | None:
    low = [w.lower() for w in wanted]
    all_nodes = list(nodes(xml_text))
    for w in low:
        for node in all_nodes:
            label = (node.get("text") or node.get("content-desc") or "").strip().lower()
            if label == w:
                m = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    return (x1 + x2) // 2, (y1 + y2) // 2
    return None


if __name__ == "__main__":
    try:
        with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
            hit = find(f.read(), sys.argv[2:])
    except OSError:
        hit = None
    if not hit:
        sys.exit(1)
    print(hit[0], hit[1])
