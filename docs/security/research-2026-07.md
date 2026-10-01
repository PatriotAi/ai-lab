# Глибоке дослідження: безпека агентних AI-систем — липень 2026

> **Метод.** Шість паралельних збирачів на дешевшому класі моделей (рецепт
> `rlm-harness` → Deep Research), синтез — оркестратором. Кожен збирач отримав
> вимогу: атрибуція кожного твердження, теги доказовості, окрема секція
> «не вдалося підтвердити», заборона вигаданих джерел.
>
> **Чесна межа всього документа (важлива).** Мережева політика середовища
> повертала **HTTP 403** для великої частини первинних джерел — серед них
> `genai.owasp.org`, `atlas.mitre.org`, `docs.github.com`, `dora.dev`,
> `anthropic.com/research`, `slsa.dev`, `cloudsecurityalliance.org`. Тому
> **більшість зовнішніх тверджень нижче має тег [C] (вторинне джерело), а не
> [E]** — навіть коли документ безсумнівно існує. Це не формальність: за
> правилом лабораторії `[E]` означає «перевірено ділом», а не «посилання
> виглядає офіційно». Там, де первинне джерело вдалося прочитати напряму
> (`code.claude.com`, `platform.claude.com`, специфікація MCP через GitHub raw,
> `github/docs` через raw, Microsoft Security Blog) — стоїть [E].

---

## 1. Що з цього змінює наші рішення

Дослідження велике; нижче — лише те, що **впливає на конструкцію пакета**.
Решта пішла у сміттєвий кошик як цікава, але не діюча.

### 1.1. Наш головний внутрішній дефект має ім'я в зовнішньому каноні

