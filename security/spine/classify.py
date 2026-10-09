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
    scope: str = ""                  # ціль незворотної дії (owner/repo#N), якщо відома — F-17

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

# Роздільники, що перетворюють одну команду на ЛАНЦЮЖОК. Перелік `WRITE_OPS`
# їх майже покриває, але не бачив **перенесення рядка** — а це теж роздільник.
# Наслідок був реальний: після послаблення «читання пропускає правила-підрядки»
# (2026-09-27) команда `cat README.md\ngit push --force origin main` ставала R0,
# бо починалась із читального префікса й не мала жодного оператора з переліку.
# Мої власні канарки цього не спіймали — усі були однорядкові; спіймав
# property-тест монотонності з `main` (`tests/property-classify.py`, Фаза S5):
# «додавання небезпечного фрагмента не може знизити рівень».
CHAIN_OPS = WRITE_OPS + ("\n", "\r")


# Ознаки того, що вміст лапок — це КОД, який виконають, а не текст-дані.
SHELL_INVOKERS = (
    "sh -c", "bash -c", "zsh -c", "eval ", "| sh", "| bash", "xargs ",
    # heredoc, поданий У САМУ оболонку: тіло виконається, отже воно не дані.
    # Пропуск, знайдений канаркою 2026-07-27: `bash <<'EOF' … rm -rf … EOF`
    # давав R2, бо тіло відкидалося як «дані». Це вже не шум, а дірка.
    "bash <<", "sh <<", "zsh <<", "bash -s", "sh -s",
    # Оболонка — не єдиний спосіб виконати текст. До 2026-09-27 перелік
    # закінчувався на `sh -s`, тож `python3 -c "…"`, `node -e "…"` і
    # `python3 - <<'PY' … PY` давали R2: лапки й тіло heredoc відкидались
    # як «дані», хоча інтерпретатор саме їх і виконує. Виміряно ділом на
    # трьох формах — усі три проходили повз правила. Це пропуск, а не шум:
    # напрям, протилежний до хибної тривоги, і тому небезпечніший.
    "python -c", "python3 -c", "python -", "python3 -",
    "node -e", "node --eval", "node -", "perl -e", "ruby -e", "php -r",
)

# Ознаки того, що «читальна» команда насправді ВИКОНУЄ дію — без жодного
# оператора оболонки, тому `WRITE_OPS` їх не бачить. Без цього переліку
# послаблення для читання (`is_pure_read` нижче) прорубало б власну дірку:
# `find . -name x -delete` теж починається з читального префікса.
# Знайдено при проєктуванні самого фіксу: перевіряли не «чи ловить»,
# а «що саме НЕ ловитиме» (Core Rule 15).
EXEC_MARKERS = ("-exec", "-execdir", "-delete", "-ok", "--exec")

# Ознаки ЗАПИСУ всередині інлайн-коду інтерпретатора. Потрібні, щоб правила на
# шляхи ловили `python3 - <<PY  open('security/policy.toml','w')  PY`, але НЕ
# кричали на `python3 -c 'print(".github/workflows/x.yml")'` — друк шляху не є
# дією (наявний стенд `tests/probe-classify.py` фіксує це як R2, і він має рацію:
# перевірка, що кричить на згадку, вчить себе ігнорувати).
#
# ЧЕСНА МЕЖА ПОКРИТТЯ: перелік іменний, тож екзотична форма запису поза ним
# лишається пропуском. Це краще за попередній стан, де інлайн-код не бачився
# ВЗАГАЛІ, і краще за суцільну тривогу на кожну згадку шляху.
INLINE_WRITE_HINTS = (
    "write", "'w'", '"w"', "'a'", '"a"', "'x'", "truncate", "unlink", "remove",
    "rmtree", "rename", "replace(", "copy", "move", "dump", "mkdir", "symlink",
    "chmod", "touch", "appendfile", "createwritestream", "outputfile", "save",
)

