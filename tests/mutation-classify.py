#!/usr/bin/env python3
"""mutation-classify.py — гейт для гейта (Фаза S5.2).

ПИТАННЯ, НА ЯКЕ ВІН ВІДПОВІДАЄ. У наборі 232 перевірки, і всі зелені. Але чи
ловлять вони хоч щось? Зелений набір на цілому коді не доводить нічого — рівно
як «✓ усі перевірки чисті» при невстановлених сканерах (дефект F-2). Єдиний
спосіб дізнатись — **зламати код навмисно** й побачити, чи набір це помітить.

Мутант, який ПРОЙШОВ перевірки, — це діра в перевірках, а не в коді.

МОДЕЛЬ GOOGLE: мутувати **змінений** код, а не всю базу
(`docs/security/research-2026-07.md` §I.1). Тут мутується лише
`security/spine/classify.py` — серце класифікації, з якого випливає все інше.

БЕЗПЕКА ПРОГОНУ. Мутації застосовуються ТІЛЬКИ до копії в тимчасовій теці.
Робочі файли не чіпаються ніколи — це пряме правило `tests/README.md`, записане
після інциденту, коли канарка на робочому файлі стерла незакомічену роботу.

Запуск: python3 tests/mutation-classify.py [--verbose]
Код виходу: 0 — кожен мутант спійманий · 1 — хтось вижив (діра в перевірках).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "security/spine/classify.py"

# Кожна мутація — правдоподібна помилка, а не випадковий шум: те, що реально
# міг би зробити автор поспіхом. Опис пояснює, ЯКУ саме перевірку вона має
# розбудити — якщо мутант виживе, значить цієї перевірки насправді немає.
MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "правило шляхів вимкнено",
        # Ціль оновлено 2026-10-16: шляхи інструмента тепер збираються по всіх
        # правилах одразу (`tool_hits`), включно з масивом `files`.
        "            if any(_match_path(p, rel, raw) for p in rule.get(\"match_paths\", [])):",
        "            if False:",
        "захищені шляхи (.env, workflows, settings) перестають бути R4",
    ),
    (
        "запис оболонкою в захищений шлях не перевіряється",
        "                bash_hits += [(idx, t, \"write\") for t in _hits(write_tokens, pattern, root, bases)]",
        "                pass",
        "`cat > .github/workflows/x.yml` знову проходить як звичайна команда",
    ),
    (
        "правило команд вимкнено",
        "            if any(needle.lower() in seg and not any(exc in seg for exc in exceptions)",
        "            if False and any(needle.lower() in seg and not any(exc in seg for exc in exceptions)",
        "push --force, rm -rf, --no-verify перестають бути R4",
    ),
    (
        "виняток поглинає все",
        # Ціль оновлено 2026-10-18: виняток тепер перевіряється в кожній частині
        # ланцюжка окремо (рев'ю #91).
        "and not any(exc in seg for exc in exceptions)",
        "and not True",
        "кожна частина ланцюжка вважається винятком — правила-підрядки мовчать",
    ),
    (
        "виняток діє на весь ланцюжок (поведінка до рев'ю #91)",
        "                   for seg in segments):",
        "                   for seg in [exec_part.lower()]):",
        "`--force-with-lease` в одній команді прикриває `--force` у сусідній",
    ),
    (
        "симлінк не розрізається",
        "        if candidate.is_symlink():",
        "        if False:",
        "GhostApproval: рішення ухвалюється за назвою, а не за реальною ціллю",
    ),
    (
        "виконувана частина = порожньо",
        # Ціль оновлено 2026-10-19 (рев'ю #94): тіла heredoc відкидає `_strip_heredocs`.
        "    stripped = _drop_data_quotes(_strip_heredocs(command))",
        "    stripped = \"\"",
        "жодна команда не збігається з правилами — усе стає R2",
    ),
    (
        "ознака виконання ігнорується (підрядкова частина)",
        # Ціль оновлено 2026-10-18 (F-27): ознаку виконання зведено в `_invokes`;
        # підрядками лишились `eval`/`xargs`, оболонки й інтерпретатори — розбором.
        "    if any(inv in _drop_data_quotes(body).lower() for inv in SHELL_INVOKERS):",
        "    if False:",
        "`eval \"rm -rf …\"` стає невидимим — справжній пропуск",
    ),
    (
        "розбір виконавців тексту вимкнено",
        "    return _runs_text(body, command)",
        "    return False",
        "`bash -c`, `bash -lc`, `python3 <<PY`, `echo … | python3` знову проходять як дані",
    ),
    (
        "MCP: незворотне стає читанням",
        # Ціль оновлено 2026-10-16: дієслово шукається і в назві, і в `method`.
        "        if by_name or by_method:",
        "        if False:",
        "злиття PR, деплой, видалення проходять без питань",
    ),
    (
        "MCP: невідоме вважається безпечним",
        "        return Verdict(\"R2\", f\"MCP-інструмент невідомого класу ({tool_name})\",",
        "        return Verdict(\"R0\", f\"MCP-інструмент невідомого класу ({tool_name})\",",
        "незнайомий інструмент отримує найнижчий рівень",
    ),
    (
        "запис поза репо дозволено",
        "        if outside:\n            return Verdict(\"R4\", \"запис ПОЗА межами репозиторію\",",
        "        if False:\n            return Verdict(\"R4\", \"запис ПОЗА межами репозиторію\",",
        "будь-який шлях поза проєктом стає звичайною правкою",
    ),
    (
        "операції запису не рахуються",
        # Ціль оновлено 2026-09-29: у цьому місці `WRITE_OPS` став `CHAIN_OPS`
        # (перенесення рядка — теж роздільник ланцюжка). Мутант цілить у
        # перевірку ланцюжка всередині `is_pure_read`: без неї читальний
        # префікс знову ховає дію, що йде другим рядком.
        # Ціль оновлено вдруге 2026-10-16: перевірка ланцюжка тепер іде по
        # кожній ланці конвеєра (W-18 б).
        "        if not link or any(op in link for op in CHAIN_OPS):",
        "        if not link:",
        "читальний префікс знову ховає дію в ланцюжку",
    ),
    # ── Хвиля 2026-10-16/17: справжня дія і справжня ціль ───────────────────
    (
        "ланка конвеєра не перевіряється на читальний префікс",
        "        if not any(link == pref or link.startswith(pref + \" \") for pref in prefixes):",
        "        if False:",
        "будь-яка команда стає «чистим читанням» і пропускає правила-підрядки",
    ),
    (
        "детектор `gh api` вимкнено",
        "        if command and rule.get(\"match_gh_api_write\"):",
        "        if False:",
        "злиття PR і зміна публічності через `gh api` знову R2 (F-20)",
    ),
    (
        "`method` MCP не читається",
        "    method = str(tool_input.get(\"method\") or \"\").strip().lower()",
        "    method = \"\"",
        "незворотна дія в аргументі `method` знову R2 (F-20)",
    ),
    (
        "дефіс у назві MCP не нормалізовано",
        "    norm = text.lower().replace(\"-\", \"_\")",
        "    norm = text.lower()",
        "`notion-delete-pages` знову R2 (F-20)",
    ),
    (
        "масив `files` ігнорується",
        "    for item in tool_input.get(\"files\") or []:",
        "    for item in []:",
        "воркфлоу через `push_files` знову R2",
    ),
    (
        "читання оболонкою не перевіряється",
        "                if rule.get(\"on_read\"):",
        "                if False:",
        "`cat .env` знову R0 (F-21)",
    ),
    (
        "`on_read` ігнорується для інструментів читання",
        "        if read_tool and not rule.get(\"on_read\"):",
        "        if read_tool:",
        "`Read .env` і MCP-читання секрету знову проходять",
    ),
    (
        "абсолютний шлях не зводиться до відносного",
        "            out.append((_rel(root, norm), form))",
        "            out.append((norm, form))",
        "запис оболонкою за абсолютним шляхом знову R2",
    ),
    (
        "друк назви файла вважається читанням",
        "        if cmd in _PRINTERS:",
        "        if False:",
        "`echo '….env'` дає R4 — хибна тривога на згадку",
    ),
    (
        "візерунок пошуку вважається файлом",
        "            if positional == 1 and not from_flags:",
        "            if False:",
        "`grep '.env' docs/` дає R4 — хибна тривога на згадку",
    ),
    # ── Рев'ю #91 (2026-10-18): кожне виправлення має свого мисливця ────────
    (
        "фоновий `&` не рахується",
        "    if \"&\" in stripped:",
        "    if False:",
        "`cat README.md & git push --force …` знову R0",
    ),
    (
        "підстановка в подвійних лапках вважається даними",
        "        return s if s.startswith('\"') and (\"$(\" in s or \"`\" in s) else \" \"",
        "        return \" \"",
        "`ls \"$(git push --force …)\"` знову R0",
    ),
    (
        "підстановки не розбираються як команди",
        "    for segment in [body] + _substitutions(body):",
        "    for segment in [body]:",
        "`echo \"$(cat .env)\"` знову не читання",
    ),
    (
        "`gh` упізнається лише як голе слово",
        "            if cmd in _PRINTERS or os.path.basename(tok) != \"gh\" or \\",
        "            if cmd in _PRINTERS or tok != \"gh\" or \\",
        "`/повний/шлях/gh api -X PUT …` знову R2",
    ),
    (
        "кластер коротких прапорців `gh api` не розбирається",
        "        elif re.match(r\"^-[A-Za-z]{2,}\", tok):          # кластер: `-iX PUT`, `-XPUT`",
        "        elif False:",
        "`gh api -iX PUT …` знову читання",
    ),
    (
        "тіло heredoc в оболонку не розбирається для `gh api`",
        "        texts += [line for chunk in _heredoc_bodies(command) for line in chunk.splitlines()]",
        "        pass",
        "`bash <<EOF … gh api -X PUT … EOF` знову R2",
    ),
    (
        "прихований GraphQL-запит вважається читанням",
        "                 or _query_hidden(text))",
        "                 or False)",
        "`gh api graphql -f query=\"$Q\"` знову R2",
    ),
    (
        "`cd` не враховується",
        "        bases += [cur, d if os.path.isabs(d) else os.path.normpath(os.path.join(base, d))]",
        "        pass",
        "`cd .claude && echo x > settings.json` знову R2",
    ),
    (
        "`#` посеред слова знову коментар",
        "        lex.commenters = \"\"                     # коментарі вже вирізано за правилами bash",
        "        pass",
        "`cat x# .env` знову R0",
    ),
    (
        "обгортка `_…_` на назвах інструментів",
        "    if bare:",
        "    if True:",
        "`get_latest_release` знову R4 і заблоковано назавжди",
    ),
    (
        "`glob` інструмента пошуку не перевіряється",
        "    for piece in re.split(r\"[{},\\s]+\", str(tool_input.get(\"glob\") or \"\")):",
        "    for piece in []:",
        "`Grep glob=.env` знову R0",
    ),
    (
        "`поле=@файл` не розбирається",
        "    if \"=@\" in token:",
        "    if False:",
        "`gh api -F q=@.env` знову не читання секрету",
    ),
    (
        "фільтр файлів (`-g`, `--include`) не перевіряється",
        "            if tok in _FILE_FILTER_FLAGS:",
        "            if False:",
        "`rg -g .env KEY` знову R0",
    ),
    (
        "прикріплений візерунок не враховується",
        "            if tok.startswith(\"--regexp=\") or short == \"-e\":",
        "            if False:",
        "`grep -eKEY .env` знову R0",
    ),
    (
        "here-string вважається файлом",
        "        if tok == \"<<<\":                        # here-string: далі РЯДОК, а не файл",
        "        if False:",
        "`grep KEY <<< .env` дає R4 — хибна тривога",
    ),
    # ── 2026-10-18: полювання на форми дії (F-25…F-28) ───────────────────────
    (
        "кластер прапорців виконавця не розбирається",
        "                if ch in spec.get(\"code\", \"\"):",
        "                if ch in spec.get(\"code\", \"\") and len(letters) == 1:",
        "`bash -lc`, `sh -xc`, `python3 -Bc` знову проходять (лише голий `-c`)",
    ),
    (
        "аргумент прапорця вважається операндом",
        "                    k += 1                            # окремий аргумент (`-o pipefail`)",
        "                    pass",
        "`bash -euo pipefail -c …`: «pipefail» стає скриптом, `-c` не видно",
    ),
    (
        "номер дескриптора вважається операндом",
        "        if tok.isdigit() and k < len(args) and _is_redirect(args[k]):",
        "        if False:",
        "`bash 2>/dev/null <<EOF … EOF`: «2» стає скриптом, тіло — даними",
    ),
    (
        "виконавець без скрипта не читає stdin",
        "    return infer_stdin and kind != \"c-flag\" and not operand",
        "    return False",
        "`cat <<EOF | bash`, `echo … | python3`, `python3 <<PY` знову проходять",
    ),
    (
        "сегмент читання не відсіюється",
        "            if _data_segment(seg):\n                continue\n"
        "            head = _command_index(seg)",
        "            head = _command_index(seg)",
        "`echo bash -c \"…\"` стає R4 — виконавець як аргумент читання вважається виконанням",
    ),
    (
        "повернувся зайвий збіг «python3 -»",
        "SHELL_INVOKERS = (\"eval \", \"xargs \")",
        "SHELL_INVOKERS = (\"eval \", \"xargs \", \"python3 -\")",
        "`python3 -I tool.py \"<згадка>\"` знову R4 — аргумент скрипта стає «кодом»",
    ),
    (
        "heredoc ковтає решту рядка відкривача (поведінка до F-28)",
        r'''_HEREDOC = re.compile(r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*\n).*?^\3$", re.DOTALL | re.MULTILINE)''',
        r'''_HEREDOC = re.compile(r"(<<-?\s*(['\"]?)(\w+)\2).*?^\3$", re.DOTALL | re.MULTILINE)''',
        "`cat <<'EOF' | bash` знову R0 — ` | bash` зникає разом із тілом",
    ),
    (
        "прапорці запису читального префікса ігноруються",
        # Ціль оновлено 2026-10-19: прапорці звіряються за словами оболонки (рев'ю #94).
        "    if any(_write_flag_hit(\" \".join(seg), write_flags)",
        "    if False and any(_write_flag_hit(\" \".join(seg), write_flags)",
        "`git branch -D`, `git diff --output=` знову R0 «читання»",
    ),
    (
        "короткий кластер прапорців запису не розбирається",
        "            elif len(tok) > 1 and tok[0] == \"-\" and any(ch in shorts for ch in tok[1:]):",
        "            elif tok in {\"-\" + s for s in shorts}:",
        "`git branch -dr origin/x` знову R0 (ловиться лише голий `-d`)",
    ),
    (
        "видалення гілки на сервері не розбирається",
        "        if command and rule.get(\"match_git_push_delete\") and _git_push_deletes(command):",
        "        if False:",
        "`git push origin --delete x` знову R2 — видалення без згоди",
    ),
    (
        "refspec `:гілка` не вважається видаленням",
        "        if arg.startswith((\":\", \"+:\")) and len(arg.lstrip(\"+\")) > 1:",
        "        if False:",
        "`git push origin :x` знову R2",
    ),
    (
        "код у лапках не розкривається для `git push`",
        r'''    texts = [re.sub(r"['\"\\,\[\]]", " ", command)] if code''',
        "    texts = [command] if code",
        "`bash -lc \"git push origin --delete x\"` знову R2",
    ),
    (
        "сухий прогін не виключено (хибна тривога)",
        "    if dry:\n        return False",
        "    if False:\n        return False",
        "`git push --dry-run origin --delete x` дає R4, хоча нічого не видаляє",
    ),
    (
        "процес-підстановка не відділяє команду",
        "            seg.append(tok)\n            segs.append((seg, prev))\n            seg, prev = [], tok\n            continue\n",
        "            seg.append(tok)\n            continue\n",
        "команда всередині `<(…)` знову не має своєї позиції команди",
    ),
    (
        "злиплі оператори не розщеплюються",
        "            out += _split_ops(word)",
        "            out += [word]",
        "`|>` / `;>` — оператор і перенаправлення зливаються в одне слово",
    ),
    (
        "провідне перенаправлення не пропускається",
        "        elif _is_redirect(seg[i]):\n            i += 2\n",
        "",
        "`| ( >/dev/null bash )` — виконавець після перенаправлення не на позиції команди",
    ),
    (
        "схожі назви виконавців не розпізнаються",
        '    return next((kind for rx, kind in _LOOSE_RUNNERS if rx.fullmatch(name)), ""), True',
        '    return "", True',
        "`ts-node -e …`, `ipython -c …` знову проходять як дані",
    ),
    (
        "схожа назва без явного коду вважається такою, що читає stdin",
        "infer_stdin=(i == head or fed) and not loose)",
        "infer_stdin=(i == head or fed))",
        "хибна тривога на команду, чия назва лише схожа на виконавця",
    ),
    (
        "виконавець-аргумент читає stdin",
        "infer_stdin=(i == head or fed) and not loose)",
        "infer_stdin=not loose)",
        "`npm install node` — хибне R4 на виконавця-аргумент",
    ),
    (
        "конвеєр не робить виконавця читачем stdin (поведінка до 2026-10-23)",
        "infer_stdin=(i == head or fed) and not loose)",
        "infer_stdin=i == head and not loose)",
        "`| strace bash`, `| sudo --user root bash` знову проходять",
    ),
    (
        "`command -v` вважається запуском",
        "        if _cmd_name(seg[i]) == \"command\" and i + 1 < n and seg[i + 1] in (\"-v\", \"-V\"):\n"
        "            return n                                  # `command -v bash` — пошук, не запуск\n",
        "",
        "`command -v bash && git commit -m \"…\"` — хибне R4 на повідомлення коміту",
    ),
    (
        "модуль-виконавець коду не розпізнається",
        '                    return module in spec.get("code_modules", ()), True, False',
        "                    return False, True, False",
        "`python3 -m timeit \"…\"` знову проходить як дані",
    ),
    (
        "find з -fprint/-fls/-okdir вважається читанням",
        '        return not any(t.startswith(("-exec", "-ok", "-delete", "-fprint", "-fls"))',
        '        return not any(t in ("-exec", "-ok", "-delete") and t.startswith(("-exec", "-ok", "-delete", "-fprint", "-fls"))',
        "`find . -okdir …` / `-fprint` знову «дані»",
    ),
    (
        "--no-dry-run не скасовує сухий прогін",
        '        elif arg == "--no-dry-run":\n            dry = False\n',
        "",
        "сухий прогін, скасований пізнішим прапорцем, знову ховає видалення",
    ),
    (
        "короткі літери git push беруть значення -o",
        '    return arg[1:].split("o", 1)[0]',
        "    return arg[1:]",
        "літера зі значення `-o…` вважається сухим прогоном — видалення без згоди",
    ),
    (
        "сегмент-дані пропускається навіть у коді",
        "            if _data_segment(seg) and not (code and piped):",
        "            if _data_segment(seg):",
        "`echo \"…\" | bash` — сегмент `echo`, що ПОДАЄ код, ховає видалення гілки",
    ),
    (
        "сегмент-читач без конвеєра в коді не пропускається (поведінка до 2026-10-23)",
        "            if _data_segment(seg) and not (code and piped):",
        "            if _data_segment(seg) and not code:",
        "`echo \"<видалення>\"; python3 -c …` — хибне R4 на друк",
    ),
    (
        "скорочення прапорців видалення не приймаються",
        "        if any(len(flag) >= k and full.startswith(flag) for full, k in _PUSH_DELETE_LONG):",
        "        if flag in (\"--delete\", \"--prune\", \"--mirror\"):",
        "`git push origin --del x` знову R2",
    ),
    (
        "мінімальна довжина скорочення ігнорується",
        "        if any(len(flag) >= k and full.startswith(flag) for full, k in _PUSH_DELETE_LONG):",
        "        if any(full.startswith(flag) for full, k in _PUSH_DELETE_LONG):",
        "неоднозначне `--pr` вважається видаленням — хибна тривога",
    ),
    (
        "список аргументів у коді не розкривається для git push",
        r'''    texts = [re.sub(r"['\"\\,\[\]]", " ", command)] if code''',
        r'''    texts = [re.sub(r"['\"\\]", " ", command)] if code''',
        "видалення гілки списком аргументів `[\"git\",\"push\",…]` знову R2",
    ),
    (
        "дослівні прапорці запису не ловляться",
        "            if tok in exact:\n                return True\n",
        "",
        "`find . -fprint f`, `git remote -v add` знову R0",
    ),
    (
        "скорочення довгого прапорця не ловиться",
        "                if flag in longs or (len(flag) >= 4 and any(f.startswith(flag) for f in longs)):",
        "                if flag in longs:",
        "`git branch --del x` знову R0",
    ),
    (
        "ціль --output не потрапляє в правила шляхів",
        "                    if name == \"git\" and len(flag) >= 5 and \"--output\".startswith(flag):",
        "                    if False:",
        "`git diff --output=<захищений шлях>` — запис без R4",
    ),
    (
        "ціль find -fprint не потрапляє в правила шляхів",
        "                    elif name == \"find\" and tok in _FIND_FILE_FLAGS:",
        "                    elif False:",
        "`find . -fprint <захищений шлях>` — запис без R4",
    ),
    (
        "--output шукається в чужих командах (поведінка до 2026-10-23)",
        "                    if name == \"git\" and len(flag) >= 5 and \"--output\".startswith(flag):",
        "                    if len(flag) >= 5 and \"--output\".startswith(flag):",
        "`echo \"--output=<шлях>\"` — хибне R4 на згадку",
    ),
    (
        "-fls шукається в чужих командах (поведінка до 2026-10-23)",
        "                    elif name == \"find\" and tok in _FIND_FILE_FLAGS:",
        "                    elif tok in _FIND_FILE_FLAGS:",
        "`ls -fls <захищений шлях>` — хибне R4 на перелік теки",
    ),
    (
        "скорочення --out не приймається",
        "                    if name == \"git\" and len(flag) >= 5 and \"--output\".startswith(flag):",
        "                    if name == \"git\" and flag == \"--output\":",
        "`git log --out=<захищений шлях>` — запис без R4",
    ),
    (
        "ціль прапорця в коді не розкривається",
        "            for s in (range(len(seg)) if code else [_command_index(seg)]):",
        "            for s in [_command_index(seg)]:",
        "`bash -c \"git diff --output=<шлях>\"` — запис без R4",
    ),
    (
        "heredoc без лапок губить підстановки",
        r'''        return m.group(1) + "".join(f"$({sub})\n" for sub in _substitutions(body, heredoc=True))''',
        "        return m.group(1)",
        "виконувана `$(…)` у heredoc без лапок зникає з розбору",
    ),
    (
        "одинарні лапки в тілі heredoc вважаються лапками (поведінка до 2026-10-23)",
        "_substitutions(body, heredoc=True))",
        "_substitutions(body))",
        "`'$(…)'` у тілі heredoc без лапок зникає з розбору",
    ),
    (
        "тіло heredoc-літерала перевіряється на прапорці запису",
        "_sh_segments(_sh_tokens(_strip_heredocs(command)))):",
        "_sh_segments(_sh_tokens(command))):",
        "`cat <<'EOF'⏎git branch -D x⏎EOF` — друк стає R2",
    ),
    (
        "перенесення рядка `\\⏎` не склеюється",
        r'''    command = re.sub(r"\\\r?\n", "", command)''',
        "    command = command",
        "команда, розірвана `\\⏎`, знову обходить правило-команду (F-29)",
    ),
    (
        "`\\⏎` замінюється пробілом (поведінка до 2026-10-23)",
        r'''    command = re.sub(r"\\\r?\n", "", command)''',
        r'''    command = re.sub(r"\\\r?\n", " ", command)''',
        "слово, розірване `\\⏎` (`--for\\⏎ce`), обходить правило-команду",
    ),
    (
        "пробіли в сегментах не зводяться",
        '    segments = [" ".join(seg.split()) for seg in segments]',
        "    segments = segments",
        "два пробіли чи табуляція знову обходять правило-команду (F-29)",
    ),
    (
        "код у лапках не дає сегментів для правил-команд",
        r'''        segments += re.split(r"&&|\|\||[;&\n]", re.sub(r"['\"\\,\[\]]", " ", exec_part.lower()))''',
        "        pass",
        "правило-команда не бачить дії всередині коду в лапках",
    ),
]

# Перевірки, якими полюємо на мутантів. Кожна має відпрацювати в пісочниці
# без жодного файлу лабораторії, крім скопійованих.
# Порядок — від найшвидшого: `hunt()` зупиняється на першому, хто спіймав, тож
# дешеві приклади йдуть першими, а дорогий property-тест — для тих, хто вижив
# (37 мутантів зі старим порядком — понад 2 хвилини, 2026-10-18).
HUNTERS = [
    ("probe-classify.py", []),
    ("probe-mcp-and-quotes.py", []),
    ("property-classify.py", ["--cases", "60"]),
]


def build_sandbox(tmp: Path) -> Path:
    """Копія лише того, що потрібно перевіркам. Робочі файли недоторкані."""
    sandbox = tmp / "repo"
    (sandbox / "tests").mkdir(parents=True)
    shutil.copytree(ROOT / "security", sandbox / "security",
                    ignore=shutil.ignore_patterns("audit", "tests"))
    for name, _ in HUNTERS:
        shutil.copy(ROOT / "tests" / name, sandbox / "tests" / name)
    return sandbox


def hunt(sandbox: Path) -> tuple[bool, str]:
    """Чи спіймав хоч один мисливець? Повертає (спіймано, ким саме)."""
    for name, extra in HUNTERS:
        res = subprocess.run([sys.executable, str(sandbox / "tests" / name), *extra],
                             capture_output=True, text=True, cwd=sandbox, timeout=180)
        if res.returncode != 0:
            return True, name
    return False, ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv[1:])

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sandbox = build_sandbox(tmp)
        original = (sandbox / TARGET).read_text(encoding="utf-8")

        # Контроль: на ЦІЛОМУ коді мисливці мають мовчати. Якщо ні — вони
        # реагують на щось інше, і подальші результати нічого не варті.
        caught, who = hunt(sandbox)
        if caught:
            print(f"  ❌ на цілому коді впав {who} — прогін недійсний")
            return 1

        survived: list[tuple[str, str]] = []
        killed = 0
        for name, old, new, effect in MUTATIONS:
            if old not in original:
                print(f"  ⚠️  мутація «{name}» не застосовна — цільовий рядок змінився")
                survived.append((name, "цільовий рядок не знайдено"))
                continue
            (sandbox / TARGET).write_text(original.replace(old, new, 1), encoding="utf-8")
            caught, who = hunt(sandbox)
            (sandbox / TARGET).write_text(original, encoding="utf-8")
            if caught:
                killed += 1
                if args.verbose:
                    print(f"  ✅ {name} — спіймав {who}")
            else:
                survived.append((name, effect))

    total = len(MUTATIONS)
    if survived:
        print(f"  ❌ мутанти: {killed}/{total} спіймано, {len(survived)} ВИЖИЛО")
        for name, effect in survived:
            print(f"     - «{name}» пройшов усі перевірки → {effect}")
        print("     Мутант, що вижив, — діра в ПЕРЕВІРКАХ, не в коді.")
        return 1
    print(f"  мутаційне тестування: {killed}/{total} мутантів спіймано")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
