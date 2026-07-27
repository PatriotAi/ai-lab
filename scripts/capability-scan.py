#!/usr/bin/env python3
"""capability-scan.py — інвентар НАТИВНИХ можливостей робочого харнесу (М2).

Єдина відповідальність: детерміновано відповісти на питання «що виконавець уміє
САМ, без наших інструкцій» — і чи це справді ввімкнено ТУТ, у цьому середовищі.

НАВІЩО. Правила лабораторії писалися для моделі-як-чорної-скриньки: не знаємо, що
вона вміє → інлайнимо все. Частина цих інструкцій дублює те, що харнес робить сам,
і коштує токенів на кожному ході. Щоб не дублювати, треба знати факт.

ТРИ СТАНИ, А НЕ ДВА (це головне рішення дизайну):
    supported — маркер знайдено в РОБОЧОМУ бінарнику          → машинний факт
    effective — можливість справді діє в цьому середовищі     → лише де гейт
                                                                змодельовано повністю
    unknown   — гейт не змодельовано або харнес не впізнано   → **нуль skip-ів**

`unknown` НЕ дорівнює `false` і тим паче не дорівнює `true`. Рішення «не інлайнити
інструкцію» приймається ЛИШЕ на `effective is True`. Будь-яка невизначеність
означає повний набір правил (fail-closed).

ЧОМУ САМЕ БІНАРНИК, А НЕ ВЕБ. Найдешевше й найточніше джерело правди про
можливості — сам харнес на диску: він не старіє, не потребує мережі й не бреше.
Один повний прохід — менш ніж секунда.

ПАСТКА, ЯКУ ЦЕЙ СКРИПТ ЗАКРИВАЄ (спіймано ділом 2026-07-27): у середовищі лежали
ДВІ інсталяції Claude Code — робочий бінарник 2.1.220 і стара копія 2.1.42 у
node_modules. Читання старої копії дало б інвентар можливостей, яких у робочому
харнесі нема (і навпаки). Тому скрипт спершу доводить, що дивиться саме на те,
що виконується, і за розбіжності версій кричить, а не мовчить.

Запуск:
    python3 scripts/capability-scan.py                 # звіт (markdown)
    python3 scripts/capability-scan.py --json          # машиночитний
    python3 scripts/capability-scan.py --cache-key     # лише ключ кешу
    python3 scripts/capability-scan.py --validate      # самотест

Код виходу: 0 — успіх · 1 — харнес не знайдено або самотест упав · 2 — помилка виклику.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

# ── Реєстр можливостей ─────────────────────────────────────────────────────
# Кожен запис: маркер у бінарнику · env-перемикач · яке НАШЕ правило він потенційно
# дублює. Колонка "rule" — не вирок, а кандидат на розгляд: збіг можливості й
# правила ще не означає, що правило зайве (див. capability-gating-policy).
#
# ВАЖЛИВО: наявність маркера доводить лише те, що харнес ЗНАЄ про можливість.
# Чи вона ввімкнена — окреме питання, на яке відповідає гейт (див. GATES).

CAPABILITIES: list[dict] = [
    {
        "id": "auto_memory",
        "title": "Автоматична пам'ять між сесіями",
        "markers": ["CLAUDE_CODE_DISABLE_AUTO_MEMORY", "autoMemoryEnabled"],
        "env": "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
        "rule": "G5-цикл (automations/g5-consolidate + g5-retrieve), continuation-memory",
    },
    {
        "id": "auto_compact",
        "title": "Автостиснення контексту",
        "markers": ["autoCompact"],
        "env": None,
        "rule": "continuation-memory: стиснення після ~20 ходів",
    },
    {
        "id": "adaptive_thinking",
        "title": "Адаптивна глибина міркування",
        "markers": ["CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING"],
        "env": "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING",
        "rule": "інструкції про глибину reasoning у model-fit-policy",
    },
    {
        "id": "background_tasks",
        "title": "Фонові задачі",
        "markers": ["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"],
        "env": "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS",
        "rule": "паралельність незалежних викликів (§Економія)",
    },
    {
        "id": "explore_plan_agents",
        "title": "Вбудовані Explore/Plan суб-агенти",
        "markers": ["CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS", "subagent_type"],
        "env": "CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS",
        "rule": "rlm-harness: делегування на дешевший клас",
    },
    {
        "id": "claude_md",
        "title": "Завантаження CLAUDE.md",
        "markers": ["CLAUDE_CODE_DISABLE_CLAUDE_MDS"],
        "env": "CLAUDE_CODE_DISABLE_CLAUDE_MDS",
        "rule": "сам шар правил лабораторії",
    },
    {
        "id": "file_checkpointing",
        "title": "Чекпоінти файлів (відкат правок)",
        "markers": ["CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING"],
        "env": "CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING",
        "rule": "«merge, не перезапис» — страховка від втрати",
    },
    {
        "id": "git_instructions",
        "title": "Вбудовані git-інструкції",
        "markers": ["CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS"],
        "env": "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS",
        "rule": "наші git-конвенції в CLAUDE.md",
    },
    {
        "id": "bundled_skills",
        "title": "Вбудовані скіли",
        "markers": ["CLAUDE_CODE_DISABLE_BUNDLED_SKILLS"],
        "env": "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS",
        "rule": "progressive disclosure навичок",
    },
    {
        "id": "long_context",
        "title": "Розширене контекстне вікно (1M)",
        "markers": ["CLAUDE_CODE_DISABLE_1M_CONTEXT"],
        "env": "CLAUDE_CODE_DISABLE_1M_CONTEXT",
        "rule": "бюджет контексту в model-fit-policy",
    },
    {
        "id": "cron",
        "title": "Планові запуски (cron/Routines)",
        "markers": ["CLAUDE_CODE_DISABLE_CRON"],
        "env": "CLAUDE_CODE_DISABLE_CRON",
        "rule": "weekly-review за розкладом",
    },
    {
        "id": "hooks",
        "title": "Хуки життєвого циклу",
        "markers": ["hook_event_name"],
        "env": None,
        "rule": "весь шар automations/",
    },
]

TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off", ""}


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in TRUTHY


# ── Гейти: де ми ЗНАЄМО повну логіку харнесу ───────────────────────────────
# Кожен гейт — це відтворення реального коду робочого бінарника, звірене ділом.
# Якщо для можливості гейта тут нема, її ефективний стан лишається `unknown`,
# і skip за нею заборонений. Додавати гейт можна ЛИШЕ прочитавши код харнесу.

def _gate_auto_memory(env: dict[str, str]) -> tuple[bool | None, str]:
    """Відтворює `xm()` робочого харнесу 2.1.220 (звірено 2026-07-27).

        if CLAUDE_CODE_DISABLE_AUTO_MEMORY truthy      -> false
        if CLAUDE_CODE_REMOTE truthy
           && !CLAUDE_CODE_REMOTE_MEMORY_DIR
           && !CLAUDE_COWORK_MEMORY_PATH_OVERRIDE      -> false
        інакше -> залежить від налаштувань/експериментів (дефолт true)

    Останню гілку НЕ моделюємо як true: вона залежить від settings і серверних
    прапорців, яких скрипт не бачить. Тому там — `unknown`, тобто skip заборонено.
    """
    if _truthy(env.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")):
        return False, "вимкнено явно через CLAUDE_CODE_DISABLE_AUTO_MEMORY"
    if (
        _truthy(env.get("CLAUDE_CODE_REMOTE"))
        and not env.get("CLAUDE_CODE_REMOTE_MEMORY_DIR")
        and not env.get("CLAUDE_COWORK_MEMORY_PATH_OVERRIDE")
    ):
        return False, (
            "віддалена сесія без CLAUDE_CODE_REMOTE_MEMORY_DIR → харнес гасить "
            "авто-пам'ять (гілка xm() робочого бінарника)"
        )
    return None, "гейт залежить від settings і серверних прапорців — не змодельовано"


def _gate_hooks(env: dict[str, str], obs: dict) -> tuple[bool | None, str]:
    """Гейт-спостереження, а не гейт-читання коду.

    Хуки не треба доводити читанням бінарника: якщо цей скрипт запущено САМИМ
    хуком, хуки працюють — доказ виконанням сильніший за доказ читанням. Немає
    спостереження → `unknown`, бо «маркер у бінарнику» не доводить, що хук
    зареєстрований у settings і справді викликається.
    """
    if obs.get("hook_event_name"):
        return True, f"доведено виконанням: скрипт запущено хуком {obs['hook_event_name']}"
    return None, "поза хуком — спостереження нема, факт не доведено"


# Гейти двох типів. Читання коду (`_gate_auto_memory`) відповідає на питання «що
# харнес зробить»; спостереження (`_gate_hooks`) — на питання «що харнес уже
# зробив». Друге сильніше, бо не залежить від того, чи правильно ми прочитали код.
GATES = {"auto_memory": _gate_auto_memory}
OBSERVED_GATES = {"hooks": _gate_hooks}


# ── Пошук робочого харнесу ─────────────────────────────────────────────────

def runtime_version(env: dict[str, str]) -> str | None:
    """Версія харнесу, що ВИКОНУЄТЬСЯ. `AI_AGENT` має вигляд
    'claude-code_2-1-220_agent' → '2.1.220'."""
    agent = env.get("AI_AGENT") or ""
    if m := re.search(r"claude-code[_-](\d+)-(\d+)-(\d+)", agent):
        return ".".join(m.groups())
    return None


def find_harness(env: dict[str, str]) -> dict:
    """Знайти виконуваний харнес і довести, що це саме він.

    Повертає dict із `path`, `version`, `trusted`. `trusted=False` означає, що
    файл знайдено, але його версія не збігається з тим, що реально виконується —
    інвентар із нього застосовувати НЕ можна."""
    expected = runtime_version(env)
    binary = shutil.which("claude", path=env.get("PATH") or os.environ.get("PATH", ""))
    resolved = str(pathlib.Path(binary).resolve()) if binary else None

    found_version = None
    if resolved and os.path.isfile(resolved):
        # Скомпільований бінарник несе рядок версії всередині; пакетна інсталяція
        # має package.json поруч.
        pkg = pathlib.Path(resolved).parent.parent / "package.json"
        if pkg.is_file():
            try:
                found_version = json.loads(pkg.read_text(encoding="utf-8")).get("version")
            except (OSError, json.JSONDecodeError):
                found_version = None
        if found_version is None and expected:
            try:
                hit = subprocess.run(
                    ["grep", "-acoF", expected, resolved],
                    capture_output=True, text=True, timeout=300,
                )
                if hit.returncode == 0 and hit.stdout.strip() not in ("", "0"):
                    found_version = expected
            except (OSError, subprocess.SubprocessError):
                pass

    trusted = bool(resolved) and (expected is None or found_version == expected)
    return {
        "path": resolved,
        "version_found": found_version,
        "version_running": expected,
        "trusted": trusted,
    }


def scan_markers(binary: str, markers: list[str]) -> dict[str, int]:
    """Один прохід по бінарнику на всі маркери одразу (~1 c на 275 МБ)."""
    if not binary or not os.path.isfile(binary):
        return {}
    pattern = "|".join(re.escape(m) for m in markers)
    try:
        proc = subprocess.run(
            ["grep", "-aoE", pattern, binary],
            capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    counts = dict.fromkeys(markers, 0)
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line in counts:
            counts[line] += 1
    return counts


def cache_key(env: dict[str, str], model: str | None, harness: dict) -> str:
    """Ключ, при незмінності якого пере-сканувати нема сенсу.

    Входить усе, що може змінити відповідь: модель, версія харнесу, налаштування
    проєкту і значення env-перемикачів. Змінилось будь-що — профіль пере-знімається."""
    settings = pathlib.Path(env.get("CLAUDE_PROJECT_DIR", ".")) / ".claude" / "settings.json"
    settings_raw = settings.read_bytes() if settings.is_file() else b""
    toggles = {
        c["env"]: env.get(c["env"], "") for c in CAPABILITIES if c["env"]
    }
    toggles["CLAUDE_CODE_REMOTE"] = env.get("CLAUDE_CODE_REMOTE", "")
    toggles["CLAUDE_CODE_REMOTE_MEMORY_DIR"] = env.get("CLAUDE_CODE_REMOTE_MEMORY_DIR", "")
    payload = json.dumps(
        {
            "model": model or "unknown",
            "harness": harness.get("version_running") or harness.get("version_found"),
            # Впізнаність харнесу — ЧАСТИНА ключа, а не деталь.
            # Інцидент 2026-07-27 (спіймано canary C4): сесія, де харнес не
            # знайшовся, діставала той самий ключ, що й здорова, і читала з кешу
            # ДОВІРЕНИЙ профіль. Тобто середовище, яке втратило харнес, отримувало
            # дозволи, здобуті іншим середовищем. Стан довіри мусить розводити ключі.
            "trusted": bool(harness.get("trusted")),
            "path": harness.get("path"),
            "toggles": toggles,
            "settings": hashlib.sha256(settings_raw).hexdigest()[:16],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_profile(env: dict[str, str] | None = None, model: str | None = None,
                  observations: dict | None = None) -> dict:
    env = dict(os.environ if env is None else env)
    obs = observations or {}
    harness = find_harness(env)

    all_markers = sorted({m for c in CAPABILITIES for m in c["markers"]})
    counts = scan_markers(harness["path"], all_markers) if harness["trusted"] else {}

    entries = []
    for cap in CAPABILITIES:
        supported = any(counts.get(m, 0) > 0 for m in cap["markers"])
        if not harness["trusted"]:
            # Харнес не впізнано — не заявляємо нічого. Це не «нема можливості»,
            # це «ми не знаємо», і різниця тут вирішальна.
            effective, why = None, "харнес не впізнано — інвентар недостовірний"
        elif not supported:
            effective, why = False, "маркера нема в робочому харнесі"
        elif cap["env"] and _truthy(env.get(cap["env"])):
            effective, why = False, f"вимкнено через {cap['env']}"
        elif gate := GATES.get(cap["id"]):
            effective, why = gate(env)
        elif observed := OBSERVED_GATES.get(cap["id"]):
            effective, why = observed(env, obs)
        else:
            effective, why = None, "гейт не змодельовано — ефективний стан невідомий"

        entries.append({
            "id": cap["id"],
            "title": cap["title"],
            "supported": supported if harness["trusted"] else None,
            "effective": effective,
            "reason": why,
            "rule_candidate": cap["rule"],
            "env": cap["env"],
        })

    return {
        "model": model or "unknown",
        "harness": harness,
        "cache_key": cache_key(env, model, harness),
        "capabilities": entries,
        "skippable": sorted(e["id"] for e in entries if e["effective"] is True),
    }


def render(profile: dict) -> str:
    h = profile["harness"]
    lines = ["# Інвентар нативних можливостей харнесу", ""]
    lines.append(f"- Модель: `{profile['model']}`")
    lines.append(f"- Харнес: `{h['path'] or '—'}`")
    lines.append(f"- Версія виконувана / знайдена: `{h['version_running'] or '?'}` / "
                 f"`{h['version_found'] or '?'}`")
    lines.append(f"- Ключ кешу: `{profile['cache_key']}`")
    if not h["trusted"]:
        lines.append("")
        lines.append("> ⚠️ **Харнес не впізнано.** Інвентар недостовірний, усі можливості — "
                     "`невідомо`, skip заборонений повністю (fail-closed).")
    lines.append("")
    lines.append("| Можливість | Є в харнесі | Діє тут | Чому | Наше правило-кандидат |")
    lines.append("|---|:--:|:--:|---|---|")

    mark = {True: "✅", False: "—", None: "❓"}
    for e in profile["capabilities"]:
        lines.append(
            f"| {e['title']} | {mark[e['supported']]} | {mark[e['effective']]} | "
            f"{e['reason']} | {e['rule_candidate']} |"
        )
    lines.append("")
    skippable = profile["skippable"]
    lines.append(f"**Підтверджено діють ({len(skippable)}):** "
                 + (", ".join(f"`{s}`" for s in skippable) if skippable else "жодної"))
    lines.append("")
    lines.append("> «Діє тут» ✅ — єдина підстава не інлайнити відповідну інструкцію. "
                 "`❓` означає «не знаємо», а не «нема»: skip за `❓` заборонений. "
                 "І навіть за ✅ skip дозволений лише разом із машинною перевіркою, "
                 "що можливість справді спрацювала (див. capability-gating-policy).")
    return "\n".join(lines)


# ── Самотест ───────────────────────────────────────────────────────────────

def validate() -> int:
    failures: list[str] = []

    def check(name: str, expected, actual):
        if expected == actual:
            print(f"  ✅ {name}")
        else:
            failures.append(name)
            print(f"  ❌ {name}\n     очікували: {expected}\n     отримали:  {actual}")

    print("capability-scan самотест:")

    base = {"PATH": os.environ.get("PATH", ""), "AI_AGENT": os.environ.get("AI_AGENT", "")}

    # 1. Гейт авто-пам'яті на РЕАЛЬНОМУ зламаному стані: віддалена сесія без
    #    MEMORY_DIR. Саме цей стан у цій лабораторії, і саме тут наївний skip
    #    зламав би пам'ять.
    state, _ = _gate_auto_memory({"CLAUDE_CODE_REMOTE": "true"})
    check("віддалена сесія без MEMORY_DIR → авто-пам'ять не діє", False, state)

    # 2. Та сама сесія, але MEMORY_DIR заданий → гілка не спрацьовує.
    state, _ = _gate_auto_memory({"CLAUDE_CODE_REMOTE": "true",
                                  "CLAUDE_CODE_REMOTE_MEMORY_DIR": "/tmp/m"})
    check("MEMORY_DIR знімає віддалену гілку", None, state)

    # 3. Явне вимкнення сильніше за все інше.
    state, _ = _gate_auto_memory({"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})
    check("явне вимкнення перемагає", False, state)

    # 4. Невідомість НЕ конвертується в дозвіл. Локальна сесія без прапорців —
    #    це `unknown`, а не `true`: інакше skip проходив би на здогадці.
    state, _ = _gate_auto_memory({})
    check("невизначений гейт лишається unknown", None, state)

    # 5. Найважливіше: невпізнаний харнес → НУЛЬ skip-ів. Підкладаємо PATH без
    #    claude, тобто ламаємо розпізнавання повністю.
    broken = dict(base, PATH="/nonexistent")
    profile = build_profile(broken, model="claude-test")
    check("невпізнаний харнес → skippable порожній", [], profile["skippable"])
    check("невпізнаний харнес → trusted=False", False, profile["harness"]["trusted"])
    check("невпізнаний харнес → усі supported=None", True,
          all(c["supported"] is None for c in profile["capabilities"]))

    # 6. Розбіжність версій (та сама пастка, що з двома інсталяціями) має
    #    знімати довіру, навіть якщо файл знайдено.
    mismatched = dict(base, AI_AGENT="claude-code_9-9-999_agent")
    profile_mm = build_profile(mismatched, model="claude-test")
    check("розбіжність версій знімає довіру", False, profile_mm["harness"]["trusted"])
    check("розбіжність версій → skip заборонено", [], profile_mm["skippable"])

    # 7. Ключ кешу реагує на зміну перемикача — інакше профіль застрягне
    #    на застарілому знімку після зміни середовища.
    k1 = cache_key({"CLAUDE_CODE_REMOTE": "true"}, "m", {"version_running": "1"})
    k2 = cache_key({"CLAUDE_CODE_REMOTE": "true",
                    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}, "m", {"version_running": "1"})
    check("ключ кешу реагує на зміну перемикача", True, k1 != k2)
    k3 = cache_key({"CLAUDE_CODE_REMOTE": "true"}, "m", {"version_running": "2"})
    check("ключ кешу реагує на зміну версії харнесу", True, k1 != k3)
    k4 = cache_key({"CLAUDE_CODE_REMOTE": "true"}, "other", {"version_running": "1"})
    check("ключ кешу реагує на зміну моделі", True, k1 != k4)

    # Інцидент 2026-07-27 (canary C4): при однаковій версії, але втраченому
    # харнесі ключ збігався зі здоровим станом → зламана сесія читала з кешу
    # ДОВІРЕНИЙ профіль. Зламаний стан зобов'язаний мати власний ключ.
    k_ok = cache_key({}, "m", {"version_running": "1", "trusted": True, "path": "/x"})
    k_broken = cache_key({}, "m", {"version_running": "1", "trusted": False, "path": None})
    check("втрата харнесу розводить ключ кешу", True, k_ok != k_broken)

    # 8. Гейт-спостереження: без спостереження — `unknown`, зі спостереженням —
    #    доведено. Наявність маркера в бінарнику НЕ має сама по собі давати ✅,
    #    інакше «харнес знає про хуки» перетворилось би на «хуки викликаються».
    live_no_obs = build_profile(model="claude-opus-5")
    hooks_entry = next(c for c in live_no_obs["capabilities"] if c["id"] == "hooks")
    check("хуки без спостереження — unknown", None, hooks_entry["effective"])
    live_obs = build_profile(model="claude-opus-5",
                             observations={"hook_event_name": "SessionStart"})
    hooks_obs = next(c for c in live_obs["capabilities"] if c["id"] == "hooks")
    check("хуки зі спостереженням — доведено", True, hooks_obs["effective"])

    # 9. Спостереження не має «протікати» на інші можливості: доказ про хуки
    #    не є доказом про пам'ять чи мислення.
    check("спостереження не поширюється на інші можливості", ["hooks"],
          live_obs["skippable"])

    # 10. Чистий стан: на РЕАЛЬНОМУ середовищі скан має відпрацювати без падіння
    #     і не заявити ✅ для жодної можливості без відповідного гейта.
    check("живий скан не падає", True, isinstance(live_no_obs["capabilities"], list))
    check("живий скан не заявляє skip без гейта", True,
          all(c["id"] in GATES or c["id"] in OBSERVED_GATES
              for c in live_obs["capabilities"] if c["effective"] is True))

    print()
    if failures:
        print(f"❌ Самотест упав: {len(failures)} перевірок — {', '.join(failures)}")
        return 1
    print("✅ Самотест: усі перевірки пройшли")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Інвентар нативних можливостей харнесу")
    ap.add_argument("--json", action="store_true", help="машиночитний вивід")
    ap.add_argument("--cache-key", action="store_true", help="надрукувати лише ключ кешу")
    ap.add_argument("--model", help="ID моделі (типово — невідома)")
    ap.add_argument("--hook-payload", action="store_true",
                    help="читати payload хука зі stdin (дає model і спостереження)")
    ap.add_argument("--validate", action="store_true", help="самотест")
    args = ap.parse_args()

    if args.validate:
        return validate()

    model, observations = args.model, {}
    if args.hook_payload:
        # Payload хука — єдине джерело, де модель відома ДО першого ходу:
        # env-змінної з ID моделі не існує (звірено 2026-07-27).
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            model = model or payload.get("model")
            observations = {
                "hook_event_name": payload.get("hook_event_name"),
                "agent_type": payload.get("agent_type"),
                "agent_id": payload.get("agent_id"),
            }

    profile = build_profile(model=model, observations=observations)
    profile["agent_type"] = observations.get("agent_type") or "root"
    if args.cache_key:
        print(profile["cache_key"])
        return 0
    if args.json:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        print(render(profile))
    return 0 if profile["harness"]["trusted"] else 1


if __name__ == "__main__":
    sys.exit(main())
