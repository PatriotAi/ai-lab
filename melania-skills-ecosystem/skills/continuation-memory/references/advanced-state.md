# Advanced State Management

## Diff-Based State Updates

Замість повного перезапису пакету — зберігай лише дельту:

```
## STATE_DELTA (від попереднього пакету)
+ ADDED:    auth.py (новий файл, OAuth flow)
~ CHANGED:  router.py (додано endpoint /api/v2)
- REMOVED:  legacy_handler.py (видалено)
→ PHASE:    BUILD → TESTING
✓ RESOLVED: TODO #3 (rate limiting) — done
```

Дельта на порядок менша за повний пакет → економія токенів при частих оновленнях.

---

## Versioned Snapshots

```json
{
  "snapshots": [
    {"v": 1, "ts": "2026-06-02T10:00", "phase": "BUILD", "files": 3, "hash": "a1b2"},
    {"v": 2, "ts": "2026-06-02T11:30", "phase": "TESTING", "files": 5, "hash": "c3d4"},
    {"v": 3, "ts": "2026-06-02T12:00", "phase": "DONE", "files": 5, "hash": "e5f6"}
  ],
  "current": 3
}
```

Дозволяє rollback до будь-якої версії стану: "повернись до snapshot v2".

---

## Automatic Checkpoint Triggers

Генеруй continuation package автоматично при:

| Тригер | Чому |
|---|---|
| Кожні N завершених кроків (N=5) | регулярний backup |
| Перед ризикованою операцією | відновлення якщо щось піде не так |
| Зміна фази (BUILD→TEST) | природна точка збереження |
| Context window > 70% | до того як впремося в ліміт |
| Користувач сказав "зберегти" | явний запит |
| Перед перемиканням задачі | щоб не загубити контекст |

---

## State Merge Strategies

Коли є два стани (паралельні сесії):

```
1. NEWER WINS    — за timestamp (default для незалежних полів)
2. UNION         — обʼєднати списки (TODO з обох сесій)
3. MANUAL        — конфлікт у тому самому файлі → спитати MA
4. THREE-WAY     — base + ours + theirs → як git merge
```

Правило: автоматичний merge лише для незалежних полів; конфлікт у тому самому артефакті завжди ескалюється до користувача.

---

## Compression Levels

| Рівень | Що зберігає | Розмір |
|---|---|---|
| **L0 Full** | Все: код, рішення, історія | ~5000 ток |
| **L1 Standard** | Архітектура + active work + TODO | ~1500 ток |
| **L2 Compact** | Лише phase + current file + next step | ~300 ток |
| **L3 STENO** | Однорядковий маркер позиції | ~30 ток |

Вибирай рівень за частотою оновлень: часті → L3, рідкі → L1.
