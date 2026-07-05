# Skill Ecosystem Auditor — Повна методологія
> Читається лише за потреби. SKILL.md тримає короткий протокол; деталі — тут.

## 1. Чеклісти етапів

### Stage 0 — Foundation
- [ ] Прочитати `melania`, `validation-mesh`, `continuation-memory`, `semantic-router`.
- [ ] Звірити джерела (skills dir, CHANGELOG-и, transcripts, uploads, наявність "read past chats").
- [ ] Чесно задокументувати, які джерела порожні/недоступні.
- [ ] Створити ледер + STENO-рядок.
- [ ] Узгодити з MA: порядок Stage 3, розмір партій, авто/чекпоінт.

### Stage 1 — Inventory (read-only)
Запустити `scripts/audit_scan.py`. На кожен скіл:
- [ ] `version`, `category` присутні?
- [ ] блоки `metadata / license / compatibility / allowed-tools`?
- [ ] каталоги `references / evals / scripts`?
- [ ] к-сть рядків (>500 → кандидат на винесення в references).

### Stage 2 — Cross-analysis (read-only)
- [ ] **P9 українською-перша** на кожен скіл: тригери / директива мови / приклади.
- [ ] **Coordination map** (хто кого називає).
- [ ] **Reverse/orphan map** (на кого ніхто не посилається — і чи це проблема).
- [ ] **Version drift**: версії в прозі/CHANGELOG vs диск.
- [ ] **Coverage gaps**: metadata / evals / guard.
- [ ] **Дублювання призначень** між скілами.
- [ ] Checkpoint MA.

### Stage 3 — Deep audit (read-only; партії 2–3 скіли)
На кожен скіл прочитати SKILL.md + references + evals + CHANGELOG і шукати:
- застарілі/мертві інструкції; зашиті моделі/версії/шляхи;
- суперечності всередині та з іншими скілами;
- надмірну довжину / порушення single-responsibility;
- відсутні edge-cases у Behavior-таблиці;
- повторювані фікси з CHANGELOG, які варто підняти в gate.
Кожна знахідка → Self-Dev Proposal (шаблон нижче).

### Stage 4 — Triage (read-only)
- [ ] Порахувати пріоритет кожної пропозиції (формула нижче).
- [ ] Згрупувати у партії 2–3, що не конфліктують між собою.
- [ ] MA схвалює/відхиляє покроково.

### Stage 5 — Execute (партії 2–3; ЄДИНИЙ етап зі змінами)
Цикл на пропозицію: `snapshot → diff → [MA confirm] → apply → validation-mesh → bump → CHANGELOG → snapshot`.
- [ ] Якщо Decision Gate = "новий скіл" → делегувати `skill-creation-guide`.
- [ ] Якщо `deprecation` → лишити shim/нотатку про міграцію, не видаляти різко.

### Stage 6 — Repackage
- [ ] `validation-mesh` по всіх змінених скілах.
- [ ] Перепакувати `.skill`/zip.
- [ ] Оновити ледер + continuation-state.

## 2. Каталог типів знахідок
| type | означає | типова дія |
|------|---------|-----------|
| `gap` | бракує обов'язкового елемента (version/evals/guard/UA-директива) | додати |
| `optimization` | працює, але можна стисліше/надійніше | переписати фрагмент |
| `new-pattern` | вдалий патерн, який варто узагальнити | підняти в gate керівних скілів |
| `deprecation` | мертве/дубльоване/не викликається | прибрати з міграцією |
| `refactor` | завелике/змішані відповідальності | розбити / винести references |
| `new-skill` | потреба не лягає в наявні скіли логічно | створити новий через guide |

## 3. Формула пріоритезації
```
priority = leverage × confidence × risk_reduction
  leverage:        3 = керівний скіл (вплив на всі), 2 = hub, 1 = листовий
  confidence:      3 = доведено даними, 2 = ймовірно, 1 = гіпотеза
  risk_reduction:  3 = прибирає рецидивний клас проблем, 2 = суттєво, 1 = косметика
```
Спершу виконуються пропозиції з найвищим `priority`; рівні — за найменшим diff.

## 4. Шаблон Self-Dev Proposal (рядок беклогу §4 ледера)
```
#N | skill(s) | type | "короткий заголовок"
   evidence:      що саме знайдено (з посиланням на рядок/файл)
   fix-location:  який скіл(и) міняємо + чи піднімаємо в gate
   action:        конкретний крок (1–2 речення)
   confidence:    high | med | low
   priority:      число за формулою §3
   status:        ⏳ awaiting MA | ✅ approved | ❌ rejected | 🟢 applied
```

## 5. Правила "не зламати"
- Жодного запису без показаного diff + явного підтвердження MA (Закон II).
- Не видаляти функцію без deprecation-плану.
- Не дублювати: спершу Decision Gate.
- Рецидив (≥2) завжди підіймається в gate + отримує eval.
- Усе, що створюємо/міняємо — лишається українською-першим.
