"""tools/status_gen.py 的正反测试（#140 第 5 条）。运行：python -m unittest discover -s tools/tests"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import status_gen  # noqa: E402

GOOD = {
    "constellation": "demo", "title": "示例", "updated": "2026-11-16", "issue": 7, "total": 5,
    "preview": "https://example.com/p/", "now": "等 Luka 验收第 2 颗星。",
    "stars": [
        {"n": 1, "title": "甲", "state": "完成", "prs": [1, 2]},
        {"n": 2, "title": "乙", "state": "等验收", "prs": [3], "waiting": "Luka 在 iPad 上验收"},
    ],
}
MD = "# 标题\n\n前文\n\n<!-- status:begin demo -->\n<!-- status:end demo -->\n\n后文\n"


def variant(**kw):
    doc = yaml.safe_load(yaml.safe_dump(GOOD, allow_unicode=True))
    doc.update(kw)
    return doc


class Fixture(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="curio-status-"))
        (self.dir / "docs/constellations/demo").mkdir(parents=True)
        self.put(GOOD)
        (self.dir / "docs/constellations/demo/index.md").write_text(MD, encoding="utf-8")
        (self.dir / "docs/handoff.md").write_text(MD, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def put(self, doc):
        (self.dir / "docs/constellations/demo/status.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


class TestValidate(unittest.TestCase):
    def bad(self, doc, text):
        errs = status_gen.validate(doc, "demo")
        self.assertTrue(any(text in e for e in errs), f"本应报「{text}」，实际：{errs}")

    def test_good_passes(self):
        self.assertEqual(status_gen.validate(GOOD, "demo"), [])

    def test_unknown_state_fails(self):
        self.bad(variant(stars=[{"n": 1, "title": "甲", "state": "差不多了"}]), "state 要是")

    def test_waiting_required_when_in_progress(self):
        self.bad(variant(stars=[{"n": 2, "title": "乙", "state": "在做"}]), "waiting 要写")

    def test_waiting_must_be_empty_when_done(self):
        self.bad(variant(stars=[{"n": 1, "title": "甲", "state": "完成", "waiting": "还在等"}]), "waiting 要留空")

    def test_duplicate_and_out_of_range_numbers_fail(self):
        self.bad(variant(stars=[{"n": 1, "title": "甲", "state": "完成"}, {"n": 1, "title": "乙", "state": "完成"}]), "编号重复")
        self.bad(variant(stars=[{"n": 6, "title": "甲", "state": "完成"}]), "1 到 total")

    def test_missing_field_and_bad_values_fail(self):
        doc = variant(); del doc["now"]
        self.bad(doc, "缺少 now")
        self.bad(variant(updated="昨天"), "updated")
        self.bad(variant(preview="http://x"), "preview")
        self.bad(variant(stars=[{"n": 1, "title": "甲", "state": "完成", "prs": ["#1"]}]), "prs")

    def test_wrong_constellation_name_fails(self):
        self.bad(variant(constellation="other"), "constellation 应为")


class TestSync(Fixture):
    def test_write_generates_both_files_then_check_passes(self):
        errs, changed = status_gen.sync(self.dir, write=True)
        self.assertEqual(errs, [])
        self.assertEqual(len(changed), 2)
        text = (self.dir / "docs/handoff.md").read_text(encoding="utf-8")
        self.assertIn("5 颗星：完成 1、等验收 1、在做 0、草案 3", text)
        self.assertIn("| 第 2 颗「乙」 | 等验收 | #3 | Luka 在 iPad 上验收 |", text)
        self.assertNotIn("「甲」 | 草案", text)
        self.assertIn("前文", text); self.assertIn("后文", text)
        self.assertEqual(status_gen.sync(self.dir, write=False), ([], []))

    def test_check_fails_when_yaml_changed_but_docs_not_regenerated(self):
        status_gen.sync(self.dir, write=True)
        self.put(variant(updated="2026-11-17"))
        errs, _ = status_gen.sync(self.dir, write=False)
        self.assertEqual(len(errs), 2)
        self.assertTrue(all("对不上" in e for e in errs))

    def test_check_fails_when_generated_block_hand_edited(self):
        status_gen.sync(self.dir, write=True)
        p = self.dir / "docs/handoff.md"
        p.write_text(p.read_text(encoding="utf-8").replace("等验收 1", "等验收 9"), encoding="utf-8")
        errs, _ = status_gen.sync(self.dir, write=False)
        self.assertTrue(any("handoff.md" in e and "对不上" in e for e in errs))

    def test_missing_markers_fail(self):
        (self.dir / "docs/handoff.md").write_text("# 没有记号\n", encoding="utf-8")
        errs, _ = status_gen.sync(self.dir, write=True)
        self.assertTrue(any("没有「status:begin demo」" in e for e in errs))

    def test_invalid_yaml_reported_not_crash(self):
        (self.dir / "docs/constellations/demo/status.yaml").write_text("a: [", encoding="utf-8")
        errs, _ = status_gen.sync(self.dir, write=False)
        self.assertTrue(any("解析失败" in e for e in errs))

    def test_no_constellations_is_fine(self):
        empty = Path(tempfile.mkdtemp(prefix="curio-status-empty-"))
        try:
            self.assertEqual(status_gen.sync(empty, write=False), ([], []))
        finally:
            shutil.rmtree(empty, ignore_errors=True)


class TestStripBlocks(unittest.TestCase):
    def test_only_generated_part_removed(self):
        a = MD.replace("<!-- status:end demo -->", "新的一行\n<!-- status:end demo -->")
        self.assertEqual(status_gen.strip_blocks(a), status_gen.strip_blocks(MD))

    def test_change_outside_block_is_visible(self):
        self.assertNotEqual(status_gen.strip_blocks(MD.replace("后文", "改了")), status_gen.strip_blocks(MD))


if __name__ == "__main__":
    unittest.main()
