#!/usr/bin/env python3
"""R1: збирає тимчасовий плагін для `claude plugin eval` у вказаній теці (поза репо).

Копії навичок (не симлінки: eval може не йти за ними) + кейси з пре-реєстрації.
Запуск: python3 build_plugin.py <тека-призначення> [--set r1|r1b]
        python3 build_plugin.py --overlap   # R1b: збіги 3 слів поспіль «опис ↔ кейси» (код 1, якщо є)

Набір `r1` — 4 кейси R1 (`preregistration.md`); `r1b` — ще 4 відкладені й 2 негативні
(`preregistration-r1b.md`).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILLS = {
    "semantic-router": ROOT / "melania-skills-ecosystem" / "skills" / "semantic-router",
    "translate-uaen": ROOT / ".claude" / "skills" / "translate-uaen",
}
FM = "---\nmax_turns: 8\nmodel: haiku\nallowed_tools: [Read, Glob, Grep, Skill]\n---\n\n"
CASES = {
    "router-a": ("Які навички використати, щоб перекласти README двома мовами й опублікувати картку? Розпиши коротко.",
                 "semantic-router", r"Routing Decision"),
    "router-b": ("Не знаю, з чого почати: треба одночасно дослідити тему й зробити з неї двомовний пост. Що робимо?",
                 "semantic-router", r"Routing Decision"),
    "translate-a": ("Переклади англійською: «Гейт зупиняє незворотні дії без записаної згоди власника.»",
                    "translate-uaen", r"\bgate\b"),
    "translate-b": ("Зроби двомовним (UA/EN) речення «Реєстр розбитих вікон — живий перелік відомого боргу.»",
                    "translate-uaen", r"UA[\s\S]*EN|EN[\s\S]*UA"),
}
# R1b: відкладені позитивні (записані до переписування описів).
HELDOUT = {
    "router-c": ("У мене кілька задач навалом: оновити документацію, перевірити безпеку й підготувати реліз. "
                 "Як розкласти це по навичках?", "semantic-router", r"Routing Decision"),
    "router-d": ("Хочу перетворити свої нотатки на статтю, перекласти її й показати команді. "
                 "Які кроки і чим їх робити?", "semantic-router", r"Routing Decision"),
    "translate-c": ("Як буде англійською \"журнал висновків\"? Потрібен варіант для документації лабораторії.",
                    "translate-uaen", r"learnings|lessons|journal"),
    "translate-d": ("Підготуй EN-версію заголовка \"Безпековий стрижень: механічна опора правил\".",
                    "translate-uaen", r"security|safety"),
}
# R1b: негативні — жодна з двох навичок не мала спрацювати.
NEGATIVE = {
    "neg-math": ("Скільки буде 17 × 23? Лише число.", r"391"),
    "neg-explain": ("Поясни одним реченням, що робить git rebase.", r"rebase|коміт|commit"),
}
ANY_SKILL = "(?:semantic-router|translate-uaen)"


def _words(text: str) -> list[str]:
    return re.findall(r"[\w'’-]+", text.lower())


def overlap() -> int:
    """Збіги трьох слів поспіль між описом навички й текстом кейсів (захист від підгонки)."""
    prompts = [c[0] for c in (*CASES.values(), *HELDOUT.values(), *NEGATIVE.values())]
    grams = {tuple(w[i:i + 3]) for p in prompts for w in [_words(p)] for i in range(len(w) - 2)}
    found = 0
    for name, src in SKILLS.items():
        text = (src / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
        desc = text.split("description:", 1)[1].split("\nlicense:", 1)[0]
        w = _words(desc)
        hits = sorted({" ".join(w[i:i + 3]) for i in range(len(w) - 2) if tuple(w[i:i + 3]) in grams})
        found += len(hits)
        print(f"{name}: збігів 3 слів поспіль — {len(hits)}" + (f": {hits}" if hits else ""))
    return 1 if found else 0


def main(dst: Path, case_set: str = "r1") -> None:
    if dst.exists():
        shutil.rmtree(dst)
    (dst / ".claude-plugin").mkdir(parents=True)
    (dst / ".claude-plugin" / "plugin.json").write_text(json.dumps(
        {"name": "r1-eval", "version": "0.0.1", "description": "R1: тимчасовий плагін для вимірювання навичок"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, src in SKILLS.items():
        shutil.copytree(src.resolve(), dst / "skills" / name,
                        ignore=shutil.ignore_patterns("evals", "scripts", "__pycache__"))
    cases = dict(CASES, **HELDOUT) if case_set == "r1b" else CASES
    for case, (prompt, skill, regex) in cases.items():
        d = dst / "evals" / case / "graders"
        d.mkdir(parents=True)
        (dst / "evals" / case / "prompt.md").write_text(FM + prompt + "\n", encoding="utf-8")
        (d / "skill-fired.md").write_text(
            f"---\ntype: tool_used\ntool: Skill\ninput_match: '\"skill\"\\s*:\\s*\"(?:[\\w-]+:)?{skill}\"'\n---\n",
            encoding="utf-8")
        # JavaScript-регулярка; регістр — полем flags (v1 мав (?i)/(?s) у стилі Python — оцінювач падав).
        (d / "result.md").write_text(f"---\ntype: regex\npattern: '{regex}'\nflags: i\n---\n", encoding="utf-8")
    if case_set == "r1b":
        for case, (prompt, regex) in NEGATIVE.items():
            d = dst / "evals" / case / "graders"
            d.mkdir(parents=True)
            (dst / "evals" / case / "prompt.md").write_text(FM + prompt + "\n", encoding="utf-8")
            # «НЕ мала спрацювати»: min 0 / max 0 і arm both — інакше оцінювач лише показовий.
            (d / "no-skill.md").write_text(
                f"---\ntype: tool_used\ntool: Skill\ninput_match: '\"skill\"\\s*:\\s*\"(?:[\\w-]+:)?{ANY_SKILL}\"'"
                "\nmin: 0\nmax: 0\narm: both\n---\n", encoding="utf-8")
            (d / "result.md").write_text(f"---\ntype: regex\npattern: '{regex}'\nflags: i\n---\n",
                                         encoding="utf-8")
    print(dst)


if __name__ == "__main__":
    if sys.argv[1:] == ["--overlap"]:
        sys.exit(overlap())
    main(Path(sys.argv[1]), sys.argv[3] if sys.argv[2:3] == ["--set"] else "r1")
