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

    def test_trial_page_build_is_not_filtered(self):
        # 试玩页（--out，build()）由维护者生成、按 STARS 显式列活动，这次不改它的行为
        set_review(self.tmp, EXPLAIN, "pending")
        with contextlib.redirect_stdout(io.StringIO()):
            data = build.build([self.tmp])
        star = next(s for s in data["stars"] if s["id"] == NODE)
        self.assertIn(EXPLAIN, [a["id"] for a in star["activities"]])


class MathConstellationPreview(unittest.TestCase):
    def test_all_nineteen_stars_have_an_exploration_and_five_questions(self):
        data = build.build([REPO], "zero-to-one")
        self.assertEqual(len(data["stars"]), 19)
        group_starts = [i for i, star in enumerate(data["stars"], 1) if star["id"] in data["groups"]]
        self.assertEqual(group_starts, [1, 4, 7, 11, 14, 17])
        for star in data["stars"]:
            with self.subTest(star=star["id"]):
                activities = star["activities"]
                self.assertEqual([a["kind"] for a in activities], ["simulation", "quiz"])
                self.assertTrue(all(a["targets"] == [star["id"]] for a in activities))
                self.assertEqual(len(activities[1]["body"]["items"]), 5)


class HomepageTrialBundle(unittest.TestCase):
    def test_named_stars_groups_and_activities_match_the_real_cards(self):
        data = build.build_trial_bundle([REPO], REPO / "prototype")
        formal = build.build_bundle([REPO])
        approved_nodes = {node["id"]: node for node in formal["nodes"]}
        trial_nodes = {node["id"]: node for node in data["nodes"]}
        catalog = data["catalog"]
        self.assertEqual(len(catalog), 23)
        self.assertFalse(approved_nodes.keys() & trial_nodes.keys())
        self.assertTrue(set(catalog) <= approved_nodes.keys() | trial_nodes.keys())
        self.assertTrue(trial_nodes.keys() <= set(catalog))
        self.assertFalse(formal["activities"].keys() & data["activities"].keys())

        math_stars = sorted((meta for meta in catalog.values() if meta["series"] == "zero-to-one"),
                            key=lambda meta: meta["star"])
        self.assertEqual([meta["star"] for meta in math_stars], list(range(1, 20)))
        groups = [meta for meta in math_stars if meta["group_order"] == 1]
        self.assertEqual([meta["star"] for meta in groups], [1, 4, 7, 11, 14, 17])
        self.assertEqual([meta["group"] for meta in groups], list(range(1, 7)))
        self.assertEqual([meta["group_title"] for meta in groups], list(build.ZERO_TO_ONE_GROUPS.values()))
        life = [nid for nid, meta in catalog.items() if meta["series"] == "life-manual"]
        self.assertEqual(len(life), 3)
        self.assertTrue(all(nid in approved_nodes and catalog[nid]["chart_theme"] == "life" for nid in life))
        chocolate = catalog["math.operation.distributive-law"]
        self.assertEqual((chocolate["series"], chocolate["series_title"]), ("chocolate", "乘法的秘密"))
        self.assertEqual(chocolate["group_title"], "掰巧克力")
        self.assertEqual(data["activities"]["act.simulation.chocolate-split-01"]["title"], "掰巧克力")

        for nid, node in trial_nodes.items():
            with self.subTest(nid=nid):
                card = yaml.safe_load(build.find_node([REPO], nid).read_text(encoding="utf-8"))
                self.assertEqual([node["theme"], node["grade"]], [card["theme"], card["grade"]])
                series = catalog[nid]["series"]
                allowed = dict(build.CONSTELLATIONS[series][1])[nid]
                self.assertEqual(node["activities"], [aid for aid in allowed if aid in card["activities"]])
                for aid in node["activities"]:
                    activity = data["activities"][aid]
                    self.assertIn(nid, activity["targets"])
                    if activity["kind"] == "simulation":
                        self.assertNotIn("html", activity)
                        self.assertEqual((REPO / "prototype" / activity["src"]).resolve(),
                                         REPO / "content/activities" / aid / "index.html")

    def test_unlisted_draft_or_extra_activity_on_a_named_card_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO / "content", root / "content")
            path = build.find_node([root], "math.operation.distributive-law")
            node = yaml.safe_load(path.read_text(encoding="utf-8"))
            node["activities"].append("act.simulation.not-in-trial")
            path.write_text(yaml.safe_dump(node), encoding="utf-8")
            node["id"] = "math.operation.extra"
            path.with_name(node["id"] + ".yaml").write_text(yaml.safe_dump(node), encoding="utf-8")
            # 若试玩清单扫描所有草稿或照搬卡上的额外活动，它会收进这两条或找不到活动。
            data = build.build_trial_bundle([root], root / "prototype")
            self.assertNotIn(node["id"], data["catalog"])
            self.assertNotIn(node["id"], [n["id"] for n in data["nodes"]])
            self.assertNotIn("act.simulation.not-in-trial", data["activities"])
            chocolate = next(n for n in data["nodes"] if n["id"] == "math.operation.distributive-law")
            self.assertEqual(chocolate["activities"], ["act.simulation.chocolate-split-01"])

    def test_promoted_math_star_uses_only_formal_approval_and_site_copies_only_trial_modules(self):
        nid, simulation, quiz = "math.fraction.unit-fraction", "act.simulation.fair-cut-01", "act.quiz.unit-fraction-01"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO / "content", root / "content")
            site = root / "site"
            build.build_trial_bundle([root], site, copy_modules=True)
            self.assertTrue((site / "trial-modules" / f"{simulation}.html").is_file())
            path = build.find_node([root], nid)
            node = yaml.safe_load(path.read_text(encoding="utf-8"))
            node["status"] = "published"
            path.write_text(yaml.safe_dump(node), encoding="utf-8")
            set_review(root, simulation, "pending")
            set_review(root, quiz, "approved")
            formal, _ = bundle(root)
            self.assertEqual(node_acts(formal, nid), [quiz])
            data = build.build_trial_bundle([root], site, copy_modules=True)
            self.assertIn(nid, data["catalog"])
            self.assertNotIn(nid, [n["id"] for n in data["nodes"]])
            self.assertNotIn(simulation, data["activities"])
            self.assertNotIn(quiz, data["activities"])
            # 第一个目录里还是旧草稿，第二个目录里已正式发布。正式包的同 ID 始终优先。
            merged = build.build_trial_bundle([REPO, root], site)
            self.assertNotIn(nid, [n["id"] for n in merged["nodes"]])
            self.assertNotIn(simulation, merged["activities"])
            sources = {a["src"] for a in data["activities"].values() if a["kind"] == "simulation"}
            self.assertEqual(sources, {f.relative_to(site).as_posix() for f in site.rglob("*.html")})
            for src in sources:
                path = site / src
                self.assertEqual(path.read_bytes(), (root / "content/activities" / path.stem / "index.html").read_bytes())


if __name__ == "__main__":
    unittest.main()
