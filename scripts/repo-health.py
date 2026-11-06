#!/usr/bin/env python3
"""repo-health.py — детермінований скан стану git-репозиторіїв + пропозиції виправлень.

НАВІЩО. Власник веде понад десяток репозиторіїв; частина без CI, частина — копії
лабораторії. Регулярний огляд «що зламано й що виправити» не має залежати від
уважності сесії: однакові перевірки щоразу, стабільні ідентифікатори знахідок,
звіт лише дельтою до попереднього прогону. Глибокий аналіз і живий стан GitHub
(CI, PR) — справа запланованого завдання (automations/repo-monitor/), не цього скрипта.

ЄДИНА ВІДПОВІДАЛЬНІСТЬ. Прочитати ЛОКАЛЬНІ клони (git ls-files + вміст файлів) і
надрукувати знахідки з пропозицією виправлення. Нічого не змінює, не ходить у мережу,
НЕ виконує код репозиторіїв. Вміст чужих репо — дані: шляхи друкуються без керівних
символів, знайдені секрети — замасковано.

ПРАВИЛА (rule → severity):
  RH01 немає CI (.github/workflows)                          medium
  RH02 дія GitHub не закріплена повним SHA                   medium
  RH03 у git відстежується .env                              high
  RH04 схоже на секрет у відстежуваному файлі               high | medium (Google API key) | info (фікстури/тести)
  RH05 .gitignore відсутній або не покриває .env/.env.*/залежності  low | medium (.env, .env.*)
  RH06 у git лежать артефакти збірки/кеші                    medium
  RH07 кілька lock-файлів одного менеджера пакетів           low
  RH08 немає README / LICENSE                                low
  RH09 є маніфест залежностей, немає Dependabot              low
  RH10 великий файл (> 5 МБ) у git                           low
  RH11 package.json без lint/test — нема чим перевіряти      info
  RH12 копія канону розійшлася з каноном (MANIFEST) або      medium
       втратила посилання / свідомо збережені артефакти
  RH13 порожній репозиторій (нема що моніторити)             info
  RH14 копія шаблону CI ai-lab застаріла (рядок sync)         low

РЕЖИМИ.
  repo-health.py PATH [PATH ...]      скан переданих репозиторіїв
  repo-health.py --root DIR           скан усіх git-репо першого рівня в DIR
  --json FILE                         записати знахідки JSON (база для наступної дельти) + HEAD кожного репо
  --compact                           JSON лише з полями для дельти (id/repo/rule/severity/title),
                                      без відступів — щоб базу можна було нести в тексті звіту
  --baseline FILE                     показати лише 🆕 нові та ✅ зниклі відносно бази
  --canon DIR                         канонічний ai-lab для RH12 (типово — цей репозиторій)
  --waivers FILE                      JSON {"<id>": "причина · дата"} — свідомо прийняті знахідки
                                      (рішення власника) не друкуються, лише лічильник
  --strict                            код 1, якщо є high (для CI)
Код виходу: 0 — скан виконано; 1 — --strict і є high; 2 — помилка аргументів.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
SEV_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡", "info": "⚪"}
LARGE_BYTES = 5 * 1024 * 1024
SCAN_MAX_BYTES = LARGE_BYTES  # більші файли — RH10 називає неперевірену частину

SECRET_PATTERNS = [
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b"), "high"),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"), "high"),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "high"),
    ("OpenAI key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}"), "high"),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "high"),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "high"),
    ("Private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"), "high"),
    # Ключі Google/Firebase web часто публічні за задумом, але мусять мати обмеження.
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "medium"),
]
ENV_OK_SUFFIXES = (".example", ".sample", ".template", ".dist", ".defaults")
BUILD_DIRS = ("node_modules/", ".gradle/", "build/", "dist/", ".next/", "__pycache__/", ".venv/")
LOCKS_NODE = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb")
MANIFESTS = ("package.json", "build.gradle", "build.gradle.kts", "requirements.txt",
             "pyproject.toml", "go.mod", "Cargo.toml", "pom.xml")
SYNC_RE = re.compile(r"#\s*sync:\s*ai-lab templates/ci/repo-check\.yml v(\d+)")
USES_RE = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^\s'\"#]+)", re.M)
CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def clean(text: str, limit: int = 160) -> str:
    """Шлях/рядок із чужого репо → безпечний для друку (без керівних символів, обрізаний)."""
    text = CTRL_RE.sub("?", str(text))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def mask(secret: str) -> str:
    return secret[:4] + "…" + f"({len(secret)} симв.)"


def git(repo: Path, *args: str) -> str:
    res = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


def git_ignored(repo: Path, path: str) -> bool:
    """Чи ігнорує шлях саме .gitignore РЕПОЗИТОРІЮ. Глобальний `core.excludesFile` і `.git/info/exclude`
    є лише в цьому клоні — іншим клонам і контриб'юторам вони захисту не дають, тож не рахуються."""
    res = subprocess.run(["git", "-c", "core.excludesFile=/dev/null", "-C", str(repo), "check-ignore", "-v",
                          "--no-index", path], capture_output=True, text=True)
    source = res.stdout.split(":", 1)[0]
    return res.returncode == 0 and source != ".git/info/exclude"


