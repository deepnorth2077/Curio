---
task: act.quiz.chromosome-intro-01
issue: 42
version: v1
---

# 任务：为知识点「染色体：把说明书卷好收起来」写一份挑战

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。孩子是飞船舰长，知识点是星图上的星星。讲解、挑战、反思都写成数据文件，由平台的通用引擎显示和判分，所以你的任务是**写内容**，不是写程序。

## 你的角色

熟悉 8 岁孩子常见错误想法的科学教育编辑，擅长出「错的选项正好戳中误区」的题，题目短、一题只问一件事

## 知识点卡（不要改动）

{{embed: content/nodes/life/biology.genetics.chromosome-intro.yaml}}

## 这份活动要做到什么

字段照下面填：`schema: activity-def/1`、`kind: quiz`、`version: 1`、`targets: [biology.genetics.chromosome-intro]`、`age_band: G3-4`、`duration_min: 5`、`review: pending`、`engine: 1`；`body.shuffle` 写 `true`。`title` 不超过 20 个字。`sources` 从下面「事实和出处」表里挑你用到的，照抄。

**题目**：7～9 道。其中恰好 2 道数字题，其余选择题：
- 「人的体细胞里一般有多少条染色体？」：`type: number`，`value: 46`，`common_wrong` 至少写 `{value: 23}`，`feedback` 说清 23 是对数；
- 「这些染色体配成多少对？」：`type: number`，`value: 23`，`common_wrong` 至少写 `{value: 46}`。
这两道题的提示**特别容易**泄露答案：考 46 的那道，提示里不能出现 46 和「四十六」；考 23 的那道，提示里不能出现 23 和「二十三」。可以用「两两配对」「数一数」这样的说法。

知识点卡的 6 条目标，每条至少有一道题考到。

**误区全覆盖（必须做到，CI 会算）**：知识点卡里的每个误区，都至少被一道题的错误选项（或数字题的 `common_wrong`）引用。本颗星的误区是：`bigger-more`、`more-is-smarter`、`chromosome-is-gene`、`from-one-parent`、`y-from-mother`、`same-in-boys-girls`（共 6 个）。引用时直接写误区 id，例如 `y-from-mother`。能对应误区的错误选项都标上；对应不上的不硬标。

**每道题**：
- 题干不超过 80 个字，一次只问一件事；不用配图，用文字说清楚。
- 选择题 3 个选项（最多 4 个），恰好一个正确；错误选项要像孩子真会选的答案，不出明显凑数的选项。每个错误选项都写 `feedback`，按「领航员怎么说话」里「答错时先接住」的写法。
- 提示 1～3 条，一条比一条具体，最后一条也不说出答案：选择题的提示里不出现正确选项的原文；数字题的提示里不出现正确答案的数字（阿拉伯数字和汉字都不行）。
- 题目只考知识点卡「目标」里的内容，用词只用「词表」里本颗星和前面几颗星的词。**讲解由另一个人写，你看不到**，所以不要假设讲解里讲过表里没有的例子。
- 题目 id 写 `q1`、`q2`……，不重复。

## 星座的共同约定

本星座几个活动由不同的人分头写。下面几节是共同约定，必须遵守。

{{embed: docs/constellations/life-manual.md#星座概况}}

{{embed: docs/constellations/life-manual.md#领航员怎么说话}}

{{embed: docs/constellations/life-manual.md#词表}}

{{embed: docs/constellations/life-manual.md#事实和出处}}

## 写给孩子的内容要求

{{embed: docs/standards.md#给孩子看的内容}}

另外：
- 句子短，说具体的事，不出现「学习」二字。
- 科学事实要有出处，写在活动的 `sources` 里。
- 简化的讲法不能和以后要教的内容矛盾，例如可以说「大约」「一般」，不能说错。

## 内容格式（必须遵守）

{{embed: docs/specs/content.md}}

{{embed: schemas/activity-def.schema.json}}

## 术语表

{{embed: GLOSSARY.md#给孩子看的世界}}

{{embed: GLOSSARY.md#内容}}

{{embed: GLOSSARY.md#协作}}

## 配图

不需要。不要交 SVG 文件，步骤或题目里也不要引用配图。

配图存为 `content/assets/<知识点 id>/<文件名>.svg`，按内容规格 3.6 的白名单写：手绘风格的线条和淡彩色块，不用 `<style>` 和 `style` 属性，颜色写在 `fill`、`stroke` 属性里；`viewBox` 写好，不写死 `width`、`height`。

## 怎么自己验证

- 能运行代码的话：用 Python 的 jsonschema（Draft 2020-12）拿上面的 schema 校验你的 `activity.yaml`，必须通过。
- 逐条核对内容规格第 5 节的校验规则：题目 id 唯一、`shaded` 不超过 `parts`、提示不说出答案、误区引用出自知识点卡、文字长度。
- 把每个科学事实和出处对一遍。

## 验收标准

- [ ] `activity.yaml` 通过 schema 校验，满足内容规格第 5 节的规则
- [ ] 每个科学事实都和 `sources` 里的出处对过；没有编造出处，也没有和知识点卡矛盾的说法
- [ ] 7～9 道题：2 道数字题（答案 46、23），其余选择题，`shuffle: true`
- [ ] 6 个误区全部被引用（预期覆盖集合：`bigger-more`、`more-is-smarter`、`chromosome-is-gene`、`from-one-parent`、`y-from-mother`、`same-in-boys-girls`）
- [ ] 6 条目标每条至少一道题
- [ ] 数字题的提示里没有自己的答案（阿拉伯数字和汉字都没有）；选择题提示里不出现正确选项原文
- [ ] 说性别时都带「一般」；没有把「像谁」说成长相一半一半
- [ ] 题干、选项、提示只用「词表」里三颗星的词

## 交付格式（必须遵守）

本任务的文件清单：
- `content/activities/act.quiz.chromosome-intro-01/activity.yaml`

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。所有文件都写在交付包文字里。分段时，**每一段的第一行都必须是段首标记**。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
