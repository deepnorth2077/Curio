# 规格：竖切片 1 · 分数挑战点亮一颗星（#24）

- 状态：提议，第 2 稿（第 1 轮审阅意见已处理，见 `docs/reviews/pr-60.md`；等第 2 轮审阅）
- 依据：内容规格（`docs/specs/content.md` 3.3、3.4、6.3）、事件规格（`docs/specs/events.md` 第 2、5、6、9 节）、ADR-001（内核与外壳）、ADR-003（发布不可变）、ADR-004（事件是事实来源）、ADR-008（不打包）、ADR-009（竖切片、验收用例先行）
- 实现任务：分两份交付。**1a**（CURIO-SL1a）：发布包 → 五道选择题 → 作答事件存好 → 点亮 → 刷新重放。**1b**（CURIO-SL1b）：提示、看答案、数字和分数输入框、点亮动效。两份都属于 #24

## 问题

内容格式、事件格式、发布构建器都有了，但还没有一个页面真正把它们串起来：孩子做完一次挑战，没有任何地方记下这件事，星星也不会亮。后面的切片（讲解、航线、维修舱、导出）都要建在「事件写进去、掌握度算出来」这条路上，这条路得先打通一次。

## 方案

一个独立的页面（不是原型）：打开后看到星图上一颗暗着的星「分数的初步认识」。点它，做一组分数挑战，逐题作答，答错可以再答。做完看到「第一次就答对了几道」。首答正确率达到 0.8，星星亮起来。刷新页面，星星还亮着，因为它是从存下来的事件重新算出来的。

**1a 只做最窄的一条路**：一个知识点、一个挑战、五道选择题、固定题序、一个窗口，答错可以再答，没有提示和看答案。重点是异步的接缝：写库失败、中途刷新、开两个窗口，都不能留下多余或缺失的事实。**1b** 在同一条路上加提示、看答案、数字和分数输入框、点亮动效。

内容来自发布包（构建器生成），每次作答都记成 event/2 事件存进浏览器；掌握度只从事件算。

## 用户故事

1. 作为舰长，我想要点一颗星就开始挑战，这样不用找入口。
2. 作为舰长，我想要答错了能再答一次（1b 还能看提示），这样卡住时不会只能放弃。
3. 作为舰长，我想要做完时看到自己答对了几道、星星亮起来，这样知道自己做到了。
4. 作为舰长，我想要刷新、关掉再打开以后星星还亮着，这样做过的事不会丢。
5. 作为舰长，我想要「没存上」的时候页面告诉我，再点一次就好，这样不会以为做完了其实没记下来。
6. 作为家长，我想要每次作答都记下当时的内容版本，这样以后能查到孩子做的是哪一版题。
7. 作为维护者，我想要摄入、掌握度、判分、挑战状态机、提交各有一个能单独测试的接口，并且有手算的黄金向量，这样实现 AI 交来的代码我能在接缝上验证，以后换算法、写 Python 版也有同一把尺子。
8. 作为维护者，我想要页面用原生 ES 模块、不打包，这样 Luka 拷贝文件就能部署。

## 实现上的决定

### 1. 目录和模块

```
kernel/js/        内核：只认通用对象，不知道星图、挑战长什么样（ADR-001）
  validate.js     信封和 payload 校验（本切片支持的 5 个动词）；导出 numberOk(x)：数值规则
  log.js          createLog()：check（不改状态）、ingest、去重、冲突、隔离区
  mastery.js      projectMastery(events)：尝试合法性 + 掌握度
  ulid.js         ULID 生成（单调递增）
kernel/test/      node:test 测试，含黄金向量的执行器
kernel/vectors/   黄金向量（Claude 手算，本 PR 提交）
engine/js/
  grade.js        grade(answer, response)：判分
  quiz.js         挑战的纯状态机：输入动作，输出界面状态和要写的事件（不碰 DOM）
engine/test/      node:test 测试
engine/vectors/   grading.json：判分向量（Claude 手算，本 PR 提交）
app/
  index.html      页面外壳：星图（只有发布包里的星）、挑战、结果
  app.js          启动、读发布包、拿窗口锁、画界面、调用内核和引擎
  commit.js       commitEvent()：一条事件「检查 → 写库 → 进日志」（不碰 DOM，可在 Node 里用假存储测）
  store.js        IndexedDB 存取（收到的原始文字、收据、设备信息、下一个序号）
app/test/         node:test 测试：commit.js（假存储）
```

