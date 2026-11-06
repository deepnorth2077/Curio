#!/usr/bin/env python3
"""好奇号 Curio 的 PR 检查。规则见 docs/collaboration.md。

用法：python tools/ci_checks.py
环境变量（GitHub Actions 自动提供，本地可手动设置）：
  BASE_REF     目标分支，默认 main
  HEAD_BRANCH  PR 的分支名，默认取当前分支
  PR_LABELS    PR 标签，用逗号分隔
依赖：pyyaml、jsonschema
"""
import fnmatch, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

PROTECTED = ["schemas/*", "docs/*", "tools/*", ".github/*", "AGENTS.md", "CLAUDE.md", "README.md", "prompts/module-template.md"]
OVERRIDE_LABEL = "越界-已批准"
KID_FACING_NODE = ["title", "driving_question", "lenses"]
KID_FACING_ACT = ["title", "predict", "explain"]
FORBIDDEN_WORD = "学习"

errors, warnings = [], []
def err(msg, file=None): errors.append((file, msg))
def warn(msg, file=None): warnings.append((file, msg))

def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout

def match(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)

# ---------- 输入 ----------
base = "origin/" + os.environ.get("BASE_REF", "main")
branch = os.environ.get("HEAD_BRANCH") or git("rev-parse", "--abbrev-ref", "HEAD").strip()
labels = {l.strip() for l in os.environ.get("PR_LABELS", "").split(",") if l.strip()}
override = OVERRIDE_LABEL in labels
changes = []  # (status, path, old_path)
_diff = subprocess.run(["git", "diff", "--name-status", "-M", f"{base}...HEAD"], capture_output=True, text=True)
if _diff.returncode != 0:
    print(f"无法和 {base} 比较，检查没有运行：{_diff.stderr.strip()}")
    print(f"本地运行前先执行：git fetch origin {base.split('/', 1)[1]}:refs/remotes/{base}")
    sys.exit(2)
for line in _diff.stdout.splitlines():
    parts = line.split("\t")
    if not parts or not parts[0]: continue
    st = parts[0][0]
    if st == "R": changes.append(("R", parts[2], parts[1]))
    else: changes.append((st, parts[1], None))
changed = [p for _, p, _ in changes] + [o for _, _, o in changes if o]

# ---------- 1. 地盘检查 ----------
def check_territory():
    prefix = branch.split("/", 1)[0] + "/" if "/" in branch else branch
    kinds = ["kp/", "arch/", "feat/", "fix/", "chore/"]
    if prefix not in kinds:
        err(f"分支名「{branch}」不符合规则，必须以 {'、'.join(kinds)} 开头（见 docs/collaboration.md）")
        return
    if prefix == "arch/":
        return
    for p in changed:
        if prefix == "kp/":
            node_id = branch.split("/", 1)[1]
            ok = (p.startswith("content/") or fnmatch.fnmatch(p, "prompts/act.*.md")) and not match(p, PROTECTED)
            if ok and p.startswith("content/nodes/"):
                ok = Path(p).stem == node_id
            if ok and p.startswith("content/activities/"):
                act_dir = Path(*Path(p).parts[:3])
                mf = act_dir / "manifest.yaml"
                ok = mf.exists() and node_id in mf.read_text(encoding="utf-8")
        else:
            ok = not match(p, PROTECTED) and not p.startswith("content/")
        if not ok:
            if override: warn(f"越界改动（已由「{OVERRIDE_LABEL}」标签放行）：{p}", p)
            else: err(f"分支「{branch}」不能改这个文件。确需修改，请 Luka 给 PR 加「{OVERRIDE_LABEL}」标签", p)

# ---------- 2. 规格校验 ----------
def load_yaml(path):
    import yaml
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        err(f"YAML 解析失败：{e}", str(path)); return None

