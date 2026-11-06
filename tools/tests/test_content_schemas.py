import copy
import json
import re
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tools" / "tests" / "fixtures"
SCHEMAS = ROOT / "schemas"


def load_document(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".yaml":
        return yaml.safe_load(text)
    return json.loads(text)


def pointer_tokens(path):
    if not path.startswith("/"):
        raise AssertionError(f"JSON Pointer 必须以 / 开头：{path}")
    return [token.replace("~1", "/").replace("~0", "~") for token in path[1:].split("/")]


def walk(document, tokens):
    current = document
    for token in tokens:
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    return current


def existing_value(document, tokens):
    parent = walk(document, tokens[:-1])
    key = tokens[-1]
    if isinstance(parent, list):
        if key == "-":
            raise AssertionError("replace/remove 不能使用数组末尾标记 -")
        index = int(key)
        if index < 0 or index >= len(parent):
            raise AssertionError(f"数组路径原本不存在：/{'/'.join(tokens)}")
        return parent[index]
    if not isinstance(parent, dict) or key not in parent:
        raise AssertionError(f"对象路径原本不存在：/{'/'.join(tokens)}")
    return parent[key]


def apply_patch(document, operation):
    op = operation["op"]
    if op not in {"add", "replace", "remove"}:
        raise AssertionError(f"不支持的补丁操作：{op}")
    tokens = pointer_tokens(operation["path"])
    if not tokens:
        raise AssertionError("本测试的补丁不支持替换整个文档")

    if op in {"replace", "remove"}:
        existing_value(document, tokens)

    parent = walk(document, tokens[:-1])
    key = tokens[-1]
    if isinstance(parent, list):
        if key == "-":
            if op != "add":
                raise AssertionError("只有 add 能使用数组末尾标记 -")
            parent.append(operation["value"])
            return
        index = int(key)
        if op == "add":
            if index < 0 or index > len(parent):
                raise AssertionError(f"add 的数组下标越界：{operation['path']}")
            parent.insert(index, operation["value"])
        elif op == "replace":
            parent[index] = operation["value"]
        else:
            parent.pop(index)
    elif isinstance(parent, dict):
        if op == "remove":
            del parent[key]
        else:
            parent[key] = operation["value"]
    else:
        raise AssertionError(f"补丁父路径不是对象或数组：{operation['path']}")


class ContentSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema_documents = {
            "activity-def": load_document(SCHEMAS / "activity-def.schema.json"),
            "release": load_document(SCHEMAS / "release.schema.json"),
            "knode": load_document(SCHEMAS / "knode.schema.json"),
            "activity": load_document(SCHEMAS / "activity.schema.json"),
        }
        cls.validators = {
            name: Draft202012Validator(schema)
            for name, schema in cls.schema_documents.items()
        }

    def assert_valid(self, schema_name, document):
        errors = sorted(
            self.validators[schema_name].iter_errors(document),
            key=lambda error: list(error.absolute_path),
        )
        details = "\n".join(
            f"{list(error.absolute_path)}: {error.message}" for error in errors
        )
        self.assertFalse(errors, f"{schema_name} 校验未通过：\n{details}")

    def test_schemas_are_valid_draft_2020_12(self):
        for name, schema in self.schema_documents.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    def test_all_valid_yaml_fixtures(self):
        paths = sorted((FIXTURES / "content").rglob("*.yaml"))
        self.assertEqual(len(paths), 4)
        for path in paths:
            schema_name = "knode" if path.name != "activity.yaml" else "activity-def"
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assert_valid(schema_name, load_document(path))

    def test_valid_json_fixtures(self):
        cases = {
            "content/release.json": "release",
            "content/experiment-manifest.json": "activity",
        }
        for relative_path, schema_name in cases.items():
            with self.subTest(path=relative_path):
                self.assert_valid(schema_name, load_document(FIXTURES / relative_path))

    def test_invalid_fixtures_are_rejected(self):
        cases = load_document(FIXTURES / "invalid" / "content.json")
        for case in cases:
            with self.subTest(case=case["name"]):
                original = load_document(FIXTURES / case["base"])
                self.assertTrue(
                    self.validators[case["schema"]].is_valid(original),
                    "反向样例的 base 本身必须合格",
                )
                patched = copy.deepcopy(original)
                for operation in case["patch"]:
                    apply_patch(patched, operation)
                self.assertNotEqual(patched, original, "补丁必须实际改变文档")
                self.assertFalse(
                    self.validators[case["schema"]].is_valid(patched),
                    f"不应通过：{case['why']}",
                )

    def test_invalid_fixture_catalog(self):
        cases = load_document(FIXTURES / "invalid" / "content.json")
        names = [case["name"] for case in cases]
        self.assertEqual(len(names), len(set(names)))
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertRegex(case["name"], r"^[a-z0-9-]+$")
                self.assertIn(case["schema"], self.validators)
                self.assertEqual(len(case["patch"]), 1, "每个反向样例只改一处")

    def test_explain_style_tutor_and_plain_are_valid(self):
        base = load_document(FIXTURES / "content" / "activities" / "act.explain.fraction-intro-01" / "activity.yaml")
        for style in ("plain", "tutor"):
            with self.subTest(style=style):
                doc = copy.deepcopy(base)
                doc["body"]["style"] = style
                self.assert_valid("activity-def", doc)

    def test_explain_style_unknown_is_rejected(self):
        doc = load_document(FIXTURES / "content" / "activities" / "act.explain.fraction-intro-01" / "activity.yaml")
        doc["body"]["style"] = "comic"
        self.assertFalse(self.validators["activity-def"].is_valid(doc))

    def test_quiz_covers_every_misconception_and_answer_type(self):
        node = load_document(
            FIXTURES
            / "content"
            / "nodes"
            / "num"
            / "math.number.fraction-intro.yaml"
        )
        quiz = load_document(
            FIXTURES
            / "content"
            / "activities"
            / "act.quiz.fraction-intro-01"
            / "activity.yaml"
        )
        required = {item["id"] for item in node["misconceptions"]}
        covered = set()
        answer_types = set()
        for item in quiz["body"]["items"]:
            answer = item["answer"]
            answer_types.add(answer["type"])
            if answer["type"] == "choice":
                for choice in answer["choices"]:
                    if not choice.get("correct") and "misconception" in choice:
                        covered.add(choice["misconception"])
            for wrong in answer.get("common_wrong", []):
                if "misconception" in wrong:
                    covered.add(wrong["misconception"])
        self.assertTrue(required <= covered, f"未覆盖的误区：{sorted(required - covered)}")
        self.assertEqual(answer_types, {"choice", "number", "fraction"})
        self.assertGreaterEqual(len(quiz["body"]["items"]), 5)
        self.assertLessEqual(len(quiz["body"]["items"]), 8)

    def test_sample_activity_requirements(self):
        activity_dir = FIXTURES / "content" / "activities"
        expected_ids = set()
        for path in sorted(activity_dir.glob("*/activity.yaml")):
            activity = load_document(path)
            expected_ids.add(activity["id"])
            with self.subTest(activity=activity["id"]):
                self.assertEqual(activity["id"], path.parent.name)
                self.assertEqual(activity["review"], "approved")
                self.assertEqual(activity["engine"], 1)
                self.assertEqual(activity["targets"], ["math.number.fraction-intro"])

        node = load_document(
            FIXTURES
            / "content"
            / "nodes"
            / "num"
            / "math.number.fraction-intro.yaml"
        )
        self.assertEqual(node["status"], "published")
        self.assertEqual(set(node["activities"]), expected_ids)
        self.assertGreaterEqual(len(node["misconceptions"]), 3)

        explain = load_document(
            activity_dir / "act.explain.fraction-intro-01" / "activity.yaml"
        )
        steps = explain["body"]["steps"]
        self.assertGreaterEqual(len(steps), 6)
        self.assertLessEqual(len(steps), 10)
        self.assertTrue(any(step["type"] == "check" for step in steps))
        figure_types = {
            step["figure"]["type"] for step in steps if step["type"] == "figure"
        }
        self.assertTrue({"pie", "rect-unequal"} <= figure_types)


if __name__ == "__main__":
    unittest.main()
# END OF FILE