- 判分属于活动引擎，不放进内核（ADR-001）：内核只看事件里记下的 `correct`。
- 全部是浏览器原生 ES 模块，用 JSDoc 写类型，不引入任何依赖（ADR-008）。测试用 Node 自带的 `node --test`（Node 20 以上），不装包。`tsc --noEmit` 类型检查以后再加。
- 内核和引擎的模块**不碰** DOM、存储、时间和随机数，所以能在 Node 里直接测。读写 IndexedDB、取当前时间、生成 ULID、洗牌都在外壳里做，结果作为参数传进去。`commit.js` 只通过传进来的 `store` 对象碰存储。
- **字符串长度**一律按 Unicode 码点数（和 JSON Schema 的 `maxLength` 一致）。JavaScript 里写 `[...s].length`，不用 `s.length`（那是 UTF-16 单元数，补充平面字符会算成 2）。

### 2. 读发布包

浏览器读不了 YAML，所以构建器在每个 YAML 旁边多写一份同名加 `.json` 的文件（内容规格 6.3，本 PR 一起改）。外壳：

1. 读 `release/release.json`；`engine_min` 大于 1 时不往下走，显示「需要更新」。
2. **核对清单**：按内容规格 6.2 把 `{engine_min, contracts, nodes, activities, assets}` 转成规范 JSON（键按码点排序、不留空白、不转义非 ASCII），用 `crypto.subtle.digest("SHA-256", …)` 算哈希，必须等于 `content_hash`，`release_id` 必须等于 `rel_` + `content_hash`。
3. 按清单里每个 YAML 条目的 `json.path` 读 `.yaml.json`，核对字节数和 SHA-256 都等于 `json.bytes`、`json.sha256` 以后才解析使用（内容规格 6.3）。
4. 第 2、3 步任何一处对不上，不往下走，显示「内容包不完整，请家长重新部署」，不写任何事件。
5. 星图只画清单里的知识点；点一颗星，列出它被收录的 `quiz` 活动，这一版只有一个，直接进入。

### 3. 摄入（`kernel/js/log.js`）

```js
const log = createLog();          // 空的内存日志
log.check(rawText)                // → {result, reason?, detail?}：判断结果，不改日志
log.ingest(rawText)               // → 和 check 同样的结果，并按结果改日志
log.events()                      // → 已接收的事件（解析后的对象），按接收顺序
log.raw()                         // → 已接收事件的原始文字，按接收顺序
log.quarantined()                 // → [{raw, reason, detail}]
```

- `result` 是 `accepted`（接收）、`duplicate`（重复）、`quarantined`（隔离）之一；隔离时 `reason` 是 `invalid`（不合格）或 `conflict`（冲突）。`detail` 是给人看的一句话，测试不比较它。
- `check` 和紧接着的 `ingest` 对同一条原始文字给出的结果必须相同。
- 外壳启动时把存下来的原始文字（接收的和隔离的）按到达顺序重新 `ingest` 一遍，就恢复出同样的日志和隔离区。

一条原始文字进来，按顺序判断，第一条命中的就是结果（事件规格 5.2，本切片收窄）：

