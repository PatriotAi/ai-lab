# Routing Optimization

## Decision Caching

Кешуй рішення для повторюваних патернів намірів:

```javascript
const routeCache = new Map();

function routeWithCache(intent) {
  const key = normalize(intent);  // lowercase, trim, remove fillers
  if (routeCache.has(key)) {
    return { ...routeCache.get(key), cached: true };
  }
  const decision = computeRoute(intent);
  routeCache.set(key, decision);
  return decision;
}
```

Однакові запити → миттєвий роут без повторного аналізу. Економія на типових командах.

---

## Fallback Chains

```
Якщо primary скіл не дав результату → fallback ланцюг:

route("складна задача"):
  1. try: specialized-skill   (найкращий для задачі)
  2. fallback: ai-core-runtime (загальний оркестратор)
  3. fallback: пряма відповідь (без скілів)

Ніколи не залишай користувача без відповіді — завжди є кінцевий fallback.
```

---

## Context-Aware Routing

Враховуй історію розмови, не лише поточне повідомлення:

```
Сигнали з контексту:
- Попередній скіл був n8n-orchestrator + "додай ще крок"
  → залишайся в n8n-orchestrator (продовження)
- Згадувався проект X раніше + "продовжимо"
  → continuation-memory спершу (відновити стан)
- Користувач у режимі дебагу + нова помилка
  → той самий debug-скіл, не перемикайся
```

Контекст важливіший за ключові слова: "додай крок" саме по собі неоднозначне, але після n8n-задачі — очевидне.

---

## Short-Circuit для Точних Патернів

```
Деякі запити мають однозначний маршрут — не витрачай аналіз:

EXACT_ROUTES = {
  /^\/skill-creator/        → skill-creation-guide
  /^аудит скіл/             → skill-ecosystem-auditor
  /notebooklm\.google\.com/ → notebooklm-connector
  /^STENO:/                 → continuation-memory
}

Match → миттєвий роут, пропусти scoring.
```

---

## Learning from Corrections

```
Коли користувач виправляє маршрут:
"ні, це не n8n, це звичайний код"

→ Зафіксуй: цей патерн намірів НЕ → n8n-orchestrator
→ Наступного разу для схожого формулювання знизь score n8n
→ (у межах сесії; для постійного — запис у memory_user_edits)
```

---

## Multi-Skill Dependency Resolution

```
Коли скіли мають залежності — впорядкуй виконання:

Задача: "побудуй валідований workflow і збережи стан"
Залежності:
  validation-mesh ПОТРЕБУЄ output від n8n-orchestrator
  continuation-memory НЕ залежить ні від чого

Топологічне впорядкування:
  1. n8n-orchestrator     (немає вхідних залежностей)
  2. validation-mesh      (потребує #1)
  ║ continuation-memory   (паралельно, незалежний)
```
