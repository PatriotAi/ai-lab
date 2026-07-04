---
name: surgical-code-refactoring
description: "Token-efficient, dependency-aware methodology for modifying large existing codebases without breaking working functionality. Patch over rewrite, validate BEFORE integrating, regression-check after every change. ALWAYS use when editing a large single-file app, adding features to working code, fixing bugs in a big file, or the user says: не зламай робоче, економ токени, хірургічно, patch not rewrite, додай функцію не переписуючи, перевір перед інтеграцією, surgical, regression check, audit before changes. Also triggers for: великий HTML/JS файл, refactor without breaking, incremental feature integration, dependency-aware edits. DO NOT use for greenfield projects from scratch, or tiny scripts under 100 lines."
license: Proprietary
metadata:
  version: 1.5.2
  author: Melania (Master Administrator)
  category: code-refactoring
  created: 2026-06-02
  last_updated: 2026-06-02
---

# Surgical Code Refactoring — v1.0
> Метод напрацьований на проєкті AI Gateway (2670-рядковий single-file React/HTML застосунок). Дозволяє додавати складні функції у великий робочий код без регресій і без перевитрати токенів.
> Українською-перша: пояснення й приклади — українською за замовчуванням; код та технічні ідентифікатори лишаються англійською. Перемикання мови лише слідом за користувачем.


## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).

---

## Core Rule
НІКОЛИ не переписуй робочий код цілком. Патч точкових місць через `str_replace`. ЗАВЖДИ перевіряй (синтаксис + симуляція) ПЕРЕД інтеграцією. Після кожної зміни — регрес-тест що старі функції цілі.

---

## Правила Karpathy (поведінкові дефолти)
1. **Think Before Coding** — не припускай; вияви невизначеність і компроміси перед кодом.
2. **Simplicity First** — мінімум коду, що вирішує задачу; нічого спекулятивного.
3. **Surgical Changes** — чіпай лише необхідне; прибирай лише власний безлад. **Тест: кожен змінений рядок має прямо трасуватися до запиту користувача.** Якщо рядок не трасується — він зайвий.
4. **Goal-Driven Execution** — визнач критерії успіху; повторюй, доки не підтверджено.

## Git-guardrails + diagnose
**Git-guardrails (блокувати без явного підтвердження):** `git push --force` (на спільні гілки), `reset --hard`, `clean -f`, `checkout .` з незбереженими змінами, force-push у main/master. Якщо потрібна небезпечна операція — спершу попередь і покажи, що буде втрачено.

**Diagnose-петля (для багів):** reproduce (стабільне відтворення) → minimise (мінімальний кейс) → hypothesise (гіпотеза причини) → instrument (логи/точки) → fix (мінімальна правка) → regression-test (тест, що ловить цей баг назавжди). Не «фікси наосліп» — спершу відтвори.

## Чому цей метод (проблема яку вирішує)
Велика помилка: переписати весь файл щоб додати фічу → ламаються залежності, втрачаються токени, з'являються невидимі регресії. Гірша помилка: вбудувати функцію не перевіривши → вона не працює, а виявляється це пізно. Цей метод обидві виключає.

---

## 6-Фазний процес (виконувати послідовно)

### PHASE 1 — AUDIT
Перед будь-якою зміною: прочитай **актуальний** стан рівно тих місць, яких торкнешся —
саме з диску/файлу, а НЕ з памʼяті чи старого контексту. Файл міг оновитися в іншій
сесії й бути новішим/кращим; правки роби на реальному поточному вмісті, щоб не перезаписати свіже.
- `grep -n` для пошуку точок інтеграції, оголошень, використань
- Перевір баланс дужок: `node -e "t.match(/{/g).length===t.match(/}/g).length"`
- Знайди ВСІ місця де використовується те, що міняєш (`grep -n "funcName"`)

### PHASE 2 — PRIORITY MAP
Розбий роботу на незалежні під-процеси. Для кожного: складність + залежності. Таблиця. Почни з фундаменту (від чого залежать інші), закінчи UI.

### PHASE 3 — SURGICAL FIXES
- `str_replace` з унікальним контекстом (3+ рядки навколо), не цілий файл
- Великі блоки (компоненти) вставляй через `python3` heredoc у точну якірну точку
- Один логічний патч = одна зміна. Critical-зміни першими.
- ⚠️ ASCII-пастка: heredoc/copy може підмінити `()` на `（）`, коми на `，`. Завжди `grep -n "（\|）\|，\|；"` після вставки.

### PHASE 4 — INTEGRATION CHECK (перед тим як вважати готовим)
**Це ключова фаза. Перевірка ЗАВЖДИ перед інтеграцією, не після.**
- Синтаксис: для JSX → Babel transformSync; для JS → node parse
- Симуляція: grep-перевірка що кожна обіцяна можливість присутня в коді (checklist 15-25 пунктів)
- Якщо хоч один ❌ — виправ перш ніж рухатись далі

### PHASE 5 — DEPENDENCY VALIDATION
Перевір що нова функція правильно з'єднана: state оголошено ДО використання, prop проброшено через всі рівні, новий провайдер/модуль доданий у реєстр, persist (localStorage) + backup/restore оновлені.

### PHASE 6 — STABILITY / REGRESSION CHECK
Останнє: checklist що ВСІ попередні функції цілі (не тільки нова). Якщо щось зникло — регресія, відкочуй.

---

## Behavior

