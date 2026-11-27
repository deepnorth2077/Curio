#!/usr/bin/env python3
"""共用色位（kit/tokens.css）与零件库（kit/<N>/）的同步和逐字节检查（docs/specs/kit.md）。

用法：
  python tools/kit.py sync [文件 …]
  python tools/kit.py check
"""
import io
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import yaml

PALETTE_KEYS = (
    "bg", "pane", "hover", "rule", "ink", "text", "muted",
    "accent", "accent-soft", "grip", "grip-soft",
    "sage", "sage-bg", "sky", "apricot", "paper",
    "good", "good-soft", "bad", "bad-soft",
)
HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
TOKEN_TARGETS = ("app/index.html", "preview/template.html")
SFX_TARGET = "app/sfx.js"
SFX_LAB = "app/sfx-lab.html"
SFX_BEGIN = "/* curio-sfx begin */"
SFX_END = "/* curio-sfx end */"
STARTER_REL = ".claude/skills/curio-anatomy/references/starter.html"
TOKENS_BEGIN = "/* curio-tokens begin */"
TOKENS_END = "/* curio-tokens end */"
KIT_MARKER = re.compile(r"/\*\s*curio-kit:(\d+)\s+(begin|end)\s*\*/")
DARK_TOKEN_RULE = re.compile(r':root\[data-theme="dark"\]\s*\{([^{}]*)\}')
README_CONTRACT = re.compile(r"^\s*(?:-\s*)?contract:\s*(\S+)\s*$", re.M)


