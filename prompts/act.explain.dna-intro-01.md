---
task: act.explain.dna-intro-01
issue: 38
version: v1
---

# 任务：为知识点「DNA：细胞里的说明书」写一份讲解

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。孩子是飞船舰长，知识点是星图上的星星。讲解、挑战、反思都写成数据文件，由平台的通用引擎显示和判分，所以你的任务是**写内容**，不是写程序。

## 你的角色

会讲故事的儿童科普作者，也是熟悉 8 岁孩子认知特点的科学教育编辑：能把看不见的东西讲成孩子摸得着的比方，同时一个字都不讲错

## 知识点卡（不要改动）

{{embed: content/nodes/life/biology.genetics.dna-intro.yaml}}

## 这份活动要做到什么

字段照下面填：`schema: activity-def/1`、`kind: explain`、`version: 1`、`targets: [biology.genetics.dna-intro]`、`age_band: G3-4`、`duration_min: 5`、`review: pending`、`engine: 1`；`body.style` 写 `tutor`（领航员对话）。`title` 不超过 20 个字。`sources` 从下面「事实和出处」表里挑你用到的，照抄。

**讲解顺序**（全篇 11～17 个步骤；可以调整措辞和步数，不能漏掉要点、不能打乱前后关系）：

1. **开场**：驱动问题「为什么小狗生下来的总是小狗，不会是小猫？」，请舰长先想一想。
2. **接上一颗星**：上一颗星说过，细胞核这个小房间里放着一份说明书。这份说明书叫 DNA。
3. **说明书**：DNA 像一本用 4 种字母写成的说明书（可以写出 A、T、C、G），记着身体怎么长、长成什么样。小狗的说明书写的是怎么长成小狗。配图 `dna-book.svg`。
4. **同一套**：身体里绝大多数细胞，带的都是同一套说明书。那为什么神经细胞和肌肉细胞本领不一样？因为它们读的是同一本书的不同几页。配图 `dna-pages.svg`。（针对 `different-books`）
5. **到处都有**：DNA 不是只在血液里，皮肤、口腔里、肌肉里的细胞都有。（针对 `blood-only`；举例不要用头发，见「容易讲错的地方」）
6. **例外**：人成熟的红细胞长好以后，把细胞核连同说明书一起扔掉了，好腾出地方多装氧气。但它当初也是照着同一本说明书长出来的。配图 `red-cell.svg`。
7. **天天在用**：说明书不是放着不动的：你每天长个子、摔破的伤口长好，细胞都在照着它做。（针对 `only-for-babies`）
8. **回到开场**：说明书是爸爸妈妈传给孩子的，这叫遗传。小狗从狗爸爸狗妈妈那里拿到的是狗的说明书，所以长成小狗。
9. **钩子**：一个细胞里的 DNA 拉直了大约有 2 米长，比大人还高。这么长，怎么装进那么小的细胞核？请舰长去下一颗星「染色体」找答案（这里只提问，不讲怎么装）。

**小问题（`check`）**：全篇 2～3 个。至少一个针对 `different-books`，至少一个针对 `blood-only` 或 `only-for-babies`。每个 `check` 用选择题，3 个选项，恰好一个正确；能对应知识点卡误区的错误选项，都写上 `misconception`（误区 id，直接写 id，例如 `different-books`）和 `feedback`。`feedback` 按「领航员怎么说话」里「答错时先接住」的写法。每题 1～3 条提示，从轻到重，最后一条也不说出答案。

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

3 张，存在 `content/assets/biology.genetics.dna-intro/` 下：

| 文件名 | 画什么 |
| --- | --- |
| `dna-book.svg` | 一个细胞，细胞核这个小房间里摊开一本书，书页上是一行行 A、T、C、G 字母（字母用 `text`，不小于 14 号字） |
| `dna-pages.svg` | 同样的两本书并排，一本翻开在贴着「神经细胞」标签的那几页，一本翻开在「肌肉细胞」那几页；两本书的封面一样，说明是同一套 |
| `red-cell.svg` | 三格：带细胞核的年轻红细胞 → 细胞核被推出细胞 → 中间凹下去的圆饼形红细胞，里面画几个小点表示装满了氧气 |

配图存为 `content/assets/<知识点 id>/<文件名>.svg`，按内容规格 3.6 的白名单写：手绘风格的线条和淡彩色块，不用 `<style>` 和 `style` 属性，颜色写在 `fill`、`stroke` 属性里；`viewBox` 写好，不写死 `width`、`height`。

## 怎么自己验证

- 能运行代码的话：用 Python 的 jsonschema（Draft 2020-12）拿上面的 schema 校验你的 `activity.yaml`，必须通过。
- 逐条核对内容规格第 5 节的校验规则：题目 id 唯一、`shaded` 不超过 `parts`、提示不说出答案、误区引用出自知识点卡、文字长度。
- 把每个科学事实和出处对一遍。

## 验收标准

- [ ] `activity.yaml` 通过 schema 校验，满足内容规格第 5 节的规则
- [ ] 每个科学事实都和 `sources` 里的出处对过；没有编造出处，也没有和知识点卡矛盾的说法
- [ ] `body.style` 是 `tutor`；步骤 11～17 个；`check` 2～3 个
- [ ] 第一步是驱动问题，第 8 步左右回到驱动问题，最后一步只提出「怎么装下」的问题，指向染色体
- [ ] DNA 卡的 4 条目标都讲到了；「词表」里 DNA 这颗星的新词全部出现，没有用「不要用的词」（尤其是「基因」「染色体」只在最后的钩子里提「染色体」这个名字）
- [ ] 至少 2 个不同的误区被 `check` 的错误选项引用，引用的 id 都出自 DNA 卡
- [ ] 讲到红细胞是例外；没有「每个细胞都有 DNA」这类绝对的说法；没有用头发举例
- [ ] 每个 `text` 步骤一两句话、不超过 60 个字；感叹号全篇不超过 3 个
- [ ] 3 张配图齐全，路径和文件名与上表一致，并且被步骤引用
- [ ] 配图通过内容规格 3.6 的白名单

## 交付格式（必须遵守）

本任务的文件清单：
- `content/activities/act.explain.dna-intro-01/activity.yaml`
- `content/assets/biology.genetics.dna-intro/dna-book.svg`
- `content/assets/biology.genetics.dna-intro/dna-pages.svg`
- `content/assets/biology.genetics.dna-intro/red-cell.svg`

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。所有文件都写在交付包文字里。分段时，**每一段的第一行都必须是段首标记**。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