1. 按 UTF-8 编码超过 16384 字节 → 不合格。
2. 不是合法 JSON（`NaN`、`Infinity` 这些写法也不合法），或者顶层不是对象 → 不合格。
3. 有任何一个数不满足事件规格第 2 节的数值规则 → 不合格。
4. 信封不满足 `schemas/event.schema.json`（必填字段、不许多余字段、各 ID 和时间的格式、`actor` 的格式）→ 不合格。
5. `verb` 不是本切片支持的 5 个之一：`attempt.started`、`item.answered`、`hint.used`、`attempt.completed`、`attempt.abandoned` → 不合格（`detail` 写「这一版不认这个动词」）。schema 里有、本切片不认的动词也算。后面的切片逐个加上。
6. 这个动词的规则不满足：必须带 `attempt_id` 和 `content`；`actor.type` 的限制；payload 的字段、类型、范围（全部照抄 schema，见下表）→ 不合格。
7. `event_id` 已经有了：两条**语义相同** → 重复；否则 → 冲突。
8. `(device_id, device_seq)` 已被另一条事件占用 → 冲突。
9. 都不是 → 接收。

| 动词 | `actor.type` | payload |
| --- | --- | --- |
| `attempt.started` | learner | `{mode}`，`mode` 是 `first`、`retry`、`review` 之一 |
| `attempt.completed` | learner | `{duration_ms}`，非负整数 |
| `attempt.abandoned` | learner 或 system | `{reason}`，`left`、`timeout`、`error` 之一 |
| `item.answered` | learner | `{item_id, response, correct, try, hints_used, misconception?}`：`item_id` 字符串；`response` 字符串，最多 32 个字符（按码点数）；`correct` 布尔值；`try` 不小于 1 的整数；`hints_used` 非负整数；`misconception` 字符串 |
| `hint.used` | learner | `{item_id?, level}`：`level` 是 1～3 的整数 |

- payload 不许有表里以外的字段。「整数」按 JSON Schema 的意思：解析后是整数值就行，`1`、`1.0`、`1e0` 都算整数 1。
- 布尔值只认 `true`、`false`：`"correct": 1` 不合格，不能按真值处理。
- **语义相同**照事件规格 5.2：解析成 JSON 值再比，类型必须相同（`true` 和 `1` 不同），对象不看键的顺序，数字按数值比。
- 冲突的事件进隔离区，**不覆盖**已有的那条。所以冲突时结果和到达顺序有关：先到的那条留下。

### 4. 掌握度（`kernel/js/mastery.js`）

```js
projectMastery(events)   // events：已接收的事件（log.events()）
// → {algorithm_version: "mastery/1", nodes: {<知识点 id>: {state, best}}, conflicts: [{attempt_id, rule}]}
```

**尝试的合法性**照事件规格 6.3：把同一 `attempt_id` 的事件按 `device_seq` 从小到大排好，依次检查 5 条规则，记下**编号最小的**一条不满足的规则。一次尝试只要有一条不满足，就是「不一致」：不计入掌握度，列进 `conflicts`。

1. 所有事件的 `device_id` 相同，`learner_id` 也相同；
2. 每条事件的 `actor` 都是 `{type: learner, id: <这条事件的 learner_id>}`；只有 `attempt.abandoned` 还允许 `actor.type` 是 `system`；
3. 所有事件的 `content` 语义相同；
4. 第一条是 `attempt.started`，而且只有这一条 `attempt.started`；结束事件（`attempt.completed` 或 `attempt.abandoned`）最多一条，有的话是最后一条；
5. 同一个 `item_id` 的 `item.answered`，按顺序排下来 `try` 恰好是 1、2、3……，不重复、不跳号。

（第 4 条里「只有一条 `attempt.started`」是把事件规格「第一条是 started」说完整：第二条 started 也让尝试不一致。）

**已完成的合法尝试**：合法，并且最后一条是 `attempt.completed`。被放弃的（最后是 `attempt.abandoned`）和还没结束的，都不算完成，也不算不一致。

**一次尝试的首答成绩** `{correct, answered}`：`answered` = 这次尝试里作答过的不同 `item_id` 个数；`correct` = 其中 `try = 1` 那条 `correct` 为 `true` 的个数。

**每个知识点**（`content.node_id`）：

