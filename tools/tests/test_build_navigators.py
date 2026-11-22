"""领航员进发布包（docs/specs/navigators.md 第 2 节，#242 PR 1）。验收测试的作者写，实现者不改（受保护路径）。

期望值来自规格第 2 节：navigators 是可选的顶层键，每位 {id, version, files}，文件 {path, bytes, sha256}，
navigator.yaml 带 .yaml.json；进 content_hash；收录了领航员 engine_min 是 2；没有领航员目录时一切照旧；
只收 review: approved；至少一位 start: true，否则构建失败。
黄金样例 fixtures/expected/navigator-release.json 的哈希由测试作者按规格独立算出，不是被测代码的输出。
"""
import copy
import hashlib
import json
import shutil
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import build_release  # noqa: E402
from nav_fixtures import FACES, LAMP, RING, nav_files  # noqa: E402
from test_build_release import COMMIT, EXPECTED_ID, REPO, BuildCase  # noqa: E402

NAV_FIXTURE = HERE / "fixtures/navigators"
GOLDEN = HERE / "fixtures/expected/navigator-release.json"
SCHEMA = json.loads((REPO / "schemas/release.schema.json").read_text(encoding="utf-8"))
SIX = sorted(f + ".svg" for f in FACES)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class NavCase(BuildCase):
    def add_fixture_navigators(self):
        shutil.copytree(NAV_FIXTURE, self.content / "navigators")

    def add_nav(self, spec, **kw):
        for name, text in nav_files(**{**spec, **kw}).items():
            path = self.content / "navigators" / (kw.get("nid") or spec["nid"]) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")

    def nav_yaml(self, nid, function):
        self.change(f"navigators/{nid}/navigator.yaml", function)


