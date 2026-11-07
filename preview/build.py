"""生成一次性试玩预览页（单个 HTML 文件，内容和配图都嵌在里面）。

用法：
    python preview/build.py --root <内容根目录> [--root <另一个根目录> ...] --out <输出文件>

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


def build(roots):
    stars, figures = [], {}
    for node_id, act_ids in STARS:
        node = yaml.safe_load(find_node(roots, node_id).read_text(encoding="utf-8"))
        acts = []
        for aid in act_ids:
            manifest = find(roots, f"content/activities/{aid}/manifest.yaml", required=False)
            if manifest:
                m = yaml.safe_load(manifest.read_text(encoding="utf-8"))
                page = find(roots, f"content/activities/{aid}/index.html").read_text(encoding="utf-8")
                acts.append({"id": m["id"], "kind": "simulation", "title": m["title"], "duration_min": m.get("duration_min"),
                             "age_band": m.get("age_band", "G3-4"), "html": page})
                continue
            path = find(roots, f"content/activities/{aid}/activity.yaml", required=False)
            if not path:
                print(f"跳过（还没有）：{aid}")
                continue
            act = yaml.safe_load(path.read_text(encoding="utf-8"))
            srcs = []
            collect_srcs(act.get("body"), srcs)
            for src in srcs:
                if src not in figures:
                    figures[src] = prep_svg(find(roots, src).read_text(encoding="utf-8"), f"f{len(figures)}")
            acts.append({k: act[k] for k in ("id", "kind", "title", "duration_min", "body") if k in act})
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
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    data = build(a.root)
    blob = json.dumps(data, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", blob)
    a.out.write_text(html, encoding="utf-8")
    n = sum(len(s["activities"]) for s in data["stars"])
    print(f"写好了 {a.out}：{len(data['stars'])} 颗星，{n} 个活动，{len(data['figures'])} 张配图")


if __name__ == "__main__":
    main()
