# Skill Lifecycle Management

## Version Scheme (Semantic)

```
MAJOR.MINOR.PATCH

MAJOR (X.0.0): breaking change
  - видалено секцію/правило що інші скіли використовують
  - змінено формат виводу несумісно
  - перейменовано скіл

MINOR (1.X.0): нова можливість, сумісна
  - додано нову секцію/патерн/reference
  - розширено можливості без ламання старих

PATCH (1.1.X): фікс
  - виправлено помилку, друкарську
  - уточнено формулювання без зміни поведінки
```

---

## Deprecation Lifecycle

```
Видалення можливості — поступово, не різко:

Stage 1 — DEPRECATE (mark)
  Додай ⚠️ DEPRECATED до секції + причину + альтернативу
  Версія: minor bump

Stage 2 — WARN (одна версія потому)
  Залиш функцію, але CHANGELOG попереджає про видалення

Stage 3 — REMOVE (наступний major)
  Видали. Major bump. CHANGELOG документує.

Ніколи не видаляй те що інші скіли активно використовують
без міграційного шляху.
```

---

## Migration Guides

```markdown
# Migration vX → vY

## Breaking Changes
- [що зламалось]

## Before (vX)
[старий спосіб]

## After (vY)
[новий спосіб]

## Automated Migration
[скрипт якщо можливо]

## Rollback
rollback до vX через snapshot якщо щось не так
```

---

## Breaking Change Protocol

```
Перед major-зміною що зачіпає інші скіли:

1. Знайди ВСІХ споживачів (grep по екосистемі)
   grep -rl "skill-name" /mnt/skills/user/*/SKILL.md

2. Для кожного споживача — план оновлення
3. Покажи MA повний impact (хто постраждає)
4. Оновлюй разом: скіл + усі споживачі в одному батчі
5. Validation-mesh перевіряє що ніщо не зламалось
6. CHANGELOG у кожному зачепленому скілі
```

---

## Snapshot & Rollback

```
Перед КОЖНИМ оновленням (CR10 + guard):
1. Прочитай поточний стан з диску
2. Збережи snapshot → scripts/.snapshots/latest.json
   (з timestamp + hash + версія)
3. Застосуй зміну
4. Якщо проблема → rollback зі snapshot

Тримай останні N snapshot для історії.
```

---

## Skill Retirement (повне видалення)

```
Коли скіл більше не потрібен:

1. Перевір 0 incoming references (ніхто не залежить)
2. Якщо є залежні → спершу мігруй/онови їх
3. Видали з Routing Map (semantic-router)
4. Архівуй (.skill у archive/, не видаляй назавжди)
5. CHANGELOG екосистеми: "retired skill-X, replaced by Y"
6. Major bump екосистеми
```

---

## Author / Branding Consistency

```
Дві групи авторства в екосистемі (свідоме рішення P-09):
- "Prompt Ingeniero Ecosystem" — core 5 (історична група)
- "Melania (Master Administrator)" — пізніші скіли

Це ідентичність, не баг. Не впливає на координацію.
Нові скіли → "Melania (Master Administrator)".
```
