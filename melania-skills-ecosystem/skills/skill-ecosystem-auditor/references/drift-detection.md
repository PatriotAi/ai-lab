# Drift Detection & Health Monitoring

## Temporal Drift Detection

Порівнюй стан екосистеми між аудитами:

```
Drift Report (vs попередній аудит):
┌─────────────────────────────────────────────┐
│ NEW skills:        +1 (auth-session-manager) │
│ VERSION bumps:     12 skills                  │
│ Metadata fixed:    9 → 0 missing              │
│ Eval coverage:     6/16 → 17/17               │
│ Avg SKILL.md size: 145 → 218 lines            │
│ Orphans:           4 → 0                       │
│ ⚠ Approaching limit: collaborative-browser    │
│   (421/500 lines)                             │
└─────────────────────────────────────────────┘
```

Зберігай snapshot кожного аудиту → відстежуй тренди.

---

## Health Dashboard Metrics

```
ECOSYSTEM HEALTH SCORE (0-100):

Coverage     (30 pts): metadata + evals + guard + UA-first
Consistency  (25 pts): naming + author + version scheme
Connectivity (20 pts): orphans, routing map completeness
Budget       (15 pts): SKILL.md < 500, desc < 1024
Freshness    (10 pts): recent updates, no stale versions

Score 90-100: Excellent
Score 70-89:  Good, minor gaps
Score 50-69:  Needs attention
Score < 50:   Significant debt
```

---

## Automated Audit Report Template

```markdown
# Audit Report — YYYY-MM-DD

## Summary
- Total skills: N
- Health score: X/100
- Critical issues: N
- Proposals generated: N

## Coverage Matrix
| Skill | meta | evals | guard | UA | lines | status |
|-------|------|-------|-------|----|----|--------|
| ...   | ✅   | ✅    | ✅    | ✅ | 218 | ✅     |

## Drift Since Last Audit
[temporal comparison]

## Proposal Backlog
[ranked by priority = confidence × impact × reach]

## Recommendations
[top 3 actions]
```

---

## Dependency Health

```
Перевірки графа залежностей:

□ Циклічні залежності (A→B→A)?           → CRITICAL
□ Скіл покликається на неіснуючий?        → CRITICAL
□ Orphan не-leaf (0 incoming, не листок)? → WARNING
□ Hub overload (1 скіл → 10+ залежностей)? → REVIEW
□ Версія в prose != версія на диску?       → DRIFT
```

---

## Recurring Issue Prevention

```
Принцип "не повторювати той самий фікс двічі":

Коли проблема знайдена в N скілах:
1. Фікс у кожному скілі (тактично)
2. ТА gate у governing skills (стратегічно):
   - melania Core Rules (для всіх майбутніх)
   - skill-creation-guide (як робити правильно)
   - guard script (автоматична перевірка)

Так проблема не повториться в наступних скілах.
```

---

## Audit Cadence

```
Коли запускати аудит:
- Після додавання 3+ нових скілів
- Перед major-релізом екосистеми
- Періодично (раз на N тижнів)
- Коли помічено дрейф (версії розійшлись)
- За запитом MA

Read-only до Stage 5 (виконання) — аудит сам нічого не змінює без підтвердження.
```
