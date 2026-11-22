#!/usr/bin/env python3
"""plan.py — перетворює вхід workflow на список прогонів (matrix).

Одна відповідальність: прочитати й ПЕРЕВІРИТИ вхід (ціль, пристрій, версію
Android, сценарій, кількість випадкових дотиків) і віддати JSON-список
прогонів у GITHUB_OUTPUT. Нічого не завантажує й не запускає.

Подія `push` (зміна коду симулятора) → самоперевірка зі `selftest.json`.
Будь-яка інша подія → один прогін з полів вводу.

Вхід — змінні оточення IN_* (не підставляються в shell напряму — захист від
ін'єкції через поля форми).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from urltools import strip as strip_secret  # noqa: E402

DEVICES = {"phone", "small", "tablet"}
# Умови середовища (fault injection): чим «реальний» телефон відрізняється від ідеального.
CONDITIONS = {"offline", "slow-net", "dark", "big-font", "landscape", "low-battery", "locale-uk", "locale-en"}
LABEL_RE = re.compile(r"[^a-z0-9-]+")


class PlanError(ValueError):
    pass


def classify_target(target: str) -> dict:
    """Що це за ціль: застосунок (app) чи сайт (web), і звідки його брати."""
    t = target.strip()
    if not t or len(t) > 2000 or any(c in t for c in "\n\r\t "):
        raise PlanError("ціль порожня, задовга або містить пробіли/переноси")
    if t.startswith("fdroid:"):
        pkg = t[len("fdroid:"):]
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+", pkg):
            raise PlanError(f"некоректна назва пакета F-Droid: {pkg!r}")
        return {"kind": "app", "source": "fdroid", "artifact_name": "", "artifact_run_id": ""}
    if t.startswith("artifact:"):
        rest = t[len("artifact:"):]
        name, _, run_id = rest.partition("@")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", name):
            raise PlanError(f"некоректна назва артефакту: {name!r}")
        if run_id and not run_id.isdigit():
            raise PlanError("після @ має бути номер запуску (лише цифри)")
        return {"kind": "app", "source": "artifact", "artifact_name": name, "artifact_run_id": run_id}
    if not re.match(r"https?://", t):
        raise PlanError("ціль має бути посиланням http(s)://, fdroid:<пакет> або artifact:<назва>")
    path = t.split("?", 1)[0].split("#", 1)[0].lower()
    if path.endswith((".apk", ".aab", ".apks", ".xapk", ".zip")):
        return {"kind": "app", "source": "url", "artifact_name": "", "artifact_run_id": ""}
    return {"kind": "web", "source": "url", "artifact_name": "", "artifact_run_id": ""}


def normalize(entry: dict, idx: int) -> dict:
    device = (entry.get("device") or "phone").strip()
    if device not in DEVICES:
        raise PlanError(f"невідомий профіль пристрою: {device!r} (є: {', '.join(sorted(DEVICES))})")
    android = (entry.get("android") or "33").strip()
    if not android.isdigit() or not 24 <= int(android) <= 36:
        raise PlanError(f"версія Android (API) має бути числом 24–36, а не {android!r}")
    monkey = (entry.get("monkey_events") or "0").strip()
    if not monkey.isdigit() or int(monkey) > 5000:
        raise PlanError("кількість випадкових дотиків — число 0–5000")
    raw_cond = (entry.get("conditions") or "").replace(" ", "")
    conds = [c for c in raw_cond.split(",") if c]
    bad = [c for c in conds if c not in CONDITIONS]
    if bad:
        raise PlanError(f"невідомі умови: {', '.join(bad)} (є: {', '.join(sorted(CONDITIONS))})")
    if "locale-uk" in conds and "locale-en" in conds:
        raise PlanError("оберіть одну мову: locale-uk або locale-en")
    flow = (entry.get("flow") or "").strip()
    if flow and (".." in flow.split("/") or flow.startswith("/") or not re.fullmatch(r"(sim:)?[A-Za-z0-9._/-]+", flow)):
        raise PlanError(f"некоректний шлях до сценарію: {flow!r}")
    target = (entry.get("target") or "").strip()
    # Перепустку до закритого сайту через поле форми НЕ приймаємо: поля форми
    # GitHub друкує у відкритому журналі раніше, ніж їх можна сховати.
    # Правильний шлях — секрет VERCEL_AUTOMATION_BYPASS_SECRET (див. README).
    if strip_secret(target) != target:
        raise PlanError("у посиланні є перепустка (_vercel_share / x-vercel-protection-bypass) — "
                        "її не можна вставляти у форму, вона потрапить у публічний журнал. "
                        "Збережіть ключ як секрет VERCEL_AUTOMATION_BYPASS_SECRET (див. README)")
    info = classify_target(target)
    kind_override = (entry.get("kind") or "auto").strip()
    if kind_override in {"app", "web"}:
        info["kind"] = kind_override
    elif kind_override != "auto":
        raise PlanError("тип цілі: auto, app або web")
    label = LABEL_RE.sub("-", (entry.get("label") or f"{info['kind']}-{device}-api{android}").lower()).strip("-")[:40]
    return {
        "label": label or f"run-{idx}",
        "target": target,
        "device": device,
        "android": android,
        "flow": flow,
        "monkey_events": monkey,
        "conditions": ",".join(dict.fromkeys(conds)),
        **info,
    }


def build(event: str, env: dict, selftest_path: Path) -> list[dict]:
    if event == "push":
        entries = json.loads(selftest_path.read_text(encoding="utf-8"))
    else:
        entries = [{
            "target": env.get("IN_TARGET", ""),
            "kind": env.get("IN_KIND", "auto"),
            "device": env.get("IN_DEVICE", "phone"),
            "android": env.get("IN_ANDROID", "33"),
            "flow": env.get("IN_FLOW", ""),
            "monkey_events": env.get("IN_MONKEY", "300"),
            "conditions": env.get("IN_CONDITIONS", ""),
            "label": env.get("IN_LABEL", ""),
        }]
    runs = [normalize(e, i) for i, e in enumerate(entries)]
    labels = [r["label"] for r in runs]
    if len(set(labels)) != len(labels):
        raise PlanError("назви прогонів (label) мають бути різні")
    return runs


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    try:
        runs = build(os.environ.get("EVENT_NAME", ""), dict(os.environ), here / "selftest.json")
    except PlanError as e:
        print(f"::error::Вхід не пройшов перевірку: {e}")
        return 1
    matrix = json.dumps({"include": runs}, ensure_ascii=False)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"matrix={matrix}\n")
    print(json.dumps(runs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
