---
name: skill-ecosystem-auditor
description: >
  Проводить глибокий, багатоетапний аудит усієї екосистеми скілів і перетворює
  напрацювання (повторювані проблеми, фікси, патерни) на оновлення наявних скілів
  або, за потреби, нові скіли. Read-only до схвалення MA: інвентаризація →
  крос-аналіз → беклог Self-Dev пропозицій → виконання diff-за-diff.

  ALWAYS use when: аудит скілів, ревізія екосистеми, "проаналізуй всі скіли",
  "онови скіли на основі напрацювань", позбавлення зайвих функцій, виявлення
  дублювання/дрейфу версій, перевірка покриття evals/guard/metadata, чи оновити
  наявний скіл чи створити новий, періодична інспекція якості скілів.

  Also: ecosystem audit, skill audit, audit ledger, Self-Dev backlog, "не
  повторювати ті самі фікси", consolidate skills, deprecate skill, drift check,
  coverage gap, "зроби з цього процесу скіл", скіл-аудитор, ревізія.

  DO NOT use for: створення ОДНОГО скіла з нуля (це skill-creation-guide +
  skill-creator), чи разову валідацію одного артефакту (це validation-mesh).
compatibility: >
  Claude.ai (всі плани) · Claude Code · Codex CLI · Cursor · Copilot.
  Логіка аудиту крос-платформна. Guard/snapshot та bash-аналіз працюють там, де
  доступний Python; на платформах без файлового доступу — degrade до ручного
  заповнення ледера.
allowed-tools:
  - Bash(python:*)
  - Read
  - Write
license: Proprietary
metadata:
  version: 1.7.0
  author: Melania (Master Administrator)
  category: skill-governance
  created: 2026-06-02
  last_updated: 2026-07-19
---

# Skill Ecosystem Auditor — v1.7.0
> Меланія · MA-керований · детальна методологія в `references/methodology.md`
> Працює під владою `melania-skill-master-administrator` (Три Закони, авторитет MA, Self-Dev Engine).
> Claude Code hooks: `pre-edit → skill_guard.py --validate` · `post-edit → skill_guard.py --snapshot`


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Core Rule
**Спершу аналізуй, потім пропонуй, і лише після схвалення MA — змінюй.**
За замовчуванням **оновлюй наявний скіл**; **новий скіл створюй ЛИШЕ** коли оновлення
неможливе або нелогічне (див. Decision Gate). Кожен повторюваний фікс вбудовуй у
*керівні* скіли як постійний gate, щоб не повторювати його щоразу.

## Мова
Працюй і звітуй **українською за замовчуванням** (українською-перша). Перемикайся
лише якщо MA пише іншою мовою. Будь-який скіл, що створюється/оновлюється цим
аудитом, має лишатися українською-першим: українські тригери + поведінка українською
за замовчуванням + українські приклади.

---

## Decision Gate — оновити наявний чи створити новий?

Перед КОЖНОЮ зміною прожени рішення цим деревом:

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| Зміна вкладається в існуючий скіл без зламу його призначення | **Онови наявний** (diff + bump версії) | Не плоди дублікат |
| Фікс стосується процесу створення/керування скілами | Вбудуй gate у `skill-creation-guide` + `melania` | Не лишай фікс лише в одному скілі |
| Нова потреба не належить жодному наявному скілу логічно | **Створи новий** через `skill-creation-guide` | Не «розпухай» чужий скіл |
| Оновлення зробило б скіл суперечливим/завеликим (>500 рядків ядра) | Винеси в `references/` або **розділи на новий скіл** | Не ламай single-responsibility |
| Функція мертва / дублюється / не викликається | Запропонуй **deprecation** (з планом міграції) | Не видаляй без diff і згоди MA |

---

## Workflow — 7 етапів (0–4 read-only, 5 змінює, 6 пакує)

```
0 Foundation  → 1 Inventory → 2 Cross-analysis → 3 Deep audit
            → 4 Triage → [MA APPROVE] → 5 Execute (diff-by-diff) → 6 Repackage
```

### Stage 0 — Foundation & State
- Прочитай `melania` (governance), `validation-mesh` (QA), `continuation-memory` (стан), `semantic-router` (маршрути).
- Звір **джерела**: диск зі скілами (у claude.ai — `/mnt/skills/user`; у лабораторії ai-lab — `melania-skills-ecosystem/skills/`), CHANGELOG-и, `/mnt/transcripts`, `/mnt/user-data/uploads`. Чесно познач, що порожнє.
- Створи `SKILL-AUDIT-LEDGER.md` (шаблон у `references/ledger-template.md`) і STENO-рядок continuation-memory.

