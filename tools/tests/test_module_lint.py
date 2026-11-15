"""tools/module_lint.py 的正反测试：每条规则一个通过样例、一个失败样例。运行：python -m unittest discover -s tools/tests"""
import sys
import unittest
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import module_lint  # noqa: E402

GRIP_CSS = ":root{ --accent:#C2603F; --grip:#2A7F7C; --grip-soft:#D3E8E5; }\n.btn.hold{background:var(--grip)}\n.gfill{fill:var(--grip)}\n.lead{fill:var(--accent)}\n"
MANIFEST = {"emits": ["predicted", "observed"], "misconceptions": ["bigger-denominator-bigger"]}


def page(script=None, css="", body=""):
    """拼一个最小模块页。script 不给时用一段合格的脚本。"""
    if script is None:
        script = (
            'const Host = { ready(){}, event(){} };\n'
            'function ask(){ Host.event("predicted", { misconception: null }); }\n'
            'const OPTS = [{ label: "八分之一那块大", mis: "bigger-denominator-bigger" }];\n'
            'function enter1(){ ask(); Host.event("observed", { station: 1 }); }\n'
            'Host.ready();\nenter1();\n'
        )
    return f"<!DOCTYPE html><html><head><style>{css}</style></head><body>{body}<script>\n{script}</script></body></html>\n"


class Lint(unittest.TestCase):
    def ok(self, html, manifest=MANIFEST, **kw):
        errors, _ = module_lint.lint(html, manifest, **kw)
        self.assertEqual(errors, [], f"本应通过，却报错：{errors}")

    def fails(self, html, text, manifest=MANIFEST, **kw):
        errors, _ = module_lint.lint(html, manifest, **kw)
        self.assertTrue(any(text in e for e in errors), f"本应报「{text}」，实际：{errors}")

    def warns(self, html, text, manifest=MANIFEST, **kw):
        _, warnings = module_lint.lint(html, manifest, **kw)
        self.assertTrue(any(text in w for w in warnings), f"本应提醒「{text}」，实际：{warnings}")


class TestAllModules(Lint):
    def test_minimal_page_passes(self):
        self.ok(page())

    def test_page_without_script_is_not_checked_for_ready(self):
        self.ok("<!doctype html><html><body><p>分蛋糕</p></body></html>", {"emits": ["answered"]})

    def test_script_with_only_comments_is_not_checked_for_ready(self):
        self.ok("<!doctype html><html><body><script>// 只有一行注释</script></body></html>", {"emits": []})

    def test_network_and_storage(self):
        for bad, name in [("fetch('/x');", "fetch("), ("new XMLHttpRequest();", "XMLHttpRequest"), ("localStorage.setItem('a', 1);", "localStorage"),
                          ("sessionStorage.clear();", "sessionStorage"), ("indexedDB.open('a');", "indexedDB"), ("new WebSocket('wss://a');", "WebSocket"),
                          ("import('./a.js');", "import(")]:
            with self.subTest(name=name):
                self.fails(page(f"const Host={{ready(){{}}}};\nHost.ready();\n{bad}\n"), name, {"emits": []})

    def test_comments_about_storage_are_fine(self):
        self.ok(page('const Host={ready(){}};\n// 不读写 localStorage，不 fetch(任何东西)\n/* 不联网：XMLHttpRequest 也不用 */\nHost.ready();\n'), {"emits": []})

    def test_external_resources(self):
        self.fails(page(body='<img src="https://example.com/a.png">'), "外部 src/href")
        self.fails(page(css="@import url(x.css);"), "@import")
        self.fails(page(css="body{background:url(https://example.com/a.png)}"), "url(外部地址)")
        self.fails(page().replace("<script>", '<script src="https://cdn.example.com/lib.js"></script><script>'), "<script src>")

    def test_ready_before_first_station(self):
        self.fails(page('const Host={ready(){}};\nfunction enter1(){}\nenter1();\nHost.ready();\n'), "Host.ready() 必须先于第一站", {"emits": []})
        self.fails(page('const Host={ready(){}};\nfunction enter1(){}\nenter1();\n'), "没有调用 Host.ready()", {"emits": []})
        self.ok(page('const Host={ready(){}};\nfunction enter1(){}\nHost.ready();\nenter1();\n'), {"emits": []})

    def test_verbs_must_be_in_emits(self):
        self.fails(page(), "代码里发了 observed", {"emits": ["predicted"], "misconceptions": ["bigger-denominator-bigger"]})
        self.warns(page(), "emits 里写了 answered，代码里没有发", {"emits": ["predicted", "observed", "answered"], "misconceptions": ["bigger-denominator-bigger"]})
        self.warns(page(), "宿主不认", {"emits": ["predicted", "observed", "started"], "misconceptions": ["bigger-denominator-bigger"]})

    def test_misconceptions_in_code_must_be_declared(self):
        self.fails(page(), "误区 bigger-denominator-bigger 没有写进 manifest", {"emits": ["predicted", "observed"], "misconceptions": []})
        self.warns(page(), "误区 unequal-parts 代码里没有针对", {"emits": ["predicted", "observed"], "misconceptions": ["bigger-denominator-bigger", "unequal-parts"]})
        self.fails(page(), "不在目标知识点的误区列表里", node_misconceptions={"numerator-only"})
        self.ok(page(), node_misconceptions={"bigger-denominator-bigger", "numerator-only"})


