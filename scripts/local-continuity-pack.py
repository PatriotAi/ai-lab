#!/usr/bin/env python3
"""Пакет локальної безперервності: повна копія робочих репозиторіїв + інструкція відновлення.

Навіщо: якщо зв'язок між пристроєм власника і хмарним середовищем (сесія, контейнер, GitHub)
обірветься, на пристрої вже лежить усе, щоб продовжити роботу: вся історія git кожного репо,
стан незбережених змін і текст для старту нової сесії. Канон правила —
`continuation-memory` § «Локальна безперервність».

  local-continuity-pack.py make   OUT_DIR REPO_DIR [REPO_DIR ...]   # зібрати пакет
  local-continuity-pack.py verify PACK.tar.gz                       # перевірити, що відновлюється

`make` для кожного репо: `git bundle --all` (уся історія й гілки) + патч незакомічених змін;
пише MANIFEST.json (голови гілок, SHA-256 файлів) і RESUME.md, пакує в один .tar.gz.
`verify` розпаковує в тимчасову теку, звіряє SHA-256, клонує кожен bundle і порівнює голову
з маніфестом. Лише stdlib + git, без мережі. Код 1 — пакет не відновлюється.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def git(repo: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} у {repo.name}: {r.stderr.strip()[:200]}")
    return r.stdout


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


RESUME = """# Як продовжити роботу з цього пакета

Зібрано: {when} (UTC). Репозиторіїв: {n}.

## 1. Що в пакеті
- `<назва>.bundle` — уся історія git репозиторію з усіма гілками (повна копія, не знімок).
- `<назва>.uncommitted.patch` — зміни, які на момент збирання ще не були збережені в git (якщо є).
- `<назва>.untracked.tar.gz` — нові файли, ще не додані в git (якщо є).
- `MANIFEST.json` — голова кожної гілки й контрольні суми файлів.

## 2. Відновити репозиторій (комп'ютер або телефон з Termux)
```
git clone <назва>.bundle <назва>
cd <назва>
git apply ../<назва>.uncommitted.patch   # лише якщо такий файл є
tar -xzf ../<назва>.untracked.tar.gz     # лише якщо такий файл є
```
Коли зв'язок повернеться: `git remote set-url origin https://github.com/PatriotAi/<назва>`
і `git push` робочої гілки — нічого не втрачено.

