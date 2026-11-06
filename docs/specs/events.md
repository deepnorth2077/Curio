# 规格：事件格式、摄入与投影（CURIO-003）

- 状态：提议，第 3 稿（已按两轮外部审阅修改，见 `docs/reviews/pr-21.md`）
- 依据：ADR-004（事件是事实来源）、ADR-005（宿主是权限边界）、`docs/domain.md`
- 实现任务：CURIO-003a（schema 和夹具），之后按竖切片实现（第 11 节）

这份规格把 ADR-004 落成可以直接写代码的格式和规则。它对 ADR-004、ADR-002、领域模型和活动契约的修订列在第 10 节，ADR-002、ADR-004 的修订以「增补 1」的形式写在原 ADR 文末，原文保留；领域模型和活动契约直接修改。

## 1. ID 和时间

ID 前缀以 `docs/domain.md` 的对象一览为准，这里重列一遍：

| 对象 | 格式 | 谁生成 |
| --- | --- | --- |
| 事件 | `evt_<ULID>` | 设备 |
| 孩子 | `lrn_<ULID>` | 建档时 |
| 家长 | `cg_<ULID>` | 建档时 |
| 设备 | `dev_<ULID>` | 设备第一次启动时。重装、清空存储后视为新设备，换新 ID，`device_seq` 从 1 重新开始 |
| 尝试 | `att_<ULID>` | 设备 |
| 航线 | `plan_<ULID>` | 设备 |
| 错题 | `rep_<ULID>` | 设备 |
| 问题 | `q_<ULID>` | 设备 |
| 私人文字 | `txt_<ULID>` | 设备（第 4 节） |
| 附件 | `blob_<64 位小写十六进制>` | 按内容的 SHA-256 寻址 |
| 导入批次 | `imp_<ULID>` | 导入工具 |
| 同步批次 | `syn_<ULID>` | 后端 |
| 奖励流水 | `rwd_<32 位小写十六进制>` | 奖励引擎，由唯一键算出（第 7.2 节） |

- ULID：26 个字符，Crockford Base32 大写（`0-9A-HJKMNP-TV-Z`），第一个字符只能是 `0`～`7`。同一毫秒内生成多个时，按 ULID 规范单调递增。
- **时间**一律是 UTC，固定写成 `YYYY-MM-DDTHH:MM:SS.sssZ`（恰好 3 位毫秒，以 `Z` 结尾）。格式固定，按字符串比较就等于按时间比较。
- **本地日期**（航线日期、按天计的奖励）按家庭时区算。规则第 1 版固定为 UTC+8（中国不实行夏令时）；以后换时区要出新版本的规则，不改旧数据。
- **设备时钟**：第一版不防作弊。设备时钟错了，事件照样按它记下的时间算；后端发现偏差会在家长端提示（第 5.3 节），由家长用调整、撤销来纠正（第 7.4 节）。

## 2. 事件信封（event/2）

```json
{
  "schema": "event/2",
  "event_id": "evt_01JC4Z8M7X2Q9W3E5R6T7Y8V9K",
  "learner_id": "lrn_01JC4Y…",
  "device_id": "dev_01JC4Y…",
  "device_seq": 42,
  "occurred_at": "2026-11-06T08:30:12.345Z",
  "actor": {"type": "learner", "id": "lrn_01JC4Y…"},
  "verb": "item.answered",
  "attempt_id": "att_01JC4Z…",
  "content": {
    "node_id": "math.number.fraction-intro",
    "activity_id": "act.quiz.fraction-intro-01",
    "activity_kind": "quiz",
    "activity_version": 1,
    "content_release": "rel_<64 位小写十六进制>"
  },
  "payload": {"item_id": "q1", "response": "b", "correct": false, "try": 1, "hints_used": 0, "misconception": "part-vs-rest"}
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema` | ✅ | 固定为 `event/2` |
| `event_id` | ✅ | 见第 1 节 |
| `learner_id` | ✅ | 这件事属于哪个孩子 |
| `device_id`、`device_seq` | ✅ | 在哪台设备上记下的；序号从 1 开始，每条加一，不跳号 |
| `occurred_at` | ✅ | 设备时钟记下的发生时间 |
| `actor` | ✅ | 谁做的：`{type: learner, id: lrn_…}`、`{type: caregiver, id: cg_…}` 或 `{type: system, id: "sys:<组件名>"}`（组件名用小写字母、数字、连字符） |
| `verb` | ✅ | 第 3 节的动词之一 |
| `attempt_id` | 视动词 | 做活动过程中的事件必填 |
| `content` | 视动词 | **活动来源**：这件事发生在哪个活动的哪个版本里。五个字段都必填。`activity_kind` 是 `explain`、`quiz`、`reflection`、`experiment`、`simulation` 之一，投影靠它区分活动类型，不必再去查发布包 |
| `import_batch` | | 由导入工具生成的事件才有，值为 `imp_<ULID>` |
| `payload` | ✅ | 按动词各自的 schema 校验；没有内容时写 `{}` |