class TestNewGeneration(Lint):
    def test_old_modules_skip_grip_rules(self):
        self.ok(page(css=":root{--accent:#C2603F}\n.btn.hold{background:var(--accent)}"))

    def test_grip_page_passes(self):
        self.ok(page(css=GRIP_CSS + "svg#stage.kbd:focus-visible{outline:2px solid var(--grip)}\n#cue{stroke:var(--grip)}\n.gsoft{fill:var(--grip-soft)}\n"))

    def test_accent_on_controls(self):
        self.fails(page(css=GRIP_CSS + ".btn.hold{background:var(--accent)}"), "强调色不能用在控件上")
        self.fails(page(css=GRIP_CSS + "svg#stage:focus-visible{outline:2px solid var(--accent)}"), "强调色不能用在控件上")
        self.fails(page(css=GRIP_CSS + "@media (prefers-color-scheme:dark){ .gfill{fill:var(--accent)} }"), "强调色不能用在控件上")

    def test_grip_used_elsewhere(self):
        self.fails(page(css=GRIP_CSS + ".lead{fill:var(--grip)}"), "圆钮色只给圆钮")
        self.fails(page(css=GRIP_CSS, body='<svg><circle fill="var(--grip)"/></svg>'), "圆钮色只能写在样式表里")

    def test_font_size_attribute(self):
        script = page().split("<script>\n")[1].split("</script>")[0]
        self.fails(page(script + 'const t = `<text font-size="26">星卡</text>`;\n', css=GRIP_CSS), "font-size 属性")
        self.ok(page(script + 'const t = `<text class="ttl">星卡</text>`;\n', css=GRIP_CSS))

    def test_slash_fraction_in_strings(self):
        script = page().split("<script>\n")[1].split("</script>")[0]
        self.fails(page(script + 'say("你拿 1/3 吧");\n', css=GRIP_CSS), "不用斜杠")
        self.ok(page(script + 'const d = `M10 20L${a}/${b}`;\nconst q = x / 3;\nconst v = "0 0 800 610";\n', css=GRIP_CSS))

    def test_exclamation_marks(self):
        script = page().split("<script>\n")[1].split("</script>")[0]
        self.fails(page(script + 'say("好！"); say("对！"); say("哇！"); say("再来！");\n', css=GRIP_CSS), "感叹号不超过 3 个")
        self.ok(page(script + 'say("好！"); say("对！"); say("哇！");\n', css=GRIP_CSS))


class TestKitSegments(Lint):
    STARTER = "<style>/* kit:grip 骨架 */\n.gfill{fill:var(--grip)}\n</style><script>/* kit:host */\nconst Host = 1;\n/* ============ 2. 下一节 */</script>"

    def test_same_segment_is_quiet(self):
        html = "<style>/* kit:grip 模块里的说明不一样也行 */\n.gfill{fill:var(--grip)}\n</style><script>/* kit:host */\nconst   Host = 1;\n/* ============ 2. x */</script>"
        _, warnings = module_lint.lint(html, {}, starter=self.STARTER)
        self.assertFalse([w for w in warnings if "kit:" in w], warnings)

    def test_drifted_segment_warns(self):
        html = "<style>/* kit:grip */\n.gfill{fill:var(--grip);opacity:.5}\n</style>"
        self.warns(html, "kit:grip 这一段和骨架", {}, starter=self.STARTER)


class TestRealModules(unittest.TestCase):
    """仓库里现有的每个动手探索模块都要通过（防止检查规则写错，误伤已经验收过的模块）。"""

    def test_every_module_passes(self):
        nodes = {}
        for f in (REPO / "content/nodes").rglob("*.yaml"):
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
            nodes[doc["id"]] = {m["id"] for m in doc.get("misconceptions", []) if isinstance(m, dict)}
        dirs = sorted(d for d in (REPO / "content/activities").glob("act.simulation.*") if (d / "index.html").exists())
        self.assertTrue(dirs)
        for d in dirs:
            with self.subTest(module=d.name):
                manifest = yaml.safe_load((d / "manifest.yaml").read_text(encoding="utf-8"))
                mis = set().union(*(nodes.get(t, set()) for t in manifest.get("targets", [])))
                errors, _ = module_lint.lint((d / "index.html").read_text(encoding="utf-8"), manifest, mis)
                self.assertEqual(errors, [], f"{d.name}：{errors}")


if __name__ == "__main__":
    unittest.main()
