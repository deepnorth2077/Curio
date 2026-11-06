# 规格：事件格式、摄入与投影（CURIO-003）

- 状态：提议，等外部审阅
- 依据：ADR-004（事件是事实来源）、ADR-005（宿主是权限边界）、`docs/domain.md`
- 实现任务：CURIO-003a（schema 和夹具）、CURIO-003b（Python 参考内核）、CURIO-003c（浏览器内核）

这份规格把 ADR-004 落成可以直接写代码的格式和规则。凡是和 ADR-004 不一致的地方，第 9 节逐条列出，合入时同步修订 ADR-004 和 `docs/domain.md`。

## 1. ID 和时间

| 对象 | 格式 | 谁生成 |
| --- | --- | --- |
| 事件 | `evt_<ULID>` | 设备 |
| 孩子 | `lrn_<ULID>` | 建档时 |
| 家长 | `cg_<ULID>` | 建档时 |
| 设备 | `dev_<ULID>` | 设备第一次启动时。重装、清空存储后视为新设备，换新 ID，`device_seq` 从 1 重新开始 |
| 尝试 | `att_<ULID>` | 设备 |
| 航线 | `plan_<ULID>` | 设备 |
| 错题 | `rpr_<ULID>` | 设备 |
| 问题 | `qst_<ULID>` | 设备 |
| 导入批次 | `imp_<ULID>` | 导入工具 |
| 同步批次 | `syn_<ULID>` | 后端 |
| 奖励流水 | `rwd_<32 位十六进制>` | 奖励引擎，由唯一键算出（见 6.2） |

- ULID：26 个字符，Crockford Base32 大写（`0-9A-HJKMNP-TV-Z`）。同一毫秒内生成多个时，按 ULID 规范单调递增。
- **时间**一律是 UTC，固定写成 `YYYY-MM-DDTHH:MM:SS.sssZ`（恰好 3 位毫秒，以 `Z` 结尾）。格式固定，按字符串比较就等于按时间比较。
- **本地日期**（航线日期、按天计的奖励）按家庭时区算。规则第 1 版固定为 UTC+8（中国不实行夏令时）；以后换时区要出新版本的规则，不改旧数据。

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
    "content_release": "rel_<64 位十六进制>"
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
| `actor` | ✅ | 谁做的：`{type: learner, id: lrn_…}`、`{type: caregiver, id: cg_…}` 或 `{type: system, id: "sys:<组件名>"}` |
| `verb` | ✅ | 第 3 节的动词之一 |
| `attempt_id` | 视动词 | 做活动过程中的事件必填 |
| `content` | 视动词 | 和内容有关的事件必填，五个字段都要有。`activity_kind` 是 `explain`、`quiz`、`reflection`、`experiment`、`simulation` 之一，投影靠它区分活动类型，不必再去查发布包 |
| `import_batch` | | 由导入工具生成的事件才有，值为 `imp_<ULID>` |
| `payload` | ✅ | 按动词各自的 schema 校验；没有内容时写 `{}` |

其他规则：

- 不允许出现表里以外的字段。`recorded_at` **不在**事件里，它在摄入收据里（第 4.3 节）。
- 整条事件转成规范 JSON 后不超过 16 KiB。规范 JSON 的写法和内容规格相同：键排序、无空白、不转义非 ASCII、UTF-8。
- 自由文字（反思、提问等）不超过 500 个字。

## 3. 动词表

「范围」一列：**尝试**表示必须带 `attempt_id` 和 `content`；**内容**表示必须带 `content`、不带 `attempt_id`；**无**表示两者都不带。「谁」一列是允许的 `actor.type`。

### 3.1 做活动

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `attempt.started` | 尝试 | learner | `{mode: first \| retry \| review}` |
| `attempt.completed` | 尝试 | learner | `{duration_ms}` |
| `attempt.abandoned` | 尝试 | learner、system | `{reason: left \| timeout \| error}` |
| `poe.predicted` | 尝试 | learner | `{choice?, text?}`，至少一个 |
| `poe.explained` | 尝试 | learner | `{choice?, text?}`，至少一个 |
| `sim.adjusted` | 尝试 | learner | `{control, value}`；`value` 是数字、字符串或布尔值 |
| `sim.observed` | 尝试 | learner | `{observable, value}` |
| `item.answered` | 尝试 | learner | `{item_id, response, correct, try, hints_used, misconception?}`；`try` 从 1 开始，同一题第几次作答 |
| `hint.used` | 尝试 | learner | `{item_id?, level}`；`level` 是 1～3 |
| `reflection.written` | 尝试 | learner | `{text}` |