其他规则：

- 不允许出现表里以外的字段。`recorded_at` **不在**事件里，它在摄入收据里（第 5.3 节）。
- **孩子或家长写的自由文字不放进事件**，事件里只放 `txt_…`，文字本身存在私人文字里（第 4 节）。事件里剩下的字符串都是 ID、枚举值或很短的作答（`item.answered` 的 `response` 最多 32 个字符）。
- **数值**：JSON 本身不允许 NaN 和 Infinity。其余的数按下面的程序检查，Python 和 JavaScript 都能照做，结果相同：
  1. 把它解析成双精度浮点数 `x`（写成 `1e2`、`100`、`100.0` 都可以，解析后是同一个值）；
  2. `x` 是整数值时：绝对值不超过 2^53−1（9007199254740991）。超过的拒绝（JavaScript 解析超大整数会丢精度，但丢精度后的值仍然超出范围，照样会被拒绝）；
  3. `x` 不是整数值时：绝对值小于 10^9，并且它的**最短十进制表示**小数点后不超过 6 位。最短十进制表示就是 Python 的 `repr(x)`、JavaScript 的 `String(x)` 给出的数字串，两者的数字部分相同、只是指数写法不同，按指数换算出小数位数即可。例如 `1.5e-7` 有 8 位小数，拒绝；`0.125` 有 3 位，接受。
  
  在这个范围内，两种语言解析出的值一一对应，不会因为精度不同而判成两个值。
- **大小**：设备写入时，按自己的序列化方式保证整条事件不超过 15 KiB；摄入时，收到的原始字节超过 16 KiB 就判为不合格。
- **保留原始字节**：存储和转发事件时，一律保留第一次收到的原始字节，任何组件都不重新序列化。需要改写数据的场合（例如导入工具把旧数据转成 event/2）产生的是**新事件**，必须重新满足写入时 15 KiB 的限制。所以中间 1 KiB 的余量只用来吸收不同程序在写入时的差别，不会遇到「中文被转义后变长一倍」的情况。

## 3. 动词表

「范围」一列：**尝试**表示必须带 `attempt_id` 和 `content`；**来源**表示必须带 `content`、不带 `attempt_id`；**无**表示两者都不带；**看来源**的规则写在 payload 一列。「谁」一列是允许的 `actor.type`。

payload 里以 `_text_id` 结尾或叫 `text_id` 的字段，值是 `txt_<ULID>`（第 4 节）。

### 3.1 做活动

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `attempt.started` | 尝试 | learner | `{mode: first \| retry \| review}` |
| `attempt.completed` | 尝试 | learner | `{duration_ms}`，非负整数 |
| `attempt.abandoned` | 尝试 | learner、system | `{reason: left \| timeout \| error}` |
| `poe.predicted` | 尝试 | learner | `{choice?, text_id?}`，至少一个 |
| `poe.explained` | 尝试 | learner | `{choice?, text_id?}`，至少一个 |
| `sim.adjusted` | 尝试 | learner | `{control, value}`；`value` 是数字、字符串（最多 32 个字符）或布尔值 |
| `sim.observed` | 尝试 | learner | `{observable, value}`，`value` 同上 |
| `item.answered` | 尝试 | learner | `{item_id, response, correct, try, hints_used, misconception?}`；`try` 从 1 开始，同一题第几次作答；`hints_used` 非负整数 |
| `hint.used` | 尝试 | learner | `{item_id?, level}`；`level` 是 1～3 |
| `reflection.written` | 尝试 | learner | `{text_id}` |

`attempt.completed` **不带分数**。分数一律由投影从 `item.answered` 算出，避免两处数据不一致。

### 3.2 问题本、维修舱

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `question.asked` | 尝试、来源或无 | learner | `{question_id, text_id, attachment_id?}`。在活动进行中提的问题带 `attempt_id` 和 `content`；在活动页面但没有进行中的尝试时只带 `content`；其他地方提的两者都不带 |
| `question.answered` | 无 | learner、caregiver | `{question_id, text_id}` |
| `repair.opened` | 看来源 | learner、system | `{ticket_id, source, node_id?, item_id?, misconception?, attachment_id?}`。`source: item`（做题时答错产生）：必须带 `content`，必须有 `item_id`，不能有 `node_id`（知识点就是 `content.node_id`）。`source: photo`（拍照录入）：不能带 `content`，必须有 `attachment_id`，`node_id` 可选（拍照时常常还不知道属于哪个知识点）；有 `misconception` 时必须有 `node_id`，否则误区不知道是哪个知识点的 |
| `repair.linked` | 无 | learner、caregiver、system | `{ticket_id, node_id, misconception?}`：给错题补上或改正所属的知识点（例如拍照错题经过诊断之后） |
| `repair.practiced` | 无 | learner | `{ticket_id, correct}` |
| `repair.resolved` | 无 | learner、caregiver | `{ticket_id, reason: fixed \| caregiver}` |

