# Topology Taxonomy — повна довідка (workflow-orchestration)
> Завантажується НА ВИМОГУ (не проактивно). Українською-перша; технічні терміни — англійською. Доповнює основний `SKILL.md` (там — робочі топології: single / sequential / subagents / hierarchical / teams / **nested** Topology 3). Тут — повна таксономія 10+, framework-мапінг, деталі shared-task, observability-стек.

## 1. Повна таксономія топологій

| # | Топологія | Суть | Коли | Головний trade-off |
|---|---|---|---|---|
| 1 | **Single agent** | один контекст, лінійно | проста задача, один домен | стеля складності одного вікна |
| 2 | **Sequential pipeline** | A→B→C, фіксовані етапи з handoff | детермінований конвеєр (SDLC) | без паралелізму; latency = сума етапів |
| 3 | **Subagents / orchestrator-worker (fan-out)** | оркестратор спавнить N паралельних воркерів, кожен звітує | незалежні гілки, breadth-first | вартість ~15×; складність координації |
| 4 | **Hierarchical (supervisor routing)** | супервізор інтелектуально маршрутизує до спеціалістів | потрібен роутинг, не фіксований конвеєр | супервізор — вузьке місце/SPOF |
| 5 | **Agent teams (shared task list + P2P)** | рівні агенти, спільний список, peer-to-peer обмін | взаємозалежні треки + крос-виклик | ~3-4× токенів; синхронізація стану |
| 6 | **Nested subagents (deep)** | агент→агент, вкладеність (стеля 5 у Claude Code, відносна до підкладки) | ієрархічна декомпозиція з ізоляцією шарів | видимість/вартість/помилки множаться (див. SKILL.md Topology 3) |
| 7 | **Swarm (decentralized handoff)** | децентралізовані агенти передають керування одне одному без центрального оркестратора | гнучкі, емерджентні маршрути | важко передбачити/дебажити; ризик циклів |
| 8 | **Handoff (agent-to-agent transfer)** | явна передача ВСЬОГО керування іншому агенту (triage → спеціаліст) | зміна спеціалізації по ходу | втрата контексту при передачі → typed-handoff обовʼязковий |
| 9 | **Blackboard (shared memory)** | кілька агентів читають/пишуть спільний стан; контролер активує за умовами | багатоджерельний синтез, порядок наперед невідомий | гонки запису; потрібен арбітр/локи |
| 10 | **Contract-net (bid/award)** | менеджер оголошує задачу → агенти «торгуються» → призначення найкращому | динамічний розподіл під здатності/навантаження | накладні витрати на торги |
| 11 | **Group chat (multi-agent conversation)** | агенти «розмовляють» у спільному треді, модератор веде чергу | дебати / рев'ю / мозковий штурм кількох ролей | дрейф розмови; токени на репліки |

**Вибір — за віссю задачі:** паралелізм незалежного → fan-out (3); інтелектуальний роутинг → hierarchical (4); крос-виклик рівних → teams (5); ізоляція шарів ієрархії → nested (6); зміна ролі по ходу → handoff (8); невідомий порядок багатоджерельного синтезу → blackboard (9). Глибока вкладеність ≠ паралелізм.

## 2. Framework-мапінг (орієнтовний — API змінюються, звіряй наживо)

| Патерн | LangGraph | CrewAI | AutoGen / MAF | OpenAI Agents SDK | Google ADK | AWS Bedrock Agents |
|---|---|---|---|---|---|---|
| Orchestrator-worker | StateGraph + умовні ребра | Crew + tasks | GroupChatManager | Agents + handoffs | Parallel/Sequential agents | Supervisor + collaborators |
| Hierarchical | nested graphs | hierarchical process | nested teams | agent-as-tool | Workflow agents | Multi-agent collaboration |
| Sequential | linear edges | sequential process | sequential chat | chained runs | SequentialAgent | Prompt chaining |
| Shared-state / blackboard | shared State channel | shared memory | shared context | session state | shared session | session attributes |
| Handoff / swarm | command/goto | (через process) | speaker transitions | handoffs (нативно) | transfer | routing |

Версії/назви API НЕ хардкодь — перевіряй через офіційні доки провайдерів/фреймворків.

## 3. Shared task list — деталі реалізації (Agent Teams, Topology 5)

- **Запис:** `{id, title, owner, status (todo/claimed/in_progress/blocked/done), deps[], artifact_ref}`.
- **Claim-протокол:** агент атомарно «клеймить» todo (CAS/lock), щоб двоє не взяли той самий; звільняє при `blocked`.
- **Детермінована координація (нуль LLM-токенів):** routing / merge / claim — кодом; LLM лише на змістовну роботу.
- **P2P-обмін:** агент пише знахідку в спільний стан → інші бачать; challenge/review — окремий todo «review X».
- **Завершення:** team lead закриває, коли всі todo = `done` і verify-гейт пройдено.

## 4. Observability-стек (для будь-якої багатоагентної топології)

- **OTEL span-tree:** кожен агент = span; `parent_agent_id` зшиває вкладеність у дерево → видно, де пішли токени/час/помилки.
- **Per-agent метрики:** tokens · turns · tool-calls · тривалість · статус (success/abort).
- **Бюджет-гард:** перевіряй сумарну вартість ПЕРЕД спавном (механіка — `rlm-harness`).
- **Trace-теги:** topology · depth · role · model — щоб фільтрувати й порівнювати прогони.
- **Навіщо:** у глибоких/широких топологіях помилка ховається за чистим резюме — span-tree є єдиним способом post-hoc аудиту.

## Джерела
Anthropic «Building Effective Agents» + multi-agent research system; офіційні framework-доки (звіряти наживо). Узгоджено з основним `SKILL.md` (Topology 1/2/3), `rlm-harness` (model-per-role, бюджет-гард) та `validation-mesh` (verify-гейти).