def _norm_lf(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _css_without_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _extract_vars(css_block):
    out = {}
    for m in re.finditer(r"--([a-z0-9-]+)\s*:\s*([^;}\n]+)", css_block):
        out[m.group(1)] = m.group(2).strip()
    return out


def parse_tokens(tokens_text):
    """解析 kit/tokens.css，返回 (light_dict, dark_dict, errors)。"""
    errors = []
    tokens_text = _css_without_comments(tokens_text)
    light_m = re.search(r"(?:^|\n):root\s*\{([^{}]*)\}", tokens_text)
    dark_m = DARK_TOKEN_RULE.search(tokens_text)
    if not light_m or not dark_m:
        return {}, {}, ["kit/tokens.css 必须同时包含 :root{…} 与 :root[data-theme=\"dark\"]{…}"]
    if re.search(r"@media[^{]*prefers-color-scheme", tokens_text, re.I):
        errors.append("kit/tokens.css 的系统深色规则由 sync 从显式深色规则生成，请删除重复的 @media")
    light = _extract_vars(light_m.group(1))
    dark = _extract_vars(dark_m.group(1))
    required = set(PALETTE_KEYS) | light.keys() | dark.keys()
    for mode, data in (("浅色 :root", light), ('深色 data-theme="dark"', dark)):
        missing = sorted(required - data.keys())
        if missing:
            errors.append(f"kit/tokens.css 的{mode}缺少平台色位：{'、'.join(missing)}")
        for k, v in data.items():
            if k == "curio-palette-keys":
                errors.append("kit/tokens.css 不能使用保留的 --curio-palette-keys")
            if not HEX_COLOR.fullmatch(v):
                errors.append(f"kit/tokens.css 的{mode}色位 --{k} 必须是十六进制颜色，现在是 {v!r}")
    return light, dark, errors


def kit_readme_contract(readme_path):
    if not readme_path.is_file():
        return None
    m = README_CONTRACT.search(readme_path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def _segment_bounds(text, begin_mark, end_mark):
    b_count, e_count = text.count(begin_mark), text.count(end_mark)
    if b_count != 1 or e_count != 1:
        return None, f"标记必须成对且恰好各出现 1 次：{begin_mark}（{b_count} 次）/ {end_mark}（{e_count} 次）"
    start = text.index(begin_mark) + len(begin_mark)
    stop = text.index(end_mark)
    if stop < start:
        return None, f"结束标记写在了开始标记前面：{begin_mark}"
    return slice(start, stop), None


def _replace_segment(text, begin_mark, end_mark, body):
    bounds, err = _segment_bounds(text, begin_mark, end_mark)
    if err:
        return text, err
    return text[:bounds.start] + body + text[bounds.stop:], None


def _inline_file(contents):
    return "\n" + contents + ("" if contents.endswith("\n") else "\n")


# HTML 定义的 classic script 的 JavaScript MIME 类型（含传统拼法）。
_JS_MIME = {
    "application/ecmascript", "application/javascript", "application/x-ecmascript", "application/x-javascript",
    "text/ecmascript", "text/javascript", "text/jscript", "text/livescript", "text/x-ecmascript", "text/x-javascript",
    *(f"text/javascript1.{minor}" for minor in range(6)),
}


class _KitBlocks(HTMLParser):
    """按源码位置记录普通 HTML 中实际生效的行内样式、classic 和 module 脚本。"""

    # 这些元素的文字即使长得像标签，也不产生 HTML script/style 元素。
    CDATA_CONTENT_ELEMENTS = ("script", "style", "title", "textarea", "iframe", "noscript", "noembed", "noframes", "xmp")

    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.blocks = {"style": [], "script": [], "module": []}
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", html)]
        self.excluded = []
        self.kind = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag in ("template", "svg", "math"):
            self.excluded.append(tag)
        if self.excluded or tag not in ("style", "script"):
            return
        # HTML 第一个同名属性生效。
        attrs = dict(reversed(attrs))
        mime = (attrs.get("type") or "").strip().lower()
        if tag == "style":
            media = (attrs.get("media") or "").strip().lower()
            if mime in ("", "text/css") and media in ("", "all") and "disabled" not in attrs:
                self.kind = "style"
        elif "src" not in attrs and "nomodule" not in attrs:
            if "type" not in attrs and attrs.get("language"):
                mime = "text/" + attrs["language"].lower()
            if not mime or mime in _JS_MIME:
                self.kind = "script"
            elif mime == "module":
                self.kind = "module"

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.kind = None
        if self.excluded and self.excluded[-1] == tag:
            self.excluded.pop()

    def handle_data(self, data):
        if self.kind:
            line, column = self.getpos()
            start = self.line_starts[line - 1] + column
            self.blocks[self.kind].append((start, start + len(data)))


def executable_scripts(html, *, classic_only=False, modules_only=False):
    blocks = _KitBlocks(html).blocks
    if classic_only:
        spans = blocks["script"]
    elif modules_only:
        spans = blocks["module"]
    else:
        spans = sorted(blocks["script"] + blocks["module"])
    return [html[start:stop] for start, stop in spans]


def _sync_kit_html(html, version, kit_css, kit_js):
    begin = f"/* curio-kit:{version} begin */"
    end = f"/* curio-kit:{version} end */"
    markers = list(KIT_MARKER.finditer(html))
    if any(int(m.group(1)) != version for m in markers):
        return html, f"标记里的 kit 版本和声明的 kit: {version} 不一致"
    if len(markers) != 4:
        return html, f"样式与脚本必须各有一对完整的 {begin} … {end}"

    blocks = _KitBlocks(html).blocks
    changes = []
    for tag, payload in (("style", kit_css), ("script", kit_js)):
        marked = [(start, stop) for start, stop in blocks[tag] if KIT_MARKER.search(html, start, stop)]
        if len(marked) != 1:
            return html, f"必须恰好有一个生效的行内 <{tag}> 包含 {begin} … {end}"
        start, stop = marked[0]
        body, err = _replace_segment(html[start:stop], begin, end, _inline_file(payload))
        if err:
            return html, f"<{tag}> 内{err}"
        changes.append((start, stop, body))
    for start, stop, body in sorted(changes, reverse=True):
        html = html[:start] + body + html[stop:]
    return html, None


def _kit_versions(repo):
    return sorted(int(d.name) for d in (repo / "kit").iterdir()
                  if d.is_dir() and re.fullmatch(r"[1-9][0-9]*", d.name))


def _starter_version(html):
    m = KIT_MARKER.search(html)
    return int(m.group(1)) if m else None


def allowlist(repo):
    """返回白名单目标：[("tokens", rel_path, None), ("kit", rel_path, version), ...]。"""
    repo = Path(repo)
    items = [("tokens", rel, None) for rel in TOKEN_TARGETS]
    items.append(("sfx", SFX_LAB, 1))
    starter = repo / STARTER_REL
    versions = _kit_versions(repo)
    items.append(("sfx", SFX_TARGET, versions[-1] if versions else None))
    ver = _starter_version(starter.read_text(encoding="utf-8")) if starter.is_file() else None
    items.append(("kit", STARTER_REL, ver))
    act_root = repo / "content/activities"
    if act_root.is_dir():
        for d in sorted(p for p in act_root.iterdir() if p.is_dir()):
            mf = d / "manifest.yaml"
            idx = d / "index.html"
            if not mf.is_file() or not idx.is_file():
                continue
            try:
                doc = yaml.safe_load(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(doc, dict) and isinstance(doc.get("kit"), int) and not isinstance(doc.get("kit"), bool):
                items.append(("kit", f"content/activities/{d.name}/index.html", doc["kit"]))
    return items


def _expected_target(repo, kind, rel, version, tokens_payload):
    path = repo / rel
    if not path.is_file():
        return None, None, f"缺少同步目标 {rel}"
    old = path.read_text(encoding="utf-8")
    if kind == "tokens":
        new, err = _replace_segment(old, TOKENS_BEGIN, TOKENS_END, _inline_file(tokens_payload))
    elif version is None:
        return old, None, "找不到同步来源的 kit 版本或 curio-kit 标记"
    else:
        kit_dir = repo / "kit" / str(version)
        js_path = kit_dir / "kit.js"
        if not js_path.is_file():
            return old, None, f"找不到 kit/{version}/kit.js"
        js = js_path.read_text(encoding="utf-8")
        if kind == "sfx":
            bounds, err = _segment_bounds(js, SFX_BEGIN, SFX_END)
            if err:
                return old, None, f"kit/{version}/kit.js：{err}"
            new, err = _replace_segment(old, SFX_BEGIN, SFX_END, js[bounds])
        else:
            css_path = kit_dir / "kit.css"
            if not css_path.is_file():
                return old, None, f"找不到 kit/{version}/kit.css"
            new, err = _sync_kit_html(old, version, css_path.read_text(encoding="utf-8"), js)
    return old, new, err


def _tokens_payload(css, light):
    # 系统深色与手选深色共用整组声明。外壳由键名表发现扩展色，排除私有变量。
    dark = DARK_TOKEN_RULE.search(_css_without_comments(css))
    system_dark = ('@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){'
                   + dark.group(1) + "}}\n") if dark else ""
    key_list = ":root{--curio-palette-keys:" + " ".join(light) + "}\n"
    return css.rstrip("\n") + "\n" + system_dark + key_list


def sync_repo(repo, targets=None):
    """把 kit/ 原件同步进白名单文件（或指定的子集）。返回 (changed_rels, errors)。"""
    repo = Path(repo)
    errors = []
    changed = []
    tokens_path = repo / "kit/tokens.css"
    if not tokens_path.is_file():
        return [], [("kit/tokens.css", "缺少 kit/tokens.css")]
    tokens_css = _norm_lf(tokens_path.read_text(encoding="utf-8"))
    light, _, tok_errs = parse_tokens(tokens_css)
    for e in tok_errs:
        errors.append(("kit/tokens.css", e))
    if errors:
        return [], errors

    wanted = None
    if targets:
        wanted = {str(Path(t).resolve().relative_to(repo.resolve())).replace("\\", "/") for t in targets}

    tokens_payload = _tokens_payload(tokens_css, light)
    for kind, rel, ver in allowlist(repo):
        if wanted is not None and rel not in wanted:
            continue
        path = repo / rel
        old, new, err = _expected_target(repo, kind, rel, ver, tokens_payload)
        if err:
            errors.append((rel, err))
            continue
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(rel)
    return changed, errors


def _published_versions(repo, base):
    """只追溯目标分支历史中实际合入的 manifest，包括已删除或迁走的最后一个使用者。"""
    changes = subprocess.run(
        ["git", "log", "--first-parent", "--no-renames", "--format=", "--raw", "--no-abbrev",
         "--diff-filter=AM", base, "--", ":(glob)content/activities/*/manifest.yaml"],
        cwd=repo, capture_output=True, check=True, text=True,
    )
    blobs = {line.split()[3] for line in changes.stdout.splitlines() if line.startswith(":")}
    if not blobs:
        return set()
    # 一次取回每个不同的清单，避免按活动乘以提交数反复启动 git。
    result = subprocess.run(["git", "cat-file", "--batch"], cwd=repo, check=True,
                            input=("\n".join(blobs) + "\n").encode(), capture_output=True)
    stream = io.BytesIO(result.stdout)
    versions = set()
    for header in iter(stream.readline, b""):
        size = int(header.split()[2])
        raw = stream.read(size)
        stream.read(1)  # cat-file 在每个对象之后额外写一个换行
        doc = yaml.safe_load(raw)
        if isinstance(doc, dict) and type(doc.get("kit")) is int:
            versions.add(doc["kit"])
    return versions


def _base_manifests(repo, base):
    """返回基准分支上已有的互动模块 manifest 相对路径集合。"""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", base, "content/activities"],
        cwd=repo, capture_output=True, check=True, text=True, encoding="utf-8",
    )
    return {
        line for line in result.stdout.splitlines()
        if re.fullmatch(r"content/activities/[^/]+/manifest\.yaml", line)
    }


def check_immutability(repo, base="origin/main", used_versions=None):
    """与基准分支逐字节比较所有已经发布过的版本。"""
    repo = Path(repo)
    if used_versions is None:
        used_versions = _published_versions(repo, base)
    errors = []
    for ver in sorted(used_versions):
        prefix = f"kit/{ver}"
        tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", base, prefix],
                              cwd=repo, capture_output=True, text=True, encoding="utf-8")
        base_files = sorted(f for f in tree.stdout.splitlines() if f.startswith(prefix + "/"))
        kdir = repo / "kit" / str(ver)
        cur_files = sorted(f"kit/{ver}/{f.relative_to(kdir).as_posix()}" for f in kdir.rglob("*") if f.is_file()) if kdir.is_dir() else []
        if base_files != cur_files:
            errors.append((prefix, f"kit/{ver}/ 已被主线上的模块使用，冻结后不能增删文件（请新建 kit/{ver + 1}/）"))
            continue
        for rel in base_files:
            old_b = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=repo, capture_output=True).stdout
            cur_b = (repo / rel).read_bytes()
            if old_b != cur_b:
                errors.append((rel, f"kit/{ver}/ 已被主线上的模块使用，冻结后不能修改（请新建 kit/{ver + 1}/）"))
    return errors


