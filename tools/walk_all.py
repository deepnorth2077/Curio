#!/usr/bin/env python3
"""决定这次跑哪些模块的走查，然后逐个跑（#140 第 4 条）。CI 的「走查」job 调用它。

- 骨架 starter.html、tools/walklib.py、tools/walks/smoke.py 有改动 → 全部动手探索模块；
- 否则只跑改过的模块：content/activities/act.simulation.<名字>/ 或 tools/walks/<活动 id>.py 有改动。
- 有专属走查（tools/walks/<活动 id>.py）用专属的，没有用冒烟走查。截图按模块分目录。

改动 = 相对 origin/<BASE_REF，默认 main> 的分叉点，到当前工作区（含没提交的和新文件）。
用法：python tools/walk_all.py [--out 截图目录] [--all]
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORE = (".claude/skills/curio-anatomy/references/starter.html", "tools/walklib.py", "tools/walks/smoke.py")
ACT = "content/activities/"
WALKS = "tools/walks/"


def select(changed, modules, everything=False):
    """changed：改动的文件路径；modules：现有模块的活动 id。返回要跑的活动 id（有序）。"""
    if everything or any(p in CORE for p in changed):
        return sorted(modules)
    hit = set()
    for p in changed:
        if p.startswith(ACT):
            hit.add(p[len(ACT):].split("/")[0])
        elif p.startswith(WALKS) and p.endswith(".py"):
            hit.add(p[len(WALKS):-3])
    return sorted(m for m in modules if m in hit)


def modules(repo=REPO):
    return sorted(d.name for d in (repo / ACT).glob("act.simulation.*") if (d / "index.html").is_file())


def script_for(aid, repo=REPO):
    own = repo / WALKS / f"{aid}.py"
    return own if own.is_file() else repo / WALKS / "smoke.py"


def changed_files(repo=REPO, base=None):
    base = base or "origin/" + os.environ.get("BASE_REF", "main")
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    mb = git("merge-base", base, "HEAD")
    if mb.returncode != 0:
        raise RuntimeError(f"无法和 {base} 比较：{mb.stderr.strip()}")
    files = git("diff", "--name-only", mb.stdout.strip()).stdout.split() + git("ls-files", "--others", "--exclude-standard").stdout.split()
    return sorted(set(files))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "curio-walks"))
    ap.add_argument("--all", action="store_true", help="不看改动，全部跑")
    a = ap.parse_args(argv)
    todo = select([] if a.all else changed_files(), modules(), a.all)
    if not todo:
        print("这次没有要走查的模块")
        return 0
    bad = []
    for aid in todo:
        script = script_for(aid)
        print(f"\n######## {aid}（{script.name}）", flush=True)
        t0 = time.monotonic()
        rc = subprocess.run([sys.executable, str(script), str(REPO / ACT / aid / "index.html"), str(Path(a.out) / aid)]).returncode
        print(f"######## {aid}：{'通过' if rc == 0 else '未通过'}，{time.monotonic() - t0:.0f} 秒", flush=True)
        if rc != 0:
            bad.append(aid)
    print(f"\n走查 {len(todo)} 个模块，" + ("全部通过" if not bad else f"未通过：{'、'.join(bad)}") + f"。截图在 {a.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
