> 基于 Curio 仓库提交 `6af4bcb998d91d4d5cf99b240c62f0bbead9c93e` 生成 · 任务 `act.simulation.chocolate-split-01` · issue #55 · 提示词版本 v1
> 交付包开头信息请照抄：`issue: #55`、`任务: act.simulation.chocolate-split-01`、`提示词版本: v1`、`基于提交: 6af4bcb998d9`


> 契约 activity/1.1 · 基于提交 `6af4bcb998d91d4d5cf99b240c62f0bbead9c93e`

# 任务：为知识点「乘法分配律：掰开来算」做一个动手探索模块「掰巧克力」

这是新星座「乘法的秘密」的第一颗星。要按下面的方法做：**实物就是解释**。不要写「乘法分配律是……」再配一张图、出三道选择题；孩子亲手掰开、拼起来、转拨盘，每一步画面和读数都来自同一个模型，他看懂这块巧克力是怎么变的，也就懂了乘法分配律。

画风、卡片、领航员、读数、操作手感，要和平台已有的三个动手探索模块一致。你看不到那三个模块，但下面附了它们共用的骨架 `starter.html`（第 9 节），**从它起步**，不要从零写。

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。孩子是飞船舰长，知识点是星图上的星球，陪他说话的是领航员。你要做的是一个可以插进平台的互动小程序：单文件 `index.html` 加一个 `manifest.yaml`，运行在平台提供的沙箱 iframe（`sandbox="allow-scripts"`）里，只通过固定的消息和平台通信。

## 你的角色

你同时是面向三年级孩子的数学互动设计师、插画师和前端工程师：能把一条规律做成孩子摸得着的东西，画得好看，手感顺，一个数都不算错。

## 舰长

小学三年级，8 岁左右。会背乘法口诀，会口算 12×3，认识小括号（先算括号里面的）。还没学过「运算律」，没见过用字母写的式子。

## 知识点卡（不要改动）

> 出处：`content/nodes/num/math.operation.distributive-law.yaml`（提交 `6af4bcb`）

````text
id: math.operation.distributive-law
schema: knode/1
title: 乘法分配律：掰开来算
subjects: [math]
theme: num
grade: G4
unit: 四年级 · 运算律（旧版人教版在四下第三单元「运算定律」；2026 年秋起的新版放在哪一册，待对照实体书）
curriculum:
  - std: 义务教育数学课程标准（2022 年版）
    ref: 第二学段「数与运算」：探索并理解运算律，包括乘法对加法的分配律
  - textbook: 人教版小学数学四年级下册（旧版）
    unit: 第三单元 运算定律
prerequisites: []
related: []
driving_question: 一块巧克力掰成两块，怎么算才一块都不会少？
objectives:
  - 知道每排一样多的一整块东西，掰成两块以后，两块加起来还是那么多：(3+4)×5 = 3×5 + 4×5。
  - 知道掰开以后两块都还有原来那么多排，所以括号里的两个数都要乘 5，不能只乘一个。
  - 知道反过来也成立：排数一样的两块能拼成一整块，3×5 + 4×5 = (3+4)×5；排数不一样就拼不成一整块，不能这样合起来。
  - 会把难算的乘法拆成好算的两道：12×3 = 10×3 + 2×3，37×101 = 37×100 + 37×1。
  - 知道这个规律叫乘法分配律，换成别的数也一样成立。
misconceptions:
  - id: multiply-one-part
    text: 拆开以后只有一部分乘了外面的数，例如把 (3+4)×5 写成 3×5 + 4，把 37×101 算成 37×100 + 1。
  - id: add-instead-of-multiply
    text: 数一整块排好的东西时，把每排几块和有几排加起来，例如每排 4 块、5 排，说成 9 块。
  - id: drop-small-part
    text: 把接近整百的数当成整百来乘，忘了补上多出来的那一点，例如把 37×101 算成 3700。
  - id: merge-unlike
    text: 两个乘法里没有一样的数，也硬合并，例如把 3×5 + 4×6 写成 (3+4)×5。
  - id: split-both
    text: 两个因数都拆开以后只把对应的部分相乘，例如把 12×13 算成 10×10 + 2×3。
sources:
  - type: curriculum
    ref: 《义务教育数学课程标准（2022 年版）》第二学段「数与运算」
  - type: textbook
    ref: 人教版小学数学四年级下册（旧版）第三单元「运算定律」；人教版小学数学三年级上册（旧版）「多位数乘一位数」口算乘法 12×3
  - type: reference
    ref: NCETM「Connecting multiplication and division, and the distributive law」（Year 4：把一个因数拆开，由已知的乘法推出新的乘法）
    url: https://ncetm.org.uk/classroom-resources/primm-210-connecting-multiplication-and-division-and-the-distributive-law
lenses:
  - band: G3-4
    approach: 不用字母，用一块排得整整齐齐的巧克力：每排 7 块、5 排，沿着缝掰成每排 3 块和每排 4 块的两块，两块都还是 5 排，所以 (3+4)×5 = 3×5 + 4×5；反过来，排数一样的两块能拼回一整块；再用它口算 12×3 和变「乘 101」的魔术。
  - band: G4-6
    approach: 用字母表示 (a+b)×c = a×c + b×c，正着用、反着用都做简便计算（102×25、38×99、25×37 + 75×37），并和乘法结合律区分开。
  - band: G7-9
    approach: 用面积模型解释去括号和合并同类项，推出 (a+b)(c+d) = ac + ad + bc + bd，说清 12×13 为什么不等于 10×10 + 2×3。
activities: []
status: draft
version: 1
# END OF FILE
````


## 1. 谜题

> 一块巧克力，每排 7 块，有 5 排：7×5 = 35 块。领航员把它掰成两块分给舰长：左边每排 3 块，右边每排 4 块。他算了算：3×5 + 4 = 19。咦，少了 16 块，跑哪儿去了？

孩子凭直觉会跟着领航员错一次：右边那块被包装纸挡着，只露出第一排的 4 块。真相是右边那块也有 5 排，4 也要乘 5：3×5 + 4×5 = 35，一块都不少。

## 2. 真相表（页面上的每个数字都只能从页面里的 `MODEL` 算出来）

| 量 | 值 | 来由 |
| --- | --- | --- |
| 巧克力 | 每排 7 块，5 排，一共 35 块 | 设计约定（为了好数、好掰） |
| 缝 | 每排 7 块，竖着有 6 条缝；第 k 条缝左边每排 k 块、右边每排 7−k 块 | 由上一行算 |
| 领航员的错账 | 3×5 + 4 = 19，比 35 少 16；少的正好是右边那块下面 4 排：4×4 = 16 | 由上面算 |
| 乘法分配律 | (3+4)×5 = 3×5 + 4×5；换成别的数也一样 | 人教版四年级下册（旧版）第三单元「运算定律」；课标 2022 第二学段 |
| 口算 12×3 | 先算 10×3 = 30，再算 2×3 = 6，30 + 6 = 36 | 人教版三年级上册（旧版）「多位数乘一位数」口算乘法 |
| 第 2 站的三块 | A：每排 3 块、5 排（15 块）；B：每排 4 块、5 排（20 块）；C：每排 4 块、6 排（24 块） | 设计约定 |
| A 和 B 拼起来 | 3×5 + 4×5 = (3+4)×5 = 35 | 由上面算 |
| A 和 C 拼不成一整块 | 15 + 24 = 39，比 7×5 多 4 块：C 最下面多出来的一排 4 块 | 由上面算 |
| 乘 101 | n×101 = n×100 + n×1；两位数 n（10～99）的结果正好是把 n 写两遍：37×101 = 3737 | 由乘法分配律算 |
| 两位数有几个 | 10 到 99，一共 90 个 | 由上一行算 |
| 只对两位数 | 123×101 = 12423，不是「写两遍」 | 由乘法分配律算（不要说「任何数」） |

**验收用例**（审核时会逐条核对，你的页面在这些输入下必须显示这些值）：

| 输入 | 页面应显示 |
| --- | --- |
| 第 1 站，第 k 条缝（k = 1…6） | 左边 k×5，右边 (7−k)×5，一共 35：k=1 → 5、30；k=2 → 10、25；k=3 → 15、20；k=4 → 20、15；k=5 → 25、10；k=6 → 30、5 |
| 第 1 站，领航员的错账 | 3×5 + 4 = 19；少了 16 块 = 右边下面 4 排 × 每排 4 块 |
| 第 2 站，C 拼到 A 旁边 | 15 + 24 = 39；7×5 只有 35；多出 4 块；拼不成一整块 |
| 第 2 站，B 拼到 A 旁边 | 3×5 + 4×5 = (3+4)×5 = 35 |
| 第 3 站，n = 10 / 37 / 58 / 99 | 1010 / 3737 / 5858 / 9999；每次都显示 n×100 和 n×1 两部分 |
| 第 3 站，错误选项 | 37×100 + 1 = 3701（比 3737 少 36）；37×100 = 3700（少 37） |

## 3. 实物

一句话：**孩子拉开包装纸、拖着那条缝把巧克力掰成两块，再把两块拼回去，最后转拨盘让「乘 101」的魔术机吐出答案。掰在哪条缝都是 35 块，就是乘法分配律；排数一样才拼得回一整块，就是它反过来用；101 掰成 100 和 1，就是用它把难算的变好算。**

## 4. 零件清单

- **主角**（陶土红 `--accent`，整个画面只给它用）：第 1 站是那条缝和缝上方的把手；第 2 站是孩子正在拖的那一块的描边；第 3 站是乘 101 时多出来的那细细的「1 列」。
- **环境**：一张桌面（一条淡淡的手绘桌沿就够）、包装纸（纸色，带一个手写感的「5 排」小标签）、第 2 站的「拼台」（一块浅色的托盘，左边固定放着 A）、第 3 站的魔术机（一个手绘的盒子，左边进数，右边出数）。
- **巧克力**：杏色的小方块，块和块之间是墨线画的缝；每一小块可以有一道很浅的高光线。
- **刻度和读数**：footer 右下的读数区写算式和结果（`3×5 = 15 · 4×5 = 20 · 一共 35 块`）；画面里最多两三个小牌子（每块巧克力下面一个「3×5」这样的小牌子），字至少 15 个 viewBox 单位。
- **控件**：缝的把手（拖动，左右吸附到 6 条缝）；包装纸（往下拉）；第 2 站的 B、C 两块（拖到 A 的右边）；第 3 站的两个拨盘（十位、个位，拖着转或点上半边 / 下半边加减）。手指能抓到的地方都至少 48 px。

