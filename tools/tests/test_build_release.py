"""tools/build_release.py 的行为测试。只通过公开构建接口和命令行观察结果。"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
FIXTURE = TOOLS / "tests/fixtures/content"
EXPECTED = TOOLS / "tests/fixtures/expected/fraction-release.json"
sys.path.insert(0, str(TOOLS))
import build_release  # noqa: E402

COMMIT = "0000000000000000000000000000000000000000"
EXPECTED_ID = "rel_b12263a7dba6595337ca156c88d0b1a3d313edf2e00a672b66ee32f1269b94fe"
NODE_ID = "math.number.fraction-intro"
NODE_PATH = "nodes/num/math.number.fraction-intro.yaml"
EXPLAIN_PATH = "activities/act.explain.fraction-intro-01/activity.yaml"
QUIZ_PATH = "activities/act.quiz.fraction-intro-01/activity.yaml"


def draft_node(node_id):
    return {
        "id": node_id,
        "schema": "knode/1",
        "title": "草稿知识点",
        "subjects": ["math"],
        "theme": "num",
        "grade": "G3",
        "prerequisites": [],
        "activities": [],
        "status": "draft",
        "version": 1,
    }


class BuildCase(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="curio-build-"))
        self.content = self.temp / "content"
        shutil.copytree(FIXTURE, self.content)

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def load(self, relative):
        return yaml.safe_load((self.content / relative).read_text(encoding="utf-8"))

    def save(self, relative, document):
        path = self.content / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )

    def change(self, relative, function):
        document = self.load(relative)
        function(document)
        self.save(relative, document)

    def build(self):
        return build_release.build(self.content, COMMIT)

    def assertBuildFails(self, *texts):
        with self.assertRaises(build_release.BuildError) as caught:
            self.build()
        message = str(caught.exception)
        for text in texts:
            self.assertIn(text, message)
        return message


class TestImmutableRelease(BuildCase):
    def test_fraction_fixture_matches_independently_written_expected_manifest(self):
        manifest = self.build()
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
        actual = copy.deepcopy(manifest)
        del actual["source_commit"]
        self.assertEqual(actual, expected)
        self.assertEqual(manifest["source_commit"], COMMIT)

    def test_same_content_and_another_directory_have_same_release_id(self):
        first = self.build()
        second = self.build()
        other = self.temp / "another-place/content"
        other.parent.mkdir()
        shutil.copytree(self.content, other)
        third = build_release.build(other, "1111111111111111111111111111111111111111")
        self.assertEqual(first, second)
        self.assertEqual(first["release_id"], EXPECTED_ID)
        self.assertEqual(third["release_id"], EXPECTED_ID)

    def test_draft_node_and_its_activities_are_not_included(self):
        self.change(NODE_PATH, lambda node: node.update(status="draft"))
        manifest = self.build()
        self.assertEqual(manifest["nodes"], [])
        self.assertEqual(manifest["activities"], [])
        self.assertEqual(manifest["assets"], [])
        self.assertEqual(manifest["contracts"], [])
        self.assertEqual(manifest["engine_min"], 1)

    def test_pending_quiz_is_excluded_then_missing_quiz_blocks_release(self):
        self.change(QUIZ_PATH, lambda activity: activity.update(review="pending"))
        self.assertBuildFails("quiz", "至少有一个")

    def test_unapproved_reflection_is_excluded_from_successful_release(self):
        reflection_path = "activities/act.reflection.fraction-intro-01/activity.yaml"
        expected_ids = ["act.explain.fraction-intro-01", "act.quiz.fraction-intro-01"]
        for review in ("pending", "claude-reviewed"):
            with self.subTest(review=review):
                self.change(reflection_path, lambda activity: activity.update(review=review))
                manifest = self.build()
                self.assertEqual([activity["id"] for activity in manifest["activities"]], expected_ids)

    def test_draft_prerequisite_breaks_reference_closure(self):
        prerequisite = "math.number.equal-parts"
        self.change(NODE_PATH, lambda node: node["prerequisites"].append(prerequisite))
        self.save(f"nodes/num/{prerequisite}.yaml", draft_node(prerequisite))
        self.assertBuildFails(prerequisite, "引用闭包")

    def test_approved_shared_activity_with_draft_target_breaks_closure(self):
        draft = "math.number.draft-target"
        self.save(f"nodes/num/{draft}.yaml", draft_node(draft))
        self.change(EXPLAIN_PATH, lambda activity: activity["targets"].append(draft))
        self.assertBuildFails("act.explain.fraction-intro-01", draft)

    def test_cr_byte_reports_the_content_path(self):
        path = self.content / QUIZ_PATH
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertBuildFails("content/" + QUIZ_PATH, "CR")

    @unittest.skipIf(os.name == "nt", "Windows 默认文件系统不能同时创建只差大小写的路径")
    def test_case_only_path_collision_fails(self):
        asset = self.content / "assets/a"
        asset.mkdir(parents=True)
        (asset / "Fig.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8")
        (asset / "fig.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8")
        self.assertBuildFails("只差大小写")

    def test_non_ascii_path_fails_before_collection(self):
        (self.content / "assets").mkdir()
        (self.content / "assets/图.svg").write_text("<svg/>\n", encoding="utf-8")
        self.assertBuildFails("content/assets/图.svg", "路径")

    def test_unreferenced_files_and_fixture_root_json_are_not_collected(self):
        (self.content / "assets").mkdir()
        (self.content / "assets/unused.svg").write_text("<svg/>\n", encoding="utf-8", newline="\n")
        manifest = self.build()
        self.assertEqual(manifest["assets"], [])
        all_paths = [entry["path"] for entry in manifest["assets"]]
        all_paths += [file["path"] for activity in manifest["activities"] for file in activity["files"]]
        self.assertFalse(any(path.endswith("release.json") or path.endswith("experiment-manifest.json") for path in all_paths))

    def test_referenced_svg_and_engine_maximum_enter_manifest(self):
        svg = "<svg xmlns=\"http://www.w3.org/2000/svg\"><title>圆</title></svg>\n"
        (self.content / "assets/fraction").mkdir(parents=True)
        (self.content / "assets/fraction/pie.svg").write_text(svg, encoding="utf-8", newline="\n")

        def add_figure(activity):
            activity["engine"] = 3
            activity["body"]["steps"].append({
                "type": "figure",
                "figure": {"type": "svg", "src": "content/assets/fraction/pie.svg"},
                "caption": "观察这张图。",
            })

        self.change(EXPLAIN_PATH, add_figure)
        manifest = self.build()
        self.assertEqual(manifest["engine_min"], 3)
        self.assertEqual([entry["path"] for entry in manifest["assets"]], ["content/assets/fraction/pie.svg"])
        self.assertEqual(manifest["assets"][0]["bytes"], len(svg.encode("utf-8")))

    def test_approved_custom_experiment_supplies_kind_files_and_contract(self):
        activity_id = "act.experiment.fraction-folding-01"
        node = self.load(NODE_PATH)
        node["activities"].append(activity_id)
        self.save(NODE_PATH, node)
        manifest_document = {
            "id": activity_id,
            "contract": "activity/1.1",
            "type": "experiment",
            "version": 2,
            "title": "折纸实验",
            "targets": [NODE_ID],
            "age_band": "G3-4",
            "entry": "index.html",
            "pedagogy": "hint-ladder",
            "emits": ["started"],
            "review": "approved",
            "misconceptions": [],
        }
        self.save(f"activities/{activity_id}/manifest.yaml", manifest_document)
        (self.content / f"activities/{activity_id}/index.html").write_text("<!doctype html><p>折纸</p>\n", encoding="utf-8", newline="\n")
        manifest = self.build()
        entry = next(activity for activity in manifest["activities"] if activity["id"] == activity_id)
        self.assertEqual(entry["kind"], "experiment")
        self.assertEqual(entry["version"], 2)
        self.assertEqual([file["path"] for file in entry["files"]], [
            f"content/activities/{activity_id}/index.html",
            f"content/activities/{activity_id}/manifest.yaml",
        ])
        self.assertEqual(manifest["contracts"], ["activity/1.1"])

    def test_write_release_copies_exact_bytes_and_manifest(self):
        manifest = self.build()
        out = self.temp / "out"
        build_release.write_release(manifest, self.content, out)
        written = json.loads((out / "release.json").read_text(encoding="utf-8"))
        self.assertEqual(written, manifest)
        for node in manifest["nodes"]:
            relative = node["path"].removeprefix("content/")
            self.assertEqual((out / node["path"]).read_bytes(), (self.content / relative).read_bytes())
        for activity in manifest["activities"]:
            for entry in activity["files"]:
                relative = entry["path"].removeprefix("content/")
                self.assertEqual((out / entry["path"]).read_bytes(), (self.content / relative).read_bytes())


class TestJsonSidecar(BuildCase):
    """内容规格 6.3：每个 YAML 旁边多写一份同名 .json，不进清单、不参与哈希。"""

    def written(self):
        manifest = self.build()
        out = self.temp / "out"
        build_release.write_release(manifest, self.content, out)
        return manifest, out

    def test_every_yaml_gets_sorted_compact_json_and_nothing_else_does(self):
        manifest, out = self.written()
        yamls = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.yaml"))
        jsons = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.json") if p.name != "release.json")
        self.assertEqual(jsons, [y + ".json" for y in yamls])
        self.assertEqual(len(yamls), 4)  # 1 个知识点 + 讲解、挑战、反思
        for y in yamls:
            sidecar = (out / (y + ".json")).read_bytes()
            self.assertTrue(sidecar.endswith(b"}\n") and not sidecar.endswith(b"\n\n"))
            self.assertNotIn(b": ", sidecar[:200])
            self.assertEqual(json.loads(sidecar), yaml.safe_load((out / y).read_text(encoding="utf-8")))

    def test_quiz_sidecar_starts_with_hand_written_bytes(self):
        _, out = self.written()
        data = (out / "content" / QUIZ_PATH.replace("activity.yaml", "activity.yaml.json")).read_bytes()
        # 手写的期望：键按字母排序，中文不转义
        self.assertTrue(data.startswith('{"age_band":"G3-4","body":{"items":[{"answer":{"choices":[{"correct":true,"id":"a","text":"1/4"}'.encode("utf-8")), data[:120])

    def test_sidecars_do_not_change_manifest_or_release_id(self):
        manifest, out = self.written()
        self.assertEqual(manifest["release_id"], EXPECTED_ID)
        listed = {f["path"] for a in manifest["activities"] for f in a["files"]} | {n["path"] for n in manifest["nodes"]}
        self.assertFalse(any(path.endswith(".json") for path in listed))

    def test_unquoted_date_fails_the_build_with_path(self):
        path = self.content / NODE_PATH
        path.write_text(path.read_text(encoding="utf-8").replace("unit: 三上 · 分数的初步认识", "unit: 2026-11-07"), encoding="utf-8", newline="\n")
        message = self.assertBuildFails("content/" + NODE_PATH, "不能转成 JSON")
        self.assertIn("unit", message)

    def test_values_json_cannot_hold_are_rejected(self):
        for text, word in [("a: .inf\n", "无穷大"), ("a: .nan\n", "NaN"), ("1: x\n", "不是字符串"), ("a: 9007199254740992\n", "2^53"), ("a: 2026-01-01\n", "日期")]:
            with self.subTest(text=text):
                with self.assertRaises(build_release.BuildError) as caught:
                    build_release.json_sidecar(text.encode("utf-8"), "content/x.yaml")
                self.assertIn(word, str(caught.exception))

    def test_largest_safe_integer_and_quoted_date_are_accepted(self):
        data = build_release.json_sidecar("b: '2026-01-01'\na: 9007199254740991\n".encode("utf-8"), "content/x.yaml")
        self.assertEqual(data, b'{"a":9007199254740991,"b":"2026-01-01"}\n')


class TestCommandLine(BuildCase):
    def test_cli_writes_package_and_prints_expected_id(self):
        out = self.temp / "cli-out"
        process = subprocess.run([
            sys.executable, str(TOOLS / "build_release.py"),
            "--content", str(self.content), "--out", str(out), "--commit", COMMIT,
        ], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.strip(), EXPECTED_ID)
        self.assertTrue((out / "release.json").is_file())

    def test_cli_build_error_exits_one(self):
        self.change(NODE_PATH, lambda node: node.update(status="published", activities=[]))
        process = subprocess.run([
            sys.executable, str(TOOLS / "build_release.py"),
            "--content", str(self.content), "--out", str(self.temp / "bad-out"), "--commit", COMMIT,
        ], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 1)
        self.assertIn("构建失败", process.stderr)

    def test_cli_missing_required_argument_exits_two(self):
        process = subprocess.run([
            sys.executable, str(TOOLS / "build_release.py"), "--content", str(self.content),
        ], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 2)


if __name__ == "__main__":
    unittest.main()
# END OF FILE