def check_repo(repo, base=None):
    """逐字节核对 kit/、外壳色位段、骨架与所有声明了 kit 的模块。返回 [(rel_path, msg), ...]。"""
    repo = Path(repo)
    errors = []
    tokens_path = repo / "kit/tokens.css"
    if not tokens_path.is_file():
        return [("kit/tokens.css", "缺少 kit/tokens.css")]
    tokens_css = _norm_lf(tokens_path.read_text(encoding="utf-8"))
    light, dark, tok_errs = parse_tokens(tokens_css)
    for e in tok_errs:
        errors.append(("kit/tokens.css", e))

    if base is None:
        probe = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "origin/main"],
                               cwd=repo, capture_output=True)
        if probe.returncode == 0:
            base = "origin/main"
    try:
        published = _published_versions(repo, base) if base else set()
        base_manifests = _base_manifests(repo, base) if base else None
    except (subprocess.CalledProcessError, yaml.YAMLError) as exc:
        return errors + [("kit", f"无法核对 {base} 上已发布的 kit 版本：{exc}")]
    versions = _kit_versions(repo)
    latest_ver = versions[-1] if versions else None
    latest_contract = (
        kit_readme_contract(repo / "kit" / str(latest_ver) / "README.md")
        if latest_ver is not None else None
    )
    for ver in versions:
        kdir = repo / "kit" / str(ver)
        for req in ("kit.css", "kit.js", "README.md"):
            if not (kdir / req).is_file():
                errors.append((f"kit/{ver}/{req}", f"kit/{ver}/ 缺少 {req}"))
        contract = kit_readme_contract(kdir / "README.md")
        if not contract:
            errors.append((f"kit/{ver}/README.md", f"kit/{ver}/README.md 必须写明 contract: activity/1.x"))
        if ver not in published and (kdir / "kit.css").is_file() and light and dark:
            kcss = _css_without_comments((kdir / "kit.css").read_text(encoding="utf-8"))
            km_l = re.search(r"(?:^|\n):root\s*\{([^{}]*)\}", kcss)
            km_d = re.search(r":root\.kit-dark\s*\{([^{}]*)\}", kcss)
            if not km_l or not km_d:
                errors.append((f"kit/{ver}/kit.css", "kit.css 必须包含 :root 与 :root.kit-dark 后备色位"))
            else:
                kl, kd = _extract_vars(km_l.group(1)), _extract_vars(km_d.group(1))
                for k in light:
                    if kl.get(k) != light.get(k):
                        errors.append((f"kit/{ver}/kit.css", f"浅色后备色位 --{k}（{kl.get(k)!r}）与 kit/tokens.css（{light.get(k)!r}）不一致"))
                    if kd.get(k) != dark.get(k):
                        errors.append((f"kit/{ver}/kit.css", f"深色后备色位 --{k}（{kd.get(k)!r}）与 kit/tokens.css（{dark.get(k)!r}）不一致"))

    # 检查未声明 kit 的模块是否误写了 curio-kit 标记，以及 1.2 模块的契约一致性
    act_root = repo / "content/activities"
    if act_root.is_dir():
        for d in sorted(p for p in act_root.iterdir() if p.is_dir()):
            mf = d / "manifest.yaml"
            idx = d / "index.html"
            if not mf.is_file() or not idx.is_file():
                continue
            rel_idx = f"content/activities/{d.name}/index.html"
            rel_mf = f"content/activities/{d.name}/manifest.yaml"
            try:
                doc = yaml.safe_load(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(doc, dict):
                continue
            kit_ver = doc.get("kit")
            contract = doc.get("contract")
            html = idx.read_text(encoding="utf-8")
            is_new = base_manifests is not None and rel_mf not in base_manifests
            if is_new and latest_ver is not None and latest_contract:
                if contract != latest_contract:
                    errors.append((
                        rel_mf,
                        f"新增互动模块必须使用最新零件库（contract: {latest_contract}、kit: {latest_ver}），不能再使用 {contract!r}",
                    ))
                    continue
                if isinstance(kit_ver, int) and not isinstance(kit_ver, bool) and kit_ver >= 1 and kit_ver != latest_ver:
                    errors.append((
                        rel_mf,
                        f"新增互动模块必须使用最新零件库 kit: {latest_ver}（现在声明的是 kit: {kit_ver}）",
                    ))
            if contract == "activity/1.2":
                if not isinstance(kit_ver, int) or isinstance(kit_ver, bool) or kit_ver < 1:
                    errors.append((rel_mf, "contract: activity/1.2 的模块必须填写正整数 kit 版本"))
                    continue
                kdir = repo / "kit" / str(kit_ver)
                if not kdir.is_dir():
                    errors.append((rel_mf, f"声明的 kit: {kit_ver} 不存在（缺少 kit/{kit_ver}/）"))
                    continue
                rc = kit_readme_contract(kdir / "README.md")
                if rc != contract:
                    errors.append((rel_mf, f"kit/{kit_ver}/README.md 声明的契约是 {rc!r}，与 manifest 的 {contract!r} 不一致"))
            elif KIT_MARKER.search(html):
                errors.append((rel_idx, f"模块包含 curio-kit 标记，但 manifest.yaml 未声明 activity/1.2 与 kit"))

    # 逐字节检查白名单
    tokens_payload = _tokens_payload(tokens_css, light)
    for kind, rel, ver in allowlist(repo):
        cur, expected, err = _expected_target(repo, kind, rel, ver, tokens_payload)
        if err:
            errors.append((rel, err))
        elif expected != cur:
            errors.append((rel, "标记段内容与 kit/ 原件不一致，请运行 python tools/kit.py sync"))

    if base:
        errors.extend(check_immutability(repo, base, published))
    return errors


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    repo = Path(__file__).resolve().parent.parent
    cmd = argv[0] if argv else "check"
    if cmd == "sync":
        changed, errors = sync_repo(repo, argv[1:] or None)
        for f, m in errors:
            print(f"[错误] {f}：{m}")
        if errors:
            return 1
        print(f"已同步 {len(changed)} 个文件" + (f"：{'、'.join(changed)}" if changed else "（无变化）"))
        return 0
    if cmd == "check":
        errors = check_repo(repo)
        for f, m in errors:
            print(f"[错误] {f}：{m}")
        print("通过" if not errors else f"未通过：{len(errors)} 个错误")
        return 1 if errors else 0
    print("用法：python tools/kit.py [sync [文件…] | check]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
