#!/usr/bin/env python3
"""tap_text.py — знайти на екрані кнопку з одним із текстів і вивести її центр «x y».

Одна відповідальність: розібрати знімок інтерфейсу (uiautomator dump, XML) і
повернути координати першого збігу. Сам дотик робить виклик `adb shell input tap`.
Використання: tap_text.py <dump.xml> "Текст 1" "Текст 2" ...   (код 1 — нема збігу)
"""
import re
import sys
import xml.etree.ElementTree as ET


def find(xml_text: str, wanted: list[str]) -> tuple[int, int] | None:
    root = ET.fromstring(xml_text)
    low = [w.lower() for w in wanted]
    for w in low:
        for node in root.iter("node"):
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
    except (OSError, ET.ParseError):
        hit = None
    if not hit:
        sys.exit(1)
    print(hit[0], hit[1])
