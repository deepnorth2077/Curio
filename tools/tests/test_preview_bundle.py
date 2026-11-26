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
TEST_FIGURE = "content/assets/biology.cell.cell-intro/preview-test.svg"
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


class PreviewBundleReviewGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(REPO / "content", self.tmp / "content")
        # 临时给第一道挑战题加图，单独核对未批准活动的配图是否随题目排除。
        figure = self.tmp / TEST_FIGURE
        figure.parent.mkdir(parents=True, exist_ok=True)
        figure.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>', encoding="utf-8")
        path = self.tmp / "content/activities" / QUIZ / "activity.yaml"
        quiz = yaml.safe_load(path.read_text(encoding="utf-8"))
        quiz["body"]["items"][0]["figure"] = {"type": "svg", "src": TEST_FIGURE}
        path.write_text(yaml.safe_dump(quiz, allow_unicode=True), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_simulation_station_count_for_resume(self):
        folder = self.tmp / "content/activities" / SIMULATION
        path = folder / "manifest.yaml"
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        for contract, count, expected in [
            ("activity/1.2", 7, 7), ("activity/1.1", 7, None),
            ("activity/1.2", 0, None), ("activity/1.2", True, None), ("activity/1.2", 257, None),
        ]:
            with self.subTest(contract=contract, count=count):
                manifest.update(contract=contract, station_count=count)
                path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
                activity = build.load_activity([self.tmp], SIMULATION, {})
                self.assertEqual(activity.get("station_count"), expected)

    def test_approved_activities_are_included(self):
        data, _ = bundle(self.tmp)
        for aid in (SIMULATION, QUIZ):
            self.assertIn(aid, data["activities"])
            self.assertIn(aid, node_acts(data, NODE))
        self.assertIn(TEST_FIGURE, data["figures"])

    def test_pending_data_activity_is_skipped_with_its_figures(self):
        set_review(self.tmp, QUIZ, "pending")
        data, log = bundle(self.tmp)
        self.assertNotIn(QUIZ, data["activities"])
        self.assertNotIn(QUIZ, node_acts(data, NODE))
        self.assertNotIn(TEST_FIGURE, data["figures"])
        self.assertIn(QUIZ, log)
        # 同一知识点下已批准的活动不受影响
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
        set_review(self.tmp, QUIZ, "pending")
        with contextlib.redirect_stdout(io.StringIO()):
            data = build.build([self.tmp])
        star = next(s for s in data["stars"] if s["id"] == NODE)
        self.assertIn(QUIZ, [a["id"] for a in star["activities"]])


class LifeConstellationPreview(unittest.TestCase):
    def test_life_cards_and_preview_offer_exploration_and_challenge(self):
        preview = build.build([REPO], "life-manual")
        formal = build.build_bundle([REPO])
        for star in preview["stars"]:
            with self.subTest(star=star["id"]):
                expected = ["simulation", "quiz"]
                if star["id"] == "biology.genetics.chromosome-intro":
                    expected.append("reflection")
                self.assertEqual([act["kind"] for act in star["activities"]], expected)
                self.assertEqual([act["id"] for act in star["activities"]], node_acts(formal, star["id"]))


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
        original = {"zero-to-one", "chocolate", "life-manual"}
        self.assertEqual(sum(meta["series"] in original for meta in catalog.values()), 23)
        self.assertEqual(data["diagram_series"], ["life-manual", "energy-dock", "newton-track"])
        for slug, starts in (("energy-dock", [1, 3, 5]), ("newton-track", [1, 3])):
            stars = sorted((v for v in catalog.values() if v["series"] == slug), key=lambda v: v["star"])
            self.assertEqual([v["star"] for v in stars], list(range(1, 2 * len(starts) + 1)))
            self.assertEqual([v["star"] for v in stars if v["group_order"] == 1], starts)
            self.assertTrue(all(v["chart_theme"] == "ene" for v in stars))
        self.assertNotIn("p.g10.newton", catalog)
        self.assertEqual(data["overviews"]["p.g10.newton"]["children"],
                         ["physics.motion.inertia", "physics.motion.force-acceleration", "physics.motion.action-reaction"])
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
        # 掰巧克力 2026-11-22 已正式发布（#54）：试玩包只留星图位置，活动由正式包给出
        self.assertIn("math.operation.distributive-law", approved_nodes)
        self.assertEqual(formal["activities"]["act.simulation.chocolate-split-01"]["title"], "掰巧克力")
        self.assertNotIn("act.simulation.chocolate-split-01", data["activities"])

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
            # 这颗星 2026-11-22 已正式发布（#54）。先在副本里退回试玩时的草稿
            node["status"] = "draft"
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
            path = build.find_node([root], nid)
            node = yaml.safe_load(path.read_text(encoding="utf-8"))
            # 这颗星 2026-11-22 已正式发布（#233）。先在副本里退回试玩时的草稿，再走一遍「转正」
            node["status"] = "draft"
            path.write_text(yaml.safe_dump(node), encoding="utf-8")
            set_review(root, simulation, "claude-reviewed")
            set_review(root, quiz, "claude-reviewed")
            build.build_trial_bundle([root], site, copy_modules=True)
            self.assertTrue((site / "trial-modules" / f"{simulation}.html").is_file())
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
            # 两个目录里同 ID 的星都已正式发布时，正式包的同 ID 始终优先，不进试玩包。
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
