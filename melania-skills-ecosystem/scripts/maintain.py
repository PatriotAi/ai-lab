#!/usr/bin/env python3
"""maintain.py — єдиний гейт обслуговування екосистеми melania-skills.

Кодифікує повторювані обов'язкові перевірки, щоб їх не треба було пам'ятати вручну.

  python3 maintain.py verify   # read-only: цілісність MANIFEST + усі guard --validate
                               #            + safety-scan скриптів. Exit!=0 при проблемі.
  python3 maintain.py resync   # після свідомого оновлення білду: пере-знімає baseline
                               #   для змінених SKILL.md, перераховує похідні поля MANIFEST
                               #   (хеші, лічильники evals, підсумки) і лічильники у
                               #   MELANIA-BOOTSTRAP.md. Версії/дата білду беруться з
                               #   frontmatter/пакета — не вигадуються. Наприкінці — verify.

  python3 maintain.py package [skill|all]
                               # upload-safe .skill-пакети для скіл-стору claude.ai:
                               #   folder-at-root, БЕЗ крапкових шляхів (.snapshots тощо —
                               #   завантажувач їх відхиляє) і БЕЗ evals/ (пакувальник
                               #   стору їх усе одно вирізає — source-істина лишається
                               #   в цьому репо/zip). Кладе у dist/.

Запускати з будь-якої теки: шляхи визначаються відносно розташування скрипта.
"""
import json, hashlib, re, sys, subprocess, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # melania-skills-ecosystem/
REPO = ROOT.parent                                     # корінь ai-lab (для вказівників [E])
SKILLS = ROOT / "skills"
MANIFEST = ROOT / "MANIFEST.json"
BOOTSTRAP = ROOT / "MELANIA-BOOTSTRAP.md"

# Небезпечні патерни у скриптах скілів (skill_guard.py тощо мають лишатись локальними).
DANGER = re.compile(r"\b(subprocess|socket|urllib|requests|os\.system|eval\(|exec\(|__import__|pickle\.loads?)"
                    r"|curl |wget |base64\.b64decode|getattr\(os|https?://")

# Реальні ЗНАЧЕННЯ секретів (не згадки в документації): формат-специфічні хвости.
SECRET_VALUES = re.compile(
    r"sk-ant-[a-zA-Z0-9_-]{10,}|ghp_[a-zA-Z0-9]{20,}|gho_[a-zA-Z0-9]{20,}"
    r"|AKIA[A-Z0-9]{12,}|xox[bp]-[0-9]{5,}|AIza[a-zA-Z0-9_-]{20,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY")
SECRET_SCAN_EXT = {".md", ".py", ".json", ".html", ".txt", ".yml", ".yaml", ".js"}

# Скіли, чий guard приймає підкоманди замість --snapshot/--validate.
SUBCMD_GUARDS = {"notebooklm-connector": ("snapshot", "validate")}
# Скіли, чий guard не тримає читабельний baseline з md5 (перевірка суто інваріантна).
NO_MD5_BASELINE = {"rlm-harness"}


