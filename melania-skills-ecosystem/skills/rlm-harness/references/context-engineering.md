# Context Engineering (для rlm-harness)

> **Канонічне джерело — не дублювати тут:** `continuation-memory/references/context-engineering.md`
> (MECW / lost-in-the-middle, ієрархія hot·warm·cold, чотири важелі, бюджет-слоти, ACON-дистиляція).

rlm-harness — споживач цього shared-reference. У контексті оркестрації важливі:
- **Multi-agent isolation** — суб-задачі в ізольованих субагентах; назад лише typed-context-обʼєкт (≈200–500 ток.), не сира історія.
- **ACON-патерн** — компресор контексту дистильований у дешевшу модель (~95% точності, ↓26–54% peak); узгоджено з «дорогий диригент / дешеві суб-процеси».
- **Бюджет-слоти** живлять бюджетний губернатор harness — див. `model-fit-policy.md` (стелі per-request/task/run, cap частки сильної моделі).
- Фінальний шар стиснення/виводу — **українською** (узгоджено зі статус-тулбаром UA, P-LS у `semantic-router`).