`attempt.completed` **不带分数**。分数一律由投影从 `item.answered` 算出，避免两处数据不一致。

### 3.2 问题本、维修舱

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `question.asked` | 内容或无 | learner | `{question_id, text, attachment_id?}` |
| `question.answered` | 无 | learner、caregiver | `{question_id, text}` |
| `repair.opened` | 内容 | learner、system | `{ticket_id, source: item \| photo, item_id?, misconception?, attachment_id?}` |
| `repair.practiced` | 内容 | learner | `{ticket_id, correct}` |
| `repair.resolved` | 内容 | learner、caregiver | `{ticket_id, reason: fixed \| caregiver}` |

### 3.3 航线（打卡）

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `plan.created` | 无 | learner、caregiver | `{plan_id, plan_date, tasks: [{ref, kind, title?}]}`；`plan_date` 是本地日期 `YYYY-MM-DD`；`kind` 是 `node`（`ref` 为知识点 id）、`free`（`ref` 固定为 `free`）或 `custom`（`ref` 为 `c-<短名>`，必须带 `title`）；1～5 项，`ref` 不重复 |
| `plan.task_done` | 无 | learner、system | `{plan_id, ref, via: manual \| auto}`；`auto` 表示完成活动后自动打勾 |
| `plan.task_undone` | 无 | learner | `{plan_id, ref}` |

### 3.4 奖励

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `reward.goal_set` | 无 | caregiver | `{title, target}`；兑换目标和需要的补给点 |
| `reward.redeem_requested` | 无 | learner | `{goal_event_id}`；指向当时的 `reward.goal_set` |
| `reward.spent` | 无 | caregiver | `{request_event_id, amount}`；家长确认兑换，扣补给点 |
| `reward.adjusted` | 无 | caregiver | `{currency, amount, reason}`；`amount` 是非零整数，可正可负 |
| `reward.revoked` | 无 | caregiver | `{entry_id, reason}`；撤销一笔 `earn` 或 `adjust` 流水 |

### 3.5 数据管理

| 动词 | 范围 | 谁 | payload |
| --- | --- | --- | --- |
| `import.voided` | 无 | caregiver | `{batch_id, reason}`；作废一整批导入 |
| `attachment.erased` | 无 | caregiver | `{attachment_id, reason}`；附件的密钥已销毁 |

### 3.6 不进事件流的东西

契约警告、AI 调用记录、性能数据属于**诊断日志**，单独存放、可以清理，不是学习证据，也不参与投影。格式在 CURIO-005 里定。

### 3.7 模块消息怎么变成事件

活动模块只能发 `docs/activity-contract.md` 里的消息。宿主校验之后，补上信封，换成本表的动词：

| 模块发的 | 宿主记成 |
| --- | --- |
| `event` · `predicted` | `poe.predicted` |
| `event` · `adjusted` | `sim.adjusted` |
| `event` · `observed` | `sim.observed` |
| `event` · `answered` | `item.answered` |
| `request_hint` | `hint.used`（宿主给出提示之后） |
| `note_question` | `question.asked` |
| `complete` | `attempt.completed` |

`attempt.started`、`attempt.abandoned`、`poe.explained` 由宿主自己记，模块不能发。

## 4. 摄入

「摄入」是把一条事件写进存储。设备本地写入和后端接收同步，走的是同一套规则。

### 4.1 唯一约束

存储层建两条唯一约束：`event_id` 唯一；`(device_id, device_seq)` 唯一。

### 4.2 一条事件进来时

按顺序判断：