错题属于哪个知识点，由投影从 `repair.opened` 和 `repair.linked` 算出（第 6.4 节），后续的练习、修好事件不再重复写。

### 3.3 航线（打卡）

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `plan.created` | 无 | learner、caregiver | `{plan_id, plan_date, tasks: [{ref, kind, title_text_id?}]}`；`plan_date` 是本地日期 `YYYY-MM-DD`；`kind` 是 `node`（`ref` 为知识点 id）、`free`（`ref` 固定为 `free`）或 `custom`（`ref` 为 `c-<小写字母、数字、连字符>`，必须带 `title_text_id`）；1～5 项，`ref` 不重复 |
| `plan.task_done` | 无 | learner、system | `{plan_id, ref, via: manual \| auto}`；`auto` 表示完成活动后自动打勾 |
| `plan.task_undone` | 无 | learner | `{plan_id, ref}` |

### 3.4 奖励

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `reward.goal_set` | 无 | caregiver | `{title_text_id, target}`；兑换目标和需要的补给点（正整数） |
| `reward.redeem_requested` | 无 | learner | `{goal_event_id}`；指向当时的 `reward.goal_set` |
| `reward.spent` | 无 | caregiver | `{request_event_id}`；家长确认兑换。扣多少补给点，由申请指向的那条 `reward.goal_set` 的 `target` 决定，不由这条事件填写 |
| `reward.adjusted` | 无 | caregiver | `{currency, amount, reason: bonus \| correction \| other, note_text_id?}`；`amount` 是非零整数，可正可负 |
| `reward.revoked` | 无 | caregiver | `{entry_id, reason: mistake \| clock \| other, note_text_id?}`；撤销一笔 `earn` 或 `adjust` 流水 |

### 3.5 数据管理

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `import.voided` | 无 | caregiver | `{batch_id, reason: wrong_learner \| duplicate \| bad_data \| other}`；作废一整批导入 |
| `attachment.erased` | 无 | caregiver | `{attachment_id, reason: requested \| mistake \| other}`；附件的密钥已销毁 |
| `text.erased` | 无 | learner、caregiver | `{text_id, reason: requested \| mistake \| other \| orphan \| lost}`；删除一段私人文字（第 4 节）。`orphan`：没有事件引用的文字；`lost`：文字已经永久找不回来（例如设备丢失） |

### 3.6 不进事件流的东西

契约警告、AI 调用记录、性能数据属于**诊断日志**，单独存放、可以清理，不是学习证据，也不参与投影。诊断日志**不能记私人文字的内容**，只能记 `txt_…`。格式在 CURIO-005 里定。

### 3.7 模块消息怎么变成事件

活动模块只能发 `docs/activity-contract.md` 里的消息。宿主校验之后，补上信封，换成本表的动词：

| 模块发的 | 宿主记成 |
| --- | --- |
| `event` · `predicted` | `poe.predicted` |
| `event` · `adjusted` | `sim.adjusted` |
| `event` · `observed` | `sim.observed` |
| `event` · `answered` | `item.answered` |
| `request_hint` | `hint.used`（宿主给出提示之后） |
| `note_question` | `question.asked`（宿主先把文字存成私人文字） |
| `complete` | `attempt.completed` |

`attempt.started`、`attempt.abandoned`、`poe.explained` 由宿主自己记，模块不能发。

## 4. 私人文字

孩子写的反思、提的问题、预测时写的理由，家长写的备注，都可能是很私人的话。十年后孩子可能想删掉某一段。而事件永远不能删，所以**文字不放进事件**，单独存放，可以真正删除。

### 4.1 私人文字（private-text/1）

| 字段 | 说明 |
| --- | --- |
| `schema` | 固定为 `private-text/1` |
| `text_id` | `txt_<ULID>` |
| `learner_id` | 属于哪个孩子（家长写的备注也记在相关的孩子名下） |
| `created_at` | 写下的时间，格式同 `occurred_at` |
| `text` | 1～500 个字 |

