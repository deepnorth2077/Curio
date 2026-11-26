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
NOSELECT = module_lint.NOSELECT_CSS   # 长按不选字（#156），每个样例模块都带上


def page(script=None, css="", body="", noselect=True):
    """拼一个最小模块页。script 不给时用一段合格的脚本；noselect=False 时不带长按不选字那两条。"""
    css = (NOSELECT if noselect else "") + css
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
        self.ok(f"<!doctype html><html><head><style>{NOSELECT}</style></head><body><p>分蛋糕</p></body></html>", {"emits": ["answered"]})

    def test_script_with_only_comments_is_not_checked_for_ready(self):
        self.ok(f"<!doctype html><html><head><style>{NOSELECT}</style></head><body><script>// 只有一行注释</script></body></html>", {"emits": []})

    def test_noselect_present_passes(self):
        """长按不选字（#156）：两条都在就通过；选择器顺序、空格、多写别的声明都不要紧。"""
        self.ok(page())
        self.ok(page(noselect=False, css="html { user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; color-scheme: light }\n"
                                         "textarea, input, [contenteditable], select { user-select:text; -webkit-user-select:text; -webkit-touch-callout:default }\n"))

    def test_noselect_missing_fails(self):
        self.fails(page(noselect=False), "长按会选中文字")
        html_rule, input_rule = NOSELECT.splitlines()
        for css, which in [(input_rule, "html 上的"), (html_rule, "input,textarea,select,[contenteditable] 上的"),
                           (html_rule.replace("-webkit-touch-callout:none", ""), "html 上的"),          # 少了不弹菜单
                           (html_rule.replace("-webkit-user-select:none;", ""), "html 上的"),          # 少了 -webkit- 写法
                           (html_rule.replace("html{", "body{"), "html 上的"),                       # 不在 html 上
                           ("@media (hover:none){" + html_rule + "}\n" + input_rule, "html 上的"),   # 只在 @media 里
                           ("/* " + html_rule + " */\n" + input_rule, "html 上的"),                  # 注释掉了
                           (html_rule + "\ninput,textarea{-webkit-user-select:text;user-select:text;-webkit-touch-callout:default}", "input,textarea,select,[contenteditable] 上的")]:
            with self.subTest(css=css):
                self.fails(page(noselect=False, css=css), which)
        self.fails(page(noselect=False, body=f"<p style='x'>{NOSELECT}</p>"), "#156")    # 写在样式表外面不算

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
        self.fails(page(body='<audio src="beep.mp3"></audio>'), "<audio>")
        self.fails(page(body='<video src="clip.mp4"></video>'), "<video>")
        self.fails(page('const Host={ready(){}};\nHost.ready();\nnew Audio("x.mp3");\n'), "new Audio(", {"emits": []})

    def test_ready_before_first_station(self):
        self.fails(page('const Host={ready(){}};\nfunction enter1(){}\nenter1();\nHost.ready();\n'), "Host.ready() 必须先于第一站", {"emits": []})
        self.fails(page('const Host={ready(){}};\nfunction enter1(){}\nenter1();\n'), "没有调用 Host.ready()", {"emits": []})
        self.ok(page('const Host={ready(){}};\nfunction enter1(){}\nHost.ready();\nenter1();\n'), {"emits": []})
        self.ok(page('/* curio-kit:1 begin */\nconst Kit={start(fn){fn()}};\n/* curio-kit:1 end */\nfunction enter1(){}\nKit.start(enter1);\n'),
                {"contract": "activity/1.2", "kit": 1, "emits": []})

    def test_v12_forbids_prefers_color_scheme_and_redeclaring_kit_exports(self):
        m12 = {"contract": "activity/1.2", "kit": 1, "emits": ["predicted", "observed"], "misconceptions": ["bigger-denominator-bigger"]}
        kit_script = (
            '/* curio-kit:1 begin */\n' + (REPO / "kit/1/kit.js").read_text(encoding="utf-8") +
            '\n/* curio-kit:1 end */\n'
            'const OPTS = [{ label: "八分之一那块大", mis: "bigger-denominator-bigger" }];\n'
            'function enter1(){ ask("选哪一块", OPTS, () => observedOnce(1)); }\n'
            'Kit.start(enter1);\n'
        )
        self.ok(page(kit_script, css=".kit-dark{--own:#112233}\n"), m12)
        self.fails(page(kit_script, css="@media (prefers-color-scheme:dark){.x{color:#fff}}\n"), "prefers-color-scheme", m12)
        for name in ("Host", "Kit", "Sfx", "Sk", "sketchLib", "fracS", "oneMark", "grip", "lineStrip"):
            with self.subTest(name=name):
                self.fails(page(kit_script + f"const {name} = 1;\n"), f"重新声明零件库导出的名字 {name}", m12)

    def test_kit_checks_script_scope_and_takes_exports_from_the_embedded_version(self):
        kit = "/* curio-kit:2 begin */\nconst Kit = {}; function createSfx(){} function newPart(){}\n/* curio-kit:2 end */\n"
        manifest = {"contract": "activity/1.2", "kit": 2, "emits": []}
        local = "function play(newPart){ const Kit = {}; var createSfx; } { let newPart; }"
        self.ok(page(kit + local + "\nKit.start(play);"), manifest)
        for decl, name in (("let first, createSfx;", "createSfx"),
                           ("const {a: newPart} = options;", "newPart"),
                           ("if (playing) { var Kit; }", "Kit"),
                           ("class newPart {}", "newPart")):
            with self.subTest(decl=decl):
                self.fails(page(kit + decl + "\nKit.start(play);"), f"重新声明零件库导出的名字 {name}", manifest)

    def test_kit_verbs_belong_to_the_activity_that_calls_the_helper(self):
        kit = ("/* curio-kit:1 begin */\n"
               'function ask(q){Host.event("predicted", q)}\n'
               'function observedOnce(n){Host.event("observed", {station:n, item:"station-complete"})}\n'
               "/* curio-kit:1 end */\n")
        manifest = {"contract": "activity/1.2", "kit": 1, "emits": ["observed"]}
        observe = 'Kit.start(() => { say("predicted"); observedOnce(1); });'
        html = page(kit + observe)
        self.assertEqual(module_lint.lint(html, manifest), ([], []))
        self.fails(page(kit + 'Kit.start(() => ask("选什么", [], cb));'), "代码里发了 predicted", manifest)
        self.warns(page(kit + "Kit.start(() => {});"), "emits 里写了 observed，代码里没有发", manifest)

    def test_events_inside_local_scopes_resolve_to_their_own_bindings(self):
        kit = ("/* curio-kit:1 begin */\nconst Host={}; function ask(){} function observedOnce(){}\n"
               "/* curio-kit:1 end */\n")
        m = {"contract": "activity/1.2", "kit": 1, "emits": []}
        for own in (
            "Kit.start(() => {const observedOnce = x => x; observedOnce(1)});",
            "Kit.start(() => {if (true) {var ask = f}; ask('local')});",
            "Kit.start(() => {function observedOnce(n){} observedOnce(1)});",
            "Kit.start(({ask}) => ask('local'));",
            "Kit.start(() => {try {} catch (Host) {Host.event('answered', {})}});",
            "Kit.start(() => {for (const ask of handlers) ask('local')});",
        ):
            with self.subTest(own=own):
                self.assertEqual(module_lint.lint(page(kit + own), m), ([], []))
        outer = "Kit.start(() => {{ const ask = f; ask(1); } ask('global'); });"
        self.fails(page(kit + outer), "代码里发了 predicted", m)

    def test_only_executable_scripts_count_and_each_module_has_its_own_scope(self):
        kit = "/* curio-kit:1 begin */\nfunction ask(){} function observedOnce(){}\n/* curio-kit:1 end */\n"
        m = {"contract": "activity/1.2", "kit": 1, "emits": []}
        body = ('<script type="text/plain">observedOnce(1)</script>'
                '<template><script>ask("question")</script></template>'
                '<script type="module">const observedOnce = callback; observedOnce(1)</script>')
        self.assertEqual(module_lint.lint(page(kit + "Kit.start(() => {});", body=body), m), ([], []))

        html = page(kit, body=body).replace("</body>", '<script type="module">\nKit.start(() => observedOnce(1));</script></body>')
        self.assertEqual(module_lint.lint(html, {**m, "emits": ["observed"]}), ([], []))

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