### Stage 1 — Inventory (read-only)
Для кожного скіла зніми: `version`, `category`, наявність `metadata/license/compatibility/allowed-tools`,
каталогів `references/evals/scripts`, к-сть рядків. Запусти `scripts/audit_scan.py`.

### Stage 2 — Cross-analysis (read-only)
- **P9 українською-перша**: чи є українські тригери / директива мови відповіді / приклади.
- **Coordination map** (хто кого називає) + **reverse map** (orphan-check).
- **Drift**: версії, зашиті у прозі/CHANGELOG, проти реальних на диску.
- **Coverage gaps**: metadata / evals / guard.
- **Дублювання**: перетин призначень скілів.
**Checkpoint:** звіт MA.

### Stage 3 — Deep audit (read-only, бить на під-етапи по 2–3 скіли)
Порядок за вибором MA: leverage-first (керівні) / risk-first (великі) / по категоріях.
Кожна знахідка → **Self-Dev Proposal** у §4 ледера з полями:
`skill(s) · type · title · evidence · fix-location · confidence · status`.
`type ∈ {gap, optimization, new-pattern, deprecation, refactor, new-skill}`.

### Stage 4 — Triage (read-only)
Ранжуй беклог (leverage × confidence × ризик). Згрупуй у партії 2–3.
**Checkpoint:** MA схвалює / відхиляє кожну пропозицію.