class TestNavigatorsInRelease(NavCase):
    def test_two_navigators_match_independently_computed_golden(self):
        self.add_fixture_navigators()
        manifest = self.build()
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        actual = copy.deepcopy(manifest)
        del actual["source_commit"]
        self.assertEqual(actual, expected)

    def test_entry_shape_and_files(self):
        self.add_fixture_navigators()
        manifest = self.build()
        navs = manifest["navigators"]
        self.assertEqual([n["id"] for n in navs], ["nav.lamp", "nav.ring"], "按 id 排序")
        for n in navs:
            with self.subTest(nav=n["id"]):
                self.assertEqual(set(n), {"id", "version", "files"})
                self.assertEqual(n["version"], 1)
                base = f"content/navigators/{n['id']}/"
                self.assertEqual([f["path"] for f in n["files"]], sorted(base + x for x in ["navigator.yaml"] + SIX), "七个文件，按路径排序")
                for f in n["files"]:
                    data = (self.content / f["path"].removeprefix("content/")).read_bytes()
                    self.assertEqual(f["sha256"], sha(data))
                    self.assertEqual(f["bytes"], len(data))
                    if f["path"].endswith("navigator.yaml"):
                        side = (json.dumps(yaml.safe_load(data), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
                        self.assertEqual(f["json"], {"path": f["path"] + ".json", "sha256": sha(side), "bytes": len(side)})
                    else:
                        self.assertNotIn("json", f, "SVG 不带 .json")

    def test_navigators_are_inside_content_hash(self):
        self.add_fixture_navigators()
        m = self.build()
        body = {k: m[k] for k in ("engine_min", "contracts", "nodes", "activities", "assets", "navigators")}
        canon = lambda d: json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.assertEqual(m["content_hash"], sha(canon(body)))
        self.assertEqual(m["release_id"], "rel_" + m["content_hash"])
        without = {k: v for k, v in body.items() if k != "navigators"}
        self.assertNotEqual(m["content_hash"], sha(canon(without)), "去掉 navigators 哈希就变")

    def test_changing_one_svg_byte_changes_release_id(self):
        self.add_fixture_navigators()
        first = self.build()["release_id"]
        path = self.content / "navigators/nav.ring/clap.svg"
        path.write_text(path.read_text(encoding="utf-8").replace('r="3"', 'r="2"', 1), encoding="utf-8", newline="\n")
        self.assertNotEqual(self.build()["release_id"], first)

    def test_engine_min_is_2_with_navigators(self):
        self.add_fixture_navigators()
        self.assertEqual(self.build()["engine_min"], 2)

    def test_engine_min_is_2_even_when_nothing_else_is_published(self):
        self.change("nodes/num/math.number.fraction-intro.yaml", lambda node: node.update(status="draft"))
        self.add_fixture_navigators()
        manifest = self.build()
        self.assertEqual(manifest["nodes"], [])
        self.assertEqual(manifest["engine_min"], 2)
        self.assertEqual(len(manifest["navigators"]), 2)

    def test_manifest_validates_against_release_schema(self):
        self.add_fixture_navigators()
        errors = [e.message for e in Draft202012Validator(SCHEMA).iter_errors(self.build())]
        self.assertEqual(errors, [])

    def test_written_release_has_every_listed_file_including_yaml_json(self):
        self.add_fixture_navigators()
        out = self.temp / "out/release"
        code = build_release.main(["--content", str(self.content), "--out", str(out), "--commit", COMMIT])
        self.assertEqual(code, 0)
        manifest = json.loads((out / "release.json").read_text(encoding="utf-8"))
        for n in manifest["navigators"]:
            for f in n["files"]:
                self.assertEqual(sha((out / f["path"]).read_bytes()), f["sha256"])
                if "json" in f:
                    self.assertEqual(sha((out / f["json"]["path"]).read_bytes()), f["json"]["sha256"])
        self.assertTrue((out / "content/navigators/nav.lamp/navigator.yaml.json").is_file())


class TestWithoutNavigators(NavCase):
    def test_no_navigators_directory_means_no_key_engine_min_unchanged_release_id_unchanged(self):
        manifest = self.build()
        self.assertNotIn("navigators", manifest)
        self.assertEqual(manifest["engine_min"], 1)
        self.assertEqual(manifest["release_id"], EXPECTED_ID, "没有领航员：旧发布包的 id 一个字不变")

    def test_old_release_without_navigators_still_validates(self):
        errors = [e.message for e in Draft202012Validator(SCHEMA).iter_errors(self.build())]
        self.assertEqual(errors, [])


class TestGate(NavCase):
    def test_unapproved_navigator_is_not_included(self):
        for review in ("pending", "claude-reviewed"):
            with self.subTest(review=review):
                shutil.rmtree(self.content / "navigators", ignore_errors=True)
                self.add_fixture_navigators()
                self.nav_yaml("nav.ring", lambda d, r=review: d.update(review=r))
                manifest = self.build()
                self.assertEqual([n["id"] for n in manifest["navigators"]], ["nav.lamp"])
                self.assertEqual(manifest["engine_min"], 2)
                self.assertFalse([f for f in manifest["navigators"][0]["files"] if "nav.ring" in f["path"]])

    def test_no_approved_start_navigator_fails_the_build(self):
        self.add_fixture_navigators()
        self.nav_yaml("nav.lamp", lambda d: d.update(review="pending"))
        self.nav_yaml("nav.ring", lambda d: d.update(review="claude-reviewed"))
        self.assertBuildFails()

    def test_directory_present_but_no_navigator_start_fails(self):
        self.add_fixture_navigators()
        self.nav_yaml("nav.lamp", lambda d: d.update(unlock={"start": False}))
        self.nav_yaml("nav.ring", lambda d: d.update(unlock={"start": False}))
        self.assertBuildFails()

    def test_one_approved_start_is_enough(self):
        self.add_fixture_navigators()
        self.nav_yaml("nav.ring", lambda d: d.update(review="pending"))
        self.assertEqual(len(self.build()["navigators"]), 1)

    def test_listed_navigator_missing_a_face_fails_the_build(self):
        self.add_fixture_navigators()
        (self.content / "navigators/nav.lamp/wrong.svg").unlink()
        self.assertBuildFails()

    def test_order_of_creating_files_does_not_change_release_id(self):
        self.add_fixture_navigators()
        first = self.build()["release_id"]
        shutil.rmtree(self.content / "navigators")
        self.add_nav(RING)
        self.add_nav(LAMP)
        self.assertEqual(self.build()["release_id"], first)


if __name__ == "__main__":
    unittest.main()