1. **不合格**：信封或 payload 校验不通过，或者动词不认识 → 放进**隔离区**，不参与投影，在家长端提示。
2. **重复**：`event_id` 已存在，而且两条事件的规范 JSON 完全相同 → 确认收到，什么也不做。
3. **冲突**：`event_id` 已存在但内容不同；或者 `(device_id, device_seq)` 已被另一条事件占用 → 放进隔离区，在家长端提示。不覆盖已有的事件。
4. 以上都不是 → **接收**，写入事件和摄入收据。

隔离区里的事件保留原样，可以导出，用来排查。

### 4.3 摄入收据（ingest-receipt/1）

| 字段 | 说明 |
| --- | --- |
| `event_id` | 对应的事件 |
| `recorded_at` | 写入时的本机时间 |
| `source` | `local`（本机产生）、`sync`（同步收到）、`import`（导入） |
| `batch_id` | `sync` 时必填，是同步批次 `syn_…`；`import` 时必填，是导入批次 `imp_…`；`local` 时不能有 |
| `clock_skew_ms` | `sync` 时必填，其他时候不能有：一批上传时，后端当前时间减去设备报告的当前时间，单位毫秒，整数 |

时钟偏差超过 5 分钟，家长端提示「某台设备的时钟不准」，但不改动任何事件。收据只用于审计和排查，**投影不读收据**，所以收据不需要同步回设备。

### 4.4 同步时检查漏传

后端对每台设备记下「连续收到的最大 `device_seq`」并在回执里返回。设备据此补传缺的部分。中间有空缺的序号时，空缺之后的事件照样接收，只是最大连续序号不前进。具体协议属于 CURIO-008。

## 5. 投影

### 5.1 投影的输入

1. 所有已接收的事件；
2. 去掉带有被 `import.voided` 作废的 `import_batch` 的事件；
3. 用升级器把旧版本事件转成 `event/2`（第 7 节）。

### 5.2 必须满足的性质

- **纯函数**：输出只取决于输入的事件**集合**，以及规则或算法的版本号。不读当前时间、不读随机数、不读收据。
- **和到达顺序无关**：同一个集合，不管以什么顺序、分几批、重复多少次进来，输出完全相同。
- **需要排序时**，用确定性的排序键 `(occurred_at, device_id, device_seq, event_id)`，逐项按字符串比较（`device_seq` 按整数比较）。
- 输出带 `algorithm_version`。

实现可以增量计算，但测试要证明：增量算出的结果，和从头全量算的结果一致。

### 5.3 一次尝试的合法性

把同一 `attempt_id` 的事件按 `device_seq` 排序后，必须满足：只来自一台设备；第一条是 `attempt.started`；最多一条结束事件（`completed` 或 `abandoned`），而且它是最后一条；所有事件的 `content` 相同。不满足的尝试标为「不一致」：事件保留，但不计入掌握度和奖励，在家长端可见。

### 5.4 第一版的投影

**航线（plans/1）**

- 同一个孩子同一个 `plan_date` 有多条 `plan.created` 时，排序键最小的那条是**生效航线**，其余的是**被取代**。
- 某天某个 `ref` 的状态：取这一天**所有**航线（包括被取代的）上这个 `ref` 的 `task_done`、`task_undone` 事件，排序键最大的一条决定它是「完成」还是「未完成」。这就是 ADR-004 说的「被取代航线上完成的任务合并到保留的那一条」。
- 被取代航线上有、生效航线上没有的 `ref`，如果状态是「完成」，作为「在另一台设备上完成」附加显示在生效航线上。

**掌握度（mastery/1）**

每个知识点的状态是下面三种之一：

- `untouched`：没有任何合法、已完成的尝试；
- `explored`：至少有一次合法、已完成的尝试；
- `lit`（点亮）：至少有一次合法、已完成的 `quiz` 尝试，它的**首答正确率** ≥ 0.8，并且这个知识点没有未修好的错题。

首答正确率 = 这次尝试里 `try = 1` 且答对的题目数 ÷ 作答过的不同题目数。用的是所有尝试里最好的那一次。

**错题、问题（repairs/1、questions/1）**

每张错题、每个问题的状态，由它的事件按排序键依次决定：错题是「打开 → 练习中 → 修好」，问题是「已提出 → 已回答」。

## 6. 奖励流水

### 6.1 流水是一种投影