- `nodes` 里列出已接收事件中出现过的每个 `content.node_id`，不管尝试合不合法、完没完成。
- `best`：这个知识点所有已完成的合法 `quiz` 尝试（`content.activity_kind` 是 `quiz`）里，`answered` 大于 0 的那些，取首答正确率最高的一次；正确率相同时取 `answered` 大的。比较正确率用整数交叉相乘（`c1 × a2` 和 `c2 × a1`），不用小数。没有这样的尝试时是 `null`。
- `state`：
  - `lit`：`best` 不是 `null`，并且 `best.correct × 5 ≥ best.answered × 4`（即首答正确率 ≥ 0.8）；
  - `explored`：不是 `lit`，但至少有一次已完成的合法尝试（任何类型）；
  - `untouched`：其他情况。
- 事件规格 6.4 里「没有未修好的错题」这个条件，本切片没有错题动词，总是满足。

`conflicts` 按 `attempt_id` 字符串排序。

本切片只有一个孩子，投影不按孩子分开算。加第二个孩子时，投影先按 `learner_id` 分组（那时改向量和本节）。

**注意**：内核不读发布包，所以不知道挑战一共几道题，首答正确率的分母是「作答过的题数」。所以「每道题都有作答」由外壳保证：`quiz.js` 只有在活动里**每个** `item_id` 都已有一条已存好的 `item.answered` 时，才产出 `attempt.completed`（第 6 节）。不能靠伪造作答补分母，也不在投影里写死题数：单题活动合法的 1/1 和五题活动漏记四题是两回事。

### 5. 判分（`engine/js/grade.js`）

```js
grade(answer, response)   // answer：活动文件里的 answer 对象；response：孩子的作答（字符串）
// → {correct: true|false, misconception: <误区 id> | null}
```

先把 `response` 规整：去掉首尾的空白，空白**只**指这 7 种字符：制表符 U+0009、换行 U+000A、U+000B、U+000C、回车 U+000D、空格 U+0020、全角空格 U+3000（不用语言自带的 `trim`/`strip`，它们认的字符不一样）；全角数字 `０`～`９` 换成半角；全角斜杠 `／` 换成 `/`；全角小数点 `．` 换成 `.`。

- **选择题**：`response` 是选项 `id`。是正确选项 → 对；是错误选项 → 错，误区是这个选项的 `misconception`（没有就是 `null`）；不是任何选项的 `id` → 错，`null`。
- **数字题**：`response` 必须整个匹配 `-?[0-9]+(\.[0-9]+)?`，否则错、`null`。解析成数 `x`。`|x − value| ≤ tolerance` → 对。否则按顺序看 `common_wrong`，第一个满足 `|x − 它的 value| ≤ tolerance` 的，误区是它的；都不满足 → `null`。`tolerance` 没写时是 0。
- **分数题**：`response` 必须整个匹配 `a/b`（斜杠两边可以有空格）或 `b分之a`（「分之」两边可以有空格），`a`、`b` 都是 1～6 位半角数字；否则错、`null`。按整数解析，`b` 是 0 时错、`null`。
  - `accept_equivalent` 为假：`a`、`b` 分别等于 `numerator`、`denominator` → 对（`01/04` 也对，按整数比）。
  - `accept_equivalent` 为真：`a × denominator = numerator × b` → 对（整数相乘，不用小数）。
  - 不对时，按顺序看 `common_wrong`，用和上面**同样的方式**（同一个 `accept_equivalent`）比，第一个匹配的误区就是结果；都不匹配 → `null`。
  - 中文数字（「四分之一」）不认，判错。界面给分数题配上下两个数字框，拼成 `a/b` 交给 `grade`，孩子不用自己打斜杠。
- 正确时 `misconception` 一律是 `null`。
- 先比正确答案，再看 `common_wrong`：一个作答同时落在正确答案和某个 `common_wrong` 的范围里时，判对。

### 6. 挑战状态机和外壳（`engine/js/quiz.js`、`app/`）

