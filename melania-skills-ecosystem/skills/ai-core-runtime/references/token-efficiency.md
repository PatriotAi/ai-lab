# Token Efficiency Reference

## Core Philosophy
Every token has a cost. Never load, generate, or retain more than necessary for the current task.

## Preferred Patterns

### Patch Updates (PREFERRED)
```diff
- old_value: "foo"
+ new_value: "bar"
```
Use diffs instead of regenerating full files. Reference unchanged sections by name.

### Modular Loading
Load only the SKILL.md sections relevant to the current step.
Never preload all reference files at session start.

### Compressed Memory
When conversation exceeds ~20 turns, invoke `continuation-memory` skill
to compress session state into a compact continuation package.

### Selective Context
Include prior context only if it directly affects current output.
Drop resolved steps; keep active TODOs and unresolved dependencies.

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution |
|---|---|---|
| Giant system prompt | Saturates context window | Microkernel + progressive loading |
| Full file rewrites | Wastes 80%+ tokens | Patch-only updates |
| Recursive reasoning loops | Unbounded token spend | Set max_depth, break on stable state |
| Monolithic orchestration | Hard to debug, high latency | Modular skill composition |
| Preloading all agents | Unnecessary context | Activate on demand |
| Re-outputting unchanged files | Pure waste | Skip with "no changes to X" |

## Estimation Guide
- Simple response: ~100–500 tokens
- Architecture diagram (text): ~200–800 tokens
- Code module: ~300–1000 tokens
- Full continuation package: ~500–1500 tokens
- Full file rewrite (avoid): ~2000–10000 tokens
