# Recipe Template (контракт кожного рецепта важкого процесу)

> Кожен рецепт — `references/recipes/<name>.md`. Вантажиться **на вимогу** (progressive disclosure).
> Рецепт описує ПРОЦЕС, не переписує механіку — він конфігурує контрол-луп RLM Harness.

## Обов'язкові секції рецепта
1. **Тригери** — коли застосовувати (ALWAYS use when / DO NOT) — узгоджені з description скіла.
2. **Objective contract** — що на вході, що на виході (формат результату), критерій «готово».
3. **Control loop** — конфіг циклу Plan-Execute-Verify-Replan для цього процесу:
   - умови REPLAN (які прогалини запускають доповнення плану);
   - критерій збіжності (специфічний для процесу);
   - гарди завершення (max-turns/depth/timeout/quality).
4. **Topology** — яка топологія (делегує `workflow-orchestration`): fan-out subagents / hierarchical / teams.
5. **Per-step model class** — таблиця крок→клас моделі (за `model-fit-policy.md`):
   зазвичай planner=топ; паралельні воркери=дешеві; critic/judge=сильний; synth=сильний; review=сильний.
6. **Validation gates** — що перевіряє `validation-mesh` на кожному гейті; рубрика якості.
7. **Output contract** — структура фінального артефакту (напр. цитований звіт, severity-таблиця, вердикт).
8. **Safety / governance notes** — тонкий покажчик на `safety-compliance-gate` де релевантно
   (зовнішній вхід = недовірені дані; side-effect = human-confirm; defensive-only де доречно).
9. **Cost note** — очікувана вартість/токени, де cap частки сильної моделі, де cascade.
10. **Evals hook** — ≥1 eval-кейс на бажану поведінку рецепта (TDD: baseline провалює).

## Опорна форма (default skeleton процесу)
```
PLAN: planner (топ-модель) → ціль у DAG під-задач (typed-handoff)
ACT:  паралельні воркери (дешеві, різні налаштування для різноманіття результатів)
VERIFY: critic / credibility judge (сильний) — чи сукупні результати закривають ціль? прогалини?
        прогалина → REPLAN (таргетований добір під-задач)
SYNTH: synthesizer (сильний) → чернетка результату
REVIEW: review-крок — атрибуція джерел / несуперечливість (validation-mesh) → фінал
```

## Заборони
- Не інлайнити рецепт у тіло SKILL.md (роздування + токени) — лише registry-рядок + цей контракт.
- Не дублювати механіку (топологія/валідація/стан) — посилання на власника.
- Не фіксувати конкретні моделі — лише класи (див. `model-fit-policy.md`).
