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
import shlex
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
    scope: str = ""                  # ціль незворотної дії, якщо відома — F-17 (див. `consent.md`)
    # Правило вимагає цілі (`require_target` у політиці): дію без визначеної цілі
    # не відкриває жоден рядок згоди — W-12. Ставить класифікатор, читає pretooluse.
    require_target: bool = False
    # Правила R4, які зачепила ОДНА складена команда (якщо їх кілька): таку
    # команду не відкриває жоден рядок згоди — рев'ю #91.
    combined: list[str] = field(default_factory=list)

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
#
# ІСТОРІЯ. Тут стояли оболонки й інтерпретатори як ПІДРЯДКИ: `"bash -c"`,
# `"bash <<"` (дірка 2026-07-27: тіло heredoc в оболонку вважалось даними),
# `"python3 -c"`, `"python3 -"`, `"node -e"` (2026-09-27: інтерпретатор зі stdin).
#
# ПІДРЯДКИ → РОЗБІР ТОКЕНІВ (F-27, 2026-10-18). Підрядок не бачить прапорців,
# і це різало в обидва боки:
#   • ПРОПУСК — 16 форм давали R2 замість R4: `bash -lc "<дія>"`, `bash -ec`,
#     `bash -euo pipefail -c`, `sh -xc`, `python3 <<PY`, `python3 /dev/stdin`,
#     `echo … | python3`, `python3.12 -c`, `source /dev/stdin`, `env -S`,
#     `su -c`, `script -qc`, `flock -c`, `watch`, `awk 'BEGIN{system(…)}'`,
#     а `cat <<'EOF' | bash` — навіть R0 (корінь — F-28 у `_HEREDOC` нижче);
#   • ХИБНА ТРИВОГА — `"python3 -"` збігався з `python3 -I`/`-m`/`-u`, тож
#     аргумент скрипта в лапках ставав «кодом» (`python3 -I tool.py "<згадка>"`
#     → R4). Саме цей зайвий збіг випадково й прикривав `python3 -I -c`.
# Тепер оболонки та інтерпретатори розбирає `_runs_text` (нижче). Тут лишились
# форми, де підрядок надійніший за розбір: `builtin eval`, `\eval`, `| xargs`.
SHELL_INVOKERS = ("eval ", "xargs ")

# Ознаки того, що «читальна» команда насправді ВИКОНУЄ дію — без жодного
# оператора оболонки, тому `WRITE_OPS` їх не бачить. Без цього переліку
# послаблення для читання (`is_pure_read` нижче) прорубало б власну дірку:
# `find . -name x -delete` теж починається з читального префікса.
# Знайдено при проєктуванні самого фіксу: перевіряли не «чи ловить»,
# а «що саме НЕ ловитиме» (Core Rule 15).
EXEC_MARKERS = ("-exec", "-execdir", "-delete", "-ok", "--exec")


# ── Виконавці ТЕКСТУ: розбір токенів замість підрядків (F-27, 2026-10-18) ─────
# Питання одне: чи виконає щось у команді ТЕКСТ, що стоїть у самій команді
# (рядок у лапках, тіло heredoc, here-string, вхід конвеєра)? Якщо так — лапки
# там код, і правила мають бачити їхній вміст (`executable_part`).
#
# ЧЕСНА МЕЖА ПОКРИТТЯ (Core Rule 15 — перелік, а не число). Розбираються:
# оболонки, python/pypy, node/bun/deno, perl, ruby, php, lua/Rscript/julia,
# awk із `system(`/`getline`, `su`/`runuser`/`script`/`flock -c`, `watch`,
# `env -S`, `source`/`.` зі stdin. НЕ розбираються (вікно в `docs/WINDOWS.md`):
# `ssh хост "…"` (дія на іншій машині), `git -c …`/аліаси з `!`, `sed` з `e`,
# `vim -c`/`ex`, `gdb -ex`, `make`, псевдоніми оболонки й функції.

_RUNNERS = (
    (re.compile(r"(ba|da|z|k|mk|a|ya|fi|c|tc|rba|pw|xon|tcl)?sh|wish"), "shell"),
    (re.compile(r"(python|pypy)(\d+(\.\d+)*)?"), "python"),
    (re.compile(r"node|nodejs|bun"), "node"),
    (re.compile(r"deno"), "deno"),
    (re.compile(r"perl(\d+(\.\d+)*)?"), "perl"),
    (re.compile(r"ruby(\d+(\.\d+)*)?"), "ruby"),
    (re.compile(r"php(\d+(\.\d+)*)?"), "php"),
    (re.compile(r"lua(jit|\d+(\.\d+)?)?|Rscript|julia"), "e-flag"),
    (re.compile(r"[gmn]?awk"), "awk"),
    (re.compile(r"su|runuser|script|flock"), "c-flag"),
    (re.compile(r"watch"), "watch"),
    (re.compile(r"env"), "env"),
    (re.compile(r"source|\."), "source"),
)
# Схожі назви ПОЗА переліком (рев'ю #94): `ts-node`, `ipython`, `jruby`, будь-яке
# «…sh». На `main` їх ловили широкі підрядки (`"sh -c"`, `"node -e"`,
# `"python -c"`), тож без цього переліку розбір став би регресією. Для них —
# лише ЯВНІ ознаки коду (прапорець коду, heredoc, `-`, `<(…)`), без висновку
# «без операнда — програма зі stdin»: інакше `git push` (закінчується на «sh»)
# чи `npm install node` робили б кодом лапки всієї команди.
_LOOSE_RUNNERS = (
    (re.compile(r"[\w.+-]*sh"), "shell"),
    (re.compile(r"[\w.+-]*(python|pypy)[\d.]*"), "python"),
    (re.compile(r"[\w.+-]*node(js)?"), "node"),
    (re.compile(r"[\w.+-]*perl[\d.]*"), "perl"),
    (re.compile(r"[\w.+-]*ruby[\d.]*"), "ruby"),
    (re.compile(r"[\w.+-]*php[\d.]*"), "php"),
)
# Обгортки, після яких наступне слово — теж КОМАНДА (`sudo bash`, `env X=1 python3`),
# і їхні короткі прапорці з окремим значенням (`sudo -u root`, `nice -n 5`).
_WRAPPERS = {
    "env": {"-u", "-C"}, "sudo": {"-u", "-g", "-C", "-h", "-p", "-r", "-t", "-U", "-D"},
    "doas": {"-u", "-C"}, "exec": {"-a"}, "nohup": set(), "time": set(),
    "timeout": {"-s", "-k"}, "nice": {"-n"}, "ionice": {"-c", "-n", "-p"},
    "command": set(), "builtin": set(), "stdbuf": set(), "setsid": set(),
    "unbuffer": set(), "chrt": {"-p"},
}
_WRAPPER_ARG = re.compile(r"^(\d+(\.\d+)?[smhd]?|[A-Za-z_]\w*=.*)$")

# Як читати прапорці кожного виду.
#   code      — літери короткого кластера, що означають «далі КОД» (`-c`, `-lc`, `-Bc`);
#   code_long — довгі прапорці коду (`--eval`, також у формі `--eval=…`);
#   stdin     — літери «програма зі stdin» (`bash -s`);
#   arg       — короткі літери з ОКРЕМИМ аргументом, якщо стоять останніми (`-o pipefail`);
#   arg_long  — довгі прапорці з окремим аргументом;
#   rest      — літери, після яких решта кластера — аргумент (`-Wignore`, `-pi.bak`);
#   digits    — літери, що беруть лише ЦИФРИ слідом (`perl -l0 -0777`): `-lne` — це
#               `-l` `-n` `-e`, а не `-l` з аргументом «ne» (інакше `-e` пропускався б);
#   stop      — перший операнд (файл-скрипт) завершує прапорці виконавця; інакше
#               прапорці шукаються далі (безпечніше, коли список опцій з аргументом
#               неповний: хибна тривога краща за пропуск);
#   module    — літера «запустити модуль» (`python -m`): далі аргументи модуля.
_RUNNER_FLAGS: dict[str, dict] = {
    "shell":  {"code": "c", "stdin": "s", "arg": "oO", "arg_long": ("--rcfile", "--init-file"),
               "code_long": ("--command", "--init-command"), "stop": True},
    # `-m timeit "<код>"` виконує свої аргументи як код (рев'ю #94; на `main` це
    # ловив зайвий збіг «python3 -»). Інші модулі — аргументи-дані.
    "python": {"code": "c", "arg": "WX", "rest": "WX", "module": "m",
               "code_modules": ("timeit",),
               "arg_long": ("--check-hash-based-pycs",), "stop": True},
    "node":   {"code": "ep", "code_long": ("--eval", "--print"), "arg": "rC",
               "arg_long": ("--require", "--import", "--loader", "--experimental-loader",
                            "--input-type", "--conditions", "--env-file", "--title")},
    "perl":   {"code": "eE", "rest": "IMmxiCdD", "digits": "0l"},
    "ruby":   {"code": "e", "rest": "IrCEFiKTWx"},
    # `-f файл` не в `arg`: файл після нього — це і є операнд-скрипт.
    "php":    {"code": "rRBE", "arg": "cdzt"},
    "e-flag": {"code": "e"},
    "c-flag": {"code": "c", "code_long": ("--command",)},
}
_STDIN_PATHS = ("-", "/dev/stdin", "/dev/fd/0", "/proc/self/fd/0")
# Команди, у сегменті яких назва виконавця — лише ДАНІ (аргумент читання):
# `which python3`, `grep -rn bash docs`, `ls /bin/sh`. `find` — виняток, коли в
# сегменті є маркер виконання (`find . -exec sh -c …` — це вже дія).
_DATA_COMMANDS = frozenset({
    "ls", "cat", "head", "tail", "wc", "grep", "rg", "pwd", "which", "echo", "printf",
    "find", "stat", "file", "readlink", "realpath", "basename", "dirname",
})
_GIT_READ = frozenset({"status", "log", "diff", "show", "branch", "blame", "grep",
                       "ls-files", "ls-tree", "rev-parse", "remote", "describe", "shortlog"})
