"""#188：目录迁移的原型快照、独立发布向量和 CI 正反用例。"""
import copy
import json
import shutil
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from test_build_release import BuildCase, COMMIT, REPO, build_release
from test_ci_checks import Repo, node

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "catalog/points.yaml"
CATALOG = "content/catalog/points.yaml"
CARD = "math.number.fraction-intro"
GOLDEN_RELEASE = json.loads((FIXTURES / "expected/catalog-release.json").read_text())


def sample():
    return yaml.safe_load(SAMPLE.read_bytes())


class TestInitialCatalog(unittest.TestCase):
    def test_catalog_covers_the_frozen_prototype(self):
        path = REPO / CATALOG
        self.assertTrue(path.is_file(), CATALOG)
        current = yaml.safe_load(path.read_bytes())
        # 基准取自 #184 首页自己的 NODES（已合并课程和前置）及 retired。
        # 首版逐字段对照。将来可以改名、增加星、撤下占位，原 ID、年级与主题仍须保留。
        golden = json.loads((FIXTURES / "expected/catalog-v1-from-prototype.json").read_text())
        identity = {r["id"]: (r["grade"], r["theme"]) for r in current["points"] + current["retired"]}
        for row in golden["points"] + golden["retired"]:
            with self.subTest(id=row[0]):
                self.assertEqual(identity.get(row[0]), tuple(row[2:4]))
        if current["version"] == 1:
            for group, last in (("points", "prerequisites"), ("retired", "replaced_by")):
                keys = ("id", "title", "grade", "theme", "unit", last)
                actual = [[item[k] for k in keys] for item in current[group]]
                self.assertCountEqual(actual, golden[group])

    def test_catalog_schema(self):
        path = REPO / "schemas/catalog.schema.json"
        self.assertTrue(path.is_file(), str(path))
        validator = Draft202012Validator(json.loads(path.read_text()))
        validator.validate(sample())
        for group, field, value in (
            ("root", "schema", "catalog/2"), ("root", "version", 0),
            ("points", "id", "一颗星"), ("points", "grade", "G13"),
            ("points", "theme", "missing"), ("points", "has_course", True),
            ("points", "prerequisites", "m.g1.count"), ("retired", "replaced_by", 7),
        ):
            with self.subTest(group=group, field=field):
                doc = sample()
                target = doc if group == "root" else doc[group][0]
                target[field] = value
                self.assertFalse(validator.is_valid(doc))
        for group, required in (("points", "prerequisites"), ("retired", "replaced_by")):
            doc = sample()
            del doc[group][0][required]
            self.assertFalse(validator.is_valid(doc), required)


class TestCatalogRelease(BuildCase):
    def setUp(self):
        super().setUp()
        self.path = self.temp / CATALOG
        self.path.parent.mkdir(parents=True)
        shutil.copyfile(SAMPLE, self.path)

    def test_manifest_files_and_hash_match_golden_vector(self):
        manifest, files = build_release.build_package(self.content, COMMIT)
        for field, expected in GOLDEN_RELEASE.items():
            self.assertEqual(manifest.get(field), expected, field)
        out = self.temp / "release"
        build_release.write_release(manifest, files, out)
        self.assertEqual((out / CATALOG).read_bytes(), SAMPLE.read_bytes())
        self.assertEqual(json.loads((out / (CATALOG + ".json")).read_bytes()), sample())
        changed = sample()
        changed["points"][0]["title"] = "数一数积木"
        self.save("catalog/points.yaml", changed)
        self.assertNotEqual(self.build()["release_id"], manifest["release_id"])

    def test_release_schema_accepts_only_the_optional_catalog_file_entry(self):
        old = json.loads((FIXTURES / "expected/fraction-release.json").read_text())
        old["source_commit"] = COMMIT
        schema = json.loads((REPO / "schemas/release.schema.json").read_text())
        validator = Draft202012Validator(schema)
        validator.validate(old)
        valid = dict(old, **GOLDEN_RELEASE)
        self.assertTrue(validator.is_valid(valid), "release/1 应接受目录条目")
        self.assertFalse(validator.is_valid(dict(valid, other=True)))
        for missing in ("path", "bytes", "sha256", "json"):
            bad = copy.deepcopy(valid)
            del bad["catalog"][missing]
            self.assertFalse(validator.is_valid(bad), missing)

    def test_invalid_catalog_is_not_released(self):
        invalid = sample()
        invalid["retired"][0]["replaced_by"] = "m.g1.count"  # 现行占位，没有卡
        self.save("catalog/points.yaml", invalid)
        with self.assertRaises(build_release.BuildError):
            self.build()