- **先文字，后事件**：设备先写私人文字，再写引用它的事件；同步时两者放在同一批里上传，接收方也先存文字、再存事件。这样中途崩溃时，最坏的情况是「有文字、没有事件」（孤儿文字，第 4.2 节可以处理），而不是「有事件、文字缺失」。
- 同一个 `text_id` 只能对应一段文字。收到同 ID、内容不同的文字，按冲突处理（放进隔离区，第 5.2 节）。
- 事件里**不存**文字的哈希：短文字的哈希可以被逐个猜出来，删了文字、留着哈希，等于没删。

### 4.2 删除

`text.erased` 是一条普通事件，只追加。它的效果是：

1. 收到它的存储，立刻删掉这个 `text_id` 的**所有**副本：主存储里的、**隔离区里同 `text_id` 的冲突副本**，以及从文字派生出来的东西（搜索索引、缓存、界面上的草稿）。设备和后端都是这样。
2. 以后再收到这段文字（例如另一台还没同步的设备上传上来），直接丢弃，不再保存。判断依据就是「存在指向它的 `text.erased`」。
3. 此后生成的导出和备份里都没有这段文字。
4. 引用它的事件原样保留。「孩子在某天完成了一次反思」这个事实还在，只是看不到写了什么。

界面上，一段文字有三种状态：

| 状态 | 条件 | 显示 |
| --- | --- | --- |
| 有 | 存储里有这段文字 | 原文 |
| 已删除 | 存在指向它的 `text.erased` | 「这段文字已删除」 |
| 缺失 | 既没有文字，也没有删除事件 | 「这段文字还没同步过来」 |

导出、恢复时做完整性检查（CURIO-006），两个方向都查：

- **事件在，文字缺失**：同步完成后仍然缺失，在家长端列出。多半是写文字的设备在上传前丢失了。家长确认找不回来时，补发一条 `text.erased`（原因 `lost`），它就从「还没同步过来」变成「已删除」。
- **文字在，没有事件引用**（孤儿文字）：在家长端列出，家长可以删除（原因 `orphan`）。

`text.erased` 可以指向任何 `text_id`，不要求这段文字存在、也不要求有事件引用它。

**能承诺什么，不能承诺什么**：删除覆盖所有在线副本（各设备、后端）和此后生成的导出、备份。**已经生成的旧备份、已经导出到别处的文件，改不了**：旧备份按保留期限到期作废（期限在 CURIO-008 定）；用旧备份恢复时，恢复工具必须先拿到最新的删除事件（从后端或较新的备份）再完成恢复，否则要明确提示「可能恢复出已删除的文字」。界面上的删除确认要把这一点说清楚。

### 4.3 投影不读文字

掌握度、奖励、航线、错题、问题这些投影只读事件，不读私人文字的内容。所以删除文字不会改变任何投影结果，投影仍然只取决于事件集合。

**以后加功能时注意**：任何要读文字内容的功能（例如「自动给反思写摘要」），都会打破这一条，必须先修订本节：说清楚它的结果存在哪里、文字删除后结果怎么处理。

## 5. 摄入

「摄入」是把一条事件（或一段私人文字）写进存储。设备本地写入和后端接收同步，走的是同一套规则。

### 5.1 唯一约束

存储层建三条唯一约束：事件的 `event_id`；事件的 `(device_id, device_seq)`；私人文字的 `text_id`。

### 5.2 一条事件进来时

按顺序判断：

1. **不合格**：超过 16 KiB；信封或 payload 校验不通过；动词不认识 → 放进**隔离区**，不参与投影，在家长端提示。
2. **重复**：`event_id` 已存在，而且两条事件**语义相同** → 确认收到，什么也不做。
3. **冲突**：`event_id` 已存在但语义不同；或者 `(device_id, device_seq)` 已被另一条事件占用 → 放进隔离区，在家长端提示。不覆盖已有的事件。
4. 以上都不是 → **接收**，写入事件和摄入收据。

**语义相同**的判断方法：两边都解析成 JSON 值再比较，不比较原始字节。

- **类型必须相同**：对象只和对象比，数组只和数组比，字符串只和字符串比，数字只和数字比，布尔值只和布尔值比，`null` 只和 `null` 比。特别注意：`true` 和 `1` **不相同**（Python 里 `True == 1` 成立，实现时要先比较类型）。
- 对象按键比较（不看键的顺序），数组按顺序比较，字符串按字符逐个比较（不做 Unicode 规范化），数字按数值比较（`1`、`1.0`、`1e0` 相同）。

这样，同一条事件被不同程序、不同版本序列化，都不会误判为冲突。

私人文字进来时同理：格式不对的放隔离区；同 `text_id` 同内容是重复；同 `text_id` 不同内容是冲突；已有删除事件的直接丢弃（第 4.2 节）；其余接收。

隔离区里的数据保留原样，可以导出，用来排查。