_AWK_EXEC = ("system(", "getline", "|&", '| "', '|"')
_PUNCT = set("|&;()<>`")
_ASSIGN = re.compile(r"^[A-Za-z_]\w*=")
_SIMPLE_WORD = re.compile(r"^[\w./+:@%=,~-]*$")
_SH_WORD = re.compile(
    r"""\n|[|&;()<>`]+|(?:[^\s|&;()<>`'"\\]+|\\.|'[^']*'|"(?:[^"\\]|\\.)*")+""", re.S)
_QUOTE_PART = re.compile(
    r"""'(?P<sq>[^']*)'|"(?P<dq>(?:[^"\\]|\\.)*)"|\\(?P<esc>.)|(?P<plain>[^'"\\]+)""", re.S)


def _sh_tokens(text: str) -> list[str]:
    """Слова оболонки. Простий вміст лапок розкривається (`'bash'` → `bash`,
    `"tool.py"` → `tool.py`), складний стає операндом-даними `Q`, а подвійні
    лапки з підстановкою лишаються як є — їх розбирає `_substitutions`."""
    out: list[str] = []
    # `\⏎` тут уже склеєно: це робить `classify()` на вході (F-29).
    for m in _SH_WORD.finditer(text):
        word = m.group(0)
        if word != "\n" and set(word) <= _PUNCT:
            out += _split_ops(word)                   # `|>` → `|` `>` (рев'ю #94)
            continue
        if word == "\n" or not any(c in word for c in "'\"\\"):
            out.append(word)
            continue
        parts: list[str] = []
        for p in _QUOTE_PART.finditer(word):
            if p.group("plain") is not None:
                parts.append(p.group("plain"))
            elif p.group("esc") is not None:
                parts.append(p.group("esc"))
            else:
                body = p.group("sq") if p.group("sq") is not None else p.group("dq")
                keep = _SIMPLE_WORD.match(body) or (p.group("dq") is not None
                                                    and ("$(" in body or "`" in body))
                parts.append(body if keep else "Q")
        out.append("".join(parts) or "Q")
    return out


# Оператори перенаправлення — ДОСЛІВНИМ переліком (рев'ю #94). Перша версія
# вважала перенаправленням будь-який пробіг пунктуації з `<`/`>`, тож злиплі
# `;>`, `|>`, `&&>` ковтали роздільник, і наступна команда зливалась із
# сегментом-читачем: `echo hi;>/dev/null bash -c "<дія>"` давав R2.
_REDIRECTS = frozenset({"<", ">", ">>", "<<", "<<<", ">&", "<&", "&>", "&>>", "<>", ">|"})
# Оператори оболонки, найдовші першими: злипла пунктуація розкладається на них.
_OPS = sorted(_REDIRECTS | {"&&", "||", ";;", "|&", "<(", ">(", "|", "&", ";", "(", ")", "`"},
              key=len, reverse=True)