| Ситуація | ✓ Дія | ✗ Ніколи |
|----------|-------|----------|
| Додати фічу у великий файл | patch точкових місць | переписати весь файл |
| Готовий вбудувати функцію | спершу Babel+симуляція | вбудувати і сподіватись |
| Після зміни | регрес-тест старих функцій | йти далі без перевірки |
| Вставка великого компонента | python heredoc у якір | str_replace на 100 рядків |
| Після heredoc-вставки | grep на fullwidth-символи | припустити що ASCII цілий |
| Економія токенів | читати тільки потрібні рядки (view_range) | перечитувати весь файл щоразу |
| Кілька файлів-копій (app+index) | синхронізувати після КОЖНОЇ зміни | дати їм розійтись |

---

## Token Economy (важливо для великих файлів)
- `view` з `view_range` замість читання всього файлу
- `grep -n` щоб знайти рядок, потім точковий `view`
- Не дублюй вивід великого файлу в контекст без потреби
- Якщо сесія довга → continuation-memory skill для стиснення

---

## Validation Snippets (copy-paste)

**JSX (React inline через Babel):**
```bash
node -e "
const fs=require('fs');const babel=require('/tmp/babelcheck/node_modules/@babel/core');
const h=fs.readFileSync('app.html','utf8');
const m=h.match(/<script type=\"text\/babel\"[^>]*>([\s\S]*?)<\/script>/);
try{babel.transformSync(m[1],{presets:[['/tmp/babelcheck/node_modules/@babel/preset-react']]});console.log('✅ VALID');}
catch(e){console.log('❌',e.message.split('\n').slice(0,5).join('\n'));}
"
```

**Feature-presence simulation:**
```bash
node -e "
const t=require('fs').readFileSync('app.html','utf8');
const checks={'feature A':t.includes('marker A'),'feature B':t.includes('marker B')};
let p=0,f=0;for(const[k,v]of Object.entries(checks)){console.log(v?'✅':'❌',k);v?p++:f++;}
console.log(p+'/'+(p+f));
"
```

---

## Coordinates with
- `validation-mesh` — глибша перевірка якості перед deploy
- `continuation-memory` — стиснення стану при довгих сесіях (>20 обмінів)
- `semantic-router` — вибір цього методу для задач редагування великого коду

---

---

## TypeScript-Specific Patterns

```typescript
// ✗ any розповсюджується як інфекція
function process(data: any) { return data.result; }

// ✓ Точний тип — виявляє помилки на compile-time
interface ApiResponse<T> { result: T; error?: string; }
function process<T>(data: ApiResponse<T>): T { return data.result; }
```

**Хірургічний рефакторинг типів:**
1. `tsc --noEmit` — знайди всі помилки без компіляції
2. Фіксуй по одному файлу — від листових (немає залежностей) до кореневих
3. Ніколи не додавай `@ts-ignore` як "фікс" — це маскування помилки

---

## React Компонент — Типові Патерни Рефакторингу

```typescript
// ✗ Великий компонент — важко тестувати і підтримувати
const Dashboard = () => { /* 300 рядків */ }

// ✓ Розбий: Container + Presentational + Custom Hooks
const useDashboardData = () => { /* логіка */ return { data, loading, error }; }
const DashboardView = ({ data }: Props) => { /* лише UI */ }
const Dashboard = () => { const state = useDashboardData(); return <DashboardView {...state}/>; }
```

**Сигнали що компонент треба розбити:**
- > 150 рядків JSX
- > 3 `useState` в одному компоненті  
- > 2 `useEffect` — кожен має своя логіку

---

## CSS/Tailwind — Безпечне Додавання Стилів

```bash
# Перед змінами стилів — знайди всі використання класу
grep -r "text-primary" src/ --include="*.tsx"

# Tailwind: ніколи не видаляй клас не перевіривши всі файли
# Додавай через tailwind.config.js extend, не через arbitrary values
```

---

## 📎 Advanced Patterns (v4)

Read `references/language-patterns.md` WHEN you need: Python pitfalls, dead code elimination, dependency injection, strangler fig, DB query optimization.
Load only on demand — not proactively.

---

## Зміни
_⚠ Історична примітка: окремі ранні записи нижче мають дубльовані номери версій (артефакт злиттів). Усі записи збережено; нумерацію НЕ переписано без верифікації джерел._
- **v1.5.2** (2026-06-26) — Stage 3 S-2: примітка про дубль v1.3.0 у changelog (вміст збережено, нумерацію не переписано). Лише додавання примітки.
- **v1.5.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.0.0** (2026-06-02) — додано `metadata`/`license`-frontmatter + явну директиву «українською-перша»; додано в Routing Map семантичного роутера. _(аудит Кластер 4: metadata + P9 + P-23)_

- **v1.3.0** (2026-06-02) — PHASE 1 підсилено: читати АКТУАЛЬНИЙ стан з диску (файл міг оновитися в іншій сесії).

- **v1.2.0** (2026-06-02) — TypeScript refactoring patterns, React component decomposition, CSS/Tailwind safe changes.

- **v1.3.0** (2026-06-02) — Pre-Update Preservation Protocol; language-patterns reference (Python, dead code, DI, strangler fig, DB).
- **v1.4.0** (2026-06-10) — Фаза 2: I-5: правила Karpathy (кожен змінений рядок трасується до запиту).
- **v1.5.0** (2026-06-10) — Фаза 3: I-8: git-guardrails (force-push/reset --hard/clean -f) + diagnose-петля (reproduce→…→regression).
