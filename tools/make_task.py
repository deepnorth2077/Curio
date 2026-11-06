"""把 prompts/<任务 id>.md 展开成可以直接派发的任务文件 <任务 id>.task.md。

用法：
    python tools/make_task.py curio-002a                 # 用 HEAD，并要求它已经合入 origin/main
    python tools/make_task.py curio-002a --commit abc123 --out /tmp/x
    python tools/make_task.py curio-002a --draft         # 允许还没合入 main 的提交（只用于审阅，不派发）

提示词源文件的写法：
    开头是一段 YAML 头：
        ---
        task: curio-002a
        issue: 16
        version: v1
        ---
    正文里可以用三种指令，只在源文件里展开，嵌进来的文件不再展开：
        {{commit}}                         换成完整提交号
        {{embed: docs/specs/content.md}}   原样嵌入整个文件
        {{embed: docs/submission.md#格式}}  只嵌入「## 格式」这一节（到下一个二级标题为止，代码块里的标题不算）
    其他 {{…}} 一律报错，防止模板占位符没填就发出去。

所有文件都从指定提交里读（git show），不读工作区。所以任务文件里的内容，就是那个提交里的内容。
"""
import argparse, hashlib, re, subprocess, sys
from pathlib import Path

DIRECTIVE = re.compile(r"\{\{\s*(.*?)\s*\}\}")
EMBED = re.compile(r"embed:\s*([^#\s]+)(?:#(.+))?")
FENCE = re.compile(r"^(`{3,}|~{3,})")
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
TASK_ID = re.compile(r"curio-\d{3}[a-z]?|act\.[a-z0-9-]+(\.[a-z0-9-]+)+|review\.[a-z0-9-]+")


class TaskError(Exception):
    pass


def git(repo, *args):
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True)
    if p.returncode != 0:
        raise TaskError(f"git {' '.join(args)} 失败：{p.stderr.decode('utf-8', 'replace').strip()}")
    return p.stdout


def read_at(repo, commit, path):
    try:
        data = git(repo, "show", f"{commit}:{path}")
    except TaskError:
        raise TaskError(f"提交 {commit[:7]} 里没有文件 {path}")
    if b"\r" in data:
        raise TaskError(f"{path} 含有 CR 换行符，先改成 LF")
    try:
        return data, data.decode("utf-8")
    except UnicodeDecodeError:
        raise TaskError(f"{path} 不是 UTF-8 文本")


def section(text, title, path):
    """取出「## title」到下一个二级标题之间的内容（含标题行），跳过代码块里的行。"""
    lines = text.split("\n")
    fence = None
    start = end = None
    for i, line in enumerate(lines):
        if fence is None:
            m = FENCE.match(line)
            if m:
                fence = m.group(1)
            elif line.startswith("## "):
                if start is None and line[3:].strip() == title:
                    start = i
                elif start is not None:
                    end = i
                    break
        else:
            s = line.strip()
            if s and set(s) == {fence[0]} and len(s) >= len(fence):
                fence = None
    if start is None:
        raise TaskError(f"{path} 里找不到二级标题「{title}」")
    return "\n".join(lines[start:end]).rstrip("\n") + "\n"


def fenced(body):
    """用比内容里最长的反引号串还长的围栏包起来，保证嵌入的代码块不会提前结束。"""
    longest = max((len(m) for m in re.findall(r"`+", body)), default=0)
    f = "`" * max(4, longest + 1)
    return f"{f}text\n{body if body.endswith(chr(10)) else body + chr(10)}{f}\n"


