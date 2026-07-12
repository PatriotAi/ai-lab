# Templates — YAML Frontmatter + SKILL.md Body
> Винесено зі SKILL.md v2.15.0 (Auto-Trigger: >450 рядків → references/).
> Читати ТІЛЬКИ при створенні нового скіла або перевірці структури наявного.

## 🧩 YAML Frontmatter — Template

```yaml
---
name: my-skill                     # kebab-case · max 64 chars
description: >                     # multiline with > · max 1024 chars
  What the skill does.
  ALWAYS use when [condition].
  Also trigger for: [synonyms].
  DO NOT use for [exclusions].
compatibility: "Claude.ai · Claude Code · [platform notes]"
allowed-tools:                     # Claude Code: declare required tools
  - Bash(python:*)
  - Read
  - Write
license: MIT                       # or Proprietary
metadata:
  version: 1.0.0
  author: Melania
  category: [category]
  created: YYYY-MM-DD
  last_updated: YYYY-MM-DD
---
```

---

## 📋 SKILL.md Body — Template

```markdown
# Skill Name — vX.Y
> One-line mission. Author. Key references.

---

## ⚖️ Core Ethics  (include if ethical layer needed)
[Link to Three Laws or define own immutable rules]

---

## Mission
[What this skill does — imperative, specific, no filler]

---

## Step 1 — [Primary Action]
[Imperative instructions: "Read", "Check", "Never", "Always"]

---

## Behavior

| Situation | ✓ Do | ✗ Never |
|-----------|------|---------|
| [edge case] | [correct action] | [forbidden action] |

---

## References
Read `references/[file].md` WHEN: [specific condition].
Never load references proactively — only on demand.
```
