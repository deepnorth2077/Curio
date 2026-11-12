# 规格：竖切片 5a · 「生命的说明书」进正式外壳（CURIO-011）

- 状态：提议
- 依据：ADR-001（内核与外壳）、ADR-003（发布不可变）、ADR-004（事件是事实来源）、ADR-005（活动宿主）、ADR-006（可恢复性）、ADR-008（不打包）；事件规格第 2、3.1、3.7、5、6.3、6.4、8 节；内容规格 3.8、6；`docs/activity-contract.md`；竖切片 1 规格（`docs/specs/slice-1.md`）
- 实现任务：规格接受后另开，分两步（见「怎么分步」）

## 问题

- 作为舰长：「生命的说明书」的三个动手探索和三个挑战现在只能在原型和试玩页里玩。玩完什么都没留下，星星不会变。
- 作为家长：正式外壳（`app/`）里只有一颗分数的夹具星，看不到孩子真正在玩的东西。
- 作为维护者：正式外壳里还没有活动宿主。ADR-005 定了边界，事件规格 3.7 定了「模块消息怎么变成事件」，但现有的四个模块发的消息和 3.7 要的 payload 对不上（见「实现上的决定」第 3 节），没有任何地方写明怎么换。

## 方案

正式外壳读真实内容的发布包。星图上有「生命的说明书」的三颗星：细胞、DNA、染色体。点一颗星，能进它的动手探索，也能进它的挑战。

- 动手探索跑在沙箱里。做到星卡，这颗星从「没碰过」变成「探索过」。
- 挑战用竖切片 1 已有的引擎。首答正确率不低于 0.8，这颗星点亮。
- 中途离开再回来，记录还在；刷新以后星星的样子不变。

## 用户故事

1. 作为舰长，我想要在星图上看到细胞、DNA、染色体三颗星，这样我知道能去哪。
2. 作为舰长，我想要做完动手探索以后星星变个样子，这样我知道自己来过。
3. 作为舰长，我想要做完挑战以后星星亮起来，这样我有东西可以给爸爸妈妈看。
4. 作为舰长，我想要模块卡住的时候有一句看得懂的话和一个「重新开始」，这样我不用找大人。
5. 作为家长，我想要知道这些记录现在存在哪、有没有备份，这样我不会以为它们已经保住了。
6. 作为维护者，我想要宿主是一个不碰 DOM 的状态机，这样「哪些消息被接收、换成什么事件」能在 Node 里用手算的用例测。
7. 作为维护者，我想要已发布的四个 activity/1.1 模块一个字节不改就能被记录，这样不用为了接进来而改版。

## 实现上的决定

### 1. 发布包和星图

- 演示部署改成从真实的 `content/` 构建发布包（现在是从 `tools/tests/fixtures/slice-1b/content`）。构建器照旧只收录 `status: published` 的知识点和 `review: approved` 的活动。
- 分数那颗夹具星不再出现在星图上。设备上已有的分数记录留在事件里，不删。
- 星图画发布包里的每个知识点，三种状态：没碰过、探索过、已点亮（`kernel/js/mastery.js` 已经算出这三种）。
- 点一颗星，列出它被收录的、本切片能运行的活动：`simulation`（按钮上写「动手探索」）和 `quiz`（「挑战」）。`explain`、`reflection` 这一版不列出，它们属于竖切片 2（#25）。
- 发布清单的 `contracts` 里有宿主不认识的契约版本时，不切换到这个发布，显示「需要更新」（内容规格 3.8）。本切片的宿主只认 `activity/1.1`。

### 2. 宿主（照 ADR-005，本切片写定数值）

宿主分两层：

- `engine/js/host.js`：纯状态机。输入是「收到一条消息」「时间到了」「舰长离开了」，输出是「要写的事件」「要发给模块的消息」「契约警告」「界面该显示什么」。不碰 DOM、存储、时间和随机数。
- `app/` 里的薄适配层：建 iframe、收发 `postMessage`、把时间和事件 ID 传进状态机、把输出交给竖切片 1 的 `committer`。

装载：

