# Language-Specific Refactoring Patterns

## Python

```python
# ✗ Mutable default argument — класична пастка
def add(item, items=[]):  # items зберігається між викликами!
    items.append(item)
    return items

# ✓ None як sentinel
def add(item, items=None):
    items = items or []
    items.append(item)
    return items
```

**Безпечний рефакторинг Python:**
1. `python -m py_compile file.py` — синтаксис перед запуском
2. Type hints + `mypy` — лови помилки типів статично
3. Ніколи не видаляй `__init__.py` не перевіривши імпорти
4. Рефактори по одній функції; запускай тести після кожної

---

## Dead Code Elimination

```bash
# Знайди невикористаний код перед видаленням
# Python:
pip install vulture && vulture src/ --min-confidence 80

# JavaScript/TS:
npx ts-prune        # неекспортований/невикористаний код
npx depcheck        # невикористані залежності
```

**Правило:** перш ніж видалити — `grep -r "functionName" .` по всьому проекту. Динамічні виклики (`getattr`, `eval`, reflection) граф не бачить.

---

## Dependency Injection (тестованість)

```typescript
// ✗ Жорстка залежність — важко тестувати
class UserService {
  private db = new PostgresDB();  // hardcoded
  getUser(id) { return this.db.query(id); }
}

// ✓ Інжекція — можна підмінити mock у тестах
class UserService {
  constructor(private db: Database) {}  // інтерфейс
  getUser(id) { return this.db.query(id); }
}
// prod:  new UserService(new PostgresDB())
// test:  new UserService(new MockDB())
```

---

## Extract Method (зменшення складності)

```
Сигнали що метод треба розбити:
- > 20 рядків
- > 3 рівні вкладеності
- коментар "// тепер робимо X" → це окремий метод
- складна умова в if → витягни в named boolean

Послідовність:
1. Визнач логічний блок
2. Витягни в приватний метод з описовою назвою
3. Заміни блок викликом
4. Запусти тести (поведінка не змінилась!)
```

---

## Strangler Fig (поступова заміна legacy)

```
Заміна старої системи БЕЗ big-bang переписування:

1. Створи новий код ПОРУЧ зі старим
2. Перенаправ ОДИН шлях на новий код
3. Перевір що працює (стара система ще fallback)
4. Поступово перенаправляй більше шляхів
5. Коли все на новому — видали старе

Ризик мінімальний: на кожному кроці можна відкотитись.
```

---

## React-Specific

```typescript
// ✗ Inline функція — новий референс щоренду → зайві ре-ренди
<Button onClick={() => handleClick(id)} />

// ✓ useCallback для стабільного референсу
const onClick = useCallback(() => handleClick(id), [id]);
<Button onClick={onClick} />

// ✗ Обчислення щоренду
const sorted = data.sort((a,b) => a.x - b.x);

// ✓ useMemo для дорогих обчислень
const sorted = useMemo(() => [...data].sort((a,b) => a.x - b.x), [data]);
```

---

## Database Query Optimization

```sql
-- ✗ N+1 проблема: запит у циклі
-- for user: SELECT * FROM orders WHERE user_id = ?

-- ✓ Один запит з JOIN
SELECT u.*, o.* FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.active = true;

-- Завжди: EXPLAIN ANALYZE перед і після оптимізації
-- Індекс на колонки у WHERE/JOIN/ORDER BY
```

---

## Safe Config Changes

```
Перед зміною конфігу (.env, config.json, tailwind.config):
1. grep всі місця де читається ця змінна
2. Зміни → перевір що всі споживачі сумісні
3. Default-значення для нових опцій (зворотна сумісність)
4. Ніколи не видаляй стару опцію одразу — deprecate спершу
```
