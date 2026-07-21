#!/usr/bin/env python3
"""audit_scan.py — Stage 1+2 сканер екосистеми скілів.
Використання: python3 audit_scan.py [SKILLS_DIR]
(типово: /mnt/skills/user у claude.ai; інакше — тека skills/ цієї екосистеми)
Read-only. Друкує: frontmatter-матрицю, вісь українською-перша (P9),
карту координації та orphan-перевірку. Жодних змін на диску."""
import os, re, sys

_LAB_SKILLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
ROOT = sys.argv[1] if len(sys.argv) > 1 else (
    "/mnt/skills/user" if os.path.isdir("/mnt/skills/user") else _LAB_SKILLS)

def cyr(s): return len(re.findall(r"[\u0400-\u04FF]", s or ""))

def main():
    if not os.path.isdir(ROOT):
        print(f"❌ Немає каталогу: {ROOT}"); sys.exit(1)
    names = sorted(d for d in os.listdir(ROOT)
                   if os.path.isfile(os.path.join(ROOT, d, "SKILL.md")))
    rows = []
    for name in names:
        d = os.path.join(ROOT, name)
        txt = open(os.path.join(d, "SKILL.md"), encoding="utf-8", errors="replace").read()
        parts = txt.split("---")
        fm = parts[1] if len(parts) >= 3 else ""
        body = txt[len(fm) + 6:] if fm else txt
        def f(k):
            m = re.search(rf"^\s*{k}\s*:\s*(.+)$", fm, re.M)
            return m.group(1).strip() if m else None
        dm = re.search(r"description:\s*(.*?)(?:\n[a-zA-Z_]+:|\Z)", fm, re.S)
        desc = dm.group(1) if dm else ""
        low = (body + desc).lower()
        ua = any(t in low for t in ["українськ", "ukrainian", "мова відповід",
                                    "respond in ukrainian", "output language",
                                    "відповідай україн", "українською-перш", "українською за"])
        refs = sorted({k for k in names if k != name and re.search(rf"\b{re.escape(k)}\b", body)})
        rows.append(dict(name=name, ver=f("version"), cat=f("category"),
            meta="metadata:" in fm, lic="license:" in fm,
            compat="compatibility:" in fm, tools="allowed-tools:" in fm,
            ref=os.path.isdir(os.path.join(d, "references")),
            evl=os.path.isdir(os.path.join(d, "evals")),
            scr=os.path.isdir(os.path.join(d, "scripts")),
            dcyr=cyr(desc), bcyr=cyr(body), ua=ua, refs=refs))

    print("=" * 100)
    print(f"STAGE 1 — FRONTMATTER / STRUCTURE  ({ROOT}, {len(rows)} скілів)")
    print("=" * 100)
    print(f"{'skill':36}{'ver':9}{'category':17}{'mta':4}{'lic':4}{'cmp':4}{'tul':4}{'ref':4}{'evl':4}{'scr':4}")
    for r in rows:
        y = lambda b: "Y" if b else "·"
        print(f"{r['name']:36}{str(r['ver'] or '—'):9}{str(r['cat'] or '—'):17}"
              f"{y(r['meta']):4}{y(r['lic']):4}{y(r['compat']):4}{y(r['tools']):4}"
              f"{y(r['ref']):4}{y(r['evl']):4}{y(r['scr']):4}")

    print("\n" + "=" * 100)
    print("STAGE 2a — UKRAINIAN-FIRST (P9)   desc_cyr | body_cyr | output-directive")
    print("=" * 100)
    for r in rows:
        print(f"{r['name']:36}{r['dcyr']:<9}{r['bcyr']:<9}{'YES' if r['ua'] else 'NO  ← gap'}")

    print("\n" + "=" * 100)
    print("STAGE 2b/2c — COORDINATION + ORPHANS")
    print("=" * 100)
    incoming = {n: [] for n in names}
    for r in rows:
        for t in r["refs"]:
            incoming[t].append(r["name"])
    for r in rows:
        print(f"• {r['name']:34} → {', '.join(r['refs']) if r['refs'] else '— none'}")
    print("-" * 100)
    for n in names:
        c = len(incoming[n])
        print(f"{n:36} ← referenced by {c}{'   🔸 ORPHAN' if c == 0 else ''}")

if __name__ == "__main__":
    main()
