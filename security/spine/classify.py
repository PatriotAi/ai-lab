#!/usr/bin/env python3
"""classify.py — визначає рівень ризику дії за політикою `security/policy.toml`.

Єдина відповідальність: відповісти на питання «яка це дія і наскільки вона
незворотна». Нічого не блокує, нічого не пояснює, нічого не виконує —
рішення ухвалює той, хто викликав (`pretooluse.py`), пояснення дає `explain.py`.

ЧОМУ ОКРЕМО. Класифікація — єдина точка, з якої випливає все інше. Тримати її
відокремленою від блокування означає, що її можна прогнати на будь-якому наборі
прикладів без жодних побічних ефектів — тобто перевірити ділом, а не на слово.

ЧЕСНА МЕЖА. Класифікатор працює за переліком відомих шляхів і підрядків команд.
Перефразована або нова форма небезпечної дії його обійде — так само, як
`scan-external-input.py` є тріажем, а не бар'єром. Він піднімає підлогу,
а не ставить стелю.

Запуск для перевірки:
    python3 security/spine/classify.py Bash 'git push --force origin main'
    python3 security/spine/classify.py Write .github/workflows/security.yml
Код виходу дорівнює числу рівня (0..4), щоб зручно перевіряти з shell.
"""
from __future__ import annotations

import fnmatch
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

LEVELS = ("R0", "R1", "R2", "R3", "R4")


@dataclass
class Verdict:
    level: str
    reason: str                      # коротко, технічно — для журналу
    rule_id: str = ""
    why: str = ""                    # людською мовою — навіщо це правило
    alternatives: str = ""           # людською мовою — як можна інакше
    target: str = ""                 # що саме зачіпається (шлях/команда)
    resolved_target: str = ""        # реальна ціль після розрізу симлінка
    notes: list[str] = field(default_factory=list)

    @property
    def rank(self) -> int:
        return LEVELS.index(self.level)


def policy_path(root: Path | None = None) -> Path:
    root = root or repo_root()
    return root / "security" / "policy.toml"


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "security" / "policy.toml").is_file():
            return parent
    return Path.cwd()


def load_policy(root: Path | None = None) -> dict:
    return tomllib.loads(policy_path(root).read_text(encoding="utf-8"))


def _resolve_symlink(root: Path, raw: str) -> tuple[str, list[str]]:
    """Розрізає симлінк і повертає РЕАЛЬНУ ціль.

    Підстава — атака GhostApproval (розкрито 08.07.2026): файл із безпечною
    назвою (`project_settings.json`) насправді є симлінком на `~/.ssh` чи
    конфіг оболонки. Діалог згоди показує безпечну назву — людина погоджується
    не на ту дію, яка станеться. Тому рішення ухвалюється по РЕАЛЬНІЙ цілі.
    """
    notes: list[str] = []
    if not raw:
        return raw, notes
    try:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.is_symlink():
            real = os.path.realpath(candidate)
            notes.append(
                f"УВАГА: «{raw}» — це симлінк. Насправді буде зачеплено: {real}"
            )
            return real, notes
        return str(candidate), notes
    except OSError as exc:                      # noqa: BLE001 — шлях може бути будь-яким
        notes.append(f"шлях не вдалося розібрати ({exc}) — вважаю підозрілим")
        return raw, notes


# Оператори, що перетворюють «читання» на запис або на ланцюжок дій.
# Без цього переліку `cat > файл` вважався читанням (реальна дірка 2026-07-27).
WRITE_OPS = (">", ">>", "|", "&&", "||", ";", "$(", "`", "<(", "tee ")