def _split_ops(run: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(run):
        op = next((o for o in _OPS if run.startswith(o, i)), run[i])
        out.append(op)
        i += len(op)
    return out


def _is_redirect(tok: str) -> bool:
    return tok in _REDIRECTS


def _sh_segments(tokens: list[str]) -> list[tuple[list[str], str]]:
    """Сегменти між роздільниками: (слова, роздільник ПЕРЕД сегментом)."""
    segs: list[tuple[list[str], str]] = []
    seg: list[str] = []
    prev = ""
    for tok in tokens:
        # Процес-підстановка: виконавець бачить «програму з потоку» (`bash <(…)`),
        # а вміст `<(…)` — окрема команда (рев'ю #94: `cat <(bash -c "…")` ховав
        # `bash` у сегменті-читачі `cat`).
        if tok.startswith(("<(", ">(")):
            seg.append(tok)
            segs.append((seg, prev))
            seg, prev = [], tok
            continue
        if tok == "\n" or (set(tok) <= _PUNCT and not _is_redirect(tok)):
            segs.append((seg, prev))
            seg, prev = [], tok
        else:
            seg.append(tok)
    segs.append((seg, prev))
    return segs


def _cmd_name(tok: str) -> str:
    return os.path.basename(tok.lstrip("\\")) if tok not in (".", "..") else tok


def _runner_kind(tok: str) -> tuple[str, bool]:
    """(вид виконавця, чи це лише схожа назва поза переліком)."""
    name = _cmd_name(tok)
    kind = next((kind for rx, kind in _RUNNERS if rx.fullmatch(name)), "")
    if kind:
        return kind, False
    return next((kind for rx, kind in _LOOSE_RUNNERS if rx.fullmatch(name)), ""), True


def _command_index(seg: list[str]) -> int:
    """Індекс слова, яке оболонка виконає як КОМАНДУ (після присвоєнь і обгорток)."""
    i, n = 0, len(seg)
    # Присвоєння й ПРОВІДНІ перенаправлення (`>/dev/null bash`, `2>&1 bash`) —
    # не команда: команда — перше слово після них (рев'ю #94).
    while i < n:
        if _ASSIGN.match(seg[i]):
            i += 1
        elif seg[i].isdigit() and i + 1 < n and _is_redirect(seg[i + 1]):
            i += 1
        elif _is_redirect(seg[i]):
            i += 2
        else:
            break
    while i < n and _cmd_name(seg[i]) in _WRAPPERS:
        if _cmd_name(seg[i]) == "command" and i + 1 < n and seg[i + 1] in ("-v", "-V"):
            return n                                  # `command -v bash` — пошук, не запуск
        valued = _WRAPPERS[_cmd_name(seg[i])]
        i += 1
        while i < n and (seg[i].startswith("-") or _WRAPPER_ARG.match(seg[i])):
            i += 2 if seg[i] in valued else 1
    return i


def _git_subcommand(seg: list[str], i: int) -> tuple[str, int]:
    """Підкоманда git після глобальних опцій (`git -C dir -c k=v push`)."""
    j = i + 1
    while j < len(seg) and seg[j].startswith("-"):
        j += 2 if seg[j] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    return (seg[j], j) if j < len(seg) else ("", j)


def _data_segment(seg: list[str]) -> bool:
    """Сегмент, де назви виконавців — лише аргументи читання."""
    words = [t for t in seg if not _ASSIGN.match(t)]
    if not words:
        return True
    name = _cmd_name(words[0])
    if name == "find":
        # Префіксом, а не дослівно (рев'ю #94): `-okdir` у `EXEC_MARKERS` немає, і
        # `find … -okdir sh -c …` вважався читанням. `-fprint*`/`-fls` — запис.
        return not any(t.startswith(("-exec", "-ok", "-delete", "-fprint", "-fls"))
                       for t in words)
    if name == "git":
        return _git_subcommand(words, 0)[0] in _GIT_READ
    return name in _DATA_COMMANDS


def _scan_runner(spec: dict, args: list[str]) -> tuple[bool, bool, bool]:
    """Прапорці виконавця → (код у прапорці, є операнд-файл, програма зі stdin)."""
    code, operand, stdin = False, False, False
    k = 0
    while k < len(args):
        tok = args[k]
        k += 1
        if tok.isdigit() and k < len(args) and _is_redirect(args[k]):
            continue                                  # `2>`: номер дескриптора, не операнд
        if tok in ("<<", "<<-", "<<<"):
            stdin, k = True, k + 1                    # тіло heredoc / here-string — текст
            continue
        if _is_redirect(tok):
            k += tok in ("<", ">", ">>", ">|", "&>", "&>>", "<>", ">&", "<&")
            continue
        if tok.startswith("<("):
            return True, operand, stdin               # програма з потоку процесу
        if tok == "--":
            if k < len(args) and not operand:
                operand = True
                if args[k] in _STDIN_PATHS:
                    return True, operand, stdin
            break
        if tok.startswith("--"):
            flag = tok.split("=", 1)[0]
            if flag in spec.get("code_long", ()):
                return True, operand, stdin
            if "=" not in tok and flag in spec.get("arg_long", ()):
                k += 1
            continue
        # Прапорці шукаються й після операнда, якщо вид не `stop` (там цикл
        # уже завершився б на операнді): `node script.js -e …` — теж код.
        if len(tok) > 1 and tok[0] in "-+":
            letters, n = tok[1:], 0
            while n < len(letters):
                ch = letters[n]
                if ch in spec.get("code", ""):
                    return True, operand, stdin
                if ch in spec.get("stdin", ""):
                    stdin = True
                if ch in spec.get("module", ""):
                    # `python -m mod …`: далі — аргументи модуля; `-m timeit` — код.
                    module = letters[n + 1:] or (args[k] if k < len(args) else "")
                    return module in spec.get("code_modules", ()), True, False
                if ch in spec.get("rest", "") and n < len(letters) - 1:
                    break                             # решта кластера — аргумент
                if ch in spec.get("arg", "") and n == len(letters) - 1:
                    k += 1                            # окремий аргумент (`-o pipefail`)
                n += 1
                if ch in spec.get("digits", ""):
                    while n < len(letters) and letters[n].isdigit():
                        n += 1
            continue
        if tok in _STDIN_PATHS:
            return True, operand, stdin
        if not operand:
            operand = True
            if spec.get("stop"):
                break
        elif spec.get("stop"):
            break
    return code, operand, stdin


def _kind_runs_text(kind: str, args: list[str], raw: str, infer_stdin: bool = True) -> bool:
    """`infer_stdin` — чи можна вважати виконавця без операнда читачем програми зі
    stdin: лише виконавець із переліку і лише в позиції КОМАНДИ (рев'ю #94:
    `npm install node && git commit -m "…"` робив кодом повідомлення коміту)."""
    if kind == "awk":
        return any(marker in raw for marker in _AWK_EXEC)
    if kind == "watch":
        return infer_stdin and any(not a.startswith("-") for a in args)
    if kind == "env":
        return any(a.split("=", 1)[0] == "--split-string"
                   or (a.startswith("-") and not a.startswith("--") and "S" in a[1:])
                   for a in args)
    if kind == "source":
        return bool(args) and (args[0] in _STDIN_PATHS or args[0].startswith("<(")
                               or (args[0] in ("<<", "<<<")))
    if kind == "deno":
        return "eval" in args or any(a in _STDIN_PATHS for a in args)
    if kind == "c-flag":                              # `su -` — вхідна оболонка, не stdin-програма
        args = [a for a in args if a not in _STDIN_PATHS]
    code, operand, stdin = _scan_runner(_RUNNER_FLAGS[kind], args)
    if code or stdin:
        return True
    # `su`/`script`/`flock` без `-c` не виконують тексту з команди.
    return infer_stdin and kind != "c-flag" and not operand


def _runs_text(body: str, raw: str) -> bool:
    """Чи якийсь виконавець у команді виконає ТЕКСТ із самої команди.

    `body` — команда з відкинутими тілами heredoc (відкривач і решта рядка
    лишаються), `raw` — повна команда (для `awk`: чи є `system(` у програмі).
    """
    for text in [body, *_substitutions(body)]:
        for seg, prev in _sh_segments(_sh_tokens(text)):
            if _data_segment(seg):
                continue
            head = _command_index(seg)
            # Сегмент, якому конвеєр подає текст: виконавець без операнда читає
            # його й тоді, коли стоїть за обгорткою поза переліком `_WRAPPERS`
            # (`| strace bash`, `| sudo --user root bash`, рев'ю 2026-10-23).
            fed = prev in ("|", "|&")
            for i, tok in enumerate(seg):
                kind, loose = _runner_kind(tok)
                if kind and _kind_runs_text(kind, seg[i + 1:], raw,
                                            infer_stdin=(i == head or fed) and not loose):
                    return True
    return False


def _invokes(command: str) -> bool:
    """Чи команда віддає ТЕКСТ на виконання: підрядком (`eval`, `xargs`) або розбором."""
    body = _strip_heredocs(command)
    if any(inv in _drop_data_quotes(body).lower() for inv in SHELL_INVOKERS):
        return True
    return _runs_text(body, command)


def _write_flag_hit(link: str, write_flags: dict) -> bool:
    """Чи ланка з читальним префіксом несе прапорець ЗАПИСУ (F-25: `git branch -D`)."""
    for pref, flags in write_flags.items():
        if not (link == pref or link.startswith(pref + " ")):
            continue
        longs = {f for f in flags if f.startswith("--")}
        shorts = {f[1] for f in flags if len(f) == 2 and f[0] == "-" and f[1] != "-"}
        # Дослівні: одно-дефісні довгі (`find -fprintf`) і слова-підкоманди
        # (`git remote -v remove`) — рев'ю #94.
        exact = {f for f in flags if not f.startswith("--") and not (len(f) == 2 and f[0] == "-")}
        for tok in link[len(pref):].split():
            if tok == "--":
                break
            if tok in exact:
                return True
            if tok.startswith("--"):
                flag = tok.split("=", 1)[0]
                # git приймає однозначні СКОРОЧЕННЯ: `--del` = `--delete` (рев'ю #94).
                if flag in longs or (len(flag) >= 4 and any(f.startswith(flag) for f in longs)):
                    return True
            elif len(tok) > 1 and tok[0] == "-" and any(ch in shorts for ch in tok[1:]):
                return True
    return False


def _push_short_letters(arg: str) -> str:
    """Літери короткого кластера `git push` до `-o` (решта — значення опції)."""
    if not (len(arg) > 1 and arg[0] == "-" and arg[1] != "-"):
        return ""
    return arg[1:].split("o", 1)[0]


# git приймає однозначні СКОРОЧЕННЯ довгих прапорців (`--del` = `--delete`,
# рев'ю 2026-10-23); число — найкоротше однозначне серед опцій `git push`
# (`--d` — це ще й `--dry-run`, `--pr` — ще й `--progress`).
_PUSH_DELETE_LONG = (("--delete", 4), ("--prune", 5), ("--mirror", 3))


def _push_args_delete(args: list[str]) -> bool:
    """Аргументи `git push`, що видаляють гілку на сервері (F-26)."""
    # Сухий прогін — за ОСТАННІМ прапорцем (рев'ю #94): `--dry-run --no-dry-run`
    # пушить насправді, а `-ocontinue` — це значення `-o`, а не `-n`.
    dry = False
    for arg in args:
        if arg == "--dry-run" or "n" in _push_short_letters(arg):
            dry = True
        elif arg == "--no-dry-run":
            dry = False
    if dry:
        return False                                   # сухий прогін нічого не видаляє
    for arg in args:
        flag = arg.split("=", 1)[0]
        if any(len(flag) >= k and full.startswith(flag) for full, k in _PUSH_DELETE_LONG):
            return True
        if "d" in _push_short_letters(arg):
            return True
        if arg.startswith((":", "+:")) and len(arg.lstrip("+")) > 1:
            return True                                # `:гілка` — порожнє джерело = видалити
    return False


def _git_push_deletes(command: str) -> bool:
    """Чи `git push` у команді видаляє гілку на сервері (F-26, 2026-10-18).

    Текст у лапках, який виконають (`bash -lc "…"`), розкривається й теж
    розбирається; згадка (`echo "…"`, повідомлення коміту) — ні.
    """
    body = _strip_heredocs(command)
    code = _invokes(command)
    # Код: лапки, коми й дужки списку — лише роздільники аргументів
    # (`subprocess.run(['git','push','origin','--delete','x'])`, рев'ю #94).
    texts = [re.sub(r"['\"\\,\[\]]", " ", command)] if code \
        else [body, *_substitutions(body)]
    for text in texts:
        segs = _sh_segments(_sh_tokens(text))
        for idx, (seg, _prev) in enumerate(segs):
            # Сегмент-читач — згадка, КРІМ коду, де його вихід іде конвеєром далі:
            # у `echo "git push …" | bash` той самий `echo` подає код (рев'ю #94),
            # а в `echo "…"; python3 -c …` — лише друкує (рев'ю 2026-10-23).
            piped = idx + 1 < len(segs) and segs[idx + 1][1] in ("|", "|&")
            if _data_segment(seg) and not (code and piped):
                continue
            for i, tok in enumerate(seg):
                if _cmd_name(tok) == "git":
                    sub, j = _git_subcommand(seg, i)
                    if sub == "push" and _push_args_delete(seg[j + 1:]):
                        return True
    return False

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
# РЕШТА РЯДКА ВІДКРИВАЧА — НЕ ТІЛО (F-28, 2026-10-18). Тіло починається з
# НАСТУПНОГО рядка. Перша версія відкидала й те, що стоїть після відкривача на
# тому ж рядку, — тож у `cat <<'EOF' | bash` разом із тілом зникав ` | bash`,
# лишалось `cat <<'EOF'`, і незворотна дія в тілі ставала «чистим читанням» R0.
# `_HEREDOC_BODY` нижче вже рахував тіло з наступного рядка; тепер обидва однакові.
_HEREDOC = re.compile(r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*\n).*?^\3$", re.DOTALL | re.MULTILINE)


def _strip_heredocs(command: str) -> str:
    """Тіла heredoc — дані, КРІМ підстановок у тілі з роздільником БЕЗ лапок.

    `<<'EOF'` — літерал: тіло відкидається повністю. `<<EOF` — оболонка тіло
    розгортає, і `$(…)` у ньому ВИКОНУЄТЬСЯ (рев'ю #94, давня діра з `main`:
    `cat <<EOF⏎$(cat .env)⏎EOF` був R0). Від такого тіла лишаються його
    підстановки — саме їх і мають бачити правила.
    """
    def keep(m: re.Match) -> str:
        if m.group(2):
            return m.group(1)
        body = m.group(0)[len(m.group(1)):-len(m.group(3))]
        return m.group(1) + "".join(f"$({sub})\n" for sub in _substitutions(body, heredoc=True))
    return _HEREDOC.sub(keep, command)


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

    ПІДСТАНОВКА В ПОДВІЙНИХ ЛАПКАХ — КОД (рев'ю #91, 2026-10-18). `"$(…)"` і
    зворотні лапки оболонка виконує й у подвійних лапках, тож такий рядок не
    відкидається: інакше `ls "$(git push --force origin main)"` був чистим
    читанням (R0). Одинарні лапки — літерал, їх відкидаємо, як і раніше.
    """
    stripped = _drop_data_quotes(_strip_heredocs(command))
    if _invokes(command):
        return command
    return stripped


def _drop_data_quotes(text: str) -> str:
    """Прибирає рядки в лапках, що є ДАНИМИ; лишає подвійні лапки з підстановкою."""
    def keep_code(m: re.Match) -> str:
        s = m.group(0)
        return s if s.startswith('"') and ("$(" in s or "`" in s) else " "
    return _QUOTED.sub(keep_code, text)


def executes_inline_code(command: str) -> bool:
    """Чи команда віддає ТЕКСТ інтерпретаторові на виконання.

    `bash -c "…"`, `eval`, `| sh`, `python3 - <<PY … PY`, `node -e "…"`.
    Ознака шукається після відкидання даних — з тієї ж причини, що в
    `executable_part`: згадка `| sh` у прозі не робить команду виконанням.
    """
    if not command:
        return False
    return _invokes(command)


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

    КОНВЕЄР ЧИТАННЯ (W-18 б, 2026-10-16). `grep -rn <назва дії> docs | head`
    теж лише читає, але одинарний `|` раніше робив її «ланцюжком», і правило-
    підрядок спрацьовувало на згадку. Тепер `|` дозволено, якщо КОЖНА ланка
    починається з читального префікса; `||`, `| sh`, `| xargs`, `| tee` і будь-
    який інший оператор у ланці, як і раніше, роблять команду нечистою.
    """
    if not command:
        return False
    stripped = executable_part(command).strip()
    if not stripped:
        return False
    low = stripped.lower()
    if "||" in stripped:
        return False
    # Фоновий `&` — теж роздільник: `cat README.md & git push --force …` виконає
    # обидві команди. `CHAIN_OPS` бачив лише `&&`, тож такий рядок був R0 (рев'ю
    # #91). `2>&1` і `&>` сюди теж потрапляють — і це правильно: в них є `>`.
    if "&" in stripped:
        return False
    if _invokes(command):
        return False
    if any(marker in low for marker in EXEC_MARKERS):
        return False
    prefixes = policy.get("levels", {}).get("R0", {}).get("bash_prefixes", [])
    write_flags = policy.get("levels", {}).get("R0", {}).get("write_flags", {})
    for link in stripped.split("|"):
        link = link.strip()
        if not link or any(op in link for op in CHAIN_OPS):
            return False
        if not any(link == pref or link.startswith(pref + " ") for pref in prefixes):
            return False
    # Читальний префікс із прапорцем запису — уже не читання (F-25). Звіряємо за
    # СЛОВАМИ оболонки, а не за `stripped`: там лапки вже стерто, і `git branch
    # "-D" x` виглядав би читанням (рев'ю #94).
    if any(_write_flag_hit(" ".join(seg), write_flags)
           for seg, _prev in _sh_segments(_sh_tokens(_strip_heredocs(command)))):
        return False
    return True


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
    # Перенаправлення: `> файл`, `>> файл` (але не `2>&1` і не `>&`). Дужка
    # закриває підстановку: `"$(echo x > .env)"` — ціль `.env`, а не `.env)`.
    targets += re.findall(r">>?\s*(?!&)([^\s;|&<>)]+)", command)
    # Команди, чий аргумент — ціль запису.
    targets += re.findall(r"\b(?:tee|truncate|install)\s+(?:-\S+\s+)*([^\s;|&<>)]+)", command)
    # Друга ціль копіювання/переміщення.
    targets += re.findall(r"\b(?:cp|mv)\s+(?:-\S+\s+)*\S+\s+([^\s;|&<>)]+)", command)
    # Прапорці, чий аргумент — файл запису (рев'ю #94): `git diff --output=<файл>`,
    # `find -fprintf <файл> <формат>`, `find -fls <файл>`. Без цього F-25 бачив
    # запис, але не його ЦІЛЬ, і захищений шлях проходив як R2 (у лапках — R0).
    targets += _flag_targets(command)
    return [t.strip("'\"") for t in targets if t.strip("'\"")]


_FIND_FILE_FLAGS = ("-fprint", "-fprint0", "-fprintf", "-fls")


def _flag_targets(command: str) -> list[str]:
    """Цілі прапорців-файлів — лише у СВОЄЇ команди й за словами оболонки.

    Перша версія шукала `--output…` і `-fls` регуляркою по всьому рядку (рев'ю
    2026-10-23): `ls -fls <шлях>` і `echo "--output=<шлях>"` ставали записом
    у захищене (R4), а скорочене `git log --out=<шлях>` — не ставало.
    """
    body = _strip_heredocs(command)
    texts = [(body, False), *((s, False) for s in _substitutions(body))]
    if _invokes(command):
        # Код: лапки — роздільники, а команда стоїть будь-де (`bash -c "git diff
        # --output=…"`), як у `_git_push_deletes`.
        texts.append((re.sub(r"['\"\\,\[\]]", " ", command), True))
    out: list[str] = []
    for text, code in texts:
        for seg, _prev in _sh_segments(_sh_tokens(text)):
            for s in (range(len(seg)) if code else [_command_index(seg)]):
                name = _cmd_name(seg[s]) if s < len(seg) else ""
                args = seg[s + 1:]
                for k, tok in enumerate(args):
                    nxt = args[k + 1] if k + 1 < len(args) else ""
                    flag, eq, val = tok.partition("=")
                    if name == "git" and len(flag) >= 5 and "--output".startswith(flag):
                        out.append(val if eq else nxt)
                    elif name == "find" and tok in _FIND_FILE_FLAGS:
                        out.append(nxt)
    return [t for t in out if t]


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


def _write_tokens(command: str) -> list[str]:
    """Слова команди, які можуть бути ЦІЛЛЮ запису (для вердикту й цілі згоди).

    ДРУГИЙ ШЛЯХ, знайдений 2026-09-27 під час хвилі 4: інлайн-код в
    інтерпретаторі пише куди завгодно БЕЗ операторів оболонки —
    `python3 - <<PY` з `open('security/policy.toml','w')` усередині не має ні
    `>`, ні `tee`, тож перевірка цілей запису його не бачила. Знайдено на власній
    дії: саме так у цій сесії правилась політика, і гейт змовчав.

    Тому там, де команда ВИКОНУЄ текст і в цьому тексті є ознака ЗАПИСУ
    (`INLINE_WRITE_HINTS`), захищений шлях шукається в усій команді. Ознака
    потрібна, щоб не кричати на друк шляху: `print("<шлях>")` — не дія, і
    наявний стенд справедливо чекає там R2.

    АБСОЛЮТНИЙ ШЛЯХ (2026-10-17). Ціль порівнювалась із правилом лише у формі,
    як написано, тож `echo x > /home/user/ai-lab/.claude/settings.json` давав R2,
    хоча той самий запис інструментом Write — R4. Тепер ціль зводиться до шляху
    відносно репо (`_path_candidates`), як для читання.
    """
    tokens = _write_targets(command)
    low = command.lower()
    if executes_inline_code(command) and any(h in low for h in INLINE_WRITE_HINTS):
        # Токен МУСИТЬ допускати провідну точку: `.github/workflows/*` і
        # `.claude/settings.json` — саме такі. Перша версія регулярки починалась
        # із `[\w]`, тож зрізала точку й обидва найважливіші правила проходили
        # повз (спіймано пробою одразу після фіксу, до коміту). Так само `/` і
        # `~`: без них абсолютний шлях у коді зрізався до `home/…` і до шляху
        # відносно репо не зводився (рев'ю #91).
        tokens += re.findall(r"[./~\w][\w./~-]*", command)
    return tokens


def _hits(tokens: list[str], pattern: str, root: Path, bases: list[str]) -> list[str]:
    """Шляхи відносно репо, у які веде хоч одна форма токена й що збігаються з правилом."""
    hits: list[str] = []
    for token in tokens:
        for rel, raw in _path_candidates(token, root, bases):
            if _match_path(pattern, rel, raw):
                hits.append(rel)
                break
    return hits


# ── Читання захищеного шляху через оболонку (F-21, 2026-10-16) ──────────────
# Правило з `on_read = true` (секрети) захищає і від ЧИТАННЯ: вміст ключа,
# прочитаний у сесію, уже в транскрипті — витік не відкотиш. До фіксу `Read
# .env` давав R4, а `cat .env` — R0: той самий вміст, інший канал (урок F-7/F-14).
#
# Межа «згадка ≠ дія» зберігається: друк назви файла (`echo`, `printf`) і
# візерунок пошуку (перший позиційний аргумент `grep`/`sed`/`awk`) — не читання.

# Роздільники, що починають НОВУ команду в рядку оболонки.
_SEGMENT_SEPS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;"}
# Команди, аргументи яких — ТЕКСТ, а не файли.
_PRINTERS = {"echo", "printf", ":"}
# Команди, перший позиційний аргумент яких — візерунок чи програма, а не файл.
_PATTERN_FIRST = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "sed", "awk", "gawk"}
# Їхні прапорці зі значенням окремим аргументом (значення — не файл).
_PATTERN_VALUE_FLAGS = {"-m", "--max-count", "-A", "-B", "-C", "--context", "-t", "--type"}
# Фільтри файлів: значення — шлях чи ім'я, тож кандидат у читання. `rg -g .env`
# і `grep --include=.env` прямо називають секрет (рев'ю #91: ці значення
# пропускались як «не файл»).
_FILE_FILTER_FLAGS = {"-g", "--glob", "--iglob", "--include"}
# Прапорці `find`, значення яких — візерунок імені, а не файл.
_FIND_PATTERN_FLAGS = {"-name", "-iname", "-path", "-ipath", "-wholename",
                       "-iwholename", "-regex", "-iregex", "-lname", "-ilname"}


def _strip_comments(text: str) -> str:
    """Вирізає коментарі оболонки: `#` на ПОЧАТКУ слова поза лапками — до кінця рядка.

    `shlex` вважає коментарем `#` будь-де, тож `cat x# .env` обривався на `x`, і
    читання `.env` зникало (рев'ю #91). У bash `x#` — звичайне слово.
    """
    out: list[str] = []
    quote = ""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and quote != "'" and i + 1 < n:
            out.append(text[i:i + 2])
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t\n;&|()"):
            end = text.find("\n", i)
            if end < 0:
                break
            i = end
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _tokens(text: str) -> list[str]:
    """Розбиває рядок оболонки на слова з урахуванням лапок; оператори — окремо."""
    try:
        lex = shlex.shlex(_strip_comments(text), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""                     # коментарі вже вирізано за правилами bash
        return list(lex)
    except ValueError:                          # незакрита лапка — грубий поділ
        return text.split()


def _substitutions(text: str, depth: int = 0, heredoc: bool = False) -> list[str]:
    """Вміст підстановок команди — `$(…)` і зворотних лапок — поза одинарними лапками.

    `heredoc` — текст є тілом heredoc без лапок: там `'` — звичайний символ, і
    `'$(…)'` теж виконується (рев'ю 2026-10-23).

    Оболонка виконує їх і всередині подвійних лапок, тож це окремі команди, які
    розбираються так само, як основна (рев'ю #91: `echo "$(cat .env)"` був R0).
    """
    out: list[str] = []
    quote = ""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and quote != "'":
            i += 2
            continue
        if quote == "'":
            quote = "" if ch == "'" else quote
            i += 1
            continue
        if ch == "'" and quote != '"' and not heredoc:
            quote = "'"
        elif ch == '"':
            quote = "" if quote == '"' else '"'
        elif text.startswith("$(", i) or ch == "`":
            if ch == "`":
                end = text.find("`", i + 1)
                end = n if end < 0 else end
                inner, i = text[i + 1:end], end + 1
            else:
                level, j = 1, i + 2
                while j < n and level:
                    level += {"(": 1, ")": -1}.get(text[j], 0)
                    j += 1
                inner, i = text[i + 2:j - 1 if level == 0 else j], j
            out.append(inner)
            if depth < 3:
                out += _substitutions(inner, depth + 1)
            continue
        i += 1
    return out


# Тіло heredoc (без відкривача й роздільника).
_HEREDOC_BODY = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)^\2$", re.DOTALL | re.MULTILINE)


def _heredoc_bodies(command: str) -> list[str]:
    return [m.group(3) for m in _HEREDOC_BODY.finditer(command)]


_CD = re.compile(r"(?:^|[;&|(\n\"'])\s*(?:cd|pushd)\s+(['\"]?)([^\s;&|()'\"]+)\1")


def _cd_bases(command: str, root: Path, cwd: str | None) -> list[str]:
    """Теки, відносно яких команда адресує шляхи: корінь, `cwd` хука, цілі `cd`.

    Рев'ю #91: `cd .claude && echo '{}' > settings.json` писав у налаштування як
    R2 — шлях порівнювався так, ніби оболонка завжди стоїть у корені репо.
    Перелік — НАДмножина: шлях перевіряється відносно кожної теки (закрито за
    замовчуванням). Тека з `~`, `$` чи `-` невідома — пропускається.
    """
    base = os.path.normpath(cwd) if cwd else str(root)
    bases = list(dict.fromkeys([str(root), base]))
    cur = base
    for m in _CD.finditer(executable_part(command)):
        d = m.group(2)
        if d.startswith(("~", "$", "-")):
            continue
        cur = d if os.path.isabs(d) else os.path.normpath(os.path.join(cur, d))
        bases += [cur, d if os.path.isabs(d) else os.path.normpath(os.path.join(base, d))]
    return list(dict.fromkeys(bases))


def _read_args(command: str) -> list[str]:
    """Аргументи, які команда може ЧИТАТИ як файли.

    Пропускаються: назва команди, аргументи `echo`/`printf`, перший позиційний
    аргумент `grep`/`sed`/`awk` і значення `find -name …` (візерунки), ціль після
    `>`/`>>` (її бачить `_write_targets`), рядок після `<<<`. Значення після `<`
    — читання. Підстановки команди розбираються як окремі команди.
    У вбудованому коді інтерпретатора (`python3 -c`, `bash -c`) меж аргументів не
    видно, тож кандидатом стає кожне «слово» коду: `open('.env')` — це читання,
    хоч шлях і в лапках.
    """
    if executes_inline_code(command):
        return [t for t in re.split(r"[\s'\"`;|&<>(),=\[\]{}]+", command) if t]
    body = _strip_heredocs(command)
    out: list[str] = []
    for segment in [body] + _substitutions(body):
        out += _segment_read_args(segment)
    return out


def _segment_read_args(body: str) -> list[str]:
    find_exec = any(m in body for m in EXEC_MARKERS)
    out: list[str] = []
    cmd = ""
    positional = 0
    from_flags = take_input = take_write = take_value = take_read_value = False
    for tok in _tokens(body):
        if tok in _SEGMENT_SEPS:
            cmd, positional = "", 0
            from_flags = take_input = take_write = take_value = take_read_value = False
            continue
        if tok == "<<<":                        # here-string: далі РЯДОК, а не файл
            take_value = True
            continue
        if tok in ("<", "<>"):
            take_input = True
            continue
        if tok in (">", ">>", ">|", "&>", "&>>", ">&"):
            take_write = True
            continue
        if take_input or take_read_value:
            out.append(tok)
            take_input = take_read_value = False
            continue
        if take_write or take_value:
            take_write = take_value = False
            continue
        if not cmd:
            if re.match(r"^[A-Za-z_]\w*=", tok):        # VAR=значення перед командою
                continue
            cmd = os.path.basename(tok)
            continue
        if cmd in _PRINTERS:
            continue
        if cmd == "find" and tok in _FIND_PATTERN_FLAGS and not find_exec:
            take_value = True
            continue
        if cmd in _PATTERN_FIRST:
            if tok in ("-e", "--regexp"):
                from_flags = take_value = True
                continue
            if tok in ("-f", "--file"):
                from_flags = take_read_value = True
                continue
            if tok in _FILE_FILTER_FLAGS:
                take_read_value = True
                continue
            # Прикріплені форми (рев'ю #91): `--regexp=KEY`, `-eKEY` — візерунок
            # уже взято, тож перший позиційний аргумент — файл; `--file=F`, `-fF`,
            # `--glob=G`, `-gG`, `--include=G` — значення є кандидатом у читання.
            short = tok[:2] if len(tok) > 2 and not tok.startswith("--") else ""
            if tok.startswith("--regexp=") or short == "-e":
                from_flags = True
                continue
            if tok.startswith("--file=") or short == "-f":
                from_flags = True
                out.append(tok.split("=", 1)[1] if tok.startswith("--") else tok[2:])
                continue
            if tok.startswith(("--glob=", "--iglob=", "--include=")) or short == "-g":
                out.append(tok.split("=", 1)[1] if tok.startswith("--") else tok[2:])
                continue
            if tok in _PATTERN_VALUE_FLAGS:
                take_value = True
                continue
            if tok.startswith("-"):
                continue
            positional += 1
            if positional == 1 and not from_flags:
                continue                                # візерунок, а не файл
        out.append(tok)
    return out


def _path_candidates(token: str, root: Path, bases: list[str] | tuple = ()) -> list[tuple[str, str]]:
    """Форми токена як шляху: [(відносно репо, як написано)].

    `--env-file=.env` → `.env`; `HEAD:.env` → `.env`; `./.env` → `.env`;
    `q=@.env` і `@.env` → `.env` (так `gh api -F`, `curl -d` читають файл).
    Відносна форма зводиться до шляху відносно репо від кожної теки з `bases`
    (корінь, `cwd`, цілі `cd`), тож `..` і `cd` не ховають ціль (рев'ю #91).
    Токен із пробілом — текст (повідомлення коміту), а не шлях: інакше
    `*id_rsa*` спрацьовував би на будь-яку фразу з цим словом.
    """
    if not token or any(ch.isspace() for ch in token):
        return []
    forms = {token}
    if token.startswith("-") and "=" in token:
        forms.add(token.split("=", 1)[1])
    if "=@" in token:
        forms.add(token.split("=@", 1)[1])
    if token.startswith("@"):
        forms.add(token[1:])
    if ":" in token and "://" not in token:
        forms.add(token.split(":", 1)[1])
    out: list[tuple[str, str]] = []
    for form in forms:
        if not form or form.startswith("-"):
            continue
        norm = os.path.normpath(form)
        if os.path.isabs(norm):
            out.append((_rel(root, norm), form))
            continue
        out.append((norm, form))
        if "*" in norm:                         # глоб `**/.env` називає файл `.env`
            out.append((os.path.basename(norm), form))
        out += [(_rel(root, os.path.join(base, norm)), form) for base in bases]
    return out


# ── `gh api` на запис (F-20, 2026-10-16) ────────────────────────────────────
# Новий канал харнесу: `gh api` ходить у GitHub з повноваженнями сесії. Злиття
# PR, зміна публічності, видалення гілки, запуск workflow через нього давали R2 —
# тобто записана згода F-17 обходилась однією командою. Читання (`GET`) лишається
# R2: вердикт залежить від МЕТОДУ, а не від назви інструмента.
_GH_FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}
_GH_VALUE_FLAGS = {"-H", "--header", "-q", "--jq", "-t", "--template", "-p",
                   "--preview", "--cache"}
