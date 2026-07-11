---
name: workflow-orchestration
description: >
  CORE playbook for structuring multi-layer, multi-subagent workflows. Teaches WHEN
  and HOW to choose Subagents (orchestrator-worker, context isolation, fan-out → report)
  vs Agent Teams (Team Lead + shared task list + peer-to-peer), plan-first decomposition
  (E0 master-plan engine), typed-context handoff, and multi-agent governance. Applied autonomously.
  USE WHEN: a task needs multiple agents/subagents, parallel work, or team coordination;
  choosing an orchestration topology; planning a multi-agent workflow; "оркеструй",
  "розбий на агентів", "subagents", "agent team", "shared task list", "паралельно", "fan-out".
  DO NOT USE for: single simple Q&A or one-off snippet (use the specific skill); runtime
  kernel / agent-activation mechanics (ai-core-runtime); intent routing across skills (semantic-router).
compatibility: Claude.ai (all plans) · Claude Code · Codex CLI · Cursor · Copilot. Core platform-neutral; subagent/Agent-Teams mechanics are Claude Code.
license: MIT
metadata:
  author: Melania (Master Administrator)
  version: 1.4.0
  category: orchestration
  created: 2026-06-13
  last_updated: 2026-07-11
---

# Workflow Orchestration
Українською-перша: тригери/відповіді/приклади — українською; перемикання лише слідом за користувачем.
Безпека/комплаєнс — `safety-compliance-gate` (обов'язково перед пакуванням/публікацією).

## 🛡️ Протокол Збереження Перед Оновленням (ОБОВ'ЯЗКОВО)
Обов'язковий перед БУДЬ-ЯКОЮ зміною цього скіла. **Канонічне джерело (не дублювати тут):** `melania` — секції «🛡️ Протокол Збереження Перед Оновленням» + «Update Workflow» + «Core Rule 10 — Re-Read Before Update».

Стисло: re-read диску → порівняти версії (диск новіший → диск база) → integrity-diff → validation-mesh → safety-compliance-gate (перед пакуванням/публікацією) → backup/snapshot → merge-not-replace → bump+CHANGELOG → показати diff і чекати явного схвалення MA (Закон II).


## Mission
Playbook, як самостійно структурувати багатоагентний воркфлоу: обрати топологію → спланувати (E0) → передати контекст → виконати під governance. Дефолт — мінімально достатня кількість агентів; нарощуй лише коли реально покращує ізоляцію, паралелізм або трасування.

## Autonomous Decision Algorithm
Застосовуй БЕЗ нагадувань, перед кожною нетривіальною задачею:
```
1. Оціни: декомпозованість · паралелізм · потреба inter-agent комунікації · цінність · толерантність до помилок
2. Один контекст + лінійна           -> SINGLE AGENT (дефолт)
3. Незалежні гілки, breadth-first     -> SUBAGENTS (fan-out, typed-брифінг кожному, parent синтезує)
4. Взаємозалежні треки + крос-обмін   -> AGENT TEAMS (shared list + P2P)
5. Детермінований конвеєр             -> SEQUENTIAL; інтелектуальний роутинг -> HIERARCHICAL
6. Ієрархічна декомпозиція, шар потребує ВЛАСНОЇ ізоляції контексту -> NESTED SUBAGENTS (Topology 3; вісь = ГЛИБИНА, не паралелізм/роутинг; глибина адаптивна)
7. ЗАВЖДИ: спершу план (E0), потім виконання; кожен субпроцес — з власного міні-плану
```
Калібрування (Anthropic): факти 1 агент/3–10 calls; порівняння 2–4 subagents/10–15; складне 10+ з чітким поділом. Cap concurrency 4–6.
Auto-agent (правило 16): складність/ризик/багатокроковість -> авто agent-chain або tool-orchestration. Дозволу на декомпозицію не питай; лише на side-effect-дії.

- Якість критична + перевірна планка (тести/rubric) → додай EVALUATOR-OPTIMIZER контур (Topology 4) поверх обраної топології.

## Decision Matrix
| Критерій | Single | Sequential | Subagents | Hierarchical | Agent Teams |
|---|---|---|---|---|---|
| Декомпозованість | низька | лінійна | незалежні гілки | потрібен роутинг | взаємозалежні треки |
| Inter-agent комунікація | — | output→input | немає | через супервізора | пряма P2P |
| Паралелізм | ні | ні | так | частково | так |
| Детермінізм | високий | високий | середній | середній | низький |
| Вартість (токени) | 1× | ~N× | ~4–15× | +30–50% | ×к-сть тіммейтів |
| Толерантність до помилок | низька | крихка | reassign | escalate | reassign+unblock |

Дефолт: start with one agent; додавай спеціалістів лише коли покращують ізоляцію, паралелізм або трасування.
> Вкладена декомпозиція (агент→агент, deep) — окрема вісь ГЛИБИНИ: див. **Topology 3**. Обирай коли шар потребує ізоляції від батьківського контексту, не для паралелізму (fan-out) чи роутингу (hierarchical).

## Topology 1 — Subagents (orchestrator-worker, fan-out -> report)
Main Agent декомпозує -> спавнить ізольовані subagents -> паралельний Work -> Result -> Main агрегує.
- Властивість: isolation boundary — workers не спілкуються; рішення про наступний крок в orchestrator-і.
- Коли: breadth-first дослідження; один шаблон до N елементів; ізоляція «шумних» задач від головного контексту.
- Сильні: context isolation; parallelism (wall-clock −60–80% на незалежних); token control (дешевша модель на воркерах).
- Обмеження: немає cross-agent комунікації; вартість агрегації; дублювання за нечіткого брифінгу -> кожному дай objective/output-format/tools/межі.

## Topology 2 — Agent Teams (Team Lead + shared task list + P2P)
Team Lead спавнить команду -> усі читають/пишуть shared task list, claim-лять вільні задачі, спілкуються P2P (mailbox).
- Властивість: shared state + horizontal coordination; dependency auto-unblock.
- Коли: великі фічі з треками; QA-swarm; debate-to-converge (спростовують гіпотези один одного).
- Сильні: dynamic load balancing; колаборація; емерджентна декомпозиція.
- Обмеження: coordination complexity; race conditions; duplicate work; токени × тіммейти.
- Anthropic-застереження: погано, де всі ділять один контекст / сильно взаємозалежні (більшість coding) -> supervisor або один агент.

**Емпірика масштабу:** паралельні команди повних агент-інстансів із git-координацією доведено тягнуть проєкти рівня 100K+ рядків (кейс: 16 паралельних агентів → робочий C-компілятор за ~2 тижні автономно).

## Topology 3 — Nested Subagents (вкладена декомпозиція: агент спавнить агента)
Саб-агент спавнить власних саб-агентів — ієрархічний ланцюг, де вивід рівня = вхід наступного. Кожен рівень — свіже ізольоване контекстне вікно; нагору повертається ЛИШЕ резюме верхнього саб-агента → головний контекст не забивається шумом проміжних кроків.
- **Коли:** генуінно ієрархічна декомпозиція (spec→design→api→impl→test), де кожен шар потребує власної ізоляції від батьківського контексту. НЕ для паралелізму (це fan-out, Topology 1) і НЕ для спільного стану (teams, Topology 2).
- **Стеля глибини — ВІДНОСНА ДО ПІДКЛАДКИ, не універсальне число.** Claude Code: жорстка серверна стеля **5 рівнів вниз** (на L5 інструмент `Agent` не видається — спавн далі неможливий; лічильник рахується вниз від поточного рівня, головна сесія = рівень 0). Інші підкладки (Agent SDK, n8n, зовнішня multi-provider оркестрація) — інша стеля або без неї → інші/майбутні поверхні не закриті. _UNKNOWN (офіційно не уточнено): «5» = рівнів під коренем чи всього — не пінь як факт._
- **Глибина = АДАПТИВНИЙ вибір планувальника, НЕ фіксоване число.** На E0-плані: оціни складність → обери МІНІМАЛЬНУ ДОСТАТНЮ глибину для ЦІЄЇ задачі (механіка — депт-леддер `ai-core-runtime`: найдешевший рівень, що відповідає; рішення про глибину ДО спавну). Треба глибоко — йди глибоко; стеля підкладки — верхня межа, НЕ ціль і НЕ «краще мілко». Гарди завершення (max-depth/budget/quality) уже в Governance Checklist + бюджет-гард `rlm-harness`.

### Трансценденція стелі — композиція консолідованих блоків («рівень Бога»)
Стеля обмежує ОДИН ланцюг вниз, не пожиттєво. «Вгору» (назад до рівня 0) — без ліміту глибини:
```
MAIN (рівень 0): спавн Блок A (вниз ≤5) → VERIFY+консолідація → компакт-резюме
                 спавн Блок B (свіжий бюджет 5) → VERIFY+консолідація → резюме
                 спавн Блок C … → MAIN поєднує A+B+C → остаточний результат
```
- Композитор МУСИТЬ сидіти на **рівні 0** (головна сесія) АБО поєднувати через зовнішній стан (`.md`). Реалізуєш композицію *глибшими саб-агентами* — вони їдять ту саму стелю 5.
- Це гілка **SPAWN-MORE** контрол-лупу `rlm-harness` (`PLAN→ACT→VERIFY→DECIDE→loop`), явна для вкладеного випадку.
- **Обмеження НЕ зникають — ЗМІЩУЮТЬСЯ (чесно):** (1) контекст КОРЕНЯ переповнюється від товстих резюме → блок повертає компакт ≈200-500 ток., надлишок у `.md`; (2) сумарна вартість ≈15× × к-сть блоків → бюджет-гард обов'язковий; (3) сумарна затримка складається; (4) помилки множаться (1 блок ≈0.95⁵≈77% наскрізно → композиція множить ще) → **VERIFY-гейт між КОЖНИМ блоком обов'язковий**, не опційний.

### Trade-offs глибокої вкладеності (вхідні дані рішення, НЕ заборона)
| Вісь | Ризик на глибині | Мітигація |
|---|---|---|
| Видимість | бачиш лише верхнє резюме; помилка на L4-L5 невидима зверху, тиха невдача підіймається «чистим» резюме | `.md`-артефакт на кожен рівень (гріпається, переживає компакцію); OTEL span-tree з `parent_id` |
| Вартість | сумарно ВИЩА за плаский (кожен рівень — повний контекст), хоч корінь і малий | дешева модель на листках (`CLAUDE_CODE_SUBAGENT_MODEL=haiku`); бюджет-гард ПЕРЕД спавном |
| Помилки | компаундинг 0.95ⁿ; «зіпсований телефон» на кожному резюме нагору | VERIFY-гейт між рівнями (`validation-mesh`); вивід у файл мінімізує телефон |
| Кермо | після запуску ланцюг некерований, не втрутишся всередині | вузька чітка задача кожному рівню (objective/output/tools/межі) ПЕРЕД спавном |

Дефолт вибору глибини: «настільки глибоко, наскільки задача варта» — НЕ «мілко про всяк випадок», НЕ «глибоко бо можна».

## Topology 4 — Evaluator-Optimizer (Outcomes-патерн)
Produce→grade→revise цикл із grader-ом в ІЗОЛЬОВАНОМУ контексті:
1. **Producer** виконує задачу.
2. **Grader** (окремий агент, ЧИСТИЙ контекст — не заражений reasoning-ом продюсера) оцінює за
   явним rubric → verdict + конкретні дефекти.
3. Не пройшло планку → producer ревізує з фідбеком; цикл до планки АБО стелі ітерацій (bounded).
**Коли:** якість критична + є перевірна планка (тести/rubric/схема). **Емпірика:** до +10 п. task
success проти простого prompting-циклу, найбільший виграш на найважчих задачах; file-generation
+8-10%. **Анти-патерн:** grader = producer (self-grade у тому самому контексті — сліпий до власних
помилок). Судова роль → клас моделі з `rlm-harness` model-fit; resilience-стеля → `ai-core-runtime`.

## Shared Task List — інваріанти (Agent Teams)
Статус-машина: `todo -> claimed -> in-progress -> done`; бічні `blocked`, `failed -> todo`.
- Atomic claim: `todo->claimed` атомарний (lock/CAS) — двоє не беруть одне.
- Idempotency: ключ (`id`+hash); повтор не дублює side-effects.
- Ownership+lease: owner+timeout -> по timeout назад у `todo`.
- Dedup: перед claim перевір, що не done.
- File-locking: ізоляція роботи (git worktrees / окремі директорії).
- Канали: shared list (основний) + mailbox (прямі узгодження). Реалізація blackboard-патерну.

## Plan-first + E0 Master-Plan Engine (правила E0, 15)
Кожен процес починається з плану. Не виконуй, доки не спланував.
```
bg-аналіз: ctx · meta · fmt · lim · rsk · tm
MasterPlan: L1 base -> L2 detail -> L3 forecast -> L4 verify -> L5 integrate
Loop (авто): sync -> verify -> update -> context -> state -> plan -> continue
```
- LiveSubPlan: під-план авто-оновлюється на кожну дію/повідомлення; користувач може коригувати.
- Дані = останнє verified; застаріле -> time-tag/history (механіка стану — `continuation-memory`).
- Meta одиниці: `ts/ver/ttl/rel`. Unverified -> async verify. Forecast: `max-probability + alternatives` (за потреби крос-модельно).
- Алгоритм виконання (правило 15): `E0 -> analysis -> risk -> verify -> validate -> structure -> respond -> optimize`.
- Декомпозиція DAG: ціль -> план у пам'ять -> subtasks (objective/output/tools/межі) -> Subagents: гілка кожному worker; Teams: у shared list з dependency-edges. Патерни: plan-and-execute, ReWOO (~2 LLM-виклики), LLMCompiler.
- **План-перший ≫ міопічний:** повний план наперед, уточнюваний доказами; «лише наступний крок» емпірично гірший. VERIFY на рівні оркестратора (сукупні результати vs ціль) → прогалина → **таргетований REPLAN**, не проштовхування. _(валідовано: VMAO/ICLR-2026; MCP-Agent/DeepPlanner.)_

## Typed-Context Handoff
Між агентами — typed-context-обʼєкт (≈200–500 ток.), НЕ сира історія:
`{objective, inputs, output_format, tools_allowed, constraints, success_criteria}`.
- Сира історія = анти-патерн (5k–20k ток.; вартість росте квадратично з хендофами).
- Subagent стартує свіжим; єдиний канал від parent — prompt-рядок -> клади туди все (шляхи/помилки/рішення).
- Повний обʼєкт/стан — `continuation-memory`.
- **Довговічний `.md`-handoff (конвеєри/вкладеність):** producer пише структурований артефакт (`spec.md`→`design.md`→`api.md`→…), consumer читає ЛИШЕ його. Anthropic-рекомендований патерн пайплайну: вивід саб-агента у файл мінімізує «зіпсований телефон» і переживає компакцію. Подвійна роль: handoff у ланцюзі + підкладка композиції блоків (Topology 3). Застереження: паралельні записи в один файл = гонка (серіалізуй або файл-на-агента); застарілий `.md` «тихо бреше» → трактуй як вхід для верифікації.

## Governance Checklist (вшивати в кожен запуск)
```
[ ] Termination: max-turns / max-depth / quality threshold / timeout
[ ] Bounded recursion: явна умова done; детект повторюваного виводу
[ ] Dedup/race (teams): atomic claim + idempotency + lease
[ ] Error: retry+backoff -> reassign (failed->todo) -> escalate
[ ] Cost: мінімальний достатній набір; cap 4–6; дешевша модель на воркерах
[ ] Deterministic coordination: routing/merge/claim — кодом, не LLM, де можливо (нуль токенів на координацію; сильна модель лише на reasoning/синтез)
[ ] Observability: trace/span з run-id; реконструйований ланцюг хендофів
```
Економіка (Anthropic, як повідомлено): multi-agent ≈15× токенів від чату; виправдано лише для high-value добре паралелізованих задач (+90.2% на research-eval). Виграш < вартості 4–15× -> відкотись на single/sequential.

## Stack Mapping (platform-neutral core + thin adapters)
Ядро (топологія -> E0-план -> typed-handoff -> governance) платформо-нейтральне.

Claude Code:
- Subagents: `.claude/agents/*.md` (`description/tools/model`); спавн Agent/Task tool; до ~7 паралельних; `CLAUDE_CODE_SUBAGENT_MODEL` дешевша модель.
- Nested subagents (Topology 3): саб-агент спавнить саб-агента; жорстка серверна стеля **5 рівнів вниз** (на L5 `Agent` не видається). Щоб агент НЕ спавнив дітей — прибери `Agent` з `tools` (leaf-агент). Гоча: `Agent(type)`-allowlist У ВИЗНАЧЕННІ саб-агента ІГНОРУЄТЬСЯ → для заборони спавну `permissions.deny: ["Agent(...)"]` у `.claude/settings.json`. Depth-tracking коректний з пізніших білдів — звіряй версію через `product-self-knowledge`, не пінь.
- Ізоляція skill: `context: fork` (+опц. `agent:`) — вміст skill = prompt субагента без історії. Відомі баги: інколи ігнорується через Skill tool -> додай явну Task-інструкцію.
- Agent Teams: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — Lead + named teammates + shared task list + mailbox (experimental).
- Shared state/governance: MCP як спільний стан/інструменти; hooks (`PreToolUse`/`PostToolUse`/`Stop`) для human-confirm/завершення.
- Recipe: plan first (plan mode, дешево) -> передай план команді на паралельне виконання.

n8n (substrate): AI Agent node = orchestrator + Agent-Tool nodes = subagents; queue mode (Redis+workers) = shared queue; Schedule Trigger; Error Trigger. Деталі — `n8n-orchestrator`.
Codex/Cursor: ті ж патерни тонким адаптером — план-обʼєкт і typed-handoff переносяться.

## Related Skills (динамічно; без хардкоду)
- ai-core-runtime — кернел ОБИРАЄ топологію й активує мінімальний набір; цей скіл — playbook ЯК виконати. Депт-леддер кернела = механіка АДАПТИВНОЇ ГЛИБИНИ вкладеності (Topology 3).
- semantic-router — L1 домен -> L2 скіл; усередині node цей скіл структурує мульти-агентів.
- continuation-memory — typed-context obj, стан/meta/freshness E0, continuation між сесіями.
- rlm-harness — мета-диригент НАД цим скілом: RLM-політика (хто на якій моделі) + динамічний контрол-луп + рецепти важких процесів; викликає цей скіл для вибору топології. Гілка SPAWN-MORE лупу = композиція консолідованих блоків (Topology 3, «рівень Бога»).
- validation-mesh — orchestration validation (повні edges, без deadlock/loop).
- n8n-orchestrator — substrate для розкладних/чергових воркфлоу.
- safety-compliance-gate — human-confirm на side-effect-tools; перед пакуванням.

## Advanced Patterns
Read `references/topology-taxonomy.md` коли потрібно: повна таксономія 10+ топологій (swarm/handoff/blackboard/contract-net/group-chat), framework-мапінг (LangGraph/CrewAI/AutoGen-MAF/OpenAI-SDK/ADK/Bedrock), детальні shared-task реалізації, observability-стек.

## Зміни
- **v1.4.0** (2026-07-11) — Topology 4: Evaluator-Optimizer / Outcomes-патерн (frontier-research harvest): produce→grade→revise з grader-ом в ізольованому чистому контексті, rubric-verdict, bounded-цикл; емпірика (+10 п. success, file-gen +8-10%); анти-патерн self-grade; крос-лінки rlm-harness (клас judge-моделі) + ai-core-runtime (resilience-стеля). Підключено до Autonomous Decision Algorithm (анти-орфан, урок v1.3.1). +1 рядок емпірики масштабу в Topology 2 (16 паралельних агентів → 100K+ рядків, агностично). Лише додавання. _(Джерело: дослідницький звіт 2026-07-11.)_
- **v1.3.3** (2026-06-26) — +`references/topology-taxonomy.md` (повна таксономія 10+ топологій swarm/handoff/blackboard/contract-net/group-chat; framework-мапінг LangGraph/CrewAI/AutoGen-MAF/OpenAI-SDK/ADK/Bedrock; деталі shared-task; observability-стек). Відновлює обіцяний-але-відсутній `references/` (форензик-аудит: артефакт не існував у git/транскриптах/FS → реконструйовано, проміс НЕ видалено). Лише додавання.
- **v1.3.2** (2026-06-26) — +evals/ (5 кейсів Topology 3: адаптивна глибина SDLC; стеля-5 / відносна до підкладки; композиція блоків «рівень Бога»; fan-out-vs-nest анти-патерн; .md-handoff). Закриває claimed-but-missing-evals для цього скіла (артефакт тепер існує). evals/ виключається з .skill (тест-артефакт). Лише додавання.
- **v1.3.1** (2026-06-26) — Coherence-патч: Topology 3 підключено до точок входу рішення — рядок у Autonomous Decision Algorithm (ієрархічна декомпозиція з ізоляцією шарів → NESTED) + покажчик біля Decision Matrix (вісь ГЛИБИНИ vs паралелізм/роутинг). Закриває орфан-секцію (раніше Topology 3 недосяжна з алгоритму вибору). Лише додавання. _(аудит-пас після 1.3.0.)_
- **v1.3.0** (2026-06-26) — Topology 3 (Nested Subagents): механіка вкладеності (агент→агент; стеля 5 ВІДНОСНА до підкладки; depth-counter вниз від рівня 0); адаптивна глибина як вибір планувальника (підключено до депт-леддера `ai-core-runtime` — НЕ дубльовано); композиція консолідованих блоків «рівень Бога» (трансценденція стелі через рівень-0 / `.md`-стан = гілка SPAWN-MORE `rlm-harness`); довговічний `.md`-артефакт handoff (Anthropic пайплайн-патерн) у Typed-Context Handoff; trade-offs-таблиця глибокої вкладеності (видимість/вартість/помилки/кермо). Усе — ДОДАВАННЯ; guard-validated (жодної наявної секції/рядка не видалено). _(дослідження nested-subagents 2026: Cherny-анонс 9.06.2026 v2.1.172; davila7-демо.)_
- **v1.2.1** (2026-06-15) — DRY: «Протокол Збереження» → тонкий міст на канон у `melania` (де-дублювання + усунення 8-варіантного дрейфу). Поведінка незмінна — гейт той самий, джерело єдине.
- **v1.2.0** (2026-06-14) — P-U3 (harvest-2026): рядок «Deterministic coordination» у Governance Checklist (routing/merge/claim кодом — нуль LLM-токенів на координацію). Решта durable-coordination (crash-recovery/approval-gates/kill-switch) вже була — не дубльовано.
- v1.0.0 (2026-06-13) — Початкова версія. Дві топології (Subagents / Agent Teams + shared task list) як вісь вибору + Decision Matrix; autonomous decision algorithm; E0 master-plan engine (L1-L5 + loop + LiveSubPlan) + правило 15 (alg) + правило 16 (auto-agent); shared-task інваріанти; typed-context handoff; governance-чеклист; стек-мапінг. Компактний AI-first формат. (Новий CORE; ресерч multi-agent orchestration 2025-2026; правила E0/15/16.)

- **v1.1.0** (2026-06-14) — P-02: «план-перший ≫ міопічний» + VERIFY на рівні оркестратора → таргетований REPLAN (валідовано VMAO/MCP-Agent); P-01: крос-лінк rlm-harness. _(SKILL-AUDIT-LEDGER, harvest RLM Harness.)_
