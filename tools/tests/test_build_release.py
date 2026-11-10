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

import hashlib

import yaml
from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
FIXTURE = TOOLS / "tests/fixtures/content"
EXPECTED = TOOLS / "tests/fixtures/expected/fraction-release.json"
sys.path.insert(0, str(TOOLS))
import build_release  # noqa: E402

COMMIT = "0000000000000000000000000000000000000000"
EXPECTED_ID = "rel_efb556635ad02d686802bc3e2bf4a3faefe6219204f49eb629579651064a9554"
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
        manifest, files = build_release.build_package(self.content, COMMIT)
        out = self.temp / "out"
        build_release.write_release(manifest, files, out)
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
    """内容规格 6.3：每个 YAML 旁边多写一份同名 .json，清单登记它的哈希，参与 content_hash。"""

    def written(self):
        manifest, files = build_release.build_package(self.content, COMMIT)
        out = self.temp / "out"
        build_release.write_release(manifest, files, out)
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

    def test_every_yaml_entry_binds_the_json_the_browser_reads(self):
        manifest, out = self.written()
        self.assertEqual(manifest["release_id"], EXPECTED_ID)
        entries = list(manifest["nodes"]) + [f for a in manifest["activities"] for f in a["files"]]
        self.assertEqual(len(entries), 4)
        for entry in entries:
            data = (out / entry["json"]["path"]).read_bytes()
            self.assertEqual(entry["json"]["path"], entry["path"] + ".json")
            self.assertEqual(entry["json"]["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(entry["json"]["bytes"], len(data))

    def test_written_release_matches_the_release_schema(self):
        manifest, _ = self.written()
        schema = json.loads((REPO / "schemas/release.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(manifest)
        broken = copy.deepcopy(manifest)
        del broken["activities"][0]["files"][0]["json"]
        self.assertFalse(Draft202012Validator(schema).is_valid(broken))


NODE_CANONICAL = r"""
// 浏览器外壳核对清单的写法（切片规格 6.3 第 2 步），在 Node 里跑：递归排序对象键，数组保持顺序，不留空白。
const fs = require("fs"), crypto = require("crypto");
const m = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const canon = v => Array.isArray(v) ? "[" + v.map(canon).join(",") + "]"
  : v && typeof v === "object" ? "{" + Object.keys(v).sort().map(k => JSON.stringify(k) + ":" + canon(v[k])).join(",") + "}"
  : JSON.stringify(v);
const input = {engine_min: m.engine_min, contracts: m.contracts, nodes: m.nodes, activities: m.activities, assets: m.assets};
const hash = crypto.createHash("sha256").update(Buffer.from(canon(input), "utf8")).digest("hex");
process.stdout.write(hash === m.content_hash && m.release_id === "rel_" + hash ? "ok" : "mismatch " + hash);
"""


class TestManifestIntegers(BuildCase):
    """第 2 轮审阅第 1 条：清单里的整数一律写成整数，Python 和浏览器算出同一个 content_hash。"""

    def test_float_version_with_integer_value_is_written_as_integer(self):
        self.change(QUIZ_PATH, lambda act: act.update(version=1.0, engine=1.0))
        text = (self.content / QUIZ_PATH).read_text(encoding="utf-8")
        self.assertIn("version: 1.0", text)
        manifest = self.build()
        quiz = [a for a in manifest["activities"] if a["id"] == "act.quiz.fraction-intro-01"][0]
        self.assertIs(type(quiz["version"]), int)
        self.assertIs(type(manifest["engine_min"]), int)
        canonical = json.dumps({k: manifest[k] for k in ("engine_min", "contracts", "nodes", "activities", "assets")},
                               sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertNotIn('"version":1.0', canonical)

    def test_non_integer_or_out_of_range_versions_fail(self):
        for bad, word in [(1.5, "必须是整数"), (True, "必须是整数"), (0, "1～2^53−1"), (9007199254740992, "2^53")]:
            with self.subTest(version=bad):
                self.change(QUIZ_PATH, lambda act: act.update(version=bad))
                with self.assertRaises(build_release.BuildError) as caught:
                    self.build()
                self.assertIn(word, str(caught.exception))
                shutil.rmtree(self.content)
                shutil.copytree(FIXTURE, self.content)

    @unittest.skipUnless(shutil.which("node"), "需要 Node.js 才能核对浏览器的写法")
    def test_browser_canonical_json_reproduces_the_release_id(self):
        """Python 构建、JavaScript 核对：含 version: 1.0、非 ASCII 内容、嵌套的 json 条目。"""
        script = self.temp / "canon.js"
        script.write_text(NODE_CANONICAL, encoding="utf-8")
        for name in ("fixture", "float-version"):
            if name == "float-version":
                self.change(QUIZ_PATH, lambda act: act.update(version=1.0))
            with self.subTest(case=name):
                manifest, files = build_release.build_package(self.content, COMMIT)
                out = self.temp / ("out-" + name)
                build_release.write_release(manifest, files, out)
                process = subprocess.run(["node", str(script), str(out / "release.json")], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(process.stdout, "ok", process.stderr)
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
        fixture = self.temp / "expected.json"
        fixture.write_text(json.dumps(dict(expected, source_commit=COMMIT), ensure_ascii=False), encoding="utf-8")
        process = subprocess.run(["node", str(script), str(fixture)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.stdout, "ok", "手写的期望清单在浏览器写法下也要对得上")


class TestSlice1aFixture(unittest.TestCase):
    """切片规格第 7、8 节：1a 的演示夹具能构建，挑战是五道选择题、固定题序。"""

    def test_fixture_builds_with_five_choice_items_in_fixed_order(self):
        root = TOOLS / "tests/fixtures/slice-1a/content"
        manifest = build_release.build(root, COMMIT)
        self.assertEqual([a["id"] for a in manifest["activities"]], ["act.explain.fraction-intro-01", "act.quiz.fraction-intro-01"])
        quiz = yaml.safe_load((root / QUIZ_PATH).read_text(encoding="utf-8"))
        self.assertIs(quiz["body"]["shuffle"], False)
        items = quiz["body"]["items"]
        self.assertEqual(len(items), 5)
        self.assertTrue(all(item["answer"]["type"] == "choice" for item in items))
        positions = [next(i for i, c in enumerate(item["answer"]["choices"]) if c.get("correct")) for item in items]
        self.assertTrue(all(sum(1 for c in item["answer"]["choices"] if c.get("correct")) == 1 for item in items))
        self.assertGreater(len(set(positions)), 1, "正确选项的位置要分散")


class TestSlice1bFixture(unittest.TestCase):
    """切片规格 6.4：1b 的演示夹具能构建；挑战是 version 2，有数字题、分数题，每道题 1～3 条提示且不泄露答案。"""

    def test_fixture_builds_with_number_fraction_and_hints(self):
        import ci_checks
        root = TOOLS / "tests/fixtures/slice-1b/content"
        manifest = build_release.build(root, COMMIT)
        self.assertEqual([a["id"] for a in manifest["activities"]], ["act.explain.fraction-intro-01", "act.quiz.fraction-intro-01"])
        quiz = yaml.safe_load((root / QUIZ_PATH).read_text(encoding="utf-8"))
        self.assertEqual(quiz["version"], 2)
        self.assertIs(quiz["body"]["shuffle"], False)
        items = quiz["body"]["items"]
        self.assertEqual(len(items), 5)
        self.assertEqual(sorted(item["answer"]["type"] for item in items), ["choice", "choice", "choice", "fraction", "number"])
        for item in items:
            self.assertTrue(1 <= len(item.get("hints", [])) <= 3, item["id"])
            self.assertEqual(list(ci_checks.hint_leaks(item)), [], item["id"])

    def test_leaky_hint_would_be_caught(self):
        import ci_checks
        item = {"id": "q", "answer": {"type": "number", "value": 6}, "hints": ["看看 1/6 横线下面写的是几。"]}
        self.assertNotEqual(list(ci_checks.hint_leaks(item)), [])


class TestWriteFromSnapshot(BuildCase):
    """第 2 轮审阅第 4 条：写出只用构建时的字节快照，先写临时目录，全部核对通过再改名。"""

    def leftovers(self):
        return sorted(p.name for p in self.temp.iterdir() if ".tmp-" in p.name)

    def test_source_edited_after_build_does_not_leak_into_package(self):
        manifest, files = build_release.build_package(self.content, COMMIT)
        original = (self.content / NODE_PATH).read_bytes()
        self.change(NODE_PATH, lambda node: node.update(title="构建以后才改的标题"))
        out = self.temp / "out"
        build_release.write_release(manifest, files, out)
        self.assertEqual((out / "content" / NODE_PATH).read_bytes(), original)
        self.assertNotIn("构建以后才改的标题", (out / "content" / (NODE_PATH + ".json")).read_text(encoding="utf-8"))

    def test_bytes_that_do_not_match_the_manifest_are_refused(self):
        manifest, files = build_release.build_package(self.content, COMMIT)
        files["content/" + QUIZ_PATH + ".json"] += b" "
        out = self.temp / "out"
        with self.assertRaises(build_release.BuildError) as caught:
            build_release.write_release(manifest, files, out)
        self.assertIn(QUIZ_PATH, str(caught.exception))
        self.assertFalse(out.exists())
        self.assertEqual(self.leftovers(), [])

    def test_missing_or_extra_files_are_refused(self):
        manifest, files = build_release.build_package(self.content, COMMIT)
        for change in ("missing", "extra"):
            with self.subTest(change=change):
                broken = dict(files)
                if change == "missing":
                    del broken["content/" + NODE_PATH + ".json"]
                else:
                    broken["content/extra.txt"] = b"x"
                with self.assertRaises(build_release.BuildError):
                    build_release.write_release(manifest, broken, self.temp / "out")
                self.assertFalse((self.temp / "out").exists())

    def test_non_empty_output_directory_is_left_alone(self):
        manifest, files = build_release.build_package(self.content, COMMIT)
        out = self.temp / "out"
        out.mkdir()
        (out / "keep.txt").write_text("别动", encoding="utf-8")
        with self.assertRaises(build_release.BuildError):
            build_release.write_release(manifest, files, out)
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["keep.txt"])

    def test_empty_output_directory_is_accepted(self):
        manifest, files = build_release.build_package(self.content, COMMIT)
        out = self.temp / "out"
        out.mkdir()
        build_release.write_release(manifest, files, out)
        self.assertTrue((out / "release.json").is_file())

    def test_failure_while_writing_leaves_no_package_and_no_temp(self):
        manifest, files = build_release.build_package(self.content, COMMIT)
        out = self.temp / "out"
        real = Path.write_bytes
        calls = []

        def flaky(path, data):
            calls.append(path)
            if len(calls) == 3:
                raise OSError("磁盘满了（测试）")
            return real(path, data)
        Path.write_bytes = flaky
        try:
            with self.assertRaises(OSError):
                build_release.write_release(manifest, files, out)
        finally:
            Path.write_bytes = real
        self.assertFalse(out.exists())
        self.assertEqual(self.leftovers(), [])

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
