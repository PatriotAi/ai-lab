#!/usr/bin/env python3
"""Канарки scripts/local-continuity-pack.py (CLAUDE.md §11): чистий пакет мусить відновлюватись,
зламаний — падати. Тимчасові git-репо, без мережі. Код 1 при будь-якому провалі."""
import hashlib, json, shutil, subprocess, sys, tarfile, tempfile
from pathlib import Path

PACK = Path(__file__).resolve().parent.parent / "scripts" / "local-continuity-pack.py"
fails = 0


def sh(*a, cwd=None):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def run(*a):
    return sh(sys.executable, "-I", str(PACK), *a).returncode


def expect(name, got, want):
    global fails
    fails += got != want
    print(f"{'✅' if got == want else '❌'} {name}: {got} (очікувано {want})")


def repack(src_tar, tmp, mutate, name):
    d = Path(tmp) / name
    d.mkdir()
    with tarfile.open(src_tar) as t:
        t.extractall(d, filter="data")
    root = next(d.iterdir())
    mutate(root)
    out = Path(tmp) / f"{name}.tar.gz"
    with tarfile.open(out, "w:gz") as t:
        t.add(root, arcname=root.name)
    return str(out)


with tempfile.TemporaryDirectory() as tmp:
    r = Path(tmp) / "repo"
    r.mkdir()
    g = lambda *a: sh("git", "-c", "user.email=t@example.com", "-c", "user.name=t", *a, cwd=r)
    g("init", "-q", "-b", "main"); (r / "a.txt").write_text("1\n"); g("add", "a.txt"); g("commit", "-q", "-m", "1")
    g("checkout", "-q", "-b", "side"); (r / "b.txt").write_text("2\n"); g("add", "b.txt"); g("commit", "-q", "-m", "2")
    g("checkout", "-q", "main"); (r / "a.txt").write_text("змінено\n"); (r / "new.txt").write_text("поза git\n")
    out = Path(tmp) / "out"; out.mkdir()
    expect("make", run("make", str(out), str(r)), 0)
    tar = str(next(out.glob("*.tar.gz")))
    expect("verify чистого пакета", run("verify", tar), 0)
    with tarfile.open(tar) as t:
        names = {Path(n).name for n in t.getnames()}
    expect("є патч незбережених змін і архів нових файлів",
           {"repo.uncommitted.patch", "repo.untracked.tar.gz"} <= names, True)

    def corrupt(root):
        b = root / "repo.bundle"; data = bytearray(b.read_bytes()); data[60] ^= 0xFF; b.write_bytes(bytes(data))
    expect("пошкоджений bundle — падає", run("verify", repack(tar, tmp, corrupt, "c1")), 1)

    def partial(root):  # bundle лише з main: гілки side нема; контрольну суму «чесно» підправлено
        sh("git", "bundle", "create", str(root / "repo.bundle"), "main", cwd=r)
        m = json.loads((root / "MANIFEST.json").read_text())
        m["files"]["repo.bundle"] = hashlib.sha256((root / "repo.bundle").read_bytes()).hexdigest()
        (root / "MANIFEST.json").write_text(json.dumps(m))
    expect("bundle без гілки side — падає", run("verify", repack(tar, tmp, partial, "c2")), 1)

    def missing(root):
        (root / "repo.uncommitted.patch").unlink()
    expect("зниклий файл пакета — падає", run("verify", repack(tar, tmp, missing, "c3")), 1)

    shallow = Path(tmp) / "shallow"
    sh("git", "clone", "-q", "--depth", "1", f"file://{r}", str(shallow))
    out2 = Path(tmp) / "out2"; out2.mkdir()
    expect("неглибокий клон — відмова збирати", run("make", str(out2), str(shallow)), 1)

print(f"local-continuity canary: {'усе гаразд' if not fails else f'{fails} провал(ів)'}")
sys.exit(1 if fails else 0)
