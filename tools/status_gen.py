#!/usr/bin/env python3
"""状态只写一处（#140 第 5 条）。

每个星座一份 `docs/constellations/<名>/status.yaml`，是星座进度的唯一来源。
`docs/constellations/<名>/index.md` 和 `docs/handoff.md` 里被下面两行包起来的段落由本脚本生成，不要手改：

    <!-- status:begin <名> -->
    ...
    <!-- status:end <名> -->

用法：
    python tools/status_gen.py --write   按 status.yaml 重新生成这些段落
    python tools/status_gen.py --check   只检查，不改文件；status.yaml 不合法或段落和它对不上就退出码 1（CI 用）
    python tools/status_gen.py [仓库目录]  仓库目录默认是本脚本的上一级

做完一步的流程：改 status.yaml → 跑 --write → 一起提交。
"""
import re
import sys
from pathlib import Path

import yaml

STATES = ["草案", "在做", "等验收", "完成"]
URL = re.compile(r"^https://\S+$")
BLOCK = re.compile(r"<!-- status:begin ([a-z0-9-]+) -->\n.*?<!-- status:end \1 -->\n?", re.S)
HEAD = "<!-- status:begin {name} -->"
TAIL = "<!-- status:end {name} -->"


def constellation_dirs(repo):
    base = Path(repo) / "docs" / "constellations"
    return sorted(p.parent for p in base.glob("*/status.yaml")) if base.exists() else []


def validate(doc, name):
    """返回错误列表。"""
    errs = []
    if not isinstance(doc, dict):
        return [f"{name}/status.yaml：根不是映射"]
    for key in ("constellation", "title", "updated", "issue", "total", "now", "stars"):
        if key not in doc:
            errs.append(f"{name}/status.yaml：缺少 {key}")
    if errs:
        return errs
    if doc["constellation"] != name:
        errs.append(f"{name}/status.yaml：constellation 应为「{name}」，现在是「{doc['constellation']}」")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(doc["updated"])):
        errs.append(f"{name}/status.yaml：updated 要写成 2026-11-16 这样的日期")
    for key in ("issue", "total"):
        if not isinstance(doc[key], int) or doc[key] < 1:
            errs.append(f"{name}/status.yaml：{key} 要是正整数")
    if doc.get("preview") is not None and not URL.match(str(doc["preview"])):
        errs.append(f"{name}/status.yaml：preview 要是 https 地址")
    if not str(doc["now"]).strip():
        errs.append(f"{name}/status.yaml：now 不能空，写一句现在该做什么")
    if not isinstance(doc["stars"], list):
        return errs + [f"{name}/status.yaml：stars 要是列表"]
    seen = set()
    for s in doc["stars"]:
        if not isinstance(s, dict):
            errs.append(f"{name}/status.yaml：stars 里有一项不是映射")
            continue
        n = s.get("n")
        where = f"{name}/status.yaml 第 {n} 颗星"
        if not isinstance(n, int) or not 1 <= n <= (doc["total"] if isinstance(doc["total"], int) else 0):
            errs.append(f"{name}/status.yaml：星的编号 n={n!r} 要在 1 到 total 之间")
            continue
        if n in seen:
            errs.append(f"{where}：编号重复")
        seen.add(n)
        if not str(s.get("title", "")).strip():
            errs.append(f"{where}：缺少 title")
        if s.get("state") not in STATES:
            errs.append(f"{where}：state 要是 {'、'.join(STATES)} 之一，现在是 {s.get('state')!r}")
        prs = s.get("prs", [])
        if not isinstance(prs, list) or not all(isinstance(x, int) and x > 0 for x in prs):
            errs.append(f"{where}：prs 要是 PR 号的列表")
        waiting = str(s.get("waiting", "") or "").strip()
        if s.get("state") in ("在做", "等验收") and not waiting:
            errs.append(f"{where}：状态是「{s.get('state')}」，waiting 要写在等什么")
        if s.get("state") in ("草案", "完成") and waiting:
            errs.append(f"{where}：状态是「{s.get('state')}」，waiting 要留空")
    return errs


