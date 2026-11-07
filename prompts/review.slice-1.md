---
task: review.slice-1
issue: 24
version: v2
---

# 审阅任务：「好奇号」竖切片 1 的规格和手算黄金向量

## 背景

「好奇号 Curio」是一个家庭自用的理科探索网站，陪一个孩子从 2026 年小学三年级用到 2036 年高三。仓库只有一个维护者 Claude；其他 AI 只按 Claude 写的任务文件做实现，碰不到仓库；Luka（家长，不写代码）负责传话和验收。

内容格式、事件格式（event/2）、发布构建器都已经合入。下一步是第一条「竖切片」：孩子在网页上做完一组分数挑战，每次作答记成事件存进浏览器，从事件算出掌握度，首答正确率达到 0.8 时星星点亮，刷新后还亮着。

派发给实现 AI 之前，Claude 写了：
1. 切片规格 `docs/specs/slice-1.md`：模块、接口，以及摄入、掌握度、判分三套规则的精确写法；
2. 内容规格 6.3 的修改：构建器在每个 YAML 旁边多写一份 `.json`（浏览器没有 YAML 解析器），以及构建器的实现；
3. **黄金向量**：`kernel/vectors/*.json`（摄入和掌握度）、`engine/vectors/grading.json`（判分）。期望值是 Claude 按规格**手算**的，实现 AI 交来的代码必须全部通过。向量错了，以后实现就会照着错的标准做，所以这是这次审阅最重要的部分。

Claude 写的架构改动不能自己审，所以请你来审。

**这是第 2 轮。**第 1 轮由另一个模型审阅，提了 2 条阻断、5 条重要、2 条建议，向量的期望值复算全部一致。Claude 的逐条答复和第 1 轮原文在 `docs/reviews/pr-60.md`（下面资料里有）。这一轮请重点看**改过的地方**是否真的解决了问题、有没有引入新问题；没改的部分不必重新逐条复算，除非你发现了新疑点。

## 你的角色

资深后端和测试工程师，熟悉事件溯源、幂等、JSON 在不同语言之间的差异。请挑刺，不要客气。**请亲手复算向量**，不要只看说明。

## 请重点看这些问题

1. **两条阻断改得对不对**：
   - 「看答案让五题挑战算成 1/1」：1a 去掉提示和看答案，由 `quiz.js` 状态机保证「每道题都有存好的作答」才产出 `attempt.completed`（切片规格 6.1）。这条规则能用状态机的测试验收吗？1b 的「看答案要先有一次存好的作答」够不够？
   - 「写库失败后重试被判成重复」：改成 `log.check` 不改状态，`commitEvent` 在 IndexedDB 事务提交完成后才 `ingest`（6.2）；重试用同一条原始文字；收件表存接收的和隔离的原始文字，启动时按到达顺序重放。还有哪种失败顺序会留下多余或缺失的事实？（例如事务提交了、但页面在 `ingest` 之前关掉；`check` 和 `ingest` 之间日志被别的东西改了。）`app/test/commit.test.js` 的三种失败场景够不够？
2. **单窗口锁**（6.3）：用 `navigator.locks` 的 `ifAvailable` 拿锁，拿不到就只读。iPad 上的 Safari、页面进入后台、锁被浏览器回收时会怎样？有没有更简单可靠的做法？
3. **清单绑定 JSON**（内容规格 6.2、6.3，`schemas/release.schema.json`，`tools/build_release.py`）：每个 YAML 条目带 `json: {path, sha256, bytes}` 并参与 `content_hash`，外壳重算 `content_hash`、逐个核对 JSON 的哈希。`release/1` 还没发布过，所以直接改定义、不升版本，这样处理可以吗？外壳用 JavaScript 重算规范 JSON 时有没有坑？构建器「只读一次、先写临时目录再改名、非空目录拒绝」写得对吗，测试（`TestWriteFromSnapshot`）测得到吗？
4. **新加的向量**：`numbers.json`、`ingest-code-points`、`mastery-best-ratio`、`mastery-best-tie-order`、`mastery-zero-score`、`mastery-seq-order`、`mastery-batches`、`attempt-multi-rule`，以及 `grading.json` 新加的 11 条。请**亲手复算**这些新向量的期望值，并看它们是否真能分辨出第 1 轮列的那些错误算法（`tools/tests/test_vectors.py` 里的 `TestVectorsCatchWrongAlgorithms` 是 Claude 的自证，请你独立判断）。
5. **执行器的新规则**（切片规格第 7 节）：先 `check` 再 `ingest` 两个结果都比；`mastery_after` 在批次边界投影；`log.raw()` 必须正好等于标成接收的原始文字。有没有写得让实现 AI 理解出两种做法的地方？
6. **字符串规则**（第 5 节和第 1 节）：长度按码点数；判分只去 7 种空白。这两条在 JavaScript 和 Python 里能写出一样的结果吗？还缺什么边界？
7. **任务拆分**：1a 只做选择题、但 `grade.js` 三种题型都在 1a 里（理由见 `docs/reviews/pr-60.md` 最后几行）。这个部分采纳合理吗？1a 还是太大吗？
8. **文档之间有没有矛盾**：切片规格、事件规格 6.3 的补充、内容规格 6.2/6.3、release schema 之间，还有没有说法不一致的地方？

## 资料

以下文件全部取自本 PR 的提交，原样贴入。

{{embed: docs/reviews/pr-60.md}}

{{embed: docs/specs/slice-1.md}}

{{embed: docs/specs/events.md#2. 事件信封（event/2）}}

{{embed: docs/specs/events.md#5. 摄入}}

{{embed: docs/specs/events.md#6. 投影}}

{{embed: docs/specs/events.md#9. 黄金向量}}

{{embed: docs/specs/content.md#3. 结构化活动（activity-def/1）}}

{{embed: docs/specs/content.md#6. 不可变发布（release/1）}}

{{embed: schemas/event.schema.json}}

{{embed: schemas/release.schema.json}}

{{embed: kernel/vectors/numbers.json}}

{{embed: kernel/vectors/ingest-code-points.json}}

{{embed: kernel/vectors/mastery-best-ratio.json}}

{{embed: kernel/vectors/mastery-best-tie-order.json}}

{{embed: kernel/vectors/mastery-zero-score.json}}

{{embed: kernel/vectors/mastery-seq-order.json}}

{{embed: kernel/vectors/mastery-batches.json}}

{{embed: kernel/vectors/attempt-multi-rule.json}}

{{embed: engine/vectors/grading.json}}

{{embed: tools/tests/fixtures/content/activities/act.quiz.fraction-intro-01/activity.yaml}}

{{embed: tools/build_release.py}}

{{embed: tools/tests/test_build_release.py}}

{{embed: tools/tests/test_vectors.py}}

## 输出格式

用简体中文，按下面的格式输出，不要写补丁，说清楚问题和建议即可：

```
# 审阅意见 · 竖切片 1 · 第 2 轮 · 审阅者：<模型名和版本>

## 结论
可以合入 / 改完再合入 / 需要大改（一句话说明）

## 向量复算
<新加的向量逐个写：复算结果一致，或者哪一项不一致、你的结果和理由>

## 问题
### 1. <一句话标题>
- 严重程度：阻断 / 重要 / 建议
- 位置：<文件和章节>
- 问题：<具体说明>
- 建议：<怎么改>

## 其他
<可以没有>
```

「阻断」只用于：照现在的写法派发，会让实现 AI 照着错的标准写代码，或者以后很难纠正的问题。向量里任何一个算错的期望值都算阻断。
