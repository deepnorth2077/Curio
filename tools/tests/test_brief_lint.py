"""从提交中的设计文件检查四节、查重、误区与学段，保留历史原稿可复查。"""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import brief_lint as lint


BRIEF = """# 灯箱

## 一句话实物
推镜筒，把窗外的树搬到纸上。

## 零件清单
- 纸屏接住像，镜筒可推拉。

## 「哇」时刻
树尖朝着脚底，窗外的树尖却朝天。

## 验收用例
| 输入 | 屏上所见 |
| --- | --- |
| 关上小孔 | 像消失 |

## 实现
- 1
- 35
"""
BRIEF_PATH = "prompts/act.simulation.light-01.md"
CARD = "content/nodes/ene/physics.light.yaml"
QUIZ = "content/activities/act.quiz.light-01/activity.yaml"
SIM = "content/activities/act.simulation.light-01/manifest.yaml"


class TestBrief(unittest.TestCase):
    def check(self, text=BRIEF, peers=None):
        return lint.lint_brief(text, peers or {}, {"1", "35"})

    def test_requires_four_populated_sections(self):
        self.assertEqual(self.check(), [])
        for title in ("一句话实物", "零件清单", "「哇」时刻", "验收用例"):
            with self.subTest(title=title):
                self.assertTrue(self.check(BRIEF.replace(f"## {title}", "## 别的标题")))
        empty = BRIEF.replace("推镜筒，把窗外的树搬到纸上。", "<!--以后填写-->")
        self.assertTrue(self.check(empty))
        self.assertTrue(self.check("~~~\n" + BRIEF + "\n~~~"))

    def test_cases_have_concrete_input_and_expected_output(self):
        self.assertTrue(self.check(BRIEF.replace("| 关上小孔 | 像消失 |", "|  |  |")))
        self.assertFalse(self.check(BRIEF.replace("## 验收用例", "## 4. 验收用例")))

    def test_implementation_allows_only_existing_lesson_numbers(self):
        for invalid in ("", "- 58", "- 35 原文复制", "```\n- 35\n```"):
            with self.subTest(invalid=invalid):
                self.assertTrue(self.check(BRIEF.replace("- 1\n- 35", invalid)))
        self.assertTrue(self.check(BRIEF + "\n## 附录\n{{embed: refs/lessons.md#实现}}"))
        self.assertFalse(self.check(BRIEF + "\n## 附录\n[经验](refs/lessons.md)"))

    def test_duplicates_count_body_characters_not_headings_or_wrapping(self):
        peer = {"另一星": lint.paragraphs(lint.markdown(BRIEF))}
        wrapped = BRIEF.replace("把窗外", "\n把窗外").replace("## 零件清单", "## 2. 零件清单")
        self.assertIn("100.0%", self.check(wrapped, peer)[0])
        unrelated = BRIEF.replace("推镜筒，把窗外的树搬到纸上。", "在木杆上挪一枚小砝码。")
        unrelated = unrelated.replace("纸屏接住像，镜筒可推拉。", "铅笔托住横杆。").replace(
            "树尖朝着脚底，窗外的树尖却朝天。", "小砝码把重箱抬了起来。")
        self.assertFalse(self.check(unrelated, peer))

    def test_threshold_is_strictly_over_thirty_percent(self):
        sections = "## 一句话实物\n" + "甲"*30 + "\n\n" + "乙"*70
        peer = {"另一星": lint.paragraphs(lint.markdown("甲"*30))}
        has_overlap = lambda s: any("30%" in error for error in self.check(s, peer))
        self.assertFalse(has_overlap(sections))
        self.assertTrue(has_overlap(sections[:-1]))


