# 规格：竖切片 1 · 分数挑战点亮一颗星（#24）

- 状态：已接受，第 3 稿（两轮外部审阅的意见都已处理，见 `docs/reviews/pr-60.md`；2026-11-08 Luka 授权处理完即合入）
- 依据：内容规格（`docs/specs/content.md` 3.3、3.4、6.3）、事件规格（`docs/specs/events.md` 第 2、5、6、9 节）、ADR-001（内核与外壳）、ADR-003（发布不可变）、ADR-004（事件是事实来源）、ADR-008（不打包）、ADR-009（竖切片、验收用例先行）
- 实现任务：分两份交付。**1a**（CURIO-SL1a）：发布包 → 五道选择题 → 作答事件存好 → 点亮 → 刷新重放。**1b**（CURIO-SL1b）：提示、看答案、数字和分数输入框、点亮动效（细则 6.4）。两份都属于 #24

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
engine/test/      node:test 测试（quiz.test.js 由 Claude 派发前写好）
engine/vectors/   grading.json：判分向量（Claude 手算，本 PR 提交）
app/
  index.html      页面外壳：星图（只有发布包里的星）、挑战、结果
  app.js          启动、读发布包、拿窗口锁、画界面、调用内核和引擎
  commit.js       createCommitter()：串行地「检查 → 写库 → 进日志」（不碰 DOM，可在 Node 里用假存储测）
  session.js      openSession()：6.3「正在恢复」的第 1～3 步（不碰 DOM，可在 Node 里用假存储测）
  store.js        IndexedDB 存取（收到的原始文字、收据、设备信息、下一个序号）
