#!/usr/bin/env python3
"""把通过发布门禁的内容构建为不可变发布包。

用法：python tools/build_release.py --content <内容目录> --out <输出目录> [--commit <提交号>]
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

from ci_checks import check_publish_gate

PATH_SEGMENT = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]*$")
MAX_SAFE_INTEGER = 2**53 - 1
COMMIT = re.compile(r"^[0-9a-f]{40}$")


class BuildError(Exception):
    """内容不满足不可变发布的构建要求。"""


def manifest_path(content_root, path):
    relative = path.relative_to(content_root).as_posix()
    return "content/" + relative


def scan_files(content_root):
    """检查全部内容文件的原始字节和路径，再按清单路径排序返回。"""
    if not content_root.is_dir():
        raise BuildError(f"内容目录不存在：{content_root}")
    files = sorted((path for path in content_root.rglob("*") if path.is_file()), key=lambda p: p.relative_to(content_root).as_posix())
    case_paths = {}
    checked = []
    for path in files:
        display_path = manifest_path(content_root, path)
        relative = path.relative_to(content_root).as_posix()
        for segment in relative.split("/"):
            if not PATH_SEGMENT.fullmatch(segment) or segment in (".", ".."):
                raise BuildError(f"{display_path}：路径的每一段只能含 ASCII 字母、数字、点、下划线、连字符，且不能以点开头")
        folded = display_path.casefold()
        if folded in case_paths and case_paths[folded] != display_path:
            raise BuildError(f"{display_path}：与 {case_paths[folded]} 只差大小写，不能同时收录")
        case_paths[folded] = display_path
        data = path.read_bytes()
        if b"\r" in data:
            raise BuildError(f"{display_path}：文件含有 CR；所有文本文件必须使用 LF 换行")
        checked.append((path, display_path, data))
    return checked


def load_document(path, display_path):
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BuildError(f"{display_path}：YAML 解析失败：{exc}") from exc
    if not isinstance(document, dict):
        raise BuildError(f"{display_path}：内容文件必须是一个 YAML 对象")
    return document


def _check_json_value(value, display_path, where):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise BuildError(f"{display_path}：{where} 的键 {key!r} 不是字符串，不能转成 JSON")
            _check_json_value(item, display_path, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_json_value(item, display_path, f"{where}[{index}]")
    elif isinstance(value, bool) or value is None or isinstance(value, str):
        return
    elif isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise BuildError(f"{display_path}：{where} 的整数超出 ±(2^53−1)，浏览器读不准")
    elif isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise BuildError(f"{display_path}：{where} 是 NaN 或无穷大，不能转成 JSON")
    else:
        raise BuildError(f"{display_path}：{where} 的值 {value!r} 不能转成 JSON（日期之类请加引号写成字符串）")


def json_sidecar(data, display_path):
    """把一个 YAML 文件的原始字节转成同名 .json 的字节（内容规格 6.3）。

    键按字母排序、不留空白、不转义非 ASCII、UTF-8 编码，末尾一个 LF。
    YAML 里有 JSON 表示不了的值（日期、NaN、非字符串键、超出 2^53−1 的整数）时抛出 BuildError。
    """
    try:
        document = yaml.safe_load(data.decode("utf-8"))
    except Exception as exc:
        raise BuildError(f"{display_path}：YAML 解析失败：{exc}") from exc
    _check_json_value(document, display_path, "$")
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def file_entry(path, display_path):
    data = path.read_bytes()
    return {
        "path": display_path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def referenced_assets(activity):
    """产出结构化活动直接引用的 SVG 清单路径。"""
    from ci_checks import activity_figures
    for figure in activity_figures(activity):
        if figure.get("type") == "svg" and isinstance(figure.get("src"), str):
            yield figure["src"]


def build(content_root, source_commit):
    """读取内容目录并返回 release/1 清单；失败时抛出 BuildError。"""
    content_root = Path(content_root)
    if not isinstance(source_commit, str) or not COMMIT.fullmatch(source_commit):
        raise BuildError("source_commit 必须是 40 位小写十六进制提交号")
    files = scan_files(content_root)
    by_path = {display_path: (path, data) for path, display_path, data in files}

    nodes = {}
    node_root = content_root / "nodes"
    node_files = sorted(node_root.rglob("*.yaml")) if node_root.exists() else []
    for path in node_files:
        display_path = manifest_path(content_root, path)
        document = load_document(path, display_path)
        node_id = document.get("id")
        if isinstance(node_id, str):
            nodes[node_id] = (path, document)

    acts = {}
    activity_root = content_root / "activities"
    activity_dirs = sorted(path for path in activity_root.iterdir() if path.is_dir()) if activity_root.exists() else []
    for directory in activity_dirs:
        path = directory / "activity.yaml"
        if not path.exists():
            path = directory / "manifest.yaml"
        if not path.exists():
            continue
        display_path = manifest_path(content_root, path)
        document = load_document(path, display_path)
        activity_id = document.get("id")
        if isinstance(activity_id, str):
            acts[activity_id] = (path, document)

    gate_errors = check_publish_gate(nodes, acts)
    if gate_errors:
        details = []
        for path, message in gate_errors:
            display_path = manifest_path(content_root, path)
            details.append(f"{display_path}：{message}")
        raise BuildError("发布门禁未通过：\n" + "\n".join(details))

    published = {node_id: (path, doc) for node_id, (path, doc) in nodes.items() if doc.get("status") == "published"}
    included_ids = set()
    for _, node in published.values():
        for activity_id in node.get("activities", []):
            if activity_id in acts and acts[activity_id][1].get("review") == "approved":
                included_ids.add(activity_id)

    node_entries = []
    for node_id in sorted(published):
        path, document = published[node_id]
        display_path = manifest_path(content_root, path)
        _, data = by_path[display_path]
        node_entries.append({
            "id": node_id,
            "version": document["version"],
            "path": display_path,
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    activity_entries = []
    asset_paths = set()
    contracts = set()
    engine_min = 1
    for activity_id in sorted(included_ids):
        primary, document = acts[activity_id]
        if "kind" in document:
            kind = document["kind"]
            activity_files = [primary]
            engine_min = max(engine_min, document["engine"])
            for src in referenced_assets(document):
                if src not in by_path:
                    raise BuildError(f"{manifest_path(content_root, primary)}：svg 配图引用的文件不存在：{src}")
                asset_paths.add(src)
        else:
            kind = document["type"]
            activity_files = [primary, primary.parent / "index.html"]
            contracts.add(document["contract"])
        entries = []
        for path in activity_files:
            display_path = manifest_path(content_root, path)
            if display_path not in by_path:
                raise BuildError(f"{display_path}：收录活动所需的文件不存在")
            entries.append(file_entry(path, display_path))
        entries.sort(key=lambda entry: entry["path"])
        activity_entries.append({
            "id": activity_id,
            "version": document["version"],
            "kind": kind,
            "files": entries,
        })

    for entry in node_entries:
        json_sidecar(by_path[entry["path"]][1], entry["path"])
    for activity in activity_entries:
        for entry in activity["files"]:
            if entry["path"].endswith(".yaml"):
                json_sidecar(by_path[entry["path"]][1], entry["path"])

    assets = []
    for display_path in sorted(asset_paths):
        source_path, _ = by_path[display_path]
        assets.append(file_entry(source_path, display_path))

    hash_input = {
        "engine_min": engine_min,
        "contracts": sorted(contracts),
        "nodes": node_entries,
        "activities": activity_entries,
        "assets": assets,
    }
    canonical = json.dumps(hash_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    content_hash = hashlib.sha256(canonical).hexdigest()
    return {
        "schema": "release/1",
        "release_id": "rel_" + content_hash,
        "content_hash": content_hash,
        "source_commit": source_commit,
        **hash_input,
    }


def write_release(manifest, content_root, out_dir):
    """把发布清单和清单列出的原始字节写入输出目录。"""
    content_root = Path(content_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "release.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    paths = [node["path"] for node in manifest["nodes"]]
    paths.extend(file["path"] for activity in manifest["activities"] for file in activity["files"])
    paths.extend(asset["path"] for asset in manifest["assets"])
    for display_path in sorted(set(paths)):
        parts = display_path.split("/")
        if parts[0] != "content":
            raise BuildError(f"清单路径必须以 content/ 开头：{display_path}")
        source = content_root.joinpath(*parts[1:])
        destination = out_dir.joinpath(*parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        destination.write_bytes(data)
        if display_path.endswith(".yaml"):
            # 浏览器没有 YAML 解析器：旁边多写一份解析好的 JSON。它由 YAML 确定性算出，不进清单、不参与哈希。
            destination.with_name(destination.name + ".json").write_bytes(json_sidecar(data, display_path))


def main(argv=None):
    parser = argparse.ArgumentParser(description="构建好奇号不可变发布包")
    parser.add_argument("--content", required=True, help="内容目录")
    parser.add_argument("--out", required=True, help="发布包输出目录")
    parser.add_argument("--commit", help="40 位来源提交号；默认取 git HEAD")
    args = parser.parse_args(argv)
    try:
        commit = args.commit
        if commit is None:
            process = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.content, capture_output=True, text=True, encoding="utf-8")
            if process.returncode != 0:
                raise BuildError(f"无法取得 git HEAD：{process.stderr.strip()}")
            commit = process.stdout.strip()
        manifest = build(args.content, commit)
        write_release(manifest, args.content, args.out)
    except BuildError as exc:
        print(f"构建失败：{exc}", file=sys.stderr)
        return 1
    print(manifest["release_id"])
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
# END OF FILE
