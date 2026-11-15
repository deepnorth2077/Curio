#!/usr/bin/env python3
"""动手探索模块（manifest.yaml + index.html）的静态检查。由 tools/ci_checks.py 调用，也可以单独跑。

把 `.claude/skills/curio-anatomy/references/lessons.md` 里能让程序查的规则变成检查，
这样质量不靠接手的模型记得逐条对照（#140）。

规则分三档：
- 所有模块（错误）：不联网、不碰存储、不引外部资源；Host.ready() 先于第一站；代码里发的 verb 都写进了 emits；
  代码里的误区 id 都写进了 manifest 的 misconceptions。
- 新一代模块，也就是样式里定义了 --grip 的模块（错误）：强调色不上控件，圆钮色不外借（圆钮规格 G8）；
  SVG 元素上不写 font-size 属性（教训 14）；给孩子看的字符串里没有斜杠写的分数（g1.md A.4）；感叹号不超过 3 个。
- 提醒（只对这次改过的模块报）：emits 里写了却没发、宿主不认的 verb；manifest 里的误区代码里没针对；
  带 kit: 记号的段落和骨架不一样。

用法：python tools/module_lint.py <模块目录> [<模块目录> …]
"""
import re
import sys
from pathlib import Path

import yaml

# 宿主认的模块 verb（docs/specs/events.md 第 3.7 节）
MODULE_VERBS = ("predicted", "adjusted", "observed", "answered")

# 不联网、不碰存储、不依赖外部资源（docs/activity-contract.md「硬性约束」，教训 10）
FORBIDDEN_APIS = [
    (r"\bfetch\s*\(", "fetch("), (r"\bXMLHttpRequest\b", "XMLHttpRequest"), (r"\bWebSocket\b", "WebSocket"),
    (r"\bEventSource\b", "EventSource"), (r"\bsendBeacon\b", "sendBeacon"), (r"\bimportScripts\b", "importScripts"),
    (r"\blocalStorage\b", "localStorage"), (r"\bsessionStorage\b", "sessionStorage"), (r"\bindexedDB\b", "indexedDB"),
    (r"\bdocument\.cookie\b", "document.cookie"), (r"\bcaches\.open\b", "caches.open"), (r"\bimport\s*\(", "import("),
    (r"<script[^>]*\bsrc\s*=", "<script src>"), (r"<link\b", "<link>"), (r"@import\b", "@import"),
    (r"url\(\s*['\"]?(?:https?:)?//", "url(外部地址)"), (r"\b(?:src|href)\s*=\s*['\"](?:https?:)?//", "外部 src/href"),
]

# 能用手动的东西：这些样式里不能用强调色（圆钮规格 G2）
CONTROL_SELECTOR = re.compile(r"\.btn\.hold|focus-visible|\.g(?:fill|soft|arrow|ring|ridge|kbd)\b|#cue\b")
# 圆钮色只能出现在这些样式里
GRIP_SELECTOR = re.compile(r"\.btn\.hold|focus-visible|\.g(?:fill|soft|arrow|ring|ridge|kbd)\b|#cue\b")