- 从发布包取 `index.html`，核对字节数和 SHA-256 以后才用（和读 YAML 同一套核对）。
- 在 `<head>` 的最前面插入一个 `<meta http-equiv="Content-Security-Policy">`，内容是 `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:`。
- 用 `srcdoc` 装进 `sandbox="allow-scripts"` 的 iframe，不给 `allow-same-origin`。
- 每一次运行新建一个 iframe，用完就移除。

运行状态：

| 状态 | 进入的条件 | 接收哪些模块消息 |
| --- | --- | --- |
| 加载 | iframe 建好 | 只有 `ready` |
| 运行 | 收到 `ready`；宿主回 `init`，记 `attempt.started` | `event`、`state`、`note_question`、`resize`、`complete` |
| 完成 | 收到 `complete`；记 `attempt.completed` | 只有 `resize` |
| 中止 | 超时、舰长离开、模块出错；记 `attempt.abandoned` | 无 |

一条消息要同时满足下面几条才被接收。第 1 条不满足的直接忽略，不记警告（那不是这个模块发的）；其余任何一条不满足，丢掉并记一条契约警告：

1. `event.source` 是本次运行的 iframe 的窗口；
2. 是一个对象，`contract` 是 `"activity/1.1"`，`type` 是字符串；
3. 当前状态接收这种 `type`（上表）；
4. `type` 是 `event` 时，`verb` 在 manifest 的 `emits` 里；
5. payload 符合第 3 节的形状；
6. 没有超出下面的配额。

数值（写进 `docs/activity-contract.md`）：

| 项目 | 数值 | 超出时 |
| --- | --- | --- |
| 单条消息 | 按 `JSON.stringify` 以后的 UTF-8 字节数，不超过 16 KiB | 丢掉，警告 |
| 消息频率 | 每秒不超过 60 条 | 这一秒里超出的丢掉，只记一条警告 |
| 每次运行写的事件 | 不超过 200 条（不含 `attempt.started` 和结束事件） | 之后的 `event` 丢掉，只记一条警告 |
| 每次运行的契约警告 | 记前 20 条，之后只记一条汇总 | — |
| `resize` 的高度 | 100 到 6000 px 之间的整数，超出的夹到范围内；每秒最多应用 10 次 | 多的丢掉，不警告 |
| 等 `ready` | 10 秒 | 中止，`reason: timeout` |

说明两处和 ADR-005 字面不同的地方（请审阅者判断要不要写成增补）：

- ADR-005 第 4 条要求消息带 `run_id`。activity/1.1 的消息里没有这个字段，已发布的模块也不发。本切片用「一次运行一个 iframe，按窗口对象认」达到同样的效果。
- ADR-005 第 6 条提到心跳。activity/1.1 没有心跳消息，本切片不做。模块卡死时，舰长点宿主画在模块外面的「重新开始」。

舰长看到的：

- 模块上方有一条宿主画的窄栏：左边「回星图」，右边「重新开始」。它们在 iframe 外面，模块卡死也能点。
- 加载超过 1 秒，显示「正在准备……」。中止以后显示一句话和「重新开始」：超时是「它好像睡着了，我们重新叫醒它。」；模块出错是「这里出了点问题，再来一次吧。」
- 完成以后，窄栏里多一个「回星图看看」，星星的新样子在回到星图时出现。
- 模块里「再玩一次」可以照常玩，但完成以后的消息不再记录。

### 3. 模块消息怎么变成事件（细化事件规格 3.7）

已发布的四个模拟模块发的 `result` 是下面的形状，宿主照表换成事件。表里没有的字段一律算形状不符。

| 模块发的 | `result` 必须是 | 宿主记成 | payload |
| --- | --- | --- | --- |
| `event` · `predicted` | `{station, choice, correct, misconception}` | `poe.predicted` | `{choice: String(choice), step: String(station), correct, misconception?}` |
| `event` · `observed` | `{station}` | `sim.observed` | `{observable: "station", value: station}` |
| `event` · `answered` | `{station, choice, correct, misconception}` | `item.answered` | `{item_id: "station-" + station, response: String(choice), correct, try, hints_used: 0, misconception?}` |
| `state` | 任意对象 | 不记事件 | 宿主只在内存里留最后一条，离开就丢 |
| `note_question` | `{text}` | 这一版不记 | 见下 |
| `complete` | `{}` 或 `{score, total}` | `attempt.completed` | `{duration_ms}`，从 `attempt.started` 到这一刻 |