# Короткі прапорці зі значенням: у кластері (`-iX PUT`, `-iXPUT`) значення бере
# перший із них — решта кластера чи наступне слово (рев'ю #91: `-iX PUT` був GET).
_GH_SHORT_VALUE = set("XfFHqtp")
# `query=…` у сирому тексті: одинарні лапки — літерал, решта може підставитись.
_QUERY_ARG = re.compile(r"""(['"]?)query=(?:'[^']*'|"([^"]*)"|(\S*))""")


def _query_hidden(text: str) -> bool:
    """Чи текст GraphQL-запиту підставить оболонка (змінна, підстановка) — тоді його не видно."""
    for m in _QUERY_ARG.finditer(text):
        literal = m.group(1) == "'" or m.group(0)[len(m.group(1)) + 6:].startswith("'")
        value = m.group(2) if m.group(2) is not None else (m.group(3) or "")
        if not literal and ("$" in value or "`" in value):
            return True
    return False


def _gh_api_calls(command: str, read_methods: list[str]) -> list[tuple[str, bool]]:
    """Виклики `gh api` у команді: [(ціль «метод шлях», чи це запис)].

    Метод: `-X`/`--method`; без нього поля `-f`/`-F`/`--input` gh сам надсилає
    як POST. GraphQL — запис, якщо в запиті є `mutation`, якщо запит узято з
    файла або якщо його текст підставить оболонка: такого запиту не видно, тож
    закрито за замовчуванням.

    Виклик шукається за СЛОВАМИ, а не за текстом (рев'ю #91): `'gh' api`, `\\gh
    api` і `/повний/шлях/gh api` — той самий клієнт, а `echo gh api …` і
    `echo 'gh api …'` — друк тексту. Підстановки й тіло heredoc, подане в
    оболонку, розбираються як окремі команди.
    """
    body = _strip_heredocs(command)
    texts = [body] + _substitutions(body)
    if executes_inline_code(command):
        texts += [a or b for a, b in re.findall(r"'([^']*)'|\"([^\"]*)\"", command)]
        texts += [line for chunk in _heredoc_bodies(command) for line in chunk.splitlines()]
    reads = {m.upper() for m in read_methods}
    calls: list[tuple[str, bool]] = []
    for text in texts:
        if "gh" not in text or "api" not in text:
            continue
        toks = _tokens(text)
        cmd = ""
        for i, tok in enumerate(toks):
            if tok in _SEGMENT_SEPS:
                cmd = ""
                continue
            if not cmd:
                if re.match(r"^[A-Za-z_]\w*=", tok):
                    continue
                cmd = os.path.basename(tok)
            if cmd in _PRINTERS or os.path.basename(tok) != "gh" or \
                    i + 1 >= len(toks) or toks[i + 1] != "api":
                continue
            calls.append(_gh_api_call(toks, i + 2, text, reads))
    return calls


