# 规格：选领航员 · 第一版（主线第 4 步，#242）

- 状态：提议，第 2 稿。取代 #112 的提议稿（第 1 稿和它的审查 `pr-112.md` 留在那个 PR 里作参考），只保留第一版要做的部分。
- 依据：`docs/handoff.md` 第 4 节主线第 4 步；Luka 2026-11-11 对 #112 的四个回答、2026-11-22 对本稿三个问题的回答（见文末）；内容规格 `docs/specs/content.md`（发布包、3.6 SVG 白名单）；事件规格 `docs/specs/events.md`；舰长资料规格 `docs/specs/profile.md`（同一种「家长或孩子的设置走事件」做法）；活动契约 `docs/activity-contract.md`
- 审查：`docs/reviews/pr-<号>.md`

## 问题

每一屏陪着舰长的领航员只有一个样子，不是他选的。动手探索里那张脸也是写死在模块里的。#105 的设计稿画了两位原创领航员「小灯」「小环」，Luka 定了两位都留下、让舰长自己挑。

## 方案

- 发布包里多一种内容「领航员」，第一版有两位：小灯、小环。以后加一位只加一个内容目录。
- 舰长挑一位陪他，选择作为一条事件写进事件流，所以备份、恢复自动带走。
- 星图上有这位领航员的头像，点头像进「领航员舱」，随时换。
- 外壳里领航员说话的地方、以及用新骨架做的 20 个动手探索（「0 和 1 之间」19 颗和掰巧克力）里，出现的都是选的那一位，表情跟着场合变。生命座三颗老模块这一版还是自带的那张脸。
- 「点亮星座认识新的一位」这一版不做（第三位还没有设计稿），但内容格式和读程序现在就为它留好位置。

## 用户故事

1. 作为舰长，我第一次要进活动时，先自己挑一位领航员，这样它是我选的伙伴。
2. 作为舰长，我随时能在星图上点它的头像，换成另一位。
3. 作为舰长，进了动手探索，旁边说话的还是我选的那位，答对时它鼓掌，答错时它在想。
4. 作为家长，换设备用备份恢复以后，孩子选的领航员还在。
5. 作为家长，在一台新设备上，挑领航员不会挡住我从备份恢复。
6. 作为维护者，加一位新的领航员只是加一份内容，不改代码；每一位都是原创的。

## 实现上的决定

### 1. 领航员是内容（`navigator/1`）

```
content/navigators/nav.<短名>/
  navigator.yaml
  curious.svg  waiting.svg  surprised.svg  clap.svg  think.svg  wrong.svg
```

```yaml
schema: navigator/1
id: nav.lamp                 # 永不复用、永不改动；目录名必须等于 id
version: 1
title: 小灯                   # 最多 6 个字
intro: 我头顶有一盏小灯，想到什么它就亮。   # 见面时说的一句话，最多 40 个字
unlock: {start: true}        # 第一版只有这一种；以后加 {lit: [知识点 id…]}
review: approved             # pending | claude-reviewed | approved
author: {model: <实际模型>, prompt_ref: <设计说明的路径>}
```

- 第一版两位：`nav.lamp`（小灯）、`nav.ring`（小环），都是 `unlock: {start: true}`。画法照 `prototype/design/navigator.html`（#105，Luka 已看过）。
- **`unlock` 的读法现在就定好**：读程序认得 `start: true` 和 `lit`（1～12 个已发布知识点 id，每颗都有一次首答正确率不低于 0.8 的挑战才算认识；Luka 2026-11-11 回答 1）。第一版的外壳只用 `start`；遇到 `lit` 的领航员先当作「还没认识」，不显示。以后做「认识新的一位」时只改外壳，不改格式。
- 已进 `main` 的领航员，`id`、`unlock` 永远不能改，目录不能删；要换条件就出一位新的。改画法、名字、见面的话是普通改版（`version` 加一）。
- **每个 SVG**（`ci_checks.py` 单独严格检查）：`viewBox="0 0 48 48"`；只用内容规格 3.6 白名单里的元素和属性；不许 `id`、`use`、`defs`、渐变、`clipPath`、`text`、位图；能画出东西的元素（`path`、`circle`、`ellipse`、`rect`、`line`、`polyline`、`polygon`）不超过 14 个；颜色只用 `class`，只许 `k`、`k1`、`f-ink`、`f-pane`、`f-sky`、`f-sage`、`f-apricot`、`f-paper`、`f-accent` 九个，不写在 `g` 上；`fill`、`stroke` 属性只许 `none`；`f-accent` 每张最多一个元素；每张不超过 2 KiB。九个类的颜色由外壳和模块骨架的样式给，浅色深色共用一套线稿。
- 发布包只收 `review: approved` 的领航员，并且至少要有一位 `start: true`。

### 2. 进发布包

`release/1` 增加一个**可选**的顶层键 `navigators`，写法和 `activities` 一样（每位一项：`id`、`version`、`files`，每个文件 `path`、`bytes`、`sha256`，`navigator.yaml` 带 `.yaml.json`）。