### Stage 5 — Execute (ЄДИНИЙ етап, що змінює; партіями 2–3)
Цикл на КОЖНУ схвалену пропозицію:
```
re-read (актуальний стан з диску) → snapshot → diff (показати MA) → [confirm] → apply → validation-mesh → bump версії → CHANGELOG → новий snapshot
```
**Re-read обовʼязковий:** реєстр живий — версія скіла могла оновитися в іншому чаті. Правки роби
на реальному поточному вмісті, не на старому з контексту, щоб НЕ перезаписати новіше/краще.
```
Закон II: жодного запису без показаного diff і явного підтвердження MA.
Якщо Decision Gate сказав "новий скіл" — делегуй у `skill-creation-guide`, не патч чужого.

### Stage 6 — Repackage & verify
Фінальний прогін `validation-mesh` по змінених скілах + перепакування `.skill`/zip.
Онови ледер і continuation-state.

---

## Тест навичок субагентом під тиском
Перевіряй навички не «вікториною», а реалістичним сценарієм: дай субагенту завдання з тиском
(дедлайн, авторитет, дефіцит, втома) і дивись, чи дотримується правил навички, чи знаходить лазівку.
Кожну знайдену лазівку → у таблицю раціоналізацій відповідної навички (`skill-creation-guide`) + новий eval-кейс.
TDD-вимога діє і тут: правка навички в Stage 5 починається з failing-тесту.

## Режим «harvest» — витяг знань і зовнішній пошук (N-1)
Два тригери, один конвеєр, той самий СТОП-гейт MA:

**A. Внутрішній (із сесії):** «що ми навчилися», «витягни патерн», «збережи як скіл», кінець сесії →
1. **Ship** — закоміть/зафіксуй незавершене.
2. **Extract** — конкретні висновки сесії (не загальники).
3. **Pattern Detect** — повторюване (≥2 рази) → кандидат у правило/скіл.
4. **Persist** — daily-log через continuation-memory (напр. файл за датою).
**Selectivity-gate:** «чи допоможе це комусь за 6 місяців?» Ні → не кодифікувати.
**Дедуп:** перед створенням — Decision Gate (онови наявний скіл; новий лише якщо не лягає).

**B. Зовнішній (за запитом MA на пошук оновлень/покращень):**
Tier1-джерела (кураторські списки, офіційні) **+ ширший пошук «необроблених діамантів»** (нішеві/нові/малозіркові — презентувати ОКРЕМОЮ секцією) → звіт + diff-пропозиції + чернетки/пакети → **СТОП до схвалення MA** → застосування лише після «застосувати».
Безпека: чужі скіли можуть виконувати код — харвестимо **ідеї**, hook/CLI лише після рев'ю рядок-за-рядком.

## Anti-repeat Engine (щоб не робити те саме щоразу)
Коли проблема трапилась **≥2 рази** в різних скілах — це більше не локальний баг, а **патерн**:
1. Виправ у кожному ураженому скілі (Stage 5).
2. Додай **постійний gate** у `skill-creation-guide` (правило) і за потреби в `melania` (governance) + спільний `references/`.
3. Додай eval, що ловить рецидив.
Так фікс стає бар'єром для всіх майбутніх скілів, а не разовою латкою.

---

## Координація зі скілами
| Skill | Роль в аудиті |
|-------|---------------|
| `melania-skill-master-administrator` | Governance, Три Закони, авторитет MA, версії/CHANGELOG |
| `validation-mesh` | Оцінка якості + VALID/INVALID/UNKNOWN на кожну зміну |
| `continuation-memory` | STENO-стан → аудит переживає сесії й продовжується |
| `semantic-router` | Куди маршрутизувати знахідки; виявлення orphan-скілів |
| `skill-creation-guide` | Виконавець гілки "створити новий скіл" |
| `n8n-orchestrator` / `ai-core-runtime` | Якщо аудит треба автоматизувати як пайплайн |
| `pre-delivery-gate` | **Межа:** PDG — гейт ОДНОГО артефакту перед видачею; авдитор — періодична ревізія ЕКОСИСТЕМИ. Не підміняють одне одного |
| `safety-compliance-gate` | Канон безпеки/IP; принцип harvest-mode B живе ТАМ — авдитор лише посилається |

**Pipeline:** `continuation-memory (state) → audit stages 0–4 → validation-mesh → MA → execute → melania (CHANGELOG/version)`

---

## References
Читай `references/methodology.md` КОЛИ: потрібні повні чеклісти кожного етапу,
формули пріоритезації, повний каталог типів знахідок, або шаблон Self-Dev Proposal.
Читай `references/ledger-template.md` КОЛИ: стартуєш новий аудит з нуля.
Читай `references/harvest-report-template.md` КОЛИ: запускаєш зовнішній harvest (Tier1+діаманти → беклог → виконання). Правило: беклог з ОПИСІВ → re-read повного вмісту при виконанні стабільно скасовує/міняє пункти — звіряй, не застосовуй наосліп.

- **v1.3.0** (2026-06-02) — re-read актуального стану як перший крок Stage 5 (захист від перезапису новіших версій).

- **v1.2.0** (2026-06-02) — automated metrics, dependency graph analysis, audit scoring.

## 📎 Advanced Patterns (v4)

Read `references/drift-detection.md` WHEN you need: temporal drift, health score (0-100), audit report template, dependency health, recurring-issue prevention.
Load only on demand — not proactively.

---

## Зміни
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (артефакт злиттів). Усі записи збережено; нумерацію НЕ переписано без верифікації джерел._
- **v1.7.0** (2026-07-19) — Self-Dev Wave 2 (аудит 2026-07-18): полагоджено зламані code-fences у Stage 5 (дубль рядка + осиротіла ```-обгортка) [#23]; шлях диска скілів узагальнено на обидва середовища claude.ai/ai-lab (SKILL.md + дефолт `audit_scan.py`) [#22/#29]; у Координацію додано межу з `pre-delivery-gate` (гейт артефакту ≠ ревізія екосистеми) [#20] і зворотний покажчик на `safety-compliance-gate` як канон harvest-mode B [#19]; синхрон H1-банера (був v1.0 при 1.6.2). Формат/межі; методологія незмінна.
- **v1.6.2** (2026-06-26) — Stage 3: **S-3** +власні `evals/` (5, канон-схема). **S-2** примітка про дубль v1.3.0. Додавання + примітка.

- **v1.6.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.6.0** (2026-06-14) — P-S3 (harvest-2026): новий `references/harvest-report-template.md` — багаторазовий шаблон зовнішнього harvest з ГОЛОВНИМ правилом «беклог з описів → re-read повного вмісту скасовує/міняє пункти» (емпірика: 3 корекції) + real-validation дисципліна (audit_scan + skill_guard, не grep).
- **v1.3.0** (2026-06-02) — Pre-Update Preservation Protocol; drift-detection reference (temporal drift, health score, dependency health).
- **v1.4.0** (2026-06-10) — Фаза 2: I-2: тест навичок субагентом під тиском + TDD-вимога у Stage 5.
- **v1.5.0** (2026-06-10) — Фаза 4: режим «harvest» (внутрішній Ship→Extract→Pattern→Persist + зовнішній Tier1+«діаманти» зі СТОП-гейтом MA; selectivity 6 міс; дедуп через Decision Gate).
- **v1.5.1** (2026-06-10) — анти-застарілість: daily-log як приклад за датою (не зашитий шлях).
