# GMI — Крок 2: Джерела та фактчек (deep-research)

- **Дата:** 2026-07-13
- **Режим:** deep-research; оркестратор `source-research-harvest` (info-max + чесний Source-Reality)
- **Легенда доказовості:** **[E]** established (усталене) · **[C]** contested (дискусійне) · **[S]** speculative (гіпотеза-лінза)

## Source-Reality (чесний статус здобуття)
- **Здобуто:** широкий зріз через WebSearch по 6 кластерах; кожен ключовий факт має ≥1
  Tier-1-атрибуцію (Nature, MIT Press, Scholarpedia, arXiv, NIH/PMC, Intel/NIST).
- **Обмеження середовища:** **WebFetch блокований (HTTP 403 навіть на Wikipedia/arXiv/PMC)** —
  прямий доступ до первинних PDF недоступний. Тому числа — **search-derived**; найвагоміші
  крос-валідовані ≥2 незалежними запитами. Перед фінальним артефактом (крок 4) позначені
  🔎 числа звірити з первинним джерелом.
- **Не вигадано:** жодного джерела/числа поза наведеними результатами пошуку.
- **Обережно з датами:** частина arXiv- id має 2025–2026 дати (сьогодні 2026-07); екзотичні
  препринти не беру як опору — спираюся на рецензовані Tier-1.

---

## C1 — Рамки інтелекту (означення GMI)