app/test/         node:test 测试：commit.test.js、resume.test.js（假存储，Claude 派发前写好）
```

- 判分属于活动引擎，不放进内核（ADR-001）：内核只看事件里记下的 `correct`。
- 全部是浏览器原生 ES 模块，用 JSDoc 写类型，不引入任何依赖（ADR-008）。测试用 Node 自带的 `node --test`（Node 20 以上），不装包。`tsc --noEmit` 类型检查以后再加。
- 内核和引擎的模块**不碰** DOM、存储、时间和随机数，所以能在 Node 里直接测。读写 IndexedDB、取当前时间、生成 ULID、洗牌都在外壳里做，结果作为参数传进去。`commit.js` 只通过传进来的 `store` 对象碰存储。
- **字符串长度**一律按 Unicode 码点数（和 JSON Schema 的 `maxLength` 一致）。JavaScript 里写 `[...s].length`，不用 `s.length`（那是 UTF-16 单元数，补充平面字符会算成 2）。

### 2. 读发布包

浏览器读不了 YAML，所以构建器在每个 YAML 旁边多写一份同名加 `.json` 的文件（内容规格 6.3，本 PR 一起改）。外壳：

1. 读 `release/release.json`；`engine_min` 大于 1 时不往下走，显示「需要更新」。
2. **核对清单**：按内容规格 6.2 把 `{engine_min, contracts, nodes, activities, assets}` 转成规范 JSON：**递归地**给每一层对象的键排序（按码点，不用 `localeCompare`），数组保持原顺序，不留空白，字符串用 `JSON.stringify` 写（清单里只有 ASCII 字符串和安全整数，构建器保证 `version`、`engine_min` 是整数，不会出现 `1.0`）。用 `crypto.subtle.digest("SHA-256", …)` 算哈希，必须等于 `content_hash`，`release_id` 必须等于 `rel_` + `content_hash`。
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
- **数字题**：`response` 必须整个匹配 `-?[0-9]{1,9}(\.[0-9]{1,6})?`（整数部分最多 9 位，小数最多 6 位），否则错、`null`。**按十进制精确比较**，不用二进制浮点直接相减（`0.4 − 0.3` 用浮点算是 `0.10000000000000003`，会把边界上的对判成错）：
  - 把作答换成「百万分之一」为单位的整数：整数部分 × 1000000 + 小数部分补足 6 位。最大约 10^15，在安全整数以内。
  - 活动里的 `value`、`tolerance`、`common_wrong[].value` 也这样换：先取它的最短十进制表示（JavaScript 的 `String(x)`、Python 的 `repr(x)`），**按带指数的十进制数**解析后再换成整数：Python 的 `repr(0.00001)` 是 `1e-05`，JavaScript 的 `String(1e-7)` 是 `1e-7`，不能只按小数点拆。这些数必须满足事件规格第 2 节的数值规则（小数不超过 6 位、绝对值小于 10^9），不满足时 `startQuiz` 抛错（6.1）。
  - `|X − V| ≤ T` → 对。否则按顺序看 `common_wrong`，第一个满足 `|X − 它的 V| ≤ T` 的，误区是它的；都不满足 → `null`。`tolerance` 没写时是 0。不加任何额外的 epsilon。
- **分数题**：`response` 必须整个匹配 `a/b` 或 `b分之a`，斜杠和「分之」两边**只**允许普通空格 U+0020（任意个），不允许制表符、全角空格；`a`、`b` 都是 1～6 位半角数字（前导零也算位数）；否则错、`null`。按整数解析，`b` 是 0 时错、`null`。
  - `accept_equivalent` 为假：`a`、`b` 分别等于 `numerator`、`denominator` → 对（`01/04` 也对，按整数比）。
  - `accept_equivalent` 为真：`a × denominator = numerator × b` → 对（整数相乘，不用小数）。
  - 不对时，按顺序看 `common_wrong`，用和上面**同样的方式**（同一个 `accept_equivalent`）比，第一个匹配的误区就是结果；都不匹配 → `null`。
  - 中文数字（「四分之一」）不认，判错。界面给分数题配上下两个数字框，拼成 `a/b` 交给 `grade`，孩子不用自己打斜杠。
- 正确时 `misconception` 一律是 `null`。
- 先比正确答案，再看 `common_wrong`：一个作答同时落在正确答案和某个 `common_wrong` 的范围里时，判对。

### 6. 挑战状态机和外壳（`engine/js/quiz.js`、`app/`）

#### 6.1 挑战状态机（`quiz.js`）

```js
let q = startQuiz(activity, order, mode)  // order：活动全部 item_id 的一个排列，由外壳决定（shuffle 为真时外壳洗牌）；mode：first 或 retry
q = step(q, action)                    // 纯函数，返回新状态
q.phase                                // "starting" | "answering" | "finishing" | "done"
q.view                                 // 界面要显示什么：当前题、选项、反馈、是否等待存储、结果
q.pending                              // 要写的事件意图 {id, verb, payload}，没有就是 null；同一时间最多一条
```

- `startQuiz` 检查：`order` 必须正好是活动里全部 `item_id` 的一个排列（不多、不少、不重复）；1a 只支持选择题；活动里的数（`value`、`tolerance` 等）满足第 5 节的范围。不满足就抛错，外壳显示「这个挑战暂时不能玩」，**不写**任何事件。
- 新状态的 `phase` 是 `starting`，`pending` 是 `attempt.started` 的意图（`payload: {mode}`）。
- **意图不带时间**。`pending.payload` 里没有 `duration_ms`；外壳第一次把这个意图组装成原始文字时补上 `duration_ms`，以后重试都用那同一条原始文字。
- `pending.id` 是状态机给每个意图编的序号（1、2、3……）。`saved`、`failed` 都带着 `id`；和当前 `pending.id` 不一样的确认一律忽略（过期的回调不会推进新的意图）。

| 动作 | 状态机做什么 |
| --- | --- |
| `{type: "answer", response}` | 只在 `phase` 是 `answering`、并且没有 `pending` 时接受，否则原样返回。调用 `grade`，产出 `item.answered` 意图（`try` 是这道题第几次作答，`hints_used` 1a 恒为 0，1b 见 6.4），界面进入「等待存储」 |
| `{type: "saved", id}` | `id` 对得上才处理：清掉 `pending`。`starting` → `answering`。作答：记下这次已存好的作答，答对 → 显示反馈、进入下一题；答错 → 显示反馈、可以再答。最后一题的正确作答存好后，进入 `finishing`，产出**一次** `attempt.completed` 意图。`finishing` 收到 `saved` → `done`，显示结果 |
| `{type: "failed", id}` | `id` 对得上才处理：`pending` 原样保留，界面显示「没存上」和「再试」按钮 |
| `{type: "retry"}` | 不改状态。外壳收到孩子点「再试」，用**同一条原始文字**重新提交；正在提交时再点不重复提交（6.2 的串行入口保证） |

- 「每道题都有作答」只看**已存好**（收到过对应 `saved`）的作答，不看界面上点过什么。
- `done` 以后不再产出任何意图；结果「第一次就答对了 X 道，一共 Y 道」里 Y 是活动的题数，X 是 try=1 答对的题数。
- 1b 再加 `{type: "hint"}`、`{type: "reveal"}`：「看答案」只有这道题已有一次**已存好**的作答后才出现，看过答案的题算「有结果」，但不写事件、不改分母。细则见 6.4。

**验收测试**（`engine/test/quiz.test.js`，Claude 派发前写好，见第 7 节）：缺任何一道已存好的作答都不完成；只存好了一次答错的作答时停在这道题；最后一道正确作答存好后只产出一次完成；完成存好后结果的分母是活动题数；失败、重试时 `pending` 不变；等待存储时再作答、过期的 `saved` 都不产生新意图；`order` 不是完整排列时抛错。

#### 6.2 提交一条事件（`commit.js`）

**不变量**：内存日志只来自两个地方——启动时重放存储，和已经提交成功的事务。除此之外谁也不改它。

```js
const committer = createCommitter(store, log, {nextSeq})   // 外壳只建一个；nextSeq 是 loadAll 读到的值
await committer.submit(raw, receipt)            // → "accepted" | "duplicate"；隔离和存储失败都抛错
committer.frozen                                // 出了「存储和内存可能不一致」的错、或外壳调用过 freeze() 以后为真，之后 submit 一律抛错
committer.freeze()                              // 外壳失去写锁时调用
committer.nextSeq                               // 下一条本机事件该用的 device_seq：创建时取 loadAll 的值，每次 accepted 后加 1
```

- **串行**：`submit` 排队，一次只处理一条，上一条结束才开始下一条。同一条原始文字正在处理时又提交（双击「再试」），返回同一个 Promise，不另起一次存储操作。启动时的补写也走它。
- 处理一条的步骤：
  1. `r = log.check(raw)`（不改日志）。
  2. `duplicate`：按不变量，它已经存好了，返回 `duplicate`，外壳当作 `saved`。
  3. `quarantined`：本机产生的事件不该不合格。`await store.putInbox(raw)` 存进收件表留作排查，然后抛错；外壳显示「出错了」，不推进状态机。
  4. `accepted`：`await store.commit(raw, receipt)`：**一个** IndexedDB 事务里写收件表、收据，并把「下一个序号」从 `device_seq` 推进到 `device_seq + 1`（事务里先读出当前值，不等于 `device_seq` 就中止）。只在事务的 `complete` 事件后 resolve；`abort`、`error` 时 reject。resolve 以后 `log.ingest(raw)`，返回 `accepted`。
  5. 第 4 步 reject：不 `ingest`，把错误抛给调用者。这时存储和内存都没变（事务没提交），可以用同一条原始文字重试。
  6. 第 4 步 resolve 以后 `ingest` 的结果不是 `accepted`（不该发生）：`frozen` 设为真，抛错；外壳提示「请刷新页面」，刷新时从存储重建。不能说「什么都没变」，因为事务已经提交了。
- **`store` 的方法**：
  - `loadAll()` → `{identity: {learner_id, device_id} | null, nextSeq, inbox: [raw, …]}`，在**一个**只读事务里读出，`inbox` 按到达序号排好。
  - `putInbox(raw)`：只往收件表追加一条。
  - `commit(raw, receipt)`：见上。
  - `init(identity)`：只在 `identity` 为空时，在一个事务里写身份和 `nextSeq = 1`；已经有身份就中止。
- **收件表**的主键是自增的到达序号，**不**以 `event_id` 或 `(device_id, device_seq)` 为唯一键：冲突的副本和解析不了的原文也要能存下来。事件的唯一约束由日志（`check`、`ingest`）负责。
- 收据在事件被接收时写（`event_id` 为键）；隔离的原文没有收据。

**验收测试**（`app/test/commit.test.js`，Claude 派发前写好，用假存储）：

| 情况 | 应该得到 |
| --- | --- |
| 作答那条事务提交前中止 | 收件表、收据、`nextSeq` 都没变，日志没变；同一条原始文字重试成功 |
| 完成那条事务提交前中止 | 同上 |
| 事务提交以后、`ingest` 之前页面关掉（重建日志模拟） | 重放能读到这条事件；这次尝试没有结束事件，启动时补一条 `abandoned` |
| 完成那条提交以后、`saved` 之前页面关掉 | 重放后尝试已完成，不补 `abandoned`，掌握度对 |
| 双击「再试」 | 只调用一次 `store.commit` |
| 启动补写还没完成就开始挑战 | 挑战的 `started` 排在补写后面，序号连续 |
| 隔离的原文 | 存进收件表，重放后隔离区一样 |
| `commit` 时存储里的 `nextSeq` 和 `device_seq` 对不上 | 事务中止，什么都没写 |

每种情况结束都检查：用存储新建的日志和内存日志的 `raw()` 完全相同；每个 `event_id` 只出现一次；本设备的 `device_seq` 从 1 连续。另外整合时 Claude 在真的浏览器里跑一次 IndexedDB 冒烟测试（中止一个事务，看三样东西都没写进去）。

#### 6.3 外壳的行为（`app/`）

外壳有三种状态：**只读**、**正在恢复**、**可以写**。只有「可以写」时能开始或继续挑战。

- **拿写锁**：启动时 `navigator.locks.request("curio-writer", {ifAvailable: true}, cb)`。拿到时 `cb` 返回一个**一直不结束**的 Promise，锁就一直持有；拿到以后进入「正在恢复」。拿不到（回调收到 `null`）→「只读」，提示「另一个窗口正在用」。只读窗口照样 `loadAll` 并重放（只读事务，不写任何东西），画出星图让孩子看；存储里还没有身份时只显示提示。给一个「再试一次」按钮（重新请求，仍然 `ifAvailable`，不抢锁、不用 `steal`）。浏览器没有 `navigator.locks` 或请求出错 → 「只读」，提示「这个浏览器不能记录」，和「被占用」分开说。
- **失去写锁**：`request` 返回的 Promise 结束或出错（例如 Safari 把页面挂起时会收回锁），或者页面从往返缓存恢复（`pageshow` 的 `persisted` 为真）→ 立刻进入「只读」，冻结 `committer`，提示「请刷新页面」。**不**自动接着做旧挑战：别的窗口可能已经把它补成了放弃。刷新后从头启动。
- **正在恢复**（拿到锁以后）：
  1. `store.loadAll()`；身份为空时调用 `store.init` 生成 `lrn_`、`dev_`（在锁里做，两个空窗口不会各生成一套）。
  2. 收件表按到达顺序重新 `ingest`。
  3. 找出本设备上没有结束事件、而且没有被判为不一致的尝试，各补一条 `attempt.abandoned`（`reason: left`，`actor` 是 `{type: system, id: "sys:shell"}`）。**补写的事件从这次尝试的事件里复制** `learner_id`、`device_id`、`attempt_id` 和完整的 `content`（包括当时的 `content_release`、`activity_version`），只有 `event_id`、`occurred_at`、`device_seq`、`actor`、`payload` 是新的。所以发布更新了、旧活动不在新发布里了，也能合法地放弃。已经有结束事件的尝试不补。每条都走 `committer`。
  4. 算掌握度、画星图，进入「可以写」。

  第 1～3 步在 `app/session.js` 里：`openSession(store, {ids, now})` → `{identity, log, committer, abandoned}`。`ids` 生成 `lrn_`、`dev_`、`evt_` 等 ID，`now()` 给 `occurred_at` 用的 UTC 时间；收据照事件规格 5.3 写成 `{event_id, recorded_at, source: "local"}`；`abandoned` 是补写的 `event_id` 列表。全部补写存好以后才 resolve，所以外壳拿到会话之前开始不了挑战。它不读发布包。（第 3 稿合入后、派发前按验收测试补写，PR #97。）
- **写事件**：外壳把状态机的意图组装成 event/2 信封（`device_seq` 取 `committer.nextSeq`、`occurred_at` 取当前 UTC 时间、完成事件补 `duration_ms`、`content` 用这次挑战开始时冻结的那一份），`JSON.stringify` 一次得到原始文字，交给 `committer.submit`。`accepted` 或 `duplicate` → 给状态机发 `saved`；抛错 → 发 `failed`，留着这条原始文字，「再试」时原样再提交。
- **开始一次挑战**：冻结当前发布的 `content`（`node_id`、`activity_id`、`activity_kind`、`activity_version`、`content_release`），这次尝试的每条事件都用它。`mode` 是 `first`（这台设备上这个活动从没完成过）或 `retry`。题目顺序按活动的 `shuffle` 决定。
- **作答**：点一个选项就是一次作答，交给状态机。答对显示 `feedback.correct`（没有就用默认的话）；答错显示这个错误选项的 `feedback`，没有就用 `feedback.wrong` 或默认的话，可以再答。
- **完成**：完成意图存好以后显示结果，重新算掌握度，星星从暗变亮（1a 直接换样子，1b 加动效，尊重 `prefers-reduced-motion`）。
- **刷新**：星星的亮暗只由收件表重放出来的事件决定。
- **外观**：照 AGENTS.md 的产品规则（暖纸面、手绘墨线、深色模式同一套线稿、不出现「学习」二字）。平板、手机、电脑都能用，只用触摸能做完，键盘也能做完。
- **引擎等级**：1a 只实现内容规格里引擎等级 1 的一个子集（选择题挑战），1b 起三种答案都支持（6.4）。发布包里有 1a 不支持的活动时，星图上照样画出知识点，点开显示「这个还在做」，不写任何事件。

**验收测试**（`app/test/resume.test.js`，Claude 派发前写好，用假存储和假时钟）：发布 R1 的活动 v1 做到一半关掉，用发布 R2（活动 v2，或者干脆没有这个活动）启动：补一条 `abandoned`，复制的是 v1 的 `content`，这次尝试合法放弃、没有规则 3 的冲突；再启动一次，不重复补。

#### 6.4 1b：提示、看答案、数字题和分数题（2026-11-10 补，派发 1b 前）

**提示**（`{type: "hint"}`）

- 只在 `phase` 是 `answering`、没有 `pending`（不管在等哪种意图）、**这道题已有至少一次已存好的作答**、并且这道题的提示还没用完时接受，否则原样返回。
  - 这是一个取舍：掌握度 `mastery/1` 只看 try=1 是否答对、不看 `hints_used`，如果作答前就能要提示，「第一次就答对」会把靠提示答对的也算进去。代价是卡住的孩子要先随便答一次，这次作答如果碰巧落在 `common_wrong` 里，会记成一条误区证据。以后要放开「作答前要提示」，得同时改掌握度（用过提示的首答不算）和本节、测试，走 A。
  - 题目没有 `hints` 时（1a 的夹具）提示一直不能要；正式内容的 `hints` 是必填的（内容规格 3.2）。
- 接受时产出 `hint.used` 意图，`payload: {item_id, level}`，`level` 是这道题已存好的提示条数 + 1（第一条是 1，最多到这道题 `hints` 的条数，并且不超过 3：`hints` 多于 3 条时只用前 3 条）。
- 存好以后这条提示才显示出来：`view.hints` 是当前这道题已存好的提示原文，按顺序。没存上时按 6.1 的 `failed`、`retry` 处理，提示不显示。
- 之后这道题的 `item.answered` 里，`hints_used` 是这道题**已存好**的 `hint.used` 条数（累计，不是这一次之前新增的条数）。

**看答案**（`{type: "reveal"}`）

- 只在 `phase` 是 `answering`、没有 `pending`（不管在等哪种意图）、这道题已有至少一次已存好的作答时接受（这时这道题一定还没答对，答对就已经进入下一题了），否则原样返回。不要求提示用完。内容规格 3.4「提示用完以后，引擎会给出答案和解释」由这个按钮承担：提示用完以前也能点。
- **不写事件、不产生意图**。这道题记为「看过答案」，进入下一题，和答对存好以后一样；`view.feedback` 是 `{item_id, correct: false, revealed: true, answer_text, text}`：`answer_text` 是正确答案的写法（选择题是正确选项的 `text`；数字题是 `String(value)`，数值规则保证不会出现指数写法，有 `unit` 时后面空一格加单位，`tolerance` 不显示；分数题是 `分子/分母`），`text` 是这道题的 `feedback.correct`（它通常解释了为什么是这个答案），没有时用引擎默认的一句话（非空字符串）。
- 看答案的是最后一道题时，和最后一道答对存好以后一样：进入 `finishing`，产出一次 `attempt.completed` 意图。
- 结果的分母仍是活动题数；看过答案的题没有 try=1 答对，不计入分子（它第一次作答已经错了）。
- 不写事件是有意的（6.1）：所以事件里分不出「答错后看了答案」和「答错后离开」。以后维修舱要用这个事实时，加一个新动词，按事件规格升版。

**数字题和分数题**

- `startQuiz` 接受三种题型。数字题的 `value`、`tolerance`、`common_wrong[].value` 必须是有限的数，满足事件规格第 2 节的数值规则（第 5 节），`tolerance` 不能是负数；分数题的 `numerator`（含 `common_wrong` 里的）必须是 0～999999 的整数、`denominator` 必须是 1～999999 的整数（判分只认 1～6 位，写不出来的答案孩子永远答不对；分子可以是 0，比如数轴上的 0/4）。不满足就抛错，外壳显示「这个挑战暂时不能玩」。
- 作答一律是字符串，交给 `grade`。分数题的界面是上下两个数字框，外壳拼成 `分子/分母` 再作为 `response` 交给状态机；数字题是一个框，有 `unit` 时框后面显示单位。框是空的时不提交。
- `response` 超过 32 个码点（事件里 `response` 的上限）时原样返回，不判分、不产生意图。外壳的输入框设 `maxlength`（数字框 16、分数的每个框 6），孩子正常输入碰不到这条。
- 当前题给界面的信息：`view.item` 是 `{id, stem, figure}`（没有配图时 `figure` 是 `null`，不再带 `choices`）；`view.answer_type` 是 `choice`、`number`、`fraction` 之一；选择题 `view.choices` 是 `[{id, text}]`（不带 `correct`、`misconception`，界面不该知道答案）；数字题有 `unit` 时 `view.unit` 是它，没有时是 `null`；`view.can_hint`、`view.can_reveal` 是布尔值，按上面的条件算（`starting`、`finishing`、`done` 和等待存储时都是 `false`）。

**点亮动效**：完成存好、星星从暗变亮时，外壳放一段不超过 1.5 秒的动效；`prefers-reduced-motion: reduce` 时直接换成亮的样子，不放动效。

**夹具**：`tools/tests/fixtures/slice-1b/content/`，同一个知识点和挑战 `act.quiz.fraction-intro-01` 的 **version 2**：五道题里有一道数字题、一道分数题，每道题 1～3 条提示（不说出答案）。演示部署改用它（第 8 节），Luka 设备上 1a 时没做完的尝试会按 6.3 用旧 `content` 合法放弃。1a 的夹具不动。

**怎么合入**：1a 已经在 `main` 上，CI 会跑全部引擎测试，所以 1b 的测试不能先于实现单独合入（会让 `main` 变红）。1b 的规格、测试、夹具和实现放在同一个 `arch/` PR 里；测试先写好的证据是只含测试的那个提交在 1a 实现上全部失败，写进审查记录。

**验收测试**（`engine/test/quiz-1b.test.js`，Claude 派发前写好）：提示只在作答存好以后、用完前接受；`level` 递增；没存好的提示不显示、不计入 `hints_used`；看答案不产生意图、进入下一题、最后一题时产出一次完成、不改分母；三种题型的 `view`；数字、分数题判分走 `grade`；数不合规则时抛错；超长作答原样返回。

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
  - `order_free` 为真的向量还要做 20 次：用固定种子把全部输入打乱，每项随机重复 1～3 次，确认没有任何一项被隔离、投影和 `mastery` 完全相同。乱序时**不**比较每一项的 `accepted`/`duplicate`（谁先到谁就是首次），也不比较 `raw()` 的顺序。
  - **`check` 没有副作用**：每一项摄入前，对 `events()`、`raw()`、`quarantined()` 做深拷贝；连续调用两次 `check`，三样都和拷贝相同；再 `ingest`，结果和 `check` 相同，并且只多出规定的一条（接收的进 `events`/`raw`，隔离的进 `quarantined`，重复的哪都不进）。
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

**派发前 Claude 还要写好**：`engine/test/quiz.test.js`（6.1）、`app/test/commit.test.js`（6.2）、`app/test/resume.test.js`（6.3），以及 1a 的演示夹具 `tools/tests/fixtures/slice-1a/content/`（一个知识点、一个挑战、五道选择题、`shuffle: false`）。这些和向量一起放进任务文件。

期望值全部由 Claude 按本规格手算，写在 `worked` 和 `why` 里（ADR-009 原文第 6 条、事件规格第 9 节）。`tools/tests/test_vectors.py` 在 CI 里检查向量本身：格式对不对；标成接收、重复的事件能不能通过 `schemas/event.schema.json`；另外用一份独立写的 Python 对照实现复核每个期望值，两边对不上就是向量或对照实现有错，要查清楚。这份对照实现**不是**被测代码，也不交给实现 AI。

整合时先确认向量在空实现上失败，再确认在交付的实现上通过。`app/test/commit.test.js`（6.2）也一样。

### 8. 演示部署（整合时 Claude 做）

`pages.yml` 改成：用 `tools/build_release.py` 把 `tools/tests/fixtures/content/` 构建成发布包放进 `release/`（1a 用 `tools/tests/fixtures/slice-1a/content/`，1b 起用 `tools/tests/fixtures/slice-1b/content/`；不改现有的通用夹具），连同 `app/`、`kernel/`、`engine/` 按仓库里的目录结构一起发布，原型仍在根目录。演示地址 `https://deepnorth2077.github.io/Curio/app/`。CI 加一步 `node --test kernel/test/*.test.js engine/test/*.test.js app/test/*.test.js`（不加引号，由 shell 展开成文件名；`node --test <目录>` 在 Node 20 和 22 上行为不同，不用）。