- 有领航员时才出现、才进 `content_hash`；没有时不写，旧发布包的哈希和校验不变。
- `engine_min` 不升：旧外壳的 `verifyManifest` 遇到不认识的顶层键会怎样，实现时先核对；如果旧外壳会报错，就升到 2 并在 PR 里写明（旧页面会显示「需要更新」，刷新即可）。
- 外壳读包时照样逐个核对字节数和 SHA-256，SVG 在核对过之后才用。

### 3. 选了谁：新动词 `navigator.chosen`

加进事件规格第 3.5 节：

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `navigator.chosen` | 无 | learner | `{rev, navigator_id}` |

- `rev`：正整数，保存时取当前生效的 `rev` 加 1，第一次是 1（和 `profile.set` 同样的理由：设备时钟走错也不会让旧选择盖过新选择）。
- `navigator_id`：`nav.<小写字母、数字、连字符>`。**不校验它在不在发布包里**：事件比发布包活得久，删了的领航员按下面的退回规则处理。
- 投影 `projectNavigator(events)`（`kernel/js/navigator.js`，纯函数）：照 profile/1 的规则——集合里有 `import.voided` 时去掉作废批次；`rev` 最大的生效，同 `rev` 时排序键 `(occurred_at, device_id, device_seq, event_id)` 最大的生效，落选的进 `conflicts`（`{event_id, reason: "same_rev"}`，按 `event_id` 升序）；输出 `{algorithm_version: "navigator/1", navigator_id 或 null, rev, conflicts}`。写进事件规格第 6.4 节。
- 改事件格式，照 profile 的做法**先读后写**：PR 1 只教读程序（schema、`validate.js`、`backup_ref.py`）认得它，PR 2 才让界面写它。旧版 Curio 恢复带它的备份，记为「这一版不认识」，其余记录照常。

### 4. 显示的是谁

`shownNavigator(chosenId, navigators)`（纯函数，放在 `app/` 里）：

- 「已认识」= 发布包里 `unlock.start` 为真的领航员，按 `id` 码点排序。
- `chosenId` 在「已认识」里就用它；否则（还没选、选的那位已从发布包里拿掉、或它是 `lit` 的）用「已认识」里排第一的那位。退回时**不写**新事件。
- 发布包里一位领航员都没有（旧发布包）时返回 `null`，外壳和模块用自带的那张脸。

### 5. 舰长看到的

**挑选。** 还没有生效的选择时：

- 设备**不干净**（已经有记录）：打开外壳先出挑选页，两位并排，各说自己的 `intro`；下面一行「舰长，选一位陪你出发吧。以后随时可以换。」点一位，它换成鼓掌的表情，按钮写「出发」；点「出发」写一条 `navigator.chosen`，进星图。
- 设备**干净**（还没有任何记录）：不先出挑选页，星图上先显示退回的那位。舰长第一次点任务的「开始」时，先出挑选页，挑完再进活动。原因和舰长资料一样：恢复只肯写进干净的设备，打开就逼着写一条事件，会挡住从备份恢复。
- 只读状态（失去写锁）下不出挑选页，用退回的那位。

**领航员舱。** 星图页左上（标题旁）是现在这位的头像，点它弹出一张卡：两位并排，名字、好奇的表情和 `intro`；现在陪着的那位标「陪着你」；点另一位就写一条 `navigator.chosen`（`rev` 加 1），卡上记号跟着换。入口是头像，不占导航（AGENTS.md：只有一套导航）。

**外壳里说话的地方。** 挑战里的提示和反馈旁边的头像用选的那位：出题时 `waiting`，答对 `clap`，答错 `think`，揭晓答案 `surprised`，其余 `curious`。

### 6. 动手探索里也是它

- 宿主在 `init` 里多发一个可选字段 `navigator: {id, faces: {curious, waiting, surprised, clap, think, wrong}}`，每个值是那张 SVG 去掉最外层 `<svg>` 以后的内容，来自核对过哈希的发布包。写进活动契约 `docs/activity-contract.md` 的 `init` 可选字段。缺了不算契约警告。
- 模块骨架 `references/starter.html` 的 `kit:host` 收到它时，把 `.ava` 的内容换成 `curious`；`kit:shell` 的 `say(html, tone)` 按 `tone` 换表情：没有 `tone` 是 `curious`，`good` 是 `clap`，`bad` 是 `think`；等孩子回答时（`ask`）是 `waiting`。没收到 `navigator`（单独打开、试玩页、旧宿主）时保留骨架自带的那张脸，行为和现在一样。
- 骨架里九个颜色类的样式加进 `kit:base`。
- 20 个新骨架模块照抄更新后的 `kit:` 段落（`ci_checks.py` 已经在查这些段落和骨架一致）。生命座三颗不改，宿主照样发 `navigator`，它们忽略。

### 7. 原创和说话方式（沿用 Luka 2026-11-11 的决定）

- 每一位都是原创的，不以任何现成角色为原型。以后的第三位从孩子自己的画或他说的性格出发重画；孩子的画和原话不进仓库。
- 所有领航员说话方式一样，模块台词和 AI 中转的领航员说明不按领航员分。每位自己的话只有一句 `intro`。

