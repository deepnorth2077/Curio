"""tools/kit.py 的正反测试（docs/specs/kit.md「测试接缝与验收用例」第 1 行）。"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import kit  # noqa: E402

SAMPLE_TOKENS_SHELL = """<!doctype html><html><head><style>
/* curio-tokens begin */
占位
/* curio-tokens end */
:root{--c-sci:var(--sage)}
</style></head><body></body></html>
"""

SAMPLE_KIT_MOD = """<!DOCTYPE html><html><head><style>
/* curio-kit:1 begin */
占位样式
/* curio-kit:1 end */
.own{color:var(--ink)}
</style></head><body><script>
"use strict";
/* curio-kit:1 begin */
占位脚本
/* curio-kit:1 end */
Kit.start(() => {});
</script></body></html>
"""


def make_fixture_repo():
    root = Path(tempfile.mkdtemp(prefix="curio-kit-"))
    # 固定的测试快照：仓库将来改配色或升版时，这里的 v1 仍代表发布当日。
    kdir = root / "kit/1"
    kdir.mkdir(parents=True)
    keys = "bg pane hover rule ink text muted accent accent-soft grip grip-soft sage sage-bg sky apricot paper good good-soft bad bad-soft".split()
    light = "".join(f"--{k}:#abc;" for k in keys)
    dark = light.replace("#abc", "#123").replace("--accent:#123", "--accent:#A797F7")
    (root / "kit/tokens.css").write_text(f':root{{{light}}}\n:root[data-theme="dark"]{{{dark}}}\n')
    (kdir / "kit.css").write_text(f":root{{{light}}}\n:root.kit-dark{{{dark}}}\n")
    (kdir / "kit.js").write_text("/* curio-sfx begin */\nfunction createSfx() {}\n/* curio-sfx end */\n")
    (kdir / "README.md").write_text("contract: activity/1.2\n")
    (root / "app").mkdir()
    (root / "preview").mkdir()
    (root / "app/sfx.js").write_text("/* curio-sfx begin */\n占位\n/* curio-sfx end */\nexport { createSfx };\n")
    (root / "app/index.html").write_text(SAMPLE_TOKENS_SHELL, encoding="utf-8")
    (root / "preview/template.html").write_text(SAMPLE_TOKENS_SHELL, encoding="utf-8")
    starter = root / kit.STARTER_REL
    starter.parent.mkdir(parents=True)
    starter.write_text(SAMPLE_KIT_MOD, encoding="utf-8")
    mod = root / "content/activities/act.simulation.demo-01"
    mod.mkdir(parents=True)
    (mod / "manifest.yaml").write_text(
        "id: act.simulation.demo-01\ncontract: activity/1.2\nkit: 1\ntype: simulation\nversion: 1\n"
        "title: 示例\ntargets: [math.fraction.unit-fraction]\nage_band: G3-4\nentry: index.html\n"
        "pedagogy: explain\nemits: [observed]\nreview: approved\n",
        encoding="utf-8",
    )
    (mod / "index.html").write_text(SAMPLE_KIT_MOD, encoding="utf-8")
    old_mod = root / "content/activities/act.simulation.old-01"
    old_mod.mkdir(parents=True)
    (old_mod / "manifest.yaml").write_text(
        "id: act.simulation.old-01\ncontract: activity/1.1\ntype: simulation\nversion: 1\n"
        "title: 旧模块\ntargets: [math.fraction.unit-fraction]\nage_band: G3-4\nentry: index.html\n"
        "pedagogy: explain\nemits: [observed]\nreview: approved\n",
        encoding="utf-8",
    )
    (old_mod / "index.html").write_text("<!DOCTYPE html><html><body>旧模块</body></html>\n", encoding="utf-8")
    return root


class TestKitTool(unittest.TestCase):
    def setUp(self):
        self.repo = make_fixture_repo()
        changed, errors = kit.sync_repo(self.repo)
        self.assertEqual(errors, [])
        self.assertEqual(len(changed), 5)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_synced_repo_passes_check(self):
        self.assertEqual(kit.check_repo(self.repo), [])
        # 再跑一次 sync 不会重复改文件
        changed, errors = kit.sync_repo(self.repo)
        self.assertEqual((changed, errors), ([], []))

    def test_one_char_drift_inside_kit_marker_fails(self):
        idx = self.repo / "content/activities/act.simulation.demo-01/index.html"
        idx.write_text(idx.read_text(encoding="utf-8").replace("--accent:#A797F7", "--accent:#A797F6", 1), encoding="utf-8")
        errs = kit.check_repo(self.repo)
        self.assertTrue(any("act.simulation.demo-01/index.html" in f and "不一致" in m for f, m in errs), errs)

    def test_one_char_drift_inside_tokens_marker_fails(self):
        sh = self.repo / "app/index.html"
        sh.write_text(sh.read_text(encoding="utf-8").replace("#A797F7", "#E0876A", 1), encoding="utf-8")
        errs = kit.check_repo(self.repo)
        self.assertTrue(any(f == "app/index.html" and "不一致" in m for f, m in errs), errs)

    def test_missing_half_marker_fails(self):
        idx = self.repo / "content/activities/act.simulation.demo-01/index.html"
        idx.write_text(idx.read_text(encoding="utf-8").replace("/* curio-kit:1 end */", "", 1), encoding="utf-8")
        errs = kit.check_repo(self.repo)
        self.assertTrue(any("act.simulation.demo-01/index.html" in f and "curio-kit:1" in m for f, m in errs), errs)

        sh = self.repo / "preview/template.html"
        sh.write_text(sh.read_text(encoding="utf-8").replace("/* curio-tokens end */", ""), encoding="utf-8")
        errs2 = kit.check_repo(self.repo)
        self.assertTrue(any(f == "preview/template.html" and "标记必须成对" in m for f, m in errs2), errs2)

    def test_nonexistent_kit_version_fails(self):
        mf = self.repo / "content/activities/act.simulation.demo-01/manifest.yaml"
        mf.write_text(mf.read_text(encoding="utf-8").replace("kit: 1", "kit: 99"), encoding="utf-8")
        errs = kit.check_repo(self.repo)
        self.assertTrue(any("kit: 99" in m for _, m in errs), errs)

    def test_v11_module_with_curio_kit_marker_fails(self):
        old_idx = self.repo / "content/activities/act.simulation.old-01/index.html"
        old_idx.write_text(SAMPLE_KIT_MOD, encoding="utf-8")
        errs = kit.check_repo(self.repo)
        self.assertTrue(any("old-01/index.html" in f and "未声明 activity/1.2" in m for f, m in errs), errs)

    def test_invalid_hex_in_tokens_css_fails(self):
        tok = self.repo / "kit/tokens.css"
        tok.write_text(tok.read_text(encoding="utf-8").replace("#A797F7", "rgb(1,2,3)"), encoding="utf-8")
        errs = kit.check_repo(self.repo)
        self.assertTrue(any(f == "kit/tokens.css" and "十六进制颜色" in m for f, m in errs), errs)

    def test_starter_missing_markers_is_an_error(self):
        path = self.repo / kit.STARTER_REL
        path.write_text("<style></style><script></script>")
        self.assertTrue(any(f == kit.STARTER_REL for f, _ in kit.sync_repo(self.repo)[1]))
        self.assertTrue(any(f == kit.STARTER_REL for f, _ in kit.check_repo(self.repo)))

    def test_marked_blocks_can_follow_other_tags_in_either_order(self):
        path = self.repo / kit.STARTER_REL
        before = '<script type="application/json">{"text":"<style>data</style>"}</script><style>.own{}</style>'
        template = "/* curio-kit:1 begin */\n占位\n/* curio-kit:1 end */"
        script = f"<script>{template}\nconst after = '活动脚本';</script>"
        style = f"<style>{template}\n.ownAfter{{}}</style>"
        for tags in ((script, style), (style, script)):
            with self.subTest(first=tags[0][:7]):
                old = before + "".join(tags)
                path.write_text(old)
                self.assertEqual(kit.sync_repo(self.repo), ([kit.STARTER_REL], []))
                new = old.replace("<script>" + template, "<script>" + template.replace(
                    "占位\n", (self.repo / "kit/1/kit.js").read_text()))
                new = new.replace("<style>" + template, "<style>" + template.replace(
                    "占位\n", (self.repo / "kit/1/kit.css").read_text()))
                self.assertEqual(path.read_text(), new)
                self.assertEqual(kit.check_repo(self.repo), [])
        split = before + script.replace("/* curio-kit:1 end */", "</script><script>/* curio-kit:1 end */") + style
        path.write_text(split)
        self.assertTrue(kit.sync_repo(self.repo)[1])
        self.assertEqual(path.read_text(), split)

    def test_kit_requires_effective_css_and_a_classic_inline_script(self):
        starter = self.repo / kit.STARTER_REL
        for old, replacement in (
            ("<script>", '<script type="application/json">'),
            ("<script>", '<script type="module">'),
            ("<script>", '<script type="importmap">'),
            ("<script>", '<script language="vbscript">'),
            ("<script>", '<script src="local.js">'),
            ("<script>", "<script nomodule>"),
            ("<style>", '<style type="text/plain">'),
            ("<style>", '<style media="print">'),
            ("<style>", "<style disabled>"),
        ):
            with self.subTest(tag=replacement):
                starter.write_text(SAMPLE_KIT_MOD.replace(old, replacement))
                self.assertTrue(any(f == kit.STARTER_REL for f, _ in kit.check_repo(self.repo)))
        for tag in ("template", "noscript", "textarea", "svg", "math", "iframe"):
            with self.subTest(tag=tag):
                starter.write_text(SAMPLE_KIT_MOD.replace("<script>", f"<{tag}><script>").replace(
                    "</script>", f"</script></{tag}>"))
                self.assertTrue(any(f == kit.STARTER_REL for f, _ in kit.check_repo(self.repo)))
        starter.write_text(SAMPLE_KIT_MOD.replace("<style>", '<style type="text/css" media="all">').replace(
            "<script>", '<script type="text/javascript">'))
        self.assertEqual(kit.sync_repo(self.repo)[1], [])
        self.assertEqual(kit.check_repo(self.repo), [])

    def test_executable_scripts_exclude_data_and_preserve_document_order(self):
        html = ('<script type="module">moduleCode</script><template><script>templateCode</script></template>'
                '<script type="application/json">data</script><script>classicCode</script>')
        self.assertEqual(kit.executable_scripts(html), ["moduleCode", "classicCode"])
        self.assertEqual(kit.executable_scripts(html, classic_only=True), ["classicCode"])
        self.assertEqual(kit.executable_scripts(html, modules_only=True), ["moduleCode"])

    def test_manifest_and_readme_contracts_must_match(self):
        (self.repo / "kit/1/README.md").write_text("contract: activity/1.1\n")
        errors = kit.check_repo(self.repo)
        self.assertTrue(any(f.endswith("demo-01/manifest.yaml") and "不一致" in msg for f, msg in errors), errors)

    def test_both_schemes_must_supply_a_hex_value_for_additional_tokens(self):
        path = self.repo / "kit/tokens.css"
        source = path.read_text()
        for dark in ("", "--outline:purple;"):
            with self.subTest(dark=dark):
                path.write_text(source.replace(":root{", ":root{--outline:#abc;").replace(
                    ':root[data-theme="dark"]{', ':root[data-theme="dark"]{' + dark))
                self.assertTrue(any(f == "kit/tokens.css" and "outline" in msg for f, msg in kit.check_repo(self.repo)))

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def publish_v1(self):
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("add", ".")
        self.git("commit", "-m", "initial with kit 1 on main")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")

    def test_commented_palette_entries_do_not_supply_colours(self):
        for path in (self.repo / "kit/tokens.css", self.repo / "kit/1/kit.css"):
            with self.subTest(path=path):
                original = path.read_text()
                path.write_text(original.replace("--accent:#A797F7;", "/* --accent:#A797F7; */"))
                self.assertTrue(any(f == path.relative_to(self.repo).as_posix() and "accent" in msg
                                    for f, msg in kit.check_repo(self.repo)))
                path.write_text(original)

    def test_first_unpublished_version_must_have_the_current_fallbacks(self):
        css = self.repo / "kit/1/kit.css"
        css.write_text(css.read_text().replace("#A797F7", "#A797F8"))
        self.assertEqual(kit.sync_repo(self.repo)[1], [])
        errors = kit.check_repo(self.repo)
        self.assertTrue(any(p == "kit/1/kit.css" and "--accent" in msg for p, msg in errors), errors)

    def test_system_and_explicit_dark_share_one_editable_palette(self):
        self.publish_v1()
        path = self.repo / "kit/tokens.css"
        css = path.read_text().replace("#A797F7", "#A797F8").replace(":root{", ":root{--outline:#abc;").replace(
            ':root[data-theme="dark"]{', ':root[data-theme="dark"]{--outline:#def;')
        path.write_text(css)
        self.assertEqual(set(kit.sync_repo(self.repo)[0]), set(kit.TOKEN_TARGETS))
        for target in kit.TOKEN_TARGETS:
            host = (self.repo / target).read_text()
            dark = host.split(':root[data-theme="dark"]{', 1)[1].split("}", 1)[0]
            self.assertIn(f'@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{dark}}}}}', host)
            self.assertIn("--accent:#A797F8", dark)
            self.assertIn("--outline:#def", dark)
            self.assertIn("--curio-palette-keys:outline bg", host)
        self.assertEqual(kit.check_repo(self.repo), [])
        self.assertEqual(kit.sync_repo(self.repo), ([], []))
        path.write_text(css + "@media (prefers-color-scheme:dark){:root{--outline:#999}}")
        self.assertTrue(any("@media" in msg for _, msg in kit.check_repo(self.repo)))

    def test_frozen_kit_allows_palette_evolution_and_checks_new_versions(self):
        self.publish_v1()
        path = self.repo / "kit/tokens.css"
        path.write_text(path.read_text().replace("#A797F7", "#A797F8").replace("--bg:", "--outline:#abc;--bg:"))
        changed, errors = kit.sync_repo(self.repo)
        self.assertEqual((set(changed), errors), (set(kit.TOKEN_TARGETS), []))
        self.assertEqual(kit.check_repo(self.repo, base="origin/main"), [])
        for shell in kit.TOKEN_TARGETS:
            self.assertIn("--curio-palette-keys:outline bg", (self.repo / shell).read_text())

        v2 = self.repo / "kit/2"
        shutil.copytree(self.repo / "kit/1", v2)
        errors = kit.check_repo(self.repo, base="origin/main")
        self.assertEqual({p for p, _ in errors}, {"kit/2/kit.css"})
        self.assertTrue(any("accent" in msg for _, msg in errors))
        self.assertTrue(any("outline" in msg for _, msg in errors))
        css = v2 / "kit.css"
        css.write_text(css.read_text().replace("#A797F7", "#A797F8").replace("--bg:", "--outline:#abc;--bg:"))
        self.assertEqual(kit.check_repo(self.repo, base="origin/main"), [])

    def test_published_version_stays_frozen_after_its_last_consumer_migrates(self):
        self.publish_v1()
        shutil.copytree(self.repo / "kit/1", self.repo / "kit/2")
        mod = self.repo / "content/activities/act.simulation.demo-01"
        for path in (mod / "manifest.yaml", mod / "index.html", self.repo / kit.STARTER_REL):
            path.write_text(path.read_text().replace("kit: 1", "kit: 2").replace("curio-kit:1", "curio-kit:2"))
        self.git("add", ".")
        self.git("commit", "-m", "last consumer upgraded")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.assertEqual(kit.check_repo(self.repo), [])
        js = self.repo / "kit/1/kit.js"
        js.write_text(js.read_text() + "// 改动已退役的 v1\n")
        errors = kit.check_repo(self.repo)
        self.assertTrue(any(f == "kit/1/kit.js" and "冻结后不能修改" in msg for f, msg in errors), errors)

    def test_versions_only_used_in_unmerged_drafts_are_not_frozen(self):
        self.publish_v1()
        v2 = self.repo / "kit/2"
        shutil.copytree(self.repo / "kit/1", v2)
        self.git("add", "kit/2")
        self.git("commit", "-m", "prepare v2")
        self.git("checkout", "-b", "draft-v2")
        manifest = self.repo / "content/activities/act.simulation.demo-01/manifest.yaml"
        old = manifest.read_text()
        manifest.write_text(old.replace("kit: 1", "kit: 2"))
        self.git("commit", "-am", "try v2 on the side branch")
        manifest.write_text(old)
        self.git("commit", "-am", "revert before merging")
        self.git("checkout", "main")
        self.git("merge", "--no-ff", "-m", "accept final branch state", "draft-v2")
        js = v2 / "kit.js"
        js.write_text(js.read_text() + "// 尚未发布的 v2 可以改。\n")
        self.assertEqual(kit.check_repo(self.repo, base="main"), [])

    def add_module(self, name, contract, kit_line):
        mod = self.repo / f"content/activities/{name}"
        mod.mkdir(parents=True)
        (mod / "manifest.yaml").write_text(
            f"id: {name}\ncontract: {contract}\n{kit_line}type: simulation\nversion: 1\n"
            "title: 新模块\ntargets: [math.fraction.unit-fraction]\nage_band: G3-4\nentry: index.html\n"
            "pedagogy: explain\nemits: [observed]\nreview: approved\n", encoding="utf-8")
        (mod / "index.html").write_text(SAMPLE_KIT_MOD if kit_line else "<!DOCTYPE html><html><body>新</body></html>\n",
                                        encoding="utf-8")
        return mod

    def test_new_module_must_use_latest_kit_version_and_contract(self):
        self.publish_v1()
        base = "origin/main"
        # 新增的 1.1 模块被拦
        old_style = self.add_module("act.simulation.new-v11", "activity/1.1", "")
        errs = kit.check_repo(self.repo, base=base)
        self.assertTrue(any(f.endswith("new-v11/manifest.yaml") and "新增互动模块必须使用最新零件库" in m and "kit: 1" in m
                            for f, m in errs), errs)
        shutil.rmtree(old_style)
        # 修改主线上已有的 1.1 模块不受影响
        old_idx = self.repo / "content/activities/act.simulation.old-01/index.html"
        old_idx.write_text(old_idx.read_text(encoding="utf-8") + "<!-- 小修 -->\n", encoding="utf-8")
        self.assertEqual(kit.check_repo(self.repo, base=base), [])
        # 新增的最新版 kit 模块通过
        self.add_module("act.simulation.new-v12", "activity/1.2", "kit: 1\n")
        self.assertEqual(kit.sync_repo(self.repo)[1], [])
        self.assertEqual(kit.check_repo(self.repo, base=base), [])
        # 出了 kit/2 以后：新增模块还用 kit: 1 被拦，主线已有的 demo-01 不受影响
        shutil.copytree(self.repo / "kit/1", self.repo / "kit/2")
        starter = self.repo / kit.STARTER_REL
        starter.write_text(starter.read_text(encoding="utf-8").replace("curio-kit:1", "curio-kit:2"), encoding="utf-8")
        self.assertEqual(kit.sync_repo(self.repo)[1], [])
        errs = kit.check_repo(self.repo, base=base)
        self.assertTrue(any(f.endswith("new-v12/manifest.yaml") and "kit: 2" in m for f, m in errs), errs)
        self.assertFalse(any("demo-01" in f for f, _ in errs), errs)
        # 新增模块改用 kit: 2 后通过
        mod = self.repo / "content/activities/act.simulation.new-v12"
        mf, idx = mod / "manifest.yaml", mod / "index.html"
        mf.write_text(mf.read_text(encoding="utf-8").replace("kit: 1", "kit: 2"), encoding="utf-8")
        idx.write_text(idx.read_text(encoding="utf-8").replace("curio-kit:1", "curio-kit:2"), encoding="utf-8")
        self.assertEqual(kit.sync_repo(self.repo)[1], [])
        self.assertEqual(kit.check_repo(self.repo, base=base), [])

    def test_shell_sfx_tracks_newest_version_without_changing_previous_versions(self):
        self.publish_v1()
        target = self.repo / "app/sfx.js"
        v1 = self.repo / "kit/1/kit.js"
        original = v1.read_text()
        v2 = self.repo / "kit/2"
        shutil.copytree(v1.parent, v2)
        path = v2 / "kit.js"
        path.write_text(original.replace("function createSfx() {}", "function createSfx() { return 2; }"))
        self.assertTrue(any(f == "app/sfx.js" for f, _ in kit.check_repo(self.repo)))
        self.assertEqual(kit.sync_repo(self.repo), (["app/sfx.js"], []))
        self.assertIn("return 2", target.read_text())
        self.assertIn("export { createSfx };", target.read_text())
        self.assertEqual(v1.read_text(), original)
        self.assertEqual(kit.check_repo(self.repo), [])
        path.write_text(original.replace("/* curio-sfx end */", ""))
        self.assertTrue(any("curio-sfx" in msg for _, msg in kit.check_repo(self.repo)))
        self.assertTrue(kit.sync_repo(self.repo)[1])


if __name__ == "__main__":
    unittest.main()
