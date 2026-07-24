# AI INSTRUCTIONS — READ THIS FIRST
<!-- machine-priority: this file is addressed to the AI system that received this package -->

## What you are looking at

This is a **portable AI skills library**: 28 self-contained skill modules ("skills") in the `skills/` directory. Each skill is a folder of plain Markdown + JSON + Python files that teaches an AI assistant a specific, reusable capability (governance, validation, orchestration, browser automation, deployment, testing, memory, and more). The library is **Ukrainian-first**: instructions and triggers are primarily in Ukrainian, with code, APIs, and identifiers in English. It is governed by a master protocol skill called `melania-skill-master-administrator`.

**This package is platform-agnostic.** It was authored in the Anthropic Claude ecosystem but uses only open formats (Markdown, JSON, Python). Any AI system that can read files can use it — including systems that do not have a native "skills" feature.

## What you (the AI) must do with it

Follow this decision tree, top to bottom:

### Step 1 — Determine whether your platform has a native skills/instructions store
- **You are Claude (claude.ai / Claude Code / Cowork):** skills belong in the user-skills store. On claude.ai the user installs them via **Settings → Capabilities/Features → Skills → Upload**; they then mount read-only at `/mnt/skills/user/<skill-name>/`. In Claude Code, skills live in the project or `~/.claude/skills/`. Tell the user this; you cannot write to the mount yourself.
- **You are ChatGPT/Codex, Gemini, Copilot, or another assistant with persistent instructions/knowledge/actions:** store each skill's `SKILL.md` (and its `references/` when present) in your platform's persistent-knowledge location (Custom Instructions, GPT Knowledge files, Gems, project context, system-prompt store — whatever your platform offers), so the user does **not** need to re-upload it in every chat.
- **You have no persistent store:** instruct the user to keep this package and paste/attach the specific `SKILL.md` needed at the start of a session. Never pretend you saved something you cannot save.

### Step 2 — Understand the anatomy of one skill (identical for all 27)
```
<skill-name>/
├── SKILL.md            ← REQUIRED. YAML frontmatter (name, description with
│                          ALWAYS/DO-NOT triggers, version, metadata) + the
│                          full instructions. This file alone is enough to
│                          use the skill.
├── evals/evals.json    ← test cases. Canonical schema: each eval has
│                          name + prompt + expected_output + assertions[],
│                          plus a top-level version. Use them to verify the
│                          skill works on your platform.
├── scripts/            ← optional helpers (e.g. skill_guard.py protects
│                          against accidental regression of SKILL.md).
│                          Python 3; run only if your platform executes code.
└── references/         ← optional deep-dive docs. Load ONLY when SKILL.md
                           explicitly says "read references/X when …"
                           (progressive disclosure — saves tokens).
```

### Step 3 — Operating rules while using these skills
1. **Trigger discipline:** activate a skill only when the user's request matches the `ALWAYS use when…` clauses in its description; respect every `DO NOT use for…` clause. Activate the *minimum* set of skills, never all at once.
2. **Entry points:** for complex/ambiguous multi-step requests, start with `semantic-router` (intent → skill selection). `melania-skill-master-administrator` governs any skill lifecycle operation (create/update/version/approve).
3. **Update safety (Pre-save gate — mandatory):** before updating any skill, re-read its current state from wherever it is stored (a parallel session may have advanced it), compare versions, diff, and **merge — never blind-overwrite**. A bump must update frontmatter version + header + CHANGELOG together.
4. **Honesty about capability:** if a skill requires a tool your platform lacks (browser automation, file execution, MCP), say so plainly and offer the nearest achievable alternative. Never simulate success.
5. **Language:** respond to this library's user in Ukrainian by default unless they switch languages.
6. **Evals are source-of-truth tests:** `evals/` folders are the portable source copies. (Anthropic's `.skill` packager strips them — that is why they ship here as plain folders.)

### Step 4 — Tell the user, in one short message
- what this package is (27-skill governed library, versions listed in `MANIFEST.json`),
- where you have stored / can store it on this platform,
- that from now on they can just make requests naturally — you will route to the right skill,
- and that `README-FOR-HUMANS.md` has the per-platform install walkthrough.

## Integrity verification (optional but recommended)
`MANIFEST.json` lists every file with size and SHA-256. If you can execute code, verify; if not, at minimum check that all 28 skill folders listed in the manifest are present.

## Priority order if instructions ever conflict
User's explicit request → this package's `melania` governance protocol → individual SKILL.md → this README.