def check_specs():
    from jsonschema import Draft202012Validator
    schemas = {}
    for f in sorted(Path("schemas").glob("*.schema.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8")); Draft202012Validator.check_schema(s); schemas[f.name] = s
        except Exception as e:
            err(f"不是合法的 JSON Schema：{e}", str(f))
    def validate(doc, schema_name, path):
        if schema_name not in schemas or doc is None: return
        for e in Draft202012Validator(schemas[schema_name]).iter_errors(doc):
            loc = "/".join(str(x) for x in e.absolute_path) or "(根)"
            err(f"{loc}：{e.message}", str(path))
    nodes, acts = {}, {}
    for f in sorted(Path("content/nodes").rglob("*.yaml")):
        d = load_yaml(f); validate(d, "knode.schema.json", f)
        if isinstance(d, dict) and "id" in d:
            if f.stem != d["id"]: err(f"文件名必须和 id 一致：{d['id']}.yaml", str(f))
            if d["id"] in nodes: err(f"知识点 ID 重复：{d['id']}", str(f))
            nodes[d["id"]] = (f, d)
    for f in sorted(Path("content/activities").glob("*/manifest.yaml")):
        d = load_yaml(f); validate(d, "activity.schema.json", f)
        if isinstance(d, dict) and "id" in d:
            if f.parent.name != d["id"]: err(f"活动目录名必须和 id 一致：content/activities/{d['id']}/", str(f))
            if d["id"] in acts: err(f"活动 ID 重复：{d['id']}", str(f))
            acts[d["id"]] = (f, d)
            if not (f.parent / "index.html").exists(): err("缺少 index.html", str(f))
            for t in d.get("targets", []):
                if t not in nodes: err(f"targets 指向不存在的知识点：{t}", str(f))
    # 图谱：前置引用存在、无环
    for nid, (f, d) in nodes.items():
        for p in d.get("prerequisites", []) + d.get("related", []):
            if p not in nodes: err(f"引用了不存在的知识点：{p}", str(f))
        if d.get("status") == "published":
            for a in d.get("activities", []):
                if a not in acts: err(f"已发布的知识点引用了不存在的活动：{a}", str(f))
    state = {}
    def dfs(n, stack):
        state[n] = 1
        for p in nodes[n][1].get("prerequisites", []):
            if p not in nodes: continue
            if state.get(p) == 1: err(f"前置关系有环：{' → '.join(stack + [p])}", str(nodes[n][0])); continue
            if not state.get(p): dfs(p, stack + [p])
        state[n] = 2
    for n in nodes:
        if not state.get(n): dfs(n, [n])
    return nodes, acts

# ---------- 3. ID 检查 ----------
def check_ids():
    for st, p, old in changes:
        src = old or p
        is_node = src.startswith("content/nodes/") and src.endswith(".yaml")
        is_act = src.startswith("content/activities/") and src.endswith("/manifest.yaml")
        if not (is_node or is_act): continue
        if st in ("D", "R"):
            msg = f"删除或改名了已有的{'知识点' if is_node else '活动'}文件：{src}。ID 永不改动"
            if override: warn(msg + "（已放行）", src)
            else: err(msg, src)
            continue
        if st == "M":
            old_text = git("show", f"{base}:{src}")
            m_old = re.search(r"^id:\s*(\S+)", old_text, re.M)
            m_new = re.search(r"^id:\s*(\S+)", Path(p).read_text(encoding="utf-8"), re.M)
            if m_old and m_new and m_old.group(1) != m_new.group(1):
                err(f"id 从 {m_old.group(1)} 改成了 {m_new.group(1)}。ID 永不改动", p)

# ---------- 4. 文案检查 ----------
def texts(v):
    if isinstance(v, str): yield v
    elif isinstance(v, dict):
        for x in v.values(): yield from texts(x)
    elif isinstance(v, list):
        for x in v: yield from texts(x)

def check_copy(nodes, acts):
    for nid, (f, d) in nodes.items():
        for k in KID_FACING_NODE:
            if any(FORBIDDEN_WORD in t for t in texts(d.get(k))): err(f"给孩子看的「{k}」里出现了「{FORBIDDEN_WORD}」", str(f))
    for aid, (f, d) in acts.items():
        for k in KID_FACING_ACT:
            if any(FORBIDDEN_WORD in t for t in texts(d.get(k))): err(f"给孩子看的「{k}」里出现了「{FORBIDDEN_WORD}」", str(f))
        html = (f.parent / "index.html")
        if html.exists():
            visible = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", html.read_text(encoding="utf-8"), flags=re.S)
            visible = re.sub(r"<[^>]+>", " ", visible)
            if FORBIDDEN_WORD in visible: err(f"页面文字里出现了「{FORBIDDEN_WORD}」", str(html))

# ---------- 5. 署名提醒 ----------
def check_trailers():
    for block in git("log", f"{base}..HEAD", "--format=%h%x00%s%x00%B%x1e").split("\x1e"):
        block = block.strip()
        if not block: continue
        sha, subject, body = (block.split("\x00") + ["", ""])[:3]
        if not re.search(r"^(Agent|Co-Authored-By):", body, re.M | re.I):
            warn(f"提交 {sha}「{subject}」没有署名（Agent: 或 Co-Authored-By:）")

# ---------- 运行 ----------
print(f"分支：{branch}　对比：{base}　改动文件：{len(changed)}　标签：{', '.join(sorted(labels)) or '无'}")
check_territory()
nodes, acts = check_specs()
check_ids()
check_copy(nodes, acts)
check_trailers()
print(f"知识点 {len(nodes)} 个，活动 {len(acts)} 个")

gha = os.environ.get("GITHUB_ACTIONS") == "true"
for kind, items in (("warning", warnings), ("error", errors)):
    for f, msg in items:
        if gha: print(f"::{kind}{' file=' + f if f else ''}::{msg}")
        else: print(f"[{'提醒' if kind == 'warning' else '错误'}] {f + '：' if f else ''}{msg}")
print("通过" if not errors else f"未通过：{len(errors)} 个错误")
sys.exit(1 if errors else 0)
