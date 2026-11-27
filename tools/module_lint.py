#!/usr/bin/env python3
"""动手探索模块（manifest.yaml + index.html）的静态检查。由 tools/ci_checks.py 调用，也可以单独跑。

把 `.claude/skills/curio-anatomy/references/lessons.md` 里能让程序查的规则变成检查，
这样质量不靠接手的模型记得逐条对照（#140）。

规则分三档：
- 所有模块（错误）：不联网、不碰存储、不引外部资源；长按不选字、不弹菜单（#156）；Host.ready() 先于第一站；代码里发的 verb 都写进了 emits；
  代码里的误区 id 都写进了 manifest 的 misconceptions。
- 新一代模块，也就是样式里定义了 --grip 的模块（错误）：强调色不上控件，圆钮色不外借（圆钮规格 G8）；
  SVG 元素上不写 font-size 属性（教训 14）；给孩子看的字符串里没有斜杠写的分数（g1.md A.4）；感叹号不超过 3 个。
- 新一代模块必须有专属走查 tools/walks/<活动 id>.py（missing_walk，由 ci_checks 调用）。
- 提醒（只对这次改过的模块报）：emits 里写了却没发、宿主不认的 verb；manifest 里的误区代码里没针对；
  带 kit: 记号的段落和骨架不一样。

用法：python tools/module_lint.py <模块目录> [<模块目录> …]
"""
from collections import defaultdict
from html.parser import HTMLParser
import re
import sys
from pathlib import Path

import tree_sitter_javascript
import yaml
from tree_sitter import Language, Parser, Query, QueryCursor

from kit import executable_scripts

# 宿主认的模块 verb（docs/specs/events.md 第 3.7 节）
MODULE_VERBS = ("predicted", "adjusted", "observed", "answered")

# 不联网、不碰存储、不依赖外部资源（docs/activity-contract.md「硬性约束」，教训 10）
FORBIDDEN_APIS = [
    (r"\bfetch\s*\(", "fetch("), (r"\bXMLHttpRequest\b", "XMLHttpRequest"), (r"\bWebSocket\b", "WebSocket"),
    (r"\bEventSource\b", "EventSource"), (r"\bsendBeacon\b", "sendBeacon"), (r"\bimportScripts\b", "importScripts"),
    (r"\blocalStorage\b", "localStorage"), (r"\bsessionStorage\b", "sessionStorage"), (r"\bindexedDB\b", "indexedDB"),
    (r"\bdocument\.cookie\b", "document.cookie"), (r"\bcaches\.open\b", "caches.open"), (r"\bimport\s*\(", "import("),
    (r"<script[^>]*\bsrc\s*=", "<script src>"), (r"<link\b", "<link>"), (r"@import\b", "@import"),
    (r"<audio\b", "<audio>"), (r"<video\b", "<video>"), (r"\bnew\s+Audio\s*\(", "new Audio("),
    (r"url\(\s*['\"]?(?:https?:)?//", "url(外部地址)"), (r"\b(?:src|href)\s*=\s*['\"](?:https?:)?//", "外部 src/href"),
]

# 能用手动的东西：这些样式里不能用强调色（圆钮规格 G2）
CONTROL_SELECTOR = re.compile(r"\.btn\.hold|focus-visible|\.g(?:fill|soft|arrow|ring|ridge|kbd)\b|#cue\b")
# 圆钮色只能出现在这些样式里
GRIP_SELECTOR = re.compile(r"\.btn\.hold|focus-visible|\.g(?:fill|soft|arrow|ring|ridge|kbd)\b|#cue\b")