#### 6.1 挑战状态机（`quiz.js`）

```js
let q = startQuiz(activity, order)     // order：题目 item_id 的顺序，由外壳决定（shuffle 为真时外壳洗牌）
q = step(q, action)                    // 纯函数，返回新状态
q.view                                 // 界面要显示什么：当前题、选项、反馈、是否等待存储、结果
q.pending                              // 要写的事件（{verb, payload}），没有就是 null；同一时间最多一条
```

`action` 有四种：

| 动作 | 什么时候 | 状态机做什么 |
| --- | --- | --- |
| `{type: "answer", response}` | 孩子点了一个选项 | 没有 `pending` 时才接受：调用 `grade`，产出 `item.answered`（`try` 是这道题第几次作答，`hints_used` 1a 恒为 0）作为 `pending`，界面进入「等待存储」，不能再点 |
| `{type: "saved"}` | 外壳报告 `pending` 已存好 | 清掉 `pending`，记下这次作答；答对 → 显示反馈，进入下一题；答错 → 显示反馈，可以再答。**每道题都有了答对的作答**以后，产出 `attempt.completed` 作为 `pending` |
| `{type: "failed"}` | 外壳报告没存上 | `pending` 原样保留，界面显示「没存上，再点一次」和「再试」按钮 |
| `{type: "retry"}` | 孩子点「再试」 | 不改 `pending`，外壳用**同一条原始文字**重新提交 |

- 「每道题都有作答」只看**已存好**（收到过 `saved`）的作答。`attempt.completed` 存好以后，`view` 显示结果「第一次就答对了 X 道，一共 Y 道」，Y 是活动的题数。
- 1a 只支持选择题；活动里有别的题型时，`startQuiz` 抛错，外壳不显示这个活动。
- 1b 再加 `{type: "hint"}`、`{type: "reveal"}`：「看答案」只有这道题已有一次存好的作答后才出现，看过答案的题算「有结果」，但不写事件、不改分母。

#### 6.2 提交一条事件（`commit.js`）

```js
await commitEvent(store, log, raw, receipt)   // → "accepted" | "duplicate" | "quarantined"；存储失败时抛错
```

1. `r = log.check(raw)`。
2. `duplicate`：已经存过了，返回 `duplicate`（重试时上一次其实已经提交成功的情况）。
3. `quarantined`：`await store.putInbox(raw)` 存进收件表，再 `log.ingest(raw)`，返回 `quarantined`。外壳当作程序错误处理（显示「出错了」，不再往下做），因为本机产生的事件不该不合格。
4. `accepted`：`await store.commit(raw, receipt, nextSeq)`：**一个** IndexedDB 事务里写收件表、收据、「下一个序号」。事务提交完成才算成功，这时才 `log.ingest(raw)`，返回 `accepted`。
5. 第 4 步抛错（写入失败、事务中止）：不调用 `ingest`，把错误抛给调用者。内存日志、存储、序号都和调用前一样。

`store` 是一个只有 `putInbox`、`commit`、`loadAll` 三个方法的对象，`app/store.js` 用 IndexedDB 实现，测试用假存储。

**验收测试**（`app/test/commit.test.js`，Claude 派发前写好）：用一个可以指定「第几次写入失败」的假存储，跑三种情况：作答那条写入失败、完成那条写入失败、事务提交到最后一步中止。每种都是：失败 → 重试同一条原始文字成功 → 用存储里的数据新建日志（模拟刷新）。检查：两本日志的 `raw()` 完全相同；每个 `event_id` 只出现一次；`device_seq` 连续不跳号；投影相同。

#### 6.3 外壳的行为（`app/`）