_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
# Роздільник ЗАХОПЛЮЄТЬСЯ і шукається дослівно (зворотне посилання \1).
# Перша версія шукала «перший рядок-слово» — і на довгому тілі, де такий
# рядок трапляється раніше за справжній кінець, відрізала не там, лишаючи
# решту тіла у «виконуваній» частині. Наслідок був безпечний (хибна тривога,
# не пропуск), але це саме той шум, який ми тут і прибираємо.
# Відкидається ТІЛО heredoc, а відкривач (`<<'EOF'`) лишається: інакше
# `bash <<'EOF' … EOF` після відкидання виглядав би як просто `bash`, і ознака
# «оболонка виконає вміст» зникала б разом із тілом.
_HEREDOC = re.compile(r"(<<-?\s*(['\"]?)(\w+)\2).*?^\3$", re.DOTALL | re.MULTILINE)


def executable_part(command: str) -> str:
    """Прибирає з команди те, що є ДАНИМИ, лишаючи те, що виконається.

    НАВІЩО. Правила шукали підрядок будь-де в тексті команди — тож `echo
    "merge_pull_request"` вмикало правило про злиття, а слово `secrets` у
    повідомленні — правило про ключі. За одну сесію це дало п'ять хибних
    тривог поспіль. Власне ж дослідження цього репозиторію (`research-2026-07`,
    посилання на дані Google про флакі) каже прямо: перевірка, що часто кричить
    дарма, вчить себе ігнорувати — тобто хибна тривога зношує гейт, а не
    підсилює його.

    ЧОГО ТУТ НЕ РОБИТЬСЯ. Якщо вміст лапок чи heredoc **виконується**
    (`bash -c "…"`, `eval`, `| sh`, `bash <<'EOF'`), не прибирається НІЧОГО:
    там це код. Інакше `bash -c "rm -rf /"` став би невидимим — а це вже не
    хибна тривога, а пропуск справжньої дії.

    ПОРЯДОК ВАЖЛИВИЙ. Ознака виконання шукається **після** відкидання даних,
    а не до нього. Перша версія перевіряла її на сирому тексті — і згадка
    `| sh` у звичайній прозі вимикала весь захист від хибних тривог, тобто
    лікування скасовувало саме себе (спіймано 2026-07-27 на записі в журнал
    напрацювань, який просто ПЕРЕЛІЧУВАВ ці ознаки).
    """
    stripped = _QUOTED.sub(" ", _HEREDOC.sub(r"\1", command))
    if any(inv in stripped.lower() for inv in SHELL_INVOKERS):
        return command
    return stripped


def executes_inline_code(command: str) -> bool:
    """Чи команда віддає ТЕКСТ інтерпретаторові на виконання.

    `bash -c "…"`, `eval`, `| sh`, `python3 - <<PY … PY`, `node -e "…"`.
    Ознака шукається після відкидання даних — з тієї ж причини, що в
    `executable_part`: згадка `| sh` у прозі не робить команду виконанням.
    """
    if not command:
        return False
    stripped = _QUOTED.sub(" ", _HEREDOC.sub(r"\1", command))
    return any(inv in stripped.lower() for inv in SHELL_INVOKERS)


