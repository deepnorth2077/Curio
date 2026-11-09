#!/usr/bin/env python3
"""Curio 的 PR 检查。工作流见 docs/collaboration.md。

用法：python tools/ci_checks.py [仓库目录]
环境变量（GitHub Actions 自动提供，本地可手动设置）：
  BASE_REF     目标分支，默认 main
  HEAD_BRANCH  PR 的分支名，默认取当前分支
  PR_LABELS    PR 标签，用逗号分隔
依赖见 tools/requirements.txt。自测：python -m unittest discover -s tools/tests
"""
import fnmatch
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# fnmatch 的 * 会跨过 /，所以 "prompts/*" 覆盖整个 prompts/ 目录。例外只有两条，见地盘检查：
# kp/ 分支改自己活动的提示词和任务文件；feat/、fix/、chore/ 分支新增任务文件留档（*.task.md）。
# relay/ 里 Claude 手算的验收用例、跑用例的脚本和领航员说明也只能在 arch/ 改：实现者不能为了通过去改期望值。
# 竖切片 1 的向量和验收测试同理；实现者自己加的测试放在同目录的其他文件里。
PROTECTED = ["schemas/*", "docs/*", "tools/*", ".github/*", "prompts/*", "AGENTS.md", "CLAUDE.md", "README.md", "GLOSSARY.md",
             "relay/test/cases.json", "relay/test/cases.test.js", "relay/src/navigator.js",
             # 竖切片 1 的黄金向量和验收测试（规格第 7 节）：同上，实现者不能改期望值
             "kernel/vectors/*", "engine/vectors/*", "kernel/test/vectors.test.js", "engine/test/grading.test.js",
             "engine/test/quiz.test.js", "app/test/commit.test.js", "app/test/resume.test.js", "app/test/fake-store.js"]
ACT_PROMPT = re.compile(r"^prompts/(act\.[A-Za-z0-9._-]+?)(\.task)?\.md$")
TASK_ARCHIVE = re.compile(r"^prompts/[A-Za-z0-9][A-Za-z0-9._-]*\.task\.md$")
# kp/ 分支可以新增、修改本知识点活动的审查记录，以及本知识点自己的审查记录（ADR-009 增补 1）；不能删除
ACT_REVIEW = re.compile(r"^docs/reviews/(act\.[A-Za-z0-9._-]+?)\.md$")
NODE_REVIEW = re.compile(r"^docs/reviews/([a-z]+(?:\.[a-z0-9-]+)+)\.md$")
BRANCH_KINDS = ["kp/", "arch/", "feat/", "fix/", "chore/"]
OVERRIDE_LABEL = "越界-已批准"
KID_FACING_NODE = ["title", "driving_question", "lenses"]
KID_FACING_ACT = ["title", "predict", "explain"]
FORBIDDEN_WORD = "学习"
PUBLISH_REQUIRED_TYPES = ["explain", "quiz"]
PATH_SEGMENT = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]*$")

# 每增加一种能力，就在这里登记它所需的最低引擎等级。
ENGINE_REQUIREMENTS = {
    "kind": {"explain": 1, "quiz": 1, "reflection": 1},
    "answer": {"choice": 1, "number": 1, "fraction": 1},
    "figure": {"pie": 1, "rect": 1, "rect-unequal": 1, "number-line": 1, "svg": 1},
}

SVG_ELEMENTS = {
    "svg", "g", "defs", "title", "desc", "path", "rect", "circle", "ellipse",
    "line", "polyline", "polygon", "text", "tspan", "use", "linearGradient",
    "radialGradient", "stop", "clipPath",
}
SVG_ATTRIBUTES = {
    "x", "y", "width", "height", "d", "points", "cx", "cy", "r", "rx", "ry",
    "x1", "y1", "x2", "y2", "transform", "viewBox", "fill", "stroke",
    "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
    "opacity", "fill-opacity", "stroke-opacity", "font-size", "font-weight",
    "text-anchor", "dominant-baseline", "offset", "stop-color", "stop-opacity",
    "gradientUnits", "clip-path", "id", "class", "xmlns", "aria-label", "role",
    "href", "xlink:href",
}