- **第一次打开**：生成 `lrn_`、`dev_` 两个 ULID，存进 IndexedDB。以后一直用它们。清空浏览器存储就是新设备（事件规格第 1 节）。
- **一台设备只有一个窗口写事件**：启动时用 `navigator.locks.request("curio-writer", {ifAvailable: true}, …)` 拿锁，一直持有到页面关闭。拿不到锁的窗口只能看星图，不能开始挑战，提示「另一个窗口正在用」。浏览器没有 `navigator.locks` 时，同样只能看。
- **启动**（拿到锁以后）：`store.loadAll()` 取出收件表，按到达顺序重新 `ingest`；然后给这台设备上还没结束的尝试补写 `attempt.abandoned`（`reason: left`，`actor` 是 `{type: system, id: "sys:shell"}`），每条都走 `commitEvent`；然后算掌握度、画星图。只读窗口跳过补写。
- **写事件**：外壳组装 event/2 信封（`device_seq` 取存储里的「下一个序号」、`occurred_at` 取当前 UTC 时间、`content_release` 是发布包的 `release_id`、`activity_version` 是活动的 `version`），`JSON.stringify` 一次得到原始文字，交给 `commitEvent`。成功 → 给状态机发 `saved`；抛错 → 发 `failed`，留着这条原始文字，孩子点「再试」时原样再提交。一条没存好之前，不组装下一条。
- **开始一次挑战**：写 `attempt.started`，`mode` 是 `first`（这台设备上这个活动从没完成过）或 `retry`。题目顺序按活动的 `shuffle` 决定（1a 的演示活动 `shuffle: false`）。
- **作答**：点一个选项就是一次作答，交给状态机。答对显示 `feedback.correct`（没有就用默认的话）；答错显示这个错误选项的 `feedback`，没有就用 `feedback.wrong` 或默认的话，可以再答。
- **完成**：状态机产出的 `attempt.completed`（`duration_ms` 是从开始到现在的毫秒数）存好以后，显示结果，重新算掌握度，星星从暗变亮（1a 直接换样子，1b 加动效，尊重 `prefers-reduced-motion`）。
- **刷新**：星星的亮暗只由收件表重放出来的事件决定。
- **外观**：照 AGENTS.md 的产品规则（暖纸面、手绘墨线、深色模式同一套线稿、不出现「学习」二字）。平板、手机、电脑都能用，只用触摸能做完，键盘也能做完。

### 7. 黄金向量

**掌握度和摄入**：`kernel/vectors/<名字>.json`，每个文件：

```json
{
  "name": "…",
  "about": "这个向量证明什么（对应事件规格第 9 节哪一行）",
  "order_free": true,
  "base": { "schema": "event/2", "learner_id": "…", "device_id": "…", "actor": {…}, "content": {…} },
  "inputs": [
    {"event": {"event_id": "…", "device_seq": 1, …}, "expect": "accepted"},
    {"raw": "{…原始文字…}", "expect": "quarantined:invalid", "why": "…"},
    {"raw": "{…}", "pad_to_bytes": 16385, "expect": "quarantined:invalid", "why": "…"}
  ],
  "mastery": { "algorithm_version": "mastery/1", "nodes": {…}, "conflicts": […] },
  "worked": "手算过程"
}
```

- `event` 项：原始文字 = `JSON.stringify(Object.assign({}, base, event))`，浅合并，`event` 里写了的字段整个替换 `base` 里的。
- `raw` 项：原样使用；有 `pad_to_bytes` 时在末尾补空格，补到 UTF-8 字节数正好等于它（JSON 末尾的空白是合法的）。
- `expect`：`accepted`、`duplicate`、`quarantined:invalid`、`quarantined:conflict`。
- `mastery_after`（可选）：写在某一项上，表示摄入到这一项为止，对 `log.events()` 做投影应该得到它。用来检查分批到达时，每个批次边界上的结果都对。
- **执行器**（`kernel/test/vectors.test.js`）：新建 `createLog()`，按顺序摄入每一项：先 `check`、再 `ingest`，两个结果都和 `expect` 比较；有 `mastery_after` 的项，摄入后立刻投影比较。全部摄入后：
  - `log.raw()` 必须**正好**等于标成 `accepted` 的那些项的原始文字，按顺序（重复和冲突不替换首次接收的原文）；
  - 对 `log.events()` 调用 `projectMastery`，和 `mastery` 深比较。
  - `order_free` 为真的向量还要做 20 次：用固定种子把全部输入打乱，每项随机重复 1～3 次，确认没有任何一项被隔离、投影和 `mastery` 完全相同。
