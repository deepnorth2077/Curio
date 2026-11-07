# 规格：竖切片 1 · 分数挑战点亮一颗星（#24）

- 状态：提议，第 1 稿（等外部审阅）
- 依据：内容规格（`docs/specs/content.md` 3.3、3.4、6.3）、事件规格（`docs/specs/events.md` 第 2、5、6、9 节）、ADR-001（内核与外壳）、ADR-003（发布不可变）、ADR-004（事件是事实来源）、ADR-008（不打包）、ADR-009（竖切片、验收用例先行）
- 实现任务：CURIO-SL1（#24），一份交付包

## 问题

内容格式、事件格式、发布构建器都有了，但还没有一个页面真正把它们串起来：孩子做完一次挑战，没有任何地方记下这件事，星星也不会亮。后面的切片（讲解、航线、维修舱、导出）都要建在「事件写进去、掌握度算出来」这条路上，这条路得先打通一次。

## 方案

一个独立的页面（不是原型）：打开后看到星图上一颗暗着的星「分数的初步认识」。点它，做一组分数挑战，逐题作答，可以看提示、答错可以再答。做完看到「第一次就答对了几道」。首答正确率达到 0.8，星星亮起来。刷新页面，星星还亮着，因为它是从存下来的事件重新算出来的。

内容来自发布包（构建器生成），每次作答都记成 event/2 事件存进浏览器；掌握度只从事件算。

## 用户故事

1. 作为舰长，我想要点一颗星就开始挑战，这样不用找入口。
2. 作为舰长，我想要答错了能看提示、再答一次，这样卡住时不会只能放弃。
3. 作为舰长，我想要做完时看到自己答对了几道、星星亮起来，这样知道自己做到了。
4. 作为舰长，我想要刷新、关掉再打开以后星星还亮着，这样做过的事不会丢。
5. 作为家长，我想要每次作答都记下当时的内容版本，这样以后能查到孩子做的是哪一版题。
6. 作为维护者，我想要摄入、掌握度、判分各有一个能单独测试的接口，并且有手算的黄金向量，这样实现 AI 交来的代码我能在接缝上验证，以后换算法、写 Python 版也有同一把尺子。
7. 作为维护者，我想要页面用原生 ES 模块、不打包，这样 Luka 拷贝文件就能部署。

## 实现上的决定

### 1. 目录和模块

```
kernel/js/        内核：只认通用对象，不知道星图、挑战长什么样（ADR-001）
  validate.js     信封和 payload 校验（本切片支持的 5 个动词）、数值规则
  log.js          createLog()：摄入、去重、冲突、隔离区
  mastery.js      projectMastery(events)：尝试合法性 + 掌握度
  ulid.js         ULID 生成（单调递增）
kernel/test/      node:test 测试，含黄金向量的执行器
kernel/vectors/   黄金向量（Claude 手算，本 PR 提交）
engine/js/
  grade.js        grade(answer, response)：判分
  quiz.js         把一个结构化挑战画出来、处理作答和提示，产出要写的事件
engine/test/      node:test 测试
engine/vectors/   grading.json：判分向量（Claude 手算，本 PR 提交）
app/
  index.html      页面外壳：星图（只有发布包里的星）、挑战、结果
  app.js          启动、读发布包、调用内核和引擎
  store.js        IndexedDB 存取（事件原始文字、收据、设备信息）
```

- 判分属于活动引擎，不放进内核（ADR-001）：内核只看事件里记下的 `correct`。
- 全部是浏览器原生 ES 模块，用 JSDoc 写类型，不引入任何依赖（ADR-008）。测试用 Node 自带的 `node --test`（Node 20 以上），不装包。`tsc --noEmit` 类型检查以后再加。
- 内核和引擎的模块**不碰** DOM、存储、时间和随机数，所以能在 Node 里直接测。读写 IndexedDB、取当前时间、生成 ULID 都在外壳里做，结果作为参数传进去。

### 2. 读发布包

浏览器读不了 YAML，所以构建器在每个 YAML 旁边多写一份同名加 `.json` 的文件（内容规格 6.3，本 PR 一起改）。外壳：

1. 读 `release/release.json`；`engine_min` 大于 1 时不往下走，显示「需要更新」。
2. 按清单读每个知识点和活动的 `.yaml.json`。
3. 星图只画清单里的知识点；点一颗星，列出它被收录的 `quiz` 活动，这一版只有一个，直接进入。

### 3. 摄入（`kernel/js/log.js`）

```js
const log = createLog();          // 空的内存日志
log.ingest(rawText)               // → {result, reason?, detail?}
log.events()                      // → 已接收的事件（解析后的对象），按接收顺序
log.raw()                         // → 已接收事件的原始文字，按接收顺序
log.quarantined()                 // → [{raw, reason, detail}]
```