### 5.3 摄入收据（ingest-receipt/1）

| 字段 | 说明 |
| --- | --- |
| `event_id` | 对应的事件 |
| `recorded_at` | 写入时的本机时间 |
| `source` | `local`（本机产生）、`sync`（同步收到）、`import`（导入） |
| `batch_id` | `sync` 时必填，是同步批次 `syn_…`；`import` 时必填，是导入批次 `imp_…`；`local` 时不能有 |
| `clock_skew_ms` | `sync` 时必填，其他时候不能有：一批上传时，后端当前时间减去设备报告的当前时间，单位毫秒，整数 |

时钟偏差超过 5 分钟，家长端提示「某台设备的时钟不准」，但不改动任何事件。收据只用于审计和排查，**投影不读收据**，所以收据不需要同步回设备。

### 5.4 同步时检查漏传

后端对每台设备记下「连续收到的最大 `device_seq`」并在回执里返回。设备据此补传缺的部分。中间有空缺的序号时，空缺之后的事件照样接收，只是最大连续序号不前进。具体协议属于 CURIO-008。

## 6. 投影

### 6.1 投影的输入

1. 所有已接收的事件；
2. 去掉带有被 `import.voided` 作废的 `import_batch` 的事件；
3. 用升级器把旧版本事件转成 `event/2`（第 8 节）。

### 6.2 必须满足的性质

- **纯函数**：输出只取决于输入的事件**集合**，以及规则或算法的版本号。不读当前时间、不读随机数、不读收据、不读私人文字。
- **和到达顺序无关**：同一个集合，不管以什么顺序、分几批、重复多少次进来，输出完全相同。
- **需要排序时**，用确定性的排序键 `(occurred_at, device_id, device_seq, event_id)`：`occurred_at`、`device_id`、`event_id` 按字符串比较（都是 ASCII），`device_seq` 按整数比较。
- **多个候选争同一个位置时**（同一张错题被修好两次、同一个兑换申请被确认两次……），除非规则另有说明，**排序键最小的那个生效**，其余列进投影输出的 `conflicts`，在家长端可见。
- **引用悬空时**（事件指向的航线、错题、问题、申请、目标或流水不在集合里），这条事件不生效，同样列进 `conflicts`。所有投影都按这条处理，家长端能看到每一处没生效的事件。
- 输出带 `algorithm_version`。

实现可以增量计算，但测试要证明：增量算出的结果，和从头全量算的结果一致。

### 6.3 一次尝试的合法性

把同一 `attempt_id` 的事件按 `device_seq` 排序后，必须全部满足：

1. 来自同一台设备、同一个孩子（`device_id`、`learner_id` 都相同）；
2. `actor` 是这个孩子本人；只有 `attempt.abandoned` 允许 `system`；
3. 所有事件的 `content` 完全相同；
4. 第一条是 `attempt.started`；最多一条结束事件（`completed` 或 `abandoned`），而且它是最后一条；
5. 同一道题（同一 `item_id`）的 `item.answered`，`try` 恰好是 1、2、3……，按 `device_seq` 递增，不重复、不跳号。

任何一条不满足，这次尝试标为「不一致」：事件保留，但不计入掌握度和奖励，列进 `conflicts`。

### 6.4 第一版的投影

**航线（plans/1）**

- 同一个孩子同一个 `plan_date` 有多条 `plan.created` 时，排序键最小的那条是**生效航线**，其余的是**被取代**。
- 某天某个 `ref` 的状态：取这一天**所有**航线（包括被取代的）上这个 `ref` 的 `task_done`、`task_undone` 事件，排序键**最大**的一条决定它是「完成」还是「未完成」。这就是 ADR-004 说的「被取代航线上完成的任务合并到保留的那一条」。
- 被取代航线上有、生效航线上没有的 `ref`，如果状态是「完成」，作为「在另一台设备上完成」附加显示在生效航线上。
- 指向不存在的航线、或者航线上没有的 `ref` 的打卡事件，不生效，列进 `conflicts`。

**掌握度（mastery/1）**

每个知识点的状态是下面三种之一：

- `untouched`：没有任何合法、已完成的尝试；
- `explored`：至少有一次合法、已完成的尝试；
- `lit`（点亮）：至少有一次合法、已完成的 `quiz` 尝试，它的**首答正确率** ≥ 0.8，并且这个知识点没有未修好的错题。

首答正确率 = 这次尝试里，`try = 1` 的那条 `item.answered` 答对的题目数 ÷ 这次尝试里作答过的不同题目数。合法性第 5 条保证每道题恰好有一条 `try = 1`，所以比例在 0～1 之间。取所有尝试里最好的那一次。

**错题（repairs/1）**

