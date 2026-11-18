"""走查相关的正反测试：walk_all.py 选谁跑、walklib 卡住时多久报错。运行：python -m unittest discover -s tools/tests

walklib 的用例要 playwright 和 chromium；没装时跳过。"""
import importlib.util
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import walk_all  # noqa: E402

MODS = ["act.simulation.cell-zoom-01", "act.simulation.fair-cut-01"]


class TestSelect(unittest.TestCase):
    def test_core_changes_select_everything(self):
        for core in walk_all.CORE:
            with self.subTest(core=core):
                self.assertEqual(walk_all.select([core], MODS), MODS)

    def test_changed_module_only(self):
        self.assertEqual(walk_all.select(["content/activities/act.simulation.fair-cut-01/index.html"], MODS), ["act.simulation.fair-cut-01"])

    def test_changed_walk_script_selects_its_module(self):
        self.assertEqual(walk_all.select(["tools/walks/act.simulation.fair-cut-01.py"], MODS), ["act.simulation.fair-cut-01"])

    def test_unrelated_changes_select_nothing(self):
        changed = ["docs/handoff.md", "tools/ci_checks.py", "content/nodes/num/x.yaml", "content/activities/act.quiz.unit-fraction-01/activity.yaml",
                   ".claude/skills/curio-anatomy/references/lessons.md"]
        self.assertEqual(walk_all.select(changed, MODS), [])

    def test_walk_for_missing_module_is_skipped(self):
        self.assertEqual(walk_all.select(["tools/walks/act.simulation.not-yet-01.py"], MODS), [])

    def test_all_flag(self):
        self.assertEqual(walk_all.select([], MODS, everything=True), MODS)

    def test_script_choice(self):
        self.assertEqual(walk_all.script_for("act.simulation.fair-cut-01").name, "act.simulation.fair-cut-01.py")
        self.assertEqual(walk_all.script_for("act.simulation.zoom-line-01").name, "act.simulation.zoom-line-01.py")
        self.assertEqual(walk_all.script_for("act.simulation.cell-zoom-01").name, "smoke.py")


FAKE = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div id="readout">切成 1 份</div><div id="say">你好</div><div id="actions"><button>开始</button></div>
<script>
const send = (type, payload) => (window.__sent = window.__sent || []).push({ type, payload: payload || {} });
send("ready");
document.querySelector("#actions button").onclick = () => {
  document.getElementById("actions").innerHTML = "<button>再来</button>";
  document.getElementById("say").textContent = "切好了";
  send("complete");
};
</script></body></html>
"""


@unittest.skipUnless(importlib.util.find_spec("playwright"), "没装 playwright，跳过 walklib 测试")
class TestWalklib(unittest.TestCase):
    def setUp(self):
        import walklib
        self.walklib = walklib
        self.dir = Path(tempfile.mkdtemp(prefix="curio-walk-"))
        (self.dir / "index.html").write_text(FAKE, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_walk(self, play):
        return self.walklib.walk(play, self.dir / "index.html", self.dir / "shots", only="desk")

    def test_normal_walk_passes(self):
        def play(w):
            w.open()
            w.check("ready 先", w.sent()[0]["type"] == "ready")
            w.shot("1-first", first=True)
            w.btn("开始")
            w.check("说了话", w.said() == "切好了", w.said())
            w.check("complete 一次", len(w.sent("complete")) == 1)
        fails, errs, oks = self.run_walk(play)
        self.assertEqual((fails, errs, oks), ([], [], 3))
        self.assertTrue((self.dir / "shots" / "desk-1-first.png").is_file())
        self.assertTrue((self.dir / "shots" / "first-screens.png").is_file())

    def test_missing_button_fails_fast_and_says_where(self):
        took = {}

        def play(w):
            w.open(); w.btn("开始")
            t0 = time.monotonic()
            try:
                w.btn("看托盘")
            finally:
                took["s"] = time.monotonic() - t0
        fails, _, _ = self.run_walk(play)
        self.assertLess(took["s"], 3.0)
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("看托盘", fails[0])
        self.assertIn("再来", fails[0])      # 写出现在有哪些按钮

    def test_failed_check_is_reported(self):
        fails, _, oks = self.run_walk(lambda w: (w.open(), w.check("读数", w.readout() == "切成 2 份", w.readout())))
        self.assertEqual(oks, 0)
        self.assertTrue(fails and "读数" in fails[0] and "切成 1 份" in fails[0], fails)

    def test_overall_timeout(self):
        def play(w):
            w.open()
            while True:
                w.wait(200); w.check("还在", True)
        fails, _, _ = self.walklib.walk(play, self.dir / "index.html", self.dir / "shots", only="desk", timeout=3)
        self.assertTrue(fails and "超时" in fails[0] and "最后一步" in fails[0], fails)


if __name__ == "__main__":
    unittest.main()