class TestWalkRequired(unittest.TestCase):
    """新一代模块要有专属走查 tools/walks/<活动 id>.py。"""

    def setUp(self):
        import tempfile
        self.repo = Path(tempfile.mkdtemp(prefix="curio-walk-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_new_generation_without_walk_fails(self):
        msg = module_lint.missing_walk(page(css=GRIP_CSS), "act.simulation.x-01", self.repo)
        self.assertIn("tools/walks/act.simulation.x-01.py", msg or "")

    def test_new_generation_with_walk_passes(self):
        (self.repo / "tools/walks").mkdir(parents=True)
        (self.repo / "tools/walks/act.simulation.x-01.py").write_text("# 走查\n", encoding="utf-8")
        self.assertIsNone(module_lint.missing_walk(page(css=GRIP_CSS), "act.simulation.x-01", self.repo))

    def test_old_module_needs_no_walk(self):
        self.assertIsNone(module_lint.missing_walk(page(css=":root{--accent:#C2603F}"), "act.simulation.x-01", self.repo))

    def test_real_new_generation_modules_have_walks(self):
        for d in sorted((REPO / "content/activities").glob("act.simulation.*")):
            with self.subTest(module=d.name):
                self.assertIsNone(module_lint.missing_walk((d / "index.html").read_text(encoding="utf-8"), d.name, REPO))


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
