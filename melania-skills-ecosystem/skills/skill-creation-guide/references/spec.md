# skill-creation-guide — Spec (джерело evals)

## Мета
Покроковий, токен-ефективний гайд створення Claude Skills у форматі SKILL.md: YAML-frontmatter,
тіло-патерни, progressive disclosure (references/), evals, guard, координація з рештою екосистеми.
НЕ дублює governance-механіку (версії/CHANGELOG/Закони — `melania`) і не є валідатором (`validation-mesh`).

## Тригери
- ALWAYS use when: створити новий скіл, написати/структурувати SKILL.md, упакувати .skill,
  «як зробити skill / формат skill / SKILL.md шаблон / додати скіл».
- DO NOT use for: оновлення наявного скіла без створення нового (→ Decision Gate; здебільшого `melania`),
  разову валідацію артефакту (→ `validation-mesh`), безпеку/публікацію/іменування (→ `safety-compliance-gate`).

## Критерії приймання (кожен → eval-кейс; baseline провалює)
1. **Frontmatter валідний:** `name` без reserved-brand (не "claude"/"anthropic"), `description` ≤ 1024 символів,
   `version` (semver); за потреби `metadata`/`license`/`compatibility`/`allowed-tools`.
2. **Тіло < ~500 рядків**; глибокі деталі винесені в `references/` (progressive disclosure), не інлайн.
3. **Description несе тригери** (ALWAYS use when / DO NOT use for) — для коректного спрацювання роутингом.
4. **Decision Gate застосовано:** за замовчуванням онова наявного; новий скіл — лише коли інакше нелогічно/неможливо.
5. **Координація явна:** посилання на власників механіки (routing→`semantic-router`, validation→`validation-mesh`,
   governance→`melania`, safety→`safety-compliance-gate`, стан→`continuation-memory`), без дублювання.
6. **Pre-save gate (канон `melania`)** — обов'язковий перед збереженням: re-read → diff → validation-mesh →
   safety-compliance-gate → backup → merge-not-replace → bump+CHANGELOG → show diff + явне схвалення (Закон II).
7. **≥1 eval-кейс** на бажану поведінку; guard-снапшот для регресій (`skill_guard.py`).
8. **UA-first (P9):** робоча мова — українська; фінал/статус — українською де доречно.

## Координація
`skill-creator` (інструментарій) · `melania` (governance/lifecycle) · `validation-mesh` (валідація) ·
`safety-compliance-gate` (безпека/IP) · `semantic-router` (інтеграція в роутинг) · `continuation-memory` (стан).
