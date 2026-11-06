#!/usr/bin/env python3
"""好奇号 Curio 的 PR 检查。工作流见 docs/collaboration.md。

用法：python tools/ci_checks.py [仓库目录]
环境变量（GitHub Actions 自动提供，本地可手动设置）：
  BASE_REF     目标分支，默认 main
  HEAD_BRANCH  PR 的分支名，默认取当前分支
  PR_LABELS    PR 标签，用逗号分隔
依赖见 tools/requirements.txt。自测：python -m unittest discover -s tools/tests
"""
import fnmatch, json, os, re, subprocess, sys
from pathlib import Path

PROTECTED = ["schemas/*", "docs/*", "tools/*", ".github/*", "AGENTS.md", "CLAUDE.md", "README.md", "GLOSSARY.md", "prompts/module-template.md", "prompts/task-template.md"]
BRANCH_KINDS = ["kp/", "arch/", "feat/", "fix/", "chore/"]
OVERRIDE_LABEL = "越界-已批准"
KID_FACING_NODE = ["title", "driving_question", "lenses"]
KID_FACING_ACT = ["title", "predict", "explain"]
FORBIDDEN_WORD = "学习"
PUBLISH_REQUIRED_TYPES = ["explain", "quiz"]


class Result:
    def __init__(self):
        self.errors, self.warnings, self.info = [], [], []

    def err(self, msg, file=None): self.errors.append((file, msg))
    def warn(self, msg, file=None): self.warnings.append((file, msg))


def git(repo, *args, check=False):
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p


