"""preview/build.py 的 build_bundle()（原型读的内容包）只收录已批准的活动。

孩子在原型里玩的就是这份内容包，所以它和正式发布（tools/build_release.py）一样，
只收 review: approved 的活动。测试只通过 build_bundle() 的返回值观察结果，变异都在临时副本里做。
"""
import contextlib
import io
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "preview"))
import build  # noqa: E402

NODE = "biology.cell.cell-intro"
EXPLAIN = "act.explain.cell-intro-01"      # 数据活动，带自己独有的配图
SIMULATION = "act.simulation.cell-zoom-01"  # 动手探索模块（manifest.yaml）
QUIZ = "act.quiz.cell-intro-01"


def set_review(root, aid, value):
    folder = root / "content/activities" / aid
    path = folder / ("manifest.yaml" if (folder / "manifest.yaml").is_file() else "activity.yaml")
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^review:.*$", f"review: {value}", text)
    assert n == 1, path
    path.write_text(new, encoding="utf-8")


def bundle(root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        data = build.build_bundle([root])
    return data, out.getvalue()


def node_acts(data, node_id):
    return next(n["activities"] for n in data["nodes"] if n["id"] == node_id)


def own_figures(root, aid):
    act = yaml.safe_load((root / "content/activities" / aid / "activity.yaml").read_text(encoding="utf-8"))
    srcs = []
    build.collect_srcs(act.get("body"), srcs)
    return srcs


class PreviewBundleReviewGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(REPO / "content", self.tmp / "content")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_approved_activities_are_included(self):
        data, _ = bundle(self.tmp)
        for aid in (EXPLAIN, SIMULATION, QUIZ):
            self.assertIn(aid, data["activities"])
            self.assertIn(aid, node_acts(data, NODE))
        for src in own_figures(self.tmp, EXPLAIN):
            self.assertIn(src, data["figures"])

    def test_pending_data_activity_is_skipped_with_its_figures(self):
        set_review(self.tmp, EXPLAIN, "pending")
        data, log = bundle(self.tmp)
        self.assertNotIn(EXPLAIN, data["activities"])
        self.assertNotIn(EXPLAIN, node_acts(data, NODE))
        for src in own_figures(self.tmp, EXPLAIN):
            self.assertNotIn(src, data["figures"])
        self.assertIn(EXPLAIN, log)
        # 同一知识点下已批准的活动不受影响
        self.assertIn(QUIZ, node_acts(data, NODE))
        self.assertIn(SIMULATION, node_acts(data, NODE))

    def test_claude_reviewed_module_is_skipped(self):
        set_review(self.tmp, SIMULATION, "claude-reviewed")
        data, log = bundle(self.tmp)
        self.assertNotIn(SIMULATION, data["activities"])
        self.assertNotIn(SIMULATION, node_acts(data, NODE))
        self.assertIn(SIMULATION, log)

    def test_missing_review_field_is_skipped(self):
        path = self.tmp / "content/activities" / QUIZ / "activity.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(r"(?m)^review:.*\n", "", text), encoding="utf-8")
        data, _ = bundle(self.tmp)
        self.assertNotIn(QUIZ, data["activities"])
        self.assertNotIn(QUIZ, node_acts(data, NODE))


if __name__ == "__main__":
    unittest.main()