形状的细则：

- `station`：1 到 20 的整数。`choice`：0 到 9 的整数。`correct`：布尔值。
- `misconception`：`null`，或者 manifest 的 `misconceptions` 里列出的一个 id。是 `null` 时事件里不写这个字段。
- `try`：由宿主数。同一次运行里同一个 `item_id` 的第几条 `answered`，从 1 开始。
- `attempt.started` 的 `mode`：这个活动以前有过已完成的合法尝试是 `retry`，否则是 `first`（和竖切片 1 的挑战同一个算法）。
- `content` 的五个字段照事件规格第 2 节填，`activity_kind` 是 `simulation`。
- `attempt.abandoned` 的 `reason`：舰长点「回星图」或「重新开始」、关掉页面是 `left`；等 `ready` 超时是 `timeout`；iframe 报错是 `error`。恢复时补写的照竖切片 1 的 6.3。

**事件格式的一处改动（只增不改，事件规格第 8 节允许）**：`poe.predicted` 的 payload 增加三个可选字段：`step`（字符串，最多 32 个字符）、`correct`（布尔值）、`misconception`（字符串）。原因：模块里每个错误选项都对应一个误区 id，这是知识点卡设计好的诊断信息；现在的 `poe.predicted` 只有 `choice`，换过去就丢了。`schema` 仍然是 `event/2`。

**「我有个问题」这一版不记录。**记下来要用私人文字（事件规格第 4 节），那是竖切片 2（#25）的内容。本切片里，宿主收到 `note_question` 时不写任何东西，在窄栏下面显示一句：「这个问题我现在还带不走。先讲给爸爸妈妈听，好吗？」

### 4. 掌握度

不改算法。照 `mastery/1`：

- 完成一次动手探索（合法、已完成的 `simulation` 尝试）：`untouched` → `explored`。
- 完成一次挑战并且首答正确率不低于 0.8：`lit`。
- 动手探索里的 `item.answered` 不参与首答正确率（那只看 `quiz` 尝试）。

### 5. 这些记录算不算数（ADR-006）

ADR-006 第 1 条：真实孩子的数据进入系统之前，要先有导出、导入、备份、版本迁移、恢复。这五件事是竖切片 6（#8），还没做。

所以本切片里的记录是**试玩记录**：

- 存在这台设备的浏览器里，没有备份。清浏览器数据、长时间不打开，都可能丢。
- 星图页的底部一直显示一行小字：「试玩记录 · 只在这台设备上 · 还没有备份」。
- 事件本身是合格的 `event/2`。等竖切片 6 做完、恢复演练过了以后，由 Luka 决定这些试玩记录是留下来算数，还是清掉重新开始。

## 怎么分步

| 步 | 做完以后能看到什么 | 改到哪里 |
| --- | --- | --- |
| 5a-1 | 星图上有三颗真实的星；每颗星的挑战能做，做完星星变（挑战是已有的引擎，只换了内容） | 演示部署、`app/` 的星图和活动列表 |
| 5a-2 | 每颗星的动手探索能在沙箱里玩，做到星卡以后星星变成「探索过」；模块卡住能重新开始 | `engine/js/host.js` 和测试、`app/` 的适配层、`schemas/event.schema.json`、`kernel/js/validate.js`、契约文档 |

每一步先由一个子 agent 照本规格的验收用例写测试（放进受保护的路径），再由另一个子 agent 实现，第三个子 agent 审查。

## 测试接缝