## 5. 三站加一个结尾

每站换一种动作：第 1 站拖（拉开、横着拖缝），第 2 站拼（拖着一块去对齐另一块），第 3 站转（拨盘）。

**第 1 站 · 掰开**
- 开场：画面上只有一块裹着包装纸的巧克力，只露出最上面一排 7 块，包装纸上的小标签写「5 排」。领航员说出谜题里的错账（`3×5 + 4 = 19`），画面上的读数区也写着这笔账。
- 猜：「右边那块，每排 4 块，一共有几块？」三个选项，按这个顺序：`4 块`（误区 `multiply-one-part`）、`20 块`（对）、`9 块`（误区 `add-instead-of-multiply`）。错误选项的反馈先接住（「我刚才也是这么算的」「把 4 和 5 加起来，看起来很顺手」），再说一句哪里不对。
- 动手 1：把包装纸往下拉。巧克力的 5 排一排排露出来。拉到底时，右边那块下面 4 排用虚线圈起来，画一个小牌子「漏掉的 16 块」：领航员的错账在画面上被纠正。
- 动手 2：缝的把手一开始在第 3 条缝（3 | 4）。孩子拖着把手左右走，缝吸附到 6 条缝之一，两块巧克力跟着微微分开；每块下面的小牌子和读数实时变（`k×5 = … · (7−k)×5 = … · 一共 35 块`）。孩子在**第 2 条不同的缝**停下时，领航员说出名字：「不管从哪条缝掰，都是 35 块。这个规律叫乘法分配律。」在**第 3 条不同的缝**停下时，这一站完成。「停下」是指手指松开时所在的缝，或者键盘每走一格；同一条缝只算一次；把手一开始就在的第 3 条缝不算，除非孩子拖走以后又停回那里。
- 揭晓 + 「哇」：「7 块一排，有 6 条缝。从哪条掰，都是 35 块，一块都不少。」画出来：6 块小小的巧克力缩略图排成一排，各掰在一条不同的缝上，下面都写 35。再补一句和舰长有关的：「口算 12×3 时，可以先算 10×3，再算 2×3，也是这样掰的。」

**第 2 站 · 拼起来**
- 开场：画面上只有一张算式牌「3×5 + 4×6」，不画巧克力（提问前不能把答案摆在画面上）。
- 猜：「3×5 + 4×6，能不能写成 (3+4)×5？」三个选项，按这个顺序：`能，就是 (3+4)×5`（误区 `merge-unlike`）、`能，是 (3+4)×(5+6)`（误区 `merge-unlike`）、`不能，排数不一样`（对）。
- 动手：拼台出现，左边固定放着 A（每排 3 块、5 排）。**先只放出 C**（每排 4 块、6 排）。孩子把 C 拖到 A 的右边：上边对齐以后，C 最下面那一排 4 块露在外面，用虚线圈出来，读数写 `15 + 24 = 39 · 7×5 只有 35 · 多出 4 块`，领航员说「拼不成方方正正的一整块」，过一会儿 C 滑回原处。**C 试过以后才放出 B**（每排 4 块、5 排）。孩子把 B 拖到 A 的右边：吸附对齐，两块合成一整块每排 7 块、5 排的巧克力，中间的缝留着一条淡淡的线；读数写 `3×5 + 4×5 = (3+4)×5 = 35`。B 拼好，这一站完成。
- 揭晓：「排数一样，才拼得成一整块。两个乘法里都有一个 5，才能合起来：3×5 + 4×5 = (3+4)×5。乘法分配律反过来也对。」

**第 3 站 · 乘 101 的魔术机**
- 开场：只有一张算式牌「37 × 101 = ?」，不画魔术机。
- 猜：「37 × 101 等于多少？」三个选项，按这个顺序：`3737`（对）、`3701`（误区 `multiply-one-part`）、`3700`（误区 `drop-small-part`）。反馈里说清 3701 和 3700 各少算了多少（36、37）。
- 动手：魔术机出现。左边两个拨盘（十位 1～9，个位 0～9），一开始是 3 和 7。中间画 n 排、每排 101 块的巧克力（不必一块块画：一大块「每排 100 块」加一条缝，缝右边是细细的「每排 1 块」那一列，用主角色；高度随 n 变，旁边写「n 排」）。右边出口显示结果，结果的前两位和后两位下面各画一道线，让孩子看出「写了两遍」。读数写 `n×100 = … · n×1 = … · 一共 …`。拨盘停下 0.8 秒不动，算试过一个数；试过 **3 个不同的数**（魔术机出现时的 37 就算第一个），这一站完成。
- 揭晓 + 「哇」：「101 掰成 100 和 1。两位数一共 90 个，每一个乘 101，都是把自己写两遍。」画出来：舰长试过的几个数排成一行，每个后面跟着它「写两遍」的结果。再补一句：「三位数就不灵了，123×101 = 12423。」

**结尾 · 星卡「我的乘法魔术」**
- 一张卡片，按固定排版画（不要用动画过程中的位置），三格：
  1. 舰长在第 1 站最后停的那条缝掰开的巧克力，下面写他那条缝的算式（例如 `(2+5)×5 = 2×5 + 5×5 = 35`）。
  2. 第 2 站拼好的 7×5 那一整块，下面写 `3×5 + 4×5 = (3+4)×5`。
  3. 舰长在第 3 站最后停的那个数，写成 `58 × 101 = 5858`，前后两半下面各一道线。
- 三个读数：`试过 x 条缝，都是 35 块`（x 是不同的缝数，最多 6）、`拼成 7×5 = 35`、`我的魔术数：58`。
- 「再玩一次」：全部回到第 1 站开头，**不再发 `complete`**。
- 「我有个问题」随时可用（骨架里已有，发 `note_question`）。

## 6. 针对的误区

`multiply-one-part`（第 1、3 站）、`add-instead-of-multiply`（第 1 站）、`merge-unlike`（第 2 站）、`drop-small-part`（第 3 站），全部写进 manifest 的 `misconceptions`。知识点卡里的 `split-both` 不归这个模块，不要写进去。

## 7. 必须遵守

下面是平台已有模块踩过的坑，逐条照做：

> 出处：`.claude/skills/curio-anatomy/references/lessons.md · 「实现」一节`（提交 `6af4bcb`）

````text
## 实现

1. 所有数字来自页面里的一个 `MODEL` 对象，每个值旁边写出处注释。画面、读数、领航员的话都从它算。
2. 孩子推到的进度 `t` 和画面上缓动跟随的进度 `p` 分开；读数和画面用 `p`。
3. 进度到 98.5% 就算完成（`fin()`），同时把 `t`、`p` 都设成 1，读数对齐到 MODEL 的终值。不然会出现读数已经四舍五入成「1 万倍」，却迟迟不触发完成；或者领航员说「13 米」，读数显示「14 米」。
4. 按住类按钮：`pointerdown` 时 `setPointerCapture`，`pointerup`、`pointercancel`、`lostpointercapture` 都要松开；完成时把 `S.hold` 设成 false；屏蔽长按菜单。
5. 每个动手操作都要有键盘替代：方向键、空格、回车推进同一个 `t`。
6. `prefers-reduced-motion`：缓动系数取 1（直接到位），自动播放的计数和飞入也直接到位，但内容一步不少。
7. 可点的东西互不重叠：每个放置时试几百个候选位置，挑离别人最远的那个；点击判定用到线段的距离，半径至少 26 个 viewBox 单位。
8. SVG 里的字少而大，至少 15 个 viewBox 单位。手机上 800 宽的 viewBox 会缩到不到一半，13 单位的字只剩 6 像素；重要的话放在 SVG 外的领航员气泡和读数里。
9. 颜色全用 CSS 变量（包括 SVG 里的 fill 和 stroke），深色模式自己截图看一遍。
10. 单文件，不联网、不读写存储、不用外部字体和库；先发 `ready`，结束发 `complete`；用到的 verb 都写进 manifest 的 `emits`。
11. 有先后顺序的玩法，要在代码里守住顺序，不能指望孩子按顺序点。染色体配对时孩子先配 X 和 Y，直接跳到了下一站，星卡也坏了。特殊的那一对要求最后配；自动帮忙的循环每一步先确认还在原来的状态。
12. 成就物（星卡）按固定的排版表画，不要用动画过程中的位置：动画没跑完、或者走了意外的路线，星卡也要是对的。
13. 手机上，动手区的 viewBox 要能缩到操作区域（染色体配对时只显示显微镜视野，相当于放大一倍）；点击判定半径按屏幕像素换算：`max(26, 24 × viewBox 宽 ÷ 画面宽)`。
14. SVG 里的字号用 CSS 类控制，并在 `@media (max-width:520px)` 里放大。注意 CSS 里的 `font-size` 会盖过 SVG 元素上的 `font-size` 属性，写在属性上的大字号其实不生效。
15. 事件的意思要准：探索时的试错（配错一对）不要记成 `answered` 错题，否则会被送进维修舱；同一道题只记一次（猜测用 `predicted`，有标准答案的提问用 `answered`）；「再玩一次」不再发 `complete`。
16. 按住类操作完成时，按钮区会换成「继续」。孩子的手指还按着，一松手就会误点到新按钮，跳过一句话（细胞模块的实现者发现）。新按钮如果是在手指按着时换出来的，先禁用，等这次抬起后再启用；记「手指已抬起」要在 `pointerup` 里立刻做，不能推迟，否则正常点击换出来的按钮也会被禁用。骨架里已经写好。
17. 猜测题的正确答案要轮换位置，选项长度尽量相近；不然孩子很快学会「选最后一个」或「选最长的」（DNA 模块四题的正确答案都在最后）。
18. 选项刚出现的约 400 毫秒内忽略点击，免得双击「继续」时第二下替孩子选了答案；每个错误选项都带误区 id。
19. 计数类的成就不能靠重复点击刷出来：同一样本只计一次，`observed` 也只发一次。星卡写「3 种都找过」，不写可被刷大的数字。
20. 手机滚动：不要在整个 svg 和按钮上设 `touch-action:none`，画面占了大半屏，孩子会滑不动页面。svg 用 `touch-action:pan-y`，拖动开始时再 `preventDefault`；按住类按钮可以用 `none`。
21. 换按钮后把焦点移到新按钮的第一个，键盘用户不用再找。
22. 第 16 条也有键盘版：按住空格「念」到完成时，焦点跳到新出现的「继续」，一松开空格就点了它。按键是在按钮出现之前按下的，就忽略这次按键触发的点击（DNA 模块的修改者发现）。
23. 不变的参照物（合上的书、尺子、底座）放在单独一组、永不重画，给它一个 id。这样「纹丝不动」能用程序断言，不用靠看图；一直闪的提示圈用 CSS 动画（并尊重减少动效），不要每帧重建 SVG。
24. 走查脚本也要守第 18 条：每次点按钮前等够 0.4 秒，不然所有点击都被当成误触，一路卡住。
25. 不要在 `pointerdown` 里用 `innerHTML` 重画手指按着的那个元素：元素被删掉，后面的 `touchstart` 就到不了 svg，拦不住滚动，拖动变成了滚页面。在 svg 最上面放一层永远不重画的透明矩形接收触摸（细胞模块的修改者发现；只用 CDP 触摸测不出来，要按真实触摸事件测）。
26. 领航员的话里不要写颜色（「深色的小圆」）：深色模式下颜色会反过来。
27. 焦点移到 svg 以后，鼠标用户也会看到焦点框；用 `:focus-visible`，只在键盘操作时显示。
28. 窄屏的判断不止 520 px：521～600 px 宽的屏幕仍用 800 宽的排版，字会偏小。需要时按 `svg.clientWidth` 算缩放系数再决定排版。
29. 数字和单位：`1207 万个`、`13 公里`，「万」和量词之间不加空格。
30. 用 `references/starter.html` 起步，不要从零写：卡片、领航员气泡、「我有个问题」、Host 契约、手绘线、按住按钮、tick 和 `fin()` 都在里面。
````


