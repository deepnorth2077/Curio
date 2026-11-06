#!/usr/bin/env python3
"""收货：解析实现 AI 的交付包，检查完整性，计算字节数和 SHA-256。格式见 docs/submission.md。

用法：
  python tools/intake.py 交付包.md [附件 ...]              # 只检查，打印收货报告
  python tools/intake.py 交付包.md [附件 ...] --write 目录   # 检查通过后，把文件写进目录

交付包可以分成几段，几段可以放进同一个文件，也可以分别存成文件，顺序不限。
附件的文件名必须是完整路径，把「/」换成「__」，例如 content__activities__act.x__index.html。
"""
import hashlib, json, re, sys
from pathlib import Path

END_MARKERS = {
    ".yaml": "# END OF FILE", ".yml": "# END OF FILE", ".py": "# END OF FILE",
    ".html": "<!-- END OF FILE -->", ".md": "<!-- END OF FILE -->", ".svg": "<!-- END OF FILE -->",
    ".js": "/* END OF FILE */", ".css": "/* END OF FILE */",
    ".json": None,
}
SEG_HEAD = re.compile(r"^=== CURIO 交付包 · 第 (\d+)/(\d+) 段 ===\s*$", re.M)
SEG_TAIL = re.compile(r"^=== 第 (\d+)/(\d+) 段完 ===\s*$", re.M)
FILE_HEAD = re.compile(r"^### FILE: (\S+)\s*$", re.M)
FENCE = re.compile(r"^(`{3,})[^\n`]*\n(.*?)^\1\s*$", re.M | re.S)
META_KEYS = ["issue", "任务", "实现者", "提示词版本", "基于提交", "轮次"]


class Report:
    def __init__(self):
        self.errors, self.files, self.meta, self.notes, self.blobs = [], [], {}, "", {}

    def err(self, msg): self.errors.append(msg)


def attachment_path(name):
    return name.replace("__", "/")


def check_content(path, text, r):
    suffix = Path(path).suffix.lower()
    if suffix not in END_MARKERS:
        r.err(f"{path}：不支持的文件类型 {suffix or '(无后缀)'}")
        return
    marker = END_MARKERS[suffix]
    lines = [l for l in text.rstrip().splitlines() if l.strip()]
    if marker is not None:
        if not lines or lines[-1].strip() != marker:
            r.err(f"{path}：最后一行不是结束标记「{marker}」，文件可能被截断")
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
            yaml.safe_load(text)
        except Exception as e:
            r.err(f"{path}：YAML 解析失败（{str(e).splitlines()[0]}），文件可能被截断")
    elif suffix == ".json":
        try:
            json.loads(text)
        except Exception as e:
            r.err(f"{path}：JSON 解析失败（{e}），文件可能被截断")
    elif suffix == ".html":
        if not re.search(r"</html>\s*(<!--\s*END OF FILE\s*-->)?\s*$", text.strip(), re.I):
            r.err(f"{path}：没有以 </html> 结束，文件可能被截断")


def safe_path(p):
    return not (p.startswith("/") or ".." in Path(p).parts or "\\" in p)