ADR-004 已经规定「奖励余额由事件算出」。这里进一步明确：**流水本身也是从事件算出来的**。每一笔流水都指向引起它的事件，所以每一点能量的来历都查得到；流水表存下来只是缓存，任何时候都能从事件重新算出完全相同的结果。

这样，同步多遍、乱序到达、撤销打卡，都不需要「先发再补扣」，结果自然一致。

### 6.2 流水的格式（reward-entry/1）

| 字段 | 说明 |
| --- | --- |
| `entry_id` | `rwd_` + SHA-256(`learner_id`、`cause_key`、`rule_id`、`currency` 用 `\n` 连接后的 UTF-8 字节) 的前 32 位十六进制 |
| `learner_id` | |
| `currency` | `energy`（能量，只增不花）或 `supply`（补给点，用来兑换） |
| `kind` | `earn`、`spend`、`adjust`、`revoke` |
| `amount` | 整数。`earn` 为正，`spend` 和 `revoke` 为负，`adjust` 非零 |
| `cause_key` | 这笔流水「因为什么」，见 6.3 |
| `cause_event_id` | 引起它的那条事件 |
| `rule_id`、`rule_version` | 由哪条规则、哪个版本算出 |
| `target_entry_id` | 只有 `revoke` 才有：撤销的是哪一笔 |

**唯一键**：`(learner_id, cause_key, rule_id, currency)`。同一个唯一键最多一笔流水。

余额 = 同一货币所有流水 `amount` 之和。

### 6.3 第一版的规则

每条规则有 `rule_id`、`rule_version` 和 `effective_from`（UTC 时间）。对一条触发事件，使用 `effective_from` ≤ 它的 `occurred_at` 的最新版本。所以规则改版只影响生效之后发生的事，旧流水按旧规则算，结果不变。

| 规则 | 触发 | `cause_key` | 产生的流水 |
| --- | --- | --- | --- |
| `task-done` v1 | 航线投影里状态为「完成」的任务 | `task:<plan_date>:<ref>` | 能量 +1、补给点 +1，`cause_event_id` 为决定「完成」的那条事件 |
| `activity-done` v1 | 合法的 `attempt.completed`，活动类型是 `quiz`、`experiment` 或 `simulation` | `act:<本地日期>:<activity_id>` | 能量 +1、补给点 +1。同一天同一活动只奖励一次，`cause_event_id` 为排序键最小的那次完成 |
| `repair-resolved` v1 | `repair.resolved` | `repair:<ticket_id>` | 能量 +1、补给点 +1 |
| `redeem` v1 | `reward.spent` | `redeem:<request_event_id>` | 补给点 −amount。同一个兑换申请只能扣一次 |
| `adjust` v1 | `reward.adjusted` | `evt:<event_id>` | 按 payload |
| `revoke` v1 | `reward.revoked` | `revoke:<entry_id>` | 被撤销那笔的相反数，`target_entry_id` 指向它。目标不存在、或者目标不是 `earn`/`adjust` 时不产生流水 |

几个例子：

- **撤销打卡**：完成 → 撤销，任务最终是「未完成」，`task-done` 不产生流水。再次完成，又会产生。始终不会多发。
- **两台设备同一天各建了航线**，都完成了「分数」这一项：`cause_key` 都是 `task:2026-11-06:math.number.fraction-intro`，只奖励一次。
- **同一份备份导入两次**：事件 `event_id` 相同，第二次全是「重复」，流水不变。

### 6.4 以后加规则时注意

需要汇总一段时间才能判断的规则（例如「一周满勤 5 天奖励 2 点」），如果直接从事件集合算，迟到的事件会让结果在周后还变来变去。这类规则不在第一版里。以后要加，先写 ADR，用「结算事件」把某个时刻的结果固定下来。

## 7. 升级器

- 事件格式只升级 `schema` 的主版本（`event/2` → `event/3`）。动词的 payload 只做向后兼容的改动（加可选字段）；需要不兼容的改动时，就出新的主版本。
- 升级器是纯函数 `upgrade(旧版本事件) → 新版本事件`，逐版串联。存储里的原事件**永远不改**，读出来进投影之前才升级。
- `event/1` 只在原型里用过，从来没有真实孩子的数据，所以**不写** `event/1` → `event/2` 的升级器。原型和旧打卡工具里的数据，由导入工具转换成带 `import_batch` 的 `event/2` 事件（CURIO-006）。
- CURIO-003b 用一个**只在测试里**的假版本 `event/2-test`，证明升级链路可用：存储里的原事件不变，投影看到的是升级后的结果。

