#!/usr/bin/env python3
"""把 #184 原型一次性导出为 catalog/1。运行 python tools/export_catalog.py [--root 仓库] [--out 路径]。"""
import argparse
import json
import re
from pathlib import Path

import yaml

from ci_checks import CATALOG_PATH, check_catalog

ROOT = Path(__file__).resolve().parents[1]


def prototype_array(html, name):
    match = re.search(rf"^\s*const {name}\s*=\s*(\[.*?\])\s*;", html, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"找不到原型数组 {name}")
    literal = match[1]
    if name == "replacements":
        # 这个 JS 数组与 JSON 的差别只有两个未加引号的键。整个数组必须成功解析。
        literal = re.sub(r'([{,]\s*)(old|to)\s*:', r'\1"\2":', literal)
    return json.loads(literal)


def export_catalog(root):
    html = (root / "prototype/index.html").read_text(encoding="utf-8")
    rows = {}
    for nid, title, grade, theme, unit, *tail in prototype_array(html, "RAW"):
        if nid in rows or len(tail) > 1:
            raise ValueError(f"原型行重复或字段过多：{nid}")
        rows[nid] = dict(id=nid, title=title, grade=grade, theme=theme, unit=unit,
                         prerequisites=tail[0] if tail else [])

    cards = {}
    for path in sorted((root / "content/nodes").rglob("*.yaml")):
        card = yaml.safe_load(path.read_text(encoding="utf-8"))
        nid = card["id"]
        if nid in cards:
            raise ValueError(f"课程卡 ID 重复：{nid}")
        cards[nid] = (path, card)
        rows[nid] = {key: card[key] for key in ("id", "title", "grade", "theme", "prerequisites")}
        rows[nid]["unit"] = card.get("unit", "")

    replacements = {}
    for entry in prototype_array(html, "replacements"):
        old, target = entry["old"], entry["to"]
        if old in replacements or old not in rows or old in cards or target not in cards:
            raise ValueError(f"原型的旧占位或接替课程对不上：{old} → {target}")
        replacements[old] = target

    catalog = dict(schema="catalog/1", version=1, points=[], retired=[])
    for nid, row in rows.items():
        point = {key: row[key] for key in ("id", "title", "grade", "theme", "unit")}
        if nid in replacements:
            catalog["retired"].append(dict(point, replaced_by=replacements[nid]))
            continue
        prerequisites = []
        for original in row["prerequisites"]:
            target = replacements.get(original, original)
            if target == nid or target not in rows:
                continue
            # 与原型 NODES 一致：撤下旧占位不能给低年级的星引入高年级前置。
            if target != original and int(rows[target]["grade"][1:]) > int(row["grade"][1:]):
                continue
            if target not in prerequisites:
                prerequisites.append(target)
        catalog["points"].append(dict(point, prerequisites=prerequisites))

    errors = check_catalog(catalog, cards)
    if errors:
        raise ValueError("\n".join(errors))
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or args.root / CATALOG_PATH
    data = yaml.safe_dump(export_catalog(args.root), allow_unicode=True, sort_keys=False).encode("utf-8")
    # 首次入库之后目录独立维护。在另一路径导出可用于比较。
    if output.exists():
        if output.read_bytes() != data:
            parser.exit(1, f"{output} 已有不同内容，另选 --out 路径来比较。\n")
        return
    output.parent.mkdir(exist_ok=True, parents=True)
    with output.open("xb") as file:
        file.write(data)


if __name__ == "__main__":
    main()
