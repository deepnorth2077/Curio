"""生成一次性试玩预览页（单个 HTML 文件，内容和配图都嵌在里面），以及原型读的内容包。

用法：
    python preview/build.py --root <内容根目录> [--root <另一个根目录> ...] --out <输出文件>
    python preview/build.py --root . --bundle prototype/content.js

--bundle：把所有 status: published 的知识点、它们卡片里列的已批准（review: approved）活动和配图打成一个 JS 文件，
原型（prototype/index.html）用 <script src="content.js"> 读。content/ 改了就重新生成一次。

每个根目录下应当有 content/nodes/、content/activities/、content/assets/。
可以给多个根目录（例如三个 kp/ 分支各导出一份），按 STARS 里列的顺序取知识点和活动。
页面不联网、不保存进度：刷新就从头开始。
"""
import argparse
import json
import re
from pathlib import Path

import yaml

CONSTELLATION = "生命的说明书"
# 星座里的星，按顺序；每颗星下面的活动也按这个顺序显示。
# 动手探索的模块（manifest.yaml + index.html）排在最前面；找不到的活动会跳过。
STARS = [
    ("biology.cell.cell-intro", ["act.simulation.cell-zoom-01", "act.explain.cell-intro-01", "act.quiz.cell-intro-01"]),
    ("biology.genetics.dna-intro", ["act.simulation.dna-book-01", "act.explain.dna-intro-01", "act.quiz.dna-intro-01"]),
    ("biology.genetics.chromosome-intro", [
        "act.simulation.chromosome-pack-01",
        "act.explain.chromosome-intro-01",
        "act.quiz.chromosome-intro-01",
        "act.reflection.chromosome-intro-01",
    ]),
]

TEMPLATE = Path(__file__).with_name("template.html")


def find(roots, rel, required=True):
    for r in roots:
        p = r / rel
        if p.is_file():
            return p
    if required:
        raise SystemExit(f"找不到文件：{rel}")
    return None


def find_node(roots, node_id):
    for r in roots:
        hits = list((r / "content/nodes").rglob(f"{node_id}.yaml"))
        if hits:
            return hits[0]
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


def load_activity(roots, aid, figures, only_approved=False):
    """读一个活动：动手探索（manifest.yaml + index.html）或数据活动（activity.yaml）。配图收进 figures。
    找不到返回 None；only_approved 时，review 不是 approved 的也返回 None，配图不收。"""
    manifest = find(roots, f"content/activities/{aid}/manifest.yaml", required=False)
    if manifest:
        m = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        if not_approved(m, aid, only_approved):
            return None
        page = find(roots, f"content/activities/{aid}/{m.get('entry', 'index.html')}").read_text(encoding="utf-8")
        return {"id": m["id"], "kind": "simulation", "title": m["title"], "duration_min": m.get("duration_min"),
                "age_band": m.get("age_band", "G3-4"), "targets": m.get("targets", []), "html": page}
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
            nodes.append({
                "id": node["id"], "title": node["title"], "theme": node["theme"], "grade": node["grade"],
                "unit": node.get("unit", ""), "prerequisites": node.get("prerequisites", []),
                "driving_question": node.get("driving_question", ""), "objectives": node.get("objectives", []),
                "misconceptions": node.get("misconceptions", []), "lenses": node.get("lenses", []), "activities": ids,
            })
    return {"nodes": nodes, "activities": acts, "figures": figures}


def build(roots):
    stars, figures = [], {}
    for node_id, act_ids in STARS:
        node = yaml.safe_load(find_node(roots, node_id).read_text(encoding="utf-8"))
        acts = [a for a in (load_activity(roots, aid, figures) for aid in act_ids) if a]
        stars.append({
            "id": node_id,
            "title": node["title"],
            "dq": node.get("driving_question", ""),
            "misconceptions": {m["id"]: m.get("text", "") for m in node.get("misconceptions", [])},
            "activities": acts,
        })
    return {"constellation": CONSTELLATION, "stars": stars, "figures": figures}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True, type=Path)
    ap.add_argument("--out", type=Path, help="试玩页（单个 HTML 文件）")
    ap.add_argument("--bundle", type=Path, help="原型读的内容包（JS 文件）")
    a = ap.parse_args()
    if not a.out and not a.bundle:
        ap.error("--out 和 --bundle 至少要给一个")
    if a.out:
        data = build(a.root)
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


if __name__ == "__main__":
    main()