- 错题所属的知识点：`repair.opened` 里的知识点（`source: item` 时是 `content.node_id`，`source: photo` 时是 payload 的 `node_id`，可能没有），被排序键最大的那条 `repair.linked` 覆盖。还没有知识点的错题，显示在维修舱的「待诊断」里，不影响任何知识点的点亮。
- 状态：只有 `opened` 时是「待修」；有 `practiced` 后是「复练中」；有 `resolved` 后是「已修好」，之后的事件不再改变状态。
- 同一张错题有多条 `repair.opened` 时，排序键最小的生效；多条 `repair.resolved` 时，也是排序键最小的生效。
- 没有 `repair.opened` 的 `ticket_id` 上的事件，不生效，列进 `conflicts`。

**问题（questions/1）**

有 `question.answered` 就是「已回答」，否则是「已提出」。同一个 `question_id` 有多条 `question.asked` 时，排序键最小的生效；没有 `question.asked` 的 `question_id` 上的回答，不生效，列进 `conflicts`。

## 7. 奖励流水

### 7.1 流水是一种投影

ADR-004 已经规定「奖励余额由事件算出」。这里进一步明确：**流水本身也是从事件算出来的**。每一笔流水都指向引起它的事件，所以每一点能量的来历都查得到；流水表存下来只是缓存，任何时候都能从事件重新算出完全相同的结果。

这样，同步多遍、乱序到达、撤销打卡，都不需要「先发再补扣」，结果自然一致。

### 7.2 流水的格式（reward-entry/1）

| 字段 | 说明 |
| --- | --- |
| `entry_id` | `rwd_` + SHA-256(`learner_id`、`cause_key`、`rule_id`、`currency` 用 `\n` 连接后的 UTF-8 字节) 的前 32 位小写十六进制 |
| `learner_id` | |
| `currency` | `energy`（能量，只增不花）或 `supply`（补给点，用来兑换） |
| `kind` | `earn`、`spend`、`adjust`、`revoke` |
| `amount` | 整数。`earn` 为正，`spend` 和 `revoke` 为负，`adjust` 非零 |
| `cause_key` | 这笔流水「因为什么」，见 7.3 |
| `cause_event_id` | 引起它的那条事件 |
| `rule_id`、`rule_version` | 由哪条规则、哪个版本算出 |
| `target_entry_id` | 只有 `revoke` 才有，而且必须有：撤销的是哪一笔 |

**唯一键**：`(learner_id, cause_key, rule_id, currency)`。同一个唯一键最多一笔流水；有多个候选事件时，按每条规则写明的方法选一条（第 7.3 节）。

余额 = 同一货币所有流水 `amount` 之和。余额**可以是负数**（例如两台设备离线时各自申请了兑换，家长都确认了）：确认兑换是现实里已经发生的事，照记不误；余额为负时在家长端提示。

### 7.3 第一版的规则

每条规则有 `rule_id`、`rule_version` 和 `effective_from`（UTC 时间）。同一条规则的各个版本，`effective_from` 互不相同。对一条触发事件，使用 `effective_from` ≤ 它的 `occurred_at` 的最新版本；早于所有版本的事件不产生流水。所以规则改版只影响生效之后发生的事，旧流水按旧规则算，结果不变。

| 规则 | 触发 | `cause_key` | 选哪条触发事件 | 产生的流水 |
| --- | --- | --- | --- | --- |
| `task-done` v1 | 航线投影里状态为「完成」的任务 | `task:<plan_date>:<ref>` | 决定「完成」的那条事件（排序键最大的打卡事件） | 能量 +1、补给点 +1 |
| `activity-done` v1 | 合法的 `attempt.completed`，活动类型是 `quiz`、`experiment` 或 `simulation` | `act:<本地日期>:<activity_id>` | 排序键最小的 | 能量 +1、补给点 +1。同一天同一活动只奖励一次 |
| `repair-resolved` v1 | 生效的 `repair.resolved` | `repair:<ticket_id>` | 排序键最小的 | 能量 +1、补给点 +1 |
| `redeem` v1 | `reward.spent`，它指向的申请和目标都在事件集合里（否则列进 `conflicts`） | `redeem:<request_event_id>` | 排序键最小的 | 补给点 −（目标的 `target`）。同一个申请只扣一次 |
| `adjust` v1 | `reward.adjusted` | `evt:<event_id>` | 只有一条 | 按 payload |
| `revoke` v1 | `reward.revoked` | `revoke:<entry_id>` | 排序键最小的 | 被撤销那笔的相反数，`target_entry_id` 指向它。目标不存在、或者目标不是 `earn`/`adjust` 时不产生流水，列进 `conflicts` |

没被选中的候选事件列进 `conflicts`。`revoke` 只能指向 `earn` 和 `adjust`，不会指向另一笔 `revoke`，所以不会出现循环。