class TestFiles(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.write(lint.LESSONS, "## 实现\n1. 单一模型。\n35. 手柄位置。\n## 其他\n58. 无效。")
        self.write(BRIEF_PATH, BRIEF)

    def write(self, name, content):
        file = self.root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content if isinstance(content, str) else yaml.safe_dump(content, allow_unicode=True),
                        encoding="utf-8")

    def lint(self, *paths):
        return lint.lint_paths(self.root, paths)

    def test_other_briefs_compared_and_archives_excluded(self):
        self.write(BRIEF_PATH.replace(".md", ".task.md"), BRIEF)
        self.assertEqual(self.lint(BRIEF_PATH), [])
        self.write("docs/constellations/space/stars/01-star.md", BRIEF)
        self.assertIn("100.0%", self.lint(BRIEF_PATH)[0])

    def test_three_different_misconceptions_and_observable_objective(self):
        traits = [{"id": id, "text": text} for id, text in
                  (("weight", "只看重量"), ("ends", "端点就是支点"), ("holes", "数孔就算距离"))]
        card = {"misconceptions": traits, "objectives": ["拖动把手并指出光屏上的变化"],
                "lenses": [{"approach": "镜筒可以移动"}], "activities": ["act.simulation.light-01"]}
        self.write(CARD, card)
        self.assertFalse(self.lint(CARD))
        for bad in (traits[:2], traits+[traits[0]], [*traits[:2], dict(traits[2], text="只看重量。")]):
            self.write(CARD, dict(card, misconceptions=bad))
            self.assertTrue(self.lint(CARD))
        for copied in ["镜筒可以移动", "小孔到屏的距离固定", "理解小孔成像"]:
            self.write(BRIEF_PATH, BRIEF + "\n## 真相表与模型\n| 模型 | 小孔到屏的距离固定 |")
            self.write(CARD, dict(card, objectives=[copied]))
            self.assertTrue(self.lint(CARD))

    def test_feedback_not_a_hint_and_companions_use_same_age_band(self):
        sim = {"id": "act.simulation.light-01", "targets": ["physics.light"], "age_band": "G3-4"}
        self.write(SIM, sim)
        item = {"id": "q", "feedback": {"wrong": "纸屏现在贴得太近"}, "hints": ["挪一下纸屏"]}
        quiz = dict(sim, kind="quiz", body={"items": [item]})
        self.write(QUIZ, quiz)
        self.assertFalse(self.lint(QUIZ, SIM))
        self.write(QUIZ, dict(quiz, age_band="G5-6"))
        self.assertTrue(self.lint(QUIZ))
        self.assertTrue(self.lint(SIM))
        item["feedback"]["wrong"] = "挪一下纸屏。"
        self.write(QUIZ, quiz)
        self.assertTrue(self.lint(QUIZ))

    def test_five_questions_diagnose_three_different_wrong_ideas(self):
        items = [{"id": f"q{i}", "answer": {"choices": [{"correct": True}, {"misconception": "weight"}]}}
                 for i in range(5)]
        quiz = {"kind": "quiz", "targets": ["physics.light"], "body": {"items": items}}
        self.write(QUIZ, quiz)
        self.assertTrue(self.lint(QUIZ))
        items[1]["answer"]["choices"][1]["misconception"] = "count-holes"
        items[3]["answer"] = {"common_wrong": [{"value": 2, "misconception": "distance"}]}
        self.write(QUIZ, quiz)
        self.assertFalse(self.lint(QUIZ))

    def test_pairing_uses_node_card_for_different_activity_names(self):
        self.write(CARD, {"activities": ["act.simulation.light-01", "act.quiz.shadow-01"],
                          "misconceptions": [{"id": code, "text": code} for code in ("near", "size", "tilt")]})
        self.write(SIM, {"age_band": "G3-4", "targets": ["physics.light"]})
        quiz = QUIZ.replace("light-01", "shadow-01")
        self.write(quiz, {"age_band": "G5-6", "targets": ["physics.light"]})
        self.assertTrue(self.lint(SIM))
        self.write(quiz, {"age_band": "G3-4", "targets": ["physics.light"]})
        self.assertFalse(self.lint(SIM))

    def test_activity_changes_find_the_authored_brief_and_only_the_target_card(self):
        html = SIM.replace("manifest.yaml", "index.html")
        authored = "docs/constellations/space/stars/01-shadow.md"
        self.write(authored, "这里仍是上次的旧模板。")
        spec = {"author": {"prompt_ref": authored}, "targets": ["physics.light"]}
        self.write(SIM, spec)
        self.write(QUIZ, {"targets": ["physics.light"]})
        self.write(html, "<body>画面变了</body>")
        self.write(CARD, {"misconceptions": [{"id": "heavy", "text": "只看重量"}]})
        self.write(CARD.replace("light", "unrelated"), {"misconceptions": []})
        for source in (html, QUIZ):
            errors = self.lint(source)
            self.assertTrue(any(e.startswith(authored) for e in errors))
            self.assertTrue(any(e.startswith(CARD) for e in errors))
            self.assertFalse(any("unrelated" in e or e.startswith(BRIEF_PATH) for e in errors))
        # 缺省来源按模拟的活动 ID 找；历史分组说明不按单星原稿审。
        self.write(SIM, dict(spec, author={}))
        self.write(BRIEF_PATH, "这是另一份还没改的旧稿。")
        self.assertTrue(any(e.startswith(BRIEF_PATH) for e in self.lint(html)))
        (self.root / BRIEF_PATH).unlink()
        self.write(SIM, dict(spec, author={"prompt_ref": "docs/constellations/space/g1.md"}))
        self.write("docs/constellations/space/g1.md", "旧课程组的整套说明")
        self.assertTrue(all(e.startswith(CARD) for e in self.lint(html)))

    def test_accepted_star_brief_skipped_only_when_brief_unchanged(self):
        html = SIM.replace("manifest.yaml", "index.html")
        authored = "docs/constellations/space/stars/01-shadow.md"
        self.write(authored, "这里仍是上次的旧模板。")
        self.write(SIM, {"author": {"prompt_ref": authored}, "targets": ["physics.light"]})
        self.write(html, "<body>只换了站完成信号</body>")
        status = "docs/constellations/space/status.yaml"
        self.write(status, {"stars": [{"n": 1, "state": "等验收"}]})
        self.assertTrue(any(e.startswith(authored) for e in self.lint(html)))
        self.write(status, {"stars": [{"n": 1, "state": "完成"}]})
        self.assertFalse(any(e.startswith(authored) for e in self.lint(html)))
        self.assertTrue(any(e.startswith(authored) for e in self.lint(html, authored)))

    def test_published_star_prompt_brief_skipped_only_when_brief_unchanged(self):
        html = SIM.replace("manifest.yaml", "index.html")
        self.write(SIM, {"targets": ["physics.light"]})
        self.write(html, "<body>只换了站完成信号</body>")
        self.write(BRIEF_PATH, "旧模板的任务说明")
        self.write(CARD, {"status": "draft", "misconceptions": [{"id": f"m{i}", "text": f"说法{i}"} for i in range(3)]})
        self.assertTrue(any(e.startswith(BRIEF_PATH) for e in self.lint(html)))
        self.write(CARD, {"status": "published", "misconceptions": [{"id": f"m{i}", "text": f"说法{i}"} for i in range(3)]})
        self.assertFalse(any(e.startswith(BRIEF_PATH) for e in self.lint(html)))
        self.assertTrue(any(e.startswith(BRIEF_PATH) for e in self.lint(html, BRIEF_PATH)))

    def test_pr_scope_does_not_block_on_archived_work(self):
        def git(*args):
            return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=t@example.com", *args],
                                  cwd=self.root, check=True, capture_output=True)
        self.write(BRIEF_PATH, "旧稿未过审")
        git("init", "-q"); git("add", "."); git("commit", "-qm", "旧稿")
        base = git("rev-parse", "HEAD").stdout.decode().strip()
        self.write("docs/note.md", "独立变更")
        git("add", "."); git("commit", "-qm", "改交接")
        self.assertFalse(lint.main(["--base", base], self.root))
        html = SIM.replace("manifest.yaml", "index.html")
        self.write(SIM, {"targets": ["physics.light"]})
        self.write(html, "<p>原实物</p>")
        git("add", "."); git("commit", "-qm", "原实物与文档")
        base = git("rev-parse", "HEAD").stdout.decode().strip()
        self.write(html, "<p>只改实物</p>")
        git("add", "."); git("commit", "-qm", "只修改 HTML")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(lint.main(["--base", base], self.root))
            self.assertTrue(lint.main([BRIEF_PATH], self.root))
