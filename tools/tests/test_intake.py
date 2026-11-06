"""tools/intake.py 的正反测试。运行：python -m unittest discover -s tools/tests"""
import hashlib, os, subprocess, sys, tempfile, unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import intake  # noqa: E402

A = "act.quiz.fraction-intro-01"
MF = f"content/activities/{A}/manifest.yaml"
HTML = f"content/activities/{A}/index.html"
JS = f"content/activities/{A}/questions.json"
F = "```"

YAML_BODY = f"id: {A}\ncontract: activity/1.1\n# END OF FILE\n"
HTML_BODY = "<!doctype html>\n<html><body><p>分蛋糕</p></body></html>\n<!-- END OF FILE -->\n"
JSON_BODY = '{"questions": [{"stem": "1/4 和 1/3 哪个大？"}]}\n'


def seg(k, n, body, first=False, last=False):
    head = f"=== CURIO 交付包 · 第 {k}/{n} 段 ===\n"
    meta = ""
    if first:
        meta = f"issue: #12\n任务: {A}\n实现者: 测试模型\n提示词版本: v1\n基于提交: abc1234\n轮次: 1\n\n## 文件清单\n- {MF}\n- {HTML}\n- {JS}\n\n## 文件\n\n"
    tail = "\n## 自查\n- [x] 都做了\n\n## 说明\n- 疑问：无\n\n=== END ===\n" if last else ""
    return head + meta + body + tail + f"=== 第 {k}/{n} 段完 ===\n"


def block(path, body, lang="yaml"):
    return f"### FILE: {path}\n{F}{lang}\n{body}{F}\n\n"


def full_package(yaml_body=YAML_BODY, html_body=HTML_BODY, json_body=JSON_BODY):
    s1 = seg(1, 2, block(MF, yaml_body) + block(HTML, html_body, "html"), first=True)
    s2 = seg(2, 2, block(JS, json_body, "json"), last=True)
    return s1, s2