def _gh_api_call(toks: list[str], j: int, text: str, reads: set[str]) -> tuple[str, bool]:
    """Розбір одного виклику `gh api` від слова після `api`: (ціль, чи це запис)."""
    method, host, endpoint, query = "", "", "", ""
    fields = from_file = False

    def field(value: str) -> None:
        nonlocal fields, from_file, query
        fields = True
        if value.startswith("query=@"):
            from_file = True
        elif value.startswith("query="):
            query = value[len("query="):]

    while j < len(toks) and toks[j] not in _SEGMENT_SEPS:
        tok = toks[j]
        value = toks[j + 1] if j + 1 < len(toks) else ""
        if tok in ("-X", "--method"):
            method, j = value, j + 2
            continue
        if tok == "--hostname":
            host, j = value, j + 2
            continue
        if tok in _GH_FIELD_FLAGS:
            from_file |= tok == "--input"
            field(value)
            j += 2
            continue
        if tok in _GH_VALUE_FLAGS:
            j += 2
            continue
        if tok.startswith("--method="):
            method = tok.split("=", 1)[1]
        elif tok.startswith("--hostname="):
            host = tok.split("=", 1)[1]
        elif re.match(r"^-[A-Za-z]{2,}", tok):          # кластер: `-iX PUT`, `-XPUT`
            for k, ch in enumerate(tok[1:], 1):
                if ch in _GH_SHORT_VALUE:
                    val = tok[k + 1:] or value
                    if ch == "X":
                        method = val
                    elif ch in "fF":
                        field(val)
                    j += 1 if tok[k + 1:] else 2
                    break
            else:
                j += 1
            continue
        elif not tok.startswith("-") and not endpoint:
            endpoint = tok
        j += 1
    path = re.sub(r"^https?://[^/]+/", "", endpoint.split("?", 1)[0]).lstrip("/")
    # Інший хост — інша ціль: згода на github.com не відкриває GitHub Enterprise.
    where = f"{host.lower()}/" if host else ""
    if path == "graphql":
        write = (from_file or not query.strip() or bool(re.search(r"\bmutation\b", query))
                 or _query_hidden(text))
        name = re.search(r"\bmutation\b[^{]*\{\s*(\w+)", query)
        return ("post " + where + "graphql" + (f":{name.group(1)}" if name else ""), write)
    verb = (method or ("POST" if fields else "GET")).upper()
    # Плейсхолдер `{owner}/{repo}` gh підставляє з поточної теки — репо в цілі не
    # названо, тож такої цілі нема: згода її не відкриє.
    scope = "" if "{" in path else f"{verb} {where}{path}".lower()
    return (scope, verb not in reads)


