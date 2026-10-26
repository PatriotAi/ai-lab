# Шаблон: базовий рівень якості Next.js-застосунку / Next.js app quality baseline

Чек-лист для нового або успадкованого застосунку на Next.js (App Router), що кличе
зовнішній LLM API. Зібрано з робіт над `PatriotAi/think-like-gpt` (PR #1–#3) і
перехресних стандартів `wikisearchgpt`; висновки — `docs/learnings.md`, 2026-10-26.
Копіюй у опис PR чи issue й відмічай пункти; кожен розділ, крім §8, закінчується рядком «Перевірка».

## 1. Репозиторій
- [ ] `.gitignore`: `node_modules/`, `.next/`, `out/`, `dist/`, `.env*` (крім `.env.example`),
      `*.log`, `.vercel`, `*.tsbuildinfo`, `next-env.d.ts`.
- [ ] `package-lock.json` закомічено; CI ставить залежності через `npm ci`.
- [ ] `.env.example` перелічує **кожну** змінну середовища: обов'язкова чи ні, що буде без неї.
- [ ] `README.md`: встановлення, змінні, таблиця скриптів, **контракт API з усіма HTTP-кодами**,
      безпекові нотатки (ліміти, таймаути, що логується).
- [ ] `package.json` → `engines.node` (Next.js 16 вимагає ≥ 20.9 [C]; Node 20 без підтримки з 2026-04-30 [C]).
- Перевірка: `git ls-files | grep -E '^\.env($|\.)'` порожньо, крім `.env.example`.

## 2. Скрипти й CI
- [ ] `typecheck` = `tsc --noEmit` (TypeScript `strict`, аліас `@/*`).
- [ ] `lint` = `eslint .` з flat config `eslint.config.mjs`, що імпортує
      `eslint-config-next/core-web-vitals` і `eslint-config-next/typescript`.
      Команди `next lint` у Next.js 16 немає [C].
- [ ] `smoke-test` (див. §7) після `build`.
- [ ] CI: `npm ci` → typecheck → lint → build → smoke-test на актуальній LTS Node.
      Дії GitHub — повним SHA коміта, не тегом (правило лабораторії, `scripts/check-action-pinning.sh`).
- Перевірка: локальний прогін усіх чотирьох скриптів дає код 0.

## 3. Залежності
- [ ] Minor/patch — звичайний PR. Major — окремий PR і рішення власника; виняток —
      коли патч безпеки існує лише в новій major-лінії (тоді причина — в описі PR).
- [ ] Гейт: `npm audit --omit=dev` → 0. Залишки в dev-ланцюжку **названо** в PR із причиною,
      чому не експлуатується і що коштує виправлення.
- [ ] Перед major-оновленням — знімки екрана «до» (desktop + mobile), після — «після».
      Анімація входу (framer-motion) дає різницю пікселів без регресії: порівнюй
      обчислений стиль після завершення анімації, а не перший кадр.
- Перевірка: `npm audit --omit=dev` і `npm outdated` у описі PR.

## 4. API-маршрути
- [ ] Вхід: тип, непорожність, ліміт довжини → `400` з людським повідомленням.
- [ ] Секрет перевіряється **до** використання → `503` (ніколи `Bearer undefined`).
- [ ] Зовнішній `fetch` — з `signal: AbortSignal.timeout(…)`; `TimeoutError`/`AbortError` → `504`.
- [ ] Відповідь провайдера `!ok` → `502` із загальним повідомленням; подробиці — лише в серверний лог.
- [ ] Платний ендпоінт — ліміт частоти на клієнта (`429` + `Retry-After`). In-memory ліміт
      діє на кожен інстанс окремо — для глобальної гарантії потрібне спільне сховище.
- [ ] Параметр, який обирає клієнт (модель, тариф), звіряється на сервері з **тим самим**
      allowlist-джерелом, що показує UI; невідоме → значення за замовчуванням, не помилка.
- [ ] URL зовнішнього API — зі змінної середовища з типовим значенням (проксі, Azure).
- Перевірка: smoke-тест має кейс на кожен код (400/429/503) і на ін'єкцію параметра.

## 5. LLM-специфіка
- [ ] Reasoning-моделі OpenAI — o-серія **і** родина `gpt-5*` (`^(o[0-9]|gpt-5)`) — відхиляють
      `max_tokens` (потрібен `max_completion_tokens`) і `temperature` ≠ 1 [C]; тіло запиту
      будується за родиною моделі. Бюджет токенів їм — більший: частину з'їдає приховане
      міркування, і замалий ліміт дає порожню відповідь. Перелік родин звіряй із довідкою
      провайдера: динамічний список приносить нові моделі раніше, ніж їх знає код.
- [ ] Динамічний список моделей (`/v1/models`) — кеш у модулі з TTL **і негативний кеш на
      помилках** (інакше під час збою провайдера кожен запит чекає повний таймаут).
- [ ] Статичний резервний список, коли ключа чи мережі нема; UI показує, що список з резерву.
- [ ] Правила за назвою моделі — **впорядкований масив** регулярок (специфічніше вище:
      `^o[0-9]` перед `mini`), а не ключі об'єкта; крапки екрановано (`4\.1`, `3\.5`).
- Перевірка: юніт або smoke-кейс на o-модель і на недоступний `/v1/models`.

## 6. Клієнт
- [ ] Форма — `<form onSubmit>` + `type="submit"` (Enter, мобільні клавіатури й скрінрідери
      працюють нативно), не `onKeyDown`.
- [ ] Спільні хуки замість копій: `useClipboard` (тост лише після успішного запису,
      таймер прибирається при розмонтуванні) і `useLocalStorage` (нижче).
- [ ] Ніякого `setState` синхронно в `useEffect` для читання зовнішнього стану — це ловить
      `react-hooks/set-state-in-effect`; зовнішнє сховище читається через `useSyncExternalStore`.
- [ ] Кожен таймер в ефекті прибирається в cleanup.
- [ ] Доступність: `label htmlFor`, `role="alert"` для помилок, `aria-live` для статусів,
      `aria-expanded`/`aria-controls` для розкривних панелей.

```ts
// lib/useLocalStorage.ts — SSR-безпечно, синхронно між вкладками, переживає збій сховища
import { useCallback, useSyncExternalStore } from "react";

const listeners = new Set<() => void>();
const memory = new Map<string, string>(); // значення, яке не вдалося записати або прочитати назад
function subscribe(l: () => void) {
  listeners.add(l); window.addEventListener("storage", l);
  return () => { listeners.delete(l); window.removeEventListener("storage", l); };
}
function read(key: string) {
  const unsaved = memory.get(key);
  if (unsaved !== undefined) return unsaved;
  try { return window.localStorage.getItem(key); } catch { return null; }
}
export function useLocalStorage(key: string, fallback: string): [string, (v: string) => void] {
  const stored = useSyncExternalStore(subscribe, () => read(key), () => null);
  const set = useCallback((v: string) => {
    let saved = false;
    try { window.localStorage.setItem(key, v); saved = window.localStorage.getItem(key) === v; } catch {}
    if (saved) memory.delete(key); else memory.set(key, v);
    listeners.forEach((l) => l());
  }, [key]);
  return [stored || fallback, set]; // порожній рядок = значення відсутнє
}
```
- Перевірка (браузер): вибір переживає перезавантаження; видно в іншій вкладці без
  перезавантаження; вибір не губиться, коли `localStorage` недоступний повністю, коли падає
  лише запис і коли падає лише читання.

## 7. Smoke-тест
- [ ] Піднімає **production**-сервер (`next start`) на окремому порту й ганяє контракт API.
- [ ] Відмовляється працювати, якщо порт уже відповідає: інакше тест мовчки перевірить
      сервер, що лишився від минулого прогону.
- [ ] Падає одразу, якщо сервер завершився до готовності (нема збірки, порт зайнятий), і
      показує його stderr.
- [ ] Прибирає **всю групу процесів**: `npx next start` запускає сервер у дочірньому
      процесі з назвою `next-server`, і той переживає `kill()` обгортки `npx`.

```js
const server = spawn("npx", ["next", "start", "-p", String(PORT)], {
  stdio: ["ignore", "ignore", "pipe"],
  detached: true, // своя група процесів
});
// … наприкінці:
try { process.kill(-server.pid, "SIGTERM"); } catch { server.kill(); }
```
- Перевірка (на зламаному стані теж): зайнятий порт → падіння з поясненням; без `.next` →
  падіння за секунди; чистий прогін → код 0 і жодного `next-server` після.
  Обережно з `pkill -f next-server` у тій самій оболонці: шаблон збігається з власним
  командним рядком оболонки й вбиває її; бери `pgrep -f '^next-server'`.

## 8. Перед PR
- [ ] typecheck · lint · build · smoke-test — код 0, вивід у описі PR.
- [ ] Браузерна перевірка змінених сценаріїв (Playwright: desktop + mobile).
- [ ] Рев'ю диффу (`/code-review`) і безпекове рев'ю (`/security-review`); кожну знахідку
      або виправлено, або в PR сказано, чому ні.
- [ ] Відомі залишки названо в PR (що, чому не зараз, чиє рішення).