def md5_text(p: Path) -> str:
    return hashlib.md5(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def sha16(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def frontmatter_version(skill_md: Path) -> str:
    m = re.search(r'^\s*version:\s*["\']?([\d.]+)', skill_md.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "?"


def eval_count(evals_json: Path) -> int:
    data = json.loads(evals_json.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return len(data.get("evals", []))
    return len(data) if isinstance(data, list) else 0


def guard_path(skill: str) -> Path | None:
    g = SKILLS / skill / "scripts" / "skill_guard.py"
    return g if g.exists() else None


def run_guard(skill: str, action: str) -> tuple[int, str]:
    """action: 'validate' | 'snapshot'. Повертає (exit_code, first_line)."""
    g = guard_path(skill)
    if not g:
        return (0, "(no guard)")
    if skill in SUBCMD_GUARDS:
        arg = SUBCMD_GUARDS[skill][0 if action == "snapshot" else 1]
    else:
        arg = "--snapshot" if action == "snapshot" else "--validate"
    r = subprocess.run([sys.executable, str(g), arg], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip().splitlines()
    return (r.returncode, out[0] if out else "")


def baseline_md5(skill: str) -> str | None:
    """Зчитує md5, який guard зберіг у своєму baseline (різні шляхи/поля у варіантів)."""
    for rel in (f"scripts/.snapshots/latest.json", f".snapshots/baseline.json"):
        p = SKILLS / skill / rel
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8")).get("md5")
            except Exception:
                return None
    return None


def skill_dirs():
    return sorted(d.name for d in SKILLS.iterdir() if d.is_dir() and (d / "SKILL.md").exists())


# ---------------------------------------------------------------- verify
def claim_evidence_problems(name: str, txt: str, root: Path | None = None,
                            skill_dir: Path | None = None) -> list[str]:
    """Гейт доказовості (Core Rule 14): фактичні твердження несуть тег [E]/[C]/[S].

    Чому саме секція «Critical Facts», а не «Core Rule»: правило-директива не буває
    істинним чи хибним — воно обов'язкове, тег там був би театром. Тегуємо лише те,
    що можна спростувати фактом.

    [E] вимагає ВКАЗІВНИКА на перевірку (шлях до тесту, файл або дата) — інакше
    «перевірено» лишається словом, а це і є той дефект, який гейт закриває.

    Формат вказівника ще НЕ доказ. Випадок №5 із брифу (скіли декларували evals
    з v1.2.1, артефакту не існувало) проходив би формат-перевірку без проблем,
    тому [E] мусить назвати шлях, який РЕАЛЬНО існує в репозиторії: доказ має
    бути знаходжуваним, а не правдоподібно виглядати. Дата лишається дозволеним
    додатковим контекстом, але сама по собі доказом не є — зовнішній прогін
    оформлюється записом у docs/ і цитується як шлях.

    Вказівник резолвиться від кореня репо АБО від теки самого скіла: посилання на
    власний `references/…` — законний доказ, і вимагати для нього повний шлях від
    кореня означало б хибну тривогу (знайдено аудитом до появи реального випадку).

    Винесено окремою функцією (root — параметр), щоб canary-тести ганяли її на
    тимчасовому тексті й тимчасовому корені, а не мутували робочі файли
    репозиторію (урок 2026-07-21).
    """
    root = root or REPO
    problems: list[str] = []
    # Секція обов'язкова в КОЖНОМУ скілі. Без цієї вимоги гейт покривав лише ті скіли,
    # де секція випадково була (2 з 28) — «у мене немає тверджень» ставало способом
    # обійти правило, і решта проходила порожньо.
    if not re.search(r"^##+ +Critical Facts", txt, re.M):
        problems.append(f"{name}: немає секції «Critical Facts» — нема чого пред'явити гейту")
        return problems
    for sec in re.finditer(r"^##+ +Critical Facts[^\n]*$", txt, re.M):
        start = sec.end()
        nxt = re.search(r"^##+ ", txt[start:], re.M)
        body = txt[start:start + (nxt.start() if nxt else len(txt))]
        for bullet in re.findall(r"^[-*] +.*", body, re.M):
            tag = re.search(r"\[(E|C|S)\]", bullet)
            if not tag:
                problems.append(f"{name}: факт без тега доказовості — {bullet[2:60].strip()}")
                continue
            if tag.group(1) != "E":
                continue
            # Кандидати-шляхи: беремо ВСІ, вимагаємо, щоб ХОЧА Б ОДИН існував.
            # (У тексті факту поруч живуть не-файлові згадки на кшталт `sw.js` —
            # вимагати існування кожної було б хибною тривогою.)
            paths = re.findall(r"[\w][\w./-]*\.(?:py|mjs|js|sh|md|json|ya?ml|html|txt)\b", bullet)
            has_date = re.search(r"\d{4}-\d{2}-\d{2}", bullet)
            if not paths and not has_date:
                problems.append(f"{name}: [E] без вказівника на перевірку — {bullet[2:60].strip()}")
            elif not any((root / p.lstrip("./")).exists()
                         or (skill_dir and (skill_dir / p.lstrip("./")).exists())
                         for p in paths):
                problems.append(
                    f"{name}: [E] без доказу, який існує на диску "
                    f"({'шляхи: ' + ', '.join(sorted(set(paths))) if paths else 'лише дата'}) "
                    f"— {bullet[2:60].strip()}")
    return problems


def version_triad_problems(name: str, txt: str, manifest_version: str | None = None) -> list[str]:
    """Крок «bump + H1-синхрон» звітується словами — тут він стає перевіркою.

    Інцидент: melania лишалась `# … — v2.20.0` при банері `> **v2.21.0**`, хоч хвиля
    чесно звітувала «H1-синхрон». Звіт був щирий — виконавець вірив, що зробив крок.
    Версія мусить збігатися в УСІХ місцях: frontmatter · H1 · банер · MANIFEST ·
    верхній запис CHANGELOG.

    Толерантність до `- **1.1.0** (…)` без префікса `v` обов'язкова: це усталена
    конвенція github-collab, і сувора регулярка дала б хибну тривогу (перевірено).
    """
    problems: list[str] = []
    fm = re.search(r'^\s*version:\s*["\']?([\d.]+)', txt, re.M)
    if not fm:
        return [f"{name}: у frontmatter немає version"]
    v = fm.group(1)
    h1 = re.search(r"^# .*$", txt, re.M)
    if h1:
        got = re.findall(r"v(\d+\.\d+\.\d+)", h1.group(0))
        if got and got[0] != v:
            problems.append(f"{name}: H1 v{got[0]} != frontmatter {v}")
    ban = re.search(r"^> \*\*v?(\d+\.\d+\.\d+)\*\*", txt, re.M)
    if ban and ban.group(1) != v:
        problems.append(f"{name}: банер v{ban.group(1)} != frontmatter {v}")
    ch = re.search(r"^## (?:Зміни|Changelog)\s*\n(?:_.*\n)?[-*]\s*\*\*v?([\d.]+)\*\*", txt, re.M)
    if not ch:
        problems.append(f"{name}: не знайдено верхнього запису CHANGELOG")
    elif ch.group(1) != v:
        problems.append(f"{name}: верхній CHANGELOG v{ch.group(1)} != frontmatter {v}")
    if manifest_version and manifest_version != v:
        problems.append(f"{name}: MANIFEST {manifest_version} != frontmatter {v}")
    return problems


def crossref_problems(name: str, txt: str) -> list[str]:
    """Посилання «П.N» мусить вести на ТОЙ пункт, який обіцяє.

    Інцидент: у чек-лист вставили новий пункт 6, нумерація з'їхала, і рядок
    «П.7: continuation-memory snapshot» став вказувати на пункт про повноту доставки.
    Перевірка «чи існує пункт N» цього НЕ ловила — пункт 7 існував. Тому звіряємо
    змістовий ідентифікатор: латинський токен після посилання має бути в пункті N.
    Хвіст обрізаємо перед наступним «П.» — інакше багатопосилальні рядки шумлять.

    Секції історії не перевіряються з тієї ж причини, що й лічильники: запис у
    CHANGELOG цитує МИНУЛИЙ стан («посилання П.6/П.7/П.8 з'їхали»), а не робить
    живе посилання. Без цього виключення власний опис виправлення дає хибну тривогу.
    """
    txt = re.split(r"^## (?:Зміни|Changelog)", txt, flags=re.M)[0]
    items = {int(m.group(1)): m.group(2) for m in re.finditer(r"^(\d+)\.\s+(.*)$", txt, re.M)}
    problems: list[str] = []
    for m in re.finditer(r"П\.(\d+)", txt):
        n = int(m.group(1))
        if n not in items:
            problems.append(f"{name}: посилання П.{n}, а пункту {n} у файлі немає")
            continue
        tail = txt[m.end():m.end() + 90]
        tail = re.split(r"П\.\d|\|", tail)[0]          # до наступного посилання/комірки
        toks = re.findall(r"[a-zA-Z][\w-]{4,}", tail)
        if toks and not any(t in items[n] for t in toks):
            problems.append(f"{name}: П.{n} обіцяє «{toks[0]}», але пункт {n} про інше "
                            f"— {items[n][:50]}")
    return problems


# Лічильники, що описують ВМІСТ ІНШОГО ФАЙЛУ. Реєстр навмисно крихітний:
# новий запис додається лише за реальним інцидентом, не «про запас».
COUNTER_REGISTRY = [
    (r"(\d+)\s+дисциплін", "skills/rlm-harness/references/conductor-standard.md",
     r"^(\d+)\.\s+\*\*"),
]


def counter_problems(name: str, txt: str, root: Path | None = None) -> list[str]:
    """Число, що описує інший файл, мусить збігатися з фактом у тому файлі.

    Інцидент: `rlm-harness` роками казав «8 дисциплін», тоді як у стандарті їх 10.
    Гейт актуальності це не ловив: він звіряв лічильники в README/BOOTSTRAP, а не
    згадки про вміст сусіднього файлу.

    Секції історії (`## Зміни` / `## Changelog`) НЕ перевіряються: там числа —
    цитати минулого стану, і перевірка їх дала б 3 хибні тривоги (виміряно).
    """
    root = root or ROOT
    live = re.split(r"^## (?:Зміни|Changelog)", txt, flags=re.M)[0]
    problems: list[str] = []
    for pat, rel, count_pat in COUNTER_REGISTRY:
        target = root / rel
        if not target.exists():
            continue
        actual = len({m.group(1) for m in
                      re.finditer(count_pat, target.read_text(encoding="utf-8"), re.M)})
        for m in re.finditer(pat, live):
            if int(m.group(1)) != actual:
                problems.append(f"{name}: «{m.group(0)}» != фактичних {actual} у {rel}")
    return problems


# Літери, яких в українському тексті бути не може, і польська діакритика.
FOREIGN_LETTERS = re.compile(r"[ыъэёЫЪЭЁłążźśćńĄĘŁŻŹŚĆŃ]")
_CYR = re.compile(r"[а-яіїєґА-ЯІЇЄҐ]")
_LAT = re.compile(r"[a-zA-Z]")


def text_hygiene_problems(name: str, txt: str) -> list[str]:
    """Омоглифи й чужомовні літери в тексті скіла.

    Інцидент: партія суб-агентів принесла полонізм «zespołу» і кириличну «е»
    всередині слова `evals` — тобто РІВНО той омоглиф-клас, який лабораторія вже
    ловила у зовнішньому вході, але у власному тексті не перевіряла. Ця ж перевірка
    знайшла успадкований дефект «aдаптовано» з латинською `a`.

    Код і бектики виключено: там латиниця легітимна. Ділимо на не-літерах, тому
    складені слова на кшталт «MCP-інструменти» хибної тривоги не дають (0 на 28 скілах).
    """
    clean = re.sub(r"```.*?```", "", txt, flags=re.S)
    clean = re.sub(r"`[^`]*`", "", clean)
    problems: list[str] = []
    for i, line in enumerate(clean.splitlines(), 1):
        if FOREIGN_LETTERS.search(line):
            bad = "".join(sorted(set(FOREIGN_LETTERS.findall(line))))
            problems.append(f"{name}: чужомовні літери [{bad}] — {line.strip()[:60]}")
        for tok in re.split(r"[^\wЀ-ӿ]+", line):
            for sub in re.split(r"[_\d]+", tok):
                if len(sub) > 2 and _CYR.search(sub) and _LAT.search(sub):
                    problems.append(f"{name}: змішані абетки в слові «{sub}» (омоглиф?)")
    return problems


def verify() -> int:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems, total_evals = [], 0
    dirs = skill_dirs()

    if man.get("skill_count") != len(dirs):
        problems.append(f"skill_count {man.get('skill_count')} != {len(dirs)} тек")

    for name in dirs:
        d = SKILLS / name
        skill_md, evals = d / "SKILL.md", d / "evals" / "evals.json"
        meta = man["skills"].get(name)
        if not meta:
            problems.append(f"{name}: відсутній у MANIFEST"); continue
        n = eval_count(evals); total_evals += n
        checks = {
            "SKILL.md hash": (sha16(skill_md), meta["sha256_16"]["SKILL.md"]),
            "evals hash": (sha16(evals), meta["sha256_16"]["evals/evals.json"]),
            "version": (frontmatter_version(skill_md), meta["version"]),
            "eval_cases": (n, meta["eval_cases"]),
        }
        for label, (actual, declared) in checks.items():
            if actual != declared:
                problems.append(f"{name}: {label} {actual} != MANIFEST {declared}")

    if total_evals != man.get("total_eval_cases"):
        problems.append(f"total_eval_cases {man.get('total_eval_cases')} != {total_evals} фактичних")

    # ── Гейт актуальності: КОЖНА згадка версії/лічильника в репо = факту ──
    # (правило актуальності: документація не має права відставати від стану)
    n_skills = len(dirs)
    mel_ver = man["skills"].get("melania-skill-master-administrator", {}).get("version")
    gov = re.search(r"v([\d.]+)", man.get("governance", ""))
    if mel_ver and gov and gov.group(1) != mel_ver:
        problems.append(f"MANIFEST.governance v{gov.group(1)} != melania {mel_ver}")

    # Похідні лічильники в будь-якому документі екосистеми та ключових файлах репо
    doc_targets = [ROOT / "MELANIA-BOOTSTRAP.md", ROOT / "README-FOR-HUMANS.md",
                   ROOT / "README-FOR-AI.md", ROOT / "INSTALL-PROMPT.txt",
                   ROOT.parent / "README.md"]
    for doc in doc_targets:
        if not doc.exists():
            continue
        txt = doc.read_text(encoding="utf-8", errors="replace")
        rel = doc.name
        for pat, actual, label in (
            (r"(\d+)\s+(?:AI-)?(?:скіл|навич|skill)|[Сс]кілів:\s*(\d+)", n_skills, "кількість скілів"),
            (r"(\d+)\s+eval-кейс|[Ee]val-кейсів:\s*(\d+)|тест-кейси\s*\((\d+)", total_evals, "кількість evals"),
        ):
            found = [g for tup in re.findall(pat, txt) for g in (tup if isinstance(tup, tuple) else (tup,)) if g]
            stale = {v for v in found if v.isdigit() and int(v) != actual and 10 < int(v) < 1000}
            if stale:
                problems.append(f"{rel}: застаріла {label} {sorted(stale)} != {actual}")
        for m_gov in re.findall(r"melania v([\d.]+)", txt):
            if mel_ver and m_gov != mel_ver:
                problems.append(f"{rel}: governance v{m_gov} != melania {mel_ver}")
        # дати «збірка/зафіксовано/верифіковано» = MANIFEST.built
        built = man.get("built", "")
        stale_dates = {d for d in re.findall(
            r"(?:збірк[аи]|зафіксовано|верифіковано|перевірено|Дата збірки:)\s*(\d{4}-\d{2}-\d{2})", txt)
            if d != built}
        if stale_dates:
            problems.append(f"{rel}: застаріла дата {sorted(stale_dates)} != built {built}")

    # Версії в маршрутній таблиці BOOTSTRAP = MANIFEST
    bs = ROOT / "MELANIA-BOOTSTRAP.md"
    if bs.exists():
        rows = dict(re.findall(r"^\|\s*([a-z0-9-]+)\s*\|\s*([\d.]+)\s*\|", bs.read_text(encoding="utf-8"), re.M))
        for name, v in rows.items():
            if name in man["skills"] and man["skills"][name]["version"] != v:
                problems.append(f"BOOTSTRAP: {name} v{v} != MANIFEST {man['skills'][name]['version']}")
        for name in set(man["skills"]) - set(rows):
            problems.append(f"BOOTSTRAP: немає рядка маршрутизації для {name}")

    # ── Гейт доказовості (Core Rule 14 Claim-evidence) ────────────────────
    # Клас дефекту: текст скіла стверджує ширше, ніж підтверджено (5 випадків,
    # 2026-07-19…26; жоден не спіймано самоперевіркою). Тегуємо ФАКТИЧНІ
    # твердження — секція «Critical Facts». Директиви («Core Rule») НЕ тегуються:
    # правило не буває істинним чи хибним, воно обов'язкове — тег там був би театром.
    #   [E] перевірено ділом → ОБОВ'ЯЗКОВИЙ вказівник (шлях/файл/дата)
    #   [C] обґрунтоване, машинно не перевірене   [S] гіпотеза
    claim_problems = []
    # ── Самоперевірний протокол (Core Rule 15) ────────────────────────────
    # Кроки, які досі звітувались словами (bump/H1-синхрон, крос-посилання,
    # лічильники про інші файли, чистота тексту), стають машинними. Підстава —
    # чотири дрейфи, що пережили попередню хвилю попри чесні звіти про виконання.
    self_check_problems = []
    for name in dirs:
        d = SKILLS / name
        txt = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        claim_problems += claim_evidence_problems(name, txt, skill_dir=d)
        self_check_problems += version_triad_problems(
            name, txt, man["skills"].get(name, {}).get("version"))
        self_check_problems += crossref_problems(name, txt)
        self_check_problems += counter_problems(name, txt)
        self_check_problems += text_hygiene_problems(name, txt)

    # Guards. Деякі guard (notebooklm) дописують runtime-лог audit.jsonl —
    # verify має лишатись read-only, тож зберігаємо й відновлюємо такі логи.
    logs = {p: p.read_bytes() for p in SKILLS.rglob("audit.jsonl")}
    guard_fail = []
    for name in dirs:
        code, first = run_guard(name, "validate")
        if code != 0:
            guard_fail.append(f"{name}: {first}")
    for p, data in logs.items():
        if p.read_bytes() != data:
            p.write_bytes(data)

    # Safety scan (py-скрипти: небезпечні виклики; docs/html не сканується DANGER-ом,
    # бо там легітимні приклади з requests/curl/URL — для них є SECRET_VALUES нижче)
    danger_hits = []
    for py in SKILLS.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if DANGER.search(line) and not line.lstrip().startswith("#"):
                danger_hits.append(f"{py.relative_to(ROOT)}:{i}: {line.strip()[:60]}")

    # Секрет-скан: реальні значення ключів/токенів у БУДЬ-ЯКОМУ текстовому файлі екосистеми.
    # Файли без розширення (.env, .env.local, dotenv-подібні) сканувати ОБОВ'ЯЗКОВО —
    # саме вони найчастіший контейнер секретів.
    secret_hits = []
    for f in ROOT.rglob("*"):
        scannable = f.suffix in SECRET_SCAN_EXT or f.suffix == "" or f.name.startswith(".env")
        if f.is_file() and scannable and ".git" not in f.parts:
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if SECRET_VALUES.search(line):
                    secret_hits.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:60]}")

    print(f"verify: {len(dirs)} скілів · {total_evals} eval-кейсів")
    ok = True
    if problems:
        ok = False; print(f"\n❌ MANIFEST/цілісність — {len(problems)}:")
        for p in problems: print(f"  ✗ {p}")
    else:
        print("✅ MANIFEST цілісний (хеші, версії, лічильники збігаються)")
    if claim_problems:
        ok = False; print(f"\n❌ доказовість тверджень (Core Rule 14) — {len(claim_problems)}:")
        for c in claim_problems: print(f"  ✗ {c}")
    else:
        print("✅ усі фактичні твердження несуть тег доказовості "
              "([E] — з доказом, який існує на диску)")
    if self_check_problems:
        ok = False; print(f"\n❌ самоперевірний протокол (Core Rule 15) — {len(self_check_problems)}:")
        for s in self_check_problems: print(f"  ✗ {s}")
    else:
        print("✅ самоперевірний протокол: версії синхронні, крос-посилання ведуть "
              "куди обіцяють, лічильники збігаються, текст без омоглифів")
    if guard_fail:
        ok = False; print(f"\n❌ regression-guard — {len(guard_fail)} не пройшли:")
        for g in guard_fail: print(f"  ✗ {g}")
    else:
        print("✅ усі regression-guard проходять --validate")
    if danger_hits:
        ok = False; print(f"\n⚠️  підозрілі виклики у скриптах — {len(danger_hits)}:")
        for h in danger_hits: print(f"  ! {h}")
    else:
        print("✅ safety-scan скриптів чистий")
    if secret_hits:
        ok = False; print(f"\n🔑 РЕАЛЬНІ значення секретів у файлах — {len(secret_hits)}:")
        for h in secret_hits: print(f"  ! {h}")
    else:
        print("✅ секрет-скан чистий (нуль захардкоджених ключів/токенів)")
    return 0 if ok else 1


# ---------------------------------------------------------------- resync
def resync() -> int:
    dirs = skill_dirs()
    resnapped = []
    for name in dirs:
        if name in NO_MD5_BASELINE:
            continue
        cur = md5_text(SKILLS / name / "SKILL.md")
        base = baseline_md5(name)
        # baseline може бути повний md5 або перші 12 символів
        changed = base is None or not (cur == base or cur.startswith(base))
        if changed:
            code, first = run_guard(name, "snapshot")
            resnapped.append(f"{name}: {first}")

    # Перерахунок похідних полів MANIFEST (версія/дата білду — авторитетні, не чіпаємо)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    changed_manifest = False
    total = 0
    for name in dirs:
        d = SKILLS / name
        meta = man["skills"].setdefault(name, {"version": frontmatter_version(d / "SKILL.md"),
                                               "eval_cases": 0, "sha256_16": {}, "files": []})
        n = eval_count(d / "evals" / "evals.json"); total += n
        new = {
            "version": frontmatter_version(d / "SKILL.md"),
            "eval_cases": n,
            "sha_skill": sha16(d / "SKILL.md"),
            "sha_evals": sha16(d / "evals" / "evals.json"),
        }
        if meta.get("version") != new["version"]: meta["version"] = new["version"]; changed_manifest = True
        if meta.get("eval_cases") != n: meta["eval_cases"] = n; changed_manifest = True
        sha = meta.setdefault("sha256_16", {})
        if sha.get("SKILL.md") != new["sha_skill"]: sha["SKILL.md"] = new["sha_skill"]; changed_manifest = True
        if sha.get("evals/evals.json") != new["sha_evals"]: sha["evals/evals.json"] = new["sha_evals"]; changed_manifest = True
    if man.get("total_eval_cases") != total: man["total_eval_cases"] = total; changed_manifest = True
    if man.get("skill_count") != len(dirs): man["skill_count"] = len(dirs); changed_manifest = True
    # governance — похідне від фактичної версії melania (правило anti-stale)
    mel_v = man["skills"].get("melania-skill-master-administrator", {}).get("version")
    if mel_v:
        want_gov = f"melania-skill-master-administrator v{mel_v}"
        if man.get("governance") != want_gov:
            man["governance"] = want_gov; changed_manifest = True
    if changed_manifest:
        MANIFEST.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    # Лічильники у MELANIA-BOOTSTRAP.md (числа, не таблиця маршрутів)
    bootstrap_warn = []
    if BOOTSTRAP.exists():
        txt = BOOTSTRAP.read_text(encoding="utf-8")
        new_txt = re.sub(r"\d+ скіл(?:ів|и|)", f"{len(dirs)} скілів", txt)
        new_txt = re.sub(r"\d+ eval-кейс(?:ів|и|)", f"{total} eval-кейсів", new_txt)
        if new_txt != txt:
            BOOTSTRAP.write_text(new_txt, encoding="utf-8")
        for name in dirs:
            if name not in txt:
                bootstrap_warn.append(name)

    print("resync:")
    print(f"  пере-знято baseline: {len(resnapped)}")
    for r in resnapped: print(f"    · {r}")
    print(f"  MANIFEST оновлено: {'так' if changed_manifest else 'без змін'} (skills={len(dirs)}, evals={total})")
    if bootstrap_warn:
        print(f"  ⚠️  нема рядка в маршрутній таблиці MELANIA-BOOTSTRAP.md (додати вручну): {bootstrap_warn}")
    print("\n--- фінальний verify ---")
    return verify()


# ---------------------------------------------------------------- package
def package(target: str = "all") -> int:
    """Upload-safe .skill для скіл-стору: folder-at-root, без крапкових шляхів і без evals/.

    Урок (емпірично): завантажувач стору відхиляє шляхи, що починаються з крапки
    (`.snapshots/…` є в КОЖНОМУ скілі) — установка падає з помилкою про недопустимі
    символи. Пакувальник стору також вирізає `evals/`, тож source-істина тестів
    лишається тут, у репо/повному zip.
    """
    import zipfile
    dist = ROOT / "dist"; dist.mkdir(exist_ok=True)
    names = skill_dirs() if target == "all" else [target]
    made, skipped = [], []
    for name in names:
        d = SKILLS / name
        if not (d / "SKILL.md").exists():
            skipped.append(f"{name}: немає SKILL.md"); continue
        out = dist / f"{name}.skill"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(d.rglob("*")):
                if not f.is_file():
                    continue
                rel = f.relative_to(d)
                # відкидаємо крапкові сегменти (.snapshots, .DS_Store…) і evals/
                if any(part.startswith(".") for part in rel.parts) or rel.parts[0] == "evals":
                    continue
                z.write(f, f"{name}/{rel.as_posix()}")
            bad = [n for n in z.namelist() if any(p.startswith(".") for p in n.split("/"))]
        if bad:
            skipped.append(f"{name}: лишились крапкові шляхи {bad[:2]}"); out.unlink(missing_ok=True)
        else:
            made.append(f"{name}.skill")
    print(f"package: зібрано {len(made)} → {dist.relative_to(ROOT.parent)}/")
    for m in made: print(f"  · {m}")
    for s in skipped: print(f"  ✗ {s}")
    print("  (evals/ навмисно виключені — source-істина в репо; крапкових шляхів: 0)")
    return 1 if skipped else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "package":
        sys.exit(package(sys.argv[2] if len(sys.argv) > 2 else "all"))
    if cmd == "verify":
        sys.exit(verify())
    elif cmd == "resync":
        sys.exit(resync())
    else:
        print(__doc__); sys.exit(2)