- **数值规则**：`kernel/vectors/numbers.json`，`{cases: [{json, expect, why}]}`。执行器对每条 `JSON.parse(json)` 得到一个数，调用 `numberOk`，和 `expect`（真或假）比较。这一组单独测数值规则，因为本切片的事件字段都要求整数，只看摄入结果会把「小数不超过 6 位」这条规则的错误盖住。

本 PR 提交的向量：

| 文件 | 证明什么 |
| --- | --- |
| `mastery-lit-basic` | 正常做完一次挑战，4/5 点亮 |
| `mastery-not-lit` | 3/5 只算 explored |
| `mastery-order-free` | 打乱、重复到达，投影不变 |
| `mastery-two-devices` | 两台设备交错到达，取最好的一次 |
| `mastery-best-of-many` | 取最好的一次；正确率相同取题数多的；放弃的、没结束的不算；系统写的放弃合法 |
| `mastery-kinds-and-nodes` | 讲解只算 explored；没结束是 untouched；1/1 会点亮；0 道题完成是 explored |
| `attempt-inconsistent` | 合法性 5 条规则各违反一次，含「两条 started」「两条结束」 |
| `ingest-duplicates-conflicts` | 键顺序、`1.0`、`1e0`、空白都是重复；同 ID 不同内容、序号被占是冲突；`correct: 1` 不合格 |
| `ingest-invalid` | 22 种不合格（含 16385 字节、2^53、7 位小数、本切片不认的动词）和 4 种边界上合格（16384 字节、2^53−1、`1e2`） |
| `ingest-code-points` | `response` 是 32 个补充平面字符时合格，33 个时不合格（按码点数，不按 UTF-16 单元数） |
| `mastery-best-ratio` | 按正确率选 best：4/5 胜过 7/10，虽然 7/10 答对的题更多 |
| `mastery-best-tie-order` | 正确率相同取题数多：8/10 先完成、4/5 后到，结果仍是 8/10 |
| `mastery-zero-score` | 合法完成 0/5：best 是 0/5，不是 null；state 是 explored |
| `mastery-seq-order` | 时间、事件 ID、到达次序都和 `device_seq` 相反，合法性仍按 `device_seq` 判断 |
| `mastery-batches` | 分三批到达，每个批次边界上的投影都对（`mastery_after`） |
| `attempt-multi-rule` | 同时违反第 1、3、5 条只报 1；某题第一条就是 try=2 报 5；只被不合法尝试涉及的两个节点都是 untouched |
| `numbers` | 数值规则单独测（见上） |

**判分**：`engine/vectors/grading.json`（第 2 轮补了全角小数点、分子 6 位、分母 7 位、首尾空白只去 7 种字符、正确答案和 `common_wrong` 同时命中），`{answers: {<名字>: answer 对象}, cases: [{answer, response, expect: {correct, misconception}, why}]}`。执行器逐条调用 `grade` 比较。

期望值全部由 Claude 按本规格手算，写在 `worked` 和 `why` 里（ADR-009 第 6 条、事件规格第 9 节）。`tools/tests/test_vectors.py` 在 CI 里检查向量本身：格式对不对；标成接收、重复的事件能不能通过 `schemas/event.schema.json`；另外用一份独立写的 Python 对照实现复核每个期望值，两边对不上就是向量或对照实现有错，要查清楚。这份对照实现**不是**被测代码，也不交给实现 AI。

整合时先确认向量在空实现上失败，再确认在交付的实现上通过。`app/test/commit.test.js`（6.2）也一样。

### 8. 演示部署（整合时 Claude 做）

