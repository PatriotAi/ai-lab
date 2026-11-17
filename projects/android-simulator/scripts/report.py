#!/usr/bin/env python3
"""report.py — розбір результатів прогону і звіт, зручний для телефона.

Команди:
  analyze <results>                 → <results>/verdict.json (падіння, «завис», чи встановилось)
  verdict <results> [--fail-on-crash] → код 1, якщо прогін провалено
  summary <root> <base_url> [--title T] → Markdown-звіт для Job Summary / коментаря в PR

Одна відповідальність: прочитати те, що зібрав run-on-emulator.sh, і
сказати людськими словами, що сталося. Нічого не запускає на пристрої.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import quote

FATAL_RE = re.compile(r"FATAL EXCEPTION:.*?\n.*?Process: ([\w.:]+)", re.S)
NATIVE_RE = re.compile(r">>> ([\w.:]+) <<<")
ANR_RE = re.compile(r"ANR in ([\w.:]+)")
MONKEY_CRASH_RE = re.compile(r"// CRASH: ([\w.:]+)")
MONKEY_ANR_RE = re.compile(r"// NOT RESPONDING: ([\w.:]+)")


def read_env(path: Path) -> dict:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                parts = shlex.split(v)
                out[k] = parts[0] if parts else ""
            except ValueError:
                out[k] = v
    return out


def _txt(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def find_problems(crash_log: str, logcat: str, monkey_log: str, package: str) -> dict:
    """Знайти падіння (crash) і зависання (ANR) саме цієї цілі."""
    def mine(proc: str) -> bool:
        return not package or proc.split(":")[0] == package

    crashes = [p for p in FATAL_RE.findall(crash_log) if mine(p)]
    crashes += [p for p in NATIVE_RE.findall(crash_log) if mine(p)]
    crashes += [p for p in MONKEY_CRASH_RE.findall(monkey_log) if mine(p)]
    anrs = [p for p in ANR_RE.findall(logcat) if mine(p)]
    anrs += [p for p in MONKEY_ANR_RE.findall(monkey_log) if mine(p)]
    first = ""
    for block in re.split(r"(?=^.*FATAL EXCEPTION)", crash_log, flags=re.M):
        m = re.search(r"Process: ([\w.:]+)", block)
        if "FATAL EXCEPTION" in block and m and mine(m.group(1)):
            first = "\n".join(block.strip().splitlines()[:12])
            break
    return {"crashes": len(crashes), "anrs": len(anrs), "first_crash": first}


def analyze(results: Path) -> dict:
    st = read_env(results / "status.env")
    tgt = read_env(results.parent / "target.env")
    device = read_env(results / "device.txt")
    package = tgt.get("PACKAGE", "")
    probs = find_problems(_txt(results / "crash.txt"), _txt(results / "logcat.txt"),
                          _txt(results / "monkey.txt"), package)
    v = {
        "target": tgt.get("DISPLAY_TARGET", ""),
        "package": package,
        "app_label": tgt.get("APP_LABEL", ""),
        "app_version": tgt.get("APP_VERSION", ""),
        "native_abis": tgt.get("NATIVE_ABIS", ""),
        "prepare_error": tgt.get("PREPARE_ERROR", ""),
        "installed": st.get("INSTALLED") == "1",
        "launched": st.get("LAUNCHED") == "1",
        "alive": st.get("ALIVE", ""),
        "install_error": st.get("INSTALL_ERROR", ""),
        "flow_rc": st.get("FLOW_RC", ""),
        "browser": st.get("BROWSER", ""),
        "device": device,
        **probs,
    }
    (results / "verdict.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    return v


def failed(v: dict, fail_on_crash: bool) -> list[str]:
    why = []
    if v.get("prepare_error"):
        why.append(f"ціль не підготовлено: {v['prepare_error']}")
    elif not v.get("installed"):
        why.append(f"не встановилось ({v.get('install_error') or 'див. install.txt'})")
    elif not v.get("launched"):
        why.append("не відкрилось")
    if v.get("flow_rc") not in ("", "0"):
        why.append("сценарій дій не пройшов")
    if fail_on_crash and (v.get("crashes") or v.get("anrs")):
        why.append(f"падінь: {v.get('crashes', 0)}, зависань: {v.get('anrs', 0)}")
    return why


def headline(v: dict, fail_on_crash: bool = True) -> str:
    why = failed(v, fail_on_crash)
    if why:
        return "❌ Проблема: " + "; ".join(why)
    extra = ""
    if v.get("crashes") or v.get("anrs"):
        extra = f" (але падінь: {v['crashes']}, зависань: {v['anrs']})"
    return "✅ Працює: відкрилось" + (", сценарій пройдено" if v.get("flow_rc") == "0" else "") + extra


def summary(root: Path, base_url: str, title: str) -> str:
    lines = [f"## 📱 {title}", ""]
    for run in sorted(p for p in root.iterdir() if p.is_dir()):
        res = run / "results"
        vf = res / "verdict.json"
        if not vf.exists():
            lines += [f"### {run.name}", "", "❌ Прогін не дійшов до кінця — див. журнал кроку.", ""]
            continue
        v = json.loads(vf.read_text(encoding="utf-8"))
        url = f"{base_url}/{run.name}"
        d = v.get("device", {})
        what = v.get("app_label") or v.get("package") if v.get("package") != "com.android.chrome" else v.get("target")
        lines += [f"### {run.name}", "", f"**{headline(v)}**", ""]
        lines.append(f"- Що перевіряли: `{what or v.get('target')}`" + (f" {v['app_version']}" if v.get("app_version") else ""))
        lines.append(f"- Телефон: {d.get('model', '?')}, Android {d.get('android', '?')} (API {d.get('api', '?')}), "
                     f"екран {d.get('screen', '?')}")
        if v.get("browser"):
            lines.append(f"- Браузер: {v['browser']}")
        if v.get("native_abis"):
            lines.append(f"- Код застосунку під процесори: {v['native_abis']} (пристрій: {d.get('abi', '?')})")
        if v.get("alive") != "":
            lines.append("- Наприкінці застосунок " + ("ще працював ✅" if v.get("alive") == "1" else "уже закрився ⚠️"))
        lines.append(f"- Падінь: {v.get('crashes', 0)} · зависань: {v.get('anrs', 0)}")
        if v.get("first_crash"):
            lines += ["", "<details><summary>Перше падіння (технічні деталі)</summary>", "", "```",
                      v["first_crash"], "```", "</details>"]
        lines.append("")
        if (res / "preview.gif").exists():
            lines += [f'<img src="{url}/results/preview.gif" width="260" alt="відео прогону">', ""]
        shots = sorted((res / "shots").glob("*.png")) + sorted((res / "maestro").rglob("*.png"))
        if shots:
            imgs = " ".join(
                f'<a href="{url}/results/{quote(s.relative_to(res).as_posix())}">'
                f'<img src="{url}/results/{quote(s.relative_to(res).as_posix())}" width="160" alt="{s.stem}"></a>'
                for s in shots[:12])
            lines += [imgs, ""]
        links = []
        for vid in sorted((res / "video").glob("*.mp4")):
            links.append(f"[🎬 відео {vid.stem}]({url}/results/video/{vid.name})")
        for name, label in (("logcat.txt", "📄 журнал"), ("crash.txt", "💥 падіння"), ("install.txt", "📦 встановлення")):
            if (res / name).exists() and (res / name).stat().st_size:
                links.append(f"[{label}]({url}/results/{name})")
        if links:
            lines += [" · ".join(links), ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "analyze":
        v = analyze(Path(argv[1]))
        print(headline(v))
        return 0
    if len(argv) >= 2 and argv[0] == "verdict":
        vf = Path(argv[1]) / "verdict.json"
        v = json.loads(vf.read_text(encoding="utf-8")) if vf.exists() else {"prepare_error": "немає результатів"}
        why = failed(v, "--fail-on-crash" in argv)
        print(headline(v, "--fail-on-crash" in argv))
        return 1 if why else 0
    if len(argv) >= 3 and argv[0] == "summary":
        title = argv[argv.index("--title") + 1] if "--title" in argv else "Віртуальний смартфон"
        sys.stdout.write(summary(Path(argv[1]), argv[2].rstrip("/"), title))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
