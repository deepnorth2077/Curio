"""生成一次性试玩预览页（单个 HTML 文件，内容和配图都嵌在里面），以及原型读的内容包。

用法：
    python preview/build.py --root <内容根目录> [--root <另一个根目录> ...] --out <输出文件>
    python preview/build.py --root . --bundle prototype/content.js
    python preview/build.py --root . --trial-bundle prototype/trial-content.js
    python preview/build.py --root . --constellation zero-to-one --out prototype/preview/zero-to-one/index.html

--bundle：把可选的知识点目录、所有 status: published 的知识点、它们卡片里列的已批准（review: approved）活动和配图打成一个 JS 文件，
原型（prototype/index.html）用 <script src="content.js"> 读。
--trial-bundle：为首页额外生成点名试玩的星座目录和未发布活动。默认引用仓库里的动手探索 HTML；
部署时加 --copy-trial-modules，把清单内需要的 HTML 复制到输出目录旁边的 trial-modules/。

每个根目录下应当有 content/nodes/、content/activities/、content/assets/。
可以给多个根目录（例如三个 kp/ 分支各导出一份），按 CONSTELLATIONS 里列的顺序取知识点和活动。
页面不联网、不保存进度：刷新就从头开始。
"""
import argparse
import json
import os
import re
import shutil
from pathlib import Path

import yaml

# 每个星座一张试玩页。星座里的星按顺序列；每颗星下面的活动也按这个顺序显示。
# 动手探索的模块（manifest.yaml + index.html）排在最前面；找不到的活动会跳过。
CONSTELLATIONS = {
    "life-manual": ("生命的说明书", [
        ("biology.cell.cell-intro", ["act.simulation.cell-zoom-01", "act.quiz.cell-intro-01"]),
        ("biology.genetics.dna-intro", ["act.simulation.dna-book-01", "act.quiz.dna-intro-01"]),
        ("biology.genetics.chromosome-intro", [
            "act.simulation.chromosome-pack-01",
            "act.quiz.chromosome-intro-01",
            "act.reflection.chromosome-intro-01",
        ]),
    ]),
    "chocolate": ("乘法的秘密", [
        ("math.operation.distributive-law", ["act.simulation.chocolate-split-01"]),
    ]),
    # 「0 和 1 之间」：分数、小数、比与百分数（docs/constellations/zero-to-one/index.md）。做完一颗加一颗
    "zero-to-one": ("0 和 1 之间", [
        ("math.fraction.unit-fraction", ["act.simulation.fair-cut-01", "act.quiz.unit-fraction-01"]),
        ("math.fraction.count-on-line", ["act.simulation.hop-line-01", "act.quiz.count-on-line-01"]),
        ("math.fraction.the-whole", ["act.simulation.whose-half-01", "act.quiz.the-whole-01"]),
        ("math.decimal.tenths", ["act.simulation.zoom-line-01", "act.quiz.tenths-01"]),
        ("math.decimal.compare-add", ["act.simulation.place-slots-01", "act.quiz.compare-add-01"]),
        ("math.decimal.point-shift", ["act.simulation.slide-rule-01", "act.quiz.point-shift-01"]),
        ("math.fraction.equivalent", ["act.simulation.recut-01", "act.quiz.equivalent-01"]),
        ("math.fraction.as-division", ["act.simulation.share-table-01", "act.quiz.as-division-01"]),
        ("math.fraction.compare", ["act.simulation.match-cuts-01", "act.quiz.fraction-order-01"]),
        ("math.fraction.add-subtract", ["act.simulation.measuring-cup-01", "act.quiz.add-subtract-01"]),
        ("math.operation.multiply-shrinks", ["act.simulation.stretch-bar-01", "act.quiz.multiply-shrinks-01"]),
        ("math.fraction.multiply", ["act.simulation.cross-cut-01", "act.quiz.fraction-multiply-01"]),
        ("math.fraction.divide", ["act.simulation.pour-cups-01", "act.quiz.fraction-divide-01"]),
        ("math.ratio.meaning", ["act.simulation.mix-drink-01", "act.quiz.ratio-meaning-01"]),
        ("math.ratio.sharing", ["act.simulation.ratio-chute-01", "act.quiz.ratio-sharing-01"]),
        ("math.ratio.proportion", ["act.simulation.stretch-frame-01", "act.quiz.proportion-01"]),
        ("math.percent.meaning", ["act.simulation.hundred-grid-01", "act.quiz.percent-meaning-01"]),
        ("math.number.same-point", ["act.simulation.three-rulers-01", "act.quiz.same-point-01"]),
        ("math.percent.change", ["act.simulation.grow-shrink-01", "act.quiz.percent-change-01"]),
    ]),
}