def _verb_hit(text: str, verbs: list[str], bare: bool = False) -> bool:
    """Чи містить назва (або аргумент `method`) одне з дієслів.

    Дефіс прирівнюється до підкреслення: `notion-delete-pages` — те саме
    видалення, що `delete_file` (F-20: назви через дефіс проходили як R2).
    Обгортка `_…_` (`bare`) — лише для голого значення `method` (`delete`). На
    назві вона робила збігом дієслово в КІНЦІ: `get_latest_release` ставав R4
    (рев'ю #91).
    """
    norm = text.lower().replace("-", "_")
    if bare:
        norm = f"_{norm}_"
    return any(v in norm for v in verbs)


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


def _mcp_scope(tool_input: dict, target_keys: list[str] | tuple[str, ...] = ()) -> str:
    """Ціль незворотної MCP-дії, якщо її видно з аргументів.

    Навіщо (F-17): записана згода ключувалась лише на інструмент, тож рядок
    «лише на PR #45» відкривав злиття БУДЬ-ЯКОГО PR — слова «лише на #45»
    читала людина, а не код.

    Форми: `owner/repo#N` для PR (як і раніше), інакше
    `[owner/repo:]ключ=значення[,ключ=значення…]` — за ВСІМА наявними ключами з
    `[mcp].target_keys` у їхньому порядку (W-12). Перший ключ не розрізняв гілок:
    згода на видалення файла в `feature` відкривала те саме в `main` (рев'ю #91).
    Порожній рядок = ціль невідома. Значення з `|` чи переносом рядка ціллю не
    стає: рядок таблиці згоди його не вмістить, тож таку дію відкрити неможливо.
    """
    owner = str(tool_input.get("owner") or "").strip()
    repo = str(tool_input.get("repo") or "").strip()
    number = tool_input.get("pullNumber", tool_input.get("pull_number"))
    if owner and repo and number not in (None, ""):
        return f"{owner}/{repo}#{number}".lower()
    prefix = f"{owner}/{repo}:" if owner and repo else ""
    parts: list[str] = []
    for key in target_keys:
        value = tool_input.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (list, tuple)):
            value = ",".join(str(v) for v in value)
        text = str(value)
        if "|" in text or "\n" in text:
            return ""
        parts.append(f"{key}={text}")
    return f"{prefix}{','.join(parts)}".lower() if parts else ""