几个例子：

- **撤销打卡**：完成 → 撤销，任务最终是「未完成」，`task-done` 不产生流水。再次完成，又会产生。始终不会多发。
- **两台设备同一天各建了航线**，都完成了「分数」这一项：`cause_key` 都是 `task:2026-11-06:math.number.fraction-intro`，只奖励一次。
- **同一个兑换申请被确认两次**：只扣一次，第二次确认列进 `conflicts`。
- **被撤销的那笔后来自己消失了**（例如家长撤销了一次打卡奖励，之后孩子又把那次打卡撤销了）：目标不存在，撤销也不产生流水，余额不会被多扣；这条撤销列进 `conflicts`。
- **同一份备份导入两次**：事件 `event_id` 相同，第二次全是「重复」，流水不变。

### 7.4 设备时钟和奖励

`activity-done` 按本地日期去重，规则版本按 `occurred_at` 选择，都依赖设备时钟。设备日期错了，同一活动可能被算成两天、各奖励一次。第一版接受这一点：这不是防作弊系统，后端会提示时钟偏差，家长用 `reward.revoked`（原因 `clock`）撤销多出来的奖励即可。如果以后真的出现问题，再写 ADR 加防护。

### 7.5 以后加规则时注意

需要汇总一段时间才能判断的规则（例如「一周满勤 5 天奖励 2 点」），如果直接从事件集合算，迟到的事件会让结果在周后还变来变去。这类规则不在第一版里。以后要加，先写 ADR，用「结算事件」把某个时刻的结果固定下来。

## 8. 升级器

- 事件格式只升级 `schema` 的主版本（`event/2` → `event/3`）。动词的 payload 只做向后兼容的改动（加可选字段）；需要不兼容的改动时，就出新的主版本。
- 升级器是纯函数 `upgrade(旧版本事件) → 新版本事件`，逐版串联。存储里的原事件**永远不改**，读出来进投影之前才升级。
- `event/1` 只在原型里用过，从来没有真实孩子的数据，所以**不写** `event/1` → `event/2` 的升级器。原型和旧打卡工具里的数据，由导入工具转换成带 `import_batch` 的 `event/2` 事件（CURIO-006）。
- 第一个用到升级器的切片，用一个**只在测试里**的假版本 `event/2-test`，证明升级链路可用：存储里的原事件不变，投影看到的是升级后的结果。

## 9. 黄金向量

内核的规则用一组**黄金向量**来验收。**期望输出必须来自独立来源**（ADR-009 第 6 条）：由 Claude 按本规格手算，每条写明手算依据，在派发切片之前写进任务；不能先让内核跑出结果，再把结果存成期望值，那样内核有错，向量也跟着错。整合时先确认向量在旧代码上失败，再确认在新代码上通过。向量存为 `kernel/vectors/<名字>.json`，每个文件包含输入的事件和私人文字、期望的摄入结果、期望的投影输出（含 `conflicts`）和期望能看到的文字。浏览器内核必须全部通过；以后写 Python 版（做同步时）也必须全部通过。改算法时先改向量，再改代码。

至少覆盖这些场景：

| 场景 | 要证明的事 |
| --- | --- |
| 正常做完一次挑战 | 掌握度、奖励算对 |
| 同一批事件打乱顺序、重复、分批 | 投影完全相同 |
| 两台设备交错到达 | 投影完全相同 |
| `event_id` 相同但内容不同 | 进隔离区，原事件不变 |
| 同一条事件，数字写成 `1` 和 `1.0` | 判为重复，不是冲突 |
| 同一条事件，`value` 一次是 `true`、一次是 `1` | 判为冲突，不是重复 |
| 整数超过 2^53−1；小数有 7 位 | 不合格 |
| `(device_id, device_seq)` 被占用 | 进隔离区 |
| 两台设备同一天各建航线 | 排序键最小的生效；任务合并；不重复奖励 |
| 完成 → 撤销 → 再完成 | 最终奖励 1 次 |
| 同一天同一活动做三遍 | 只奖励 1 次 |
| 同一题两条 `try = 1`；`try` 跳号 | 尝试判为不一致，不计入掌握度和奖励 |
| 一次尝试里混进另一个孩子或另一台设备的事件 | 尝试判为不一致 |
| 同一兑换申请确认两次 | 只扣一次，另一次进 `conflicts` |
| 同一错题修好两次 | 只奖励一次 |
| 家长撤销一笔，那笔后来消失 | 撤销也不产生流水 |
| 拍照错题：先没有知识点，再补上 | 先在「待诊断」，补上后影响该知识点的点亮 |
| 写反思 → 同步 → 删除文字 → 全部重放 | 两台设备都看不到原文；「完成了一次反思」还在；投影不变 |
| 删除之后，另一台设备又上传这段文字 | 被丢弃 |
| 同一 `text_id` 的冲突副本在隔离区里，然后删除 | 隔离区里的副本也消失 |
| 文字永久缺失，家长补发删除 | 状态从「缺失」变成「已删除」 |
| 作废一批导入 | 那批事件不再影响任何投影 |
| 规则 `effective_from` 前后各一条事件 | 各用各的版本 |
| 两台设备各自兑换，余额变负 | 余额为负，有提示 |