## 测试接缝

| 接缝 | 能发现 | 发现不了 |
| --- | --- | --- |
| 摄入向量 `kernel/vectors/navigator-*.json`（JS 和 Python 两边） | `navigator.chosen` 的合法与不合法写法：缺字段、多字段、`rev` 不是正整数、`navigator_id` 格式不对、actor 不是 learner、带了 `attempt_id` 或 `content` | 界面有没有写 |
| `projectNavigator` 单元测试 | `rev` 优先于时钟；同 `rev` 按排序键；乱序结果相同；作废批次；空输入为 null | — |
| `shownNavigator` 单元测试 | 下面的用例 1～5 | 画面 |
| `ci_checks.py` 对 `content/navigators/` 的检查（正反测试） | 下面的反例 | 好不好看、是不是原创 |
| `build_release.py` 和外壳读包（黄金样例：有、没有领航员各一份） | 键缺了或多了、哈希不对、没有 `start` 的领航员、没批准的被收录 | — |
| 宿主发出的 `init`、骨架收到后的 `.ava` | 没带 `navigator`；带的不是选的那位；骨架没换脸或换错表情 | 生命座老模块 |
| 备份往返测试加一例 | 带 `navigator.chosen` 的备份恢复后投影出同一位 | — |
| Luka 的演示步骤 | 整条路走不通 | — |

选择的用例（期望值手算；`nav.lamp`、`nav.ring` 都是 `start`）：

| # | 生效的 `navigator_id` | 发布包里的领航员 | 显示 |
| --- | --- | --- | --- |
| 1 | 没有 | lamp、ring | `nav.lamp`（退回，不写事件） |
| 2 | `nav.ring` | lamp、ring | `nav.ring` |
| 3 | `nav.gone` | lamp、ring | `nav.lamp` |
| 4 | `nav.x`（发布包里有，但它是 `lit`） | lamp、ring、x | `nav.lamp` |
| 5 | `nav.ring` | 没有领航员（旧发布包） | `null`（用自带的脸） |

内容检查的反例（每条都应不通过）：缺 `wrong.svg`；`viewBox` 是 `0 0 100 100`；用了 `<text>`；用了类 `f-red`；类写在 `g` 上；`fill="#000"`；15 个能画出东西的元素；两个元素用了 `f-accent`；带 `id` 属性；超过 2 KiB；目录名和 `id` 不同；把已进 `main` 的 `unlock` 改掉；删掉已进 `main` 的领航员；整个目录里没有 `start: true` 的；`lit` 里有未发布的知识点。

## 不做什么

- 不做「点亮星座认识新的一位」、影子、认识卡片（等第三位的设计稿）。
- 不改生命座三颗老模块；不做零件库第 2 版（#108）。
- 不给领航员改名字（那是孩子写的自由文字）；不做动画；不按领航员写不同台词。
- 不改设备存储版本和备份格式。

## 怎么分步

| PR | 内容 | 审查 |
| --- | --- | --- |
| 1 · 读 | `navigator.schema.json`、`release.schema.json` 加可选键、`build_release.py`、`ci_checks.py` 的领航员检查和测试；事件 schema 加 `navigator.chosen`，`validate.js`、`backup_ref.py`；`kernel/js/navigator.js`；外壳读包认得 `navigators`（只核对，不显示）；事件规格 3.5、6.4 和内容规格同步。向量和测试另一个子 agent 先写（先红）。 | 独立审（存下来的格式） |
| 2 · 写 | `content/navigators/` 两位（从设计稿生成六个表情的 SVG）；外壳的挑选页、头像、领航员舱、挑战里的头像；宿主 `init.navigator`；骨架和 20 个模块的 `kit:` 段落；活动契约文档。 | Claude 看差异和截图，Luka 和舰长看 |

## 演示步骤（Luka 在 iPad 上）

1. 打开正式外壳（已经有记录的这台 iPad）。先出挑选页：小灯和小环并排，各说一句话。
2. 点「小环」，它鼓掌；点「出发」，进星图。星图标题旁是小环的头像。
3. 点头像，弹出卡片，小环标着「陪着你」。点「小灯」，头像变成小灯。刷新，还是小灯。
4. 进「几分之一」的动手探索，旁边说话的是小灯；猜错时它在想，做完一站它鼓掌。
5. 做一次挑战：答对时头像鼓掌，答错时在想。
6. 做一份备份，在干净浏览器里恢复：头像还是小灯，不再出挑选页。

## Luka 拍板的结果

- 2026-11-11（#112）：认识新领航员的条件是指定几颗星各有一次首答正确率不低于 0.8 的挑战，认识了不会再失去；说话方式都一样；第三位从孩子自己的画重画；小灯、小环都留下，让舰长挑。
- 2026-11-22（本稿）：选择存进记录流；第一版只做挑选和更换，「认识新的一位」以后再做；新骨架的 20 个动手探索跟着换，生命座三颗暂不换。