`pages.yml` 改成：用 `tools/build_release.py` 把 `tools/tests/fixtures/content/` 构建成发布包放进 `release/`（1a 用一份只有五道选择题的夹具活动），连同 `app/`、`kernel/`、`engine/` 按仓库里的目录结构一起发布，原型仍在根目录。演示地址 `https://deepnorth2077.github.io/Curio/app/`。CI 加一步 `node --test kernel engine app`。

## 测试接缝

| 接缝 | 能发现 | 发现不了 |
| --- | --- | --- |
| `createLog().ingest` + 摄入向量 | 不合格的判断（大小、JSON、数值、信封、动词、payload）、重复和冲突、`true` 和 `1` 不分、`1` 和 `1.0` 误判冲突 | 存储读写 |
| `projectMastery` + 掌握度向量 | 首答计算、5 条合法性规则、放弃和未完成的尝试、多次尝试取最好、乱序重复分批结果一样 | 外壳有没有按规定写事件 |
| `grade` + 判分向量 | 两种分数写法、全角字符、等值分数、误区匹配的顺序、认不出的写法 | 界面显示 |
| `numberOk` + 数值向量 | 小数位数、10^9 和 2^53−1 的边界、`-0`、`1.0` | 别的字段规则 |
| `startQuiz`/`step` | 没存好不前进；每道题都存好作答才产出完成；没存上时 `pending` 不变 | 画面 |
| `commitEvent` + 假存储 | 写库失败、事务中止后重试只有一份事实；刷新后日志一样 | 真的 IndexedDB 行为（交给演示步骤） |
| 页面（Luka 的演示步骤） | 整条路通不通、刷新后还亮着、触摸能不能做完 | 规则细节（交给上面三个接缝） |

## 演示步骤（Luka 亲手验收）

1a：

1. 平板打开演示地址，看到星图上一颗暗的星「分数的初步认识」。
2. 点它，开始挑战。其中一道故意先答错，再答对。
3. 做完看到「第一次就答对了 4 道，一共 5 道」，星星亮起来。
4. 刷新页面，星星还亮着。
5. 再做一遍，只答对 2 道：星星仍然亮着（取最好的一次）。
6. 再开始一遍，答到第 3 题时刷新：星星还亮着；指挥中心以后能看到这次是「中途离开」。
7. 同时在两个标签页打开演示地址：后打开的那个只能看，写着「另一个窗口正在用」。

写库失败没法在平板上演示，由 6.2 的验收测试保证。

1b：在 1a 的基础上，故意答错一道，点「要个提示」，再点「看答案」；结果里的「一共 5 道」不变。

## 不做什么

- **断网可用**（Service Worker）：挪到 #9（发布、预览与回滚），它本来就要处理发布包的缓存。
- 其他动词、私人文字、奖励、航线、错题、导出导入、同步、升级器：后面的切片按需加。
- 真实内容：演示用测试夹具里的「分数的初步认识」。真实知识点试玩合入后再换成 `content/`。
- 讲解、反思、星座缩放、知识地铁、家长端。
- 多窗口同时写事件：本切片只允许一个窗口写（6.3）。以后真要同时写，需要跨窗口分配序号、判断哪个窗口还活着。
- 在 `attempt.started` 里记下题目 ID 快照、让投影核对作答是否完整：以后接收第三方事件或导入时再定。
- `tsc --noEmit` 类型检查。

## 和已有规格的关系

- 内容规格 6.2、6.3：每个 YAML 旁边写一份 `.json`，清单里登记它的路径、哈希、字节数并参与 `content_hash`；构建只读一次文件、先写临时目录（本 PR 改）。
- 事件规格 6.3：「只有一条 `attempt.started`」和「`conflicts` 里记编号最小的那条规则」已补回（本 PR 改）。
- 事件规格第 9 节表里「`value` 一次是 `true`、一次是 `1` 判为冲突」需要 `sim.*` 动词，本切片不认，所以这里只测「`correct: 1` 不合格」，冲突那条留到加 `sim.*` 的切片。
