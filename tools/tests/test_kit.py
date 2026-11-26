"""tools/kit.py 的正反测试（docs/specs/kit.md「测试接缝与验收用例」第 1 行）。"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
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
    shutil.copytree(REPO / "kit", root / "kit")
    (root / "app").mkdir()
    (root / "preview").mkdir()
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
        self.assertEqual(len(changed), 4)

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

    def test_modifying_frozen_kit_on_main_fails_while_tokens_change_is_allowed(self):
        git = lambda *a: subprocess.run(["git", *a], cwd=self.repo, check=True, capture_output=True, text=True)
        git("init", "-b", "main")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "Test")
        git("add", ".")
        git("commit", "-m", "initial with kit 1 on main")
        git("update-ref", "refs/remotes/origin/main", "HEAD")
        git("checkout", "-b", "arch/edit")

        # 改已上 main 的 kit/1/kit.js → 必须报错
        kjs = self.repo / "kit/1/kit.js"
        orig_js = kjs.read_text(encoding="utf-8")
        kjs.write_text(orig_js + "\n// 偷偷加一行\n", encoding="utf-8")
        kit.sync_repo(self.repo)
        errs = kit.check_repo(self.repo, base="origin/main")
        self.assertTrue(any(f == "kit/1/kit.js" and "冻结后不能修改" in m for f, m in errs), errs)

        # 恢复 kit/1/kit.js，新建 kit/2/ → 允许
        kjs.write_text(orig_js, encoding="utf-8")
        shutil.copytree(self.repo / "kit/1", self.repo / "kit/2")
        kit.sync_repo(self.repo)
        self.assertEqual(kit.check_repo(self.repo, base="origin/main"), [])


if __name__ == "__main__":
    unittest.main()
