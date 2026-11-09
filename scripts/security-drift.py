#!/usr/bin/env python3
"""security-drift.py — чи справді ввімкнені контролі, які документи називають активними.

Єдина відповідальність: порівняти ЗАДЕКЛАРОВАНИЙ стан безпекових контролів
із ФАКТИЧНИМ і показати розбіжність. Нічого не виправляє, нічого не вмикає.

НАВІЩО (не теорія — зафіксований дефект):
    `SECURITY.md` описує pre-commit як активний локальний контроль. Зріз
    2026-07-27 показав, що в робочому середовищі не встановлено ні pre-commit,
    ні gitleaks, ні trivy, ні semgrep, а тека `.git/hooks/` порожня — тобто
    весь локальний шар не працював, доки про це ніхто не питав.
    Це «Control Effectiveness» із наданого Master-документа в масштабі
    лабораторії: недостатньо, щоб контроль ІСНУВАВ — треба, щоб він ПРАЦЮВАВ.

ЧЕСНА МЕЖА:
    Перевіряється лише те, що видно з файлової системи. Стан на боці GitHub
    (чи ввімкнено Dependency graph, чи проходять воркфлоу) звідси не видно —
    такі контролі позначаються як «не перевіряється звідси», а НЕ як робочі.

Запуск:
    python3 scripts/security-drift.py          # звіт для людини
    python3 scripts/security-drift.py --quiet  # лише рядки з розбіжністю

Код виходу: 0 — розбіжностей немає · 1 — є розбіжності · 2 — помилка виклику.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

OK, DRIFT, UNKNOWN = "✅", "⚠️", "❓"


def repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def stale_limit(root: Path) -> int:
    """Скільки днів контроль лишається підтвердженим. Джерело — та сама політика."""
    try:
        pol = tomllib.loads((root / "security" / "policy.toml").read_text(encoding="utf-8"))
        return int(pol.get("levels", {}).get("R3", {}).get("stale_after_days", 30))
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return 30


def check_tool(name: str, why: str) -> tuple[str, str, str]:
    if shutil.which(name):
        return OK, name, "встановлено"
    return DRIFT, name, f"НЕ встановлено — {why}"


def check_git_hooks(root: Path) -> tuple[str, str, str]:
    hooks = root / ".git" / "hooks"
    if not hooks.is_dir():
        return DRIFT, "git-хуки", "теки .git/hooks немає"
    live = [p.name for p in hooks.iterdir() if not p.name.endswith(".sample")]
    if live:
        return OK, "git-хуки", f"встановлено: {', '.join(sorted(live))}"
    return DRIFT, "git-хуки", "жодного активного — запусти scripts/setup.sh"


def check_claude_hooks(root: Path) -> list[tuple[str, str, str]]:
    """Чи зареєстровані хуки й чи існують файли, на які вони вказують."""
    settings = root / ".claude" / "settings.json"
    if not settings.is_file():
        return [(DRIFT, "хуки Claude Code", ".claude/settings.json відсутній")]
    try:
        cfg = json.loads(settings.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [(DRIFT, "хуки Claude Code", f".claude/settings.json не читається: {exc}")]

    rows: list[tuple[str, str, str]] = []
    events = cfg.get("hooks", {})
    if not events:
        rows.append((DRIFT, "хуки Claude Code", "жодного не зареєстровано"))
    for event, groups in events.items():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                # Хук може посилатись на $CLAUDE_PROJECT_DIR — резолвимо на корінь репо.
                rel = cmd.replace("$CLAUDE_PROJECT_DIR/", "").replace("${CLAUDE_PROJECT_DIR}/", "")
                target = root / rel
                if target.is_file():
                    rows.append((OK, f"хук {event}", rel))
                else:
                    rows.append((DRIFT, f"хук {event}", f"файл не знайдено: {rel}"))
    return rows


def check_pretooluse(root: Path) -> tuple[str, str, str]:
    """Механічний гейт дій — окремо, бо його відсутність це дефект F-3."""
    settings = root / ".claude" / "settings.json"
    text = settings.read_text(encoding="utf-8") if settings.is_file() else ""
    if "PreToolUse" in text:
        return OK, "механічний гейт дій (PreToolUse)", "зареєстровано"
    return (
        DRIFT,
        "механічний гейт дій (PreToolUse)",
        "відсутній — незворотні дії тримаються лише на дисципліні (F-3)",
    )


def check_action_pinning(root: Path) -> tuple[str, str, str]:
    """Дії GitHub закріплені хешем чи рухомим тегом (F-5)."""
    wf = root / ".github" / "workflows"
    if not wf.is_dir():
        return UNKNOWN, "закріплення дій GitHub", "теки воркфлоу немає"
    tagged = 0
    for path in wf.glob("*.yml"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("- uses:", "uses:")):
                ref = stripped.split("@", 1)[1].split()[0] if "@" in stripped else ""
                # Повний SHA коміту — 40 шістнадцяткових символів.
                if not (len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower())):
                    tagged += 1
    if tagged:
        return DRIFT, "закріплення дій GitHub", f"{tagged} закріплено рухомим тегом, не хешем (F-5)"
    return OK, "закріплення дій GitHub", "усі закріплені хешем коміту"


def check_last_verified(root: Path, limit_days: int) -> tuple[str, str, str]:
    """Коли контролі востаннє підтверджували ділом (S3.3).

    Контроль, який давно не прогоняли, — НЕ робочий контроль, а непідтверджений.
    Різниця та сама, що між «чисто» і «не перевіряли»: виглядає однаково,
    означає протилежне. Мітку пише `tests/run-tests.sh` при успішному прогоні.
    """
    marker = root / "security" / "audit" / "last-verified.json"
    if not marker.is_file():
        return (
            DRIFT, "підтвердження контролів",
            "НІКОЛИ не прогонялось у цьому середовищі — статус контролів "
            "нижче не підтверджений. Прогін: bash tests/run-tests.sh",
        )
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        stamp = datetime.fromisoformat(data["ts"].replace("Z", "+00:00"))
        passed = data.get("passed", "?")
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        return DRIFT, "підтвердження контролів", f"мітка не читається ({exc})"

    days = (datetime.now(timezone.utc) - stamp).days
    when = stamp.strftime("%Y-%m-%d %H:%M UTC")
    if days > limit_days:
        return (
            DRIFT, "підтвердження контролів",
            f"НЕПІДТВЕРДЖЕНО — останній прогін {when} ({days} дн. тому, "
            f"межа {limit_days}). Прогін: bash tests/run-tests.sh",
        )
    return OK, "підтвердження контролів", f"{when} · {passed} перевірок · {days} дн. тому"


def check_self_modification(root: Path) -> tuple[str, str, str]:
    """Скільки разів агент правив код власного гейта (рішення власника: записувати, не блокувати)."""
    log = root / "security" / "audit" / "decisions.jsonl"
    if not log.is_file():
        return UNKNOWN, "самозміни гейта", "журнал порожній — записів немає"
    count = 0
    try:
        for line in log.read_text(encoding="utf-8").splitlines():
            if '"self_modification": true' in line or '"self_modification":true' in line:
                count += 1
    except OSError as exc:
        return UNKNOWN, "самозміни гейта", f"журнал не читається ({exc})"
    if count:
        return (
            OK, "самозміни гейта",
            f"{count} у журналі цього середовища — це НЕ помилка, а видимість: "
            "правки власного гейта не блокуються, але й не проходять тихо",
        )
    return OK, "самозміни гейта", "жодної в журналі цього середовища"


def check_unwired_hooks(root: Path) -> list[tuple[str, str, str]]:
    """Зворотний бік перевірки хуків: що ОГОЛОШУЄ себе хуком, але не підключене.

    Наявна перевірка йшла від реєстрації до файлу («хук зареєстровано — чи є
    файл?»). Цей напрямок ловить протилежне: файл є, у шапці написано «-хук»,
    а в жодній події його немає. Саме так пройшла повз увагу F-12 — і ще
    один випадок, від іншої сесії, знайшовся вже під час побудови цієї
    перевірки. Тобто клас системний, а не разовий недогляд.

    Урок F-13 (хибна знахідка першої версії): «нема в проєктних
    налаштуваннях» ≠ «не працює» — частину хуків реєструє СЕРЕДОВИЩЕ.
    Такі названі в `[[wiring.environment_wired]]` і перевіряються окремо.

    Спираємось на САМООГОЛОШЕННЯ скрипта: це чесніше за здогад по імені файлу
    й не дає хибних тривог на допоміжні скрипти поруч.
    """
    try:
        pol = tomllib.loads((root / "security" / "policy.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [(DRIFT, "підключеність автоматизацій", f"політика не читається ({exc})")]

    cfg = pol.get("wiring", {})
    markers = cfg.get("hook_markers", ["-хук", "-hook"])
    allowed = {line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
               for line in cfg.get("intentionally_unwired", []) if ":" in line}
    env_wired = {e["script"]: e for e in cfg.get("environment_wired", [])
                 if isinstance(e, dict) and e.get("script")}

    settings = root / ".claude" / "settings.json"
    registered = settings.read_text(encoding="utf-8") if settings.is_file() else ""

    rows: list[tuple[str, str, str]] = []
    for rel_dir in cfg.get("scan_dirs", []):
        base = root / rel_dir
        if not base.is_dir():
            continue
        for script in sorted(base.rglob("*.sh")):
            try:
                head = "\n".join(script.read_text(encoding="utf-8").splitlines()[:12])
            except OSError:
                continue
            declares_hook = any(m in head for m in markers)
            if not declares_hook:
                continue                       # допоміжний скрипт — не наша справа
            name = script.name
            if name in registered:
                continue                       # підключений — усе гаразд
            if name in env_wired:
                rows.append(check_env_wired(env_wired[name], script, registered))
                continue
            try:
                shown = str(script.relative_to(root))
            except ValueError:
                shown = str(script)
            reason = allowed.get(name)
            if reason:
                rows.append((OK, f"не підключено свідомо: {shown}", reason))
            else:
                rows.append((
                    DRIFT, f"НЕ ПІДКЛЮЧЕНО: {shown}",
                    "скрипт називає себе хуком у власній шапці, але його немає в "
                    "жодній події `.claude/settings.json`. Або підключи, або назви "
                    "причину в `security/policy.toml` → [wiring].intentionally_unwired",
                ))
    if not rows:
        rows.append((OK, "підключеність автоматизацій", "усі самооголошені хуки на місці"))
    return rows


# ── W-16: твердження README про підключеність (2026-10-18) ──────────────────
_HOOK_EVENTS = ("SessionStart", "SessionEnd", "SubagentStop", "Stop", "PreToolUse",
                "PostToolUse", "UserPromptSubmit", "Notification", "PreCompact")
_EVENT_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(_HOOK_EVENTS) + r")(?![a-z])")
# Рядок про СЕБЕ: «Тригер: …» / «Подія: …» (з маркером списку й жирним).
_OWN_CLAIM = re.compile(r"^\s*(?:[-*]\s*)?\**\s*(Тригер|Подія)\b")
# Ознаки МИНУЛОГО стоять ПЕРЕД тим, до чого відносяться («раніше `X`», «історично:
# `X`»): маркер ОБРІЗАЄ рядок, бо чинне твердження стоїть ДО нього (рев'ю #94:
# «Тригер: `Stop` (раніше `SessionEnd`)»). Межа слова — щоб «найраніше» не
# читалось як «раніше».
_PAST = re.compile(r"(?<!\w)(історично|до 2026|раніше|колись)", re.I)
# Заперечення, зняття, інструкція, відкрите питання стоять і ДО предмета, і ПІСЛЯ
# нього («`X` — знято», «`a` на `Stop` більше не підключено»), тож рядок із ними —
# не твердження про чинний стан і пропускається цілком (рев'ю 2026-10-23:
# обрізання давало хибну тривогу саме на такому порядку слів).
_NOT_A_CLAIM = re.compile(r"(?<!\w)(знято|знята|прибрано|не зареєстр|не підключ|зняти)"
                          r"|\[\?\]|~~", re.I)


def _wired(name: str, event: str, settings: dict, env_wired: list[dict], root: Path) -> bool:
    """Чи автоматизація `name` справді виконується на події `event`."""
    for group in (settings.get("hooks", {}) or {}).get(event, []) or []:
        for hook in (group.get("hooks", []) if isinstance(group, dict) else []):
            if f"automations/{name}/" in str((hook or {}).get("command", "")):
                return True
    # Реєстрація середовища (stop-git-check): правдивість самої реєстрації
    # перевіряє `check_env_wired`; тут — чи описана подія та сама.
    return any(e.get("event") == event and (root / "automations" / name / e["script"]).is_file()
               for e in env_wired)


def check_readme_claims(root: Path) -> list[tuple[str, str, str]]:
    """Чи README автоматизацій кажуть про підключеність ПРАВДУ (W-16).

    Інцидент: README `g5-consolidate` два місяці описував Stop-хук, знятий
    2026-07-31 (F-12); знайдено лише 2026-10-09 через `git log -S`. Перевірка
    шапки скрипта (`check_unwired_hooks`) цього не бачить: вона йде від скрипта,
    а неправду казала ПРОЗА — і не лише про себе: парний README `g5-retrieve`
    досі називав «повним авто-циклом» пару з уже знятою Stop-консолідацією.

    Твердження — рядок README, де назва події стоїть поруч із назвою автоматизації
    (`` `назва` `` чи `` `automations/назва` ``, у парі з найближчою подією після
    неї), або рядок «Тригер:/Подія:» — тоді про саму цю автоматизацію. Ознака
    минулого (`_PAST`) обрізає рядок: твердженням лишається текст ДО неї; рядок
    із запереченням чи зняттям (`_NOT_A_CLAIM`) не перевіряється зовсім.

    ЧЕСНА МЕЖА: це розбір прози. Твердження без назви події («працює на
    старті») або з назвою, написаною інакше, перевірка не побачить; так само
    чинне твердження в одному рядку із запереченням іншого.
    """
    try:
        pol = tomllib.loads((root / "security" / "policy.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [(DRIFT, "твердження README", f"політика не читається ({exc})")]
    env_wired = [e for e in pol.get("wiring", {}).get("environment_wired", [])
                 if isinstance(e, dict) and e.get("script")]
    try:
        settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = {}
    base = root / "automations"
    names = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    if not names:
        return [(UNKNOWN, "твердження README", "теки automations/ нема — перевірити нічого")]
    auto_re = re.compile(r"`(?:automations/)?(" + "|".join(map(re.escape, names)) + r")(?:/[^`]*)?`")

    rows: list[tuple[str, str, str]] = []
    checked = 0
    for own in names:
        readme = base / own / "README.md"
        if not readme.is_file():
            continue
        for n, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
            if _NOT_A_CLAIM.search(line):
                continue
            cut = _PAST.search(line)
            if cut:
                line = line[:cut.start()]
            mentions = sorted([(m.start(), "auto", m.group(1)) for m in auto_re.finditer(line)]
                              + [(m.start(), "event", m.group(1)) for m in _EVENT_RE.finditer(line)])
            claims: list[tuple[str, str]] = []
            for k, (_pos, kind, value) in enumerate(mentions):
                if kind != "auto":
                    continue
                # Назва бере КОЖНУ подію до наступної назви: «`a` на SessionStart
                # і Stop» стверджує обидві (перша версія звіряла лише першу —
                # мутант «пара з усіма подіями» вижив, бо ніщо не доводило обмеження).
                for _p2, kind2, value2 in mentions[k + 1:]:
                    if kind2 == "auto":
                        break
                    claims.append((value, value2))
            if _OWN_CLAIM.match(line) and not any(c[0] != own for c in claims):
                claims += [(own, m.group(1)) for m in _EVENT_RE.finditer(line)]
            for name, event in dict.fromkeys(claims):
                checked += 1
                if not _wired(name, event, settings, env_wired, root):
                    rows.append((DRIFT, f"README каже неправду: automations/{own}/README.md:{n}",
                                 f"«{name}» на події {event} — але такої реєстрації немає "
                                 "(ні в `.claude/settings.json`, ні в середовищі). Виправ "
                                 "текст або підключи"))
    if not rows:
        rows.append((OK, "твердження README про підключеність",
                     f"перевірено {checked}, усі правдиві"))
    return rows


def _env_commands(settings_file: Path) -> list[tuple[str, str]] | None:
    """(подія, команда) з файлу налаштувань хуків; None — читабельність не доведено.

    Неочікувана ФОРМА (корінь-список, `hooks`-рядок, подія-число, група-рядок)
    — теж «не читається», а не падіння: зіпсований файл середовища не має
    зупиняти решту звіту. Знайдено рев'ю на PR #73; відтворено на 4 формах.
    """
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
        return None
    found: list[tuple[str, str]] = []
    for event, groups in data.get("hooks", {}).items():
        if not isinstance(groups, list):
            return None
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
                return None
            for hook in group.get("hooks", []):
                if not isinstance(hook, dict):
                    return None
                cmd = hook.get("command")
                if isinstance(cmd, str):
                    found.append((str(event), cmd))
    return found


def _runs_file(cmd: str, target: Path) -> bool:
    """Чи запускає команда САМЕ цей файл, а не інший з тим самим ім'ям.

    `~/.claude/x.sh`, `"$HOME/.claude/x.sh"` і `bash ~/.claude/x.sh` — той
    самий файл; `/opt/other/x.sh` — ні. Порівнюються реальні шляхи.
    """
    try:
        words = shlex.split(cmd)
    except ValueError:
        return False
    want = os.path.realpath(target)
    return any(os.path.realpath(os.path.expanduser(os.path.expandvars(w))) == want for w in words)


def check_env_wired(entry: dict, canon: Path, registered: str) -> tuple[str, str, str]:
    """Хук, який реєструє СЕРЕДОВИЩЕ, а не проєкт (F-13 виявився саме таким).

    У `.claude/settings.json` його немає — і не повинно бути: друга реєстрація
    запускала б ту саму перевірку двічі. Тому доводимо не один факт, а три:
    синхронізатор підключений · середовище запускає САМЕ активну копію САМЕ
    на потрібній події · копія байт-у-байт дорівнює канону. Без файлу
    налаштувань середовища (локальна машина, CI) довести нічого не можна —
    це ❓, а НЕ ✅.
    """
    name = canon.name
    label = f"хук середовища: {name}"
    event = str(entry.get("event", ""))
    if not event:
        return (UNKNOWN, label, "у політиці не названо подію (`event`) — нема з чим звіряти")
    synced_by = str(entry.get("synced_by", ""))
    # За повним ім'ям файла, не підрядком: `sync.sh` не має збігатися з `async.sh`.
    if not synced_by or not re.search(rf"(^|[/\s\"']){re.escape(synced_by)}([\s\"']|$)", registered, re.M):
        return (DRIFT, label,
                f"синхронізатор `{synced_by or '—'}` не підключений у `.claude/settings.json` — "
                "після рестарту контейнера середовище запускатиме стару базову версію")

    env_raw = str(entry.get("env_settings", ""))
    active_raw = str(entry.get("active_copy", ""))
    env_file = Path(os.path.expanduser(env_raw))
    active = Path(os.path.expanduser(active_raw))
    if not env_file.is_file():
        return (UNKNOWN, label,
                f"звідси не перевірити: нема `{env_raw}` (це не середовище Claude Code web)")
    commands = _env_commands(env_file)
    if commands is None:
        return (UNKNOWN, label, f"`{env_raw}` не читається (JSON або його форма) — підключеність не доведено")
    # Не за ім'ям файла: команда на іншій події або з іншим шляхом до файла з
    # тим самим ім'ям давала б ✅, хоча наша копія в потрібний момент не працює.
    events = sorted({ev for ev, cmd in commands if _runs_file(cmd, active)})
    if event not in events:
        if events:
            return (DRIFT, label,
                    f"`{active_raw}` зареєстровано на {', '.join(events)}, а не на {event} — "
                    "у потрібний момент не виконується")
        return (DRIFT, label, f"середовище НЕ запускає `{active_raw}` (`{env_raw}`) — хук не виконується")
    if not active.is_file():
        return (DRIFT, label, f"середовище посилається на `{active_raw}`, але файла немає")
    try:
        same = active.read_bytes() == canon.read_bytes()
    except OSError as exc:
        return (UNKNOWN, label, f"копію не вдалося звірити з каноном ({exc})")
    if not same:
        return (DRIFT, label,
                f"активна копія `{active_raw}` ≠ канон — зараз працює інша версія; "
                f"оновиться на старті наступної сесії (`{synced_by}`)")
    return (OK, f"підключено середовищем: {name}",
            f"подія {event} у `{env_raw}` запускає саме `{active_raw}`; копія = канон; "
            f"синхронізує `{synced_by}`")

def check_remote_only() -> list[tuple[str, str, str]]:
    return [
        (UNKNOWN, "Dependency graph на GitHub", "не перевіряється звідси — лише в налаштуваннях репо"),
        (UNKNOWN, "захист гілок", "недоступний на приватному репо безкоштовного плану (рішення «варіант C»)"),
    ]


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv[1:]
    unknown_args = [a for a in argv[1:] if a not in ("--quiet",)]
    if unknown_args:
        print(f"security-drift: невідомі аргументи: {' '.join(unknown_args)}", file=sys.stderr)
        return 2

    root = repo_root()
    rows: list[tuple[str, str, str]] = [
        check_tool("pre-commit", "локальний гейт гігієни й секретів не працює"),
        check_tool("gitleaks", "локальний скан секретів не працює (у CI є)"),
        check_tool("trivy", "локальний скан вразливостей не працює (у CI є)"),
        check_git_hooks(root),
    ]
    rows += check_claude_hooks(root)
    rows.append(check_pretooluse(root))
    rows.append(check_action_pinning(root))
    rows += check_unwired_hooks(root)
    rows += check_readme_claims(root)
    rows.append(check_last_verified(root, stale_limit(root)))
    rows.append(check_self_modification(root))
    rows += check_remote_only()

    drifted = [r for r in rows if r[0] == DRIFT]

    if not quiet:
        print("Дрейф безпекових контролів — задекларовано проти фактично\n")
        for mark, name, detail in rows:
            print(f"  {mark} {name}: {detail}")
        print()

    if drifted:
        print(f"⚠️  Розбіжностей: {len(drifted)}")
        if quiet:
            for _, name, detail in drifted:
                print(f"  - {name}: {detail}")
        print("   «Контроль існує» ≠ «контроль працює». Виправ або свідомо прийми.")
        return 1

    print("✅ Розбіжностей немає: усе, що задекларовано, справді ввімкнено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
