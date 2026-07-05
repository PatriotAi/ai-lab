#!/usr/bin/env python3
"""
skill_guard.py — Safety Update System for notebooklm-connector Skill

Prevents content/functionality loss during Skill rewrites by:
  1. SNAPSHOT  — extract feature fingerprint BEFORE any edit
  2. VALIDATE  — check fingerprint against current file AFTER edit
  3. DIFF      — show exactly what was added / removed / changed
  4. APPROVE   — block save unless validation passes (or override with --force)
  5. AUDIT LOG — append every update attempt to audit.jsonl

Usage:
  python skill_guard.py snapshot              # save fingerprint of current state
  python skill_guard.py validate              # check current vs last snapshot
  python skill_guard.py diff                  # show detailed diff report
  python skill_guard.py update <new_file>     # validate new version before replacing
  python skill_guard.py history               # show audit log
  python skill_guard.py baseline --create     # create/update the canonical baseline
  python skill_guard.py baseline --check      # check current vs canonical baseline

Root cause this prevents:
  - Dispatch table truncation (counts each tool entry)
  - Section condensation (enforces minimum lines per section)
  - Behavior Rules deletion (counts table rows)
  - Detail simplification (checks canonical terms)
  - Case inconsistency (case-insensitive + canonical form validation)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Paths ────────────────────────────────────────────────────────────────────

SKILL_DIR    = Path(__file__).parent.parent
SKILL_FILE   = SKILL_DIR / "SKILL.md"
SNAPSHOT_DIR = SKILL_DIR / "scripts" / ".snapshots"
AUDIT_LOG    = SKILL_DIR / "scripts" / "audit.jsonl"
BASELINE     = SKILL_DIR / "scripts" / "baseline.json"

SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Canonical Terms (case-insensitive search, stored as canonical form) ──────
# Any term here MUST appear in SKILL.md (case-insensitive).
# Add new terms when new features are developed.

CANONICAL_TERMS: dict[str, str] = {
    # Python MCP tools (19)
    "open_notebook":           "open_notebook",
    "get_all_content":         "get_all_content",
    "list_sources":            "list_sources",
    "get_source_content":      "get_source_content",
    "get_notes":               "get_notes",
    "generate_briefing":       "generate_briefing",
    "chat_query":              "chat_query",
    "add_source":              "add_source",
    "generate_audio":          "generate_audio",
    "generate_video":          "generate_video",
    "generate_quiz":           "generate_quiz",
    "generate_flashcards":     "generate_flashcards",
    "generate_mind_map":       "generate_mind_map",
    "generate_slide_deck":     "generate_slide_deck",
    "notebooklm_download":     "download",
    "list_notebooks":          "list_notebooks",
    "inject_cookies":          "inject_cookies",
    "session_status":          "session_status",
    "notebooklm_authenticate": "authenticate",

    # Browserbase tools (12, including raw browser control)
    "browserbase_authenticate": "browserbase_authenticate",
    "browserbase_navigate":     "browserbase_navigate",
    "browserbase_screenshot":   "browserbase_screenshot",
    "browserbase_click":        "browserbase_click",
    "browserbase_type":         "browserbase_type",
    "browserbase_extract":      "browserbase_extract",
    "browserbase_scroll":       "browserbase_scroll",
    "browserbase_wait":         "browserbase_wait",
    "browse_open":              "notebooklm_browse_open",
    "browse_sources":           "notebooklm_browse_sources",
    "browse_studio":            "notebooklm_browse_studio",
    "browse_chat":              "notebooklm_browse_chat",

    # Studio features (13 — 2025)
    "Audio Overview":    "Audio Overview",
    "Video Overview":    "Video Overview",
    "Briefing Doc":      "Briefing Doc",
    "Study Guide":       "Study Guide",
    "FAQ":               "FAQ",
    "Timeline":          "Timeline",
    "Mind Map":          "Mind Map",
    "Slide Deck":        "Slide Deck",
    "Infographic":       "Infographic",
    "Flashcards":        "Flashcards",
    "Deep Research":     "Deep Research",
    "Discover Sources":  "Discover Sources",
    "Chat Persona":      "Chat Persona",

    # i18n / Collab Browser
    "translatePage":     "translatePage",
    "BroadcastChannel":  "BroadcastChannel",
    "window.storage":    "window.storage",
    "6 languages":       "6 languages",
    "sendPrompt":        "sendPrompt",
    "Autopilot":         "Autopilot",

    # Android
    "Cookie Editor":     "Cookie Editor",
    "Browserbase":       "Browserbase",
    "Smithery":          "Smithery",
    "days_remaining":    "days_remaining",
    "needs_refresh":     "needs_refresh",

    # Skill chain integrations
    "docx skill":        "docx skill",
    "pptx skill":        "pptx skill",
    "theme-factory":     "theme-factory",

    # Interactive features
    "Interactive Mode":  "Interactive Mode",
}

# ─── Section minimum line counts ─────────────────────────────────────────────
# Prevent any section from being silently collapsed below its minimum.

SECTION_MINIMUMS: dict[str, int] = {
    "## Step 0":   12,   # Method Priority + modes
    "## Step 1":   55,   # All access methods + raw tools
    "## Step 2":    8,   # Decision engine
    "## Step 3":   10,   # Merge + template
    "## Step 4":   25,   # Feature generator + all features
    "## Step 5":    4,   # Deep analysis
    "## Behavior":  15,  # Rules table
    "## References": 6,  # All reference files
}

# ─── Table minimums ───────────────────────────────────────────────────────────

TABLE_MINIMUMS: dict[str, int] = {
    "Behavior Rules":  14,  # was 16 in v3, 14 in v4 after fixes
    "Source Index":     3,   # template table header rows
}

# ─── Fingerprint extraction ───────────────────────────────────────────────────

def extract_fingerprint(text: str) -> dict[str, Any]:
    """Extract a structured fingerprint from SKILL.md content."""
    lines = text.splitlines()

    # 1. Term presence (case-insensitive)
    terms_found = {}
    text_lower = text.lower()
    for term_id, search_str in CANONICAL_TERMS.items():
        terms_found[term_id] = search_str.lower() in text_lower

    # 2. Section line counts
    section_counts: dict[str, int] = {}
    current_section = None
    current_count = 0
    for line in lines:
        if line.startswith("## "):
            if current_section:
                section_counts[current_section] = current_count
            # Match section to minimum key
            for key in SECTION_MINIMUMS:
                if line.startswith(key):
                    current_section = key
                    break
            else:
                current_section = line[:40]
            current_count = 0
        elif current_section:
            current_count += 1
    if current_section:
        section_counts[current_section] = current_count

    # 3. Behavior Rules table row count
    behavior_rows = 0
    in_behavior = False
    for line in lines:
        if "## Behavior" in line:
            in_behavior = True
        elif in_behavior and line.startswith("## "):
            in_behavior = False
        elif in_behavior and line.startswith("|") and "---|" not in line and "Situation" not in line:
            behavior_rows += 1

    # 4. Tool count in Step 1A
    step1a_tools = len(re.findall(r'→ \w+\(', text))

    # 5. Description metadata
    m = re.search(r'description: "(.*?)"', text)
    desc = m.group(1) if m else ""
    desc_len = len(desc)

    # 6. Reference file count
    ref_count = len(re.findall(r'`references/[\w-]+\.md`', text))

    # 7. Total line count
    total_lines = len(lines)

    # 8. Frontmatter check
    has_valid_frontmatter = (
        text.startswith("---\n") and
        "name: " in text and
        "description: " in text and
        "<" not in desc and
        ">" not in desc and
        desc_len <= 1024
    )

    return {
        "timestamp":             datetime.now(timezone.utc).isoformat(),
        "md5":                   hashlib.md5(text.encode()).hexdigest(),
        "total_lines":           total_lines,
        "desc_length":           desc_len,
        "has_valid_frontmatter": has_valid_frontmatter,
        "terms":                 terms_found,
        "section_counts":        section_counts,
        "behavior_rows":         behavior_rows,
        "step1a_tool_calls":     step1a_tools,
        "reference_count":       ref_count,
    }


# ─── Validation ──────────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.errors:   list[str] = []
        self.warnings: list[str] = []
        self.passed:   list[str] = []

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def error(self, msg: str):   self.errors.append(f"❌ ERROR:   {msg}")
    def warning(self, msg: str): self.warnings.append(f"⚠️  WARN:    {msg}")
    def pass_(self, msg: str):   self.passed.append(f"✅ OK:      {msg}")


def validate_fingerprint(fp: dict[str, Any], baseline: dict[str, Any] | None = None) -> ValidationResult:
    r = ValidationResult()

    # 1. Frontmatter
    if fp["has_valid_frontmatter"]:
        r.pass_("Frontmatter valid (name, description, no XML, ≤1024 chars)")
    else:
        r.error(f"Frontmatter invalid — desc len={fp['desc_length']}, check for < > chars")

    # 2. Term presence — all canonical terms must appear
    missing_terms = [k for k, v in fp["terms"].items() if not v]
    found_count   = sum(1 for v in fp["terms"].values() if v)
    total_terms   = len(fp["terms"])
    if not missing_terms:
        r.pass_(f"All {total_terms} canonical terms present")
    else:
        for t in missing_terms:
            r.error(f"Missing canonical term: '{CANONICAL_TERMS[t]}' (key: {t})")

    # 3. Section line counts vs minimums
    for section_key, minimum in SECTION_MINIMUMS.items():
        actual = fp["section_counts"].get(section_key, 0)
        if actual >= minimum:
            r.pass_(f"Section '{section_key}' has {actual} lines (min {minimum})")
        elif actual == 0:
            r.error(f"Section '{section_key}' NOT FOUND")
        else:
            r.error(f"Section '{section_key}' too short: {actual} lines (min {minimum}) — likely condensed")

    # 4. Behavior Rules rows
    min_rows = TABLE_MINIMUMS["Behavior Rules"]
    if fp["behavior_rows"] >= min_rows:
        r.pass_(f"Behavior Rules: {fp['behavior_rows']} rows (min {min_rows})")
    else:
        r.error(f"Behavior Rules table: only {fp['behavior_rows']} rows (min {min_rows}) — rows were deleted")

    # 5. Reference count
    if fp["reference_count"] >= 6:
        r.pass_(f"References: {fp['reference_count']} files linked")
    else:
        r.warning(f"References: only {fp['reference_count']} linked (expected ≥6)")

    # 6. Line count sanity
    if fp["total_lines"] < 150:
        r.error(f"SKILL.md is too short: {fp['total_lines']} lines — possible data loss")
    elif fp["total_lines"] > 500:
        r.warning(f"SKILL.md is {fp['total_lines']} lines — consider splitting into references")
    else:
        r.pass_(f"Total lines: {fp['total_lines']}")

    # 7. Regression check against baseline
    if baseline:
        # Terms regression
        baseline_terms = baseline.get("terms", {})
        regressed = [k for k, v in baseline_terms.items() if v and not fp["terms"].get(k)]
        if regressed:
            for t in regressed:
                r.error(f"REGRESSION: Term '{CANONICAL_TERMS.get(t, t)}' was present in baseline, now missing")
        else:
            r.pass_("No term regressions vs baseline")

        # Section count regression (>20% shrinkage = error)
        for sec, base_count in baseline.get("section_counts", {}).items():
            curr_count = fp["section_counts"].get(sec, 0)
            if base_count > 0 and curr_count < base_count * 0.8:
                r.error(f"REGRESSION: Section '{sec}' shrank {base_count}→{curr_count} lines (>20% loss)")

        # Behavior rows regression
        base_rows = baseline.get("behavior_rows", 0)
        if base_rows > 0 and fp["behavior_rows"] < base_rows:
            r.error(f"REGRESSION: Behavior Rules {base_rows}→{fp['behavior_rows']} rows (rows deleted)")

    return r


# ─── Diff ─────────────────────────────────────────────────────────────────────

def diff_fingerprints(old: dict, new: dict) -> list[str]:
    lines = ["## Fingerprint Diff\n"]

    # Terms
    old_terms = old.get("terms", {})
    new_terms = new.get("terms", {})
    lost    = [CANONICAL_TERMS.get(k, k) for k in old_terms if old_terms[k] and not new_terms.get(k)]
    gained  = [CANONICAL_TERMS.get(k, k) for k in new_terms if new_terms[k] and not old_terms.get(k)]
    if lost:
        lines.append(f"❌ Terms LOST  ({len(lost)}): {', '.join(lost)}")
    if gained:
        lines.append(f"✅ Terms ADDED ({len(gained)}): {', '.join(gained)}")
    if not lost and not gained:
        lines.append("✅ Terms: no changes")

    # Section counts
    all_sections = set(list(old.get("section_counts", {}).keys()) + list(new.get("section_counts", {}).keys()))
    for sec in sorted(all_sections):
        o = old.get("section_counts", {}).get(sec, 0)
        n = new.get("section_counts", {}).get(sec, 0)
        if o != n:
            icon = "⚠️ " if n < o else "✅"
            lines.append(f"{icon} Section '{sec}': {o} → {n} lines ({'–' if n<o else '+'}{abs(n-o)})")

    # Counts
    for field, label in [("behavior_rows", "Behavior rows"), ("reference_count", "References"), ("total_lines", "Total lines")]:
        o = old.get(field, 0)
        n = new.get(field, 0)
        if o != n:
            icon = "⚠️ " if n < o else "✅"
            lines.append(f"{icon} {label}: {o} → {n}")

    lines.append(f"\nSize: {old.get('total_lines',0)} → {new.get('total_lines',0)} lines")
    return lines


# ─── Audit log ────────────────────────────────────────────────────────────────

def log_audit(event: str, details: dict):
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **details}
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── CLI commands ─────────────────────────────────────────────────────────────

def cmd_snapshot(args):
    text = SKILL_FILE.read_text()
    fp   = extract_fingerprint(text)
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out  = SNAPSHOT_DIR / f"snapshot_{ts}.json"
    out.write_text(json.dumps(fp, indent=2, ensure_ascii=False))
    # Also write "latest"
    (SNAPSHOT_DIR / "latest.json").write_text(json.dumps(fp, indent=2, ensure_ascii=False))
    print(f"✅ Snapshot saved: {out.name}")
    print(f"   Lines: {fp['total_lines']}, Terms: {sum(fp['terms'].values())}/{len(fp['terms'])}, Behavior rows: {fp['behavior_rows']}")
    log_audit("snapshot", {"file": str(out), "md5": fp["md5"]})


def cmd_validate(args):
    text = SKILL_FILE.read_text()
    fp   = extract_fingerprint(text)

    # Load baseline if exists
    baseline = None
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text())

    result = validate_fingerprint(fp, baseline)

    print("=" * 60)
    print("SKILL GUARD — Validation Report")
    print("=" * 60)
    for msg in result.passed:   print(msg)
    for msg in result.warnings: print(msg)
    for msg in result.errors:   print(msg)
    print("=" * 60)

    passed = len(result.passed)
    total  = passed + len(result.warnings) + len(result.errors)
    score  = int(passed / total * 100) if total else 0
    print(f"\nScore: {passed}/{total} ({score}%)")

    if result.ok:
        print("\n✅ VALIDATION PASSED — safe to save/publish")
        log_audit("validate_pass", {"score": score, "md5": fp["md5"]})
    else:
        print(f"\n❌ VALIDATION FAILED — {len(result.errors)} error(s) must be fixed before saving")
        log_audit("validate_fail", {"errors": result.errors, "score": score, "md5": fp["md5"]})

    return 0 if result.ok else 1


def cmd_diff(args):
    latest_path = SNAPSHOT_DIR / "latest.json"
    if not latest_path.exists():
        print("❌ No snapshot found. Run: python skill_guard.py snapshot")
        return 1

    old_fp = json.loads(latest_path.read_text())
    text   = SKILL_FILE.read_text()
    new_fp = extract_fingerprint(text)

    diff = diff_fingerprints(old_fp, new_fp)
    print("\n".join(diff))
    return 0


def cmd_update(args):
    """Validate a new version before replacing SKILL.md."""
    new_path = Path(args.new_file)
    if not new_path.exists():
        print(f"❌ File not found: {new_path}")
        return 1

    new_text = new_path.read_text()
    old_text = SKILL_FILE.read_text()

    old_fp = extract_fingerprint(old_text)
    new_fp = extract_fingerprint(new_text)

    # Load baseline
    baseline = None
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text())

    # Show diff first
    print("=== DIFF: current → proposed ===")
    print("\n".join(diff_fingerprints(old_fp, new_fp)))

    # Validate new version
    print("\n=== VALIDATION: proposed version ===")
    result = validate_fingerprint(new_fp, old_fp)  # old version as regression baseline

    for msg in result.passed:   print(msg)
    for msg in result.warnings: print(msg)
    for msg in result.errors:   print(msg)

    if result.ok or getattr(args, 'force', False):
        if result.ok:
            print("\n✅ SAFE — replacing SKILL.md")
        else:
            print("\n⚠️  FORCED — replacing despite errors (--force)")
        # Backup old
        ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        bak = SNAPSHOT_DIR / f"backup_{ts}.md"
        bak.write_text(old_text)
        print(f"   Backup: {bak.name}")
        # Write new
        SKILL_FILE.write_text(new_text)
        # Update snapshot
        (SNAPSHOT_DIR / "latest.json").write_text(json.dumps(new_fp, indent=2))
        log_audit("update_success", {"backup": str(bak), "errors": result.errors})
        return 0
    else:
        print(f"\n❌ BLOCKED — {len(result.errors)} error(s). Fix them or use --force to override.")
        log_audit("update_blocked", {"errors": result.errors})
        return 1


def cmd_history(args):
    if not AUDIT_LOG.exists():
        print("No audit log yet.")
        return 0
    entries = [json.loads(l) for l in AUDIT_LOG.read_text().splitlines() if l.strip()]
    limit   = getattr(args, 'limit', 20)
    for e in entries[-limit:]:
        ts    = e.get("timestamp", "?")[:19].replace("T", " ")
        event = e.get("event", "?")
        info  = ""
        if "score" in e:  info = f"score={e['score']}%"
        if "errors" in e and e["errors"]: info += f" errors={len(e['errors'])}"
        print(f"  {ts}  {event:<25} {info}")
    return 0


def cmd_baseline(args):
    if getattr(args, 'create', False):
        text = SKILL_FILE.read_text()
        fp   = extract_fingerprint(text)
        BASELINE.write_text(json.dumps(fp, indent=2, ensure_ascii=False))
        print(f"✅ Baseline created/updated from current SKILL.md")
        print(f"   Terms: {sum(fp['terms'].values())}/{len(fp['terms'])}")
        print(f"   Behavior rows: {fp['behavior_rows']}")
        print(f"   Lines: {fp['total_lines']}")
        log_audit("baseline_created", {"md5": fp["md5"]})
    elif getattr(args, 'check', False):
        if not BASELINE.exists():
            print("❌ No baseline. Run: python skill_guard.py baseline --create")
            return 1
        text     = SKILL_FILE.read_text()
        fp       = extract_fingerprint(text)
        baseline = json.loads(BASELINE.read_text())
        result   = validate_fingerprint(fp, baseline)
        for msg in (result.errors + result.warnings): print(msg)
        if result.ok:
            print("✅ No regressions vs baseline")
        return 0 if result.ok else 1
    return 0


def cmd_add_term(args):
    """Add a new canonical term to the guard."""
    # This modifies the script itself — guided output only
    print(f"To add term '{args.term}', add this line to CANONICAL_TERMS in skill_guard.py:")
    print(f'    "{args.term}": "{args.term}",')
    print("Then run: python skill_guard.py baseline --create")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Skill Guard — Safety Update System")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("snapshot",   help="Save fingerprint of current SKILL.md")
    sub.add_parser("validate",   help="Validate current SKILL.md")
    sub.add_parser("diff",       help="Diff current vs last snapshot")

    upd = sub.add_parser("update", help="Validate and replace SKILL.md with new version")
    upd.add_argument("new_file", help="Path to proposed new SKILL.md")
    upd.add_argument("--force", action="store_true", help="Replace even if validation fails")

    hist = sub.add_parser("history", help="Show audit log")
    hist.add_argument("--limit", type=int, default=20)

    bl = sub.add_parser("baseline", help="Manage canonical baseline")
    bl.add_argument("--create", action="store_true", help="Create baseline from current file")
    bl.add_argument("--check",  action="store_true", help="Check current vs baseline")

    at = sub.add_parser("add-term", help="Get instructions to add a new canonical term")
    at.add_argument("term", help="Term to add")

    args = p.parse_args()

    dispatch = {
        "snapshot": cmd_snapshot,
        "validate": cmd_validate,
        "diff":     cmd_diff,
        "update":   cmd_update,
        "history":  cmd_history,
        "baseline": cmd_baseline,
        "add-term": cmd_add_term,
    }

    if args.cmd not in dispatch:
        p.print_help()
        return 0

    return dispatch[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
