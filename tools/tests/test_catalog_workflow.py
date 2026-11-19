"""#188：从原型导出、发布和试玩预览，以及旧占位的生命周期。"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

import test_catalog as catalog_tests
from test_ci_checks import Repo, node
from test_preview_bundle import REPO, build


class TestExportCatalog(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "prototype").mkdir()
        self.prototype = self.root / "prototype/index.html"
        self.card_dir = self.root / "content/nodes/num"
        self.card_dir.mkdir(parents=True)
        self.card = self.card_dir / (catalog_tests.CARD + ".yaml")
        self.card.write_text(node(catalog_tests.CARD), encoding="utf-8")
        self.source = """const RAW=[
 ["m.g1.count","数一数","G1","num","一上"],
 ["m.g3.old","旧分数星","G3","num","三上"],
 ["m.g4.compare","比较分数","G4","num","四上",["m.g3.old"]]
];
const replacements=[
 {old:"m.g3.old",to:"math.number.fraction-intro"}
];
"""
        self.prototype.write_text(self.source, encoding="utf-8")
        self.output = self.root / "out/points.yaml"

    def export(self):
        return subprocess.run(
            [sys.executable, str(REPO / "tools/export_catalog.py"),
             "--root", str(self.root), "--out", str(self.output)],
            capture_output=True, text=True, encoding="utf-8",
        )

    def read_export(self):
        result = self.export()
        self.assertEqual(result.returncode, 0, result.stderr)
        return yaml.safe_load(self.output.read_bytes())

    def test_export_uses_current_prototype_and_cards(self):
        first = self.read_export()
        points = {row["id"]: row for row in first["points"]}
        self.assertEqual(set(points), {"m.g1.count", "m.g4.compare", catalog_tests.CARD})
        self.assertEqual(points["m.g4.compare"]["prerequisites"], [catalog_tests.CARD])
        self.assertEqual(first["retired"], [{
            "id": "m.g3.old", "title": "旧分数星", "grade": "G3", "theme": "num",
            "unit": "三上", "replaced_by": catalog_tests.CARD,
        }])

        original = self.output.read_bytes()
        self.assertEqual(self.read_export(), first)
        self.assertEqual(self.output.read_bytes(), original)
        self.prototype.write_text(self.source.replace("数一数", "一起数一数"), encoding="utf-8")
        card = yaml.safe_load(self.card.read_bytes())
        card["title"] = "分数新标题"
        self.card.write_text(yaml.safe_dump(card, allow_unicode=True), encoding="utf-8")
        self.assertNotEqual(self.export().returncode, 0)
        self.assertEqual(self.output.read_bytes(), original, "一次性导出不能覆盖已经维护的目录")
        self.output.unlink()
        updated = {row["id"]: row for row in self.read_export()["points"]}
        self.assertEqual(updated["m.g1.count"]["title"], "一起数一数")
        self.assertEqual(updated[catalog_tests.CARD]["title"], "分数新标题")

    def test_duplicate_id_and_missing_target_prevent_export(self):
        for broken in (self.source.replace("m.g4.compare", "m.g1.count"),
                       self.source.replace('to:"math.number.fraction-intro"', 'to:"m.g1.count"')):
            with self.subTest(source=broken):
                self.prototype.write_text(broken, encoding="utf-8")
                self.assertNotEqual(self.export().returncode, 0)
                self.assertFalse(self.output.exists())


class TestCatalogPreview(unittest.TestCase):
    def test_optional_formal_catalog_keeps_trial_series_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO / "content", root / "content", ignore=shutil.ignore_patterns("catalog"))
            old_formal = build.build_bundle([root])
            old_trial = build.build_trial_bundle([root], root)
            self.assertNotIn("catalog", old_formal)
            path = root / catalog_tests.CATALOG
            path.parent.mkdir()
            shutil.copyfile(REPO / catalog_tests.CATALOG, path)
            formal = build.build_bundle([root])
            self.assertEqual(formal.pop("catalog"), yaml.safe_load(path.read_bytes()))
            self.assertEqual(formal, old_formal)
            trial = build.build_trial_bundle([root], root)
            self.assertEqual(trial["catalog"], old_trial["catalog"])
            self.assertEqual(trial["catalog"]["math.fraction.unit-fraction"]["series"], "zero-to-one")


class TestRetiredCatalogId(unittest.TestCase):
    def test_a_retired_id_cannot_become_a_new_point(self):
        repo = Repo()
        self.addCleanup(repo.close)
        repo.write("content/nodes/num/" + catalog_tests.CARD + ".yaml", node(catalog_tests.CARD))
        doc = catalog_tests.sample()
        repo.write(catalog_tests.CATALOG, yaml.safe_dump(doc, allow_unicode=True))
        repo.baseline()
        repo.branch("arch/reuse-id")
        old = doc["retired"].pop()
        del old["replaced_by"]
        old["prerequisites"] = []
        doc["points"].append(old)
        doc["version"] += 1
        repo.write(catalog_tests.CATALOG, yaml.safe_dump(doc, allow_unicode=True))
        repo.commit()
        self.assertTrue(repo.check().errors)


class TestKnowledgePointCatalogBranch(unittest.TestCase):
    def check_branch(self, nid, before, after):
        repo = Repo()
        self.addCleanup(repo.close)
        repo.write("content/nodes/num/" + catalog_tests.CARD + ".yaml", node(catalog_tests.CARD))
        repo.write(catalog_tests.CATALOG, yaml.safe_dump(before, allow_unicode=True))
        repo.baseline()
        repo.branch("kp/" + nid)
        repo.write("content/nodes/num/" + nid + ".yaml", node(nid))
        repo.write(catalog_tests.CATALOG, yaml.safe_dump(after, allow_unicode=True))
        repo.commit()
        return repo.check().errors

    def test_new_card_can_register_its_own_point(self):
        before = catalog_tests.sample()
        after = catalog_tests.sample()
        nid = "math.number.thirds"
        after["points"].append(dict(id=nid, title="三等份", grade="G3", theme="num",
                                    unit="三上", prerequisites=[catalog_tests.CARD]))
        after["version"] += 1
        self.assertEqual(self.check_branch(nid, before, after), [])

    def test_existing_card_can_update_its_own_directory_entry(self):
        before = catalog_tests.sample()
        after = catalog_tests.sample()
        after["points"][1]["title"] = "分数和图"
        after["version"] += 1
        self.assertEqual(self.check_branch(catalog_tests.CARD, before, after), [])

    def test_other_rows_and_version_only_changes_stay_protected(self):
        for group in ("points", "retired", "version_only"):
            with self.subTest(group=group):
                before = catalog_tests.sample()
                after = catalog_tests.sample()
                after["version"] += 1
                if group != "version_only":
                    after["points"][1]["title"] = "分数和图"
                    after[group][0]["title"] = "夹带修改"
                errors = self.check_branch(catalog_tests.CARD, before, after)
                self.assertTrue(any(path == catalog_tests.CATALOG for path, _ in errors), errors)

    def test_card_on_its_own_branch_preserves_the_registered_grade(self):
        before = catalog_tests.sample()
        after = catalog_tests.sample()
        # 新卡与新目录都是 G3，但这个占位进 main 时属于 G1。
        after["points"][0]["grade"] = "G3"
        after["version"] += 1
        errors = self.check_branch("m.g1.count", before, after)
        self.assertTrue(any("m.g1.count" in message and "年级" in message
                            for _, message in errors), errors)
