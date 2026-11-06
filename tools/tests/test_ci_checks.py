"""tools/ci_checks.py 的正反测试。运行：python -m unittest discover -s tools/tests"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import ci_checks  # noqa: E402


def node(nid, status="draft", activities=(), mis=(), prereq=(), dq="一块蛋糕平均分给 3 个人，每人分到多少？", theme="num"):
    mis_y = "".join(f"\n  - {{id: {m}, text: 说明}}" for m in mis)
    return textwrap.dedent(f"""\
        id: {nid}
        schema: knode/1
        title: 测试知识点
        subjects: [math]
        theme: {theme}
        grade: G3
        prerequisites: [{', '.join(prereq)}]
        driving_question: {dq}
        activities: [{', '.join(activities)}]
        status: {status}
        version: 1
        """) + (f"misconceptions:{mis_y}\n" if mis else "")


def activity(aid, targets, type_="experiment", review="pending", mis=(), extra=""):
    return textwrap.dedent(f"""\
        id: {aid}
        contract: activity/1.1
        type: {type_}
        version: 1
        title: 测试活动
        targets: [{', '.join(targets)}]
        age_band: G3-4
        entry: index.html
        pedagogy: hint-ladder
        emits: [started, answered]
        review: {review}
        misconceptions: [{', '.join(mis)}]
        """) + extra


def choice_item(index=1, mis="denominator-bigger", correct_text="甲"):
    wrong = {"id": "b", "text": "乙"}
    if mis is not None:
        wrong["misconception"] = mis
    return {
        "id": f"q{index}",
        "stem": "哪一种说法正确？",
        "answer": {
            "type": "choice",
            "choices": [{"id": "a", "text": correct_text, "correct": True}, wrong],
        },
        "hints": ["先看清题目问的是什么。"],
    }


def number_item(value=18, hints=("先看清数量之间的关系。",)):
    return {
        "id": "q1",
        "stem": "应该填多少？",
        "answer": {"type": "number", "value": value},
        "hints": list(hints),
    }


def fraction_item(numerator=1, denominator=4, equivalent=False, hints=("先数一数一共几份。",)):
    return {
        "id": "q1",
        "stem": "涂色部分用分数怎样表示？",
        "answer": {
            "type": "fraction",
            "numerator": numerator,
            "denominator": denominator,
            "accept_equivalent": equivalent,
        },
        "hints": list(hints),
    }


def structured(aid, targets, kind="quiz", review="approved", items=None, engine=1):
    doc = {
        "id": aid,
        "schema": "activity-def/1",
        "kind": kind,
        "version": 1,
        "title": "结构化活动",
        "targets": list(targets),
        "age_band": "G3-4",
        "duration_min": 5,
        "review": review,
        "engine": engine,
    }
    if kind == "quiz":
        doc["body"] = {"items": list(items) if items is not None else [choice_item(i) for i in range(5)]}
    elif kind == "explain":
        doc["body"] = {"steps": [
            {"type": "text", "text": "先观察。"},
            {"type": "text", "text": "再比较。"},
            {"type": "text", "text": "说说发现。"},
        ]}
    else:
        doc["body"] = {"prompt": "说说你的发现。", "max_chars": 120}
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


class Repo:
    """临时 git 仓库：main 上放好基线，再在分支上改。"""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="curio-ci-"))
        shutil.copytree(REPO / "schemas", self.dir / "schemas")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "测试")

    def git(self, *args):
        process = subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True, encoding="utf-8")
        if process.returncode != 0:
            raise RuntimeError(process.stderr)
        return process.stdout

    def write(self, path, text):
        file = self.dir / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")

    def delete(self, path):
        (self.dir / path).unlink()

    def commit(self, msg="改动\n\nImplemented-By: 测试模型"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)

    def baseline(self):
        self.commit("基线")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")

    def branch(self, name):
        self.git("checkout", "-q", "-b", name)
        self.name = name

    def check(self, labels=()):
        return ci_checks.run(self.dir, "origin/main", self.name, labels)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


N1, N2 = "math.number.division-meaning", "math.number.fraction-intro"
NODE_DIR = "content/nodes/num"


class Base(unittest.TestCase):
    def setUp(self):
        self.r = Repo()

    def tearDown(self):
        self.r.close()

    def ok(self, result):
        self.assertEqual(result.errors, [], f"本应通过，却报错：{result.errors}")

    def fails(self, result, text):
        messages = [message for _, message in result.errors]
        self.assertTrue(any(text in message for message in messages), f"本应报「{text}」，实际：{messages}")

    def add_html(self, aid, body="<p>分蛋糕</p>"):
        self.r.write(f"content/activities/{aid}/index.html", f"<!doctype html><html><body>{body}</body></html>\n")

    def add_structured(self, doc, nid=N2, status="draft", mis=("denominator-bigger",)):
        aid = doc["id"]
        self.r.write(f"{NODE_DIR}/{nid}.yaml", node(nid, status=status, activities=[aid], mis=mis))
        self.r.write(f"content/activities/{aid}/activity.yaml", yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))

    def published_set(self, review="approved"):
        explain_id, quiz_id = "act.explain.frac-0", "act.quiz.frac-1"
        acts = [explain_id, quiz_id]
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, status="published", activities=acts, mis=("denominator-bigger",)))
        self.r.write(f"content/activities/{explain_id}/activity.yaml", structured(explain_id, [N2], kind="explain", review=review))
        self.r.write(f"content/activities/{quiz_id}/activity.yaml", structured(quiz_id, [N2], kind="quiz", review=review))
        return acts


class TestBranches(Base):
    def test_bad_prefix_fails(self):
        self.r.baseline(); self.r.branch("patch-1"); self.r.commit()
        self.fails(self.r.check(), "不符合规则")

    def test_arch_may_touch_docs(self):
        self.r.baseline(); self.r.branch("arch/x"); self.r.write("docs/a.md", "x"); self.r.commit()
        self.ok(self.r.check())

    def test_feat_may_not_touch_schemas_or_content(self):
        self.r.baseline(); self.r.branch("feat/x")
        self.r.write("schemas/extra.md", "x"); self.r.write("content/nodes/num/z.yaml", "x"); self.r.commit()
        result = self.r.check()
        self.assertEqual(sum("不能改这个文件" in message for _, message in result.errors), 2)

    def test_glossary_only_on_arch(self):
        self.r.baseline(); self.r.branch("feat/x"); self.r.write("GLOSSARY.md", "x"); self.r.commit()
        self.fails(self.r.check(), "不能改这个文件")
        self.r.branch("arch/glossary"); self.r.write("GLOSSARY.md", "y"); self.r.commit()
        self.ok(self.r.check())

    def test_feat_may_touch_prototype(self):
        self.r.baseline(); self.r.branch("feat/x"); self.r.write("prototype/index.html", "<html></html>"); self.r.commit()
        self.ok(self.r.check())

    def test_override_label_turns_error_into_warning(self):
        self.r.baseline(); self.r.branch("feat/x"); self.r.write("docs/a.md", "x"); self.r.commit()
        result = self.r.check(labels={"越界-已批准"})
        self.ok(result)
        self.assertTrue(any("越界改动" in message for _, message in result.warnings))


class TestKnowledgePointBranch(Base):
    def test_new_node_on_its_own_branch_passes(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, prereq=[N1])); self.r.commit()
        self.ok(self.r.check())

    def test_kp_branch_may_not_touch_other_node(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, dq="改了别人的问题？")); self.r.commit()
        self.fails(self.r.check(), "不能改这个文件")

    def test_revision_branch_with_suffix_fails(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch(f"kp/{N2}-v2"); self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, dq="新的问题？")); self.r.commit()
        self.fails(self.r.check(), "不存在")

    def test_revision_of_published_node_passes(self):
        acts = self.published_set(); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, status="published", activities=acts, mis=("denominator-bigger",), dq="改版后的问题？"))
        self.r.write(f"content/activities/{acts[0]}/activity.yaml", structured(acts[0], [N2], kind="explain")); self.r.commit()
        self.assertFalse([message for _, message in self.r.check().errors if "不能改这个文件" in message])

    def test_unrelated_activity_mentioning_id_in_comment_fails(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=["act.quiz.other"]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write("content/activities/act.quiz.other/manifest.yaml", activity("act.quiz.other", [N1]))
        self.add_html("act.quiz.other"); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write("content/activities/act.quiz.other/manifest.yaml", activity("act.quiz.other", [N1], extra=f"# 参考 {N2}\n")); self.r.commit()
        self.fails(self.r.check(), "不能改这个文件")

    def test_own_activity_and_prompt_pass(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.frac"]))
        self.r.write("content/activities/act.quiz.frac/manifest.yaml", activity("act.quiz.frac", [N2]))
        self.add_html("act.quiz.frac")
        self.r.write("prompts/act.quiz.frac.md", "# 提示词"); self.r.commit()
        self.ok(self.r.check())

    def test_own_structured_activity_on_kp_branch_passes(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.frac"], mis=("denominator-bigger",)))
        self.r.write("content/activities/act.quiz.frac/activity.yaml", structured("act.quiz.frac", [N2])); self.r.commit()
        self.ok(self.r.check())

    def test_prompt_of_other_activity_fails(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=["act.quiz.other"]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write("content/activities/act.quiz.other/manifest.yaml", activity("act.quiz.other", [N1]))
        self.add_html("act.quiz.other"); self.r.baseline()
        self.r.branch(f"kp/{N2}"); self.r.write("prompts/act.quiz.other.md", "# 改别人的提示词"); self.r.commit()
        self.fails(self.r.check(), "不能改这个文件")


class TestSharedActivity(Base):
    def setUp(self):
        super().setUp()
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=["act.quiz.shared"]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.shared"]))
        self.r.write("content/activities/act.quiz.shared/manifest.yaml", activity("act.quiz.shared", [N1, N2]))
        self.add_html("act.quiz.shared"); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.add_html("act.quiz.shared", body="<p>改过的共享活动</p>"); self.r.commit()

    def test_kp_branch_may_not_change_shared_activity(self):
        result = self.r.check()
        self.fails(result, "共享活动")
        self.assertTrue(any(N1 in message for _, message in result.errors), "错误信息应列出受影响的其他知识点")

    def test_shared_activity_with_override_lists_affected_nodes(self):
        result = self.r.check(labels={"越界-已批准"})
        self.ok(result)
        self.assertTrue(any("共享活动改动" in message and N1 in message and N2 in message for _, message in result.warnings))


class TestActivityShapeAndSchema(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/shape")

    def test_structured_and_custom_shapes_pass(self):
        self.published_set()
        aid = "act.experiment.custom-1"
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=[aid]))
        self.r.write(f"content/activities/{aid}/manifest.yaml", activity(aid, [N1]))
        self.add_html(aid)
        self.ok(self.r.check())

    def test_mixed_shape_fails(self):
        aid = "act.quiz.mixed"
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=[aid]))
        self.r.write(f"content/activities/{aid}/activity.yaml", structured(aid, [N2]))
        self.r.write(f"content/activities/{aid}/manifest.yaml", activity(aid, [N2]))
        self.add_html(aid)
        self.fails(self.r.check(), "不能混用或缺少文件")

    def test_empty_and_incomplete_activity_directories_fail(self):
        (self.r.dir / "content/activities/act.quiz.empty").mkdir(parents=True)
        self.r.write("content/activities/act.quiz.incomplete/manifest.yaml", activity("act.quiz.incomplete", [N2]))
        result = self.r.check()
        self.assertEqual(sum("不能混用或缺少文件" in message for _, message in result.errors), 2)

    def test_extra_file_in_structured_directory_fails(self):
        aid = "act.quiz.extra"
        self.add_structured(yaml.safe_load(structured(aid, [N2])))
        self.r.write(f"content/activities/{aid}/notes.txt", "不属于发布格式")
        self.fails(self.r.check(), "不能混用或缺少文件")

    def test_structured_activity_schema_violation_fails(self):
        aid = "act.quiz.bad-schema"
        doc = yaml.safe_load(structured(aid, [N2]))
        doc["duration_min"] = 0
        self.add_structured(doc)
        self.fails(self.r.check(), "duration_min")


class TestReferences(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/refs")

    def test_node_lists_activity_that_does_not_target_it(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"]))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N1]))
        self.add_html("act.quiz.a"); self.r.commit()
        self.fails(self.r.check(), "两边要互相写上")

    def test_activity_targets_node_that_does_not_list_it(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2]))
        self.add_html("act.quiz.a"); self.r.commit()
        self.fails(self.r.check(), "两边要互相写上")

    def test_structured_activity_bidirectional_reference_passes(self):
        aid = "act.quiz.a"
        self.add_structured(yaml.safe_load(structured(aid, [N2])))
        self.ok(self.r.check())

    def test_missing_prerequisite_and_cycle(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, prereq=[N2]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, prereq=[N1, "math.number.nope"])); self.r.commit()
        result = self.r.check()
        self.fails(result, "不存在的知识点")
        self.fails(result, "有环")

    def test_filename_must_match_id(self):
        self.r.write(f"{NODE_DIR}/wrong-name.yaml", node(N2)); self.r.commit()
        self.fails(self.r.check(), "文件名必须和 id 一致")

    def test_schema_violation(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2).replace("theme: num", "theme: history")); self.r.commit()
        self.fails(self.r.check(), "theme")

    def test_activity_misconception_must_exist_in_node(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"], mis=("denominator-bigger",)))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2], mis=("made-up",)))
        self.add_html("act.quiz.a"); self.r.commit()
        self.fails(self.r.check(), "不在目标知识点的误区列表里")

    def test_single_target_uses_unqualified_misconception(self):
        aid = "act.quiz.a"
        doc = yaml.safe_load(structured(aid, [N2], items=[choice_item(mis=N2 + ":denominator-bigger")]))
        self.add_structured(doc)
        self.fails(self.r.check(), "直接写 id")

    def test_shared_activity_requires_and_accepts_qualified_misconceptions(self):
        aid = "act.quiz.shared"
        for nid in (N1, N2):
            self.r.write(f"{NODE_DIR}/{nid}.yaml", node(nid, activities=[aid], mis=("denominator-bigger",)))
        unqualified = yaml.safe_load(structured(aid, [N1, N2], items=[choice_item()]))
        self.r.write(f"content/activities/{aid}/activity.yaml", yaml.safe_dump(unqualified, allow_unicode=True, sort_keys=False))
        self.fails(self.r.check(), "必须写成 <知识点 id>:<误区 id>")
        qualified = yaml.safe_load(structured(aid, [N1, N2], items=[choice_item(mis=N2 + ":denominator-bigger")]))
        self.r.write(f"content/activities/{aid}/activity.yaml", yaml.safe_dump(qualified, allow_unicode=True, sort_keys=False))
        self.ok(self.r.check())

    def test_unknown_qualified_misconception_fails(self):
        aid = "act.quiz.shared"
        for nid in (N1, N2):
            self.r.write(f"{NODE_DIR}/{nid}.yaml", node(nid, activities=[aid], mis=("denominator-bigger",)))
        doc = yaml.safe_load(structured(aid, [N1, N2], items=[choice_item(mis=N2 + ":made-up")]))
        self.r.write(f"content/activities/{aid}/activity.yaml", yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
        self.fails(self.r.check(), "不在目标知识点的误区列表里")


class TestItemsAndFigures(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/items")

    def test_unique_item_ids_and_valid_figures_pass(self):
        aid = "act.quiz.figures"
        items = []
        for index, figure in enumerate((
            {"type": "pie", "parts": 4, "shaded": 4},
            {"type": "rect", "parts": 4, "shaded": 2, "direction": "h"},
            {"type": "rect-unequal", "widths": [1, 2, 1], "shaded": [0, 2]},
        )):
            item = choice_item(index)
            item["figure"] = figure
            items.append(item)
        self.add_structured(yaml.safe_load(structured(aid, [N2], items=items)))
        self.ok(self.r.check())

    def test_duplicate_item_id_fails(self):
        aid = "act.quiz.duplicate"
        items = [choice_item(1), choice_item(1)]
        self.add_structured(yaml.safe_load(structured(aid, [N2], items=items)))
        self.fails(self.r.check(), "题目 id 重复")

    def test_explain_check_ids_participate_in_uniqueness(self):
        aid = "act.explain.duplicate"
        doc = yaml.safe_load(structured(aid, [N2], kind="explain"))
        doc["body"]["steps"] = [
            {"type": "check", "item": choice_item(1)},
            {"type": "check", "item": choice_item(1)},
            {"type": "text", "text": "再想想。"},
        ]
        self.add_structured(doc)
        self.fails(self.r.check(), "题目 id 重复")

    def test_pie_and_rect_shaded_cannot_exceed_parts(self):
        for kind in ("pie", "rect"):
            with self.subTest(kind=kind):
                aid = f"act.quiz.bad-{kind}"
                item = choice_item()
                item["figure"] = {"type": kind, "parts": 4, "shaded": 5}
                if kind == "rect":
                    item["figure"]["direction"] = "h"
                self.add_structured(yaml.safe_load(structured(aid, [N2], items=[item])))
                self.fails(self.r.check(), "shaded 不能超过 parts")

    def test_rect_unequal_shaded_index_cannot_be_out_of_range(self):
        aid = "act.quiz.bad-index"
        item = choice_item()
        item["figure"] = {"type": "rect-unequal", "widths": [1, 2, 1], "shaded": [3]}
        self.add_structured(yaml.safe_load(structured(aid, [N2], items=[item])))
        self.fails(self.r.check(), "下标超出")

    def test_svg_reference_must_exist_and_existing_reference_passes(self):
        aid = "act.quiz.svg"
        item = choice_item()
        item["figure"] = {"type": "svg", "src": "content/assets/diagram.svg"}
        doc = yaml.safe_load(structured(aid, [N2], items=[item]))
        self.add_structured(doc)
        self.fails(self.r.check(), "文件不存在")
        self.r.write("content/assets/diagram.svg", "<svg xmlns=\"http://www.w3.org/2000/svg\"><title>图</title></svg>\n")
        self.ok(self.r.check())


class TestHintLeaks(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/hints")

    def check_item(self, item):
        aid = "act.quiz.hints"
        self.add_structured(yaml.safe_load(structured(aid, [N2], items=[item])))
        return self.r.check()

    def test_fraction_chinese_answer_leak_fails_and_safe_hint_passes(self):
        self.fails(self.check_item(fraction_item(hints=["涂了四分之一"])), "泄露了正确答案")
        self.ok(self.check_item(fraction_item(hints=["先数一数一共几份"])))

    def test_fraction_ascii_and_word_order_forms_fail(self):
        for hint in ("写成 1/4", "可以写成 4分之1"):
            with self.subTest(hint=hint):
                self.fails(self.check_item(fraction_item(hints=[hint])), "泄露了正确答案")

    def test_equivalent_fraction_simplest_form_also_fails(self):
        item = fraction_item(2, 8, equivalent=True, hints=["涂了四分之一"])
        self.fails(self.check_item(item), "四分之一")

    def test_number_match_does_not_hit_longer_number(self):
        self.ok(self.check_item(number_item(18, ["一共 180 页"])))

    def test_number_exact_answer_fails(self):
        self.fails(self.check_item(number_item(18, ["答案是 18 厘米"])), "18")

    def test_choice_correct_text_warns_but_does_not_fail(self):
        item = choice_item(correct_text="1/4")
        item["hints"] = ["可以写成 1/4"]
        result = self.check_item(item)
        self.ok(result)
        self.assertTrue(any("可能泄露" in message and "1/4" in message for _, message in result.warnings))


class TestSvgWhitelist(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/svg")

    def write_svg(self, text):
        self.r.write("content/assets/check.svg", text)

    def test_whitelisted_svg_passes(self):
        self.write_svg("""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="圆">
  <defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient>
  <path id="p" d="M0 0L1 1"/></defs>
  <use href="#p" fill="url(#g)"/><text x="1" y="2">图</text>