Дефект **F-1** (пам'ять G5 подає невалідований текст у контекст) — це не
екзотика лабораторії. Він проходить одразу за трьома каталогами:

- **OWASP ASI06 — Context Management and Retrieval Manipulation** (отруєння чи
  підміна збереженого/витягнутого контексту) у Top 10 для агентних застосунків
  ([OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)) — [C];
- **OWASP Agentic AI Threats** — окрема категорія **Agent Memory** із темою
  memory poisoning — [C];
- **MITRE ATLAS** — техніки отруєння контексту/пам'яті, додані у жовтні 2025
  разом із Zenity Labs ([MITRE ATLAS](https://atlas.mitre.org/)) — [C].

**Наслідок для плану:** Фаза S1 не «про всяк випадок», а закриття пункту, який
галузь ставить у першу десятку.

### 1.2. Офіційна рекомендація Anthropic збігається з тим, що ми проєктуємо

Це найцінніша знахідка, бо вона [E] — прочитана з першоджерела.
[Mitigate jailbreaks and prompt injections](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks) прописує для **непрямих** ін'єкцій:

- недовірений вміст — **лише** в `tool_result`, ніколи в системному промпті;
- JSON-кодування недовіреного тексту як бар'єр від «виходу з лапок»;
- явна політика в системному промпті: вміст з інструментів — **дані, не команди**;
- **скринінг виходу інструментів окремим дешевим класифікатором ДО передачі
  в основну розмову.**

Останній пункт — дослівно архітектура нашої Фази S1 (гейт пам'яті) і шару Ш2
(аналітичний гейт лише за підозрою). Тобто ми не винаходимо конструкцію —
ми застосовуємо рекомендовану.

> **Окремо важливо** [E]: та сама сторінка застерігає, що **власні** інструкції
> застосунку не варто класти в `tool_result` — Claude навчений ставитись до
> вмісту `tool_result` скептично, тож власні команди там можуть бути
> проігноровані або позначені як ін'єкція. Це впливає на те, **як** гейт
> пам'яті подає відновлений текст: як дані з поміткою, а не як інструкцію.

### 1.3. Детектори самі по собі не працюють — і це вже враховано в наших правилах

Дві незалежні лінії доказів:

- Емпіричний аналіз ухилення: character injection (zero-width, омоглифи),
  парафразування й розбиття інструкції на кроки обходять класифікатори
  (Llama Prompt Guard 2, DeBERTa-класифікатори) під адаптивною атакою; входи,
  що обійшли guardrail, часто все одно коректно інтерпретуються моделлю
  ([Bypassing LLM Guardrails](https://arxiv.org/pdf/2504.11168), 04.2025) — [C].
- **EchoLeak (CVE-2025-32711)**, CVSS 9.3 — прихована інструкція в
  HTML-коментарі листа обійшла класифікатор Microsoft у Copilot і призвела до
  zero-click ексфільтрації ([розбір Sentra/Aim Security](https://sentra.io/blog/copilot-echoleak-prompt-injection), 06.2025) — [C].

**Наслідок:** формулювання `scan-external-input.py` про себе («тріаж, а не
бар'єр»; «чисто ≠ безпечно») **підтверджується зовнішнім каноном**. Це не
скромність — це точна самооцінка. Гейт пам'яті (S1) успадковує ту саму межу.

### 1.4. «Летальна тріада» має незалежного двійника

Simon Willison сформулював **lethal trifecta** (приватні дані + недовірений
вміст + канал назовні) 16.06.2025 ([джерело](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)) — [C].
Meta у листопаді 2025 незалежно опублікувала **Agents Rule of Two** — по суті
той самий принцип ([Meta AI](https://ai.meta.com/blog/practical-ai-agent-security/)) — [C].
Microsoft посилається на нього у розборі інциденту з Claude Code GitHub Action
([Microsoft Security Blog, 05.06.2026](https://www.microsoft.com/en-us/security/blog/2026/06/05/securing-ci-cd-in-agentic-world-claude-code-github-action-case/)) — [E].

**Наслідок:** розділ §6 нашого протоколу («Розрив летальної тріади») спирається
на принцип, який дві великі організації вивели незалежно. Змінювати його не треба.

### 1.5. Механіка блокування дій — підтверджена первинним джерелом

Найважливіше [E] для Фази S2, прочитане з офіційної документації:

- **Хук `PreToolUse` може заблокувати виклик** — кодом виходу `2` (тоді `stderr`
  повертається моделі як причина) або JSON-виходом
  `hookSpecificOutput.permissionDecision` зі значенням `"deny"` та полем
  `permissionDecisionReason` ([Hooks reference](https://code.claude.com/docs/en/hooks.md)).
- **Порядок дозволів — `deny → ask → allow`**, перший збіг вирішує, і широке
  `deny`-правило **не можна перебити** вужчим `allow`
  ([Configure permissions](https://code.claude.com/docs/en/permissions)).
- Рішення хука **не обходять** правила дозволів: `deny` у налаштуваннях блокує
  незалежно від того, що повернув хук.
- Подій життєвого циклу значно більше, ніж ми використовуємо: крім
  `SessionStart`/`Stop` є `PreToolUse`, `PostToolUse`, `PermissionRequest`,
  `PermissionDenied`, `UserPromptSubmit`, `PreCompact`/`PostCompact`,
  `SubagentStart`/`SubagentStop` та інші.

**Наслідок:** Фаза S2 технічно реалізовна саме так, як спроєктована.

### 1.6. Дозволи — не те саме, що ізоляція (і межа ізоляції вужча, ніж здається)

[E], офіційна документація ([Sandboxing](https://code.claude.com/docs/en/sandboxing.md),
[Choose a sandbox environment](https://code.claude.com/docs/en/sandbox-environments)):

- Дозволи зупиняють **спробу**; пісочниця зупиняє **результат** спроби, навіть
  якщо ін'єкція переконала модель спробувати.
- **Вбудована пісочниця ізолює лише Bash-підпроцеси.** `Read`/`Edit`/`Write`,
  MCP-сервери та **хуки** працюють **поза** її межею, напряму на хості.
- Мережевий проксі за замовчуванням **не інспектує TLS**, тож надто широкий
  дозволений домен (напр. `github.com`) відкриває шлях для domain fronting.
- Документація прямо каже: **жодна система не імунна до всіх атак.**

**Наслідок для нас:** ми працюємо в керованому Anthropic хмарному середовищі
з ізольованою ВМ і обмеженою мережею — це вже сильніша ізоляція, ніж локальна
пісочниця. Але **хук-гейт (S2) сам виконується поза пісочницею**, тому його код
має бути таким же простим і перевіреним, як решта автоматизацій лабораторії.

### 1.7. Нова вимога до гейта згоди, якої в наших документах не було

**GhostApproval** (розкрито 08.07.2026, Wiz Research) — атака симлінками проти
діалогу підтвердження одразу в шести кодових асистентах: файл у репозиторії,
названий безпечно (напр. `project_settings.json`), насправді є симлінком на
`~/.ssh` чи конфіг оболонки. Людина в діалозі бачить **безпечну назву**, тоді як
агент уже «знає», що це насправді
([The Hacker News](https://thehackernews.com/2026/07/ghostapproval-symlink-flaws-could-let.html),
[The Register](https://www.theregister.com/security/2026/07/08/bug-in-top-ai-coding-agents-shows-that-unix-era-security-headaches-never-really-die/5268025)) — [C].

**Наслідок — новий пункт у Фазу S2:** гейт рівня R4 зобов'язаний **розрізати
симлінк до ухвалення рішення** і показувати **реальний цільовий шлях**, а не
той, що написаний у виклику. Без цього людська згода дається на інший об'єкт,
ніж той, що буде змінено.

### 1.8. Економіка підтверджує конструкцію каскаду цифрами

Три незалежні архітектури сходяться на тому самому: **детермінований префільтр
відсіює ~95–96 % обсягу до дорогого етапу** (Nextron: до LLM-тріажу доходить
~4 % артефактів; Revelio: статичний фільтр знижує сукупну вартість аналізу
понад 96 %; Semgrep: гібрид дає 3.5× більше справжніх знахідок при на 19 %
нижчій вартості за одну — усе [C], первинні сторінки повернули 403).

Офіційні цифри Anthropic, прочитані напряму — [E]
([Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching),
[Pricing](https://platform.claude.com/docs/en/about-claude/pricing)):

- читання з кешу — **0.1× ціни входу**; запис — 1.25× (5 хв) або 2× (1 год);
- окупність кешу — **після 1 читання** (5-хв TTL) або **2 читань** (1-год TTL);
- **Batch API — гарантовані −50 %** на вхід і вихід; знижки **стекуються**
  з кешуванням.

Маршрутизація за класами моделей: FrugalGPT — економія до 98 % за тієї ж якості
([arXiv 2305.05176](https://arxiv.org/abs/2305.05176)) — [E]; RouteLLM — 85 % на
MT-Bench, 45 % на MMLU, 35 % на GSM8K ([arXiv 2406.18665](https://arxiv.org/abs/2406.18665)) — [E].

> ⚠️ **Застереження, яке рятує від помилки.** Задокументований production-кейс
> (SaaS, ~4 млн MAU): жорстка **статична** маршрутизація за вартістю тихо
> зламала продукт на довгому хвості складних випадків; рекомендація авторів —
> **ескалація-на-невпевненості**, а не фіксовані правила
> ([Towards Data Science, 2026](https://towardsdatascience.com/we-built-a-routing-layer-to-cut-our-ai-costs-it-broke-the-product/)) — [C].
> Це прямо лягає у наш шар Ш2: він вмикається **за підозрою**, а не за
> фіксованим розкладом.

### 1.9. Модель «прогнати всі гейти на кожну зміну» доказово шкідлива

Розгорнуто в `docs/security/PLAN.md` §I.1. Ключові опори: ставка флакі-тестів
Google (**~1.5 % прогонів нестабільні; 84 % переходів pass→fail — флакі, а не
баги**, [Google Testing Blog](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html)) — [C];
емпірика alert fatigue ([arXiv 2203.00483](https://arxiv.org/pdf/2203.00483)) — [C];
Meta ловить **>99.9 % регресій, ганяючи ~третину** тестів
([arXiv 1810.05286](https://arxiv.org/abs/1810.05286)) — [E].

---

## 2. Що з цього **не** беремо — і чому

Чесний перелік відкинутого важливіший за перелік узятого.

| Ідея з вхідних документів / канону | Чому не беремо |
|---|---|
| **Formal Verification Engine**, що автоматично верифікує довільний код | Такого інструмента не існує. Формальна верифікація (TLA+, Alloy, Dafny, CBMC) потребує **ручного** опису інваріантів для **вибраної** ділянки. Уся доказова база (AWS, CACM 2015) — про команди, не про соло-розробника |
| **Architecture Gate** як автоматичний PASS/FAIL | Архітектурна якість не зводиться до машинної метрики; максимум — лінтери залежностей |
| **Requirements Gate** зі звіркою коду проти вимог | Нерозв'язана дослідницька задача (formal requirements traceability), не готовий інструмент |
| **Відсоток покриття як гейт** | Зв'язок покриття з дефектністю емпірично слабкий і **суперечливий**: [Inozemtseva & Holmes ICSE 2014](https://www.cs.ubc.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf) і [Kochhar et al.](https://ieeexplore.ieee.org/document/8031982/) не знаходять значущого зв'язку; [SANER 2015](http://www.mysmu.edu/faculty/davidlo/papers/saner15-coverage.pdf) на реальних багах знаходить. Консенсусу немає → гейтом бути не може |
| **ISO/IEC 42001 сертифікація, CSA STAR for AI** | Платні зовнішні аудитори; сертифікат нікому пред'являти. Чистий оверхед |
| **PASTA** (7-етапна threat-модель) | Compliance-важка; для однієї людини — оверхед. Беремо STRIDE у мініатюрі |
| **Повна модель MAESTRO** (CSA, 7 шарів) | Забагато апарату; беремо лише **погляд** «перевір кожен шар» як чек-лист |
| **EU AI Act відповідність** | Ст. 2 виключає дослідницьку діяльність до виведення на ринок і особисте непрофесійне використання. Стає релевантним лише коли щось із `projects/` піде користувачам у ЄС — [C] |
| **Окрема інфраструктура спостережуваності** (метрики, трейси, дашборди з Master.pdf §10) | Для однієї людини це побудова заводу заради однієї деталі. Замінюємо журналом рішень (S2.3) |

---

## 3. Знахідки, що стосуються нашого репозиторію напряму

### 3.1. GitHub Actions закріплені **тегами**, а не хешами комітів

Перевірено на диску (2026-07-27): усі 19 викликів `uses:` у чотирьох воркфлоу
використовують рухомі теги — `actions/checkout@v7`, `actions/setup-python@v6`,
`gitleaks/gitleaks-action@v3`, `github/codeql-action/upload-sarif@v4` тощо.

Чому це важливо: компрометація `tj-actions/changed-files`
(**CVE-2025-30066**, ~03.2025) зачепила близько **23 000 репозиторіїв** —
зловмисник із доступом на запис до популярної дії змусив її логувати секрети
збірок у **публічні** логи Actions ([GitHub Advisory](https://github.com/advisories/ghsa-mrrh-fwg8-r2c3)) — [C].
Офіційна позиція GitHub: закріплення на **повний SHA коміту — єдиний спосіб**
використати дію як незмінний реліз — [C].

**Чесний контекст, а не паніка:** ризик у нас нижчий за середній, бо
`permissions: contents: read` угорі кожного воркфлоу, `pull_request_target` не
використовується, а секрети в Actions практично не задіяні. Автор воркфлоу вже
свідомий цього класу — у `security.yml` є коментар про supply-chain-інцидент
Trivy і свідоме закріплення на `v0.36.0`. Це **посилення**, а не виправлення
недбалості. → пункт **F-5** у план.

### 3.2. `dependency-review-action` на приватному репозиторії, ймовірно, не дає сигналу

`.github/workflows/dependencies.yml` викликає `actions/dependency-review-action@v5`
із `continue-on-error: true`. За дослідженням, на **приватних** репозиторіях ця
дія вимагає GitHub Advanced Security ([issue проєкту #919](https://github.com/actions/dependency-review-action/issues/919)) — [C].
З `continue-on-error` будь-яка відмова **проковтується мовчки**.

Тобто це ще один випадок класу F-2: контроль **задекларований**, сигналу
**не дає**. Безкоштовна заміна, що працює незалежно від плану — **osv-scanner**
(Google, база OSV.dev) — [C]. → пункт **F-6** у план.

> `[C]`, не `[E]`: перевірити це ділом можна лише прогоном у самому GitHub,
> чого з цієї сесії я не робив. Формулювання свідомо звужене до «ймовірно».

### 3.3. Захист гілок на приватному безкоштовному плані — **технічно недоступний**

Перевірено первинним джерелом через дзеркало офіційного репозиторію документації
([github/docs, protected-branches.md](https://github.com/github/docs/blob/main/data/reusables/gated-features/protected-branches.md),
[repo-rules.md](https://github.com/github/docs/blob/main/data/reusables/gated-features/repo-rules.md)) — [E]:
класичні branch protection і rulesets на приватних репозиторіях вимагають
щонайменше GitHub Pro; push rulesets — Team/GHEC.

**Це підтверджує рішення лабораторії «варіант C» (2026-07-13)** — м'який
governance плюс покриття на рівні CI. Рішення було не компромісом від ліні, а
єдиним доступним варіантом. Змінювати нічого не треба; варто лише знати ціну
альтернативи: **GitHub Pro — $4/міс** — [C].

### 3.4. Що вже закрито краще, ніж у каноні

- Клас атаки «comment and control» (розкрито 04.2026; CVSS 9.4; підтверджено
  трьома вендорами) **до нас не застосовний**: AI-агент у GitHub Actions не
  запускається — і протокол це фіксує явно.
- Цілісність навичок через `MANIFEST.json` із хешами — це саме та практика, яку
  дослідження називає **найкращою доступною** за відсутності усталеного
  стандарту: галузь **не має** визнаного BOM-формату для промптів/навичок
  (CycloneDX ML-BOM і SPDX AI Profile описують **моделі й датасети**, не
  навички), тому самостійний хеш-маніфест, звірюваний у CI, — рекомендований
  шлях, а не милиця — [C].

---

## 4. Відкриті питання (чесно не закриті)

1. ~~Чи справді `dependency-review-action` мовчки падає на цьому репозиторії~~
   **ЗАКРИТО 2026-07-27 логом CI** (PR #48, job `90074416308`… точніше
   `90004989688`): крок дав `##[error]Dependency review is not supported on this
   repository. Please ensure that Dependency graph is enabled along with GitHub
   Advanced Security`, а джоба відзвітувала `success` через `continue-on-error`.
   Додатковий факт, що змінив виправлення: у репозиторії **немає жодного файлу
   залежностей**, тож планована заміна на `osv-scanner` була б тим самим театром.
   Крок прибрано; замість нього — перевірка закріплення дій GitHub.
2. Точні безкоштовні ліміти хвилин GitHub Actions для приватних репозиторіїв —
   усі збирачі отримали 403 на офіційній сторінці білінгу; цифри (2000/міс на
   Free) лишаються [C].
3. ~~Чи вплинув supply-chain-інцидент Trivy на версію `v0.36.0`~~
   **ЗАКРИТО 2026-07-27 — advisory прочитано.** `GHSA-69fq-xp46-6x23` /
   **CVE-2026-33634**: `aquasecurity/trivy-action` уражені версії **< 0.35.0**,
   виправлено в **0.35.0**; `aquasecurity/setup-trivy` — **< 0.2.6**, виправлено
   в 0.2.6; Go-модуль `trivy` — уражена 0.69.4, патча немає (відкат до 0.69.2/0.69.3).
   **Ми на `trivy-action` v0.36.0 → не зачеплені**; `setup-trivy` і Go-модуль не
   використовуються (перевірено grep по воркфлоу).
   **Чому це варто прочитати повністю:** 19.03.2026 атакувальник із викраденими
   обліковими даними опублікував шкідливий реліз і **force-push'нув 76 із 77 тегів
   версій** `trivy-action` на код-крадій, що витягав секрети з оточення GitHub
   Actions. Тобто той самий вендор, чию дію ми використовуємо, пережив рівно той
   сценарій, від якого рятує закріплення хешем коміта — і це найсильніший
   аргумент за рішення S3½, який лише можна було отримати.
4. Чи варто підписувати коміти через `gitsign` — технічно безкоштовно й працює
   на приватних репозиторіях, але keyless-підпис пише метадані (власник, назва
   репозиторію) у **публічний** прозорий лог Rekor. Для приватного репозиторію
   це витік метаданих. **Рішення власника, не автоматичне.**

---

## 5. Повний перелік джерел

Стандарти й рамки: [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) ·
[NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) ·
[NIST SSDF](https://csrc.nist.gov/projects/ssdf) ·
[SP 800-218A](https://csrc.nist.gov/pubs/sp/800/218/a/final) ·
[ISO/IEC 42001](https://www.iso.org/standard/42001) ·
[EU AI Act, ст. 2](https://artificialintelligenceact.eu/article/2/) ·
[CSA MAESTRO](https://cloudsecurityalliance.org/blog/2025/02/06/agentic-ai-threat-modeling-framework-maestro) ·
[CSA AI Security Maturity Model](https://cloudsecurityalliance.org/artifacts/ai-security-maturity-model)

Загрози: [OWASP Top 10 for LLM Apps 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/) ·
[OWASP Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/) ·
[OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) ·
[MITRE ATLAS](https://atlas.mitre.org/) ·
[lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) ·
[Agents Rule of Two](https://ai.meta.com/blog/practical-ai-agent-security/) ·
[Bypassing LLM Guardrails](https://arxiv.org/pdf/2504.11168) ·
[MCPTox](https://arxiv.org/pdf/2508.14925)

Інциденти: [EchoLeak](https://sentra.io/blog/copilot-echoleak-prompt-injection) ·
[comment and control](https://www.securityweek.com/claude-code-gemini-cli-github-copilot-agents-vulnerable-to-prompt-injection-via-comments/) ·
[Microsoft розбір](https://www.microsoft.com/en-us/security/blog/2026/06/05/securing-ci-cd-in-agentic-world-claude-code-github-action-case/) ·
[CVE-2025-30066 tj-actions](https://github.com/advisories/ghsa-mrrh-fwg8-r2c3) ·
[postmark-mcp](https://postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package) ·
[GhostApproval](https://thehackernews.com/2026/07/ghostapproval-symlink-flaws-could-let.html) ·
[DuneSlide](https://www.catonetworks.com/blog/duneslide-two-critical-rce-vulnerabilities/)

Механіка: [Claude Code — Security](https://code.claude.com/docs/en/security) ·
[Permissions](https://code.claude.com/docs/en/permissions) ·
[Hooks](https://code.claude.com/docs/en/hooks.md) ·
[Sandboxing](https://code.claude.com/docs/en/sandboxing.md) ·
[Sandbox environments](https://code.claude.com/docs/en/sandbox-environments) ·
[Mitigate jailbreaks](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks) ·
[MCP Authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)

Інженерія та економіка: [Flaky Tests at Google](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html) ·
[Test flakiness survey](https://arxiv.org/pdf/2203.00483) ·
[Predictive Test Selection](https://arxiv.org/abs/1810.05286) ·
[State of Mutation Testing at Google](https://research.google/pubs/state-of-mutation-testing-at-google/) ·
[Coverage is not strongly correlated](https://www.cs.ubc.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf) ·
[Property-based testing eval](https://dl.acm.org/doi/10.1145/3764068) ·
[AWS formal methods](https://cacm.acm.org/research/how-amazon-web-services-uses-formal-methods/) ·
[FrugalGPT](https://arxiv.org/abs/2305.05176) ·
[RouteLLM](https://arxiv.org/abs/2406.18665) ·
[Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) ·
[Pricing](https://platform.claude.com/docs/en/about-claude/pricing) ·
[GitHub Actions pricing 2026](https://github.com/resources/insights/2026-pricing-changes-for-github-actions)

Ланцюг постачання: [SLSA v1.2](https://slsa.dev/blog/2025/11/announce-slsa-v1.2) ·
[GitHub attestations — gating](https://github.com/github/docs/blob/main/data/reusables/gated-features/attestations.md) ·
[branch protection — gating](https://github.com/github/docs/blob/main/data/reusables/gated-features/protected-branches.md) ·
[secret scanning — gating](https://github.com/github/docs/blob/main/data/reusables/gated-features/secret-scanning.md) ·
[CycloneDX ML-BOM](https://cyclonedx.org/capabilities/mlbom/) ·
[cosign sign-blob](https://docs.sigstore.dev/cosign/signing/signing_with_blobs/) ·
[gitsign](https://docs.sigstore.dev/cosign/signing/gitsign/)