| 接缝 | 能发现 | 发现不了 |
| --- | --- | --- |
| `host.js` 状态机：给一串输入，看输出的事件、警告、状态 | 换错事件、接收了不该接收的消息、配额和超时不对 | 真实浏览器里沙箱和 CSP 有没有生效 |
| 内核摄入加掌握度投影：把状态机输出的事件喂进去 | 写出不合格的事件；尝试不合法；星星状态不对 | — |
| 浏览器里的宿主页：装一个故意越界的测试模块 | 模块能联网、能读存储、能碰到父页面 | 模块画得对不对 |
| Luka 的演示步骤 | 整条路走不通 | — |

验收用例（期望值是手算的，实现时逐条写成测试）。下面 `M` 是染色体模块的 manifest：`emits: [predicted, observed, answered]`，`misconceptions` 里有 `cut-into-pieces`、`y-from-mother`。时间用毫秒数表示。

**用例 1：正常做完。**输入依次是：

1. t=0 建好 iframe
2. t=400 收到 `ready`
3. t=5000 `event` · `predicted` · `{station: 1, choice: 0, correct: false, misconception: "cut-into-pieces"}`
4. t=9000 `state` · `{station: 1, length_m: 0.3}`
5. t=30000 `event` · `observed` · `{station: 1}`
6. t=60000 `event` · `answered` · `{station: 4, choice: 1, correct: false, misconception: "y-from-mother"}`
7. t=70000 `event` · `answered` · `{station: 4, choice: 0, correct: true, misconception: null}`
8. t=90000 `complete` · `{}`

期望写出 6 条事件，顺序和 payload 是：

1. `attempt.started` · `{mode: "first"}`
2. `poe.predicted` · `{choice: "0", step: "1", correct: false, misconception: "cut-into-pieces"}`
3. `sim.observed` · `{observable: "station", value: 1}`
4. `item.answered` · `{item_id: "station-4", response: "1", correct: false, try: 1, hints_used: 0, misconception: "y-from-mother"}`
5. `item.answered` · `{item_id: "station-4", response: "0", correct: true, try: 2, hints_used: 0}`
6. `attempt.completed` · `{duration_ms: 89600}`

发给模块的消息只有一条 `init`（在第 2 步之后）。契约警告 0 条。最后的状态是「完成」。把这 6 条喂进内核：全部接收，这次尝试合法、已完成，知识点的状态是 `explored`。

**用例 2：该丢的都丢掉。**在用例 1 的基础上，分别插入下面的一条，期望都是「不写事件，记 1 条警告，其余不变」：

| 插入 | 位置 |
| --- | --- |
| `event` · `predicted`（形状正确） | 第 2 步之前（还没 `ready`） |
| `event` · `adjusted` · `{control: "x", value: 1}`（`adjusted` 不在 `emits` 里） | 第 3 步之后 |
| `event` · `predicted` · `{station: 1, choice: 0, correct: false, misconception: "not-in-manifest"}` | 第 3 步之后 |
| `event` · `predicted` · `{station: 1, choice: 0, correct: false, misconception: null, extra: 1}` | 第 3 步之后 |
| `event` · `observed` · `{station: 0}` | 第 3 步之后 |
| `contract` 是 `"activity/1.0"` 的任何消息 | 第 3 步之后 |
| 第二条 `complete` | 第 8 步之后 |
| `event` · `observed` · `{station: 2}` | 第 8 步之后 |

另外：`event.source` 不是本次运行的 iframe 的消息，直接忽略，不记警告（那不是这个模块发的）。

**用例 3：超时。**t=0 建好 iframe，一直没有 `ready`。t=10000 时：状态是「中止」，写出 0 条事件（还没有 `attempt.started`，所以也没有 `attempt.abandoned`），界面显示超时的那句话和「重新开始」。

**用例 4：中途离开。**用例 1 做到第 5 步，t=40000 舰长点「回星图」。期望写出 4 条：`attempt.started`、`poe.predicted`、`sim.observed`、`attempt.abandoned` · `{reason: "left"}`。喂进内核：尝试合法、未完成，知识点的状态是 `untouched`。

**用例 5：第二次做。**设备上已有用例 1 的 6 条事件，再做一次。`attempt.started` 的 `mode` 是 `retry`。

**用例 6：频率。**运行状态下，同一秒里收到 100 条形状正确的 `state`。期望：接收前 60 条，丢掉 40 条，记 1 条警告，写出 0 条事件。