def render_table(doc):
    rows = ["| 星 | 状态 | 主要 PR | 在等什么 |", "| --- | --- | --- | --- |"]
    for s in sorted(doc["stars"], key=lambda x: x["n"]):
        if s["state"] == "草案":
            continue
        prs = "、".join(f"#{x}" for x in s.get("prs", [])) or "—"
        waiting = str(s.get("waiting", "") or "").strip() or "—"
        rows.append(f"| 第 {s['n']} 颗「{s['title']}」 | {s['state']} | {prs} | {waiting} |")
    return rows


def counts(doc):
    by = {st: 0 for st in STATES}
    listed = {s["n"]: s["state"] for s in doc["stars"]}
    for st in listed.values():
        by[st] += 1
    by["草案"] += doc["total"] - len(listed)
    return by


def render(doc, where):
    """where: 'index' 或 'handoff'。返回包含起止行的完整段落。"""
    name = doc["constellation"]
    by = counts(doc)
    summary = f"{doc['total']} 颗星：完成 {by['完成']}、等验收 {by['等验收']}、在做 {by['在做']}、草案 {by['草案']}"
    lines = [HEAD.format(name=name), f"_这一段由 `tools/status_gen.py` 按 `docs/constellations/{name}/status.yaml` 生成，不要手改。_", ""]
    if where == "index":
        lines.append(f"**状态（{doc['updated']}）**：{summary}。主 issue #{doc['issue']}。"
                     + (f"试玩页 {doc['preview']}" if doc.get("preview") else ""))
    else:
        lines.append(f"**标杆星座「{doc['title']}」**（{doc['updated']}；主 issue #{doc['issue']}；完整任务说明从 `docs/constellations/{name}/index.md` 看起）："
                     + summary + "。" + (f"试玩页 {doc['preview']}" if doc.get("preview") else ""))
    lines += ["", *render_table(doc), "", f"**现在**：{str(doc['now']).strip()}", TAIL.format(name=name)]
    return "\n".join(lines) + "\n"


def strip_blocks(text):
    """去掉生成段落后的文本。CI 用它判断「只改了生成段落」。"""
    return BLOCK.sub("", text)


def sync(repo, write):
    """返回 (错误列表, 改了的文件列表)。write=False 时只比较，不写。"""
    repo = Path(repo)
    errs, changed = [], []
    for d in constellation_dirs(repo):
        name = d.name
        try:
            doc = yaml.safe_load((d / "status.yaml").read_text(encoding="utf-8"))
        except Exception as exc:
            errs.append(f"{name}/status.yaml 解析失败：{exc}")
            continue
        bad = validate(doc, name)
        errs += bad
        if bad:
            continue
        for where, path in (("index", d / "index.md"), ("handoff", repo / "docs" / "handoff.md")):
            text = path.read_text(encoding="utf-8")
            pat = re.compile(rf"<!-- status:begin {re.escape(name)} -->\n.*?<!-- status:end {re.escape(name)} -->\n?", re.S)
            if not pat.search(text):
                errs.append(f"{path.relative_to(repo)} 里没有「status:begin {name}」段落，先放一对起止记号")
                continue
            new = pat.sub(lambda _m: render(doc, where), text, count=1)
            if new != text:
                if write:
                    path.write_text(new, encoding="utf-8")
                    changed.append(str(path.relative_to(repo)))
                else:
                    errs.append(f"{path.relative_to(repo)} 里的「{name}」状态段落和 status.yaml 对不上，跑 python tools/status_gen.py --write")
    return errs, changed


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    repo = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    write = "--write" in argv
    if not write and "--check" not in argv:
        print(__doc__)
        return 2
    errs, changed = sync(repo, write)
    for e in errs:
        print("错误：" + e)
    for c in changed:
        print("已更新：" + c)
    if not errs and not changed:
        print("状态一致")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