</svg>
""")
        self.ok(self.r.check())

    def test_disallowed_svg_constructs_fail(self):
        cases = {
            "元素": "<svg><script>alert(1)</script></svg>",
            "属性": "<svg><rect style=\"fill:red\"/></svg>",
            "外部引用": "<svg><use href=\"https://example.com/a.svg#x\"/></svg>",
            "外部渐变": "<svg><rect fill=\"url(https://example.com/a.svg#g)\"/></svg>",
            "DOCTYPE": "<!DOCTYPE svg><svg/>",
            "实体": "<!DOCTYPE svg [<!ENTITY x \"y\">]><svg/>",
            "处理指令": "<svg/><?work unsafe?>",
        }
        for name, document in cases.items():
            with self.subTest(name=name):
                self.write_svg(document)
                self.assertTrue(self.r.check().errors, f"本应拦截：{name}")


class TestPathsAndEngine(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/paths")

    def test_ascii_content_paths_pass(self):
        self.published_set()
        self.r.write("content/assets/a/Fig-1.svg", "<svg/>\n")
        self.ok(self.r.check())

    def test_non_ascii_and_dot_led_paths_fail(self):
        self.r.write("content/assets/图.svg", "<svg/>\n")
        self.r.write("content/assets/.hidden.svg", "<svg/>\n")
        result = self.r.check()
        self.assertEqual(sum("路径的每一段" in message for _, message in result.errors), 2)

    @unittest.skipIf(os.name == "nt", "Windows 默认文件系统不能同时创建只差大小写的路径")
    def test_case_only_path_collision_fails(self):
        self.r.write("content/assets/a/Fig.svg", "<svg/>\n")
        self.r.write("content/assets/a/fig.svg", "<svg/>\n")
        self.fails(self.r.check(), "只差大小写")

    def test_engine_requirement_table_is_enforced(self):
        aid = "act.quiz.engine"
        doc = yaml.safe_load(structured(aid, [N2], engine=1))
        self.add_structured(doc)
        self.ok(self.r.check())
        original = ci_checks.ENGINE_REQUIREMENTS["answer"]["choice"]
        ci_checks.ENGINE_REQUIREMENTS["answer"]["choice"] = 2
        try:
            self.fails(self.r.check(), "至少需要 2 级引擎")
        finally:
            ci_checks.ENGINE_REQUIREMENTS["answer"]["choice"] = original

    def test_fixture_directory_does_not_run_content_ci_rules(self):
        self.r.write("tools/tests/fixtures/content/activities/act.quiz.bad/activity.yaml", "not: valid")
        self.r.write("tools/tests/fixtures/content/assets/.bad.svg", "<script/>")
        self.ok(self.r.check())


class TestPublishGate(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/publish")

    def test_complete_published_node_with_structured_activities_passes(self):
        self.published_set(); self.r.commit()
        self.ok(self.r.check())

    def test_pending_extra_activity_is_not_included_and_does_not_block(self):
        acts = self.published_set()
        pending = "act.reflection.pending"
        acts.append(pending)
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, status="published", activities=acts, mis=("denominator-bigger",)))
        self.r.write(f"content/activities/{pending}/activity.yaml", structured(pending, [N2], kind="reflection", review="pending"))
        self.ok(self.r.check())

    def test_published_without_approved_quiz_fails(self):
        self.published_set()
        quiz = "act.quiz.frac-1"
        self.r.write(f"content/activities/{quiz}/activity.yaml", structured(quiz, [N2], review="pending"))
        self.fails(self.r.check(), "至少有一个 quiz")

    def test_published_quiz_with_fewer_than_five_items_fails(self):
        self.published_set()
        quiz = "act.quiz.frac-1"
        self.r.write(f"content/activities/{quiz}/activity.yaml", structured(quiz, [N2], items=[choice_item()]))
        self.fails(self.r.check(), "至少要有 5 道题")

    def test_published_quiz_four_items_fails_and_five_items_passes(self):
        self.published_set()
        quiz = "act.quiz.frac-1"
        self.r.write(f"content/activities/{quiz}/activity.yaml", structured(quiz, [N2], items=[choice_item(i) for i in range(4)]))
        self.fails(self.r.check(), "至少要有 5 道题")
        self.r.write(f"content/activities/{quiz}/activity.yaml", structured(quiz, [N2], items=[choice_item(i) for i in range(5)]))
        self.ok(self.r.check())

    def test_published_with_uncovered_misconception_fails(self):
        self.published_set()
        quiz = "act.quiz.frac-1"
        self.r.write(f"content/activities/{quiz}/activity.yaml", structured(quiz, [N2], items=[choice_item(i, mis=None) for i in range(5)]))
        self.fails(self.r.check(), "还没有被收录活动")

    def test_misconception_only_on_correct_choice_does_not_count_as_covered(self):
        self.published_set()
        quiz = "act.quiz.frac-1"
        items = [choice_item(i, mis=None) for i in range(5)]
        items[0]["answer"]["choices"][0]["misconception"] = "denominator-bigger"
        self.r.write(f"content/activities/{quiz}/activity.yaml", structured(quiz, [N2], items=items))
        result = self.r.check()
        self.fails(result, "denominator-bigger")
        self.fails(result, "还没有被收录活动")

    def test_custom_manifest_misconception_declaration_still_counts(self):
        acts = self.published_set()
        quiz = "act.quiz.frac-1"
        self.r.write(f"content/activities/{quiz}/activity.yaml", structured(quiz, [N2], items=[choice_item(i, mis=None) for i in range(5)]))
        custom = "act.experiment.cover"
        acts.append(custom)
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, status="published", activities=acts, mis=("denominator-bigger",)))
        self.r.write(f"content/activities/{custom}/manifest.yaml", activity(custom, [N2], review="approved", mis=("denominator-bigger",)))
        self.add_html(custom)
        self.ok(self.r.check())

    def test_draft_prerequisite_fails_reference_closure(self):
        self.published_set()
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, status="published", activities=["act.explain.frac-0", "act.quiz.frac-1"], mis=("denominator-bigger",), prereq=[N1]))
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1))
        self.fails(self.r.check(), N1)

    def test_approved_activity_with_draft_target_fails_reference_closure(self):
        self.published_set()
        quiz = "act.quiz.frac-1"
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=[quiz], mis=("denominator-bigger",)))
        self.r.write(f"content/activities/{quiz}/activity.yaml", structured(quiz, [N2, N1]))
        self.fails(self.r.check(), "引用闭包")
        self.fails(self.r.check(), N1)


class TestIdsCopyTrailers(Base):
    def test_changing_id_fails(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch("arch/rename"); self.r.write(f"{NODE_DIR}/{N2}.yaml", node("math.number.fraction-renamed")); self.r.commit()
        self.fails(self.r.check(), "ID 永不改动")

    def test_changing_structured_activity_id_fails(self):
        aid = "act.quiz.a"
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=[aid]))
        self.r.write(f"content/activities/{aid}/activity.yaml", structured(aid, [N2])); self.r.baseline()
        self.r.branch("arch/rename")
        self.r.write(f"content/activities/{aid}/activity.yaml", structured("act.quiz.b", [N2])); self.r.commit()
        self.fails(self.r.check(), "ID 永不改动")

    def test_quoting_id_is_not_a_change(self):
        quoted = node(N2).replace(f"id: {N2}", f'id: "{N2}"')
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch("arch/quote"); self.r.write(f"{NODE_DIR}/{N2}.yaml", quoted); self.r.commit()
        self.ok(self.r.check())

    def test_unquoting_id_is_not_a_change(self):
        quoted = node(N2).replace(f"id: {N2}", f"id: '{N2}'")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", quoted); self.r.baseline()
        self.r.branch("arch/unquote"); self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.commit()
        self.ok(self.r.check())

    def test_deleting_node_fails(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch("arch/delete"); self.r.delete(f"{NODE_DIR}/{N2}.yaml"); self.r.commit()
        self.fails(self.r.check(), "ID 永不改动")

    def test_forbidden_word_in_kid_facing_text_fails(self):
        self.r.baseline(); self.r.branch("arch/copy")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, dq="一起来学习分数吧？")); self.r.commit()
        self.fails(self.r.check(), "出现了「学习」")

    def test_forbidden_word_only_in_script_passes(self):
        self.r.baseline(); self.r.branch("arch/copy")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"]))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2]))
        self.add_html("act.quiz.a", body="<p>分蛋糕</p><script>// 学习事件</script>"); self.r.commit()
        self.ok(self.r.check())

    def test_forbidden_word_in_page_text_fails(self):
        self.r.baseline(); self.r.branch("arch/copy")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"]))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2]))
        self.add_html("act.quiz.a", body="<p>一起学习</p>"); self.r.commit()
        self.fails(self.r.check(), "页面文字里出现了")

    def test_missing_trailer_warns_but_passes(self):
        self.r.baseline(); self.r.branch("arch/x"); self.r.write("docs/a.md", "x"); self.r.commit("没有署名的中文提交")
        result = self.r.check()
        self.ok(result)
        self.assertTrue(any("没有署名" in message for _, message in result.warnings))

    def test_trailer_present_no_warning(self):
        self.r.baseline(); self.r.branch("arch/x"); self.r.write("docs/a.md", "x"); self.r.commit()
        self.assertFalse(any("没有署名" in message for _, message in self.r.check().warnings))


class TestCli(Base):
    def test_chinese_commit_under_c_locale_does_not_crash(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, dq="中文改动？")); self.r.commit("中文标题\n\n中文正文，带「引号」。\n\nImplemented-By: 测试模型")
        env = {key: value for key, value in os.environ.items() if key not in ("LANG", "LC_ALL", "PYTHONIOENCODING", "PYTHONUTF8")}
        env.update(LANG="C", LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", BASE_REF="main", HEAD_BRANCH=f"kp/{N2}")
        preferred = subprocess.run([sys.executable, "-c", "import locale;print(locale.getpreferredencoding(False))"], capture_output=True, text=True, env=env)
        self.assertNotIn("utf", preferred.stdout.lower(), "测试环境没能切到非 UTF-8")
        process = subprocess.run([sys.executable, str(TOOLS / "ci_checks.py"), str(self.r.dir)], capture_output=True, env=env)
        output = process.stdout.decode("utf-8", errors="replace") + process.stderr.decode("utf-8", errors="replace")
        self.assertNotIn("Traceback", output)
        self.assertEqual(process.returncode, 0, output)

    def test_missing_base_exits_2(self):
        self.r.commit("只有一个提交")
        env = dict(os.environ, BASE_REF="main", HEAD_BRANCH="arch/x")
        process = subprocess.run([sys.executable, str(TOOLS / "ci_checks.py"), str(self.r.dir)], capture_output=True, env=env)
        self.assertEqual(process.returncode, 2)


if __name__ == "__main__":
    unittest.main()
# END OF FILE
