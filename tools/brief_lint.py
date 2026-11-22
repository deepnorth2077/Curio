"""检查动手探索原稿、知识点卡和配套挑战。CI 用 --base，也可以直接传入要审的文件。

查重按被检稿中匹配的正文字符数计算，同一篇对照稿超过 30% 即报告。标题、表头、
经验编号和生成档不计。能否产生惊讶、动作能否展示掌握、误区是否真是两种想法由人审。
"""
import argparse
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LESSONS = Path(".claude/skills/curio-anatomy/references/lessons.md")
BRIEF = re.compile(r"prompts/act\.simulation\.[a-z0-9-]+\.md$")
LESSON = re.compile(r"- (\d+)")
REQUIRED = ("一句话实物", "零件清单", "哇", "验收用例", "实现")
TABLE_RULE = re.compile(r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?")
OVERLAP_LIMIT = 0.30


def normalized(value):
    return "".join(re.findall(r"\w+", str(value), re.UNICODE)).casefold()


def markdown(text):
    """只取原稿正文；代码围栏里的示例标题不构成设计章节。"""
    text = re.sub(r"\A---\n.*?\n---(?:\n|$)", "", text, count=1, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    sections = defaultdict(list)
    title = ""
    fence = ""
    for line in text.splitlines():
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence) and not stripped.strip(fence[0]):
                fence = ""
            continue
        match = re.match(r"^(`{3,}|~{3,})", stripped)
        if match:
            fence = match[1]
            # 代码示例可以列在验收说明；实现一节只许列经验编号。
            if title == "实现":
                sections[title].append(stripped)
            continue
        if line.startswith("## "):
            title = re.sub(r"^\d+[.、．]\s*", "", line[3:].strip())
            title = "哇" if re.fullmatch(r"[「“]?哇[」”]?(?:时刻)?", title) else title
        elif not stripped.startswith("#") or title == "实现":
            sections[title].append(line)
    return sections


def paragraphs(sections):
    """段落、列表项和表格数据行是比较单位，普通正文允许跨行折行。"""
    blocks = []
    for lines in sections.values():
        paragraph = []
        for index, line in enumerate(lines):
            following = lines[index + 1] if index + 1 < len(lines) else ""
            line = line.strip()
            standalone = re.match(r"^(?:[-*] |\d+\. |[|>])", line)
            if line and not standalone and not TABLE_RULE.fullmatch(line) and not TABLE_RULE.fullmatch(following.strip()):
                paragraph.append(line)
                continue
            if paragraph:
                blocks.append("".join(paragraph))
                paragraph.clear()
            if (line and not LESSON.fullmatch(line) and not TABLE_RULE.fullmatch(line)
                    and not TABLE_RULE.fullmatch(following.strip())):
                blocks.append(line)
        if paragraph:
            blocks.append("".join(paragraph))
    keys = [normalized(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", block)) for block in blocks]
    return Counter(key for key in keys if key)


def lint_brief(text, peers, lesson_ids):
    sections = markdown(text)
    errors = []
    for title in REQUIRED:
        if not any(normalized(line) for line in sections.get(title, [])):
            errors.append(f"缺少有正文的「{title}」一节")
    rows = [line.strip() for line in sections.get("验收用例", []) if line.strip()]
    if not any(TABLE_RULE.fullmatch(rule) and "|" in before and sum(
            bool(normalized(cell)) for cell in after.strip("|").split("|")) >= 2
            for before, rule, after in zip(rows, rows[1:], rows[2:])):
        errors.append("验收用例要写成有数据行的输入、预期画面表")
    entries = [line.strip() for line in sections.get("实现", []) if line.strip()]
    for entry in entries:
        match = LESSON.fullmatch(entry)
        if match is None or match[1] not in lesson_ids:
            errors.append(f"「实现」只按行列有效的经验编号（如 - 35），请改写「{entry[:35]}」")
            break
    if re.search(r"\{\{\s*embed:\s*[^}]*lessons\.md\s*(?:#实现\s*)?\}\}", text):
        errors.append("经验编号应直接列在「实现」，请移除嵌入经验全文的指令")
    ours = paragraphs(sections)
    total = sum(len(key) * count for key, count in ours.items())
    for peer, other in peers.items():
        shared = sum(len(key) * count for key, count in (ours & other).items())
        if total and shared / total > OVERLAP_LIMIT:
            errors.append(f"与 {peer} 逐段相同的正文占 {shared / total:.1%}（上限 30%）")
    return errors


def lint_card(doc, truth):
    errors = []
    misconceptions = doc.get("misconceptions") or []
    ids = [item.get("id") for item in misconceptions if isinstance(item, dict)]
    names = [normalized(item.get("text", "")) for item in misconceptions if isinstance(item, dict)]
    if (len(set(ids)) < 3 or len(set(ids)) != len(misconceptions) or
            len(set(names)) != len(misconceptions) or "" in names or None in ids):
        errors.append("知识点卡至少写三种不同误区，各有独立的 id 和说法")
    lenses = {normalized(lens.get("approach", "")) for lens in doc.get("lenses", []) if isinstance(lens, dict)}
    for action in doc.get("objectives", []):
        key = normalized(action)
        if key and (key in lenses or any(key in line for line in truth)):
            errors.append(f"目标照抄了真相表或年龄视角，改写成孩子能演示的动作：{action}")
        elif re.fullmatch(r"(?:能|能够|会)?(?:理解|了解|知道|熟悉|掌握)[^，。；、：,;]+[。.]?", str(action)):
            errors.append(f"请写出能观察到的动作：{action}")
    return errors


def companion_spec(root, doc, path):
    """优先看知识点卡的配对，再按同名活动配对，以支持先写活动后登记卡的流程。"""
    aid = path.parent.name
    if not aid.startswith(("act.simulation.", "act.quiz.")):
        return None
    simulation = aid.startswith("act.simulation.")
    prefix, filename = ("act.quiz.", "activity.yaml") if simulation else ("act.simulation.", "manifest.yaml")
    targets = doc.get("targets", [])
    if len(targets) == 1:
        for card in (root / "content/nodes").rglob(f"{targets[0]}.yaml"):
            ids = yaml.safe_load(card.read_text(encoding="utf-8")).get("activities", [])
            mates = [other for other in ids if other.startswith(prefix)]
            if aid in ids and len(mates) == 1:
                return path.parent.parent / mates[0] / filename
    return path.parent.parent / (prefix + aid.split(".", 2)[-1]) / filename


def simulation_brief(root, activity_id, briefs):
    manifest = root / "content/activities" / activity_id / "manifest.yaml"
    spec = yaml.safe_load(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    ref = spec.get("author", {}).get("prompt_ref", "").partition("#")[0]
    # 旧星可能引用整个分组的总说明；它不是单星原稿，不能套用单星章节要求。
    if ref in briefs:
        return ref
    canonical = f"prompts/{activity_id}.md"
    return canonical if canonical in briefs else None


def related_inputs(root, paths, briefs):
    """从改动的实物、配图或活动定义定位本星的卡和原稿；不把同一组的其他星算进去。"""
    affected = set(paths)
    directories = set()
    for path in paths:
        parts = Path(path).parts
        if len(parts) >= 4 and parts[:2] == ("content", "activities"):
            directories.add(root.joinpath(*parts[:3]))
    for directory in directories:
        for filename in ("activity.yaml", "manifest.yaml"):
            definition = directory / filename
            if not definition.is_file():
                continue
            affected.add(definition.relative_to(root).as_posix())
            doc = yaml.safe_load(definition.read_text(encoding="utf-8"))
            for target in doc.get("targets", []):
                for card in (root / "content/nodes").rglob(f"{target}.yaml"):
                    affected.add(card.relative_to(root).as_posix())
            sim = directory
            if directory.name.startswith("act.quiz."):
                mate = companion_spec(root, doc, definition)
                if not mate or not mate.is_file():
                    continue
                paired = yaml.safe_load(mate.read_text(encoding="utf-8"))
                if doc.get("targets") != paired.get("targets"):
                    continue
                sim = mate.parent
            if sim.name.startswith("act.simulation."):
                brief = simulation_brief(root, sim.name, briefs)
                if brief:
                    affected.add(brief)
    return affected


def accepted(root, brief):
    """已验收的星：status.yaml 里是「完成」，或模块原稿对应的知识点卡都已发布。只改模块、不改原稿时，
    旧原稿不按新模板审（Luka 2026-11-22，#233、#54）。"""
    p = re.fullmatch(r"prompts/(act\.simulation\.[^/]+)\.md", brief)
    manifest = root / "content/activities" / p[1] / "manifest.yaml" if p else None
    if manifest and manifest.is_file():
        targets = yaml.safe_load(manifest.read_text(encoding="utf-8")).get("targets") or []
        cards = [c for t in targets for c in (root / "content/nodes").rglob(f"{t}.yaml")]
        return bool(cards) and all(yaml.safe_load(c.read_text(encoding="utf-8")).get("status") == "published" for c in cards)
    m = re.fullmatch(r"docs/constellations/([^/]+)/stars/(\d+)-[^/]*\.md", brief)
    status = root / "docs/constellations" / m[1] / "status.yaml" if m else None
    if not status or not status.is_file():
        return False
    stars = yaml.safe_load(status.read_text(encoding="utf-8")).get("stars") or []
    return any(star.get("n") == int(m[2]) and star.get("state") == "完成" for star in stars)


def lint_paths(root, paths):
    sources = [p for p in (root / "prompts").glob("act.simulation.*.md")
               if BRIEF.fullmatch(p.relative_to(root).as_posix())]
    sources.extend((root / "docs/constellations").glob("*/stars/*.md"))
    briefs = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(sources)}
    output = []
    edited = set(paths)
    paths = related_inputs(root, paths, briefs)
    changed_briefs = {b for b in paths.intersection(briefs) if b in edited or not accepted(root, b)}
    if changed_briefs:
        lessons = markdown((root / LESSONS).read_text(encoding="utf-8"))["实现"]
        lesson_ids = set(re.findall(r"^(\d+)\.", "\n".join(lessons), re.M))
        fingerprints = {name: paragraphs(markdown(text)) for name, text in briefs.items()}
    for path in sorted(set(paths)):
        errors = []
        file = root / path
        if path in changed_briefs:
            peers = {name: blocks for name, blocks in fingerprints.items() if name != path}
            errors = lint_brief(briefs[path], peers, lesson_ids)
        elif path.startswith("content/nodes/") and path.endswith(".yaml"):
            doc = yaml.safe_load(file.read_text(encoding="utf-8"))
            truth = [normalized(line) for aid in doc.get("activities", [])
                     if aid.startswith("act.simulation.")
                     for title, lines in markdown(briefs.get(simulation_brief(root, aid, briefs), "")).items()
                     if title.startswith("真相表") for line in lines if line.strip()]
            errors = lint_card(doc, truth)
        elif path.startswith("content/activities/") and file.name in ("activity.yaml", "manifest.yaml"):
            doc = yaml.safe_load(file.read_text(encoding="utf-8"))
            if doc.get("kind") == "quiz":
                items = doc["body"]["items"]
                diagnoses = set()
                for item in items:
                    answer = item.get("answer", {})
                    for alternative in answer.get("choices", []) + answer.get("common_wrong", []):
                        if not alternative.get("correct") and alternative.get("misconception"):
                            diagnoses.add(alternative["misconception"])
                    feedback = normalized(item.get("feedback", {}).get("wrong", ""))
                    if feedback and feedback in [normalized(h) for h in item.get("hints", [])]:
                        errors.append(f"{item['id']} 的答错反馈照抄了提示")
                if len(doc.get("targets", [])) == 1 and len(items) >= 5 and len(diagnoses) < 3:
                    errors.append("单颗星的五题挑战至少区分三种误区，核对各错选项和常见错数的标签")
            other = companion_spec(root, doc, file)
            if other and other.is_file():
                companion = yaml.safe_load(other.read_text(encoding="utf-8"))
                if doc.get("targets") == companion.get("targets") and doc.get("age_band") != companion.get("age_band"):
                    errors.append(f"同一颗星的配套活动 {other.parent.name} 与本活动适用年龄不一致")
        output.extend(f"{path}：{message}" for message in errors)
    return output


def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="从指定 Git 基线到 HEAD 的新增或改动文件，例如 origin/main")
    parser.add_argument("paths", nargs="*", help="直接审核的仓库相对路径")
    args = parser.parse_args(argv)
    if bool(args.base) == bool(args.paths):
        parser.error("指定要审核的文件，或使用 --base")
    paths = args.paths
    if args.base:
        changed = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMR", "-z",
                                  f"{args.base}...HEAD"], cwd=root, capture_output=True, check=True)
        paths = changed.stdout.decode().split("\0")[:-1]
    for path in paths:
        if not (root / path).is_file():
            parser.error(f"找不到文件：{path}")
    errors = lint_paths(root, paths)
    for error in errors:
        print(error)
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