class TestCatalogCi(unittest.TestCase):
    def check(self, updated, previous=None, extra_card=None):
        repo = Repo()
        self.addCleanup(repo.close)
        node_path = "content/nodes/num/"
        repo.write(node_path + CARD + ".yaml", node(CARD))  # draft 也有卡
        if previous is not None:
            repo.write(CATALOG, yaml.safe_dump(previous, allow_unicode=True))
        repo.baseline()
        repo.branch("arch/catalog")
        if updated is None:
            repo.delete(CATALOG)
        else:
            repo.write(CATALOG, yaml.safe_dump(updated, allow_unicode=True))
        if extra_card:
            repo.write(node_path + extra_card + ".yaml", node(extra_card))
        repo.commit()
        return repo.check().errors

    def test_initial_import_and_retirement_pass(self):
        self.assertEqual(self.check(sample()), [])
        before = sample()
        old = before["retired"].pop()
        del old["replaced_by"]
        before["points"].append(dict(old, prerequisites=[]))
        after = sample()
        after["version"] = 2
        after["points"][0]["title"] = "新的名字"
        self.assertEqual(self.check(after, previous=before), [])

    def test_ids_and_references(self):
        changes = (
            ("现行 ID 重复", lambda d: d["points"].append(d["points"][0])),
            ("旧 ID 重复", lambda d: d["retired"].append(d["retired"][0])),
            ("两表重名", lambda d: d["retired"][0].update(id="m.g1.count")),
            ("没有该前置", lambda d: d["points"][0].update(prerequisites=["m.g9.missing"])),
            ("已撤下的前置", lambda d: d["points"][0].update(prerequisites=["m.g3.old"])),
            ("接替者缺失", lambda d: d["retired"][0].update(replaced_by="m.g9.missing")),
            ("接替者只有占位", lambda d: d["retired"][0].update(replaced_by="m.g1.count")),
            ("卡的主题不同", lambda d: d["points"][1].update(theme="rel")),
            ("卡的年级不同", lambda d: d["points"][1].update(grade="G4")),
            ("目录不合 schema", lambda d: d["points"][0].update(grade="G13")),
        )
        for reason, change in changes:
            with self.subTest(reason=reason):
                doc = sample()
                change(doc)
                self.assertTrue(self.check(doc), reason)
        self.assertTrue(self.check(sample(), extra_card="math.number.missing"), "草案卡漏登")

    def test_main_ids_are_permanent(self):
        before = sample()
        for group in ("points", "retired"):
            for change in ("remove", "grade", "theme"):
                with self.subTest(group=group, change=change):
                    after = sample()
                    after["version"] = 2
                    if change == "remove":
                        after[group].pop(0)
                        # 消除悬空的前置，单独验证主线上已存在的 ID 不得消失。
                        after["points"][-1]["prerequisites"] = []
                    else:
                        after[group][0][change] = "G2" if change == "grade" else "rel"
                    self.assertTrue(self.check(after, previous=before))
        self.assertTrue(self.check(None, previous=before), "不能删除整个已登记目录")

    def test_changed_catalog_requires_version_bump(self):
        changed = sample()
        changed["points"][0]["title"] = "数积木"
        self.assertTrue(self.check(changed, previous=sample()))
