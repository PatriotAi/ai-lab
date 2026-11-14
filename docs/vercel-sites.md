# Реєстр сайтів на Vercel

Шар **лише про Vercel**: які проєкти там живуть, з якою версією Node збираються, який
прод-деплой зараз віддається і що блокує наступний. Сесії не мають прямого зв'язку між
собою, тому стан тримаємо в GitHub, а не в повідомленнях.

**Знімок від 2026-11-14**, звірений конектором Vercel (`get_project`, `list_deployments`,
`list_deployment_events`, `list_deployment_aliases`) і `git ls-remote` + `package.json` у `main`
публічних репо. **Ризик застарівання:** таблицю ніщо не оновлює й не перевіряє автоматично —
перед роботою над сайтом звір свій рядок конектором наново, а після зміни онови дату.

Теги — за `CLAUDE.md` §10: **[E]** перевірено, є вказівник; **[C]** обґрунтовано, машинно не
перевірено; **[S]** гіпотеза.

## Що вже робить `main` — тут не дублюємо

| Потреба | Де живе | Що там є |
|---|---|---|
| Стан репозиторіїв, CI, відкриті PR | `automations/repo-monitor/` (щоденний прогін, приватна сторінка) | правила RH01–RH14, CI на гілці за замовчуванням, простій PR |
| Перевірка на кожне заливання | `templates/ci/repo-check.yml` → `.github/workflows/repo-check.yml` у репо сайтів | gitleaks, встановлення, lint/build/test |
| Паралельна незлита робота інших сесій | SessionStart-радар `scripts/check-main-drift.py --inflight` | карта гілок, що чіпають ті самі файли |
| Правила сесії (незворотне, merge-not-replace, зовнішній вхід) | `CLAUDE.md`, «Робочий стандарт щозапиту» | чинні для будь-якої сесії, що підключила ai-lab |

**Чого жоден із них не бачить:** налаштувань і деплоїв самого Vercel. `repo-check` збирає на
`node-version: lts/*` [E: `templates/ci/repo-check.yml`], а Vercel — на версії з налаштувань
проєкту, якщо в `package.json` немає `engines.node`. Тому зелений CI не доводить, що збереться
прод: 2026-11-03 злиття PR #4 у `wikisearchgpt` пройшло з зеленим CI [E: `docs/WINDOWS.md`, W-35],
а прод-збірка того ж коміту впала [E: деплой `dpl_Ce3JhLAdq3iL4k144a8JCAWs76Cc`].

## Реєстр (знімок 2026-11-14)

