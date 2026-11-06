"""tools/make_task.py 的正反测试。运行：python -m unittest discover -s tools/tests"""
import hashlib, os, subprocess, sys, tempfile, unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import make_task  # noqa: E402

FRONT = "---\ntask: curio-002a\nissue: 16\nversion: v1\n---\n"
SUBMISSION = (
    "# 交付包格式\n\n前言\n\n## 格式\n\n示例：\n\n"
    "`````\n## 文件清单\n- a.yaml\n`````\n\n"
    "```\n## 不是标题\n```\n\n格式结尾\n\n## 规则\n\n1. 规则一\n\n## 其他\n\n不要的内容\n"
)
SPEC = "# 规格\n\n正文里有 ``` 三个反引号，也有 {{不是指令}} 和 {{commit}}。\n"


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class Repo:
    """临时 git 仓库，带 refs/remotes/origin/main。"""

    def __init__(self, files):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        sh(self.path, "git", "init", "-q", "-b", "main")
        sh(self.path, "git", "config", "user.email", "t@example.com")
        sh(self.path, "git", "config", "user.name", "t")
        self.commit(files)
        sh(self.path, "git", "update-ref", "refs/remotes/origin/main", "HEAD")

    def commit(self, files):
        for p, text in files.items():
            f = self.path / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        sh(self.path, "git", "add", "-A")
        sh(self.path, "git", "commit", "-q", "-m", "c")
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.path, capture_output=True, text=True).stdout.strip()

    def build(self, task="curio-002a", **kw):
        return make_task.build(str(self.path), task, **kw)


def base(prompt_body):
    return {"docs/submission.md": SUBMISSION, "docs/specs/content.md": SPEC,
            "prompts/curio-002a.md": FRONT + prompt_body}


class TestMakeTask(unittest.TestCase):
    def setUp(self):
        self.repos = []

    def tearDown(self):
        for r in self.repos:
            r.tmp.cleanup()

    def repo(self, body):
        r = Repo(base(body))
        self.repos.append(r)
        return r

    def assertFails(self, fn, text):
        with self.assertRaises(make_task.TaskError) as cm:
            fn()
        self.assertIn(text, str(cm.exception))

    # ---- 正例 ----
    def test_expands_commit_and_embeds(self):
        r = self.repo("提交 {{commit}}\n\n{{embed: docs/specs/content.md}}\n")
        text, full, expect = r.build()
        self.assertIn(f"提交 {full}", text)
        self.assertIn(f"基于 Curio 仓库提交 `{full}`", text)
        self.assertIn("{{不是指令}} 和 {{commit}}", text)  # 嵌入的内容不再展开
        self.assertIn("````text\n# 规格", text)  # 围栏比内容里的反引号长
        sha = hashlib.sha256(SPEC.encode()).hexdigest()
        self.assertIn(f"| `docs/specs/content.md` | 全文 | `{sha}` |", text)
        self.assertEqual(expect, ["--expect-issue", "#16", "--expect-task", "curio-002a", "--expect-commit", full, "--expect-version", "v1"])

    def test_section_skips_headings_inside_code_blocks(self):
        r = self.repo("{{embed: docs/submission.md#格式}}\n")
        text, _, _ = r.build()
        self.assertIn("## 格式", text)
        self.assertIn("## 不是标题", text)
        self.assertIn("格式结尾", text)
        self.assertNotIn("规则一", text)
        self.assertIn("「格式」一节", text)
        self.assertIn("``````text\n## 格式", text)  # 内容里有 5 个反引号的围栏，外层要用 6 个

    def test_last_section_runs_to_end(self):
        r = self.repo("{{embed: docs/submission.md#其他}}\n")
        self.assertIn("不要的内容", r.build()[0])

    def test_reads_from_commit_not_worktree(self):
        r = self.repo("{{embed: docs/specs/content.md}}\n")
        (r.path / "docs/specs/content.md").write_text("工作区里没提交的改动\n", encoding="utf-8")
        self.assertNotIn("没提交的改动", r.build()[0])

    def test_cli_writes_file(self):
        r = self.repo("{{commit}}\n")
        with tempfile.TemporaryDirectory() as out:
            p = subprocess.run([sys.executable, str(TOOLS / "make_task.py"), "curio-002a", "--repo", str(r.path), "--out", out],
                               capture_output=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
            self.assertTrue((Path(out) / "curio-002a.task.md").exists())
            self.assertIn("--expect-commit", p.stdout.decode("utf-8"))

    # ---- 反例 ----
    def test_unknown_directive(self):
        self.assertFails(lambda: self.repo("{{提交号}}\n").build(), "不认识的指令")

    def test_missing_file(self):
        self.assertFails(lambda: self.repo("{{embed: docs/nope.md}}\n").build(), "没有文件 docs/nope.md")

    def test_missing_section(self):
        self.assertFails(lambda: self.repo("{{embed: docs/submission.md#不存在}}\n").build(), "找不到二级标题")

    def test_heading_inside_code_block_is_not_a_section(self):
        self.assertFails(lambda: self.repo("{{embed: docs/submission.md#不是标题}}\n").build(), "找不到二级标题")

    def test_missing_front_matter(self):
        r = Repo({"prompts/curio-002a.md": "没有头\n"}); self.repos.append(r)
        self.assertFails(r.build, "YAML 头")

    def test_front_matter_task_mismatch(self):
        r = Repo({"prompts/curio-002a.md": FRONT.replace("curio-002a", "curio-002b") + "x\n"}); self.repos.append(r)
        self.assertFails(r.build, "和文件名不一致")

    def test_front_matter_bad_issue_and_version(self):
        r = Repo({"prompts/curio-002a.md": FRONT.replace("issue: 16", "issue: #16") + "x\n"}); self.repos.append(r)
        self.assertFails(r.build, "issue 应该是数字")
        r2 = Repo({"prompts/curio-002a.md": FRONT.replace("version: v1", "version: 1") + "x\n"}); self.repos.append(r2)
        self.assertFails(r2.build, "version 应该像 v1")

    def test_review_task_id(self):
        r = Repo({"prompts/review.specs.md": FRONT.replace("curio-002a", "review.specs") + "{{commit}}\n"}); self.repos.append(r)
        text = r.build(task="review.specs")[0]
        self.assertIn("任务 `review.specs`", text)
        self.assertNotIn("交付包开头信息", text)  # 审阅任务不交交付包
        self.assertIn("交付包开头信息请照抄：`issue: #16`", self.repo("x\n").build()[0])

    def test_bad_task_id(self):
        self.assertFails(lambda: self.repo("x\n").build(task="../etc"), "格式不对")

    def test_commit_not_on_main_requires_draft(self):
        r = self.repo("{{commit}}\n")
        r.commit({"prompts/curio-002a.md": FRONT + "新版 {{commit}}\n"})
        self.assertFails(r.build, "还没有合入 main")
        text, _, _ = r.build(draft=True)
        self.assertIn("新版", text)

    def test_missing_origin_main(self):
        r = self.repo("x\n")
        sh(r.path, "git", "update-ref", "-d", "refs/remotes/origin/main")
        self.assertFails(r.build, "没有 origin/main")

    def test_crlf_rejected(self):
        r = Repo({"prompts/curio-002a.md": FRONT + "{{embed: docs/a.md}}\n", "docs/a.md": b"a\r\nb\r\n"}); self.repos.append(r)
        self.assertFails(r.build, "CR")


if __name__ == "__main__":
    unittest.main()
