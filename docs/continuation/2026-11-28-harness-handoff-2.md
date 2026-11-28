# Продовження: harness-handoff-2 — перехід у нову сесію 2026-11-28

Ціль: покращення harness ai-lab за запитами власника; кожна зміна — окремий PR, злиття лише за свіжою згодою власника в розмові (§5).
Далі: підписатися (`subscribe_pr_activity`) на ai-lab#146, #149, #150, #152, #153, #154, звірити їх CI й нові зауваження рев'ю; далі — черга нижче.
Попередня сесія: `session_01Tu38bq1W7DqGgVeHvnrU1J` — НЕ видалена й не архівована [C: стан на момент запису пакета; звірити `get_session`]; дочитувати її лише найдешевшим виконавцем-читачем (`list_events` з `kinds`), підсумок ≤500 токенів. Архівація — лише рішенням власника.
Привід переходу: поріг контексту (≈450 тис. токенів).

## Живий стан (зібрано скриптом, без моделі)
- гілка `claude/harness-rules-drift` @ `8236f1c` · main попереду на 0 · незбережених файлів: 0
- незлиті гілки claude/*: `origin/claude/agent-skills-map`, `origin/claude/custom-plugin-marketplace-6nnd7t`, `origin/claude/github-automation-collaboration-aqf4qf`, `origin/claude/gmi-research-series-70k60b`, `origin/claude/harness-auto-handoff`, `origin/claude/harness-research-improvements-fp6ebm-resume`, `origin/claude/harness-research-improvements-fp6ebm-routine`, `origin/claude/harness-research-improvements-fp6ebm-routing`, `origin/claude/harness-rules-drift`, `origin/claude/models-default-class`, `origin/claude/monitor-cancelled-grey`, `origin/claude/sim-conditions`
- відкритих вікон боргу: 31 (`docs/WINDOWS.md`)

## Рішення й наміри
Рішення власника 2026-11-28 (у сесії-попередниці):
- архівація старих сесій після переходу — **варіант А: щоразу окрема згода**; запис у `security/consent.md` (`mcp-archive_session@session_id=<id у нижньому регістрі>`). Перед архівацією — перевірка готовності: усе закомічено й відправлено, підписки PR перенесено, нагадувань на стару сесію немає, пакет пройшов `validate`;
- тест архівації: одноразова сесія `session_01Tu38bsLF3LtnaTyEBifJcU` заархівована за згодою; журнал архівної сесії читається повністю через `list_events` [E: запис згоди в `security/consent.md`, висновок у `docs/learnings.md` 2026-11-28];
- «будуй детектор дрейфу й драбину 1–3» — зроблено: ai-lab#154;
- «завжди застосовуючи актуальні правила працюємо далі»: на старті прочитати вивід «Дрейф правил» SessionStart-хука й діяти за рівнем.

Чекають згоди власника (готові фрази):
1. «Погоджую злиття ai-lab#146, ai-lab#149 і ai-lab#150» (порядок для складених: #149 → #153 → #154; після кожного — перенаправити базу наступного на main).
2. Злиття ai-lab#152 (карта agent-skills) і вибір: «Беремо пункти … з карти agent-skills»; підтвердити ⏭* (API й observability поза скоупом).
3. Хуки `UserPromptSubmit`/`PreCompact` з `docs/continuation/README.md`: «Дозволяю хуки UserPromptSubmit і PreCompact з docs/continuation/README.md».
4. Архівація цієї сесії-попередниці `session_01Tu38bq1W7DqGgVeHvnrU1J` (варіант А): «Дозволяю архівувати сесію session_01Tu38bq1W7DqGgVeHvnrU1J» — після перевірки готовності.
5. Старі пункти без змін: W-14 (авто-об'єднання `consent.md` для чистого дописування), Graphify-пілот, витрата на A/B-пілот `experiments/minimal-code-ab/`, файл повної копії на телефоні, оновлення налаштувань Claude; старша сесія `session_01Tu38bsz6NFQe2UqfD9B6TG` (відключена; архівація — так само окремою згодою).

## Відкриті PR і підписки
[C: стан на 2026-11-28 ~06:45 UTC, звірено `pull_request_read`/REST у сесії-попередниці]
- #146 `multi-provider-ai-orchestration` 1.8.0 — голова `40b532c`, clean, CI зелений, Codex без зауважень.
- #149 `continuation-memory` 1.13.0 + `resume-card.py` — голова `d45b78a`, clean, CI зелений; останнє рев'ю Codex (2 знахідки) виправлено й відповіді дано; нового рев'ю на `d45b78a` ще не було.
- #150 `github-collab` 1.3.0 + `merge-prep.sh` — голова `2240d98`, clean, CI зелений, Codex без зауважень.
- #152 карта agent-skills — голова `d1d1a12`, clean, CI зелений; 7 знахідок Codex виправлено.
- #153 автоперехід (база — гілка #149) — голова `ad96dd5`, clean, CI зелений, Codex без зауважень.
- #154 дрейф правил (база — гілка #153) — голова після цього пакета; повний набір 771/0/0; рев'ю й CI — ще попереду.
- Чужі відкриті PR (не з цієї лінії, лише стежити): #151, #136 (dependabot), #147, #142, #137, #134, #130.
- Підписки: у сесії-попередниці знято після відкриття нової; заплановане нагадування `trig_014LJEbzN1VPGGmNWoodTQZ9` (на попередницю) скасовано — нова сесія заводить своє.
- Інше: «Ранковий огляд» (`trig_01AJn6vYog15JTKRBDCt855D`) 2026-11-27 упав через ліміт використання; 28 із 28 скілів акаунта старші за канон (оновлення — `maintain.py package` + завантаження, дія власника).

## Перехід (робить модель, MCP)
1. `validate` цього файлу → коміт і пуш.
2. `create_session` (та сама гілка/репо) з промптом: «прочитай цей пакет першим кроком».
3. Перенести підписки PR; у старій сесії — останнє повідомлення з посиланням на нову.
4. Ланцюг нащадків обмежений (`get_session` → `lineage.limit`): біля межі — нову сесію відкриває власник.
