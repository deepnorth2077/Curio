"""#193：用交付的课程文件和试玩构建入口验收。科学读数由独立审查者按 golden 的操作复测。"""
import json
from pathlib import Path
import unittest

import yaml
from jsonschema import Draft202012Validator

from test_preview_bundle import REPO, build

EXPECTED = json.loads((Path(__file__).parent / "fixtures/expected/energy-course.json").read_text(encoding="utf-8"))


class TestPhysicsCourses(unittest.TestCase):
    def read_doc(self, path, schema):
        self.assertTrue(path.is_file(), f"缺少 {path.relative_to(REPO)}")
        doc = yaml.safe_load(path.read_bytes())
        validator = Draft202012Validator(json.loads((REPO / f"schemas/{schema}.schema.json").read_bytes()))
        errors = [e.message for e in validator.iter_errors(doc)]
        self.assertEqual(errors, [], str(path))
        return doc

    def test_cards_open_their_own_simulation_and_five_questions(self):
        for course in EXPECTED.values():
            for spec in course:
                nid = spec["node"]
                short = spec["activity"]
                simulation = f"act.simulation.{short}-01"
                challenge = f"act.quiz.{short}-01"
                with self.subTest(node=nid, file="知识点卡"):
                    cards = list((REPO / "content/nodes").rglob(f"{nid}.yaml"))
                    self.assertEqual(len(cards), 1, nid)
                    card = self.read_doc(cards[0], "knode")
                    self.assertEqual(card["id"], nid)
                    self.assertEqual(card["theme"], "ene")
                    self.assertIn(simulation, card["activities"])
                    self.assertIn(challenge, card["activities"])
                with self.subTest(node=nid, file="实物"):
                    directory = REPO / "content/activities" / simulation
                    manifest = self.read_doc(directory / "manifest.yaml", "activity")
                    self.assertEqual(manifest["id"], simulation)
                    self.assertEqual(manifest["targets"], [nid])
                    self.assertEqual(manifest["type"], "simulation")
                    page = (directory / manifest["entry"]).read_text(encoding="utf-8")
                    self.assertIn("<script", page.lower())
                with self.subTest(node=nid, file="挑战"):
                    quiz = self.read_doc(REPO / "content/activities" / challenge / "activity.yaml", "activity-def")
                    self.assertEqual(quiz["id"], challenge)
                    self.assertEqual(quiz["targets"], [nid])
                    self.assertEqual(quiz["kind"], "quiz")
                    items = quiz["body"]["items"]
                    self.assertEqual(len(items), 5)
                    self.assertEqual(len({item["id"] for item in items}), 5)
                    for item in items:
                        answer = item["answer"]
                        if answer["type"] == "choice":
                            self.assertEqual(sum(c.get("correct") is True for c in answer["choices"]), 1, item["id"])

    def test_standalone_preview_opens_stars_in_course_order(self):
        for slug, course in EXPECTED.items():
            with self.subTest(series=slug):
                self.assertIn(slug, build.CONSTELLATIONS)
                stars = build.build([REPO], slug)["stars"]
                self.assertEqual([star["id"] for star in stars], [s["node"] for s in course])
                for spec, star in zip(course, stars):
                    short = spec["activity"]
                    activities = {a["id"]: a for a in star["activities"]}
                    self.assertTrue(activities[f"act.simulation.{short}-01"]["html"].strip())
                    self.assertEqual(len(activities[f"act.quiz.{short}-01"]["body"]["items"]), 5)

    def test_family_review_of_one_star_contains_only_its_activities(self):
        lever = build.build([REPO], "energy-dock", "physics.machine.lever")
        self.assertEqual([s["id"] for s in lever["stars"]], ["physics.machine.lever"])
        self.assertEqual([a["id"] for a in lever["stars"][0]["activities"]],
                         ["act.simulation.lever-dock-01", "act.quiz.lever-dock-01"])
        self.assertNotIn("groups", lever)
        with self.assertRaises(ValueError):
            build.build([REPO], "newton-track", "physics.machine.lever")

    def test_newton_overview_keeps_its_original_id(self):
        catalog = yaml.safe_load((REPO / "content/catalog/points.yaml").read_bytes())
        current = [p for p in catalog["points"] if p["id"] == "p.g10.newton"]
        self.assertEqual(len(current), 1)
        self.assertEqual((current[0]["grade"], current[0]["theme"]), ("G10", "ene"))
        self.assertFalse(any(p["id"] == "p.g10.newton" for p in catalog["retired"]))