def build(repo, task_id, commit="HEAD", draft=False):
    if not TASK_ID.fullmatch(task_id):
        raise TaskError(f"任务 id「{task_id}」格式不对，应该像 curio-002a、act.quiz.xxx 或 review.xxx（审阅任务，issue 写 PR 号）")
    full = git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    if not draft:
        try:
            git(repo, "rev-parse", "--verify", "origin/main")
        except TaskError:
            raise TaskError("本地没有 origin/main，先运行 git fetch origin main:refs/remotes/origin/main")
        if subprocess.run(["git", "merge-base", "--is-ancestor", full, "origin/main"], cwd=repo).returncode != 0:
            raise TaskError(f"提交 {full[:7]} 还没有合入 main。正式派发必须基于已合入的规格；只做审阅时加 --draft")

    src_path = f"prompts/{task_id}.md"
    _, src = read_at(repo, full, src_path)
    m = FRONT.match(src)
    if not m:
        raise TaskError(f"{src_path} 开头缺少 --- 包起来的 YAML 头（task、issue、version）")
    meta = dict(re.findall(r"^(\w+):\s*(.+?)\s*$", m.group(1), re.M))
    for key in ("task", "issue", "version"):
        if key not in meta:
            raise TaskError(f"{src_path} 的 YAML 头缺少 {key}")
    if meta["task"] != task_id:
        raise TaskError(f"{src_path} 的 task 是 {meta['task']}，和文件名不一致")
    if not re.fullmatch(r"\d+", meta["issue"]):
        raise TaskError(f"{src_path} 的 issue 应该是数字，例如 16")
    if not re.fullmatch(r"v[1-9]\d*", meta["version"]):
        raise TaskError(f"{src_path} 的 version 应该像 v1")
    body = src[m.end():]

    embeds = []

    def expand(mm):
        d = mm.group(1)
        if d == "commit":
            return full
        e = EMBED.fullmatch(d)
        if not e:
            raise TaskError(f"不认识的指令「{{{{{d}}}}}」。只支持 {{{{commit}}}} 和 {{{{embed: 路径}}}}、{{{{embed: 路径#二级标题}}}}")
        path, title = e.group(1), e.group(2)
        raw, text = read_at(repo, full, path)
        part = section(text, title.strip(), path) if title else text
        embeds.append((path, title.strip() if title else "全文", hashlib.sha256(raw).hexdigest()))
        label = f"{path}" + (f" · 「{title.strip()}」一节" if title else "")
        return f"> 出处：`{label}`（提交 `{full[:7]}`）\n\n" + fenced(part)

    # 先逐个展开，展开结果不再扫描
    out, pos = [], 0
    for mm in DIRECTIVE.finditer(body):
        out.append(body[pos:mm.start()])
        out.append(expand(mm))
        pos = mm.end()
    out.append(body[pos:])
    body = "".join(out)

    header = (
        f"> 基于 Curio 仓库提交 `{full}` 生成 · 任务 `{task_id}` · issue #{meta['issue']} · 提示词版本 {meta['version']}\n"
        f"> 交付包开头信息请照抄：`issue: #{meta['issue']}`、`任务: {task_id}`、`提示词版本: {meta['version']}`、`基于提交: {full[:12]}`\n\n"
    )
    table = ["", "---", "", "## 附：本任务文件嵌入的仓库文件", "", "| 文件 | 范围 | SHA-256（整个文件） |", "| --- | --- | --- |"]
    table += [f"| `{p}` | {t} | `{h}` |" for p, t, h in embeds] or ["| （无） | | |"]
    text = header + body.rstrip("\n") + "\n" + "\n".join(table) + "\n"
    expect = ["--expect-issue", "#" + meta["issue"], "--expect-task", task_id, "--expect-commit", full, "--expect-version", meta["version"]]
    return text, full, expect


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成任务文件 <任务 id>.task.md")
    ap.add_argument("task_id")
    ap.add_argument("--commit", default="HEAD")
    ap.add_argument("--out", default=".")
    ap.add_argument("--draft", action="store_true", help="允许未合入 main 的提交，只用于审阅")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args(argv)
    try:
        text, full, expect = build(a.repo, a.task_id, a.commit, a.draft)
    except TaskError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    dest = Path(a.out) / f"{a.task_id}.task.md"
    dest.write_text(text, encoding="utf-8", newline="\n")
    print(f"✓ {dest}（基于 {full[:7]}{'，草稿' if a.draft else ''}）")
    print("收货时用：python tools/intake.py " + " ".join(expect))
    return 0


if __name__ == "__main__":
    sys.exit(main())
# END OF FILE