def match(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def load_yaml_text(text):
    import yaml
    return yaml.safe_load(text)


def run(repo, base="origin/main", branch="", labels=()):
    """对 repo 的 HEAD 相对 base 做全部检查，返回 Result。"""
    repo = Path(repo)
    r = Result()
    labels = set(labels)
    override = OVERRIDE_LABEL in labels

    diff = git(repo, "diff", "--name-status", "-M", f"{base}...HEAD")
    if diff.returncode != 0:
        raise RuntimeError(f"无法和 {base} 比较：{diff.stderr.strip()}")
    changes = []  # (status, path, old_path)
    for line in diff.stdout.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0]:
            continue
        st = parts[0][0]
        changes.append(("R", parts[2], parts[1]) if st == "R" else (st, parts[1], None))
    changed = [p for _, p, _ in changes] + [o for _, _, o in changes if o]
    r.info.append(f"分支：{branch}　对比：{base}　改动文件：{len(changed)}　标签：{', '.join(sorted(labels)) or '无'}")

    def base_text(path):
        p = git(repo, "show", f"{base}:{path}")
        return p.stdout if p.returncode == 0 else None

    def manifest_targets(act_dir):
        """活动归属：先看当前版本的 manifest，被删掉时看 base 里的版本。"""
        for text in ((repo / act_dir / "manifest.yaml").read_text(encoding="utf-8") if (repo / act_dir / "manifest.yaml").exists() else None,
                     base_text(f"{act_dir}/manifest.yaml")):
            if text is None:
                continue
            try:
                d = load_yaml_text(text)
            except Exception:
                return None
            return d.get("targets", []) if isinstance(d, dict) else None
        return None

    # ---------- 1. 地盘检查 ----------
    prefix = branch.split("/", 1)[0] + "/" if "/" in branch else branch
    if prefix not in BRANCH_KINDS:
        r.err(f"分支名「{branch}」不符合规则，必须以 {'、'.join(BRANCH_KINDS)} 开头（见 docs/collaboration.md）")
    elif prefix != "arch/":
        node_id = branch.split("/", 1)[1] if prefix == "kp/" else None
        if node_id is not None:
            exists = list((repo / "content/nodes").rglob(f"{node_id}.yaml")) if (repo / "content/nodes").exists() else []
            in_base = any(p.endswith(f"/{node_id}.yaml") for p in git(repo, "ls-tree", "-r", "--name-only", base, "content/nodes").stdout.splitlines())
            if not exists and not in_base:
                r.err(f"分支名里的知识点「{node_id}」不存在。知识点分支一律叫 kp/<知识点 id>，改版也用同一个名字")
        for p in changed:
            shared = None
            if prefix == "kp/":
                ok = (p.startswith("content/") or fnmatch.fnmatch(p, "prompts/act.*.md")) and not match(p, PROTECTED)
                targets = None
                if ok and p.startswith("content/nodes/"):
                    ok = Path(p).stem == node_id
                elif ok and p.startswith("content/activities/"):
                    parts = Path(p).parts
                    targets = manifest_targets("/".join(parts[:3])) if len(parts) >= 3 else None
                elif ok and p.startswith("content/"):
                    ok = False
                elif ok and p.startswith("prompts/"):
                    targets = manifest_targets(f"content/activities/{Path(p).stem}")
                if ok and (p.startswith("content/activities/") or p.startswith("prompts/")):
                    # kp/ 分支只能改「只针对这一个知识点」的活动；共享活动会影响别的知识点，要单独开 PR
                    ok = isinstance(targets, list) and targets == [node_id]
                    if isinstance(targets, list) and node_id in targets and len(targets) > 1:
                        shared = targets
            else:
                ok = not match(p, PROTECTED) and not p.startswith("content/")
            if not ok and shared:
                msg = (f"这是共享活动，同时影响 {'、'.join(shared)}。kp/ 分支只能改只针对 {node_id} 的活动；"
                       f"共享活动要单独开 PR，覆盖所有受影响知识点的审核和试玩，并在征得 Luka 同意后加「{OVERRIDE_LABEL}」标签")
                if override:
                    r.warn(f"共享活动改动（已由「{OVERRIDE_LABEL}」标签放行），受影响的知识点：{'、'.join(shared)}", p)
                else:
                    r.err(msg, p)
            elif not ok:
                if override:
                    r.warn(f"越界改动（已由「{OVERRIDE_LABEL}」标签放行）：{p}", p)
                else:
                    r.err(f"分支「{branch}」不能改这个文件。确需修改，先在对话里征得 Luka 同意，再给 PR 加「{OVERRIDE_LABEL}」标签并在评论里注明", p)

    # ---------- 2. 规格校验 ----------
    from jsonschema import Draft202012Validator
    schemas = {}
    for f in sorted((repo / "schemas").glob("*.schema.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(s)
            schemas[f.name] = s
        except Exception as e:
            r.err(f"不是合法的 JSON Schema：{e}", rel(repo, f))

    def validate(doc, schema_name, path):
        if schema_name not in schemas or doc is None:
            return
        for e in Draft202012Validator(schemas[schema_name]).iter_errors(doc):
            loc = "/".join(str(x) for x in e.absolute_path) or "(根)"
            r.err(f"{loc}：{e.message}", rel(repo, path))

    def load(path):
        try:
            return load_yaml_text(path.read_text(encoding="utf-8"))
        except Exception as e:
            r.err(f"YAML 解析失败：{e}", rel(repo, path))
            return None

    nodes, acts = {}, {}
    for f in sorted((repo / "content/nodes").rglob("*.yaml")) if (repo / "content/nodes").exists() else []:
        d = load(f)
        validate(d, "knode.schema.json", f)
        if isinstance(d, dict) and "id" in d:
            if f.stem != d["id"]:
                r.err(f"文件名必须和 id 一致：{d['id']}.yaml", rel(repo, f))
            if d["id"] in nodes:
                r.err(f"知识点 ID 重复：{d['id']}", rel(repo, f))
            nodes[d["id"]] = (f, d)
    for f in sorted((repo / "content/activities").glob("*/manifest.yaml")) if (repo / "content/activities").exists() else []:
        d = load(f)
        validate(d, "activity.schema.json", f)
        if isinstance(d, dict) and "id" in d:
            if f.parent.name != d["id"]:
                r.err(f"活动目录名必须和 id 一致：content/activities/{d['id']}/", rel(repo, f))
            if d["id"] in acts:
                r.err(f"活动 ID 重复：{d['id']}", rel(repo, f))
            acts[d["id"]] = (f, d)
            if not (f.parent / "index.html").exists():
                r.err("缺少 index.html", rel(repo, f))

    # 引用：知识点之间、知识点和活动之间（双向）
    for nid, (f, d) in nodes.items():
        for p in d.get("prerequisites", []) + d.get("related", []):
            if p not in nodes:
                r.err(f"引用了不存在的知识点：{p}", rel(repo, f))
        for a in d.get("activities", []):
            if a not in acts:
                r.err(f"activities 里的活动不存在：{a}", rel(repo, f))
            elif nid not in acts[a][1].get("targets", []):
                r.err(f"活动 {a} 的 targets 里没有这个知识点，两边要互相写上", rel(repo, f))
    for aid, (f, d) in acts.items():
        for t in d.get("targets", []):
            if t not in nodes:
                r.err(f"targets 指向不存在的知识点：{t}", rel(repo, f))
            elif aid not in nodes[t][1].get("activities", []):
                r.err(f"知识点 {t} 的 activities 里没有这个活动，两边要互相写上", rel(repo, f))
        target_mis = {m["id"] for t in d.get("targets", []) if t in nodes for m in nodes[t][1].get("misconceptions", []) if isinstance(m, dict) and "id" in m}
        for m in d.get("misconceptions", []):
            if m not in target_mis:
                r.err(f"misconceptions 里的误区 {m} 不在目标知识点的误区列表里", rel(repo, f))

    # 前置关系无环
    state = {}
    def dfs(n, stack):
        state[n] = 1
        for p in nodes[n][1].get("prerequisites", []):
            if p not in nodes:
                continue
            if state.get(p) == 1:
                r.err(f"前置关系有环：{' → '.join(stack + [p])}", rel(repo, nodes[n][0]))
                continue
            if not state.get(p):
                dfs(p, stack + [p])
        state[n] = 2
    for n in nodes:
        if not state.get(n):
            dfs(n, [n])

    # 发布门禁
    for nid, (f, d) in nodes.items():
        if d.get("status") != "published":
            continue
        own = [acts[a][1] for a in d.get("activities", []) if a in acts]
        for a in d.get("activities", []):
            if a in acts and acts[a][1].get("review") != "approved":
                r.err(f"已发布的知识点只能引用已批准（review: approved）的活动，{a} 还是 {acts[a][1].get('review')}", rel(repo, f))
        types = {a.get("type") for a in own}
        for t in PUBLISH_REQUIRED_TYPES:
            if t not in types:
                r.err(f"发布前必须至少有一个 {t} 类活动", rel(repo, f))
        covered = {m for a in own for m in a.get("misconceptions", [])}
        for m in d.get("misconceptions", []):
            mid = m.get("id") if isinstance(m, dict) else None
            if mid and mid not in covered:
                r.err(f"误区 {mid} 还没有任何活动针对，不能发布", rel(repo, f))

    # ---------- 3. ID 检查 ----------
    for st, p, old in changes:
        src = old or p
        is_node = src.startswith("content/nodes/") and src.endswith(".yaml")
        is_act = src.startswith("content/activities/") and src.endswith("/manifest.yaml")
        if not (is_node or is_act):
            continue
        if st in ("D", "R"):
            msg = f"删除或改名了已有的{'知识点' if is_node else '活动'}文件：{src}。ID 永不改动"
            r.warn(msg + "（已放行）", src) if override else r.err(msg, src)
            continue
        if st == "M":
            def yaml_id(text):
                try:
                    d = load_yaml_text(text or "")
                except Exception:
                    return None
                return d.get("id") if isinstance(d, dict) else None
            old_id = yaml_id(base_text(src))
            new_id = yaml_id((repo / p).read_text(encoding="utf-8"))
            if old_id is not None and old_id != new_id:
                r.err(f"id 从 {old_id} 改成了 {new_id}。ID 永不改动", p)

    # ---------- 4. 文案检查 ----------
    for nid, (f, d) in nodes.items():
        for k in KID_FACING_NODE:
            if any(FORBIDDEN_WORD in t for t in texts(d.get(k))):
                r.err(f"给孩子看的「{k}」里出现了「{FORBIDDEN_WORD}」", rel(repo, f))
    for aid, (f, d) in acts.items():
        for k in KID_FACING_ACT:
            if any(FORBIDDEN_WORD in t for t in texts(d.get(k))):
                r.err(f"给孩子看的「{k}」里出现了「{FORBIDDEN_WORD}」", rel(repo, f))
        html = f.parent / "index.html"
        if html.exists():
            visible = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", html.read_text(encoding="utf-8"), flags=re.S | re.I)
            visible = re.sub(r"<[^>]+>", " ", visible)
            if FORBIDDEN_WORD in visible:
                r.err(f"页面文字里出现了「{FORBIDDEN_WORD}」", rel(repo, html))

    # ---------- 5. 署名提醒 ----------
    log = git(repo, "log", f"{base}..HEAD", "--format=%h%x00%s%x00%B%x1e").stdout
    for block in log.split("\x1e"):
        block = block.strip()
        if not block:
            continue
        sha, subject, body = (block.split("\x00") + ["", ""])[:3]
        if not re.search(r"^(Implemented-By|Agent|Co-Authored-By):", body, re.M | re.I):
            r.warn(f"提交 {sha}「{subject}」没有署名（Implemented-By:、Agent: 或 Co-Authored-By:）")

    r.info.append(f"知识点 {len(nodes)} 个，活动 {len(acts)} 个")
    return r


def rel(repo, path):
    try:
        return str(Path(path).resolve().relative_to(Path(repo).resolve()))
    except ValueError:
        return str(path)


def texts(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from texts(x)
    elif isinstance(v, list):
        for x in v:
            yield from texts(x)


def main():
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    base = "origin/" + os.environ.get("BASE_REF", "main")
    branch = os.environ.get("HEAD_BRANCH") or git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    labels = {l.strip() for l in os.environ.get("PR_LABELS", "").split(",") if l.strip()}
    try:
        r = run(repo, base, branch, labels)
    except RuntimeError as e:
        print(f"检查没有运行：{e}")
        print(f"本地运行前先执行：git fetch origin {base.split('/', 1)[1]}:refs/remotes/{base}")
        return 2
    for line in r.info:
        print(line)
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    for kind, items in (("warning", r.warnings), ("error", r.errors)):
        for f, msg in items:
            if gha:
                print(f"::{kind}{' file=' + f if f else ''}::{msg}")
            else:
                print(f"[{'提醒' if kind == 'warning' else '错误'}] {f + '：' if f else ''}{msg}")
    print("通过" if not r.errors else f"未通过：{len(r.errors)} 个错误")
    return 1 if r.errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
