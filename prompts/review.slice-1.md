---
task: review.slice-1
issue: 24
version: v1
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

## 你的角色

资深后端和测试工程师，熟悉事件溯源、幂等、JSON 在不同语言之间的差异。请挑刺，不要客气。**请亲手复算向量**，不要只看说明。

## 请重点看这些问题

1. **向量的期望值对不对**。每个向量都有 `worked`（手算过程），每个特殊输入有 `why`。请逐个复算：
   - 摄入：每一项的 `expect` 是否符合规格第 3 节的判断顺序（尤其是「不合格」在「重复、冲突」之前判断这一点带来的结果）；
   - 掌握度：每次尝试合法不合法、违反的是第几条规则（取编号最小的）、首答成绩、`best` 的选法、`state`；
   - 判分：每一条 `expect`。
   哪条算错了，请写明向量文件、第几项、你算出的结果和理由。
2. **规格有没有没写清、写错的地方**：实现 AI 只看得到任务文件，照着规格写代码时，哪里可能写出两种都「符合规格」但结果不同的实现？特别是：数值规则（事件规格第 2 节）在 JavaScript 里怎么判断小数位数；「整数」的意思（`1.0`）；语义相同的比较；合法性第 4 条「只有一条 started」的补充；`best` 在正确率相同时取题数多的；`nodes` 列出哪些知识点。
3. **和事件规格的一致性**：切片规格对事件规格 5.2、6.3、6.4 的收窄和补充（见切片规格最后一节）合不合理？有没有和事件规格冲突的地方？
4. **向量覆盖得够不够**：对照事件规格第 9 节和切片规格，还缺哪些能发现实现错误的场景？有没有向量其实测不出它声称要测的东西？
5. **`.json` 旁路文件**：不进清单、不参与哈希，外壳却直接读它，这样做的风险是什么？（例如：怎么保证读到的 JSON 和审核过的 YAML 一致。）值得为此改清单格式吗？
6. **「1/1 会点亮」**：内核不读发布包，首答正确率的分母是「作答过的题数」，所以只答一道就完成会被算成 1/1 点亮。规格把责任交给外壳（等每道题都有结果才写 completed）。这样处理可以吗？还是应该在事件或投影里防住？
7. **任务大小**：这份规格会变成一个任务交给一个实现 AI，一次交付包含内核、引擎、页面和测试。会不会太大？如果太大，按 ADR-009「缩窄行为、不按层切」应该怎么缩？

## 资料

以下文件全部取自本 PR 的提交，原样贴入。

{{embed: docs/specs/slice-1.md}}

{{embed: docs/specs/events.md#2. 事件信封（event/2）}}

{{embed: docs/specs/events.md#5. 摄入}}

{{embed: docs/specs/events.md#6. 投影}}

{{embed: docs/specs/events.md#9. 黄金向量}}

{{embed: docs/specs/content.md#3. 结构化活动（activity-def/1）}}

{{embed: docs/specs/content.md#6. 不可变发布（release/1）}}

{{embed: schemas/event.schema.json}}

{{embed: kernel/vectors/mastery-lit-basic.json}}

{{embed: kernel/vectors/mastery-not-lit.json}}

{{embed: kernel/vectors/mastery-order-free.json}}

{{embed: kernel/vectors/mastery-two-devices.json}}

{{embed: kernel/vectors/mastery-best-of-many.json}}

{{embed: kernel/vectors/mastery-kinds-and-nodes.json}}

{{embed: kernel/vectors/attempt-inconsistent.json}}

{{embed: kernel/vectors/ingest-duplicates-conflicts.json}}

{{embed: kernel/vectors/ingest-invalid.json}}

{{embed: engine/vectors/grading.json}}

{{embed: tools/tests/fixtures/content/activities/act.quiz.fraction-intro-01/activity.yaml}}

{{embed: tools/build_release.py}}

## 输出格式

用简体中文，按下面的格式输出，不要写补丁，说清楚问题和建议即可：

```
# 审阅意见 · 竖切片 1 · 审阅者：<模型名和版本>

## 结论
可以合入 / 改完再合入 / 需要大改（一句话说明）

## 向量复算
<逐个向量写：复算结果一致，或者哪一项不一致、你的结果和理由>

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