## 测试接缝

| 接缝 | 能发现 | 发现不了 |
| --- | --- | --- |
| `createLog().ingest` + 摄入向量 | 不合格的判断（大小、JSON、数值、信封、动词、payload）、重复和冲突、`true` 和 `1` 不分、`1` 和 `1.0` 误判冲突 | 存储读写 |
| `projectMastery` + 掌握度向量 | 首答计算、5 条合法性规则、放弃和未完成的尝试、多次尝试取最好、乱序重复分批结果一样 | 外壳有没有按规定写事件 |
| `grade` + 判分向量 | 两种分数写法、全角字符、等值分数、误区匹配的顺序、认不出的写法 | 界面显示 |
| `numberOk` + 数值向量 | 小数位数、10^9 和 2^53−1 的边界、`-0`、`1.0` | 别的字段规则 |
| `startQuiz`/`step` | 没存好不前进；每道题都存好作答才产出完成；没存上时 `pending` 不变 | 画面 |
| `createCommitter` + 假存储 | 写库失败、事务中止、提交后关页面，重试或刷新后只有一份事实；串行；序号连续 | 真的 IndexedDB 行为（整合时的冒烟测试） |
| 启动恢复 + 假存储 | 跨发布补写 `abandoned` 用旧 `content`；不重复补 | 锁的真实行为（演示步骤 7、8） |
| 页面（Luka 的演示步骤） | 整条路通不通、刷新后还亮着、触摸能不能做完 | 规则细节（交给上面三个接缝） |

