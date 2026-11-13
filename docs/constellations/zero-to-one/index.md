# 「0 和 1 之间」星座 · 完整 TASK 总索引

> v1 草案 · 2026-11-13 · 基于仓库提交 `3437b8c` · 分数、小数、比与百分数 · 主 issue #127

这是入口。整个星座的 TASK 一共 8 份文件：

| 文件 | 内容 |
| --- | --- |
| `index.md` | 这份：19 颗星的 id、依赖、派发顺序、共用零件登记、还没做的事 |
| `../zero-to-one.md` | 拆解：星座的谜题、三样贯穿物、六组十九颗星、「标杆级」的十条标准 |
| `g1.md` | 第 1 组 · 一份有多大（3 颗星）。**全星座共用的约定 A 部分和模块通则 C.0 在这份里** |
| `g2.md` | 第 2 组 · 小数：把一份再切十份（3 颗星） |
| `g3.md` | 第 3 组 · 一个数，很多名字（4 颗星） |
| `g4.md` | 第 4 组 · 乘除的怪事（3 颗星） |
| `g5.md` | 第 5 组 · 比：两个量的关系（3 颗星） |
| `g6.md` | 第 6 组 · 百分数：大家说好的分母（3 颗星） |

每份组文件的结构一样：A 共用约定（或增补）、B 知识点卡、C 模块设计说明、D 挑战、E Luka 怎么验收。

## 1. 十九颗星

| # | 星 | 知识点 id | 动手探索 | 挑战 | 年级 | 前置 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 几分之一：越分越小 | `math.fraction.unit-fraction` | `act.simulation.fair-cut-01` 切分机 | `act.quiz.unit-fraction-01` | 三上 | 无 |
| 2 | 几分之几：分数也能数 | `math.fraction.count-on-line` | `act.simulation.hop-line-01` 数线跳跳 | `act.quiz.count-on-line-01` | 三上 | 1 |
| 3 | 谁的几分之几 | `math.fraction.the-whole` | `act.simulation.whose-half-01` 谁的一半 | `act.quiz.the-whole-01` | 三上 | 1 |
| 4 | 小数是什么 | `math.decimal.tenths` | `act.simulation.zoom-line-01` 数线放大镜 | `act.quiz.tenths-01` | 三下 | 1、2 |
| 5 | 小数比大小和加减 | `math.decimal.compare-add` | `act.simulation.place-slots-01` 位值格 | `act.quiz.compare-add-01` | 四下 | 4 |
| 6 | 小数点搬家 | `math.decimal.point-shift` | `act.simulation.slide-rule-01` 滑尺 | `act.quiz.point-shift-01` | 四下 | 4 |
| 7 | 等值分数：再切一刀 | `math.fraction.equivalent` | `act.simulation.recut-01` 再切刀 | `act.quiz.equivalent-01` | 五下 | 1、2 |
| 8 | 分数和除法 | `math.fraction.as-division` | `act.simulation.share-table-01` 分饼台 | `act.quiz.as-division-01` | 五下 | 2、3 |
| 9 | 分数比大小 | `math.fraction.compare` | `act.simulation.match-cuts-01` 对刀口 | `act.quiz.fraction-order-01` | 五下 | 7 |
| 10 | 分数加减 | `math.fraction.add-subtract` | `act.simulation.measuring-cup-01` 量杯 | `act.quiz.add-subtract-01` | 五下 | 9 |
| 11 | 乘了反而变小 | `math.operation.multiply-shrinks` | `act.simulation.stretch-bar-01` 伸缩条 | `act.quiz.multiply-shrinks-01` | 五上 | 1、4 |
| 12 | 分数乘分数 | `math.fraction.multiply` | `act.simulation.cross-cut-01` 横切再竖切 | `act.quiz.fraction-multiply-01` | 六上 | 3、7、11 |
| 13 | 除以分数 | `math.fraction.divide` | `act.simulation.pour-cups-01` 倒水 | `act.quiz.fraction-divide-01` | 六上 | 8、12 |
| 14 | 比：味道一样的秘密 | `math.ratio.meaning` | `act.simulation.mix-drink-01` 调饮料台 | `act.quiz.ratio-meaning-01` | 六上 | 7、8 |
| 15 | 按比分配 | `math.ratio.sharing` | `act.simulation.ratio-chute-01` 分配槽 | `act.quiz.ratio-sharing-01` | 六上 | 3、14 |
| 16 | 比例和比例尺 | `math.ratio.proportion` | `act.simulation.stretch-frame-01` 拉伸相框 | `act.quiz.proportion-01` | 六下 | 14 |
| 17 | 百分数：都换成 100 份 | `math.percent.meaning` | `act.simulation.hundred-grid-01` 百格电量条 | `act.quiz.percent-meaning-01` | 六上 | 3、7 |
| 18 | 一个点，几个名字 | `math.number.same-point` | `act.simulation.three-rulers-01` 三把尺子 | `act.quiz.same-point-01` | 六上 | 4、7、8、17 |
| 19 | 涨一半再跌一半 | `math.percent.change` | `act.simulation.grow-shrink-01` 伸缩柱 | `act.quiz.percent-change-01` | 六下 | 11、17 |

一共 19 张知识点卡、19 个动手探索模块、19 个挑战（95 道题）。「年级」是人教版旧版的册次；四到六年级 2026 年秋起换新版，轮到那一组时对照实体书改 `unit` 和 `curriculum`。

知识点卡的 `theme`：第 14 到 16 颗是 `rel`（数量关系）；第 17、19 颗是 `stat`（2022 年版课标把百分数放在「统计与概率」，待核对原文）；其余是 `num`。