class TestIntake(unittest.TestCase):
    def errors(self, r):
        return " | ".join(r.errors)

    def assertProblem(self, r, text):
        self.assertTrue(any(text in e for e in r.errors), f"本应报「{text}」，实际：{r.errors}")

    def test_complete_two_segment_package_passes(self):
        r = intake.intake(list(full_package()))
        self.assertEqual(r.errors, [], self.errors(r))
        self.assertEqual({f["path"] for f in r.files}, {MF, HTML, JS})
        self.assertEqual(r.meta["实现者"], "测试模型")
        sha = next(f["sha256"] for f in r.files if f["path"] == MF)
        self.assertEqual(sha, hashlib.sha256(YAML_BODY.encode()).hexdigest())

    def test_segments_in_any_order_and_same_hash(self):
        s1, s2 = full_package()
        a, b = intake.intake([s1, s2]), intake.intake([s2 + s1])
        self.assertEqual(b.errors, [])
        self.assertEqual(sorted(f["sha256"] for f in a.files), sorted(f["sha256"] for f in b.files))

    def test_missing_segment(self):
        s1, _ = full_package()
        self.assertProblem(intake.intake([s1]), "缺第 2/2 段")

    def test_duplicate_segment(self):
        s1, s2 = full_package()
        self.assertProblem(intake.intake([s1, s2, s2]), "第 2 段重复")

    def test_truncated_segment(self):
        s1, s2 = full_package()
        self.assertProblem(intake.intake([s1, s2.replace("=== 第 2/2 段完 ===\n", "")]), "可能被截断")

    def test_truncated_json(self):
        r = intake.intake(list(full_package(json_body='{"questions": [{"stem": "1/4 和\n')))
        self.assertProblem(r, "JSON 解析失败")

    def test_missing_end_marker(self):
        r = intake.intake(list(full_package(yaml_body=f"id: {A}\ncontract: activity/1.1\n")))
        self.assertProblem(r, "结束标记")

    def test_html_cut_off(self):
        r = intake.intake(list(full_package(html_body="<!doctype html>\n<html><body><p>分\n<!-- END OF FILE -->\n")))
        self.assertProblem(r, "</html>")

    def test_listed_but_not_delivered(self):
        s1 = seg(1, 1, block(MF, YAML_BODY) + block(HTML, HTML_BODY, "html"), first=True, last=True)
        self.assertProblem(intake.intake([s1]), f"清单里有 {JS}")

    def test_file_delivered_twice(self):
        s1 = seg(1, 2, block(MF, YAML_BODY) + block(HTML, HTML_BODY, "html"), first=True)
        s2 = seg(2, 2, block(JS, JSON_BODY, "json") + block(MF, YAML_BODY), last=True)
        self.assertProblem(intake.intake([s1, s2]), "交付了不止一次")

    def test_attachment_with_full_path_name_passes(self):
        s1 = seg(1, 1, block(MF, YAML_BODY) + block(JS, JSON_BODY, "json"), first=True, last=True)
        r = intake.intake([s1], [(HTML.replace("/", "__"), HTML_BODY.encode())])
        self.assertEqual(r.errors, [], self.errors(r))
        self.assertEqual(next(f["source"] for f in r.files if f["path"] == HTML), "附件")

    def test_attachment_with_bare_name_fails(self):
        s1 = seg(1, 1, block(MF, YAML_BODY) + block(JS, JSON_BODY, "json"), first=True, last=True)
        self.assertProblem(intake.intake([s1], [("index.html", HTML_BODY.encode())]), "必须是完整路径")

    def test_attachment_for_wrong_activity_is_caught(self):
        other = HTML.replace(A, "act.quiz.other").replace("/", "__")
        s1 = seg(1, 1, block(MF, YAML_BODY) + block(JS, JSON_BODY, "json"), first=True, last=True)
        r = intake.intake([s1], [(other, HTML_BODY.encode())])
        self.assertProblem(r, "清单里没有的文件")
        self.assertProblem(r, f"清单里有 {HTML}")

    def test_unsafe_path(self):
        s1 = seg(1, 1, block("../outside.yaml", YAML_BODY), first=True, last=True).replace(f"- {MF}\n- {HTML}\n- {JS}", "- ../outside.yaml")
        self.assertProblem(intake.intake([s1]), "不安全的路径")

    def test_missing_metadata(self):
        s1, s2 = full_package()
        self.assertProblem(intake.intake([s1.replace("实现者: 测试模型\n", ""), s2]), "缺少「实现者:」")

    def test_unsafe_paths_rejected(self):
        for bad in ["C:/x/a.yaml", "c:a.yaml", "//server/share/a.yaml", "a\\b.yaml", "content\\activities/a.yaml",
                    "a/./b.yaml", "a//b.yaml", "a/b/", "", ".", "a/../b.yaml", "a/b c.yaml"]:
            self.assertFalse(intake.safe_path(bad), bad)
        for good in [MF, HTML, "prompts/act.quiz.x.md"]:
            self.assertTrue(intake.safe_path(good), good)

    def test_windows_drive_path_in_list_fails(self):
        s1 = seg(1, 1, block("C:/Windows/evil.yaml", YAML_BODY), first=True, last=True).replace(f"- {MF}\n- {HTML}\n- {JS}", "- C:/Windows/evil.yaml")
        self.assertProblem(intake.intake([s1]), "不安全的路径")

    def test_symlink_escape_blocked_on_write(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            os.symlink(outside, Path(root) / "content")
            r = intake.intake(list(full_package()))
            self.assertEqual(r.errors, [])
            with self.assertRaises(ValueError):
                intake.write_files(r, root)
            self.assertEqual(list(Path(outside).rglob("*")), [], "不应写出任何文件")

    def test_zero_segments_is_an_error_not_a_crash(self):
        bad = "=== CURIO 交付包 · 第 0/0 段 ===\nissue: #1\n=== 第 0/0 段完 ===\n"
        self.assertProblem(intake.intake([bad]), "至少是 1")

    def test_segment_number_out_of_range(self):
        s1, s2 = full_package()
        s3 = s2.replace("第 2/2 段", "第 3/2 段")
        self.assertProblem(intake.intake([s1, s3]), "超出范围")

    def test_tail_total_mismatch(self):
        s1, s2 = full_package()
        self.assertProblem(intake.intake([s1, s2.replace("=== 第 2/2 段完 ===", "=== 第 2/3 段完 ===")]), "不一致")

    def test_all_metadata_required(self):
        s1, s2 = full_package()
        for line in ["基于提交: abc1234\n", "提示词版本: v1\n"]:
            self.assertProblem(intake.intake([s1.replace(line, ""), s2]), "第 1 段缺少")

    def test_metadata_formats(self):
        s1, s2 = full_package()
        for old, new, key in [("轮次: 1", "轮次: 0", "轮次"), ("轮次: 1", "轮次: 一", "轮次"),
                              ("基于提交: abc1234", "基于提交: main", "基于提交"), ("提示词版本: v1", "提示词版本: 1", "提示词版本"),
                              ("issue: #12", "issue: 12", "issue")]:
            self.assertProblem(intake.intake([s1.replace(old, new), s2]), f"「{key}:")

    def test_expected_commit_and_task(self):
        s1, s2 = full_package()
        self.assertEqual(intake.intake([s1, s2], expect={"基于提交": "abc1234def", "任务": A, "issue": "#12", "提示词版本": "v1"}).errors, [])
        self.assertProblem(intake.intake([s1, s2], expect={"基于提交": "fff0000"}), "任务文件要求是 fff0000")
        self.assertProblem(intake.intake([s1, s2], expect={"任务": "act.quiz.other"}), "任务文件要求是 act.quiz.other")

    def test_cli_write(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            s1, s2 = full_package()
            (d / "p1.md").write_text(s1, encoding="utf-8"); (d / "p2.md").write_text(s2, encoding="utf-8")
            p = subprocess.run([sys.executable, str(TOOLS / "intake.py"), str(d / "p1.md"), str(d / "p2.md"), "--write", str(d / "out")], capture_output=True)
            self.assertEqual(p.returncode, 0, p.stdout.decode("utf-8", "replace"))
            self.assertEqual((d / "out" / MF).read_text(encoding="utf-8"), YAML_BODY)


if __name__ == "__main__":
    unittest.main()