def intake(package_texts, attachments=()):
    """package_texts：交付包各段的文本（可以一个文本里含多段）；attachments：[(文件名, bytes)]。"""
    r = Report()
    text = "\n".join(package_texts)

    # ---- 分段 ----
    heads = [(m.start(), int(m.group(1)), int(m.group(2))) for m in SEG_HEAD.finditer(text)]
    if not heads:
        r.err("没有找到交付包的开头「=== CURIO 交付包 · 第 k/n 段 ===」")
        return r
    totals = {n for _, _, n in heads}
    if len(totals) != 1:
        r.err(f"各段写的总段数不一致：{sorted(totals)}")
        return r
    n = totals.pop()
    seen = {}
    segments = {}
    for i, (start, k, _) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        body = text[start:end]
        if k in seen:
            r.err(f"第 {k} 段重复出现")
            continue
        seen[k] = True
        tail = SEG_TAIL.search(body)
        if not tail or int(tail.group(1)) != k:
            r.err(f"第 {k} 段没有以「=== 第 {k}/{n} 段完 ===」结束，这一段可能被截断")
        segments[k] = body
    for k in range(1, n + 1):
        if k not in segments:
            r.err(f"缺第 {k}/{n} 段")
    if n in segments and "=== END ===" not in segments[n]:
        r.err(f"最后一段（第 {n} 段）缺少「=== END ===」")
    if r.errors:
        return r

    first = segments[1]
    for key in META_KEYS:
        m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", first, re.M)
        if m:
            r.meta[key] = m.group(1)
    for key in ("issue", "任务", "实现者", "轮次"):
        if key not in r.meta:
            r.err(f"第 1 段缺少「{key}:」")

    # ---- 清单 ----
    m = re.search(r"^## 文件清单\s*\n(.*?)(?=^## |\Z)", first, re.M | re.S)
    listed = []
    if not m:
        r.err("第 1 段缺少「## 文件清单」")
    else:
        for line in m.group(1).splitlines():
            lm = re.match(r"^-\s+`?([^`\s（(]+)`?", line.strip())
            if lm:
                listed.append(lm.group(1))
    if len(set(listed)) != len(listed):
        r.err("文件清单里有重复的路径")
    for p in listed:
        if not safe_path(p):
            r.err(f"文件清单里有不安全的路径：{p}")

    # ---- 内联文件 ----
    delivered = {}
    for k in sorted(segments):
        body = segments[k]
        heads_f = list(FILE_HEAD.finditer(body))
        for i, fm in enumerate(heads_f):
            path = fm.group(1)
            chunk_end = heads_f[i + 1].start() if i + 1 < len(heads_f) else len(body)
            chunk = body[fm.end():chunk_end]
            fence = FENCE.search(chunk)
            if not fence:
                r.err(f"{path}：没有找到完整的代码块（开头和结尾的 ``` 要成对），文件可能被截断")
                continue
            content = fence.group(2)
            if path in delivered:
                r.err(f"{path}：交付了不止一次")
                continue
            delivered[path] = ("内联", content.encode("utf-8"))

    # ---- 附件 ----
    for name, data in attachments:
        path = attachment_path(Path(name).name)
        if "/" not in path:
            r.err(f"附件「{name}」的文件名必须是完整路径，把「/」换成「__」，例如 content__activities__act.x__index.html")
            continue
        if path in delivered:
            r.err(f"{path}：附件和内联内容重复交付")
            continue
        delivered[path] = ("附件", data)

    # ---- 对账 ----
    for p in listed:
        if p not in delivered:
            r.err(f"清单里有 {p}，但没有交付")
    for p in delivered:
        if listed and p not in listed:
            r.err(f"交付了清单里没有的文件：{p}（附件名和清单对不上时也会出现这个错误）")

    # ---- 逐个文件 ----
    for p, (src, data) in sorted(delivered.items()):
        try:
            text_c = data.decode("utf-8")
        except UnicodeDecodeError:
            r.err(f"{p}：不是 UTF-8 文本")
            continue
        check_content(p, text_c, r)
        r.blobs[p] = data
        r.files.append({"path": p, "source": src, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    last = segments[n]
    nm = re.search(r"^## 说明\s*\n(.*?)(?==== END ===)", last, re.M | re.S)
    r.notes = nm.group(1).strip() if nm else ""
    return r


def render(r):
    out = []
    meta = "　".join(f"{k}：{v}" for k, v in r.meta.items())
    out.append(f"收货报告　{meta}")
    if r.files:
        out.append("")
        out.append("| 文件 | 来源 | 字节 | SHA-256 |")
        out.append("| --- | --- | --- | --- |")
        for f in r.files:
            out.append(f"| `{f['path']}` | {f['source']} | {f['bytes']} | `{f['sha256'][:16]}` |")
    out.append("")
    if r.errors:
        out.append(f"未通过：{len(r.errors)} 个问题")
        out += [f"- {e}" for e in r.errors]
    else:
        out.append("通过：交付包完整")
    return "\n".join(out)


def main(argv):
    write_to = None
    if "--write" in argv:
        i = argv.index("--write")
        write_to = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__)
        return 2
    pkgs, atts = [], []
    for a in argv:
        p = Path(a)
        data = p.read_bytes()
        if SEG_HEAD.search(data.decode("utf-8", errors="replace")):
            pkgs.append(data.decode("utf-8"))
        else:
            atts.append((p.name, data))
    r = intake(pkgs, atts)
    print(render(r))
    if r.errors:
        return 1
    if write_to:
        for f in r.files:
            dest = write_to / f["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.blobs[f["path"]])
        print(f"已写入 {len(r.files)} 个文件到 {write_to}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