ENTRY_CALL = re.compile(r"^(?:enter\w*|start\w*|init\w*|boot\w*)\s*\(", re.M)
HOST_READY = re.compile(r"^Host\.ready\s*\(\s*\)", re.M)
STRING_LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`', re.S)
SLASH_FRACTION = re.compile(r"(?<![\w$}.\-/])\d{1,4}/\d{1,4}(?![\w/.])")
MIS_IN_CODE = re.compile(r"\b(?:mis|misconception)\s*:\s*[\"']([a-z0-9-]+)[\"']")
KIT_MARK = re.compile(r"kit:([a-z0-9-]+)")
SECTION_BREAK = re.compile(r"/\* =+|</style>|</script>")


def _strip_comments(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(^|[\s;{}()])//[^\n]*", r"\1", text)


def _blocks(text, tag):
    return re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", text, flags=re.S | re.I)


def _css_rules(css):
    """(选择器, 声明) 的列表；@media 里面的规则也拆出来。"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def _kit_segments(text):
    """kit: 记号到下一个记号、节标题或 </style>、</script> 为止的那一段，空白归一。"""
    out = {}
    marks = list(KIT_MARK.finditer(text))
    for i, m in enumerate(marks):
        end = len(text)
        nxt = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        brk = SECTION_BREAK.search(text, m.end())
        end = min(nxt, brk.start() if brk else len(text))
        # 记号所在那一行之后才算内容（记号行本身常带日期和说明）
        start = text.find("\n", m.end())
        body = text[start:end] if 0 <= start < end else ""
        out.setdefault(m.group(1), re.sub(r"\s+", " ", body).strip())
    return out


def lint(html, manifest=None, node_misconceptions=None, starter=None):
    """检查一个模块。返回 (errors, warnings)，都是字符串列表。

    html：index.html 的文字；manifest：manifest.yaml 解析后的 dict；
    node_misconceptions：目标知识点的误区 id 集合（不给就不查）；starter：骨架的文字（不给就不比 kit 段落）。
    """
    errors, warnings = [], []
    manifest = manifest or {}
    code = _strip_comments(html)

    # ---------- 所有模块 ----------
    for pattern, name in FORBIDDEN_APIS:
        if re.search(pattern, code, flags=re.I):
            errors.append(f"模块不能联网、读写存储或引用外部资源：发现 {name}（活动契约「硬性约束」，教训 10）")

    scripts = "\n".join(_blocks(html, "script"))
    has_code = bool(_strip_comments(scripts).strip())   # 脚本里只有注释的不算
    if has_code:
        ready = HOST_READY.search(scripts)
        entry = ENTRY_CALL.search(scripts)
        if not ready:
            errors.append("脚本最外层没有调用 Host.ready()（教训 31）")
        elif entry and entry.start() < ready.start():
            errors.append(f"Host.ready() 必须先于第一站：{entry.group(0).rstrip('(').strip()}() 写在了它前面（教训 31）")

    literals = [s[1:-1] for s in STRING_LITERAL.findall(_strip_comments(scripts))]
    sent = {v for v in MODULE_VERBS if v in literals}
    emits = set(manifest.get("emits") or [])
    for verb in sorted(sent - emits):
        errors.append(f"代码里发了 {verb}，manifest 的 emits 里没写：平台会记一条契约警告")
    for verb in sorted(emits - sent):
        warnings.append(f"emits 里写了 {verb}，代码里没有发" if verb in MODULE_VERBS else f"emits 里的 {verb} 宿主不认（只认 {'、'.join(MODULE_VERBS)}）")

    in_code = set(MIS_IN_CODE.findall(scripts))
    declared = set(manifest.get("misconceptions") or [])
    for mid in sorted(in_code - declared):
        errors.append(f"代码里的误区 {mid} 没有写进 manifest 的 misconceptions")
    for mid in sorted(declared - in_code):
        if has_code:
            warnings.append(f"manifest 里的误区 {mid} 代码里没有针对（猜测选项里没有它）")
    if node_misconceptions is not None:
        for mid in sorted(in_code - set(node_misconceptions)):
            errors.append(f"代码里的误区 {mid} 不在目标知识点的误区列表里")

    # ---------- 新一代模块（定义了 --grip） ----------
    styles = "\n".join(_blocks(html, "style"))
    if re.search(r"--grip\s*:", styles):
        for sel, body in _css_rules(styles):
            if ":root" in sel or sel.startswith("@"):
                continue
            if "var(--accent" in body and CONTROL_SELECTOR.search(sel):
                errors.append(f"强调色不能用在控件上：样式「{sel}」用了 --accent（圆钮规格 G2）")
            if "var(--grip" in body and not GRIP_SELECTOR.search(sel):
                errors.append(f"圆钮色只给圆钮、托、按住按钮、焦点框、提醒环用：样式「{sel}」用了 --grip（圆钮规格 G2）")
        outside = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
        if "var(--grip" in _strip_comments(outside):
            errors.append("圆钮色只能写在样式表里，画面里用圆钮的类（.gfill 等），不要直接写 var(--grip)（圆钮规格 G2）")
        if re.search(r"font-size\s*=", code):
            errors.append("SVG 元素上不要写 font-size 属性：会被样式表盖掉，字号写在 CSS 类上（教训 14）")
        for lit in literals:
            m = SLASH_FRACTION.search(lit)
            if m:
                errors.append(f"给孩子看的分数一律上下结构，不用斜杠：字符串里有「{m.group(0)}」（g1.md A.4 第 2 条）")
                break
        bangs = sum(lit.count("！") for lit in literals)
        if bangs > 3:
            errors.append(f"一个模块里感叹号不超过 3 个，现在有 {bangs} 个（A.2 领航员怎么说话）")

    # ---------- 提醒：kit 段落和骨架不一样 ----------
    if starter:
        mine, base = _kit_segments(html), _kit_segments(starter)
        for name in sorted(set(mine) & set(base)):
            if mine[name] != base[name]:
                warnings.append(f"kit:{name} 这一段和骨架 references/starter.html 不一样：有意改的，先改骨架再同步")

    return errors, warnings


def main(argv):
    repo = Path(__file__).resolve().parent.parent
    starter_path = repo / ".claude/skills/curio-anatomy/references/starter.html"
    starter = starter_path.read_text(encoding="utf-8") if starter_path.exists() else None
    bad = 0
    for arg in argv:
        d = Path(arg)
        manifest = yaml.safe_load((d / "manifest.yaml").read_text(encoding="utf-8")) if (d / "manifest.yaml").exists() else {}
        errs, warns = lint((d / "index.html").read_text(encoding="utf-8"), manifest, None, starter)
        for e in errs:
            print(f"[错误] {d}：{e}")
        for w in warns:
            print(f"[提醒] {d}：{w}")
        bad += len(errs)
    print("通过" if not bad else f"未通过：{bad} 个错误")
    return 1 if bad else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
# END OF FILE