**用例 7：事件上限。**一次运行里收到 250 条形状正确的 `observed`。期望写出 200 条 `sim.observed`，记 1 条警告；之后的 `complete` 照常接收，写出 `attempt.completed`。

**用例 8：越界的测试模块（在浏览器里跑）。**模块依次尝试：`fetch` 一个地址、加载一张外部图片、读 `localStorage`、读 `parent.document`。期望：四样全部失败；宿主页没有发出任何网络请求；宿主页的存储没有变化。

**用例 9：已发布的模块。**`act.simulation.cell-zoom-01`、`dna-book-01`、`chromosome-pack-01` 一个字节不改，各用键盘从头走到星卡。期望：契约警告 0 条；每个模块最后都有 `attempt.completed`；对应的知识点是 `explored`。

## 演示步骤（Luka 亲手验收，iPad）

1. 打开演示页。星图上有三颗星：细胞、DNA、染色体，都是没碰过的样子。页面底部有一行「试玩记录 · 只在这台设备上 · 还没有备份」。
2. 点「细胞」，看到「动手探索」和「挑战」两个按钮。
3. 进「动手探索」，玩到星卡。点「回星图看看」，细胞这颗星变成探索过的样子。
4. 刷新页面，它还是探索过的样子。
5. 进「挑战」，全部答对。回到星图，细胞这颗星亮了。
6. 点「DNA」的「动手探索」，玩到一半点「回星图」。DNA 这颗星还是没碰过的样子。
7. 再进一次，点「重新开始」，模块回到开头。
8. 在模块里点「我有个问题」，写一句话发出去，看到「这个问题我现在还带不走。先讲给爸爸妈妈听，好吗？」

## 不做什么

- 讲解和反思（竖切片 2，#25）；私人文字；「我有个问题」的记录和 AI 回答（#86）。
- 「预测 → 观察 → 解释」由平台负责的那一套，以及小孔成像（竖切片 5，#28）。本切片的宿主是它的地基。
- 导出、导入、备份、恢复（竖切片 6，#8）；多设备同步（#11）。
- 新的星图画法（#105 的设计稿选定以后另开任务）。本切片的星图沿用竖切片 1 的画法，只是星多了。
- activity/1.2、颜色下发的新规则和零件库（#107）。本切片的宿主发的 `init` 照 1.1；#107 接受以后再改。
- 知识地铁、维修舱、航线、奖励、指挥中心。

## 和已有规格的关系

- **事件规格 3.7**：本规格第 3 节是它对 activity/1.1 模拟模块的细化。3.7 的表只写了动词怎么对应，没写 payload 怎么换。
- **事件规格 3.1**：`poe.predicted` 增加三个可选字段（第 3 节）。
- **ADR-005 第 4、6 条**：`run_id` 和心跳，见第 2 节的两处说明。
- **ADR-006 第 1 条**：见第 5 节。本切片不放宽它。
- **竖切片 1 规格**：摄入、掌握度、会话恢复、窗口锁都沿用；第 2 节「读发布包」多读一种文件（模块的 `index.html`）；第 8 节「演示部署」的内容来源改成 `content/`。
- **#28**：宿主的状态机、校验、配额、越界测试在本切片做掉；#28 剩下「预测 → 观察 → 解释」、契约测试器的完整流程和小孔成像。

## 拍板结果（2026-11-11，Luka）

前三个问题都采纳了推荐：

1. 本切片的记录先算「试玩记录」，页面上写明没有备份；紧接着做竖切片 6（导出、导入、恢复演练），演练过了再决定这些记录留不留。
2. 演示页改用真实内容，分数那颗夹具星不再显示，记录不删。
3. 「我有个问题」这一版先不记录，只显示一句话，等竖切片 2 做了私人文字再接上。

还没有结果的一项：2026-11-08 Codex 基础设施审查里延后的数据模型改动，约定是「在真正开始记进度之前」再定。仓库里没有那份审查的原文。第 1 条的「试玩记录」不触发那个约定；竖切片 6 开工之前要先拿到原文对照。