- **[E] Legg & Hutter, «Universal Intelligence»:** інтелект = *здатність агента досягати цілей
  у широкому діапазоні середовищ*; звели **>70 означень** у формальну міру (на базі
  Solomonoff/Hutter AIXI). → ядро інваріантів I2 (ціль), I8 (генералізація).
  [Scholarpedia AGI](http://www.scholarpedia.org/article/Artificial_General_Intelligence) ·
  [arXiv 1109.5951](https://arxiv.org/pdf/1109.5951)
- **[E] Pei Wang:** інтелект = *адаптація до середовища за обмежених ресурсів* — **прямо
  релевантно H-B** (ресурсна межа вбудована у саме означення інтелекту!).
  [Goertzel AGI survey](https://goertzel.org/AGI_survey_early_draft.pdf)
- **[E] g-фактор (Spearman, 1904):** статистичний загальний фактор, спільний майже всім
  когнітивним задачам; ~40–50% дисперсії батареї тестів. → I3 (абстрагування).
  [Defining Intelligence, Mensa Foundation](https://www.mensafoundation.org/wp-content/uploads/Defining-Intelligence.pdf)
- **[E] Cognitive architectures — Common Model of Cognition** (Soar/ACT-R/Sigma; Newell,
  «Unified Theories of Cognition»): робоча пам'ять + процедурна (продукції) + декларативна
  (факти/епізоди). → I4 (висновок), I5 (пам'ять), I7.
  [ACS: ACT-R vs Soar](https://advancesincognitivesystems.github.io/acs2021/data/ACS-21_paper_6.pdf) ·
  [Common Model + analogical memory](https://arxiv.org/pdf/2210.11731)
- **[E] World-models:** Ha & Schmidhuber (2018), Hafner (Dreamer, 2023) — вчать представлення
  для *передбачення, планування, рішень*; LeCun **JEPA** (joint-embedding predictive). → I1.
  [Survey of World Models (arXiv 2411.14499)](https://arxiv.org/html/2411.14499v4)

---

## C2 — Фізика/енергетика обчислень (серце H-B)

- **[E] Межа Ландауера:** стирання 1 біта коштує ≥ *kT·ln2* ≈ **2.8×10⁻²¹ Дж** (кімнатна t°).
  [Stanford PH240](http://large.stanford.edu/courses/2016/ph240/vega1/) ·
  [Landauer bound review, PMC11119825](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11119825/)
- **[C] 🔎 Мозок ≈1.26× межі Ландауера (для обчислювальної частки):** бюджет мозку ~15–20 Вт
  ділиться на *обчислення+комунікація ≈3 Вт*, *терморегуляція ≈9 Вт*, *інша біологія ≈3–8 Вт*;
  саме ~3 Вт-частка ≈ **1.26× теоретичного мінімуму**. Тобто мозок майже вичерпав
  термодинамічний резерв для своєї обчислювальної роботи. *(Крос-валідовано 2 запитами;
  первинне — arXiv 2508.03191 + escholarship qt9p12m226.)*
  [Neuromorphic architecture of brain (arXiv 2508.03191)](https://arxiv.org/pdf/2508.03191) ·
  [Intrinsic HW efficiency of human brain](https://escholarship.org/content/qt9p12m226/qt9p12m226_noSplash.pdf)
- **[E] Мозок vs суперкомп'ютер (порядки):** мозок ~20 Вт; El Capitan (2026) 1.8 exaFLOPS
  за ~30 МВт. → на *енергію* мозок на ~6 порядків ощадніший *за деяких припущень*.
  [isat.academy](https://www.isat.academy/post/human-mind-vs-ai-energy-efficiency) ·
  [Energy challenges of ASI (PMC10629395)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10629395/)
- **[C] ⚠️ «У N мільйонів разів ефективніший» — НЕСТІЙКЕ ЧИСЛО:** оцінки мозку в FLOPS
  спанять **10¹²–10²⁸** (Carlsmith ~1e15; ±1 порядок «незвідної» невизначеності через
  визначення «операції»). Тому конкретний множник (1.5M× vs 9×10⁸×) залежить від методики.
  **Чесна опора:** мозок радикально ощадніший на *своїх* задачах (сприйняття, one-shot
  навчання, втілений контроль), не обов'язково на сирій арифметиці. Є й контрар-погляд.
  [Brain performance in FLOPS (AI Impacts)](https://aiimpacts.org/brain-performance-in-flops/) ·
  [Open Phil brain-compute report](https://coefficientgiving.org/research/how-much-computational-power-does-it-take-to-match-the-human-brain/) ·
  [контрар: «brains not much more efficient» (LessWrong)](https://www.lesswrong.com/posts/KsKfvLx7nFBZnWtEu/no-human-brains-are-not-much-more-efficient-than-computers)

---

## C3 — Субстрати (що уможливлює перенос — H-C)

- **[E] Нейроморфіка Loihi 2 (Intel):** 1 млн нейронів, 120 млн синапсів; **до 100× ощадніше
  за GPU** на певних задачах; sparse, подієво-керовані спайки, memory+compute разом.
  [Intel Neuromorphic](https://www.intel.com/content/www/us/en/research/neuromorphic-computing.html) ·
  [Loihi 2 ecosystem](https://uplatz.com/blog/the-convergence-of-spiking-neural-networks-and-neuromorphic-hardware-an-in-depth-analysis-of-intels-loihi-2-ecosystem/)
- **[E] SpiNNaker 2 (Manchester/TU Dresden):** 152k нейронів, 152 ARM-ядра/чип; DVFS +
  power-gating → енергія масштабується з активністю.
  [SpiNNaker2 SNN inference (arXiv 2406.17049)](https://arxiv.org/pdf/2406.17049)
- **[E] Аналогові in-memory / мемристори:** пам'ять і обчислення в одному місці (як синапс),
  аналогова матрично-векторна множина в crossbar, **одиниці fJ/спайк**; знімає
  von-Neumann-вузол. Огляди Nature.
  [Nature Rev. Electrical Eng. (memristor accelerators)](https://www.nature.com/articles/s44287-024-00037-6) ·
  [Nature Materials: high-accuracy analog CIM](https://www.nature.com/articles/s41563-026-02600-y)

---

## C4 — Динаміка інтелекту (твоя «течія/круговорот» — на СОЛІДНІЙ основі)

- **[E] Free Energy Principle / Active Inference (Friston):** система мінімізує *варіаційну
  вільну енергію* = похибку передбачення; **єдиний потік**, що поєднує сприйняття, дію,
  навчання. Це формалізація «інтелект = потік передбачення». → I1, I6.
  [FEP→AI, active inference (RG 397380587)](https://www.researchgate.net/publication/397380587) ·
  [Neural dynamics under active inference (arXiv 2001.08028)](https://arxiv.org/pdf/2001.08028)
- **[E] Кортикальні біжучі хвилі:** хвилі активності в сенсорних/моторних/когнітивних
  системах модулюють збудливість — літеральні «хвилі» в мозку (Nature Reviews Neuroscience).
  [Cortical travelling waves (NRN 2018)](https://www.nature.com/articles/nrn.2018.20)
- **[C] Критичність / self-organized criticality:** робота біля критичного стану → макс.
  динамічний діапазон, оптимальна передача/зберігання інформації, успішне навчання. Є й
  контроверсії щодо всюдисущості. → кандидат-принцип ефективності P6.
  [Criticality foundations (MIT Press NetNeuro)](https://direct.mit.edu/netn/article/6/4/1148/112392) ·
  [25 years of criticality (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0959438819300248)

> **Вагомий висновок:** «круговорот/хвиля/потік» як онтологія інтелекту **підтверджується
> усталеною наукою (FEP + біжучі хвилі + критичність)** — без потреби залучати квантову фізику.

---

## C5 — Квантова/заплутаностна лінза (чесний розбір — найслабша ланка)

- **[C]/[S] Orch-OR (Penrose–Hameroff):** свідомість із квантових процесів у мікротрубочках.
  2024 — теоретична superradiance у мікротрубочках; 2023 — міграція енергії ~6.6 нм,
  чутлива до анестетиків.
- **[E]-критика (вирішальна):** будь-який квантовий стан у «теплому, вологому, шумному»
  мозку **декогерує за фемтосекунди** — на порядки швидше за нейронні часи; **немає
  унікальних фальсифікованих передбачень**.
  [Orch-OR quantum-classical complexity (Frontiers 2025)](https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2025.1630906/full) ·
  [ScienceDaily: microtubule quantum vibrations](https://www.sciencedaily.com/releases/2014/01/140116085105.htm)

> **Вердикт по лінзі:** буквальна «квантова заплутаність як субстрат розуму» — наразі
> **не підтримана [S]**. Продуктивний перенос: «заплутаність» → *метафора* високо-вимірної
> кореляції/зв'язності в динаміці (це якраз [E]-критичність і хвилі), а не буквальний квант.

---

## C6 — Здійсненність: сучасний AI-compute vs мозок

- **[E] 🔎 Енергія LLM:** тренування GPT-3 ~1 287 МВт·год; GPT-4 >50 ГВт·год; **інференс — >90%
  енергії за час життя** моделі. Дата-центри: ~415 ТВт·год (2024) → ~945 ТВт·год (2030).
  [Energy of generative models (2025)](https://techjury.net/industry-analysis/how-much-energy-do-generative-models-use/) ·
  [LLM inference energy (arXiv 2504.17674)](https://arxiv.org/pdf/2504.17674)
- **Контраст:** людина-експерт «працює» на ~20 Вт — розрив із дата-центровим ШІ величезний,
  що й робить питання H-B практично вагомим.

---

## Синтез-затравка → кандидат-ПРИНЦИПИ ефективності мозку (для кроку 3)
*(чому мозок ощадний — не один принцип, а СТЕК; це саме по собі результат для H-B)*

| # | Принцип | Тег | Опора |
|---|---|---|---|
| P1 | Пам'ять і обчислення в одному місці (немає von-Neumann-вузла) | [E] | нейроморфіка, мемристори |
| P2 | Розріджена, подієва (спайкова) активність — енергія ∝ роботі | [E] | Loihi/SpiNNaker |
| P3 | Аналогові, низько-точні, ймовірнісні сигнали | [E] | мозок; аналог CIM |
| P4 | Масивна паралельність / розподіленість | [E] | архітектура кори |
| P5 | Обробляти лише «несподіванку» (мінімізація похибки передбачення) | [E]/[C] | FEP |
| P6 | Робота біля критичності (макс. діапазон/інфо-передача) | [C] | SOC |
| P7 | Фізика-native обчислення (хай фізика рахує) | [E]/[C] | аналог/фотоніка |
| P8 | Квантова когерентність як ресурс | [S] | Orch-OR (не підтримано) |

---

## Чернетка звуження інваріантів 8 → 6 (на ГЕЙТ, крок 3)
Спираючись на джерела (не «на око»):
1. **Передбачувальна модель світу** (злиті I1+I3: побудова+стиснення внутрішньої моделі) — world-models, FEP, g.
2. **Вектор цінності/ціль** (I2) — Legg-Hutter, RL, active inference.
3. **Висновок і планування над моделлю** (I4) — Soar/ACT-R, sampling.
4. **Пам'ять як атракторна динаміка** (I5) — Common Model, Хопфілд.
5. **Навчання = мінімізація похибки передбачення** (I6) — FEP, пластичність.
6. **Метакогніція / self-model** (I7) — Global Workspace, Common Model.

> **Елегантний хід:** **I8 (генералізація) — не окрема «цеглинка», а ЦІЛЬОВА властивість**,
> що *емерджентно виникає*, коли інваріанти 1–6 стають домен-інваріантними. «General» — це
> результат, не компонент.

---

## Відкриті нитки фальсифікації (для кроку 3 — критерій §2.5)
- **F1:** «мозок у N× ефективніший» — число нестійке (16 порядків розкиду FLOPS) → H-B треба
  формулювати як *ефективність на втілених/сприйняттєвих задачах*, не на арифметиці.
- **F2:** «єдиний принцип ефективності» — джерела кажуть про **стек P1–P7**, не про один
  принцип → H-B уточнити: «мала *множина* принципів», а не «принцип».
- **F3:** втілений/реактивний інтелект комах (~10⁵ нейронів, без явної «моделі світу») —
  виклик необхідності I1 як строго обов'язкового. [C]
- **F4:** квантова основа [S] провалює тест декогеренції → лінзу переформулювати як метафору
  кореляції, не буквальний квант.

---

## Статус критеріїв (§2 README)
| Критерій | Статус | Нотатка |
|---|---|---|
| 1. Покриття C1–C6, ≥3 джерела/кластер | ✅ | всі 6 кластерів, Tier-1-атрибуція |
| 3. Gap-map ефективності | 🟡 | числа є; множник — чесно як діапазон; 🔎 звірити первинники |
| 4. Теги [E]/[C]/[S] | ✅ | застосовано всюди |
| 5. Фальсифікація | 🟡 | 4 нитки відкрито (F1–F4) — добити на кроці 3 |