- `result` 是 `accepted`（接收）、`duplicate`（重复）、`quarantined`（隔离）之一；隔离时 `reason` 是 `invalid`（不合格）或 `conflict`（冲突）。`detail` 是给人看的一句话，测试不比较它。
- 外壳启动时把存下来的原始文字按原来的顺序重新 `ingest` 一遍，就恢复出同样的日志。

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
| `item.answered` | learner | `{item_id, response, correct, try, hints_used, misconception?}`：`item_id` 字符串；`response` 字符串，最多 32 个字符；`correct` 布尔值；`try` 不小于 1 的整数；`hints_used` 非负整数；`misconception` 字符串 |
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

**注意**：内核不读发布包，所以不知道挑战一共几道题，首答正确率的分母是「作答过的题数」。外壳必须等每道题都有结果（答对或看了答案）才写 `attempt.completed`，否则答 1 道就完成会被算成 1/1。

### 5. 判分（`engine/js/grade.js`）

```js
grade(answer, response)   // answer：活动文件里的 answer 对象；response：孩子的作答（字符串）
// → {correct: true|false, misconception: <误区 id> | null}
```

先把 `response` 规整：去掉首尾空白；全角数字 `０`～`９` 换成半角；全角斜杠 `／` 换成 `/`；全角小数点 `．` 换成 `.`。

- **选择题**：`response` 是选项 `id`。是正确选项 → 对；是错误选项 → 错，误区是这个选项的 `misconception`（没有就是 `null`）；不是任何选项的 `id` → 错，`null`。
- **数字题**：`response` 必须整个匹配 `-?[0-9]+(\.[0-9]+)?`，否则错、`null`。解析成数 `x`。`|x − value| ≤ tolerance` → 对。否则按顺序看 `common_wrong`，第一个满足 `|x − 它的 value| ≤ tolerance` 的，误区是它的；都不满足 → `null`。`tolerance` 没写时是 0。
- **分数题**：`response` 必须整个匹配 `a/b`（斜杠两边可以有空格）或 `b分之a`（「分之」两边可以有空格），`a`、`b` 都是 1～6 位半角数字；否则错、`null`。按整数解析，`b` 是 0 时错、`null`。
  - `accept_equivalent` 为假：`a`、`b` 分别等于 `numerator`、`denominator` → 对（`01/04` 也对，按整数比）。
  - `accept_equivalent` 为真：`a × denominator = numerator × b` → 对（整数相乘，不用小数）。
  - 不对时，按顺序看 `common_wrong`，用和上面**同样的方式**（同一个 `accept_equivalent`）比，第一个匹配的误区就是结果；都不匹配 → `null`。
  - 中文数字（「四分之一」）不认，判错。界面给分数题配上下两个数字框，拼成 `a/b` 交给 `grade`，孩子不用自己打斜杠。
- 正确时 `misconception` 一律是 `null`。

### 6. 外壳的行为（`app/`）

- **第一次打开**：生成 `lrn_`、`dev_` 两个 ULID，存进 IndexedDB。以后一直用它们。清空浏览器存储就是新设备（事件规格第 1 节）。
- **写事件**：外壳组装 event/2 信封（`device_seq` 每条加一、`occurred_at` 取当前 UTC 时间、`content_release` 是发布包的 `release_id`、`activity_version` 是活动的 `version`），把 `JSON.stringify` 的结果交给 `log.ingest`；结果是接收时，把原始文字和收据（`{event_id, recorded_at, source: "local"}`）一起写进 IndexedDB。写库失败时提示「没存上」，不假装成功。
- **开始一次挑战**：写 `attempt.started`，`mode` 是 `first`（这台设备上这个活动从没完成过）或 `retry`。题目顺序按活动的 `shuffle` 决定。
- **作答**：选择题点选项；数字题一个数字框；分数题上下两个数字框。点「好了」后调用 `grade`，写 `item.answered`（`try` 是这道题第几次作答，`hints_used` 是这道题已经看过几条提示，`response` 是交给 `grade` 的那个字符串，答错并且有误区时写上 `misconception`）。
  - 答对：显示 `feedback.correct`（没有就用默认的话），进入下一题。
  - 答错：显示这个错误选项或 `common_wrong` 的 `feedback`，没有就用 `feedback.wrong` 或默认的话；可以再答。
  - 「要个提示」：一次给一级，写 `hint.used`（`item_id` 和 `level`）。
  - 提示用完还没答对时，出现「看答案」：显示正确答案，进入下一题。看答案不写事件。