TEMPLATE = Path(__file__).with_name("template.html")

# 每组第一颗星在试玩页里有一个跳转入口，便于分几次验收。
ZERO_TO_ONE_GROUPS = {
    "math.fraction.unit-fraction": "一份有多大",
    "math.decimal.tenths": "小数：把一份再切十份",
    "math.fraction.equivalent": "一个数，很多名字",
    "math.operation.multiply-shrinks": "乘除的怪事",
    "math.ratio.meaning": "比：两个量的关系",
    "math.percent.meaning": "百分数：大家说好的分母",
}


# 首页、地铁和独立试玩页共用这份星序与分组；卡片仍决定唯一的年级和主题。
COURSE_DATA = yaml.safe_load(Path(__file__).with_name("courses.yaml").read_text(encoding="utf-8"))
if COURSE_DATA["version"] != 1:
    raise ValueError("不支持的试玩课程目录版本")
GROUPS = {"zero-to-one": ZERO_TO_ONE_GROUPS}
CHART_THEMES = {"zero-to-one": "num", "chocolate": "num", "life-manual": "life"}
for slug, course in COURSE_DATA["courses"].items():
    stars = []
    GROUPS[slug] = {}
    for group in course["groups"]:
        GROUPS[slug][group["stars"][0][0]] = group["title"]
        for nid, activity in group["stars"]:
            stars.append((nid, [f"act.simulation.{activity}-01", f"act.quiz.{activity}-01"]))
    CONSTELLATIONS[slug] = course["title"], stars
    CHART_THEMES[slug] = course["theme"]


def find(roots, rel, required=True):
    for r in roots:
        p = r / rel
        if p.is_file():
            return p
    if required:
        raise SystemExit(f"找不到文件：{rel}")
    return None


def find_node(roots, node_id, prefer_published=False):
    first = None
    for r in roots:
        for path in (r / "content/nodes").rglob(f"{node_id}.yaml"):
            if first is None:
                first = path
            if not prefer_published or yaml.safe_load(path.read_text(encoding="utf-8")).get("status") == "published":
                return path
    if first:
        return first
    raise SystemExit(f"找不到知识点卡：{node_id}")


def prep_svg(text, prefix):
    """去掉 XML 声明和注释，给 id 加前缀，免得几张图放在同一页时 id 撞车。"""
    text = re.sub(r"<\?xml[^>]*\?>", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{prefix}-{m.group(1)}"', text)
    text = re.sub(r'\b(xlink:href|href)="#([^"]+)"', lambda m: f'{m.group(1)}="#{prefix}-{m.group(2)}"', text)
    text = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{prefix}-{m.group(1)})", text)
    return text.strip()


def collect_srcs(obj, out):
    if isinstance(obj, dict):
        if obj.get("type") == "svg" and "src" in obj:
            out.append(obj["src"])
        for v in obj.values():
            collect_srcs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_srcs(v, out)


def not_approved(doc, aid, only_approved):
    """只收已批准的活动时，没批准的返回 True 并打印原因（和 tools/build_release.py 的筛选一致）。"""
    if only_approved and doc.get("review") != "approved":
        print(f"跳过（还没批准，review: {doc.get('review')}）：{aid}")
        return True
    return False


