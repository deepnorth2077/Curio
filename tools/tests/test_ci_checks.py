"""tools/ci_checks.py 的正反测试。运行：python -m unittest discover -s tools/tests"""
import os, shutil, subprocess, sys, tempfile, textwrap, unittest
from pathlib import Path

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


def activity(aid, targets, type_="quiz", review="pending", mis=(), extra=""):
    return textwrap.dedent(f"""\
        id: {aid}
        contract: activity/1.1
        type: {type_}
        title: 测试活动
        targets: [{', '.join(targets)}]
        age_band: G3-4
        entry: index.html
        pedagogy: hint-ladder
        emits: [started, answered]
        review: {review}
        misconceptions: [{', '.join(mis)}]
        """) + extra


class Repo:
    """临时 git 仓库：main 上放好基线，再在分支上改。"""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="curio-ci-"))
        shutil.copytree(REPO / "schemas", self.dir / "schemas")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "测试")

    def git(self, *args):
        p = subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True, encoding="utf-8")
        if p.returncode != 0:
            raise RuntimeError(p.stderr)
        return p.stdout

    def write(self, path, text):
        f = self.dir / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

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

    def ok(self, res):
        self.assertEqual(res.errors, [], f"本应通过，却报错：{res.errors}")

    def fails(self, res, text):
        msgs = [m for _, m in res.errors]
        self.assertTrue(any(text in m for m in msgs), f"本应报「{text}」，实际：{msgs}")

    def add_html(self, aid, body="<p>分蛋糕</p>"):
        self.r.write(f"content/activities/{aid}/index.html", f"<!doctype html><html><body>{body}</body></html>\n")

    def published_set(self, review="approved", types=("explain", "quiz"), cover=("denominator-bigger",)):
        acts = [f"act.{t}.frac-{i}" for i, t in enumerate(types)]
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, status="published", activities=acts, mis=("denominator-bigger",)))
        for i, (a, t) in enumerate(zip(acts, types)):
            self.r.write(f"content/activities/{a}/manifest.yaml", activity(a, [N2], type_=t, review=review, mis=cover if i == len(acts) - 1 else ()))
            self.add_html(a)
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
        res = self.r.check()
        self.assertEqual(sum("不能改这个文件" in m for _, m in res.errors), 2)

    def test_feat_may_touch_prototype(self):
        self.r.baseline(); self.r.branch("feat/x"); self.r.write("prototype/index.html", "<html></html>"); self.r.commit()
        self.ok(self.r.check())

    def test_override_label_turns_error_into_warning(self):
        self.r.baseline(); self.r.branch("feat/x"); self.r.write("docs/a.md", "x"); self.r.commit()
        res = self.r.check(labels={"越界-已批准"})
        self.ok(res)
        self.assertTrue(any("越界改动" in m for _, m in res.warnings))


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
        self.r.write(f"content/activities/{acts[0]}/index.html", "<!doctype html><html><body>新版</body></html>\n"); self.r.commit()
        self.ok(self.r.check())

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
        res = self.r.check()
        self.fails(res, "共享活动")
        self.assertTrue(any(N1 in m for _, m in res.errors), "错误信息应列出受影响的其他知识点")

    def test_shared_activity_with_override_lists_affected_nodes(self):
        res = self.r.check(labels={"越界-已批准"})
        self.ok(res)
        self.assertTrue(any("共享活动改动" in m and N1 in m and N2 in m for _, m in res.warnings))


class TestReferences(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/refs")

    def test_node_lists_activity_that_does_not_target_it(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"]))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N1]))
        self.add_html("act.quiz.a"); self.r.commit()
        res = self.r.check()
        self.fails(res, "两边要互相写上")

    def test_activity_targets_node_that_does_not_list_it(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2]))
        self.add_html("act.quiz.a"); self.r.commit()
        self.fails(self.r.check(), "两边要互相写上")

    def test_missing_prerequisite_and_cycle(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, prereq=[N2]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, prereq=[N1, "math.number.nope"])); self.r.commit()
        res = self.r.check()
        self.fails(res, "不存在的知识点")
        self.fails(res, "有环")

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


class TestPublishGate(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/publish")

    def test_complete_published_node_passes(self):
        self.published_set(); self.r.commit()
        self.ok(self.r.check())

    def test_published_with_pending_activity_fails(self):
        self.published_set(review="pending"); self.r.commit()
        self.fails(self.r.check(), "只能引用已批准")

    def test_published_without_quiz_fails(self):
        self.published_set(types=("explain",)); self.r.commit()
        self.fails(self.r.check(), "至少有一个 quiz")

    def test_published_with_uncovered_misconception_fails(self):
        self.published_set(cover=()); self.r.commit()
        self.fails(self.r.check(), "还没有任何活动针对")


class TestIdsCopyTrailers(Base):
    def test_changing_id_fails(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch("arch/rename"); self.r.write(f"{NODE_DIR}/{N2}.yaml", node("math.number.fraction-renamed")); self.r.commit()
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
        res = self.r.check()
        self.ok(res)
        self.assertTrue(any("没有署名" in m for _, m in res.warnings))

    def test_trailer_present_no_warning(self):
        self.r.baseline(); self.r.branch("arch/x"); self.r.write("docs/a.md", "x"); self.r.commit()
        self.assertFalse(any("没有署名" in m for _, m in self.r.check().warnings))


class TestCli(Base):
    def test_chinese_commit_under_c_locale_does_not_crash(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, dq="中文改动？")); self.r.commit("中文标题\n\n中文正文，带「引号」。\n\nImplemented-By: 测试模型")
        env = {k: v for k, v in os.environ.items() if k not in ("LANG", "LC_ALL", "PYTHONIOENCODING", "PYTHONUTF8")}
        # 关掉 Python 的 UTF-8 模式和 C 区域强制转换，模拟真正的非 UTF-8 环境（例如 Windows 的 GBK）
        env.update(LANG="C", LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", BASE_REF="main", HEAD_BRANCH=f"kp/{N2}")
        p0 = subprocess.run([sys.executable, "-c", "import locale;print(locale.getpreferredencoding(False))"], capture_output=True, text=True, env=env)
        self.assertNotIn("utf", p0.stdout.lower(), "测试环境没能切到非 UTF-8")
        p = subprocess.run([sys.executable, str(TOOLS / "ci_checks.py"), str(self.r.dir)], capture_output=True, env=env)
        out = p.stdout.decode("utf-8", errors="replace") + p.stderr.decode("utf-8", errors="replace")
        self.assertNotIn("Traceback", out)
        self.assertEqual(p.returncode, 0, out)

    def test_missing_base_exits_2(self):
        self.r.commit("只有一个提交")
        env = dict(os.environ, BASE_REF="main", HEAD_BRANCH="arch/x")
        p = subprocess.run([sys.executable, str(TOOLS / "ci_checks.py"), str(self.r.dir)], capture_output=True, env=env)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