## 演示步骤（Luka 亲手验收）

1a：

1. 平板打开演示地址，看到星图上一颗暗的星「分数的初步认识」。
2. 点它，开始挑战。其中一道故意先答错，再答对。
3. 做完看到「第一次就答对了 4 道，一共 5 道」，星星亮起来。
4. 刷新页面，星星还亮着。
5. 再做一遍：只有 2 道第一次就答对，另外 3 道先答错、再答对，做完。星星仍然亮着（取最好的一次）。
6. 再开始一遍，答到第 3 题时刷新：星星还亮着；指挥中心以后能看到这次是「中途离开」。
7. 同时在两个标签页打开演示地址：后打开的那个只能看，写着「另一个窗口正在用」。
8. 在第一个标签页开始挑战，切到别的 App 几分钟再回来：如果页面提示「请刷新页面」，刷新后能重新开始，星星的状态不变。

写库失败没法在平板上演示，由 6.2 的验收测试保证。

1b（在 iPad 上开一个**无痕标签页**打开演示地址，这样星星从暗的开始；普通标签页里 1a 时已经点亮了）：

1. 点暗的星开始。第 1 题故意答错，点「要个提示」，看到第一条提示；再点一次，看到第二条。
2. 点「看答案」：看到正确答案和一句解释，进入第 2 题。
3. 第 3 题是分数题：上下两个框，下面填 4、上面填 3，答对。
4. 第 4 题是数字题：框后面写着「块」。先填 1，看到提示「1 是分子……」，再填 6，答对。
5. 做完看到「一共 5 道」（看过答案的那道也算在里面）。第一次就答对至少 4 道时，星星亮起来有一小段动画。
6. 在 iPad 的「设置 → 辅助功能 → 动态效果」打开「减弱动态效果」，再做一遍点亮：星星直接变亮，没有动画。
7. 回到普通标签页（1a 时用过的），打开演示地址：星星还亮着，1a 时没做完的那次不影响。

