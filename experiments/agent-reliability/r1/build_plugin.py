#!/usr/bin/env python3
"""R1: збирає тимчасовий плагін для `claude plugin eval` у вказаній теці (поза репо).

Копії навичок (не симлінки: eval може не йти за ними) + кейси з пре-реєстрації.
Запуск: python3 build_plugin.py <тека-призначення>
"""
from __future__ import annotations

import json
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
                    "translate-uaen", r"(?i)\bgate\b"),
    "translate-b": ("Зроби двомовним (UA/EN) речення «Реєстр розбитих вікон — живий перелік відомого боргу.»",
                    "translate-uaen", r"(?s)UA.*EN|EN.*UA"),
}


def main(dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    (dst / ".claude-plugin").mkdir(parents=True)
    (dst / ".claude-plugin" / "plugin.json").write_text(json.dumps(
        {"name": "r1-eval", "version": "0.0.1", "description": "R1: тимчасовий плагін для вимірювання навичок"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, src in SKILLS.items():
        shutil.copytree(src.resolve(), dst / "skills" / name,
                        ignore=shutil.ignore_patterns("evals", "scripts", "__pycache__"))
    for case, (prompt, skill, regex) in CASES.items():
        d = dst / "evals" / case / "graders"
        d.mkdir(parents=True)
        (dst / "evals" / case / "prompt.md").write_text(FM + prompt + "\n", encoding="utf-8")
        (d / "skill-fired.md").write_text(
            f"---\ntype: tool_used\ntool: Skill\ninput_match: '\"skill\"\\s*:\\s*\"(?:[\\w-]+:)?{skill}\"'\n---\n",
            encoding="utf-8")
        (d / "result.md").write_text(f"---\ntype: regex\npattern: '{regex}'\n---\n", encoding="utf-8")
    print(dst)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