## 3. Продовжити роботу — від найкращого варіанта до запасного
1. **Інша поверхня Claude з тим самим класом моделі** (застосунок claude.ai, Claude Code на
   комп'ютері): якість не падає. Почніть нову розмову з тексту з розділу 4.
2. **Claude Code локально** на комп'ютері з відновленими репозиторіями: правила
   лабораторії (`ai-lab/CLAUDE.md`), навички й перевірки працюють так само.
3. **Без інтернету — локальна модель** (Ollama на комп'ютері, WebLLM у браузері): робота
   продовжується, але модель слабша; результати перевіряйте тестами репозиторію й
   позначайте як зроблені в запасному режимі.

## 4. Текст для старту нової сесії
```
Продовжуємо роботу лабораторії ai-lab після обриву зв'язку. Стан — пакет локальної
безперервності від {when}; голови гілок — у MANIFEST.json. Правила — ai-lab/CLAUDE.md
і docs/portable-standard.md. Спершу звір стан репозиторіїв із MANIFEST.json, далі
продовжуй відкриті пункти з ai-lab/docs/WINDOWS.md і останнього запису docs/learnings.md.
```
"""


def make(out: Path, repos: list[Path]) -> int:
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    stamp = when.replace(" ", "_").replace(":", "")
    work = out / f"continuity-{stamp}"
    work.mkdir(parents=True, exist_ok=False)
    manifest: dict = {"created_utc": when, "repos": {}, "files": {}}
    for repo in repos:
        name = repo.resolve().name
        if git(repo, "rev-parse", "--is-shallow-repository").strip() == "true":
            print(f"✗ {name}: неглибокий клон — bundle не містив би всієї історії; `git fetch --unshallow`",
                  file=sys.stderr)
            return 1
        bundle = work / f"{name}.bundle"
        git(repo, "bundle", "create", str(bundle), "--all")
        heads = {}
        for line in git(repo, "for-each-ref", "--format=%(refname) %(objectname)",
                        "refs/heads", "refs/remotes").splitlines():
            ref, sha = line.split()
            if not ref.endswith("/HEAD"):
                heads[ref] = sha
        dirty = git(repo, "diff", "HEAD", "--binary")
        untracked = git(repo, "ls-files", "--others", "--exclude-standard").split("\n")
        untracked = [u for u in untracked if u]
        if dirty:
            (work / f"{name}.uncommitted.patch").write_text(dirty, encoding="utf-8")
        if untracked:  # нові файли, ще не додані в git, — інакше копія не повна
            with tarfile.open(work / f"{name}.untracked.tar.gz", "w:gz") as ut:
                for u in untracked:
                    ut.add(repo / u, arcname=u)
        manifest["repos"][name] = {"head": git(repo, "rev-parse", "HEAD").strip(),
                                   "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip(),
                                   "refs": heads, "uncommitted_patch": bool(dirty),
                                   "untracked_files": untracked}
    (work / "RESUME.md").write_text(RESUME.format(when=when, n=len(repos)), encoding="utf-8")
    for f in sorted(work.iterdir()):
        manifest["files"][f.name] = sha256(f)
    (work / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    tar = out / f"{work.name}.tar.gz"
    with tarfile.open(tar, "w:gz") as t:
        t.add(work, arcname=work.name)
    print(f"✅ пакет: {tar} ({tar.stat().st_size // 1024} КБ, репо: {len(repos)})")
    for name, r in manifest["repos"].items():
        extra = []
        if r["uncommitted_patch"]:
            extra.append("є незбережені зміни (патч)")
        if r["untracked_files"]:
            extra.append(f"нові файли поза git: {len(r['untracked_files'])} (в архіві)")
        print(f"  {name}: {r['branch']} @ {r['head'][:7]}" + (f" — {'; '.join(extra)}" if extra else ""))
    return 0


def verify(tar: Path) -> int:
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(tar) as t:
            for m in t.getmembers():  # без шляхів назовні теки й без посилань
                if m.name.startswith("/") or ".." in Path(m.name).parts or m.issym() or m.islnk():
                    print(f"✗ підозрілий шлях у пакеті: {m.name}", file=sys.stderr)
                    return 1
            t.extractall(tmp, filter="data")
        roots = [p for p in Path(tmp).iterdir() if p.is_dir()]
        if len(roots) != 1:
            print("✗ очікувалась одна тека в пакеті", file=sys.stderr)
            return 1
        root = roots[0]
        manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
        for fname, digest in manifest["files"].items():
            f = root / fname
            if not f.is_file():
                problems.append(f"{fname}: файла нема")
            elif sha256(f) != digest:
                problems.append(f"{fname}: контрольна сума не збігається (файл пошкоджено)")
        for name, r in manifest["repos"].items():
            dest = Path(tmp) / "restore" / name
            res = subprocess.run(["git", "clone", "-q", "--no-checkout", str(root / f"{name}.bundle"), str(dest)],
                                 capture_output=True, text=True)
            if res.returncode != 0:
                problems.append(f"{name}: bundle не клонується — {res.stderr.strip()[:120]}")
                continue
            missing = [ref for ref, sha in r["refs"].items()
                       if subprocess.run(["git", "-C", str(dest), "cat-file", "-e", sha + "^{commit}"],
                                         capture_output=True).returncode != 0]
            if missing:
                problems.append(f"{name}: у bundle бракує комітів {len(missing)} гілок (напр. {missing[0]})")
            if subprocess.run(["git", "-C", str(dest), "cat-file", "-e", r["head"] + "^{commit}"],
                              capture_output=True).returncode != 0:
                problems.append(f"{name}: робочої голови {r['head'][:7]} у bundle нема")
    for p in problems:
        print(f"✗ {p}")
    if not problems:
        print(f"✅ пакет відновлюється: {len(manifest['repos'])} репо, усі голови й гілки на місці")
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == "make":
        return make(Path(argv[1]), [Path(a) for a in argv[2:]])
    if len(argv) == 2 and argv[0] == "verify":
        return verify(Path(argv[1]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