def load_activity(roots, aid, figures, only_approved=False, module_src=None):
    """读一个活动：动手探索（manifest.yaml + index.html）或数据活动（activity.yaml）。配图收进 figures。
    找不到返回 None；only_approved 时，review 不是 approved 的也返回 None，配图不收。"""
    manifest = find(roots, f"content/activities/{aid}/manifest.yaml", required=False)
    if manifest:
        m = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        if not_approved(m, aid, only_approved):
            return None
        entry = find(roots, f"content/activities/{aid}/{m.get('entry', 'index.html')}")
        activity = {"id": m["id"], "kind": "simulation", "title": m["title"], "duration_min": m.get("duration_min"),
                    "age_band": m.get("age_band", "G3-4"), "targets": m.get("targets", [])}
        if module_src:
            activity["src"] = module_src(entry, aid)
        else:
            activity["html"] = entry.read_text(encoding="utf-8")
        return activity
    path = find(roots, f"content/activities/{aid}/activity.yaml", required=False)
    if not path:
        print(f"跳过（还没有）：{aid}")
        return None
    act = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not_approved(act, aid, only_approved):
        return None
    srcs = []
    collect_srcs(act.get("body"), srcs)
    for src in srcs:
        if src not in figures:
            figures[src] = prep_svg(find(roots, src).read_text(encoding="utf-8"), f"f{len(figures)}")
    return {k: act[k] for k in ("id", "kind", "title", "duration_min", "age_band", "targets", "body") if k in act}


def bundle_node(node, activity_ids):
    return {
        "id": node["id"], "title": node["title"], "theme": node["theme"], "grade": node["grade"],
        "unit": node.get("unit", ""), "prerequisites": node.get("prerequisites", []),
        "driving_question": node.get("driving_question", ""), "objectives": node.get("objectives", []),
        "misconceptions": node.get("misconceptions", []), "lenses": node.get("lenses", []),
        "activities": activity_ids,
    }


def build_bundle(roots):
    """原型用的内容包：所有已发布的知识点（同一个 id 取第一个根目录里的），活动按知识点卡里的顺序。
    孩子在原型里玩的就是这份，所以只收 review: approved 的活动；没批准的跳过。"""
    nodes, acts, figures, seen = [], {}, {}, set()
    for r in roots:
        for path in sorted((r / "content/nodes").rglob("*.yaml")):
            node = yaml.safe_load(path.read_text(encoding="utf-8"))
            if node.get("status") != "published" or node["id"] in seen:
                continue
            seen.add(node["id"])
            ids = []
            for aid in node.get("activities", []):
                if aid not in acts:
                    a = load_activity(roots, aid, figures, only_approved=True)
                    if not a:
                        continue
                    acts[aid] = a
                ids.append(aid)
            nodes.append(bundle_node(node, ids))
    bundle = {"nodes": nodes, "activities": acts, "figures": figures}
    catalog = find(roots, "content/catalog/points.yaml", required=False)
    if catalog:
        bundle["catalog"] = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    return bundle


def build_trial_bundle(roots, output_dir, copy_modules=False):
    """首页额外读的试玩清单。只让点名的未发布活动进入试玩包。"""
    nodes, activities, figures, catalog = [], {}, {}, {}

    def module_src(entry, aid):
        if copy_modules:
            dest = output_dir / "trial-modules" / f"{aid}.html"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry, dest)
            return dest.relative_to(output_dir).as_posix()
        return Path(os.path.relpath(entry, output_dir)).as_posix()

    for series, chart_theme in CHART_THEMES.items():
        name, stars = CONSTELLATIONS[series]
        group, group_start = 1, 1
        group_title = "掰巧克力" if series == "chocolate" else name
        for star, (nid, allowed_ids) in enumerate(stars, 1):
            # 多个根目录合并时，任一根里已发布的同 ID 都会进入正式包。
            path = find_node(roots, nid, prefer_published=len(roots) > 1)
            node = yaml.safe_load(path.read_text(encoding="utf-8"))
            published = node["status"] == "published"
            if series == "life-manual" and not published:
                continue
            if nid in GROUPS.get(series, {}):
                if star > 1:
                    group += 1
                group_start, group_title = star, GROUPS[series][nid]
            catalog[nid] = {
                "series": series, "series_title": name, "star": star, "chart_theme": chart_theme,
                "group": group, "group_title": group_title, "group_order": star - group_start + 1,
            }
            # 晋级后完全交回正式内容包的审核筛选；试玩包只保留位置。
            if published:
                continue
            ids = [aid for aid in allowed_ids if aid in node.get("activities", [])]
            for aid in ids:
                activity = load_activity(roots, aid, figures, module_src=module_src)
                if not activity or nid not in activity["targets"]:
                    raise SystemExit(f"试玩清单的活动缺失或不属于 {nid}：{aid}")
                activities[aid] = activity
            nodes.append(bundle_node(node, ids))
    if copy_modules:
        # 重建同一部署目录时也撤下已转正或已移出名单的旧试玩入口。
        for old in (output_dir / "trial-modules").glob("act.simulation.*.html"):
            if old.stem not in activities:
                old.unlink()
    return {"nodes": nodes, "activities": activities, "figures": figures, "catalog": catalog,
            "diagram_series": ["life-manual", *COURSE_DATA["courses"]], "overviews": COURSE_DATA["overviews"]}