## 8. 黄金向量

为了让 Python 参考内核和浏览器内核算出一样的结果，CURIO-003b 产出一组**黄金向量**：`kernel/vectors/<名字>.json`，每个文件包含输入事件、期望的摄入结果和期望的投影输出。浏览器内核（CURIO-003c）必须全部通过。以后任何一边改了算法，向量也跟着更新，两边一起验证。

至少覆盖这些场景：

| 场景 | 要证明的事 |
| --- | --- |
| 正常做完一次挑战 | 掌握度、奖励算对 |
| 同一批事件打乱顺序、重复、分批 | 投影完全相同 |
| 两台设备交错到达 | 投影完全相同 |
| `event_id` 相同但内容不同 | 进隔离区，原事件不变 |
| `(device_id, device_seq)` 被占用 | 进隔离区 |
| 两台设备同一天各建航线 | 排序键最小的生效；任务合并；不重复奖励 |
| 完成 → 撤销 → 再完成 | 最终奖励 1 次 |
| 同一天同一活动做三遍 | 只奖励 1 次 |
| 不一致的尝试 | 不计入掌握度和奖励 |
| 家长撤销一笔、兑换确认两次 | 撤销生效；只扣一次 |
| 作废一批导入 | 那批事件不再影响任何投影 |
| 规则 `effective_from` 前后各一条事件 | 各用各的版本 |

## 9. 和 ADR-004、领域模型的出入

合入本规格时，同步修改这两份文档：

1. **奖励唯一键**：ADR-004 写的是 `(learner_id, cause_event_id, rule_id, currency)`。改为 `(learner_id, cause_key, rule_id, currency)`，`cause_event_id` 保留，用于追溯。原因：只按事件去重，挡不住「两台设备各建一条航线、完成同一项任务」和「同一活动一天做很多遍」这类重复奖励。
2. **流水是投影**：ADR-004 把流水写成独立的只追加记录。改为「从事件确定性算出、可以随时重建」。只追加的仍然是事件；流水每一笔都能追溯到事件，可审计性不变。撤销打卡不再产生 `revoke` 流水，`revoke` 只用于家长撤销。
3. **流水 ID**：`docs/domain.md` 写的是 `rwd_<ULID>`。改为由唯一键算出的哈希，这样不同设备独立算出的流水 ID 相同。
4. **航线**：ADR-004 说「另一条记为被取代」。这里不为此写事件，被取代是投影的结果。原因：写事件就要决定由谁、在什么时候写，两台设备可能都写，反而引入新的冲突。
5. **作废导入**：ADR-004 写的是「指向那一批导入」。这里规定导入的事件在信封里带 `import_batch`，作废时按它过滤，投影不需要读收据。

## 10. 任务拆分

| 任务 | 做什么 | 交付 | 依赖 |
| --- | --- | --- | --- |
| **CURIO-003a** | schema 和夹具 | `schemas/event.schema.json`（改写为 event/2，信封加逐动词 payload）、`schemas/ingest-receipt.schema.json`、`schemas/reward-entry.schema.json`；`tools/tests/fixtures/` 下每个动词至少一个合格样例、一个不合格样例，收据和流水也有样例；校验这些夹具的测试 | 本规格合入 |
| **CURIO-003b** | Python 参考内核 | `kernel/reference/`：ULID、规范 JSON、摄入（SQLite，含唯一约束、隔离区、收据）、排序键、尝试合法性、四个投影、奖励引擎、升级器框架；测试，含随机打乱、重复、分批到达的性质测试；`kernel/vectors/` 黄金向量 | CURIO-003a 合入 |
| **CURIO-003c** | 浏览器内核 | `kernel/js/`：同样的规则，ES 模块、JSDoc 类型、不依赖框架（ADR-008）；通过全部黄金向量 | CURIO-003b 合入 |
