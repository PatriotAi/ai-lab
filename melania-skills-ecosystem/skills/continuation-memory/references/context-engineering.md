# Context Engineering — shared reference
> Власник: continuation-memory. Споживачі: ai-core-runtime, rlm-harness. Вантажити на вимогу.

## 1. MECW — чому стиснення обов'язкове (не лише економія)
Ефективність падає ЗАДОВГО до технічного ліміту вікна — функція архітектури уваги, не
лічби токенів. Початок/кінець вікна отримують більше уваги, середина тоне (lost-in-the-middle).
Нерелевантний контекст КОНКУРУЄ за увагу з релевантним. Сфокусовані ~5k часто кращі за ~50k.
Висновок: context engineering — постійна дисципліна на весь lifecycle мульти-тур агента,
а не обхід тимчасового ліміту вікна.

## 2. Ієрархія за свіжістю (hot/warm/cold)
Hot (≈10 ходів, verbatim) · Warm (summary: рішення/імена/артефакти збережені, вирішені дебати
відкинуті) · Cold (винесено на диск / memory_user_edits).
Ортогонально до retrieval-сходів L1→L3 continuation-memory (ті — глибина дістання з архіву;
ці — свіжість живої сесії).

## 3. Чотири важелі проти необмеженого росту контексту
1. **Compaction (в сесії)** — Anthropic Compaction API: server-side авто-стиснення старіших
   частин, Opus 4.6/4.7, ZDR. Прозоро, без reset.
2. **Session splitting (між сесіями)** — явні межі фаз + continuation-пакет/STENO несе
   компактний стан вперед.
3. **Structured note-taking** — нотатки поза вікном (скафолд проєкту: ROADMAP/CONTEXT/log).
4. **Multi-agent isolation** — суб-задачі в ізольованих субагентах; назад — лише
   typed-context-обʼєкт, не сира історія.

### Compaction vs Split — коли що
| Ситуація | Важіль |
|---|---|
| Структуровано (spec→implement→verify), межі фаз явні | Split + STENO (тісніший контроль межі) |
| Відкрите/довге (exploratory debug, research, багатокрок без чітких меж) | Compaction API (drop-in; ціна — непрозорість межі) |

## 4. Бюджет-слоти (budget-governor: ai-core-runtime / rlm-harness)
Орієнтир при ~200k baseline — важливі ПРОПОРЦІЇ, не абсолюти (масштабуй під розмір вікна):

| Слот | Призначення | ~частка |
|---|---|---|
| System/instructions | системний промпт, правила | low-fixed |
| Hot history | свіжі ходи verbatim | medium |
| Retrieved/JIT | just-in-time документи | medium, еластично |
| Working/scratch | проміжні міркування | medium |
| Output reserve | резерв під відповідь | fixed |

Рамка курування: **write / select / compress / isolate** — що покласти, що дістати,
коли стиснути, що винести в субагента.

## 5. Дистиляція компресора (ACON-патерн → rlm-harness)
Компресор контексту можна дистилювати в МЕНШУ/дешевшу модель, зберігаючи ~95% точності
вчителя, ↓26–54% peak tokens. Узгоджено з «дорогий диригент / дешеві суб-процеси» rlm-harness
і з внутрішнім мультимовним шаром стиснення (фінал — українською). Малі моделі як агенти
працюють краще, коли їх не відволікає довгий контекст.

## Джерела (harvest 2026)
Anthropic «Effective context engineering» + Compaction API docs; agentmarketcap (hierarchical
memory); tokenoptimize / digitalapplied (levers, budget-slots); ACON (arXiv 2510.00615).
Харвестились ІДЕЇ; жодного зовнішнього коду не внесено.