## 不做什么

- **断网可用**（Service Worker）：挪到 #9（发布、预览与回滚），它本来就要处理发布包的缓存。
- 其他动词、私人文字、奖励、航线、错题、导出导入、同步、升级器：后面的切片按需加。
- 真实内容：演示用测试夹具里的「分数的初步认识」。真实知识点试玩合入后再换成 `content/`。
- 讲解、反思、星座缩放、知识地铁、家长端。
- 多窗口同时写事件：本切片只允许一个窗口写（6.3）。以后真要同时写，需要跨窗口分配序号、判断哪个窗口还活着。
- 在 `attempt.started` 里记下题目 ID 快照、让投影核对作答是否完整：以后接收第三方事件或导入时再定。
- `tsc --noEmit` 类型检查。

## 和已有规格的关系

- 内容规格 6.2、6.3：每个 YAML 旁边写一份 `.json`，清单里登记它的路径、哈希、字节数并参与 `content_hash`；构建只读一次文件、先写临时目录；`version`、`engine_min` 写成整数（本 PR 改）。`release/1` 没有升版本：核对过，到 2026-11-08 为止仓库只发布过原型和试玩页（`pages.yml` 只发 `prototype/`），没有任何一份 `release/1` 发布包被部署、分发或保存，唯一的读者是测试夹具，已同步更新。
- 事件规格 6.3：「只有一条 `attempt.started`」和「`conflicts` 里记编号最小的那条规则」已补回（本 PR 改）。
- 事件规格第 9 节表里「`value` 一次是 `true`、一次是 `1` 判为冲突」需要 `sim.*` 动词，本切片不认，所以这里只测「`correct: 1` 不合格」，冲突那条留到加 `sim.*` 的切片。
