---
task: review.kp-assets
issue: 46
version: v1
---

# 审阅任务：「好奇号」CI 的两处地盘规则改动

## 背景

「好奇号 Curio」是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。仓库只有一个维护者 Claude；其他 AI 只按 Claude 写的任务文件做实现，碰不到仓库；Luka（家长，不写代码）负责传话和验收。

每个 PR 都会跑 `tools/ci_checks.py`。其中「地盘检查」按分支名限制能改哪些文件：`kp/<知识点 id>` 分支只能改这个知识点自己的东西，`arch/` 分支能改受保护的文件（规格、schema、工具、模板）。

PR #46 改了两处：

1. **知识点的配图**：讲解要用 SVG 配图，规定存放在 `content/assets/<知识点 id>/` 下（`docs/workflow.md`）。原来 `kp/` 分支一律不能改 `content/assets/`，配图放不进来。现在允许 `kp/<知识点 id>` 分支改 `content/assets/<知识点 id>/` 下的文件，别的知识点的配图、`content/assets/` 根目录下的文件仍然不行。
2. **内容任务模板**：`prompts/content-template.md` 是写讲解、挑战、反思任务用的模板，原来不在受保护路径里，`feat/` 之类的分支也能改。现在加进受保护路径，和另外两个模板一样，只有 `arch/` 分支能改。

同时把 `docs/collaboration.md`「CI 检查什么」一节按目前的实际规则重写了。Claude 写的改动不能自己审，所以请你来审。

## 你的角色

严谨的代码审阅者，熟悉 Python 和 git，擅长找边界情况和绕过规则的写法。请挑刺，不要客气。

## 请重点看这些问题

1. **能不能绕过**：`kp/` 分支的配图规则，有没有办法改到别的知识点的配图？例如知识点 id 是另一个 id 的前缀（`a.b` 和 `a.b-c`）、改名（git 的重命名会同时检查新旧两个路径）、路径里有 `..`、大小写不同、深层子目录。
2. **会不会误伤**：合理的写法会不会被拦下？例如知识点卡还没合入、只在本分支新建时放配图；删掉自己的旧配图。
3. **测试够不够**：新加的 3 个测试，能不能发现规则被改坏（例如把「`parts[2] == node_id`」改成「以 node_id 开头」，或者把 `content-template.md` 从受保护列表里拿掉）？还缺什么测试？
4. **文档和代码一致吗**：重写后的「CI 检查什么」表，每一行是不是都和 `tools/ci_checks.py` 的实际行为一致？有没有写多了、写少了、写错了的？
5. **还有没有该保护却没保护的**：例如 `docs/constellations/`、`prompts/review.*.md`、`prompts/` 下 Claude 写的平台任务提示词。

## 资料

以下文件取自 PR #46 的提交，原样贴入。

### 改动后的 CI 脚本（完整文件）

{{embed: tools/ci_checks.py}}

### 测试的改动（diff）

```diff
diff --git a/tools/tests/test_ci_checks.py b/tools/tests/test_ci_checks.py
index ab15652..82b17fe 100644
--- a/tools/tests/test_ci_checks.py
+++ b/tools/tests/test_ci_checks.py
@@ -158,6 +158,7 @@ class Repo:
 
 
 N1, N2 = "math.number.division-meaning", "math.number.fraction-intro"
+SVG_OK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#CCD6C0"/></svg>\n'
 NODE_DIR = "content/nodes/num"
 
 
@@ -213,6 +214,12 @@ class TestBranches(Base):
         self.r.branch("arch/glossary"); self.r.write("GLOSSARY.md", "y"); self.r.commit()
         self.ok(self.r.check())
 
+    def test_content_template_only_on_arch(self):
+        self.r.baseline(); self.r.branch("feat/x"); self.r.write("prompts/content-template.md", "x"); self.r.commit()
+        self.fails(self.r.check(), "不能改这个文件")
+        self.r.branch("arch/template"); self.r.write("prompts/content-template.md", "y"); self.r.commit()
+        self.ok(self.r.check())
+
     def test_feat_may_touch_prototype(self):
         self.r.baseline(); self.r.branch("feat/x"); self.r.write("prototype/index.html", "<html></html>"); self.r.commit()
         self.ok(self.r.check())
@@ -275,6 +282,22 @@ class TestKnowledgePointBranch(Base):
         self.r.write("content/activities/act.quiz.frac/activity.yaml", structured("act.quiz.frac", [N2])); self.r.commit()
         self.ok(self.r.check())
 
+    def test_kp_branch_may_add_assets_under_own_node(self):
+        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
+        self.r.branch(f"kp/{N2}")
+        self.r.write(f"content/assets/{N2}/cake.svg", SVG_OK)
+        self.r.write(f"content/assets/{N2}/parts/half.svg", SVG_OK); self.r.commit()
+        self.ok(self.r.check())
+
+    def test_kp_branch_may_not_touch_assets_of_other_node_or_outside_node_folder(self):
+        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1)); self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
+        self.r.branch(f"kp/{N2}")
+        self.r.write(f"content/assets/{N1}/cake.svg", SVG_OK)
+        self.r.write("content/assets/cake.svg", SVG_OK)
+        self.r.write(f"content/assets/{N2}x/cake.svg", SVG_OK); self.r.commit()
+        result = self.r.check()
+        self.assertEqual(sum("不能改这个文件" in message for _, message in result.errors), 3)
+
     def test_prompt_of_other_activity_fails(self):
         self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=["act.quiz.other"]))
         self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
```

### 改动后的协作文档里的 CI 一节

{{embed: docs/collaboration.md#CI 检查什么}}

### 知识点工作流（配图放在哪里）

{{embed: docs/workflow.md}}

## 输出格式

用简体中文，按下面的格式输出，不要写补丁，说清楚问题和建议即可：

```
# 审阅意见 · PR #46 · 审阅者：<模型名和版本>

## 结论
可以合入 / 改完再合入 / 需要大改（一句话说明）

## 问题
### 1. <一句话标题>
- 严重程度：阻断 / 重要 / 建议
- 位置：<文件和位置>
- 问题：<具体说明，能绕过的请给出具体的分支名和文件路径>
- 建议：<怎么改>

## 其他
<可以没有>
```

「阻断」只用于：照现在的写法，会让不该改的文件被改掉，或者让正常的知识点工作流卡住。