def _write_targets(command: str) -> list[str]:
    """Витягує з команди те, у що вона СПРАВДІ пише.

    Перша версія просто питала «чи згадано захищений шлях у команді» — і це
    виявилось непридатним: слово `secrets` у тексті будь-якого повідомлення
    вмикало правило про ключі, а разом із крапкою з комою в python-однорядковику
    давало R4 на порожньому місці (спіймано 2026-07-27, тричі поспіль).
    Перевірка, що кричить на згадку, швидко навчає її ігнорувати — тому тут
    береться саме ЦІЛЬ запису, а не наявність слова.
    """
    targets: list[str] = []
    # Перенаправлення: `> файл`, `>> файл` (але не `2>&1` і не `>&`).
    targets += re.findall(r">>?\s*(?!&)([^\s;|&<>]+)", command)
    # Команди, чий аргумент — ціль запису.
    targets += re.findall(r"\b(?:tee|truncate|install)\s+(?:-\S+\s+)*([^\s;|&<>]+)", command)
    # Друга ціль копіювання/переміщення.
    targets += re.findall(r"\b(?:cp|mv)\s+(?:-\S+\s+)*\S+\s+([^\s;|&<>]+)", command)
    return [t.strip("'\"") for t in targets if t.strip("'\"")]


def _tool_managed(resolved: str, policy: dict) -> bool:
    """Чи лежить шлях у теці, якою керує сам Claude Code.

    Свідомо вузько: збіг лише за явними шаблонами з `[workspace]`. Це не
    «дозволити все поза репо» — решта зовнішніх шляхів лишається R4.
    """
    patterns = policy.get("workspace", {}).get("tool_managed_paths", [])
    for pattern in patterns:
        if fnmatch.fnmatch(resolved, pattern) or fnmatch.fnmatch(resolved, pattern + "/*"):
            return True
        base = pattern.rstrip("/*")
        if base and resolved.startswith(base + "/"):
            return True
    return False


def _command_touches_path(command: str, pattern: str) -> bool:
    """Чи пише команда в захищений шлях."""
    for target in _write_targets(command):
        if _match_path(pattern, target.lstrip("./"), target):
            return True
    return False


def _rel(root: Path, target: str) -> str:
    """Шлях відносно кореня репо — правила написані у відносній формі."""
    try:
        return str(Path(target).resolve().relative_to(root.resolve()))
    except (ValueError, OSError):
        return target


def _match_path(pattern: str, rel_target: str, raw_target: str) -> bool:
    for candidate in (rel_target, raw_target):
        if not candidate:
            continue
        if fnmatch.fnmatch(candidate, pattern):
            return True
        # `.github/workflows/*` має ловити і вкладені теки
        if pattern.endswith("/*") and candidate.startswith(pattern[:-1]):
            return True
    return False