def classify(tool_name: str, tool_input: dict, root: Path | None = None,
             policy: dict | None = None, cwd: str | None = None) -> Verdict:
    """`cwd` — тека, з якої харнес виконує команду (поле входу хука); без неї — корінь."""
    root = root or repo_root()
    pol = policy or load_policy(root)
    levels = pol.get("levels", {})
    rules = pol.get("rules", [])
    resolve_symlinks = pol.get("behaviour", {}).get("resolve_symlinks", True)

    command = str(tool_input.get("command", "") or "")
    # `\⏎` оболонка ВИДАЛЯЄ — і рядки, і слова склеюються (F-29, рев'ю #94; давня
    # діра з `main`): без цього `git push \⏎ --force origin main` розривав
    # підрядок правила й давав R2. Заміна пробілом (перша версія) лишала діру
    # посеред СЛОВА: `--for\⏎ce` — це `--force` (рев'ю 2026-10-23).
    command = re.sub(r"\\\r?\n", "", command)
    raw_path = str(
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("notebook_path")
        or ""
    )

    exec_part = executable_part(command) if command else ""
    pure_read = is_pure_read(command, pol) if command else False
    mcp = pol.get("mcp", {})
    irreversible = mcp.get("irreversible_verbs", [])
    method = str(tool_input.get("method") or "").strip().lower()

    notes: list[str] = []
    resolved = raw_path
    if raw_path and resolve_symlinks:
        resolved, notes = _resolve_symlink(root, raw_path)
    rel_target = _rel(root, resolved) if resolved else ""

    # Інструмент лише ЧИТАЄ (Read/Grep/… або MCP із дієсловом читання): правила
    # шляхів, що захищають від ЗАПИСУ, на нього не діють — лише ті, що з
    # `on_read`. Інакше Read файла політики гейта зупинявся як «зміна
    # налаштувань агента» (W-18 а) — хибна тривога, що вчить обходити гейт.
    read_tool = tool_name in levels.get("R0", {}).get("tools", []) or (
        tool_name.startswith("mcp__")
        and _verb_hit(tool_name.rsplit("__", 1)[-1], mcp.get("read_verbs", []))
        and not _verb_hit(tool_name.rsplit("__", 1)[-1], irreversible)
        and not (method and _verb_hit(method, irreversible, bare=True))
    )

    # Захищені шляхи, яких торкається КОМАНДА, — по всіх правилах одразу. Ціль
    # згоди перелічує кожен шлях правила. Кожна форма шляху зводиться до шляху
    # відносно репо від кореня, `cwd` хука й цілей `cd` (рев'ю #91).
    bash_hits: list[tuple[int, str, str]] = []
    if command:
        bases = _cd_bases(command, root, cwd)
        write_tokens, read_tokens = _write_tokens(command), _read_args(command)
        for idx, rule in enumerate(rules):
            for pattern in rule.get("match_paths", []):
                bash_hits += [(idx, t, "write") for t in _hits(write_tokens, pattern, root, bases)]
                if rule.get("on_read"):
                    bash_hits += [(idx, t, "read") for t in _hits(read_tokens, pattern, root, bases)]
    bash_targets = "+".join(sorted({t for _, t, _ in bash_hits}))

    # Шляхи з аргументів ІНСТРУМЕНТА — так само по всіх правилах. MCP-інструмент
    # може нести кілька файлів у масиві `files` (`push_files`), а правило
    # дивилось лише на `path`: воркфлоу через MCP проходив як R2 (2026-10-17).
    # Файл в іншому репозиторії — інша ціль, тож для MCP ціль несе `owner/repo:`.
    paths = [(rel_target, raw_path)] if raw_path else []
    for item in tool_input.get("files") or []:
        if isinstance(item, dict) and item.get("path"):
            paths.append((os.path.normpath(str(item["path"]).lstrip("/")), str(item["path"])))
    # Фільтр файлів інструмента пошуку (`glob` у Grep), що прямо називає файл, —
    # теж шлях: `Grep glob=.env` читав секрет як R0 (рев'ю #91).
    for piece in re.split(r"[{},\s]+", str(tool_input.get("glob") or "")):
        if piece:
            paths.append((os.path.basename(piece) or piece, piece))
    tool_hits: list[tuple[int, str]] = []
    for idx, rule in enumerate(rules):
        if read_tool and not rule.get("on_read"):
            continue
        for rel, raw in paths:
            if any(_match_path(p, rel, raw) for p in rule.get("match_paths", [])):
                tool_hits.append((idx, rel))
    owner = str(tool_input.get("owner") or "").strip()
    repo = str(tool_input.get("repo") or "").strip()
    in_repo = f"{owner}/{repo}:" if tool_name.startswith("mcp__") and owner and repo else ""
    tool_targets = in_repo + "+".join(sorted({t for _, t in tool_hits}))

    # ── Крок 1. Явні правила R4 мають найвищий пріоритет ────────────────────
    # Спершу найсуворіше: якщо дія збігається з чимось незворотним — далі не дивимось.
    #
    # ВАЖЛИВО: правила на ШЛЯХИ перевіряються і для Bash-команд, не лише для
    # Write/Edit. Інакше весь захист шляхів обходиться однією командою:
    # `cat > .github/workflows/evil.yml` — і це не гіпотеза, а дірка, знайдена
    # 2026-07-27 у момент, коли гейт заблокував власного автора на Write, а той
    # мав під рукою Bash. Гейт, який захищає один спосіб дії з двох, не захищає.
    #
    # ЦІЛЬ ЗГОДИ (W-12, 2026-10-16). Для правила з `require_target` вердикт несе
    # ціль: шлях відносно репо, перелік шляхів команди, «метод шлях» `gh api` або
    # саму команду. Рядок згоди мусить назвати її точно (`правило@ціль`); рядок
    # без цілі таку дію не відкриває. До цього `require_target` у політиці не
    # читав жоден рядок коду — політика обіцяла те, чого гейт не робив.
    #
    # Частини ланцюжка (`;`, `&&`, `||`, `&`, новий рядок) — для винятків: виняток
    # діє лише в ТІЙ команді, де стоїть.
    segments = re.split(r"&&|\|\||[;&\n]", exec_part.lower()) if command else []
    # У коді інтерпретатора аргументи бувають СПИСКОМ (`['git','push','--force',…]`):
    # лапки, коми й дужки там — лише роздільники (рев'ю #94).
    if command and _invokes(command):
        segments += re.split(r"&&|\|\||[;&\n]", re.sub(r"['\"\\,\[\]]", " ", exec_part.lower()))
    # Пробіли й табуляції — до одного пробілу (F-29, давня діра з `main`): підрядки
    # правил пишуться з одним, тож `push  --force` (два пробіли) чи табуляція
    # давали R2 на тій самій незворотній дії.
    segments = [" ".join(seg.split()) for seg in segments]

    def rule_verdict(idx: int, rule: dict) -> Verdict | None:
        need = bool(rule.get("require_target"))

        def verdict(reason: str, target: str, real: str, scope: str) -> Verdict:
            return Verdict(level=rule.get("level", "R4"), reason=reason, rule_id=rule["id"],
                           why=rule.get("why", ""), alternatives=rule.get("alternatives", ""),
                           target=target, resolved_target=real, notes=notes,
                           scope=scope if need else "", require_target=need)

        hit = next((h for h in bash_hits if h[0] == idx), None)
        if hit:
            return verdict(f"команда {'читає' if hit[2] == 'read' else 'пише у'} захищений "
                           f"шлях «{hit[1]}» (правило «{rule['id']}»)",
                           command, command, bash_targets)
        tool_hit = next((h for h in tool_hits if h[0] == idx), None)
        if tool_hit:
            return verdict(f"шлях «{tool_hit[1]}» збігається з правилом «{rule['id']}»",
                           raw_path or tool_hit[1], resolved or tool_hit[1], tool_targets)
        # `gh api` на запис: вердикт за МЕТОДОМ, а не за назвою (F-20). Виклик
        # без цілі (плейсхолдер репо) робить без цілі всю команду.
        if command and rule.get("match_gh_api_write"):
            writes = sorted({s for s, w in _gh_api_calls(
                command, rule.get("read_methods", ["GET", "HEAD"])) if w})
            if writes:
                return verdict(f"`gh api` змінює стан на GitHub (правило «{rule['id']}»)",
                               command, command, "" if "" in writes else "+".join(writes))
        # Видалення гілки на сервері — за РОЗБОРОМ `git push`, а не підрядком (F-26):
        # назва remote будь-яка, а refspec `:гілка` пишеться без пробілів.
        if command and rule.get("match_git_push_delete") and _git_push_deletes(command):
            return verdict(f"`git push` видаляє гілку на сервері (правило «{rule['id']}»)",
                           command, command, " ".join(command.split()))
        # Читальна команда пропускає правила-підрядки: показати текст — не те
        # саме, що виконати дію. Правила на ШЛЯХИ (вище) лишаються чинними завжди,
        # бо вони дивляться на ціль запису.
        if not command or pure_read:
            return None
        # Виняток перевіряється ПЕРЕД збігом: безпечна форма дії не має
        # блокуватись лише тому, що містить у собі підрядок небезпечної. Але лише
        # у своїй частині ланцюжка: `--force-with-lease` в одній команді не
        # прикриває `--force` у сусідній (рев'ю #91).
        exceptions = [e.lower() for e in rule.get("except_commands", [])]
        for needle in rule.get("match_commands", []):
            # Збіг шукається лише у ВИКОНУВАНІЙ частині: назва дії в лапках
            # чи в тілі heredoc — це дані, а не команда.
            if any(needle.lower() in seg and not any(exc in seg for exc in exceptions)
                   for seg in segments):
                return verdict(f"команда містить «{needle}» (правило «{rule['id']}»)",
                               command, command, " ".join(command.split()))
        return None

    verdicts: list[Verdict] = []
    for idx, rule in enumerate(rules):
        found = rule_verdict(idx, rule)
        if found is None:
            continue
        if not command:
            return found                # дія інструмента: одна ціль — перше правило
        verdicts.append(found)
    if verdicts:
        # Складена команда з КІЛЬКОМА незворотними діями (рев'ю #91): вердикт —
        # за першим правилом, а згода на нього відкривала б і решту (`echo x >
        # .claude/settings.json && git push --force …`). Тепер `combined` перелічує
        # усі правила, і жоден рядок таку команду не відкриває — її розбивають.
        first = verdicts[0]
        rule_ids = list(dict.fromkeys(v.rule_id for v in verdicts))
        if len(rule_ids) > 1:
            first.combined = rule_ids
        return first

    # ── Крок 1½. MCP-інструменти ────────────────────────────────────────────
    # Окремим кроком і ПІСЛЯ правил шляхів: інструмент може і мати захищений
    # шлях в аргументах, і бути незворотним за назвою — суворіше має вигравати.
    if tool_name.startswith("mcp__"):
        # Виняток перевіряється ПЕРШИМ і за ТОЧНИМ збігом суфікса назви
        # (після останнього `__`), а не підрядком: підрядковий виняток сам
        # став би дірою, через яку пройшло б `slack_send_message`.
        suffix = tool_name.lower().rsplit("__", 1)[-1]
        excepted = {e.lower().replace("-", "_") for e in mcp.get("except_tools", [])}
        if suffix.replace("-", "_") in excepted:
            return Verdict("R2", f"MCP-інструмент у переліку винятків ({tool_name})",
                           target=tool_name, resolved_target=tool_name, notes=notes)
        # Дієслово — у назві (з дефісами нарівні з підкресленнями) АБО в
        # аргументі `method`: один інструмент може і читати, і видаляти, а дія
        # тоді живе в аргументі (F-20: `actions_run_trigger` з
        # `delete_workflow_run_logs` проходив як R2).
        by_name = _verb_hit(suffix, irreversible)
        by_method = bool(method) and _verb_hit(method, irreversible, bare=True)
        if by_name or by_method:
            return Verdict(
                "R4", f"MCP-інструмент незворотної дії ({tool_name}"
                      f"{'' if by_name else ' · ' + method})",
                # Ідентифікатор — НА ІНСТРУМЕНТ, не на клас. Спільний
                # `mcp-irreversible` означав би, що записана згода на злиття PR
                # відкриває заразом деплой, видалення й надсилання в Slack.
                # Знайдено 2026-07-31 при спробі змержити PR #49: згода була
                # написана під `merge-to-main` (канал оболонки) і не покривала
                # ту саму дію через MCP — та сама дія, інший канал, інший ключ.
                # Дія з аргументу `method` — окремий ключ: згода на запуск
                # workflow не відкриває видалення його журналів.
                rule_id=f"mcp-{suffix}" if by_name else f"mcp-{suffix}.{method}",
                why=mcp.get("why", ""), alternatives=mcp.get("alternatives", ""),
                target=tool_name, resolved_target=resolved or tool_name, notes=notes,
                scope=_mcp_scope(tool_input, mcp.get("target_keys", [])),
                require_target=bool(mcp.get("require_target")),
            )
        if _verb_hit(suffix, mcp.get("read_verbs", [])):
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
    if command and pure_read:
        # Дивимось на ВИКОНУВАНУ частину, як і правила вище: `echo "| sh"` —
        # це друк тексту, а не конвеєр в оболонку. Ланцюжок, перенаправлення чи
        # маркер виконання роблять команду нечистою (`cat > файл` — запис), а
        # конвеєр із самих читальних ланок — ні (`is_pure_read`, W-18 б).
        first = (exec_part or command).strip().split("|", 1)[0].strip()
        prefix = next((p for p in levels.get("R0", {}).get("bash_prefixes", [])
                       if first == p or first.startswith(p + " ")), "")
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
