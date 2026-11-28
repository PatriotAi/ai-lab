# docs/continuation/ — пакети продовження

Тут лежать пакети передачі роботи в нову сесію (`<дата>-<тема>.md`). Протокол —
`continuation-memory` §§ «Дешеве відновлення» і «Автоперехід у нову сесію».

- Скелет пакета пише скрипт: `python3 scripts/session-handoff.py pack --trigger context|compact|wave --topic <тема>`.
- Модель дописує лише позначене `<!-- ДОПИСУЄ МОДЕЛЬ … -->`.
- Перед комітом: `python3 scripts/session-handoff.py validate <файл>` (exit 0).
- Стара сесія не видаляється й не архівується; її id — у рядку `Попередня сесія:`.

## Що працює зараз і що чекає згоди власника

| Тригер | Стан |
|---|---|
| поріг контексту на старті / resume / після стиснення | ✅ чинний SessionStart-хук (`automations/session-start/session-start.sh`) |
| вказівка після стиснення (`source=compact`) | ✅ той самий хук |
| поріг **щоходу** (`UserPromptSubmit`) | ⏸ потребує зміни налаштувань агента — гейт R4, згода власника |
| до стиснення (`PreCompact`): скелет пакета з живого стану + інструкція підсумку зберегти рішення, наміри й шлях пакета (дописує модель уже після) | ⏸ те саме |

Готовий фрагмент для блоку `hooks` налаштувань агента (додати до наявних, нічого не прибираючи).
Чинна документація Claude Code (звірено 2026-11-28): вхід хука приходить JSON-ом у stdin (з
`transcript_path`); вивід `PreCompact` із кодом 0 стає інструкцією для підсумку стиснення.

```json
"UserPromptSubmit": [
  { "hooks": [ { "type": "command",
    "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/session-handoff.py\" check --hook-input -" } ] }
],
"PreCompact": [
  { "hooks": [ { "type": "command",
    "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/session-handoff.py\" pack --trigger compact --topic after-compact --hook-input -" } ] }
]
```

Щоб увімкнути — рядок згоди в `security/consent.md` з ціллю, яку назве гейт, і окремий PR.