def classify(tool_name: str, tool_input: dict, root: Path | None = None,
             policy: dict | None = None) -> Verdict:
    root = root or repo_root()
    pol = policy or load_policy(root)
    levels = pol.get("levels", {})
    rules = pol.get("rules", [])
    resolve_symlinks = pol.get("behaviour", {}).get("resolve_symlinks", True)

    command = str(tool_input.get("command", "") or "")
    raw_path = str(
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("notebook_path")
        or ""
    )

    notes: list[str] = []
    resolved = raw_path
    if raw_path and resolve_symlinks:
        resolved, notes = _resolve_symlink(root, raw_path)
    rel_target = _rel(root, resolved) if resolved else ""

    # ── Крок 1. Явні правила R4 мають найвищий пріоритет ────────────────────
    # Спершу найсуворіше: якщо дія збігається з чимось незворотним — далі не дивимось.
    #
    # ВАЖЛИВО: правила на ШЛЯХИ перевіряються і для Bash-команд, не лише для
    # Write/Edit. Інакше весь захист шляхів обходиться однією командою:
    # `cat > .github/workflows/evil.yml` — і це не гіпотеза, а дірка, знайдена
    # 2026-07-27 у момент, коли гейт заблокував власного автора на Write, а той
    # мав під рукою Bash. Гейт, який захищає один спосіб дії з двох, не захищає.
    for rule in rules:
        for pattern in rule.get("match_paths", []):
            if command and _command_touches_path(command, pattern):
                return Verdict(
                    level=rule.get("level", "R4"),
                    reason=f"команда пише у захищений шлях «{pattern}» (правило «{rule['id']}»)",
                    rule_id=rule["id"], why=rule.get("why", ""),
                    alternatives=rule.get("alternatives", ""),
                    target=command, resolved_target=command, notes=notes,
                )
            if raw_path and _match_path(pattern, rel_target, raw_path):
                return Verdict(
                    level=rule.get("level", "R4"),
                    reason=f"шлях збігається з правилом «{rule['id']}» ({pattern})",
                    rule_id=rule["id"], why=rule.get("why", ""),
                    alternatives=rule.get("alternatives", ""),
                    target=raw_path, resolved_target=resolved, notes=notes,
                )
        # Виняток перевіряється ПЕРЕД збігом: безпечна форма дії не має
        # блокуватись лише тому, що містить у собі підрядок небезпечної.
        exceptions = [e.lower() for e in rule.get("except_commands", [])]
        if command and any(exc in command.lower() for exc in exceptions):
            continue
        for needle in rule.get("match_commands", []):
            if command and needle.lower() in command.lower():
                return Verdict(
                    level=rule.get("level", "R4"),
                    reason=f"команда містить «{needle}» (правило «{rule['id']}»)",
                    rule_id=rule["id"], why=rule.get("why", ""),
                    alternatives=rule.get("alternatives", ""),
                    target=command, resolved_target=command, notes=notes,
                )

    # ── Крок 2. Недовірений вхід ────────────────────────────────────────────
    if tool_name in levels.get("R3", {}).get("tools", []):
        return Verdict("R3", f"{tool_name} приносить у контекст зовнішній текст",
                       target=command or raw_path, resolved_target=resolved, notes=notes)

    # ── Крок 3. Читання ─────────────────────────────────────────────────────
    if tool_name in levels.get("R0", {}).get("tools", []):
        return Verdict("R0", f"{tool_name} лише читає", notes=notes)
    if command:
        stripped = command.strip()
        for prefix in levels.get("R0", {}).get("bash_prefixes", []):
            if stripped == prefix or stripped.startswith(prefix + " "):
                # Ланцюжок АБО перенаправлення можуть ховати запис за читанням:
                # `cat > файл` — це запис, хоч і починається з `cat`.
                if any(op in stripped for op in WRITE_OPS):
                    break
                return Verdict("R0", f"команда читання ({prefix})", notes=notes)

    # ── Крок 4. Локальний запис ─────────────────────────────────────────────
    if tool_name in levels.get("R1", {}).get("tools", []):
        outside = bool(rel_target) and (
            rel_target.startswith("..") or Path(resolved).is_absolute()
            and not str(Path(resolved)).startswith(str(root))
        )
        # Теки, якими керує сам інструмент, — не «вихід за межі проєкту».
        if outside and _tool_managed(resolved, pol):
            return Verdict("R1", "тека, якою керує сам інструмент",
                           target=raw_path, resolved_target=resolved, notes=notes)
        if outside:
            return Verdict("R4", "запис ПОЗА межами репозиторію",
                           rule_id="outside-repo",
                           why="Файл лежить за межами цього проєкту. Зміни там я не бачу в git, "
                               "і відкотити їх звичайним способом не вийде.",
                           alternatives="Якщо файл справді потрібен — скажи, і ми запишемо його "
                                        "всередину проєкту, де кожна зміна видима й оборотна.",
                           target=raw_path, resolved_target=resolved, notes=notes)
        return Verdict("R1", f"{tool_name} пише у файл проєкту",
                       target=raw_path, resolved_target=resolved, notes=notes)

    # ── Крок 5. Решта виконання ─────────────────────────────────────────────
    if command:
        return Verdict("R2", "команда з можливим побічним ефектом",
                       target=command, resolved_target=command, notes=notes)

    return Verdict("R2", f"{tool_name}: невідомий клас — вважаю дією з наслідками",
                   notes=notes)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    tool, payload = argv[1], argv[2]
    tool_input = {"command": payload} if tool == "Bash" else {"file_path": payload}
    v = classify(tool, tool_input)
    print(f"{v.level}  {v.reason}")
    for note in v.notes:
        print(f"  ⚠ {note}")
    if v.why:
        print(f"  чому: {v.why}")
    return v.rank


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