class Result:
    def __init__(self):
        self.errors, self.warnings, self.info = [], [], []

    def err(self, msg, file=None):
        self.errors.append((file, msg))

    def warn(self, msg, file=None):
        self.warnings.append((file, msg))


def git(repo, *args, check=False):
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p


def match(path, patterns):
    # fnmatchcase：本地（包括 Windows）和 CI 上的结论一致，大小写不同就是不同的路径。
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def load_yaml_text(text):
    import yaml
    return yaml.safe_load(text)


def activity_items(doc):
    """按显示顺序产出结构化活动里的全部题目。"""
    if not isinstance(doc, dict):
        return
    body = doc.get("body", {})
    if not isinstance(body, dict):
        return
    if doc.get("kind") == "quiz":
        for item in body.get("items", []):
            if isinstance(item, dict):
                yield item
    elif doc.get("kind") == "explain":
        for step in body.get("steps", []):
            if isinstance(step, dict) and step.get("type") == "check" and isinstance(step.get("item"), dict):
                yield step["item"]


def activity_figures(doc):
    """产出题目配图和讲解步骤配图。"""
    if not isinstance(doc, dict) or not isinstance(doc.get("body"), dict):
        return
    for item in activity_items(doc):
        if isinstance(item.get("figure"), dict):
            yield item["figure"]
    if doc.get("kind") == "explain":
        for step in doc["body"].get("steps", []):
            if isinstance(step, dict) and step.get("type") == "figure" and isinstance(step.get("figure"), dict):
                yield step["figure"]


def activity_misconception_refs(doc):
    """产出结构化题目中实际使用的误区引用。"""
    for item in activity_items(doc):
        answer = item.get("answer", {})
        if not isinstance(answer, dict):
            continue
        if answer.get("type") == "choice":
            for choice in answer.get("choices", []):
                if isinstance(choice, dict) and not choice.get("correct") and choice.get("misconception"):
                    yield choice["misconception"]
        for wrong in answer.get("common_wrong", []):
            if isinstance(wrong, dict) and wrong.get("misconception"):
                yield wrong["misconception"]


def check_publish_gate(nodes, acts):
    """返回发布门禁错误；nodes/acts 的值均为 (文件路径, 已解析文档)。

    构建器和 PR 检查都调用这里，保证收录范围、误区覆盖和引用闭包一致。
    """
    errors = []
    for nid, (node_path, node) in nodes.items():
        if not isinstance(node, dict) or node.get("status") != "published":
            continue
        for prerequisite in node.get("prerequisites", []):
            if prerequisite not in nodes or nodes[prerequisite][1].get("status") != "published":
                errors.append((node_path, f"已发布知识点的前置知识点 {prerequisite} 不存在或还没有发布，引用闭包不成立"))

        own = []
        for aid in node.get("activities", []):
            if aid in acts and isinstance(acts[aid][1], dict) and acts[aid][1].get("review") == "approved":
                own.append((aid, acts[aid][1]))
        kinds = {a.get("kind") if "kind" in a else a.get("type") for _, a in own}
        for kind in PUBLISH_REQUIRED_TYPES:
            if kind not in kinds:
                errors.append((node_path, f"发布前收录的活动中必须至少有一个 {kind} 类活动"))
        for aid, activity in own:
            activity_kind = activity.get("kind") if "kind" in activity else activity.get("type")
            activity_path = acts[aid][0]
            if activity_kind == "quiz":
                items = activity.get("body", {}).get("items", [])
                if len(items) < 5:
                    errors.append((activity_path, f"发布前每个 quiz 至少要有 5 道题，{aid} 现在只有 {len(items)} 道"))
            for target in activity.get("targets", []):
                if target not in nodes or nodes[target][1].get("status") != "published":
                    errors.append((activity_path, f"收录的活动 {aid} 针对了不存在或未发布的知识点 {target}，引用闭包不成立"))

        covered = set()
        for _, activity in own:
            if "kind" in activity:
                targets = activity.get("targets", [])
                for ref in activity_misconception_refs(activity):
                    if ":" in ref:
                        target, misconception = ref.rsplit(":", 1)
                        if target == nid:
                            covered.add(misconception)
                    elif targets == [nid]:
                        covered.add(ref)
            elif nid in activity.get("targets", []):
                covered.update(activity.get("misconceptions", []))
        for misconception in node.get("misconceptions", []):
            mid = misconception.get("id") if isinstance(misconception, dict) else None
            if mid and mid not in covered:
                errors.append((node_path, f"误区 {mid} 还没有被收录活动中的题目或实验覆盖，不能发布"))
    return errors