| Проєкт Vercel | Репозиторій | Прод-адреса | Node у налаштуваннях | Що віддає прод | Що блокує |
|---|---|---|---|---|---|
| wikisearchgpt | [`PatriotAi/wikisearchgpt`](https://github.com/PatriotAi/wikisearchgpt) (публічний) | https://wikisearchgpt.vercel.app [E: аліас прод-деплою] | `20.x` [E: `get_project`] | збірку `81eb576` від **2026-07-04** [E: `dpl_AsccXD3wu5vahXxhFb5J9YNEZFCX`, останній READY з `target: production`] | `main` = `b4ee85f` [E: `git ls-remote`]; його прод-збірка 2026-11-03 впала на Node 20.x [E: лог `dpl_Ce3JhLAdq3iL4k144a8JCAWs76Cc`]. У `package.json` на `main` немає `engines` [E: `package.json` @ `b4ee85f`]. **PR [#3](https://github.com/PatriotAi/wikisearchgpt/pull/3) відкритий**, ставить `engines.node: "24.x"`; прев'ю його голови `8cd5111` (2026-11-06) — READY [E: `dpl_7TMLafEEVdBtz6YoBg9TNvbC81rt`] |
| wikigpt | [`PatriotAi/wikigpt`](https://github.com/PatriotAi/wikigpt) (публічний) | https://wikigpt-ebon.vercel.app [E: аліас прод-деплою] | `20.x` [E: `get_project`] | збірку `4f13cbd` від **2026-07-05** [E: `dpl_F2swXybBSWNgdZUHLxpJ961zkRgd`, останній READY з `target: production`] | `main` = `2789875` [E: `git ls-remote`]; прод-збірка 2026-11-03 впала з тієї ж причини [E: лог `dpl_4yyB62JuYqMT4ABEaEdR7KCu2fZg`]; стан CI того злиття не прочитано (W-35). У `package.json` на `main` немає `engines` [E: `package.json` @ `2789875`]. **PR [#3](https://github.com/PatriotAi/wikigpt/pull/3) відкритий**, ставить `engines.node: "24.x"`; прев'ю `3b89fa1` (2026-11-07) — READY [E: `dpl_HKapXDAWwTiuobTdE5psVR6DD3hq`] |
| think-like-gpt | приватний репозиторій | — | — | — | Подробиці приватного проєкту в публічному ai-lab не публікуємо. Сесія цього сайту звіряє його з базовою лінією конектором сама |

Рядок логу обох упалих збірок дослівно: `Node.js Version "20.x" is discontinued and must be
upgraded. Please set Node.js Version to 26.x in your Project Settings to use Node.js 26.`

## Спільна базова лінія (мінімум для кожного сайту)

1. `package.json` → `engines.node` задано явно: тоді версію задає репо, а не налаштування
   Vercel. Node 20.x Vercel не збирає [E: лог вище]; `24.x` збирається [E: прев'ю обох PR #3];
   Vercel радить уже `26.x` [E: лог вище]. Перехід на 26 — окреме рішення [S].
2. Залежності без вразливостей рівня high (`npm audit`). На вразливостях ніщо автоматичне не
   падає: у `templates/ci/repo-check.yml` окремого кроку `npm audit` немає, серед правил
   RH01–RH14 у `scripts/repo-health.py` такого теж немає [E: обидва файли] — перевіряє сесія сайту.
3. `npm run build` проходить; маршрути SPA після `vite preview` віддають 200.
4. SPA з `BrowserRouter` має `vercel.json` з rewrite на `/` (у `main` обох публічних репо файл є
   [E: `b4ee85f`, `2789875`]).
5. `.gitignore`, `package-lock.json`, `.env.example`; секрети — лише через env.

## Черга дій

| # | Проєкт | Дія | Хто |
|---|---|---|---|
| 1 | wikisearchgpt | Рішення про злиття PR #3 → після нього перевірити, що прод-деплой `main` став READY | власник; перевірка — будь-яка сесія |
| 2 | wikigpt | Те саме для PR #3 | власник; перевірка — будь-яка сесія |
| 3 | think-like-gpt | Звірити з базовою лінією (`engines.node` проти налаштувань проєкту) | сесія think-like-gpt |
| 4 | шаблон CI | Корінь розбіжності: `repo-check` збирає на `lts/*`, а не на версії з `engines.node`. Кандидат — `actions/setup-node` з `node-version-file: package.json`, щоб CI брав ту саму версію, що й Vercel [C] | рішення власника; окремий PR у `templates/ci/` |

## Як сесії працювати із сайтом

1. Підключи `patriotai/ai-lab` додатковим джерелом: тоді діють `CLAUDE.md` і SessionStart-радар.
2. Звір свій рядок реєстру конектором Vercel (`get_project`, `list_deployments`) — це знімок.
3. Після зміни, що стосується Vercel (версія Node, домени, налаштування проєкту, прод-деплой), —
   онови рядок і дату знімка малим docs-PR в ai-lab. Нова знахідка → `docs/learnings.md`.

Стартовий промпт для сесії сайту:

```
Підключи patriotai/ai-lab додатковим джерелом. Прочитай docs/vercel-sites.md і звір
мій рядок конектором Vercel. Виконай мої пункти черги. Нічого не видаляй і не
переписуй; merge не виконуй. Наприкінці онови рядок реєстру й дату знімка.
```