def is_test_path(path: str) -> bool:
    parts = path.lower().split("/")
    return any(p in ("tests", "test", "fixtures", "__tests__", "testdata") for p in parts[:-1])


class Scan:
    def __init__(self, repo: Path, canon: Path | None):
        self.repo = repo
        self.name = repo.name
        self.canon = canon
        self.findings: list[dict] = []
        self.files = [f for f in git(repo, "ls-files", "-z").split("\0") if f]
        self.fileset = set(self.files)

    def add(self, rule: str, sev: str, title: str, proposal: str, path: str = "") -> None:
        fid = hashlib.sha1(f"{rule}|{self.name}|{path}|{title}".encode()).hexdigest()[:10]
        self.findings.append({"id": fid, "repo": self.name, "rule": rule, "severity": sev,
                              "path": clean(path), "title": clean(title, 220),
                              "proposal": clean(proposal, 400)})

    def has(self, name: str) -> bool:
        return name in self.fileset

    def run(self) -> list[dict]:
        code_files = [f for f in self.files if not re.match(r"(?i)^(license|readme)(\.\w+)?$", f)]
        if len(code_files) == 0:
            self.add("RH13", "info", "порожній репозиторій (лише README/LICENSE)",
                     "нічого моніторити; заповнити або архівувати, щоб не плодив шуму")
            self.rule_readme_license()
            return self.findings
        self.rule_ci()
        self.rule_env_and_secrets()
        self.rule_gitignore()
        self.rule_build_artifacts()
        self.rule_locks()
        self.rule_readme_license()
        self.rule_dependabot()
        self.rule_large()
        self.rule_scripts()
        self.rule_canon_copy()
        return self.findings

    # --- правила -------------------------------------------------------------
    def rule_ci(self) -> None:
        wfs = [f for f in self.files if re.match(r"^\.github/workflows/[^/]+\.ya?ml$", f)]
        if not wfs:
            self.add("RH01", "medium", "немає CI: зміни ніхто не перевіряє при заливанні",
                     "додати workflow перевірки на push/PR — шаблон ai-lab "
                     "templates/ci/repo-check.yml (секрети + лінт/збірка/тести стеку)")
            return
        for wf in wfs:
            text = self.read(wf) or ""
            for ref in USES_RE.findall(text):
                if ref.startswith(("./", "docker://")) or "@" not in ref:
                    continue
                action, _, pin = ref.rpartition("@")
                if not re.fullmatch(r"[0-9a-f]{40}", pin):
                    self.add("RH02", "medium", f"дія {action}@{pin} закріплена тегом, не SHA",
                             "замінити на повний SHA коміта з коментарем-версією "
                             "(тег можна перепризначити — CVE-2025-30066)", wf)
            self.template_sync(wf, text)

    def template_sync(self, wf: str, text: str) -> None:
        """Копія шаблону CI ai-lab несе рядок `# sync: ai-lab templates/ci/repo-check.yml vN`.
        Шаблон оновили, а копію ні — копія перевіряє менше, ніж обіцяє монітор."""
        m = SYNC_RE.search(text)
        if not m or self.canon is None or self.repo.resolve() == self.canon.resolve():
            return
        try:
            canon_m = SYNC_RE.search((self.canon / "templates/ci/repo-check.yml").read_text(encoding="utf-8"))
        except OSError:
            return
        if canon_m and int(m.group(1)) < int(canon_m.group(1)):
            self.add("RH14", "low", f"копія шаблону CI застаріла (v{m.group(1)} < v{canon_m.group(1)})",
                     "оновити з ai-lab templates/ci/repo-check.yml (правити шаблон, копії — з нього)", wf)

    def rule_env_and_secrets(self) -> None:
        for f in self.files:
            base = f.rsplit("/", 1)[-1]
            if (base == ".env" or base.startswith(".env.")) and not base.endswith(ENV_OK_SUFFIXES):
                self.add("RH03", "high", f"файл {base} відстежується git",
                         "git rm --cached; ротувати всі ключі з нього (історія git їх зберігає); "
                         "додати .env* у .gitignore, лишити лише .env.example", f)
        for f in self.files:
            text = self.read(f, SCAN_MAX_BYTES)
            if not text:
                continue
            seen: set[str] = set()
            for label, rx, sev in SECRET_PATTERNS:
                for m in rx.finditer(text):
                    if m.group(0) in seen:
                        continue
                    seen.add(m.group(0))
                    line = text.count("\n", 0, m.start()) + 1
                    if is_test_path(f):
                        s, prop = "info", "схоже на тестову фікстуру — переконатися, що ключ фейковий"
                    elif label == "Google API key":
                        s, prop = sev, ("ключі Google/Firebase web публічні за задумом, але мусять мати "
                                        "обмеження (HTTP referrer/API) у Google Cloud Console; "
                                        "інакше — ротувати й винести в env")
                    else:
                        s, prop = sev, ("ротувати ключ НЕГАЙНО, прибрати з коду в env/секрети CI; "
                                        "очищення історії — лише за згодою власника")
                    self.add("RH04", s, f"{label} {mask(m.group(0))} (рядок {line})", prop, f)

    def rule_gitignore(self) -> None:
        if not self.has(".gitignore"):
            self.add("RH05", "low", "немає .gitignore",
                     "додати .gitignore під стек (.env*, залежності, артефакти збірки)")
        if not git_ignored(self.repo, ".env"):
            self.add("RH05", "medium", ".env не ігнорується — ключі легко закомітити випадково",
                     "додати рядки `.env` і `.env.*` та `!.env.example` у .gitignore")
        elif not git_ignored(self.repo, ".env.local"):  # лише `.env` у .gitignore — `.env.local` тощо відкриті
            self.add("RH05", "medium", ".env.* (напр. .env.local) не ігнорується — ключі легко закомітити випадково",
                     "додати рядок `.env.*` та `!.env.example` у .gitignore")
        if self.has("package.json") and not git_ignored(self.repo, "node_modules/x"):
            self.add("RH05", "low", "node_modules не ігнорується", "додати `node_modules/` у .gitignore")
        if any(f.startswith(("build.gradle", "settings.gradle")) for f in self.files) \
                and not git_ignored(self.repo, ".gradle/x"):
            self.add("RH05", "low", ".gradle/ не ігнорується",
                     "додати `.gradle/`, `build/`, `local.properties` у .gitignore")

    def rule_build_artifacts(self) -> None:
        # Свідомий виняток власника в кореневому .gitignore: `!тека/` звільняє всю теку (напр.
        # dist/ мобільного агента — це сам продукт), `!шлях/файл` — лише цей файл, не теку.
        negs = [ln[1:].strip() for ln in (self.read(".gitignore") or "").splitlines() if ln.startswith("!")]
        allowed_dirs = [n.strip("/") + "/" for n in negs if n.endswith("/")]
        allowed_files = {n.lstrip("/") for n in negs if not n.endswith("/")}
        counts: dict[str, int] = {}
        for f in self.files:
            if f in allowed_files or any(f.startswith(d) for d in allowed_dirs):
                continue
            for d in BUILD_DIRS:
                if f.startswith(d) or f"/{d}" in f:
                    top = f[: f.index(d) + len(d)]
                    counts[top] = counts.get(top, 0) + 1
                    break
        for top, n in sorted(counts.items()):
            self.add("RH06", "medium", f"у git лежить {n} файл(ів) артефактів/кешу в {top}",
                     f"git rm -r --cached {top} + рядок у .gitignore; кеші роздувають репо "
                     "й дають шумні коміти", top)

    def rule_locks(self) -> None:
        locks = [f for f in LOCKS_NODE if self.has(f)]
        if len(locks) > 1:
            self.add("RH07", "low", f"кілька lock-файлів: {', '.join(locks)}",
                     "обрати один менеджер пакетів і лишити один lock — інакше версії розходяться")

    def rule_readme_license(self) -> None:
        names = {f.lower() for f in self.files if "/" not in f}
        if not any(n.startswith("readme") for n in names):
            self.add("RH08", "low", "немає README", "додати README (UA/EN): що це, як запустити")
        if not any(n.startswith(("license", "licence")) for n in names):
            self.add("RH08", "low", "немає LICENSE", "додати LICENSE (у лабораторії — MIT, рішення 2026-09-28)")

    def rule_dependabot(self) -> None:
        manifests = [m for m in MANIFESTS if self.has(m)]
        if manifests and not (self.has(".github/dependabot.yml") or self.has(".github/dependabot.yaml")):
            self.add("RH09", "low", f"є {manifests[0]}, але немає Dependabot",
                     "додати .github/dependabot.yml (оновлення залежностей і дій GitHub щотижня)")

    def rule_large(self) -> None:
        for f in self.files:
            p = self.repo / f
            try:
                size = p.stat().st_size if p.is_file() else 0
            except OSError:
                continue
            if size > LARGE_BYTES:
                self.add("RH10", "low", f"великий файл {size // (1024 * 1024)} МБ",
                         "винести в Releases/Git LFS або прибрати з git; секрети (RH04) в ньому "
                         f"перевірено лише в перших {LARGE_BYTES // (1024 * 1024)} МБ", f)

    def rule_scripts(self) -> None:
        if not self.has("package.json"):
            return
        try:
            scripts = json.loads(self.read("package.json") or "{}").get("scripts") or {}
        except (json.JSONDecodeError, AttributeError):
            self.add("RH11", "info", "package.json не розбирається як JSON", "виправити синтаксис", "package.json")
            return
        if not any(k in scripts for k in ("lint", "test", "typecheck")):
            self.add("RH11", "info", "package.json без lint/test — CI нема чим перевіряти, крім збірки",
                     "додати хоча б `lint` (eslint) або `typecheck` (tsc --noEmit)", "package.json")

    def rule_canon_copy(self) -> None:
        rel = "melania-skills-ecosystem/MANIFEST.json"
        if not self.has(rel) or self.canon is None:
            return
        canon_manifest = self.canon / rel
        if self.repo.resolve() == self.canon.resolve() or not canon_manifest.is_file():
            return
        def fingerprint(text: str):  # валідний JSON, але не об'єкт ([] чи null) — не падіння всього скану
            d = json.loads(text)
            return d.get("built_fingerprint") if isinstance(d, dict) else None
        try:
            mine = fingerprint(self.read(rel) or "{}")
            theirs = fingerprint(canon_manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if mine != theirs:
            self.add("RH12", "medium", f"копія melania-екосистеми розійшлася з каноном "
                     f"(fingerprint {clean(mine, 20)} ≠ {clean(theirs, 20)})",
                     "синхронізувати з ai-lab main або позначити копію штампом синхронізації/строком "
                     "життя (правило «Цеглина»)", rel)
        self.canon_copy_rules()
        self.canon_copy_losses()

    def canon_copy_rules(self) -> None:
        """Копія `CLAUDE.md` лабораторії, що відстала від канону, тихо вимикає новіші правила для
        сесій цього репо, а відбиток MANIFEST цього не бачить (W-40, 2026-11-05: Sophie-TMS без §12 і
        W-39). Штамп синхронізації (`> **Копія канону** …` і його рядки-продовження) не рахується."""
        mine, canon = self.read("CLAUDE.md"), self.canon / "CLAUDE.md"
        try:
            theirs = canon.read_text(encoding="utf-8")
        except OSError:
            return
        if mine is None or mine.splitlines()[:1] != theirs.splitlines()[:1]:
            return  # власний CLAUDE.md репо, не копія лабораторії
        def body(text: str) -> tuple[list[str], bool]:
            out, stamped, in_stamp = [], False, False
            for ln in text.splitlines():
                if ln.startswith("> **Копія канону**"):
                    stamped = in_stamp = True
                    continue
                if in_stamp and ln.startswith(">"):
                    continue
                in_stamp = False
                out.append(ln.rstrip())
            while len(out) > 1 and out[1] == "" and out[2:3] == [""]:
                out.pop(1)  # порожній рядок, що лишився на місці штампа
            return out, stamped
        (m, stamped), (t, _) = body(mine), body(theirs)
        if m != t:
            diff = sum(1 for _ in difflib.unified_diff(t, m, n=0) if _[:1] in "+-" and _[:3] not in ("+++", "---"))
            self.add("RH12", "medium", f"копія CLAUDE.md розійшлася з каноном ({diff} рядк. відрізняються)"
                     + ("" if stamped else ", штампа синхронізації нема"),
                     "синхронізувати з ai-lab main і оновити штамп `> **Копія канону** … @ <коміт>` "
                     "(правило «Цеглина»): відстала копія вимикає новіші правила для сесій цього репо",
                     "CLAUDE.md")
        elif not stamped:
            self.add("RH12", "info", "копія CLAUDE.md збігається з каноном, але без штампа синхронізації",
                     "додати під заголовком `> **Копія канону** `patriotai/ai-lab/CLAUDE.md` @ <коміт> …`",
                     "CLAUDE.md")

    def canon_copy_losses(self) -> None:
        """Копіювання (архів, вивантаження з іншого сервісу) губить символьні посилання і свідомо
        збережені артефакти збірки (`!шлях/` у .gitignore), а відбиток MANIFEST при цьому збігається.
        Інцидент 2026-11-02: Sophie-TMS — червоний CI, бо бракувало plugins/*/skills і dist/.
        Рахуємо лише втрати там, де батьківська тека копії існує, — розвиток копії шумом не стає."""
        canon_files = git(self.canon, "ls-files", "-s", "-z").split("\0")
        links = [ln.split("\t", 1)[1] for ln in canon_files if ln.startswith("120000 ") and "\t" in ln]
        dirs = {"/".join(f.split("/")[:i]) for f in self.files for i in range(1, f.count("/") + 1)}
        lost_links = [p for p in links if p.rsplit("/", 1)[0].rsplit("/", 1)[0] in dirs and p not in self.fileset]
        if lost_links:
            self.add("RH12", "medium", f"копія ai-lab втратила {len(lost_links)} символьних посилань "
                     f"(напр. {clean(lost_links[0], 80)})",
                     "відновити з ai-lab (копіювання архівом/вивантаженням губить посилання) або прибрати "
                     "копію лабораторії з репо; без них падають тести, що їх перевіряють",
                     lost_links[0].split("/", 1)[0] + "/")
        canon_gi = (self.canon / ".gitignore")
        try:
            negs = [ln[1:].strip().strip("/") + "/" for ln in canon_gi.read_text(encoding="utf-8").splitlines()
                    if ln.startswith("!") and ln.strip().endswith("/")]
        except OSError:
            negs = []
        canon_tracked = [f for f in (ln.split("\t", 1)[-1] for ln in canon_files) if f]
        for neg in negs:
            kept = [f for f in canon_tracked if f.startswith(neg)]
            parent = neg.rstrip("/").rsplit("/", 1)[0]
            if not kept or parent not in dirs:
                continue
            missing = [f for f in kept if f not in self.fileset]
            fix = ("відновити з ai-lab (у каноні вони під винятком `!` у .gitignore — це продукт, не "
                   "сміття) або прибрати копію лабораторії з репо")
            if len(missing) == len(kept):
                self.add("RH12", "medium", f"копія ai-lab без свідомо збережених артефактів {clean(neg, 60)} "
                         f"({len(kept)} файл(ів) у каноні)", fix, neg)
            elif missing:  # часткова втрата (напр. лишився .html, зник sw.js — офлайн-кеш зламано)
                self.add("RH12", "medium", f"копія ai-lab втратила частину свідомо збережених артефактів "
                         f"{clean(neg, 60)}: {len(missing)} з {len(kept)} (напр. {clean(missing[0], 80)})",
                         fix, neg)

    # --- допоміжне -----------------------------------------------------------
    def read(self, rel: str, limit: int | None = None) -> str | None:
        p = self.repo / rel
        try:
            if not p.is_file() or p.is_symlink():
                return None
            data = p.read_bytes() if limit is None else p.open("rb").read(limit)
        except OSError:
            return None
        if b"\0" in data[:4096]:
            return None
        return data.decode("utf-8", errors="replace")


def render(findings: list[dict], repos: list[str], baseline: list[dict] | None) -> str:
    out = []
    if baseline is not None:
        old = {f["id"]: f for f in baseline}
        new = {f["id"]: f for f in findings}
        added = [f for i, f in new.items() if i not in old]
        gone = [f for i, f in old.items() if i not in new]
        kept = len(new) - len(added)
        out.append(f"## Дельта стану репозиторіїв ({len(repos)} репо)\n")
        if not added and not gone:
            out.append(f"Без змін: {kept} відомих знахідок, нових немає.\n")
            return "\n".join(out)
        out.append(f"🆕 нових: **{len(added)}** · ✅ зникло: **{len(gone)}** · без змін: {kept}\n")
        for f in sorted(added, key=lambda x: (SEV_ORDER[x["severity"]], x["repo"])):
            out.append(line(f, "🆕"))
        for f in sorted(gone, key=lambda x: x["repo"]):
            out.append(f"- ✅ `{f['repo']}` {f['rule']} — {f['title']}")
        return "\n".join(out) + "\n"
    by_sev: dict[str, int] = {}
    for f in findings:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    summary = " · ".join(f"{SEV_ICON[s]} {s}: {by_sev[s]}" for s in SEV_ORDER if s in by_sev) or "знахідок немає"
    out.append(f"## Стан репозиторіїв ({len(repos)} репо)\n\n{summary}\n")
    for repo in repos:
        items = sorted((f for f in findings if f["repo"] == repo), key=lambda x: (SEV_ORDER[x["severity"]], x["rule"]))
        if not items:
            out.append(f"### {repo}\n- ✅ знахідок немає\n")
            continue
        out.append(f"### {repo}")
        out.extend(line(f) for f in items)
        out.append("")
    return "\n".join(out)


def line(f: dict, prefix: str = "") -> str:
    where = f" `{f['path']}`" if f["path"] else ""
    lead = f"{prefix} " if prefix else ""
    repo = f"`{f['repo']}` " if prefix else ""
    return (f"- {lead}{SEV_ICON[f['severity']]} {repo}**{f['rule']}** {f['title']}{where}\n"
            f"  → {f['proposal']}  `[{f['id']}]`")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--root")
    ap.add_argument("--json")
    ap.add_argument("--baseline")
    ap.add_argument("--canon", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--waivers")
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()

    repos = [Path(p) for p in a.paths]
    if a.root:
        root = Path(a.root)
        if not root.is_dir():
            print(f"помилка: --root {clean(a.root)} не тека", file=sys.stderr)
            return 2
        repos += sorted(d for d in root.iterdir() if (d / ".git").exists())
    if not repos:
        print("помилка: передай шляхи репозиторіїв або --root DIR", file=sys.stderr)
        return 2
    bad = [str(r) for r in repos if not (r / ".git").exists()]
    if bad:
        print(f"помилка: не git-репозиторій: {clean(', '.join(bad))}", file=sys.stderr)
        return 2

    canon = Path(a.canon) if a.canon and Path(a.canon).is_dir() else None
    findings: list[dict] = []
    heads: dict[str, dict] = {}
    for r in repos:
        findings.extend(Scan(r, canon).run())
        sha, _, date = git(r, "log", "-1", "--format=%h %cI").strip().partition(" ")
        heads[r.name] = {"sha": clean(sha, 12), "date": clean(date, 40)}

    waived, waived_ids = 0, []
    if a.waivers:
        try:
            waivers = json.loads(Path(a.waivers).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"помилка: waivers не прочитано ({clean(e)})", file=sys.stderr)
            return 2
        kept = [f for f in findings if f["id"] not in waivers]
        waived = len(findings) - len(kept)
        waived_ids = sorted({f["id"] for f in findings if f["id"] in waivers})  # сторінці: «прийнято», не «виправлено»
        findings = kept

    baseline = None
    if a.baseline:
        try:
            baseline = json.loads(Path(a.baseline).read_text(encoding="utf-8")).get("findings", [])
        except (OSError, json.JSONDecodeError) as e:
            print(f"увага: базу не прочитано ({clean(e)}) — показую повний звіт", file=sys.stderr)
    if a.json:
        keep = ("id", "repo", "rule", "severity", "title")
        rows = [{k: f[k] for k in keep} for f in findings] if a.compact else findings
        Path(a.json).write_text(json.dumps({"repos": [r.name for r in repos], "heads": heads, "waived": waived,
                                           "waived_ids": waived_ids, "findings": rows},
                                           ensure_ascii=False, indent=None if a.compact else 1),
                                encoding="utf-8")
    print(render(findings, [r.name for r in repos], baseline))
    if waived:
        print(f"_Свідомо прийнято власником (waivers): {waived} — не показано._")
    return 1 if a.strict and any(f["severity"] == "high" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