def chinese_number(value):
    """把 0～99 的整数写成提示泄露检查使用的中文数字。"""
    if not 0 <= value <= 99:
        return None
    digits = "零一二三四五六七八九"
    if value < 10:
        return digits[value]
    tens, ones = divmod(value, 10)
    prefix = "" if tens == 1 else digits[tens]
    return prefix + "十" + (digits[ones] if ones else "")


def number_pattern(text):
    return re.compile(rf"(?<![0-9]){re.escape(text)}(?![0-9])")


def hint_leaks(item):
    """返回数字题、分数题中泄露正确答案的写法。"""
    answer = item.get("answer", {})
    hints = item.get("hints", [])
    if not isinstance(answer, dict) or not isinstance(hints, list):
        return []
    patterns = []
    if answer.get("type") == "number" and isinstance(answer.get("value"), (int, float)):
        value = answer["value"]
        patterns.append(number_pattern(str(value)))
        if isinstance(value, float) and value.is_integer():
            patterns.append(number_pattern(str(int(value))))
    elif answer.get("type") == "fraction":
        numerator, denominator = answer.get("numerator"), answer.get("denominator")
        if isinstance(numerator, int) and isinstance(denominator, int) and denominator > 0:
            pairs = [(numerator, denominator)]
            if answer.get("accept_equivalent"):
                from math import gcd
                divisor = gcd(abs(numerator), denominator)
                reduced = (numerator // divisor, denominator // divisor)
                if reduced != pairs[0]:
                    pairs.append(reduced)
            for a, b in pairs:
                patterns.extend([
                    number_pattern(f"{a}/{b}"),
                    number_pattern(f"{b}分之{a}"),
                ])
                if 0 <= a <= 99 and 0 <= b <= 99:
                    patterns.append(re.compile(re.escape(f"{chinese_number(b)}分之{chinese_number(a)}")))
    leaked = []
    for hint in hints:
        if not isinstance(hint, str):
            continue
        for pattern in patterns:
            match_ = pattern.search(hint)
            if match_:
                leaked.append(match_.group(0))
    return leaked


def check_svg(path):
    """按内容规格的白名单检查一个 SVG，返回错误文字列表。"""
    errors = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"SVG 读取失败：{exc}"]
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        errors.append("SVG 不允许 DOCTYPE 或实体")
    for match_ in re.finditer(r"<\?([A-Za-z0-9_-]+).*?\?>", text, re.S):
        declaration = match_.group(1).lower() == "xml" and match_.start() == 0
        if not declaration:
            errors.append("SVG 只允许第一行的 XML 声明，不允许其他处理指令")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return errors + [f"SVG 不是合法的 XML：{exc}"]
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
        if tag not in SVG_ELEMENTS:
            errors.append(f"SVG 元素不在白名单：{tag or element.tag}")
        if tag == "style":
            errors.append("SVG 不允许 style 元素")
        for raw_name, value in element.attrib.items():
            if raw_name == "{http://www.w3.org/1999/xlink}href":
                name = "xlink:href"
            else:
                name = raw_name.rsplit("}", 1)[-1]
            if name not in SVG_ATTRIBUTES:
                errors.append(f"SVG 属性不在白名单：{name}")
            if name == "style":
                errors.append("SVG 不允许 style 属性")
            if name in ("href", "xlink:href") and not re.fullmatch(r"#[A-Za-z_][A-Za-z0-9_.:-]*", value):
                errors.append(f"SVG 的 {name} 只能引用文件内的 #id")
            for url in re.finditer(r"url\s*\(", value, re.I):
                if not re.match(r"url\(#[A-Za-z_][A-Za-z0-9_.:-]*\)", value[url.start():]):
                    errors.append("SVG 属性里的 url(…) 只能是 url(#id)")
    return errors