另外：

- **和骨架不同的一处**：骨架的结尾 `enterEnd()` 又发了一次 `observed`。本模块每站只在完成时发一次 `observed`（`station` 为 1、2、3），结尾只发 `complete`，不再发 `observed`。
- 领航员的话、词表、画风按下面「星座的共同约定」。不出现「学习」二字；不用字母 a、b、c；不在领航员的话里写颜色。
- 不用外部字体、图片、库；不联网；不读写 `localStorage`、`sessionStorage`、IndexedDB、cookie。

## 8. 测试接缝（审核的走查脚本靠它们，必须保留）

- 页面元素沿用骨架的 id：`#station`（「第 1 站 · 共 3 站」，星卡时写「星卡」）、`#title`、`#hint`、`#readout`、`#say`（领航员气泡）、`#actions`（按钮区，选项按钮带 class `choice`）、`#stage`（动手区 svg，`tabindex="0"`）、`#qarea`。
- 键盘（焦点在 `#stage` 上）：第 1 站拉包装纸用 ↓、空格或回车，拖缝用 ← →（每按一次走一条缝）；第 2 站用 ← → 选要拖的那块，回车或空格把它放到 A 的右边；第 3 站用 ← → 选十位或个位拨盘，↑ ↓ 加减。
- 发给宿主的 `state`：第 1 站 `{station:1, left:k, right:7-k, rows:5, total:35}`；第 2 站 `{station:2, piece:"B"|"C", fits:true|false, sum:…}`；第 3 站 `{station:3, n:…, product:…}`。
- 发给宿主的 `event`：`predicted`（每站一次，`{station, choice, correct, misconception}`，`misconception` 没有时写 `null`）、`observed`（每站完成时一次，`{station}`）。manifest 的 `emits` 写 `[predicted, observed]`。
- `complete` 只在第一次进入星卡时发一次，payload 为 `{}`。

## 9. 起步的骨架（原样从它改起：换掉 `{{…}}`，把两个示例站改成上面的三站）

> 出处：`.claude/skills/curio-anatomy/references/starter.html`（提交 `6af4bcb`）