def build(roots, constellation="life-manual"):
    name, star_list = CONSTELLATIONS[constellation]
    stars, figures = [], {}
    for node_id, act_ids in star_list:
        node = yaml.safe_load(find_node(roots, node_id).read_text(encoding="utf-8"))
        acts = [a for a in (load_activity(roots, aid, figures) for aid in act_ids) if a]
        stars.append({
            "id": node_id,
            "title": node["title"],
            "dq": node.get("driving_question", ""),
            "misconceptions": {m["id"]: m.get("text", "") for m in node.get("misconceptions", [])},
            "activities": acts,
        })
    data = {"constellation": name, "stars": stars, "figures": figures}
    if constellation in GROUPS:
        data["groups"] = GROUPS[constellation]
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True, type=Path)
    ap.add_argument("--out", type=Path, help="试玩页（单个 HTML 文件）")
    ap.add_argument("--bundle", type=Path, help="原型读的内容包（JS 文件）")
    ap.add_argument("--trial-bundle", type=Path, help="首页额外加载的试玩包（JS 文件）")
    ap.add_argument("--copy-trial-modules", action="store_true", help="把试玩模块复制到可独立部署的同级目录")
    ap.add_argument("--constellation", default="life-manual", choices=sorted(CONSTELLATIONS), help="试玩页做哪个星座")
    a = ap.parse_args()
    if not (a.out or a.bundle or a.trial_bundle):
        ap.error("--out、--bundle 和 --trial-bundle 至少要给一个")
    if a.copy_trial_modules and not a.trial_bundle:
        ap.error("--copy-trial-modules 需要 --trial-bundle")
    if a.out:
        data = build(a.root, a.constellation)
        blob = json.dumps(data, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
        html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", blob)
        a.out.write_text(html, encoding="utf-8")
        n = sum(len(s["activities"]) for s in data["stars"])
        print(f"写好了 {a.out}：{len(data['stars'])} 颗星，{n} 个活动，{len(data['figures'])} 张配图")
    if a.bundle:
        data = build_bundle(a.root)
        blob = json.dumps(data, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
        a.bundle.write_text("// 自动生成，不要手改：python preview/build.py --root . --bundle prototype/content.js\n"
                            f"window.CURIO_CONTENT={blob};\n", encoding="utf-8")
        print(f"写好了 {a.bundle}：{len(data['nodes'])} 个知识点，{len(data['activities'])} 个活动，{len(data['figures'])} 张配图")
    if a.trial_bundle:
        data = build_trial_bundle(a.root, a.trial_bundle.parent, a.copy_trial_modules)
        blob = json.dumps(data, ensure_ascii=False, sort_keys=True)
        a.trial_bundle.write_text("// 自动生成：python preview/build.py --root . --trial-bundle prototype/trial-content.js\n"
                                  f"window.CURIO_TRIAL={blob};\n", encoding="utf-8")
        print(f"写好了 {a.trial_bundle}：{len(data['catalog'])} 颗星，{len(data['activities'])} 个试玩活动")


if __name__ == "__main__":
    main()