- **完成**：每道题都答对了或看过答案，写 `attempt.completed`（`duration_ms` 是从开始到现在的毫秒数），然后显示「第一次就答对了 X 道，一共 Y 道」，并重新算掌握度。星星从暗变亮时有一个克制的点亮效果（尊重 `prefers-reduced-motion`）。
- **中途离开**：下次打开时，这台设备上还没结束的尝试，补写一条 `attempt.abandoned`（`reason: left`，`actor` 是 `{type: system, id: "sys:shell"}`）。
- **刷新**：启动时把 IndexedDB 里的原始文字按顺序重新摄入，再算掌握度，所以星星的亮暗只由事件决定。
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
- **执行器**（`kernel/test/vectors.test.js`）：新建 `createLog()`，按顺序摄入每一项，逐项比较结果；再对 `log.events()` 调用 `projectMastery`，和 `mastery` 深比较。`order_free` 为真的向量还要做 20 次：用固定种子把全部输入打乱，每项随机重复 1～3 次，确认没有任何一项被隔离、投影和 `mastery` 完全相同。

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

**判分**：`engine/vectors/grading.json`，`{answers: {<名字>: answer 对象}, cases: [{answer, response, expect: {correct, misconception}, why}]}`。执行器逐条调用 `grade` 比较。

期望值全部由 Claude 按本规格手算，写在 `worked` 和 `why` 里（ADR-009 第 6 条、事件规格第 9 节）。`tools/tests/test_vectors.py` 在 CI 里检查向量本身：格式对不对；标成接收、重复的事件能不能通过 `schemas/event.schema.json`；另外用一份独立写的 Python 对照实现复核每个期望值，两边对不上就是向量或对照实现有错，要查清楚。这份对照实现**不是**被测代码，也不交给实现 AI。

整合时先确认向量在空实现上失败，再确认在交付的实现上通过。

### 8. 演示部署（整合时 Claude 做）

`pages.yml` 改成：用 `tools/build_release.py` 把 `tools/tests/fixtures/content/` 构建成发布包放进 `release/`，连同 `app/`、`kernel/`、`engine/` 按仓库里的目录结构一起发布，原型仍在根目录。演示地址 `https://deepnorth2077.github.io/Curio/app/`。CI 加一步 `node --test kernel engine`。

## 测试接缝

| 接缝 | 能发现 | 发现不了 |
| --- | --- | --- |
| `createLog().ingest` + 摄入向量 | 不合格的判断（大小、JSON、数值、信封、动词、payload）、重复和冲突、`true` 和 `1` 不分、`1` 和 `1.0` 误判冲突 | 存储读写 |
| `projectMastery` + 掌握度向量 | 首答计算、5 条合法性规则、放弃和未完成的尝试、多次尝试取最好、乱序重复分批结果一样 | 外壳有没有按规定写事件 |
| `grade` + 判分向量 | 两种分数写法、全角字符、等值分数、误区匹配的顺序、认不出的写法 | 界面显示 |
| 页面（Luka 的演示步骤） | 整条路通不通、刷新后还亮着、触摸能不能做完 | 规则细节（交给上面三个接缝） |

## 演示步骤（Luka 亲手验收）

1. 平板打开演示地址，看到星图上一颗暗的星「分数的初步认识」。
2. 点它，开始挑战。其中一道故意先答错，点「要个提示」，再答对。
3. 做完看到「第一次就答对了 4 道，一共 5 道」，星星亮起来。
4. 刷新页面，星星还亮着。
5. 再做一遍，只答对 2 道：星星仍然亮着（取最好的一次）。

## 不做什么

- **断网可用**（Service Worker）：挪到 #9（发布、预览与回滚），它本来就要处理发布包的缓存。
- 其他动词、私人文字、奖励、航线、错题、导出导入、同步、升级器：后面的切片按需加。
- 真实内容：演示用测试夹具里的「分数的初步认识」。真实知识点试玩合入后再换成 `content/`。
- 讲解、反思、星座缩放、知识地铁、家长端。
- `tsc --noEmit` 类型检查。

## 和已有规格的关系

- 内容规格 6.3 加上「每个 YAML 旁边写一份 `.json`」（本 PR 改）。
- 事件规格 6.3 第 4 条在本切片里说得更完整（只有一条 `attempt.started`）；投影输出 `conflicts` 里的 `rule` 取编号最小的那条。审阅通过后，把这两点补回事件规格 6.3。
- 事件规格第 9 节表里「`value` 一次是 `true`、一次是 `1` 判为冲突」需要 `sim.*` 动词，本切片不认，所以这里只测「`correct: 1` 不合格」，冲突那条留到加 `sim.*` 的切片。