````text
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{活动标题}}</title>
<style>
:root{
  --bg:#F5F4EE; --pane:#FBFAF6; --rule:#E0DCD0; --hover:#E7E4D9;
  --ink:#1F1E1C; --text:#3B3833; --muted:#7A766D;
  --accent:#C2603F; --accent-soft:#F3E0D6;
  --sage:#CCD6C0; --sage-bg:#DCE3D2; --sky:#CFDCE6; --apricot:#ECCDB6; --paper:#EFE4D6;
  --dad:#4F7FA8; --mom:#C2603F; --good:#3B7A56; --good-soft:#DCEBDF; --bad:#B4432E; --bad-soft:#F5DFD8;
  --f-serif:"Noto Serif SC","Source Han Serif SC","Songti SC",Georgia,serif;
  --f-sans:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  --f-mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#1E1E1E; --pane:#252525; --rule:#353535; --hover:#2E2E2E;
  --ink:#E4E0D8; --text:#CBC6BC; --muted:#8C887F;
  --accent:#E0876A; --accent-soft:#3A2A24;
  --sage:#3C4836; --sage-bg:#28301F; --sky:#2D3B47; --apricot:#5A4536; --paper:#33302A;
  --dad:#7FA9CF; --mom:#E0876A; --good:#7CC79A; --good-soft:#203528; --bad:#EF8A72; --bad-soft:#3A2420;
  color-scheme:dark;
}}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);font-family:var(--f-sans);font-size:17px;line-height:1.65;-webkit-font-smoothing:antialiased}
button{font:inherit;color:inherit;cursor:pointer}
.wrap{max-width:820px;margin:0 auto;padding:12px 14px 28px}
.card{background:var(--pane);border:1px solid var(--rule);border-radius:18px;overflow:hidden}
.card header,.card footer{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:10px 16px}
.card header{border-bottom:1px solid var(--rule)}
.card footer{border-top:1px solid var(--rule);min-height:44px;align-items:center}
.station{font-size:13px;color:var(--muted);letter-spacing:.04em;white-space:nowrap}
h1{font-family:var(--f-serif);font-size:20px;font-weight:600;color:var(--ink);margin:0;text-align:right}
.hint{font-size:14px;color:var(--muted)}
.readout{font-family:var(--f-mono);font-variant-numeric:tabular-nums;color:var(--ink);font-size:15px;text-align:right}
.readout b{color:var(--accent);font-weight:600}
svg#stage{display:block;width:100%;height:auto;touch-action:pan-y;user-select:none;-webkit-user-select:none}
svg#stage:focus{outline:none}
svg#stage:focus-visible{outline:2px solid var(--accent);outline-offset:-4px}
.k{fill:none;stroke:var(--ink);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.k1{fill:none;stroke:var(--ink);stroke-width:1.3;stroke-linecap:round;stroke-linejoin:round}
.kf{fill:none;stroke:var(--muted);stroke-width:1.2;stroke-linecap:round;stroke-dasharray:3 6}
.thread{fill:none;stroke:var(--accent);stroke-width:4;stroke-linecap:round;stroke-linejoin:round}
.thread-thin{fill:none;stroke:var(--accent);stroke-width:2.2;stroke-linecap:round}
.t{fill:var(--ink);font-family:var(--f-sans);font-size:15px}
.tm{fill:var(--muted);font-family:var(--f-sans);font-size:13px}
.num{fill:var(--ink);font-family:var(--f-mono);font-size:12px}
.talk{display:flex;gap:10px;align-items:flex-start;margin:14px 2px 6px}
.ava{flex:none;width:42px;height:42px}
.bubble{background:var(--pane);border:1px solid var(--rule);border-radius:16px 16px 16px 4px;padding:10px 14px;color:var(--ink);min-height:44px;flex:1}
.bubble.good{background:var(--good-soft);border-color:transparent}
.bubble.bad{background:var(--bad-soft);border-color:transparent}
.actions{display:flex;flex-wrap:wrap;gap:10px;justify-content:flex-end;margin:10px 0 0}
.btn{border:1.5px solid var(--ink);background:var(--ink);color:var(--bg);border-radius:12px;padding:9px 18px;min-height:48px;font-size:17px;font-weight:600;touch-action:manipulation}
.btn.hold{touch-action:none}
.btn.ghost{background:var(--pane);color:var(--ink)}
.btn.choice{background:var(--bg);color:var(--ink);font-weight:500;text-align:left;flex:1 1 220px}
.btn.choice:hover{background:var(--hover)}
.btn.hold{background:var(--accent);border-color:var(--accent);color:#fff}
.btn.hold.on{filter:brightness(.9)}
.btn:disabled{opacity:.4;cursor:default}
.btn.small{min-height:40px;font-size:15px;padding:6px 14px;font-weight:500}
.qbox{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}
.qbox textarea{flex:1 1 260px;font:inherit;font-size:16px;padding:8px 10px;border:1.5px solid var(--ink);border-radius:12px;background:var(--bg);color:var(--ink);min-height:64px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@media (max-width:520px){ body{font-size:16px} h1{font-size:17px} .card header,.card footer{padding:8px 12px} }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <header><span class="station" id="station"></span><h1 id="title"></h1></header>
    <svg id="stage" viewBox="0 0 800 610" tabindex="0" role="application" aria-label="动手区">
      <g id="static"></g><g id="dyn"></g>
      <rect id="touch" x="-400" y="-400" width="1600" height="1410" fill="transparent"/><!-- 永不重画的触摸层：重画 dyn 时不会删掉手指按着的元素 -->
    </svg>
    <footer><span class="hint" id="hint"></span><span class="readout" id="readout"></span></footer>
  </div>
  <div class="talk">
    <svg class="ava" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="27" r="16" fill="var(--sky)"/>
      <path class="k" d="M9 27 C9 18 15 11 24 11 C33 11 39 18 39 27 C39 36 33 43 24 43 C15 43 9 36 9 27 Z"/>
      <path class="k1" d="M24 11 L24 5 M21 4.5 C22 3.5 26 3.5 27 4.5"/>
      <circle cx="18.5" cy="25" r="2.2" fill="var(--ink)"/><circle cx="29.5" cy="25" r="2.2" fill="var(--ink)"/>
      <path class="k1" d="M18 32 C21 35 27 35 30 32"/>
    </svg>
    <div class="bubble" id="say" aria-live="polite"></div>
  </div>
  <div class="actions" id="actions"></div>
  <div id="qarea"></div>
</div>

<script>
"use strict";
/* 好奇号 · 动手探索模块骨架（来自 act.simulation.chromosome-pack-01）。复制本文件，把 {{…}} 换成具体内容。 */

/* ============ 1. 真相模型：页面上的每个数字都从这里算，每个值旁边写出处 ============ */
const MODEL = {
  example: 100,            // {{量的含义}}（{{出处}}）
};
const fmt = n => String(Math.round(n));

/* ============ 2. 平台契约 activity/1.1（单独打开时也能玩） ============ */
const Host = (() => {
  const h = {}, inFrame = window.parent !== window;
  addEventListener("message", e => { const m = e.data; if (m && m.contract === "activity/1.1" && h[m.type]) h[m.type](m.payload || {}); });
  const send = (type, payload) => { if (inFrame) parent.postMessage({ contract: "activity/1.1", type, payload: payload || {} }, "*"); };
  if (window.ResizeObserver) new ResizeObserver(() => send("resize", { h: document.documentElement.scrollHeight })).observe(document.body);
  return { on: (k, f) => { h[k] = f; }, ready: () => send("ready"), event: (verb, result) => send("event", { verb, result }),
    state: o => send("state", o), noteQuestion: text => send("note_question", { text }), complete: r => send("complete", r || {}) };
})();
Host.on("init", p => {
  if (p && p.palette) for (const [k, v] of Object.entries(p.palette)) if (/^[a-z-]+$/.test(k)) document.documentElement.style.setProperty("--" + k, v);
});

/* ============ 3. 手绘线条（平台的 sketchLib） ============ */
function sketchLib(){
  const R=(seed)=>{ let s=((seed|0)*2654435761)>>>0||7; return ()=>{ s^=s<<13; s>>>=0; s^=s>>>17; s^=s<<5; s>>>=0; return s/4294967296; }; };
  const f=n=>Math.round(n*10)/10;
  function cr(p,closed){ const n=p.length; let d=`M${f(p[0][0])} ${f(p[0][1])}`;
    for(let i=0;i<(closed?n:n-1);i++){ const p1=p[i],p2=p[(i+1)%n]; const p0=(!closed&&i===0)?p1:p[(i-1+n)%n]; const p3=(!closed&&i+2>=n)?p2:p[(i+2)%n];
      d+=`C${f(p1[0]+(p2[0]-p0[0])/6)} ${f(p1[1]+(p2[1]-p0[1])/6)} ${f(p2[0]-(p3[0]-p1[0])/6)} ${f(p2[1]-(p3[1]-p1[1])/6)} ${f(p2[0])} ${f(p2[1])}`; }
    return d; }
  function line(x1,y1,x2,y2,seed,j){ const r=R(seed); j=j==null?1:j; const L=Math.hypot(x2-x1,y2-y1)||1; const a=Math.min(1.8,.5+L*.008)*j; const o=()=>(r()-.5)*2*a;
    const nx=-(y2-y1)/L, ny=(x2-x1)/L, bow=(r()-.5)*Math.min(L*.035,6)*j;
    return `M${f(x1+o())} ${f(y1+o())}Q${f((x1+x2)/2+nx*bow)} ${f((y1+y2)/2+ny*bow)} ${f(x2+o())} ${f(y2+o())}`; }
  function ellipse(cx,cy,rx,ry,seed,j){ const r=R(seed); j=j==null?1:j; const N=12, a0=r()*Math.PI*2, turn=1.05+r()*.06, p=[];
    for(let i=0;i<=N;i++){ const t=a0+i/N*Math.PI*2*turn, k=1+(r()-.5)*.07*j; p.push([cx+Math.cos(t)*rx*k, cy+Math.sin(t)*ry*k]); }
    return cr(p,false); }
  function blob(cx,cy,rx,ry,seed){ const r=R(seed), N=9, p=[]; for(let i=0;i<N;i++){ const t=i/N*Math.PI*2, k=1+(r()-.5)*.1; p.push([cx+Math.cos(t)*rx*k, cy+Math.sin(t)*ry*k]); } return cr(p,true)+"Z"; }
  function curve(pts,seed,j){ const r=R(seed); j=j==null?1:j; return cr(pts.map(q=>[q[0]+(r()-.5)*2*j,q[1]+(r()-.5)*2*j]),false); }
  return {line,ellipse,blob,curve,cr,R};
}
const Sk = sketchLib();
const P = (d, cls, extra) => `<path class="${cls || "k"}" d="${d}"${extra ? " " + extra : ""}/>`;
const T = (x, y, s, cls, extra) => `<text x="${x}" y="${y}" class="${cls || "t"}"${extra ? " " + extra : ""}>${s}</text>`;
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const smooth = t => t * t * (3 - 2 * t);
const lerp = (a, b, t) => a + (b - a) * t;

/* ============ 4. 页面骨架 ============ */
const $ = id => document.getElementById(id);
const svg = $("stage"), gStatic = $("static"), gDyn = $("dyn");
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const STATIONS = 2;   // 一共几站
// t1 是孩子操作推到的进度（0～1），p1 是画面上缓动跟随的进度；读数和画面都用 p
const S = { station: 1, mode: "talk", hold: false, t1: 0, p1: 0, t2: 0, p2: 0 };

function head(n, title){ $("station").textContent = n ? `第 ${n} 站 · 共 ${STATIONS} 站` : "星卡"; $("title").textContent = title; }
function hint(s){ $("hint").textContent = s || ""; }
function readout(html){ $("readout").innerHTML = html || ""; }
function say(text, tone){ const b = $("say"); b.textContent = text; b.className = "bubble" + (tone ? " " + tone : ""); }
// 手指还按着时换出来的新按钮，先禁用到手指抬起，免得松手时误点（按住类操作刚完成时最常见）
let fingerDown = false;
addEventListener("pointerdown", () => { fingerDown = true; }, true);
for (const ev of ["pointerup", "pointercancel"]) addEventListener(ev, () => { fingerDown = false; }, true);   // 抬起时立刻记下：随后的 click 里换出的按钮不必禁用
// 键盘版：按住空格或回车时换出来的新按钮会拿到焦点，松键就会点到它。按键在按钮出现前就按下了，这次点击不算
let keysDown = 0;
addEventListener("keydown", e => { if (!e.repeat) keysDown++; }, true);
addEventListener("keyup", () => { keysDown = Math.max(0, keysDown - 1); }, true);
addEventListener("blur", () => { keysDown = 0; });
function actions(list){
  const box = $("actions"); box.replaceChildren();
  const guard = fingerDown, born = performance.now();
  let keyGuard = keysDown > 0;
  if (keyGuard){ const off = () => { if (keysDown === 0){ setTimeout(() => { keyGuard = false; }, 0); removeEventListener("keyup", off, true); } }; addEventListener("keyup", off, true); }
  for (const a of list || []){
    const b = document.createElement("button");
    b.type = "button"; b.className = "btn " + (a.cls || ""); b.textContent = a.label;
    if (a.hold){
      const on = v => { S.hold = v; b.classList.toggle("on", v); };
      b.addEventListener("pointerdown", e => { e.preventDefault(); b.setPointerCapture && b.setPointerCapture(e.pointerId); on(true); });
      for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) b.addEventListener(ev, () => on(false));
      b.addEventListener("keydown", e => { if (e.key === " " || e.key === "Enter"){ e.preventDefault(); a.step(); } });
      b.addEventListener("contextmenu", e => e.preventDefault());
    } else {
      // 刚出现的 0.4 秒内不响应，免得双击「继续」时第二下替孩子选了答案
      b.addEventListener("click", e => { if (performance.now() - born < 400 || (keyGuard && e.detail === 0)) return; a.go(e); });
      if (guard){ b.disabled = true; const on = () => { setTimeout(() => { b.disabled = false; }, 120); removeEventListener("pointerup", on, true); }; addEventListener("pointerup", on, true); }
    }
    box.append(b);
  }
  const first = box.querySelector("button");
  if (first && !/^act/.test(S.mode)) first.focus({ preventScroll: true });   // 键盘用户不用再找按钮
  return box;
}
function ask(question, options, onAnswer){
  say(question);
  actions(options.map((o, i) => ({ label: o.label, cls: "choice", go: () => {
    Host.event("predicted", { station: S.station, choice: i, correct: !!o.correct, misconception: o.mis || null });
    say(o.feedback, o.correct ? "good" : "bad");
    onAnswer(o);
  }})));
}
function next(label, go, cls){ actions([{ label, go, cls }]); }

// 「我有个问题」：随时可以问，发到信号站
(function(){
  const area = $("qarea");
  const open = document.createElement("button");
  open.type = "button"; open.className = "btn ghost small"; open.textContent = "我有个问题";
  open.style.marginTop = "12px";
  open.addEventListener("click", () => {
    if (area.querySelector("textarea")) return;
    const ta = document.createElement("textarea"); ta.maxLength = 120; ta.placeholder = "想问领航员什么？";
    const send = document.createElement("button"); send.type = "button"; send.className = "btn small"; send.textContent = "发给领航员";
    const box = document.createElement("div"); box.className = "qbox"; box.append(ta, send);
    send.addEventListener("click", () => {
      const q = ta.value.trim(); if (!q) return;
      Host.noteQuestion(q); box.remove(); say("好问题，我记下来了。等会儿一起找答案。");
    });
    area.append(box); ta.focus();
  });
  area.append(open);
})();


/* ============ 5. 第 1 站（示例：拖动） ============ */
function draw1(){
  // 用 Sk.line / Sk.ellipse / Sk.blob / Sk.curve 画手绘线，色块用 CSS 变量；主角只用 var(--accent)
  const x = 120 + 560 * S.p1;
  return P(Sk.line(120, 300, 680, 300, 11), "k1") +
    `<circle cx="${x}" cy="300" r="22" fill="var(--accent)"/>` + P(Sk.ellipse(x, 300, 22, 22, 12)) +
    `<circle id="knob" cx="${x}" cy="300" r="40" fill="transparent"/>`;
}
function readout1(){ readout(`读数 <b>${fmt(MODEL.example * S.p1)}</b>`); Host.state({ station: 1, value: MODEL.example * S.p1 }); }
function enter1(){
  S.station = 1; S.mode = "talk"; head(1, "{{第 1 站标题}}"); gStatic.innerHTML = ""; render();
  // 先猜：每个错误选项对应一个误区 id，反馈先接住、再说清
  ask("{{猜测题}}", [
    { label: "{{误区选项}}", mis: "{{误区 id}}", feedback: "{{先接住，再说清}}" },
    { label: "{{正确选项}}", correct: true, feedback: "{{猜对了，我们试试}}" }
  ], () => next("开始", act1));
}
function act1(){ S.mode = "act1"; hint("{{操作提示}}"); say("{{领航员说怎么做}}"); actions([]); readout1(); svg.focus({ preventScroll: true }); }
function done1(){ S.mode = "talk"; hint(""); Host.event("observed", { station: 1 }); say("{{揭晓 + 一个从 MODEL 算出来的「哇」}}", "good"); next("去第 2 站", enter2); }

/* ============ 6. 第 2 站（示例：按住） ============ */
function draw2(){ return `<circle cx="400" cy="300" r="${40 + 160 * S.p2}" fill="var(--sage)" opacity=".7"/>` + P(Sk.ellipse(400, 300, 40 + 160 * S.p2, 40 + 160 * S.p2, 21)); }
function enter2(){
  S.station = 2; S.mode = "act2"; head(2, "{{第 2 站标题}}"); gStatic.innerHTML = ""; render();
  hint("按住「{{动作}}」"); say("{{领航员说怎么做}}");
  actions([{ label: "按住 {{动作}}", cls: "hold", hold: true, step: () => { S.t2 = clamp(S.t2 + .05); } }]);
}
function done2(){ S.mode = "talk"; Host.event("observed", { station: 2 }); say("{{揭晓}}", "good"); next("看我的星卡", enterEnd); }

/* ============ 7. 结尾：星卡（孩子亲手做出来的东西 + 三个读数） ============ */
function drawEnd(){
  return `<rect x="30" y="20" width="740" height="570" rx="20" fill="var(--pane)" stroke="var(--rule)"/>` +
    `<path d="M712 44l7 14 15 2-11 11 3 15-14-7-14 7 3-15-11-11 15-2z" fill="var(--accent)" opacity=".85"/>` +
    T(60, 72, "{{星卡标题}}", "t", 'font-size="26" font-family="var(--f-serif)"');
}
function enterEnd(){
  S.station = STATIONS + 1; S.mode = "end"; head(0, "{{星卡标题}}"); hint(""); readout(""); gStatic.innerHTML = ""; render();
  say("{{收尾的话}}", "good"); Host.event("observed", { station: STATIONS }); Host.complete({});
  next("再玩一次", () => { Object.assign(S, { t1: 0, p1: 0, t2: 0, p2: 0 }); enter1(); }, "ghost");
}

/* ============ 8. 画面和输入 ============ */
function render(){ svg.style.touchAction = /^act|^pair$/.test(S.mode) ? "none" : "pan-y"; gDyn.innerHTML = S.station === 1 ? draw1() : S.station === 2 ? draw2() : drawEnd(); }
function toSvg(e){ const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; return pt.matrixTransform(svg.getScreenCTM().inverse()); }
let drag = null;
svg.addEventListener("pointerdown", e => {
  const q = toSvg(e);
  if (S.mode === "act1" && Math.hypot(q.x - (120 + 560 * S.p1), q.y - 300) < 60) drag = { x0: q.x, t0: S.t1 };
  if (drag){ svg.setPointerCapture(e.pointerId); e.preventDefault(); }
});
svg.addEventListener("pointermove", e => { if (drag) S.t1 = clamp(drag.t0 + (toSvg(e).x - drag.x0) / 560); });
for (const ev of ["pointerup", "pointercancel"]) svg.addEventListener(ev, () => { drag = null; });
svg.addEventListener("keydown", e => {   // 键盘替代：每个动手操作都要有
  if (!/Arrow|Enter| /.test(e.key)) return;
  if (S.mode === "act1"){ e.preventDefault(); S.t1 = clamp(S.t1 + .05); }
  if (S.mode === "act2"){ e.preventDefault(); S.t2 = clamp(S.t2 + .05); }
});

let last = performance.now();
function tick(now){
  const dt = Math.min(.05, (now - last) / 1000); last = now;
  let dirty = false;
  if (S.hold && S.mode === "act2") S.t2 = clamp(S.t2 + dt * .4);
  const k = reduced ? 1 : 1 - Math.exp(-dt / .12);       // 指数跟随；减少动效时直接到位
  for (const n of [1, 2]){
    const t = S["t" + n], p = S["p" + n];
    if (Math.abs(t - p) > 1e-4){ S["p" + n] = Math.abs(t - p) < 1e-3 ? t : p + (t - p) * k; dirty = true; }
  }
  // 到 98.5% 就算完成，并把读数对齐到 MODEL 的终值
  const fin = n => { if (S["t" + n] >= .985 && S["p" + n] > .975){ S["t" + n] = S["p" + n] = 1; S.hold = false; return true; } return false; };
  if (dirty && S.station <= STATIONS){
    render();
    if (S.mode === "act1"){ const f = fin(1); readout1(); if (f){ render(); done1(); } }
    if (S.mode === "act2"){ const f = fin(2); if (f){ render(); done2(); } }
  }
  requestAnimationFrame(tick);
}
enter1();
Host.ready();
requestAnimationFrame(tick);
</script>
</body>
</html>
````


## 10. 验收清单（逐屏）

审核会把你的模块放进平板 820×1180 浅色、手机 390×844 深色、电脑 1280×900 浅色加 `prefers-reduced-motion` 三种环境，从头玩到尾，逐张截图看；除了下面这些条目，也看**好不好看、耐不耐看**：线条是不是手绘的、留白够不够、主角是不是一眼就能找到、深色模式是不是一样好看。

1. 不看任何字，能看懂每一站在演什么：拉开包装纸、掰开、拼起来、魔术机吐出数。
2. 孩子的动作真的改变了巧克力的状态，读数跟着变；第 2 节的验收用例逐条对得上。
3. 先问再揭晓：三次提问之前，画面和读数都不泄露答案（第 1 站下面 4 排被包装纸挡着；第 2、3 站提问前只有算式牌）。
4. 每个错误选项都带误区 id，反馈先接住再说清；三题正确答案的位置各不相同（按第 5 节给的顺序）。
5. 「乘法分配律」这个名字在第 1 站动手时第一次出现。
6. 「哇」画出来了：漏掉的 16 块被圈出来；6 块缩略图都是 35；「写两遍」的结果排成一行。
7. 星卡用的是舰长自己停的那条缝、自己选的那个数，按固定排版画；「再玩一次」后状态全部复位，不再发 `complete`。
8. 平板、手机都能完整操作，只用触摸也行；画面外的页面能正常上下滑；键盘能走完全程；`prefers-reduced-motion` 时动画直接到位，内容不少。
9. 浅色、深色都清楚好看：墨线、巧克力、字在两种模式下都看得清；主角色只给主角用。
10. 不联网、不读写存储、不用外部字体和库；先发 `ready`，结尾发 `complete`；只发 `emits` 里写了的 verb；manifest 符合第 11 节的格式。
11. 没有「学习」二字；领航员叫孩子「舰长」，每句不超过 40 个字；没有字母 a、b、c；没有说「任何数乘 101 都是写两遍」。

如果你能运行浏览器，按上面三种环境自己走一遍、截图检查，至少改两轮再交。不能运行的话，在交付包的「自查」里逐条写明你是怎样确认的，不确定的就写「未验证」，不要写打勾。

## 星座的共同约定（原样贴入）

> 出处：`docs/constellations/multiplication.md · 「星座概况」一节`（提交 `6af4bcb`）

````text
## 星座概况

- **舰长**：小学三年级的孩子，8 岁左右。会背乘法口诀，会口算两位数乘一位数（12×3），认识小括号（先算括号里面的）。还没在学校里学过「运算律」，也没见过用字母写的式子。
- **这个星座讲什么**：乘法藏着的几条规律，以及怎么用它们把难算的乘法变好算。第一颗星是乘法分配律；以后可能加入乘法交换律、乘法结合律、两位数乘两位数。
- **第一颗星的活动**：一个动手探索模块「掰巧克力」（模拟，约 8 分钟）。之后再补结构化的讲解和挑战。

| 星 | 知识点 id | 动手探索 |
| --- | --- | --- |
| 乘法分配律 | `math.operation.distributive-law` | `act.simulation.chocolate-split-01` |
````


> 出处：`docs/constellations/multiplication.md · 「领航员怎么说话」一节`（提交 `6af4bcb`）

````text
## 领航员怎么说话

领航员是飞船上陪舰长探索的向导。

- **称呼**：叫孩子「舰长」，自称「我」。不说「同学们」「小朋友」「老师」，不出现「学习」二字。
- **一句话一件事**：气泡里每次一两句话，一句不超过 40 个字。
- **先问再讲**：每一站先让舰长猜，再让他动手找答案，最后用一句话说清刚才看到的是什么。
- **可以犯错的领航员**：领航员可以先算错一次，让舰长帮他找出错在哪里（第 1 站就是这样开场的）。说错的话要马上由画面纠正，不能留到下一站。
- **答错时先接住**：先承认这个想法有道理（「很多人第一次都这么算」「看起来确实像」），再用一句话说清哪里不对。不说「错了」「不对哦」开头。
- **像一起探险**：语气好奇、平等，说具体的东西（一排、一块、一条缝），少用抽象的词。一个模块里感叹号不超过 3 个。
- **不在话里写颜色**：深色模式下颜色会变，说「那条缝」「细细的那一列」，不说「红色的缝」。
````


> 出处：`docs/constellations/multiplication.md · 「词表」一节`（提交 `6af4bcb`）

````text
## 词表

| 可以用 | 意思 | 不要用 |
| --- | --- | --- |
| 排、每排几块 | 巧克力横着的一行叫「一排」；「每排 7 块，有 5 排」 | 行、列、矩阵、阵列、面积 |
| 缝 | 巧克力块和块之间可以掰开的那条线 | 分割线、刻痕 |
| 掰开、拼起来 | 把一块分成两块；把两块合成一块 | 分解、合并同类项、提取公因数 |
| 算式、括号 | 「(3+4)×5」里的小括号，先算括号里面的 | 表达式、代数式 |
| 乘法分配律 | 第 1 站动手时第一次说出名字，以后都用这个名字 | 分配率（错字）、分配法则 |
| 一样多、一块都不少 | 两边相等 | 恒等、等价 |

- 不用字母（a、b、c），只用具体的数。
- 「×」「+」「=」「( )」可以用；不用「≠」，说「不一样多」。
- 读数里的数字用阿拉伯数字，单位「块」「排」紧跟数字，不加空格：`35 块`、`5 排`。
````


> 出处：`docs/constellations/multiplication.md · 「画风」一节`（提交 `6af4bcb`）

````text
## 画风

- **底子**：和「生命的说明书」三个模块同一套 Claude 画风：暖纸面、手绘墨线（带一点抖动、线头是圆的）、淡彩色块不描边、深色模式是 Obsidian 风格的夜色，两种模式共用同一套线稿。颜色全部用 CSS 变量。
- **巧克力**：用杏色 `--apricot` 做块，块和块之间留出墨线画的缝（`k1` 细线）。深色模式下杏色变成深棕，正好像巧克力。每一小块可以有一道很浅的高光线，不要渐变、阴影。
- **主角**（陶土红 `--accent`，整个画面只给它用）：第 1 站是孩子拖的那条缝和它的把手；第 2 站是孩子正在拖的那一块；第 3 站是乘 101 时多出来的那「1 列」。
- **包装纸**：纸色 `--paper`，上面一个手写感的小标签（「5 排」）。
- **算式牌**：画面外的读数区和画面里的小牌子都可以写算式；画面里的字至少 15 个 viewBox 单位，最多几个短标签。
- **不要**：真实品牌的包装和标志、卡通吉祥物、照片、渐变、阴影、闪光特效。
````


> 出处：`docs/constellations/multiplication.md · 「事实和出处」一节`（提交 `6af4bcb`）

````text
## 事实和出处

数学事实本身不需要出处，但**画面上的每个数字都要从页面里的 `MODEL` 算出来**。和教材、课标有关的说法，只用下表里的。

| 事实 | 出处 |
| --- | --- |
| 乘法分配律：两个数的和与一个数相乘，可以先把它们分别与这个数相乘，再把两个积相加，(a+b)×c = a×c + b×c | 人教版小学数学四年级下册（旧版）第三单元「运算定律」；《义务教育数学课程标准（2022 年版）》第二学段「数与运算」：探索并理解运算律 |
| 口算 12×3：先算 10×3 = 30，再算 2×3 = 6，30 + 6 = 36 | 人教版小学数学三年级上册（旧版）「多位数乘一位数」口算乘法 |
| 把一个因数拆开，可以由已知的乘法推出新的乘法 | NCETM「Connecting multiplication and division, and the distributive law」 |

**容易讲错的地方**：

- 不要说「乘法分配律是三年级学的」：它在四年级的运算律单元。可以说「四年级会正式学到它，今天我们先在巧克力上把它找出来」。
- 不要说「所有的数都能这样拆」「拆成哪两个数都一样快」：拆成整十、整百才变好算，随便拆只是「一样多」，不一定更好算。
- 乘 101 的魔术只对**两位数**成立（37×101 = 3737）。三位数不是「写两遍」（123×101 = 12423），不要说「任何数」。
- 「排数一样才能拼成一整块」说的是巧克力；落到算式上，说「两个乘法里有一个一样的数，才能合起来」。不要说成「两个算式一样才能合」。
````


## 画风和适龄（来自平台的设计方法，原样贴入）

> 出处：`.claude/skills/curio-anatomy/SKILL.md · 「Claude 画风」一节`（提交 `6af4bcb`）

````text
## Claude 画风

- **纸和墨**：浅色是暖纸面 `#F5F4EE`，墨线 `#1F1E1C`，手绘的线带一点抖动，线头是圆的。深色是 Obsidian 风格的夜色，墨线换成浅色。两种模式共用同一套线稿。
- **淡彩**：鼠尾草绿 `#CCD6C0`、天蓝 `#CFDCE6`、杏色 `#ECCDB6`、纸色 `#EFE4D6`，透明度 0.6 到 0.85，色块不描边。
- **强调色**：陶土红 `#C2603F`，整个画面只给主角用。爸爸蓝 `#4F7FA8`、妈妈红 `#C2603F` 这类有意义的颜色，要在图注里说明。
- **字**：标题用衬线体，读数用等宽数字。画面里最多几个短标签，说明放在画面外。
- **卡片**：每一站是一张卡片。左上写「第 1 站 · 共 3 站」，右上写标题，左下写操作提示（「转动把手」），右下写实时读数。
- **动效**：克制。用指数跟随或真实的弹簧，不用花哨的弹跳。没人碰时可以慢慢演示一遍。尊重 `prefers-reduced-motion`：动画变成直接到位，内容不少。
- **留白**：画面占卡片的六成左右，四周留空。
````


> 出处：`.claude/skills/curio-anatomy/SKILL.md · 「适龄」一节`（提交 `6af4bcb`）

````text
## 适龄

- **三四年级**：一屏只做一件事。字少，句子短，说具体的东西。动作要大：拖、转、按住。数字配孩子世界里的对照（身高、操场、乒乓球）。不出现「学习」二字。
- **初中以上**：可以显示单位、公式和真实数值，可以给两个控件让孩子比较。
````


> 出处：`.claude/skills/curio-anatomy/SKILL.md · 「检查」一节`（提交 `6af4bcb`）

````text
## 检查

像挑刺的人一样检查。手机（390 px 宽）、平板、电脑各截一张图，浅色和深色各一张，动起来的几个瞬间也要截。每张图都要打开看。然后回答：

1. 不看任何字，能看懂画面在演什么吗？
2. 孩子的动作真的改变了实物的状态吗？读数跟着变吗？
3. 有让人「哇」的数字或事实吗？它是从真相表算出来的吗？
4. 做完以后，孩子手里有自己做出来的东西吗？
5. 孩子会想再玩一次吗？
6. 画面上的每个数字都有出处吗？
7. 放大看，线条有没有断在半空、文字有没有挤出卡片？

有一条答「不」，就接着改。
````


## 写给孩子的内容要求（原样贴入）

> 出处：`docs/standards.md · 「给孩子看的内容」一节`（提交 `6af4bcb`）

````text
## 给孩子看的内容

- **科学上准确**。数学上对的答案不能判错（例如等值分数）；简化讲法不能和以后要教的内容矛盾。
- **先教后用**。题目、提示里用到的词，讲解里要先出现。
- **一句话只说一件事**。题干一次只问一个问题。
- **提示是梯子**。一条比一条更具体，前一条没帮上忙，后一条才多给一点。最后一条有没有说出答案，数字题、分数题由 CI 检查，选择题由 CI 提醒、审核者判断（内容规格 3.4）。
````


## 术语表（界面文字、注释都用这里的词）

> 出处：`GLOSSARY.md · 「给孩子看的世界」一节`（提交 `6af4bcb`）

````text
## 给孩子看的世界

**舰长**：
用好奇号的孩子。界面上这样称呼他。
_避免_：学生、用户、学习者（「学习者」只用于技术文档里的对象名 Learner）

**领航员**：
飞船上陪舰长探索的向导。讲解用对话方式显示时，说话的就是领航员。
_避免_：老师、AI 助手、机器人

**星图**：
把全部知识点画成星空的主界面，一颗星是一个知识点。
_避免_：知识图谱、课程表

**星座**：
星图里一组相关的知识点，用来在知识点很多时分组缩放。
_避免_：单元、章节（教材单元另有字段 `unit`）

**掌握度**：
孩子对一个知识点掌握到什么程度，由事件算出：没碰过、探索过、已点亮。
_避免_：分数、成绩、进度

**点亮**：
掌握度的最高一级，星图上的那颗星亮起来。
_避免_：完成、通关、学会

**知识地铁**：
按课标大概念把知识点串成线路的视图，一条线是一个大概念，一站是一个知识点。
_避免_：路线图、学习路径

**维修舱**：
存放错题的地方，孩子在这里把错题「修好」。
_避免_：错题本（只在对家长说明时用）

**信号站**：
存放孩子提出的「为什么」的地方。
_避免_：问题本、提问箱

**今日航线**：
孩子某一天要做的几项任务，也就是打卡。界面上是辅助功能。
_避免_：打卡表、作业、计划

**指挥中心**：
家长用的页面：看进度、设奖励、确认兑换。
_避免_：后台、管理端

**能量**：
孩子完成事情累计得到的点数，表示一共付出了多少努力。
_避免_：积分、经验值

**补给点**：
和能量同时得到、可以向家长兑换奖励的点数。
_避免_：积分、金币
````


> 出处：`GLOSSARY.md · 「内容」一节`（提交 `6af4bcb`）

````text
## 内容

**知识点**：
一个可以独立掌握的概念，例如「分数的初步认识」，是星图上的一颗星。
_避免_：课、题、节点（「节点」只在图论语境下用）

**活动**：
围绕知识点的一次互动，分讲解、挑战、反思、实验、模拟五种。
_避免_：模块、练习、课件

**讲解**：
按步骤展示、中途可以穿插小问题的活动。
_避免_：教程、课文

**挑战**：
一组题目，由平台判分。
_避免_：测验、考试、作业

**反思**：
请孩子用一句话写下发现的活动。
_避免_：总结、作文

**实验**、**模拟**：
平台通用引擎做不了、需要单独编写、运行在沙箱里的互动。实验对应真实世界的操作，模拟展示看不见的过程。
_避免_：小游戏、动画

**误区**：
孩子在一个知识点上常有的错误想法，每个都有 ID，题目的错误选项会标明它对应哪个误区。
_避免_：错因、易错点

**提示阶梯**：
一道题的 1～3 条提示，从轻到重，最后一条也不直接说出答案。
_避免_：答案解析、hint

**预测 → 观察 → 解释**：
实验的三步：先猜，再看，再说为什么。前后两步由平台负责，实验只做「观察」。
_避免_：POE（只在技术文档里作为缩写）

**发布**：
一组已审核内容的快照，用内容哈希作为身份。
_避免_：版本、上线

**部署**：
「现在生效的是哪个发布」这个可以切换、可以回滚的指针。
_避免_：发布（两者不能混用）

**引擎等级**：
共享引擎支持哪些内容格式的编号。
_避免_：版本号

**宿主**：
平台里负责运行自定义活动的那部分：把活动放进沙箱、转发消息、记下事件。
_避免_：容器、播放器

**契约**：
自定义活动和宿主之间允许传递哪些消息、每条长什么样的约定，例如 activity/1.1。
_避免_：接口协议、API
````


> 出处：`GLOSSARY.md · 「协作」一节`（提交 `6af4bcb`）

````text
## 协作

**任务文件**：
发给实现 AI 的、自成一体的提示词文件，由 `tools/make_task.py` 从已合入的提交生成。
_避免_：工单、prompt

**交付包**：
实现 AI 按固定格式交回来的全部文件和说明。
_避免_：提交、PR（这两个词只指 git 里的东西）

**收货**：
用 `tools/intake.py` 检查交付包是否完整，并记下每个文件的指纹。
_避免_：验收（「验收」指 Luka 按步骤亲自检查）

**打回**：
审核没通过，附上修改提示词，请同一个实现 AI 重交。
_避免_：拒绝、驳回

**竖切片**：
一个从内容、内核到界面都打通的窄任务，单独完成后就能演示或验收。打通全链路的第一条竖切片叫「曳光弹」。
_避免_：模块任务、分层任务

**测试接缝**：
测试观察行为的公开接口，在规格和任务文件里事先定好。
_避免_：测试点、钩子
````


## 技术契约 activity/1.1（必须遵守，原样贴入）

> 出处：`docs/activity-contract.md`（提交 `6af4bcb`）

````text
# 互动模块契约 activity/1.1

互动模块是讲解、实验、测验等可插拔的小程序。每个模块由两个文件组成：

- `manifest.yaml`：描述模块，格式见 `schemas/activity.schema.json`；
- `index.html`：单文件实现。

平台把模块放进 `sandbox="allow-scripts"` 的 iframe 里运行，双方只通过 `postMessage` 通信。每条消息都带 `contract: "activity/1.1"`，不带的一律忽略。

## 硬性约束

- 不发起任何网络请求，不读写 `localStorage` 或 IndexedDB。
- 不依赖外部 CDN，所需的库全部内联。
- 在 768 px 宽的平板上完整可用，只用触摸也能操作。
- 支持键盘操作，尊重 `prefers-reduced-motion`。
- 实验类：画面和读数必须来自同一个模型。读数措辞按 `age_band` 选择，三四年级用「更亮 / 更暗、清楚 / 模糊」，初二以上再显示公式和数值。

## 消息

| 方向 | type | payload | 说明 |
| --- | --- | --- | --- |
| 模块 → 平台 | `ready` | — | 模块加载完成。平台 3 秒内没收到 `ready`，会记一条契约警告。 |
| 平台 → 模块 | `init` | `{age_band, lang, phase, palette, mastery}` | `palette` 是当前主题的颜色表，模块据此设置自己的 CSS 变量，保证和平台的明暗主题一致。 |
| 平台 → 模块 | `phase` | `{phase}` | 实验类的阶段：`predict`（锁定操作）、`observe`（解锁）。 |
| 模块 → 平台 | `event` | `{verb, result}` | 一条学习事件。`verb` 必须在 manifest 的 `emits` 里声明过，否则平台会记一条契约警告。 |
| 模块 → 平台 | `state` | 可观测量的当前值 | 实验类在每次变化时发送，平台用它生成「解释」一步里的对比，例如亮度从「很暗」变成「较亮」。 |
| 模块 → 平台 | `request_hint` | — | 请求下一级提示。 |
| 平台 → 模块 | `hint` | `{level}` | 允许显示第 `level` 级提示。 |
| 模块 → 平台 | `note_question` | `{text}` | 把孩子的疑问发到信号站。 |
| 模块 → 平台 | `complete` | `{score, total}` 或 `{}` | 模块结束。`score`、`total` 只用于诊断，宿主不把它们记进事件：分数一律由平台从作答事件算出（`docs/specs/events.md` 第 3.1 节）。 |
| 模块 → 平台 | `resize` | `{h}` | 内容高度变化时发送，平台据此调整 iframe 高度。 |
| 模块 → 平台 | `ai_request` | `{capability, input}` | **计划中**：申请调用 AI 能力，必须先在 manifest 的 `capabilities` 里声明 `ai:<能力名>`。 |

## 「预测 → 观察 → 解释」由谁做

`pedagogy: POE` 的实验，三步之中只有「观察」由模块实现。

1. **预测**：平台根据 manifest 的 `predict` 出题，这时模块处于锁定状态。
2. **观察**：平台发送 `phase: observe`，模块解锁。孩子操作，模块持续发送 `state`；孩子点「观察完了」，模块发送 `event: observed`。
3. **解释**：平台对比预测和观察结果，展示 `explain` 里的解释，并收集一句反思。

## 最小实现

```html
<script>
const Host = (() => {
  const h = {};
  addEventListener("message", e => { const m = e.data; if (m && m.contract === "activity/1.1" && h[m.type]) h[m.type](m.payload || {}); });
  const send = (type, payload) => parent.postMessage({ contract: "activity/1.1", type, payload: payload || {} }, "*");
  if (window.ResizeObserver) new ResizeObserver(() => send("resize", { h: document.documentElement.scrollHeight })).observe(document.body);
  return {
    on: (k, f) => { h[k] = f },
    ready: () => send("ready"),
    event: (verb, result) => send("event", { verb, result }),
    state: o => send("state", o),
    requestHint: () => send("request_hint"),
    noteQuestion: text => send("note_question", { text }),
    complete: r => send("complete", r)
  };
})();

Host.on("init", p => { /* 应用 p.palette，按 p.age_band 选读数措辞 */ });
Host.on("phase", p => { if (p.phase === "observe") { /* 解锁操作 */ } });
Host.ready();
</script>
```

完整样例：`prototype/index.html` 里的 `MODULES.pinholeModule`（小孔成像实验）和 `MODULES.quizModule`（分数挑战）。
````


## manifest 格式（原样贴入）

> 出处：`schemas/activity.schema.json`（提交 `6af4bcb`）

````text
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/deepnorth2077/curio/schemas/activity.schema.json",
  "title": "activity/1.1 · 互动模块 manifest",
  "description": "讲解、实验、测验等互动模块的描述文件。消息协议见 docs/activity-contract.md。",
  "type": "object",
  "required": ["id", "contract", "type", "version", "title", "targets", "age_band", "entry", "pedagogy", "emits", "review"],
  "additionalProperties": false,
  "properties": {
    "id": { "type": "string", "pattern": "^act\\.[a-z]+\\.[a-z0-9-]+$" },
    "contract": { "const": "activity/1.1" },
    "type": { "enum": ["experiment", "simulation"] },
    "version": { "type": "integer", "minimum": 1 },
    "title": { "type": "string", "maxLength": 20 },
    "targets": { "type": "array", "minItems": 1, "items": { "type": "string", "pattern": "^[a-z]+(\\.[a-z0-9-]+)+$" } },
    "age_band": { "type": "string", "pattern": "^G\\d{1,2}(-\\d{1,2})?$" },
    "entry": { "const": "index.html" },
    "capabilities": { "type": "array", "uniqueItems": true, "items": { "type": "string", "pattern": "^(pointer|keyboard|audio|ai:[a-z]+\\.[a-z_]+)$" } },
    "duration_min": { "type": "integer", "minimum": 1, "maximum": 30 },
    "pedagogy": { "enum": ["POE", "hint-ladder", "explain"], "description": "POE：预测 → 观察 → 解释，由平台负责前后两步" },
    "controls": { "type": "array", "items": { "type": "object", "required": ["key", "label"], "properties": { "key": { "type": "string" }, "label": { "type": "string" }, "values": { "type": "array", "items": { "type": "string" } } } }, "description": "孩子可调的量" },
    "observables": { "type": "array", "items": { "type": "object", "required": ["key", "label"], "properties": { "key": { "type": "string" }, "label": { "type": "string" } } }, "description": "可观测量，模块用 state 消息上报" },
    "predict": { "type": "object", "required": ["prompt", "options", "correct"], "additionalProperties": false, "properties": { "prompt": { "type": "string" }, "options": { "type": "array", "minItems": 2, "maxItems": 5, "items": { "type": "string" } }, "correct": { "type": "integer", "minimum": 0 } } },
    "explain": { "type": "string", "description": "解释一步里给孩子看的话，按 age_band 的措辞写" },
    "misconceptions": { "type": "array", "uniqueItems": true, "items": { "type": "string", "pattern": "^[a-z0-9-]+$" }, "description": "这个活动针对的误区 id，必须出自目标知识点的 misconceptions。知识点发布前，它的每个误区都要被至少一个活动针对。这是过渡做法：结构化题目落地后（ADR-002、CURIO-002），覆盖关系改为从题目和选项数据计算" },
    "params": { "type": "object", "description": "平台传入的可配置参数，各字段用 JSON Schema 描述" },
    "emits": { "type": "array", "minItems": 1, "uniqueItems": true, "items": { "type": "string", "pattern": "^[a-z_]+$" } },
    "author": { "type": "object", "properties": { "model": { "type": "string" }, "prompt_ref": { "type": "string" } } },
    "review": { "enum": ["pending", "claude-reviewed", "approved"] }
  },
  "allOf": [ { "if": { "properties": { "pedagogy": { "const": "POE" } } }, "then": { "required": ["controls", "observables", "predict", "explain"] } } ]
}
````


manifest 照下面写，`author.model` 换成你自己的模型名和版本：

```yaml
id: act.simulation.chocolate-split-01
contract: activity/1.1
type: simulation
version: 1
title: 掰巧克力
targets: [math.operation.distributive-law]
age_band: G3-4
entry: index.html
duration_min: 8
pedagogy: explain
capabilities: [pointer, keyboard]
misconceptions: [multiply-one-part, add-instead-of-multiply, merge-unlike, drop-small-part]
emits: [predicted, observed]
author: {model: <你的模型名和版本>, prompt_ref: prompts/act.simulation.chocolate-split-01.md}
review: pending
# END OF FILE
```

## 交付格式（必须遵守，格式不对整包打回）

文件清单（只交这两个文件，路径一字不差）：
- `content/activities/act.simulation.chocolate-split-01/manifest.yaml`
- `content/activities/act.simulation.chocolate-split-01/index.html`

开头信息照抄：`issue: #55`、`任务: act.simulation.chocolate-split-01`、`提示词版本: v1`、`基于提交: 6af4bcb998d91d4d5cf99b240c62f0bbead9c93e`、`轮次: 1`；`实现者` 写你自己的模型名和版本。`index.html` 很长时，可以分成两段交付（manifest 在第 1 段，index.html 在第 2 段），或者按第 6 条做成附件；一个文件不能拆到两段里。

> 出处：`docs/submission.md · 「格式」一节`（提交 `6af4bcb`）

``````text
## 格式

一段交付包长这样（`````里面的就是要输出的内容）：

`````
=== CURIO 交付包 · 第 1/2 段 ===
issue: #12
任务: act.quiz.fraction-intro-01
实现者: <模型名和版本，例如 GPT-5.1、Gemini 3 Pro>
提示词版本: v1
基于提交: <提示词开头写的提交号>
轮次: 1

## 文件清单
- content/activities/act.quiz.fraction-intro-01/manifest.yaml
- content/activities/act.quiz.fraction-intro-01/index.html

## 文件

### FILE: content/activities/act.quiz.fraction-intro-01/manifest.yaml
```yaml
id: act.quiz.fraction-intro-01
…
# END OF FILE
```

=== 第 1/2 段完 ===
`````

最后一段：

`````
=== CURIO 交付包 · 第 2/2 段 ===

### FILE: content/activities/act.quiz.fraction-intro-01/index.html
```html
<!doctype html>
…
</html>
<!-- END OF FILE -->
```

## 自查
- [x] 提示词里「验收标准」的每一条
- [x] …

## 说明
- 做了哪些决定，为什么：
- 没做什么：
- 疑问（规格不清楚、互相矛盾，或者觉得不合理的地方）：

=== END ===
=== 第 2/2 段完 ===
`````

一个回答放得下时，就只有一段：写成「第 1/1 段」，开头信息、清单、文件、自查、说明、`=== END ===` 都在这一段里。
``````


> 出处：`docs/submission.md · 「规则」一节`（提交 `6af4bcb`）

````text
## 规则

1. **分段**：每段以 `=== CURIO 交付包 · 第 k/n 段 ===` 开头，以 `=== 第 k/n 段完 ===` 结尾，n 是总段数，每段都写同一个 n。
   - 开头信息和「文件清单」只写在第 1 段。开头信息六项**全部必填**，格式如下，照抄任务文件里给的值：
     - `issue: #12`
     - `任务: act.quiz.fraction-intro-01`
     - `实现者: <模型名和版本>`
     - `提示词版本: v1`
     - `基于提交: <任务文件开头写的提交号>`
     - `轮次: 1`（正整数，打回一次加一）
   - 「自查」「说明」和 `=== END ===` 只写在最后一段。
2. **一个文件不能拆到两段里。**单个文件长到一个回答放不下时，把它改为附件交付（见第 6 条），清单里照常列出。
3. **文件路径**：每个文件用 `### FILE: <路径>` 开头。路径必须和「文件清单」完全一致，也必须是提示词里指定的路径。
4. **结束标记**：每个文件的最后一行写结束标记，按文件类型选择对应的注释写法：
   - YAML、Python：`# END OF FILE`
   - HTML、Markdown、SVG：`<!-- END OF FILE -->`
   - JavaScript、CSS：`/* END OF FILE */`
   - JSON 不能写注释，所以不加结束标记；收货时会检查它能不能完整解析。
5. **交付完整文件**：每次都给出完整文件，不要只给改动的片段，也不要写「其余部分不变」。
6. **附件**：文件太长、需要做成附件时，附件的文件名必须是**完整路径**，把其中的 `/` 换成 `__`。例如 `content/activities/act.x/index.html` 的附件名是 `content__activities__act.x__index.html`。只写 `index.html` 会被打回，因为几个活动的同名文件会对不上号。
7. **疑问写在「说明」里**：不要为了让自己的实现能跑通，就去改规格、字段或消息格式。
8. **打回之后**：交付完整的新一轮交付包，「轮次」加一，并在「说明」里逐条写出改了什么。
````

---

## 附：本任务文件嵌入的仓库文件

| 文件 | 范围 | SHA-256（整个文件） |
| --- | --- | --- |
| `content/nodes/num/math.operation.distributive-law.yaml` | 全文 | `d0afd9c887b22a002fcae1d1108431274618dc8347eb2adbb6992a0e1f67a80f` |
| `.claude/skills/curio-anatomy/references/lessons.md` | 实现 | `591fa79fe30901c2c6c8e39e4b2cfaaabc507411d5dfd58a96fb1fee2ebc063c` |
| `.claude/skills/curio-anatomy/references/starter.html` | 全文 | `805203fc29f714b30a52bac091a907b64ea774313022d5e06e86991618891ce7` |
| `docs/constellations/multiplication.md` | 星座概况 | `f31aa4993912924dc399a0b0123d113e3ef4d421d5e4b957597b24dcc4396ead` |
| `docs/constellations/multiplication.md` | 领航员怎么说话 | `f31aa4993912924dc399a0b0123d113e3ef4d421d5e4b957597b24dcc4396ead` |
| `docs/constellations/multiplication.md` | 词表 | `f31aa4993912924dc399a0b0123d113e3ef4d421d5e4b957597b24dcc4396ead` |
| `docs/constellations/multiplication.md` | 画风 | `f31aa4993912924dc399a0b0123d113e3ef4d421d5e4b957597b24dcc4396ead` |
| `docs/constellations/multiplication.md` | 事实和出处 | `f31aa4993912924dc399a0b0123d113e3ef4d421d5e4b957597b24dcc4396ead` |
| `.claude/skills/curio-anatomy/SKILL.md` | Claude 画风 | `0238b3af92c5e30bdf7fab12180dac5e1b1f64b8d28daebe0c432818b9d63ebb` |
| `.claude/skills/curio-anatomy/SKILL.md` | 适龄 | `0238b3af92c5e30bdf7fab12180dac5e1b1f64b8d28daebe0c432818b9d63ebb` |
| `.claude/skills/curio-anatomy/SKILL.md` | 检查 | `0238b3af92c5e30bdf7fab12180dac5e1b1f64b8d28daebe0c432818b9d63ebb` |
| `docs/standards.md` | 给孩子看的内容 | `e25474d70e2398c923ee74de4b7b5370268ccc45ef04976e83dd47d08342d0e9` |
| `GLOSSARY.md` | 给孩子看的世界 | `2fedad9b6d645a067d3d7a7adf3d94dfcf63a9245f38e0e148a945deae2ce413` |
| `GLOSSARY.md` | 内容 | `2fedad9b6d645a067d3d7a7adf3d94dfcf63a9245f38e0e148a945deae2ce413` |
| `GLOSSARY.md` | 协作 | `2fedad9b6d645a067d3d7a7adf3d94dfcf63a9245f38e0e148a945deae2ce413` |
| `docs/activity-contract.md` | 全文 | `42503500dac2392d9423c6825c64e99e21f0ce6b27746bfcfe7cf270f60334d8` |
| `schemas/activity.schema.json` | 全文 | `8a0901a0ce8b2a3df689500a1596f92f87b4a8eeb84ce3591ed18fdfcce613ad` |
| `docs/submission.md` | 格式 | `ea8f185947df7a9b176193b27dd2c5c334c04351acf5cacf91087a9171ba31bf` |
| `docs/submission.md` | 规则 | `ea8f185947df7a9b176193b27dd2c5c334c04351acf5cacf91087a9171ba31bf` |