def run(repo, base="origin/main", branch="", labels=()):
    """对 repo 的 HEAD 相对 base 做全部检查，返回 Result。"""
    repo = Path(repo)
    r = Result()
    labels = set(labels)
    override = OVERRIDE_LABEL in labels

    diff = git(repo, "diff", "--name-status", "-M", f"{base}...HEAD")
    if diff.returncode != 0:
        raise RuntimeError(f"无法和 {base} 比较：{diff.stderr.strip()}")
    changes = []
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

    def activity_targets(act_dir):
        """活动归属：优先看当前版本，两种形态都支持，删除时看 base。"""
        candidates = []
        for name in ("activity.yaml", "manifest.yaml"):
            current = repo / act_dir / name
            candidates.append(current.read_text(encoding="utf-8") if current.exists() else None)
        for name in ("activity.yaml", "manifest.yaml"):
            candidates.append(base_text(f"{act_dir}/{name}"))
        for text in candidates:
            if text is None:
                continue
            try:
                doc = load_yaml_text(text)
            except Exception:
                return None
            return doc.get("targets", []) if isinstance(doc, dict) else None
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
        status_of = {}
        for st, p, old in changes:
            status_of[p] = st
            if old:
                status_of[old] = "D"   # 改名时旧路径相当于删除
        for p in changed:
            shared = None
            act_prompt = ACT_PROMPT.match(p) or ACT_REVIEW.match(p)
            node_review = NODE_REVIEW.match(p) if not act_prompt else None
            if prefix == "kp/":
                ok = (p.startswith("content/") and not match(p, PROTECTED)) or bool(act_prompt)
                targets = None
                if node_review:
                    ok = node_review.group(1) == node_id and status_of.get(p) != "D"
                elif p.startswith("docs/reviews/") and status_of.get(p) == "D":
                    ok = False   # 审查记录是证据，不能在知识点分支里删
                if ok and p.startswith("content/nodes/"):
                    ok = Path(p).stem == node_id
                elif ok and p.startswith("content/activities/"):
                    parts = Path(p).parts
                    targets = activity_targets("/".join(parts[:3])) if len(parts) >= 3 else None
                elif ok and p.startswith("content/assets/"):
                    # 知识点自己的配图放在 content/assets/<知识点 id>/ 下（docs/workflow.md）
                    parts = Path(p).parts
                    ok = len(parts) >= 4 and parts[2] == node_id and p.endswith(".svg")
                elif ok and p.startswith("content/"):
                    ok = False
                elif ok and act_prompt:
                    targets = activity_targets(f"content/activities/{act_prompt.group(1)}")
                if ok and (p.startswith("content/activities/") or act_prompt):
                    ok = isinstance(targets, list) and targets == [node_id]
                    if isinstance(targets, list) and node_id in targets and len(targets) > 1:
                        shared = targets
            else:
                ok = not match(p, PROTECTED) and not p.startswith("content/")
                if not ok and TASK_ARCHIVE.match(p) and status_of.get(p) == "A":
                    ok = True   # 整合时新增任务文件留档；改动或删除已有的提示词仍然只能走 arch/
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
            schema = json.loads(f.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[f.name] = schema
        except Exception as exc:
            r.err(f"不是合法的 JSON Schema：{exc}", rel(repo, f))

    def validate(doc, schema_name, path):
        if schema_name not in schemas or doc is None:
            return
        for error in Draft202012Validator(schemas[schema_name]).iter_errors(doc):
            loc = "/".join(str(x) for x in error.absolute_path) or "(根)"
            r.err(f"{loc}：{error.message}", rel(repo, path))

    def load(path):
        try:
            return load_yaml_text(path.read_text(encoding="utf-8"))
        except Exception as exc:
            r.err(f"YAML 解析失败：{exc}", rel(repo, path))
            return None

    # 路径规则针对真正的 content/；测试夹具不参与这些 PR 内容规则。
    content = repo / "content"
    case_paths = {}
    if content.exists():
        for path in sorted(p for p in content.rglob("*") if p.is_symlink()):
            r.err("content/ 下不能有符号链接，只能放普通文件", rel(repo, path).replace(os.sep, "/"))
        for path in sorted(p for p in content.rglob("*") if p.is_file() and not p.is_symlink()):
            relative = rel(repo, path).replace(os.sep, "/")
            parts = Path(relative).parts
            if any(not PATH_SEGMENT.fullmatch(part) or part in (".", "..") for part in parts):
                r.err("路径的每一段只能含 ASCII 字母、数字、点、下划线、连字符，且不能以点开头", relative)
            key = relative.casefold()
            if key in case_paths and case_paths[key] != relative:
                r.err(f"路径只差大小写：{case_paths[key]} 和 {relative}", relative)
            else:
                case_paths[key] = relative

    nodes, acts = {}, {}
    node_root = repo / "content/nodes"
    for f in sorted(node_root.rglob("*.yaml")) if node_root.exists() else []:
        doc = load(f)
        validate(doc, "knode.schema.json", f)
        if isinstance(doc, dict) and "id" in doc:
            if f.stem != doc["id"]:
                r.err(f"文件名必须和 id 一致：{doc['id']}.yaml", rel(repo, f))
            if doc["id"] in nodes:
                r.err(f"知识点 ID 重复：{doc['id']}", rel(repo, f))
            nodes[doc["id"]] = (f, doc)

    activity_root = repo / "content/activities"
    activity_dirs = sorted(p for p in activity_root.iterdir() if p.is_dir()) if activity_root.exists() else []
    for directory in activity_dirs:
        entries = {p.name for p in directory.iterdir()}
        structured_file = directory / "activity.yaml"
        manifest_file = directory / "manifest.yaml"
        if entries == {"activity.yaml"}:
            pass
        elif entries == {"manifest.yaml", "index.html"}:
            pass
        else:
            r.err("活动目录要么只有 activity.yaml，要么只有 manifest.yaml + index.html，不能混用或缺少文件", rel(repo, directory))

        primary = structured_file if structured_file.exists() else manifest_file if manifest_file.exists() else None
        if primary is None:
            continue
        doc = load(primary)
        validate(doc, "activity-def.schema.json" if primary.name == "activity.yaml" else "activity.schema.json", primary)
        if isinstance(doc, dict) and "id" in doc:
            if directory.name != doc["id"]:
                r.err(f"活动目录名必须和 id 一致：content/activities/{doc['id']}/", rel(repo, primary))
            if doc["id"] in acts:
                r.err(f"活动 ID 重复：{doc['id']}", rel(repo, primary))
            acts[doc["id"]] = (primary, doc)

    # 引用：知识点之间、知识点和活动之间（双向）。
    for nid, (f, doc) in nodes.items():
        for other in doc.get("prerequisites", []) + doc.get("related", []):
            if other not in nodes:
                r.err(f"引用了不存在的知识点：{other}", rel(repo, f))
        for aid in doc.get("activities", []):
            if aid not in acts:
                r.err(f"activities 里的活动不存在：{aid}", rel(repo, f))
            elif nid not in acts[aid][1].get("targets", []):
                r.err(f"活动 {aid} 的 targets 里没有这个知识点，两边要互相写上", rel(repo, f))
    for aid, (f, doc) in acts.items():
        targets = doc.get("targets", [])
        for target in targets:
            if target not in nodes:
                r.err(f"targets 指向不存在的知识点：{target}", rel(repo, f))
            elif aid not in nodes[target][1].get("activities", []):
                r.err(f"知识点 {target} 的 activities 里没有这个活动，两边要互相写上", rel(repo, f))
        if "kind" not in doc:
            target_misconceptions = {m["id"] for target in targets if target in nodes for m in nodes[target][1].get("misconceptions", []) if isinstance(m, dict) and "id" in m}
            for misconception in doc.get("misconceptions", []):
                if misconception not in target_misconceptions:
                    r.err(f"misconceptions 里的误区 {misconception} 不在目标知识点的误区列表里", rel(repo, f))

    # 前置关系无环。
    state = {}

    def dfs(node_id, stack):
        state[node_id] = 1
        for prerequisite in nodes[node_id][1].get("prerequisites", []):
            if prerequisite not in nodes:
                continue
            if state.get(prerequisite) == 1:
                r.err(f"前置关系有环：{' → '.join(stack + [prerequisite])}", rel(repo, nodes[node_id][0]))
                continue
            if not state.get(prerequisite):
                dfs(prerequisite, stack + [prerequisite])
        state[node_id] = 2

    for node_id in nodes:
        if not state.get(node_id):
            dfs(node_id, [node_id])

    # 结构化活动的题目、配图、提示和引擎等级。
    for aid, (f, doc) in acts.items():
        if "kind" not in doc:
            continue
        item_ids = set()
        for item in activity_items(doc):
            item_id = item.get("id")
            if item_id is not None:
                if item_id in item_ids:
                    r.err(f"同一活动内题目 id 重复：{item_id}", rel(repo, f))
                item_ids.add(item_id)
            for leaked in hint_leaks(item):
                r.err(f"题目 {item_id} 的提示泄露了正确答案：{leaked}", rel(repo, f))
            answer = item.get("answer", {})
            if isinstance(answer, dict) and answer.get("type") == "choice":
                correct_texts = [c.get("text") for c in answer.get("choices", []) if isinstance(c, dict) and c.get("correct") and isinstance(c.get("text"), str)]
                for hint in item.get("hints", []):
                    if isinstance(hint, str):
                        for correct in correct_texts:
                            if correct in hint:
                                r.warn(f"题目 {item_id} 的提示可能泄露了正确选项原文：{correct}", rel(repo, f))

            answer_type = answer.get("type") if isinstance(answer, dict) else None
            required = ENGINE_REQUIREMENTS["answer"].get(answer_type, 1)
            if isinstance(doc.get("engine"), int) and doc["engine"] < required:
                r.err(f"活动 {aid} 的 engine 为 {doc['engine']}，但答案类型 {answer_type} 至少需要 {required} 级引擎", rel(repo, f))

        for ref in activity_misconception_refs(doc):
            targets = doc.get("targets", [])
            if len(targets) == 1:
                if ":" in ref:
                    target, misconception = ref.rsplit(":", 1)
                    r.err(f"活动只有一个目标知识点，误区应直接写 id，不要写成 {ref}", rel(repo, f))
                else:
                    target, misconception = targets[0], ref
            else:
                if ":" not in ref:
                    r.err(f"共享活动的误区必须写成 <知识点 id>:<误区 id>：{ref}", rel(repo, f))
                    continue
                target, misconception = ref.rsplit(":", 1)
                if target not in targets:
                    r.err(f"误区引用 {ref} 的知识点不在活动 targets 里", rel(repo, f))
                    continue
            if target in nodes:
                valid = {m.get("id") for m in nodes[target][1].get("misconceptions", []) if isinstance(m, dict)}
                if misconception not in valid:
                    r.err(f"题目引用的误区 {ref} 不在目标知识点的误区列表里", rel(repo, f))

        for figure in activity_figures(doc):
            figure_type = figure.get("type")
            if figure_type in ("pie", "rect") and isinstance(figure.get("shaded"), int) and isinstance(figure.get("parts"), int) and figure["shaded"] > figure["parts"]:
                r.err(f"配图 {figure_type} 的 shaded 不能超过 parts", rel(repo, f))
            if figure_type == "rect-unequal" and isinstance(figure.get("shaded"), list) and isinstance(figure.get("widths"), list):
                if any(isinstance(index, int) and index >= len(figure["widths"]) for index in figure["shaded"]):
                    r.err("rect-unequal 配图的 shaded 下标超出 widths 的范围", rel(repo, f))
            if figure_type == "svg" and isinstance(figure.get("src"), str):
                src = figure["src"]
                if not (src.startswith("content/assets/") and src.endswith(".svg")) or ".." in src.split("/"):
                    r.err(f"svg 配图必须是 content/assets/ 下的 .svg 文件（这样才会经过 SVG 白名单检查）：{src}", rel(repo, f))
                elif not (repo / src).is_file():
                    r.err(f"svg 配图引用的文件不存在：{src}", rel(repo, f))
            required = ENGINE_REQUIREMENTS["figure"].get(figure_type, 1)
            if isinstance(doc.get("engine"), int) and doc["engine"] < required:
                r.err(f"活动 {aid} 的 engine 为 {doc['engine']}，但配图类型 {figure_type} 至少需要 {required} 级引擎", rel(repo, f))
        required = ENGINE_REQUIREMENTS["kind"].get(doc.get("kind"), 1)
        if isinstance(doc.get("engine"), int) and doc["engine"] < required:
            r.err(f"活动 {aid} 的 engine 为 {doc['engine']}，但活动类型 {doc.get('kind')} 至少需要 {required} 级引擎", rel(repo, f))

    # SVG 白名单。
    asset_root = repo / "content/assets"
    for svg in sorted(asset_root.rglob("*.svg")) if asset_root.exists() else []:
        for message in check_svg(svg):
            r.err(message, rel(repo, svg))

    # 发布门禁只看已发布知识点引用的 approved 活动。
    for f, message in check_publish_gate(nodes, acts):
        r.err(message, rel(repo, f))

    # ---------- 3. ID 检查 ----------
    for st, p, old in changes:
        src = old or p
        is_node = src.startswith("content/nodes/") and src.endswith(".yaml")
        is_act = src.startswith("content/activities/") and src.endswith(("/manifest.yaml", "/activity.yaml"))
        if not (is_node or is_act):
            continue
        if st in ("D", "R"):
            msg = f"删除或改名了已有的{'知识点' if is_node else '活动'}文件：{src}。ID 永不改动"
            r.warn(msg + "（已放行）", src) if override else r.err(msg, src)
            continue
        if st == "M":
            def yaml_id(text):
                try:
                    doc = load_yaml_text(text or "")
                except Exception:
                    return None
                return doc.get("id") if isinstance(doc, dict) else None

            old_id = yaml_id(base_text(src))
            new_id = yaml_id((repo / p).read_text(encoding="utf-8"))
            if old_id is not None and old_id != new_id:
                r.err(f"id 从 {old_id} 改成了 {new_id}。ID 永不改动", p)

    # ---------- 4. 文案检查 ----------
    for nid, (f, doc) in nodes.items():
        for key in KID_FACING_NODE:
            if any(FORBIDDEN_WORD in text for text in texts(doc.get(key))):
                r.err(f"给孩子看的「{key}」里出现了「{FORBIDDEN_WORD}」", rel(repo, f))
    for aid, (f, doc) in acts.items():
        if "kind" not in doc:
            for key in KID_FACING_ACT:
                if any(FORBIDDEN_WORD in text for text in texts(doc.get(key))):
                    r.err(f"给孩子看的「{key}」里出现了「{FORBIDDEN_WORD}」", rel(repo, f))
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


def texts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from texts(item)


def main():
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    base = "origin/" + os.environ.get("BASE_REF", "main")
    branch = os.environ.get("HEAD_BRANCH") or git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    labels = {label.strip() for label in os.environ.get("PR_LABELS", "").split(",") if label.strip()}
    try:
        result = run(repo, base, branch, labels)
    except RuntimeError as exc:
        print(f"检查没有运行：{exc}")
        print(f"本地运行前先执行：git fetch origin {base.split('/', 1)[1]}:refs/remotes/{base}")
        return 2
    for line in result.info:
        print(line)
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    for kind, items in (("warning", result.warnings), ("error", result.errors)):
        for file, message in items:
            if gha:
                print(f"::{kind}{' file=' + file if file else ''}::{message}")
            else:
                print(f"[{'提醒' if kind == 'warning' else '错误'}] {file + '：' if file else ''}{message}")
    print("通过" if not result.errors else f"未通过：{len(result.errors)} 个错误")
    return 1 if result.errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
# END OF FILE
