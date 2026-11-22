"""领航员测试用的最小合法内容（docs/specs/navigators.md 第 1 节）。不是测试文件，只供 test_*.py 引用。

face_svg 造的 SVG 满足规格第 1 节的每一条：viewBox 0 0 48 48、白名单元素、颜色只用十个类、
能画出东西的元素不超过 16 个、f-accent 最多一个、不带 id/title/注释、不超过 3 KiB。
需要造反例时用参数改一处。
"""
import yaml

FACES = ["curious", "waiting", "surprised", "clap", "think", "wrong"]
# 非 accent 的类写法（一个元素可以两个类：线稿 + 色块）
CLASS_CYCLE = ["k f-paper", "f-ink", "k1", "f-sky", "f-apricot", "k f-pane", "f-sage", "f-muted"]
HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">'


def drawable(i, cls):
    kind = i % 4
    if kind == 0:
        return f'<circle class="{cls}" cx="{8 + i}" cy="{10 + i}" r="3"/>'
    if kind == 1:
        return f'<ellipse class="{cls}" cx="24" cy="{12 + i}" rx="6" ry="4"/>'
    if kind == 2:
        return f'<rect class="{cls}" x="{4 + i}" y="30" width="6" height="5" rx="1"/>'
    return f'<path class="{cls}" fill="none" d="M{6 + i} 40 Q24 {44 - i} {42 - i} 40"/>'


def face_svg(seed=0, count=5, accent=0, viewbox="0 0 48 48", inject="", pad_to=None, classes=None):
    """count 个能画出东西的元素，其中前 accent 个用 f-accent。inject 原样插在最后（造反例用）。
    pad_to：末尾补空白，补到正好这么多字节。"""
    parts = []
    for i in range(count):
        cls = "f-accent" if i < accent else (classes or CLASS_CYCLE)[(i + seed) % len(classes or CLASS_CYCLE)]
        parts.append(drawable(i + seed, cls))
    text = HEAD.format(vb=viewbox) + "".join(parts) + inject + "</svg>\n"
    if pad_to is not None:
        need = pad_to - len(text.encode("utf-8"))
        assert need >= 0, f"SVG 已有 {len(text)} 字节，超过 pad_to"
        text = text[: -len("</svg>\n")] + " " * need + "</svg>\n"
        assert len(text.encode("utf-8")) == pad_to
    return text


def navigator_yaml(nid, title, intro, review="approved", unlock=None, version=1, **extra):
    doc = {
        "schema": "navigator/1", "id": nid, "version": version, "title": title, "intro": intro,
        "unlock": {"start": True} if unlock is None else unlock, "review": review,
        "author": {"model": "Claude Opus 5.5", "prompt_ref": "prototype/design/navigator.html"},
    }
    doc.update(extra)
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def nav_files(nid="nav.lamp", title="小灯", intro="我头顶有一盏小灯，想到什么它就亮。", seed=0, faces=None, omit=(), **yaml_args):
    """一位领航员的全部文件：{相对文件名: 文本}。faces 覆盖某几张脸的文本；omit 去掉某些文件（如 "wrong.svg"）。"""
    files = {"navigator.yaml": navigator_yaml(nid, title, intro, **yaml_args)}
    for k, face in enumerate(FACES):
        files[f"{face}.svg"] = face_svg(seed=seed + k)
    for face, text in (faces or {}).items():
        files[f"{face}.svg"] = text
    for name in omit:
        files.pop(name)
    return files


LAMP = dict(nid="nav.lamp", title="小灯", intro="我头顶有一盏小灯，想到什么它就亮。", seed=0)
RING = dict(nid="nav.ring", title="小环", intro="我是一个小圆环，什么都爱转一转。", seed=3)


def two_navigators():
    """{ "content/navigators/<id>/<文件>": 文本 }，两位都合法、都是 start、都 approved。"""
    out = {}
    for spec in (LAMP, RING):
        for name, text in nav_files(**spec).items():
            out[f"content/navigators/{spec['nid']}/{name}"] = text
    return out