## 2. 先后

**按学校进度**（默认）：第 1 组现在做；第 2 组在三年级下学期开学前；第 11 颗在五年级上；第 3 组在五年级下；第 12、13、14、15、17、18 颗在六年级上；第 16、19 颗在六年级下。

**能插队的**（只依赖已经做完的星，孩子感兴趣就可以提前）：

- 第 1 组做完以后：第 7 颗（再切一刀）、第 4 颗（数线放大镜）。第 7 颗正好揭开第 2 颗星埋的伏笔。
- 第 4 颗做完以后：第 11 颗（乘了反而变小）、第 6 颗（小数点搬家）。
- 第 3、7 颗做完以后：第 17 颗（百格电量条）。孩子天天看 iPad 的电量，这颗很容易引起兴趣。

**每一组怎么派**（和第 1 组一样）：知识点卡先核对、先合入 → 模块一颗星一个 Opus 子 agent，同组的同时派 → Luka 在 iPad 上走一遍 → 舰长试玩 → 模块定稿后派挑战。一组没验收完，不开下一组。

## 3. 共用零件登记

三个贯穿物和十样共用零件。后做的模块必须和先做的画得一样；第一次做出来的那个模块就是这样零件的标杆，合入后把它抽成一段可以照抄的代码，写进 `references/lessons.md`。

| # | 零件 | 在哪一组定的 | 第一次做它的模块 | 以后谁用 |
| --- | --- | --- | --- | --- |
| 1 | 「1」记号（虚线框加小牌） | 第 1 组 A.4 | 切分机 | 全部 |
| 2 | 分数的上下写法 `.frac` | 第 1 组 A.4 | 切分机 | 全部 |
| 3 | 数线条（星卡底部） | 第 1 组 A.4 | 切分机 | 全部 |
| 4 | 位值格 | 第 2 组 A.3 | 位值格 | 5、6 |
| 5 | 放大圈 | 第 2 组 A.3 | 切分机（先用），数线放大镜（定型） | 1、2、4、9、11、18 |
| 6 | 分数条 | 第 3 组 A.3 | 再切刀 | 7、9、10、12 |
| 7 | 一颗钉子，几块名牌 | 第 3 组 A.3 | 再切刀 | 7、8、18 |
| 8 | 百格 | 第 4 组 A.3 | 伸缩条 | 11、17 |
| 9 | 巧克力板 | 第 4 组 A.3 | 已有的「掰巧克力」 | 12 |
| 10 | 格子纸 | 第 5 组 A.3 | 拉伸相框 | 16，以后的正比例函数 |

**伏笔和回收**（跨星的线，改任何一颗星时别弄断）：

- 第 2 颗星插旗时「2/4 压在 1/2 上」→ 第 7 颗星揭开 → 第 18 颗星把小数和百分数的名牌也叠上去。
- 第 1 颗星「1 米的 1/10、1/100、1/1000 是分米、厘米、毫米」→ 第 4 颗星「0.1 米、0.01 米」→ 第 9 颗星「99/100 和 999/1000 差的是 1 厘米和 1 毫米」。
- 第 3 颗星「谁的 1/4」→ 第 15 颗星「拿谁当 1」→ 第 17 颗星「换过来比」→ 第 19 颗星「1 的记号每一步都跳」。
- 第 5 颗星「0.3 = 0.30」→ 第 6 颗星领航员的错账「1.50」。
- 已有的「掰巧克力」→ 第 12 颗星的巧克力板。

## 4. 现在的状态和我做了什么假设

- **状态**：全部是草案。2026-11-13 起八份文件都在仓库里，主 issue 是 #127；还没有派发，也没有任何知识点卡进 `content/`。
- **假设**：拆解文档第 6 节的五个问题，Luka 还没有明确回答；我按推荐答案写完了全部 TASK（星座名「0 和 1 之间」、六组十九颗星、新开 `math.*` 的 id、第 1 组先上试玩页、同分母加减不单独成星）。任何一条改了，受影响的只是名字和 id，设计不用重做。
- **已经查过的**：19 张知识点卡全部通过 `schemas/knode.schema.json` 校验；前置和关联的 id 都存在；每张卡的每个误区都至少被一个模块的猜测或一道挑战题针对；38 个活动 id 和仓库里已有的、测试夹具里的都不重名；验收用例里的数全部手算或用程序复算过。
- **还没做的**：
  1. 标了「请核对」的出处没有独立核对（课标原文措辞、各册单元名、蓝鲸、身高、博尔特、纸厚、上海中心、海水盐度、空气成分、耕地、地月数据、身体含水、莱因德纸草书）。按流程，每组合入知识点卡之前由没参与制作的子 agent 查。
  2. 四到六年级的新版教材目录没有对照。
  3. 挑战只定了题目、答案和误区，题干措辞、提示、反馈、配图由实现者写。
  4. 第 2 到第 6 组的设计是按现在的理解写的。等第 1 组在舰长手里玩过，按他的反应回头修后面的组：哪种动作他喜欢、哪种谜题他不上当、一个模块 8 分钟够不够。

## 5. 下一步

Luka 回答「是」（或者说哪条要改），我就：

1. 派一个子 agent 核对第 1 组的出处，改好后合入三张知识点卡。
2. 同时派三个 Opus 子 agent 做切分机、数线跳跳、谁的一半。
3. 把试玩页链接发给你。

派发的时候，各组里的「基准提交」换成当时 `main` 的提交号，再看一遍这份 TASK 依赖的文件（活动契约、schema、术语表、`lessons.md`）有没有变。

另外还缺一样：孩子数学书第六单元的目录页或前两页的照片。