## 10. 对 ADR-004、ADR-002、领域模型和活动契约的修订

ADR-002、ADR-004 的修订以「增补 1」的形式写在原 ADR 文末（原文保留），领域模型和活动契约直接修改：

1. **私人文字可以删除**（ADR-004 第 1 节）：「只追加」的例外从两种变成三种，加上「删除私人文字」。自由文字不再写进事件（本规格第 4 节）。
2. **奖励唯一键**（ADR-004 第 3、5 节）：从 `(learner_id, cause_event_id, rule_id, currency)` 改为 `(learner_id, cause_key, rule_id, currency)`，`cause_event_id` 保留，用于追溯。原因：只按事件去重，挡不住「两台设备各建一条航线、完成同一项任务」和「同一活动一天做很多遍」这类重复奖励。
3. **流水是投影**（ADR-004 第 5 节）：流水从事件确定性算出、可以随时重建。只追加的仍然是事件；流水每一笔都能追溯到事件，可审计性不变。撤销打卡不再产生 `revoke` 流水，`revoke` 只用于家长撤销。
4. **流水 ID**（领域模型）：从 `rwd_<ULID>` 改为由唯一键算出的哈希，这样不同设备独立算出的流水 ID 相同。
5. **航线被取代不写事件**（ADR-004 第 7 节）：被取代是投影的结果。写事件就要决定由谁、在什么时候写，两台设备可能都写，反而引入新的冲突。
6. **作废导入**（ADR-004 第 1 节）：导入的事件在信封里带 `import_batch`，作废时按它过滤，投影不需要读收据。
7. **新对象 PrivateText**（领域模型）：`txt_<ULID>`。
8. **提示阶梯不是活动类型**（ADR-002）：它是每道题都有的能力，活动类型只有讲解、挑战、反思三种。
9. **航线唯一性在投影层**（ADR-004 第 3 节）：原来列为存储层唯一约束。改为两台设备各建的航线都被接收，由投影决定哪条生效；否则第二台设备的航线会被拒收，上面完成的任务不算数。存储层唯一约束改为：`event_id`、`(device_id, device_seq)`、`text_id`。
10. **信封字段**（ADR-004 第 2 节）：同步成 event/2 的实际字段。
11. **接受时钟风险**（ADR-004 第 6 节）：第 7.4 节的取舍写进 ADR，作为长期立场。
12. **问题没有「已归档」状态**（领域模型）：只有「已提出」「已回答」，需要时再加动词。
13. **航线的组成**（领域模型）：「2 个主线加 1 个自由探索」是外壳的默认安排，内核只要求 1～5 项。
14. **`complete` 的分数只用于诊断**（活动契约）：宿主不把它记进事件。

## 11. 任务拆分

按竖切片重排（Luka 2026-11-06 确认，见 #13 和 ADR-009）。原来的 CURIO-003b（Python 参考内核）推迟到做同步时，CURIO-003c（浏览器内核）拆进各条竖切片。

| 任务 | 做什么 | 交付 | 依赖 |
| --- | --- | --- | --- |
| **CURIO-003a** | schema 和夹具 | `schemas/event.schema.json`（改写为 event/2，信封加逐动词 payload）、`schemas/ingest-receipt.schema.json`、`schemas/reward-entry.schema.json`、`schemas/private-text.schema.json`；`tools/tests/fixtures/` 下每个动词至少一个合格样例、一个不合格样例，收据、流水、私人文字也有样例；校验这些夹具的测试 | 本规格合入 |
| **竖切片 1～6**（#24～#28、#8） | 浏览器内核随各条切片逐步实现：每条切片只实现它用到的那部分规则（例如竖切片 1 只做摄入和掌握度，竖切片 3 加上航线和奖励），并带上 Claude 手算的相应黄金向量 | `kernel/js/`：ES 模块、JSDoc 类型、不依赖框架（ADR-008）；测试在 CI 里自动跑 | 见各 issue |
| **CURIO-008**（#11） | Python 参考内核，作为后端的事件存储和投影 | `kernel/reference/`：同样的规则，通过全部黄金向量 | 做同步时 |