def is_pure_read(command: str, policy: dict) -> bool:
    """Чи команда лише ЧИТАЄ — тобто фізично не здатна виконати незворотну дію.

    НАВІЩО. Правило-підрядок на читальній команді міряє ЗГАДКУ, а не дію:
    пошук по документації за назвою небезпечного прапорця нічого не обходить —
    він показує текст. До цього фіксу такий пошук класифікувався як R4, і та
    сама хибна тривога двічі зупинила дослідження `gsd-core` — причому вдруге
    саме на спробі ЗАПИСАТИ висновок про неї в журнал. Перевірка, що кричить
    на згадку, вчить себе ігнорувати (`docs/security/research-2026-07.md`),
    тож це не косметика, а зношування гейта.

    МЕЖА ПОСЛАБЛЕННЯ. Діє, лише коли команда не має жодного оператора
    запису чи ланцюжка (`WRITE_OPS`), жодної ознаки виконання
    (`SHELL_INVOKERS`) і жодного маркера дії без оболонки (`EXEC_MARKERS`).
    Інакше `cat f | sh` або `find . -delete` пролізли б як «читання».
    Правила на ШЛЯХИ це послаблення не зачіпає взагалі.
    """
    if not command:
        return False
    stripped = executable_part(command).strip()
    if not stripped:
        return False
    low = stripped.lower()
    if any(op in stripped for op in CHAIN_OPS):
        return False
    if any(inv in low for inv in SHELL_INVOKERS):
        return False
    if any(marker in low for marker in EXEC_MARKERS):
        return False
    prefixes = policy.get("levels", {}).get("R0", {}).get("bash_prefixes", [])
    return any(stripped == pref or stripped.startswith(pref + " ") for pref in prefixes)


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
    """Чи пише команда в захищений шлях.

    ДРУГИЙ ШЛЯХ, знайдений 2026-09-27 під час хвилі 4: інлайн-код в
    інтерпретаторі пише куди завгодно БЕЗ операторів оболонки —
    `python3 - <<PY` з `open('security/policy.toml','w')` усередині не має ні
    `>`, ні `tee`, тож перевірка цілей запису його не бачила. Знайдено на власній
    дії: саме так у цій сесії правилась політика, і гейт змовчав.

    Тому там, де команда ВИКОНУЄ текст і в цьому тексті є ознака ЗАПИСУ
    (`INLINE_WRITE_HINTS`), захищений шлях шукається в усій команді. Ознака
    потрібна, щоб не кричати на друк шляху: `print("<шлях>")` — не дія, і
    наявний стенд справедливо чекає там R2.
    """
    for target in _write_targets(command):
        if _match_path(pattern, target.lstrip("./"), target):
            return True
    low = command.lower()
    if executes_inline_code(command) and any(h in low for h in INLINE_WRITE_HINTS):
        # Токен МУСИТЬ допускати провідну точку: `.github/workflows/*` і
        # `.claude/settings.json` — саме такі. Перша версія регулярки починалась
        # із `[\w]`, тож зрізала точку й обидва найважливіші правила проходили
        # повз (спіймано пробою одразу після фіксу, до коміту).
        for token in re.findall(r"[.\w][\w./-]*", command):
            if _match_path(pattern, token.lstrip("./"), token):
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