ENTRY_CALL = re.compile(r"^(?:enter\w*|start\w*|init\w*|boot\w*)\s*\(", re.M)
HOST_READY = re.compile(r"^(?:Host\.ready\s*\(\s*\)|Kit\.start\s*\()", re.M)
STRING_LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`', re.S)
SLASH_FRACTION = re.compile(r"(?<![\w$}.\-/])\d{1,4}/\d{1,4}(?![\w/.])")
MIS_IN_CODE = re.compile(r"\b(?:mis|misconception)\s*:\s*[\"']([a-z0-9-]+)[\"']")
KIT_MARK = re.compile(r"(?<!curio-)kit:([a-z0-9-]+)")
CURIO_KIT_SEG = re.compile(r"/\*\s*curio-kit:\d+\s+begin\s*\*/.*?/\*\s*curio-kit:\d+\s+end\s*\*/", re.S)
JS = Language(tree_sitter_javascript.language())
# 由解析器定位声明左侧（含解构），分别按块作用域、函数作用域和参数作用域查找绑定。
JS_BINDINGS = Query(JS, """
    (lexical_declaration (variable_declarator name: (_) @lexical))
    (variable_declaration (variable_declarator name: (_) @var))
    (for_in_statement kind: ["let" "const"] left: (_) @loop)
    (for_in_statement kind: "var" left: (_) @var)
    [(function_declaration name: (_) @declaration)
     (generator_function_declaration name: (_) @declaration)
     (class_declaration name: (_) @declaration)]
    [(function_expression name: (_) @self)
     (generator_function name: (_) @self)
     (class name: (_) @self)]
    (formal_parameters (_) @parameter)
    (arrow_function parameter: (_) @single_parameter)
    (catch_clause parameter: (_) @catch)
    (import_clause (identifier) @import)
    (namespace_import (identifier) @import)
    (import_specifier name: (identifier) @import !alias)
    (import_specifier alias: (identifier) @import)
""")
JS_LEXICAL_SCOPES = {"program", "statement_block", "switch_body", "for_statement", "for_in_statement"}
JS_VAR_SCOPES = {
    "program", "function_declaration", "generator_function_declaration", "function_expression",
    "generator_function", "arrow_function", "method_definition", "class_static_block",
}
JS_CALLS = Query(JS, "(call_expression) @call")
# 检查成员引用也能覆盖把音效作为回调传递的情况。
JS_SFX_MEMBERS = Query(JS, """
    (member_expression object: (identifier) @object property: (property_identifier) @property)
    (subscript_expression object: (identifier) @object index: [(string) (template_string)] @property)
""")
KIT_REWARD_ENTRYPOINTS = {"right": "observedOnce(n)", "lit": "Host.complete()"}
SECTION_BREAK = re.compile(r"/\* =+|</style>|</script>")

# 长按不选字、不弹菜单（#156）：孩子会碰到的页面都要有这两条，ci_checks 也拿它查三个外壳文件
NOSELECT_CSS = (
    "html{-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}\n"
    "input,textarea,select,[contenteditable]{-webkit-user-select:text;user-select:text;-webkit-touch-callout:default}\n"
)
NOSELECT_RULES = [
    ({"html"}, {"-webkit-user-select:none", "user-select:none", "-webkit-touch-callout:none"},
     "html 上的 -webkit-user-select:none、user-select:none、-webkit-touch-callout:none"),
    ({"input", "textarea", "select", "[contenteditable]"}, {"-webkit-user-select:text", "user-select:text", "-webkit-touch-callout:default"},
     "input,textarea,select,[contenteditable] 上的 -webkit-user-select:text、user-select:text、-webkit-touch-callout:default"),
]


def _strip_comments(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(^|[\s;{}()])//[^\n]*", r"\1", text)


def _blocks(text, tag):
    return re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", text, flags=re.S | re.I)


def _binding_names(pattern):
    """声明左侧的绑定名，解构的属性键、计算表达式和默认值都不是新声明。"""
    if pattern.type in ("identifier", "shorthand_property_identifier_pattern"):
        yield pattern.text.decode()
    elif pattern.type == "pair_pattern":
        yield from _binding_names(pattern.child_by_field_name("value"))
    elif pattern.type in ("assignment_pattern", "object_assignment_pattern"):
        yield from _binding_names(pattern.child_by_field_name("left"))
    elif pattern.type in ("array_pattern", "object_pattern", "rest_pattern"):
        for child in pattern.named_children:
            yield from _binding_names(child)


def _nearest_scope(node, kinds):
    while node.type not in kinds:
        node = node.parent
    return node


def _scope_bindings(root):
    scopes = defaultdict(set)
    for kind, patterns in QueryCursor(JS_BINDINGS).captures(root).items():
        for pattern in patterns:
            parent = pattern.parent
            if kind == "var":
                scope = _nearest_scope(parent, JS_VAR_SCOPES)
            elif kind in ("declaration", "lexical"):
                scope = _nearest_scope(parent.parent, JS_LEXICAL_SCOPES)
            elif kind == "parameter":
                scope = parent.parent   # formal_parameters 属于函数或方法
            elif kind == "import":
                scope = root
            else:
                scope = parent          # for-in/of、catch、单参数箭头或具名函数表达式
            scopes[scope].update(_binding_names(pattern))
    return scopes


def _shadowed(call, name, scopes):
    while call:
        if name in scopes.get(call, ()):
            return True
        call = call.parent
    return False


def _literal(node):
    if node and node.type in ("string", "template_string"):
        return node.text[1:-1].decode()
    return None


def _station_payload(node):
    if node.type != "object":
        return False
    fields = {}
    for child in node.named_children:
        if child.type == "shorthand_property_identifier":
            fields[child.text.decode()] = child
        elif child.type == "pair":
            key = child.child_by_field_name("key")
            fields[_literal(key) or key.text.decode()] = child.child_by_field_name("value")
    return "station" in fields and _literal(fields.get("item")) == "station-complete"


def _script_events(own, local, exports):
    verbs = set()
    completes_station = False
    for call in QueryCursor(JS_CALLS).captures(own).get("call", []):
        fn = call.child_by_field_name("function")
        args = [child for child in call.child_by_field_name("arguments").named_children if child.type != "comment"]
        if fn.type == "identifier" and args:
            name = fn.text.decode()
            if name not in exports or _shadowed(call, name, local):
                continue
            if name == "ask":
                verbs.add("predicted")
            elif name == "observedOnce":
                verbs.add("observed")
                completes_station = True
        if fn.type != "member_expression" or not args:
            continue
        if fn.child_by_field_name("object").text != b"Host" or fn.child_by_field_name("property").text != b"event":
            continue
        if _shadowed(call, "Host", local):
            continue
        verb = _literal(args[0])
        if verb in MODULE_VERBS:
            verbs.add(verb)
        if verb == "observed" and len(args) >= 2 and _station_payload(args[1]):
            completes_station = True
    return verbs, completes_station


class _EventHandlers(HTMLParser):
    """收集 HTML/SVG 元素上以内联事件或 javascript: URL 形式出现的脚本片段。"""

    CDATA_CONTENT_ELEMENTS = ("script", "style", "title", "textarea", "iframe", "noscript", "noembed", "noframes", "xmp")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        seen = set()
        for raw_name, raw_val in attrs:
            name = raw_name.lower()
            if name in seen:
                continue
            seen.add(name)
            if not raw_val:
                continue
            if name.startswith("on") and len(name) > 2:
                self.scripts.append(raw_val)
            elif name in ("href", "xlink:href", "action", "formaction"):
                stripped = raw_val.lstrip()
                if stripped[:11].lower() == "javascript:":
                    self.scripts.append(stripped[11:])


def _event_handler_scripts(html):
    parser = _EventHandlers()
    parser.feed(html)
    parser.close()
    return parser.scripts


def _reward_sounds_used(script, bindings):
    names = set()
    for _, match in QueryCursor(JS_SFX_MEMBERS).matches(script):
        obj, prop = match["object"][0], match["property"][0]
        name = _literal(prop) or prop.text.decode()
        if obj.text == b"Sfx" and name in KIT_REWARD_ENTRYPOINTS and not _shadowed(obj, "Sfx", bindings):
            names.add(name)
    return names


def _kit_usage(html, check_reward_sounds=False):
    """经典脚本共用全局绑定；各 module 可调用全局 kit，也可以在自己的作用域内重新用名。"""
    classic = "\n;\n".join(executable_scripts(html, classic_only=True))
    parser = Parser(JS)
    shared = parser.parse("\n".join(CURIO_KIT_SEG.findall(classic)).encode()).root_node
    exports = _scope_bindings(shared)[shared]
    own = parser.parse(CURIO_KIT_SEG.sub("\n", classic).encode()).root_node
    global_bindings = _scope_bindings(own)
    conflicts = global_bindings[own] & exports
    verbs, completes_station = _script_events(own, global_bindings, exports)
    reward_sounds = _reward_sounds_used(own, global_bindings) if check_reward_sounds else set()
    for script in executable_scripts(html, modules_only=True):
        module = parser.parse(script.encode()).root_node
        module_bindings = _scope_bindings(module)
        module_verbs, module_completes = _script_events(module, module_bindings, exports)
        if check_reward_sounds:
            reward_sounds.update(_reward_sounds_used(module, module_bindings))
        verbs.update(module_verbs)
        completes_station |= module_completes
    if check_reward_sounds:
        for code in _event_handler_scripts(html):
            handler = parser.parse(f"function _handler(event){{\n{code}\n}}".encode()).root_node
            handler_bindings = _scope_bindings(handler)
            reward_sounds.update(_reward_sounds_used(handler, handler_bindings))
    return verbs, completes_station, conflicts, reward_sounds


def kit_reports_station(html):
    return _kit_usage(html)[1]


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


def noselect_missing(html):
    """页面样式里缺的「长按不选字」规则（#156），返回缺的那几条的说明；都有就返回空列表。
    选择器要在同一条规则里（顺序不限），声明多写别的也行；@media 里面的不算。"""
    css = re.sub(r"/\*.*?\*/", "", "\n".join(_blocks(html, "style")), flags=re.S)
    css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    have = []
    for sel, body in _css_rules(css):
        sels = {s.strip() for s in sel.split(",")}
        decls = {re.sub(r"\s+", "", d).lower() for d in body.split(";") if d.strip()}
        have.append((sels, decls))
    return [desc for need_sel, need_decl, desc in NOSELECT_RULES
            if not any(need_sel <= sels and need_decl <= decls for sels, decls in have)]


def is_new_generation(html):
    """样式里定义了 --grip 的是新一代模块。"""
    return bool(re.search(r"--grip\s*:", "\n".join(_blocks(html, "style"))))


def missing_walk(html, aid, repo):
    """新一代模块没有 tools/walks/<活动 id>.py 时返回错误说明，否则返回 None。"""
    if is_new_generation(html) and not (Path(repo) / "tools/walks" / f"{aid}.py").is_file():
        return f"新一代模块要有专属走查 tools/walks/{aid}.py：验收用例写成断言，CI 的「走查」会跑它（#140）"
    return None


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

    for desc in noselect_missing(html):
        errors.append(f"样式里少了「{desc}」：iPad 上长按会选中文字、弹出拷贝菜单（#156）。照骨架 kit:base 开头的两条抄")

    uses_kit = manifest.get("contract") == "activity/1.2" or "kit" in manifest
    scripts = ("\n;\n".join(executable_scripts(html)) if uses_kit
               else "\n".join(_blocks(html, "script")))
    has_code = bool(_strip_comments(scripts).strip())   # 脚本里只有注释的不算
    if has_code:
        ready = HOST_READY.search(scripts)
        entry = ENTRY_CALL.search(scripts)
        if not ready:
            errors.append("脚本最外层没有调用 Host.ready()（教训 31）")
        elif entry and entry.start() < ready.start():
            errors.append(f"Host.ready() 必须先于第一站：{entry.group(0).rstrip('(').strip()}() 写在了它前面（教训 31）")

    literals = [s[1:-1] for s in STRING_LITERAL.findall(_strip_comments(scripts))]
    if uses_kit:
        version = manifest.get("kit")
        sent, _, conflicts, reward_sounds = _kit_usage(html, type(version) is int and version >= 2)
        for name in sorted(reward_sounds):
            errors.append(f"模块不能手写 Sfx.{name}()，请由 {KIT_REWARD_ENTRYPOINTS[name]} 统一发声")
    else:
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
    if is_new_generation(html):
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

    # ---------- activity/1.2 与共用零件库规则（docs/specs/kit.md 3.2） ----------
    if uses_kit:
        if "prefers-color-scheme" in _strip_comments(styles):
            errors.append("activity/1.2 模块的样式里不能写 prefers-color-scheme：明暗由宿主通过 .kit-dark 类同步（kit.md 3.2）")
        for name in sorted(conflicts):
            errors.append(f"不能在 curio-kit 标记段外重新声明零件库导出的名字 {name}（kit.md 3.2）")

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
        html = (d / "index.html").read_text(encoding="utf-8")
        errs, warns = lint(html, manifest, None, starter)
        errs += [m for m in [missing_walk(html, d.resolve().name, repo)] if m]
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
