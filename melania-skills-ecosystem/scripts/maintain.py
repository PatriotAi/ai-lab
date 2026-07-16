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

Запускати з будь-якої теки: шляхи визначаються відносно розташування скрипта.
"""
import json, hashlib, re, sys, subprocess, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # melania-skills-ecosystem/
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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "verify":
        sys.exit(verify())
    elif cmd == "resync":
        sys.exit(resync())
    else:
        print(__doc__); sys.exit(2)