def _mcp_scope(tool_input: dict) -> str:
    """Ціль незворотної MCP-дії — `owner/repo#N`, якщо її видно з аргументів.

    Навіщо (F-17): записана згода ключувалась лише на інструмент, тож рядок
    «лише на PR #45» відкривав злиття БУДЬ-ЯКОГО PR — слова «лише на #45»
    читала людина, а не код. Порожній рядок = ціль невідома; тоді, як і раніше,
    діє лише згода без цілі.
    """
    owner = str(tool_input.get("owner") or "").strip()
    repo = str(tool_input.get("repo") or "").strip()
    number = tool_input.get("pullNumber", tool_input.get("pull_number"))
    if not owner or not repo or number in (None, ""):
        return ""
    return f"{owner}/{repo}#{number}".lower()


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

    exec_part = executable_part(command) if command else ""
    pure_read = is_pure_read(command, pol) if command else False

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
        if command and any(exc in exec_part.lower() for exc in exceptions):
            continue
        # Читальна команда пропускає правила-підрядки: показати текст — не те
        # саме, що виконати дію. Правила на ШЛЯХИ (вище в цьому ж циклі)
        # лишаються чинними завжди, бо вони дивляться на ціль запису.
        if command and pure_read:
            continue
        for needle in rule.get("match_commands", []):
            # Збіг шукається лише у ВИКОНУВАНІЙ частині: назва дії в лапках
            # чи в тілі heredoc — це дані, а не команда.
            if command and needle.lower() in exec_part.lower():
                return Verdict(
                    level=rule.get("level", "R4"),
                    reason=f"команда містить «{needle}» (правило «{rule['id']}»)",
                    rule_id=rule["id"], why=rule.get("why", ""),
                    alternatives=rule.get("alternatives", ""),
                    target=command, resolved_target=command, notes=notes,
                )

    # ── Крок 1½. MCP-інструменти ────────────────────────────────────────────
    # Окремим кроком і ПІСЛЯ правил шляхів: інструмент може і мати захищений
    # шлях в аргументах, і бути незворотним за назвою — суворіше має вигравати.
    if tool_name.startswith("mcp__"):
        mcp = pol.get("mcp", {})
        low = tool_name.lower()
        # Виняток перевіряється ПЕРШИМ і за ТОЧНИМ збігом суфікса назви
        # (після останнього `__`), а не підрядком: підрядковий виняток сам
        # став би дірою, через яку пройшло б `slack_send_message`.
        suffix = low.rsplit("__", 1)[-1]
        if suffix in {e.lower() for e in mcp.get("except_tools", [])}:
            return Verdict("R2", f"MCP-інструмент у переліку винятків ({tool_name})",
                           target=tool_name, resolved_target=tool_name, notes=notes)
        if any(v in low for v in mcp.get("irreversible_verbs", [])):
            return Verdict(
                "R4", f"MCP-інструмент незворотної дії ({tool_name})",
                # Ідентифікатор — НА ІНСТРУМЕНТ, не на клас. Спільний
                # `mcp-irreversible` означав би, що записана згода на злиття PR
                # відкриває заразом деплой, видалення й надсилання в Slack.
                # Знайдено 2026-07-31 при спробі змержити PR #49: згода була
                # написана під `merge-to-main` (канал оболонки) і не покривала
                # ту саму дію через MCP — та сама дія, інший канал, інший ключ.
                rule_id=f"mcp-{suffix}",
                why=mcp.get("why", ""), alternatives=mcp.get("alternatives", ""),
                target=tool_name, resolved_target=resolved or tool_name, notes=notes,
                scope=_mcp_scope(tool_input),
            )
        if any(v in low for v in mcp.get("read_verbs", [])):
            return Verdict("R0", f"MCP-інструмент читання ({tool_name})", notes=notes)
        # Невідоме дієслово — НЕ вважаємо безпечним.
        return Verdict("R2", f"MCP-інструмент невідомого класу ({tool_name})",
                       target=tool_name, resolved_target=tool_name, notes=notes)

    # ── Крок 2. Недовірений вхід ────────────────────────────────────────────
    if tool_name in levels.get("R3", {}).get("tools", []):
        return Verdict("R3", f"{tool_name} приносить у контекст зовнішній текст",
                       target=command or raw_path, resolved_target=resolved, notes=notes)

    # ── Крок 3. Читання ─────────────────────────────────────────────────────
    if tool_name in levels.get("R0", {}).get("tools", []):
        return Verdict("R0", f"{tool_name} лише читає", notes=notes)
    if command:
        # Дивимось на ВИКОНУВАНУ частину, як і правила вище: `echo "| sh"` —
        # це друк тексту, а не конвеєр в оболонку, і рахувати його командою
        # з наслідками означало б знову міряти згадку замість дії.
        stripped = (exec_part or command).strip()
        for prefix in levels.get("R0", {}).get("bash_prefixes", []):
            if stripped == prefix or stripped.startswith(prefix + " "):
                # Ланцюжок АБО перенаправлення можуть ховати запис за читанням:
                # `cat > файл` — це запис, хоч і починається з `cat`.
                if any(op in stripped for op in CHAIN_OPS) or \
                        any(marker in stripped.lower() for marker in EXEC_MARKERS):
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
