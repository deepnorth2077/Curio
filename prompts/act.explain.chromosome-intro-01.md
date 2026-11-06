---
task: act.explain.chromosome-intro-01
issue: 41
version: v1
---

# 任务：为知识点「染色体：把说明书卷好收起来」写一份讲解

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。孩子是飞船舰长，知识点是星图上的星星。讲解、挑战、反思都写成数据文件，由平台的通用引擎显示和判分，所以你的任务是**写内容**，不是写程序。

## 你的角色

会讲故事的儿童科普作者，也是熟悉 8 岁孩子认知特点的科学教育编辑：能把看不见的东西讲成孩子摸得着的比方，同时一个字都不讲错

## 知识点卡（不要改动）

{{embed: content/nodes/life/biology.genetics.chromosome-intro.yaml}}

## 这份活动要做到什么

字段照下面填：`schema: activity-def/1`、`kind: explain`、`version: 1`、`targets: [biology.genetics.chromosome-intro]`、`age_band: G3-4`、`duration_min: 5`、`review: pending`、`engine: 1`；`body.style` 写 `tutor`（领航员对话）。`title` 不超过 20 个字。`sources` 从下面「事实和出处」表里挑你用到的，照抄。

**讲解顺序**（全篇 14～20 个步骤；可以调整措辞和步数，不能漏掉要点、不能打乱前后关系）：

1. **开场**：驱动问题「这么长的说明书，小小的细胞是怎么装下的？」：一个细胞里的 DNA 拉直了大约有 2 米长，细胞核却小得要用显微镜才能看见。
2. **卷起来**：就像一大堆毛线，先一圈圈绕在小线轴上，再收成一小团。DNA 缠在像小线轴一样的蛋白质上，再折叠起来，就成了染色体。配图 `chr-wind.svg`。
3. **数一数**：人的体细胞里一般有 46 条染色体，两两配成 23 对。配图 `chr-pairs.svg`。
4. **一半一半**：每一对里，一条来自爸爸，一条来自妈妈。说明书就写在染色体上，所以你的说明书一半抄自爸爸、一半抄自妈妈。这就是你既像爸爸又像妈妈的原因；更像谁，每个人不一样。（针对 `from-one-parent`）
5. **基因**：说明书里一段一段的，叫基因。一条染色体上有很多很多个基因，所以染色体不是基因，它是一整卷说明书。配图 `chr-genes.svg`。（针对 `chromosome-is-gene`）
6. **第 23 对**：第 23 对叫性染色体。女孩一般是两条 X，男孩一般是一条 X、一条短一点的 Y。配图 `chr-xy.svg`。（针对 `same-in-boys-girls`）
7. **X 和 Y 从哪来**：男孩的 X 来自妈妈，Y 来自爸爸；女孩的两条 X，一条来自爸爸，一条来自妈妈。（针对 `y-from-mother`）
8. **别的生物**：不同的生物，染色体数目不一样。狗有 78 条，比人还多；小小的果蝇只有 8 条。染色体的多少，和个子大小、聪不聪明都没有关系。（针对 `bigger-more`、`more-is-smarter`）
9. **连起来**：用一两句话把三颗星串起来：身体由细胞搭成 → 细胞核里放着说明书 DNA → DNA 卷好收起来就是染色体。
10. **结尾**：请舰长去写一句反思；还有想知道的，可以点「我有个问题」问领航员。

**小问题（`check`）**：全篇 3～4 个。至少覆盖 `from-one-parent`、`y-from-mother`，以及 `bigger-more` 或 `more-is-smarter` 中的一个。每个 `check` 用选择题，3 个选项，恰好一个正确；能对应知识点卡误区的错误选项，都写上 `misconception`（误区 id，直接写 id，例如 `from-one-parent`）和 `feedback`。`feedback` 按「领航员怎么说话」里「答错时先接住」的写法。每题 1～3 条提示，从轻到重，最后一条也不说出答案。

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

4 张，存在 `content/assets/biology.genetics.chromosome-intro/` 下。染色体一律画成两头圆的短棒，**不画 X 形**；区分来源时爸爸用蓝 `#4F7FA8`、妈妈用陶土红 `#C2603F`。

| 文件名 | 画什么 |
| --- | --- |
| `chr-wind.svg` | 从左到右三格：一根长长弯弯的线 → 线一圈圈绕在几个小线轴上（像一串珠子）→ 折叠收成一根短棒 |
| `chr-pairs.svg` | 22 对短棒排成几行，从大到小，每对一根蓝、一根红；第 23 对的位置画一个虚线框，里面一个问号（留给下一张图） |
| `chr-genes.svg` | 一根放大的短棒，上面分成一段一段（不同深浅的色块），旁边一个小箭头指着其中一段，标签「基因」 |
| `chr-xy.svg` | 左右两组：女孩是两根一样长的 X（一蓝一红），男孩是一根长的 X（红，来自妈妈）和一根短的 Y（蓝，来自爸爸）；每根用字母 X 或 Y 标出 |

配图存为 `content/assets/<知识点 id>/<文件名>.svg`，按内容规格 3.6 的白名单写：手绘风格的线条和淡彩色块，不用 `<style>` 和 `style` 属性，颜色写在 `fill`、`stroke` 属性里；`viewBox` 写好，不写死 `width`、`height`。

## 怎么自己验证

- 能运行代码的话：用 Python 的 jsonschema（Draft 2020-12）拿上面的 schema 校验你的 `activity.yaml`，必须通过。
- 逐条核对内容规格第 5 节的校验规则：题目 id 唯一、`shaded` 不超过 `parts`、提示不说出答案、误区引用出自知识点卡、文字长度。
- 把每个科学事实和出处对一遍。

## 验收标准

- [ ] `activity.yaml` 通过 schema 校验，满足内容规格第 5 节的规则
- [ ] 每个科学事实都和 `sources` 里的出处对过；没有编造出处，也没有和知识点卡矛盾的说法
- [ ] `body.style` 是 `tutor`；步骤 14～20 个；`check` 3～4 个
- [ ] 第一步是驱动问题；结尾把三颗星串起来，并请舰长写反思或提问
- [ ] 染色体卡的 6 条目标都讲到了；「词表」里染色体这颗星的新词全部出现，没有用「不要用的词」
- [ ] 至少 3 个不同的误区被 `check` 的错误选项引用，引用的 id 都出自染色体卡
- [ ] 讲清了蛋白质（小线轴）、X 来自妈妈和 Y 来自爸爸、「像谁」落在说明书上
- [ ] 每个 `text` 步骤一两句话、不超过 60 个字；感叹号全篇不超过 3 个
- [ ] 4 张配图齐全，路径和文件名与上表一致，并且被步骤引用；染色体都是短棒，没有 X 形；蓝是爸爸、红是妈妈，并在图注里说明
- [ ] 配图通过内容规格 3.6 的白名单

## 交付格式（必须遵守）

本任务的文件清单：
- `content/activities/act.explain.chromosome-intro-01/activity.yaml`
- `content/assets/biology.genetics.chromosome-intro/chr-wind.svg`
- `content/assets/biology.genetics.chromosome-intro/chr-pairs.svg`
- `content/assets/biology.genetics.chromosome-intro/chr-genes.svg`
- `content/assets/biology.genetics.chromosome-intro/chr-xy.svg`

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。所有文件都写在交付包文字里。分段时，**每一段的第一行都必须是段首标记**。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
