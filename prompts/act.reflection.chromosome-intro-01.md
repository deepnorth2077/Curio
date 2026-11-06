---
task: act.reflection.chromosome-intro-01
issue: 43
version: v1
---

# 任务：为知识点「染色体：把说明书卷好收起来」写一份反思

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。孩子是飞船舰长，知识点是星图上的星星。讲解、挑战、反思都写成数据文件，由平台的通用引擎显示和判分，所以你的任务是**写内容**，不是写程序。

## 你的角色

熟悉 8 岁孩子的科学教育编辑，知道怎样的问题能让孩子愿意动笔

## 知识点卡（不要改动）

{{embed: content/nodes/life/biology.genetics.chromosome-intro.yaml}}

## 这份活动要做到什么

字段照下面填：`schema: activity-def/1`、`kind: reflection`、`version: 1`、`targets: [biology.genetics.chromosome-intro]`、`age_band: G3-4`、`duration_min: 2`、`review: pending`、`engine: 1`。`title` 不超过 20 个字。

这是三颗星走完后的最后一步：请舰长用一句话写下自己的发现。写下来的话是舰长的私人文字，只给自己和家长看，不打分。

- `body.prompt`：一句话，不超过 40 个字，问舰长自己发现了什么，例如围绕「说明书的秘密」。不要问成考题（不要有标准答案），也不要问家里的具体情况。
- `body.starters`：2～3 个开头，给不知道怎么起笔的舰长，每个不超过 12 个字，以「……」结尾。其中一个和「像爸爸又像妈妈」有关，一个是「我还想知道……」这类（舰长写下的问题，家长会帮着转到信号站）。
- `body.max_chars`：120。
- 语气按「领航员怎么说话」：像领航员在旅程结束时轻轻问一句。
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
- 逐条核对内容规格 3.5（反思的 body）和 3.7（文字规则）。
- 把每个科学事实和出处对一遍。

## 验收标准

- [ ] `activity.yaml` 通过 schema 校验，满足内容规格第 5 节的规则
- [ ] 每个科学事实都和 `sources` 里的出处对过；没有编造出处，也没有和知识点卡矛盾的说法
- [ ] 字段齐全：`kind: reflection`、`duration_min: 2`、`body.max_chars: 120`
- [ ] `prompt` 一句话、不超过 40 个字，问的是舰长自己的发现，不是考题
- [ ] `starters` 2～3 个，每个不超过 12 个字，以「……」结尾；其中一个和「像爸爸又像妈妈」有关，一个是「我还想知道……」这类
- [ ] 不出现「学习」「总结」「作文」这些词；只用「词表」里三颗星的词

## 交付格式（必须遵守）

本任务的文件清单：
- `content/activities/act.reflection.chromosome-intro-01/activity.yaml`

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。所有文件都写在交付包文字里。分段时，**每一段的第一行都必须是段首标记**。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
