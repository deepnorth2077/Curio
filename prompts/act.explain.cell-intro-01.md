---
task: act.explain.cell-intro-01
issue: 35
version: v1
---

# 任务：为知识点「细胞：生命的小房间」写一份讲解

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。孩子是飞船舰长，知识点是星图上的星星。讲解、挑战、反思都写成数据文件，由平台的通用引擎显示和判分，所以你的任务是**写内容**，不是写程序。

## 你的角色

会讲故事的儿童科普作者，也是熟悉 8 岁孩子认知特点的科学教育编辑：能把看不见的东西讲成孩子摸得着的比方，同时一个字都不讲错

## 知识点卡（不要改动）

{{embed: content/nodes/life/biology.cell.cell-intro.yaml}}

## 这份活动要做到什么

字段照下面填：`schema: activity-def/1`、`kind: explain`、`version: 1`、`targets: [biology.cell.cell-intro]`、`age_band: G3-4`、`duration_min: 5`、`review: pending`、`engine: 1`；`body.style` 写 `tutor`（领航员对话）。`title` 不超过 20 个字。`sources` 从下面「事实和出处」表里挑你用到的，照抄。

**讲解顺序**（全篇 10～16 个步骤；可以调整措辞和步数，不能漏掉要点、不能打乱前后关系）：

1. **开场**：领航员抛出驱动问题「你的身体是用什么搭起来的？」，请舰长先想一想。
2. **积木**：房子用一块块积木搭，身体用一个个细胞搭。不只是人和动物，大树、小草也是细胞搭成的。（针对误区 `only-animals`）
3. **很小**：细胞很小，大多数要用显微镜才能看见，放大镜都不够。配图 `cell-zoom.svg`。（针对 `visible`）
4. **很多种**：身体里的细胞形状和本领各不一样：神经细胞长长的、伸出很多分叉，负责传消息；红细胞圆圆扁扁的像小饼，负责运氧气；肌肉细胞细细长长，能用力收缩。配图 `cell-kinds.svg`。（针对 `one-kind`）
5. **是活的**：细胞和积木最不一样的地方：细胞是活的，会吃东西、会长大，还会一个分成两个。配图 `cell-divide.svg`。（针对 `cells-are-dead`）
6. **细胞核**：细胞这个小房间里，还有一个更小的房间，叫细胞核，里面放着一份「说明书」。动物和植物的细胞一般都有细胞核；人成熟的红细胞把细胞核扔掉了，是例外（只点一句，下一颗星再讲为什么）。配图 `cell-nucleus.svg`。
7. **钩子**：这份说明书上写的是什么？请舰长去下一颗星 DNA 找答案。

**小问题（`check`）**：全篇 2～3 个，放在第 2～5 步之间。至少一个针对 `only-animals`，至少一个针对 `cells-are-dead` 或 `visible`。每个 `check` 用选择题，3 个选项，恰好一个正确；能对应知识点卡误区的错误选项，都写上 `misconception`（误区 id，直接写 id，例如 `only-animals`）和 `feedback`。`feedback` 按「领航员怎么说话」里「答错时先接住」的写法。每题 1～3 条提示，从轻到重，最后一条也不说出答案。

## 星座的共同约定

本星座几个活动由不同的人分头写。下面几节是共同约定，必须遵守。

{{embed: docs/constellations/life-manual.md#星座概况}}

{{embed: docs/constellations/life-manual.md#领航员怎么说话}}

{{embed: docs/constellations/life-manual.md#词表}}

{{embed: docs/constellations/life-manual.md#配图风格}}

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

4 张，存在 `content/assets/biology.cell.cell-intro/` 下：

| 文件名 | 画什么 |
| --- | --- |
| `cell-zoom.svg` | 从左到右三格：一片树叶 → 一个放大镜 → 显微镜圆形视野里一格一格挨着的细胞（像砖墙或蜂巢） |
| `cell-kinds.svg` | 三种细胞并排：神经细胞（中间圆、伸出很多分叉和一条长尾巴）、红细胞（扁圆饼，中间凹，**没有细胞核**）、肌肉细胞（细长两头尖）。神经细胞和肌肉细胞里画出细胞核的小圆点。每个下面一个短标签 |
| `cell-divide.svg` | 三格：一个细胞 → 中间收紧、细胞核变成两个 → 两个细胞 |
| `cell-nucleus.svg` | 一个动物细胞，中间的细胞核画成一个小房间，里面放着一本合上的小书（暗示「说明书」，书上不写字） |

配图存为 `content/assets/<知识点 id>/<文件名>.svg`，按内容规格 3.6 的白名单写：手绘风格的线条和淡彩色块，不用 `<style>` 和 `style` 属性，颜色写在 `fill`、`stroke` 属性里；`viewBox` 写好，不写死 `width`、`height`。

## 怎么自己验证

- 能运行代码的话：用 Python 的 jsonschema（Draft 2020-12）拿上面的 schema 校验你的 `activity.yaml`，必须通过。
- 逐条核对内容规格第 5 节的校验规则：题目 id 唯一、`shaded` 不超过 `parts`、提示不说出答案、误区引用出自知识点卡、文字长度。
- 把每个科学事实和出处对一遍。

## 验收标准

- [ ] `activity.yaml` 通过 schema 校验，满足内容规格第 5 节的规则
- [ ] 每个科学事实都和 `sources` 里的出处对过；没有编造出处，也没有和知识点卡矛盾的说法
- [ ] `body.style` 是 `tutor`；步骤 10～16 个；`check` 2～3 个
- [ ] 第一步是驱动问题，最后一步指向下一颗星 DNA
- [ ] 细胞卡的 5 条目标都讲到了；「词表」里细胞这颗星的新词全部出现，没有用「不要用的词」
- [ ] 至少 2 个不同的误区被 `check` 的错误选项引用，引用的 id 都出自细胞卡
- [ ] 每个 `text` 步骤一两句话、不超过 60 个字；感叹号全篇不超过 3 个
- [ ] 4 张配图齐全，路径和文件名与上表一致，并且被步骤引用；`cell-kinds.svg` 里的红细胞没有细胞核
- [ ] 没有「每个细胞都有细胞核」这类绝对的说法
- [ ] 配图通过内容规格 3.6 的白名单

## 交付格式（必须遵守）

本任务的文件清单：
- `content/activities/act.explain.cell-intro-01/activity.yaml`
- `content/assets/biology.cell.cell-intro/cell-zoom.svg`
- `content/assets/biology.cell.cell-intro/cell-kinds.svg`
- `content/assets/biology.cell.cell-intro/cell-divide.svg`
- `content/assets/biology.cell.cell-intro/cell-nucleus.svg`

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。所有文件都写在交付包文字里。分段时，**每一段的第一行都必须是段首标记**。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
