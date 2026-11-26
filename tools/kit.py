#!/usr/bin/env python3
"""共用色位（kit/tokens.css）与零件库（kit/<N>/）的同步和逐字节检查（docs/specs/kit.md）。

用法：
  python tools/kit.py sync [文件 …]
  python tools/kit.py check
"""
import re
import subprocess
import sys
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
STARTER_REL = ".claude/skills/curio-anatomy/references/starter.html"
TOKENS_BEGIN = "/* curio-tokens begin */"
TOKENS_END = "/* curio-tokens end */"
KIT_MARKER = re.compile(r"/\*\s*curio-kit:(\d+)\s+(begin|end)\s*\*/")
README_CONTRACT = re.compile(r"^\s*(?:-\s*)?contract:\s*(\S+)\s*$", re.M)
STYLE_BLOCK = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)
SCRIPT_BLOCK = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)


def _norm_lf(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _extract_vars(css_block):
    out = {}
    for m in re.finditer(r"--([a-z0-9-]+)\s*:\s*([^;}\n]+)", css_block):
        out[m.group(1)] = m.group(2).strip()
    return out


def parse_tokens(tokens_text):
    """解析 kit/tokens.css，返回 (light_dict, dark_dict, errors)。"""
    errors = []
    light_m = re.search(r"(?:^|\n):root\s*\{([^{}]*)\}", tokens_text)
    dark_m = re.search(r':root\[data-theme="dark"\]\s*\{([^{}]*)\}', tokens_text)
    if not light_m or not dark_m:
        return {}, {}, ["kit/tokens.css 必须同时包含 :root{…} 与 :root[data-theme=\"dark\"]{…}"]
    light = _extract_vars(light_m.group(1))
    dark = _extract_vars(dark_m.group(1))
    for mode, data in (("浅色 :root", light), ("深色 data-theme=\"dark\"", dark)):
        missing = [k for k in PALETTE_KEYS if k not in data]
        extra = [k for k in data if k not in PALETTE_KEYS]
        if missing:
            errors.append(f"kit/tokens.css 的{mode}缺少平台色位：{'、'.join(missing)}")
        if extra:
            errors.append(f"kit/tokens.css 的{mode}多了非平台色位：{'、'.join(extra)}")
        for k, v in data.items():
            if k in PALETTE_KEYS and not HEX_COLOR.fullmatch(v):
                errors.append(f"kit/tokens.css 的{mode}色位 --{k} 必须是十六进制颜色，现在是 {v!r}")
    return light, dark, errors


def kit_readme_contract(readme_path):
    if not readme_path.is_file():
        return None
    m = README_CONTRACT.search(readme_path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def _replace_segment(text, begin_mark, end_mark, payload):
    """把 text 中唯一一对 begin_mark … end_mark 中间换成 payload。返回 (new_text, error_or_none)。"""
    b_count = text.count(begin_mark)
    e_count = text.count(end_mark)
    if b_count != 1 or e_count != 1:
        return text, f"标记必须成对且恰好各出现 1 次：{begin_mark}（{b_count} 次）/ {end_mark}（{e_count} 次）"
    i = text.index(begin_mark)
    j = text.index(end_mark)
    if j < i:
        return text, f"结束标记写在了开始标记前面：{begin_mark}"
    body = payload if payload.endswith("\n") else payload + "\n"
    return text[:i + len(begin_mark)] + "\n" + body + text[j:], None


def _sync_tokens_html(html, tokens_css):
    return _replace_segment(html, TOKENS_BEGIN, TOKENS_END, tokens_css)


def _sync_kit_html(html, version, kit_css, kit_js):
    begin = f"/* curio-kit:{version} begin */"
    end = f"/* curio-kit:{version} end */"
    other = [m.group(1) for m in KIT_MARKER.finditer(html) if int(m.group(1)) != version]
    if other:
        return html, f"标记里的 kit 版本（{other[0]}）和声明的 kit: {version} 不一致"
    marks = [(m.group(2), m.start()) for m in KIT_MARKER.finditer(html)]
    if [k for k, _ in marks] != ["begin", "end", "begin", "end"]:
        return html, f"样式与脚本必须各有一对完整的 {begin} … {end}"
    sm = STYLE_BLOCK.search(html)
    jm = SCRIPT_BLOCK.search(html)
    if not sm or not jm:
        return html, "缺少 <style> 或 <script> 标签"
    new_style, err1 = _replace_segment(sm.group(2), begin, end, kit_css)
    if err1:
        return html, f"<style> 内{err1}"
    new_script, err2 = _replace_segment(jm.group(2), begin, end, kit_js)
    if err2:
        return html, f"<script> 内{err2}"
    out = html[:sm.start(2)] + new_style + html[sm.end(2):jm.start(2)] + new_script + html[jm.end(2):]
    return out, None


def _starter_version(html):
    m = KIT_MARKER.search(html)
    return int(m.group(1)) if m else None


def allowlist(repo):
    """返回白名单目标：[("tokens", rel_path, None), ("kit", rel_path, version), ...]。"""
    repo = Path(repo)
    items = []
    for rel in TOKEN_TARGETS:
        if (repo / rel).is_file():
            items.append(("tokens", rel, None))
    starter = repo / STARTER_REL
    if starter.is_file():
        ver = _starter_version(starter.read_text(encoding="utf-8"))
        if ver is not None:
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


def sync_repo(repo, targets=None):
    """把 kit/ 原件同步进白名单文件（或指定的子集）。返回 (changed_rels, errors)。"""
    repo = Path(repo)
    errors = []
    changed = []
    tokens_path = repo / "kit/tokens.css"
    if not tokens_path.is_file():
        return [], [("kit/tokens.css", "缺少 kit/tokens.css")]
    tokens_css = _norm_lf(tokens_path.read_text(encoding="utf-8"))
    _, _, tok_errs = parse_tokens(tokens_css)
    for e in tok_errs:
        errors.append(("kit/tokens.css", e))
    if errors:
        return [], errors

    wanted = None
    if targets:
        wanted = {str(Path(t).resolve().relative_to(repo.resolve())).replace("\\", "/") for t in targets}

    for kind, rel, ver in allowlist(repo):
        if wanted is not None and rel not in wanted:
            continue
        path = repo / rel
        old = _norm_lf(path.read_text(encoding="utf-8"))
        if kind == "tokens":
            new, err = _sync_tokens_html(old, tokens_css)
        else:
            kdir = repo / "kit" / str(ver)
            if not (kdir / "kit.css").is_file() or not (kdir / "kit.js").is_file():
                errors.append((rel, f"找不到 kit/{ver}/kit.css 或 kit/{ver}/kit.js"))
                continue
            kit_css = _norm_lf((kdir / "kit.css").read_text(encoding="utf-8"))
            kit_js = _norm_lf((kdir / "kit.js").read_text(encoding="utf-8"))
            new, err = _sync_kit_html(old, ver, kit_css, kit_js)
        if err:
            errors.append((rel, err))
            continue
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(rel)
    return changed, errors


def check_immutability(repo, base="origin/main"):
    """一旦 base 上已有模块使用 kit/<N>/，kit/<N>/ 下任何文件不得增删改。返回 [(file, msg), ...]。"""
    repo = Path(repo)
    errors = []
    p = subprocess.run(["git", "ls-tree", "-r", "--name-only", base, "content/activities"],
                       cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return errors
    used_versions = set()
    for line in p.stdout.splitlines():
        if not line.endswith("/manifest.yaml"):
            continue
        show = subprocess.run(["git", "show", f"{base}:{line}"], cwd=repo, capture_output=True, text=True, encoding="utf-8")
        if show.returncode != 0:
            continue
        try:
            doc = yaml.safe_load(show.stdout)
        except Exception:
            continue
        if isinstance(doc, dict) and isinstance(doc.get("kit"), int) and not isinstance(doc.get("kit"), bool):
            used_versions.add(doc["kit"])

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

    kit_root = repo / "kit"
    for kdir in sorted(p for p in kit_root.iterdir() if p.is_dir()) if kit_root.is_dir() else []:
        if not kdir.name.isdigit():
            continue
        ver = int(kdir.name)
        for req in ("kit.css", "kit.js", "README.md"):
            if not (kdir / req).is_file():
                errors.append((f"kit/{ver}/{req}", f"kit/{ver}/ 缺少 {req}"))
        contract = kit_readme_contract(kdir / "README.md")
        if not contract:
            errors.append((f"kit/{ver}/README.md", f"kit/{ver}/README.md 必须写明 contract: activity/1.x"))
        if ver == 1 and (kdir / "kit.css").is_file() and light and dark:
            kcss = (kdir / "kit.css").read_text(encoding="utf-8")
            km_l = re.search(r"(?:^|\n):root\s*\{([^{}]*)\}", kcss)
            km_d = re.search(r":root\.kit-dark\s*\{([^{}]*)\}", kcss)
            if not km_l or not km_d:
                errors.append((f"kit/{ver}/kit.css", "kit.css 必须包含 :root 与 :root.kit-dark 后备色位"))
            else:
                kl, kd = _extract_vars(km_l.group(1)), _extract_vars(km_d.group(1))
                for k in PALETTE_KEYS:
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
    for kind, rel, ver in allowlist(repo):
        path = repo / rel
        cur = _norm_lf(path.read_text(encoding="utf-8"))
        if kind == "tokens":
            expected, err = _sync_tokens_html(cur, tokens_css)
        else:
            kdir = repo / "kit" / str(ver)
            if not (kdir / "kit.css").is_file() or not (kdir / "kit.js").is_file():
                errors.append((rel, f"找不到 kit/{ver}/kit.css 或 kit/{ver}/kit.js"))
                continue
            kit_css = _norm_lf((kdir / "kit.css").read_text(encoding="utf-8"))
            kit_js = _norm_lf((kdir / "kit.js").read_text(encoding="utf-8"))
            expected, err = _sync_kit_html(cur, ver, kit_css, kit_js)
        if err:
            errors.append((rel, err))
        elif expected != cur:
            errors.append((rel, "标记段内容与 kit/ 原件不一致，请运行 python tools/kit.py sync"))

    if base:
        errors.extend(check_immutability(repo, base))
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
