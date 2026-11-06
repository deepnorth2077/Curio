---
task: curio-003a
issue: 18
version: v1
---

# 任务：为「好奇号」的学习事件写 JSON Schema 和夹具

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。网站运行在平板、电脑和手机上，可以离线使用，联网后多台设备之间同步。

孩子在平台上做的每一件事（答了一道题、调了一下实验的旋钮、完成了一项打卡任务）都记成一条**事件**。事件只追加、不修改，是唯一的事实来源：掌握度、星球点亮、能量和补给点余额，全部从事件算出来。这套数据要用十年，还要支持多设备离线、重复同步、乱序到达，所以事件格式必须非常严格。

你的任务是把下面「事件规格」里定义的格式写成 JSON Schema，并为每个动词准备合格和不合格的样例，再写测试证明 schema 既放行合格的事件，也拦得住不合格的事件。摄入、投影、奖励的**代码**不在本任务里，后面的任务会做。

## 你的角色

严谨的数据格式工程师，熟悉 JSON Schema 2020-12 和 Python 的 `jsonschema` 库。

## 你需要的资料

### 1. 事件规格（唯一依据，不要改动）

{{embed: docs/specs/events.md}}

### 2. 现有的旧版事件 schema（event/1，只在原型里用过，你要把它整个改写成 event/2）

{{embed: schemas/event.schema.json}}

## 要交付的文件

1. `schemas/event.schema.json`：整个改写为 event/2（规格第 1～3 节）。`$id` 保持不变，`title` 改为 `event/2 · 学习事件`。
2. `schemas/ingest-receipt.schema.json`：摄入收据（规格第 4.3 节）。
3. `schemas/reward-entry.schema.json`：奖励流水（规格第 6.2 节）。
4. 合格样例：`tools/tests/fixtures/events/valid/<动词>.json`，规格第 3 节的**每个动词至少一个**，文件名就是动词（例如 `item.answered.json`）；同一个动词要多个时，加后缀 `item.answered-2.json`。收据和流水的合格样例分开放：`tools/tests/fixtures/receipts/` 下至少有 `local.json`、`sync.json`、`import.json`；`tools/tests/fixtures/rewards/` 下 `earn`、`spend`、`adjust`、`revoke` 各至少一个（例如 `earn.json`）。
5. 不合格样例：`tools/tests/fixtures/invalid/events/<名字>.json`，格式见下面「测试怎么写」。
6. `tools/tests/test_event_schemas.py`：测试。

## schema 要表达的规则

规格里能在**单条记录内部**检查的规则，都要写进 schema：

- 信封：必填字段；不允许多余字段；`schema` 固定为 `event/2`。
- ID 格式：`evt_`、`lrn_`、`dev_`、`att_`、`plan_`、`rpr_`、`qst_`、`imp_` 加 ULID。ULID 是 26 个 Crockford Base32 大写字符（`0-9A-HJKMNP-TV-Z`），而且第一个字符只能是 `0`～`7`（时间戳只有 48 位）。`cg_` 同理。`sys:` 后面跟小写字母、数字、连字符。
- `device_seq`：正整数。
- `occurred_at`：恰好 `YYYY-MM-DDTHH:MM:SS.sssZ`。月份 01～12、日期 01～31、小时 00～23、分秒 00～59 要在正则里限制（「2 月 30 日」这种不用管）。
- `content`：五个字段都必填；`content_release` 是 `rel_` 加 64 位小写十六进制；`activity_kind` 是五种之一；`activity_version` 是正整数。
- **按动词分派**：每个动词各有自己的 payload schema（不允许多余字段），并按规格第 3 节的「范围」一列要求或禁止 `attempt_id`、`content`，按「谁」一列限制 `actor.type`。不认识的动词必须不通过。
- `actor`：`type` 为 `learner` 时 `id` 是 `lrn_…`，为 `caregiver` 时是 `cg_…`，为 `system` 时是 `sys:…`。
- 自由文字最多 500 个字（`maxLength` 按字符算）；`hint.used` 的 `level` 是 1～3；`item.answered` 的 `try` 是正整数；`plan.created` 的 `tasks` 1～5 项、`plan_date` 是 `YYYY-MM-DD`、`kind: custom` 时必须有 `title`、`kind: free` 时 `ref` 必须是 `free`；`reward.adjusted` 的 `amount` 是非零整数。
- 奖励流水：`kind` 和 `amount` 的符号要一致（`earn` 为正、`spend` 和 `revoke` 为负、`adjust` 非零）；只有 `revoke` 才有 `target_entry_id`，而且 `revoke` 必须有。`entry_id` 是 `rwd_` 加 32 位小写十六进制。

下面这些**不要**在 schema 里做，后面的任务用代码做：整条事件不超过 16 KiB；同一 `ref` 在 `tasks` 里不重复（如果你能用 schema 干净地表达，可以做，并在说明里写出来）；跨事件的检查（唯一约束、尝试的合法性、`entry_id` 是否等于哈希）。

## 测试怎么写

- 用 Python 3.12 标准库 `unittest`，依赖只有 `PyYAML==6.0.3` 和 `jsonschema==4.26.0`，不要加别的库。运行方式是在仓库根目录执行 `python -m unittest discover -s tools/tests`。
- 用 `jsonschema.Draft202012Validator`。先对每个 schema 调用 `check_schema`。
- **合格样例**全部校验通过。另外断言：规格第 3 节表格里的每个动词，都至少有一个合格样例（在测试里写一份动词清单，和样例文件逐一对账）。
- **不合格样例**用「合格样例加一个补丁」的方式写，保证它只错在你想测的那一处。每个文件是一个 JSON 对象：

  ```json
  {
    "why": "try 必须从 1 开始",
    "schema": "event",
    "base": "events/valid/item.answered.json",
    "patch": [{"op": "replace", "path": "/payload/try", "value": 0}]
  }
  ```

  `schema` 是 `event`、`ingest-receipt` 或 `reward-entry`；`base` 是相对 `tools/tests/fixtures/` 的路径；`patch` 支持 `replace`、`add`、`remove`，路径写法同 JSON Pointer（RFC 6901）。在测试文件里自己实现这三种操作，不要引入库。测试读出 base、应用补丁、断言校验**不通过**；同时断言补丁的每一步都真的生效了（`replace` 和 `remove` 的路径原本存在）。
- 不合格样例：**每个动词至少一个**针对它自己 payload 的；另外至少覆盖下面每一条，每条一个文件：
  1. 信封缺 `event_id`、`device_seq`、`occurred_at`、`actor`、`payload` 各一个
  2. 信封有多余字段，包括 `recorded_at`
  3. `schema` 写成 `event/1`
  4. ULID 含字母 `I`、`L`、`O`、`U` 之一；长度 25；第一个字符是 `8`
  5. `device_seq` 为 0
  6. `occurred_at` 没有毫秒；毫秒 2 位；以 `+08:00` 结尾；月份 13
  7. 不认识的动词
  8. 范围为「尝试」的动词缺 `attempt_id`；范围为「无」的动词带了 `content`
  9. `content` 缺 `content_release`；`activity_kind` 不认识
  10. `actor.type` 不允许（例如孩子发 `reward.spent`）；`actor.type` 和 `id` 前缀不配
  11. 反思超过 500 个字
  12. `plan.created` 的 `tasks` 为空；`custom` 缺 `title`；`free` 的 `ref` 不是 `free`
  13. `reward.adjusted` 的 `amount` 为 0
  14. 收据 `source: sync` 缺 `batch_id`；`source: local` 带了 `clock_skew_ms`
  15. 流水 `earn` 的 `amount` 为负；`revoke` 缺 `target_entry_id`；`earn` 带了 `target_entry_id`
- 可以多写，但不要少写。

## 约束

- 规格是唯一依据。规格里没写的，不要自己加字段或动词；觉得规格不清楚、不合理或互相矛盾，**不要自己改**，写进交付包「说明」里的「疑问」。- 样例里的数据要像真的：时间合理，ULID 合法，文字是三年级孩子会写的话，不出现「学习」二字。
- 所有文本文件用 UTF-8、LF 换行。

## 验收标准

- [ ] 三个 schema 都通过 `check_schema`
- [ ] 每个动词都有合格样例，测试里有对账
- [ ] 全部合格样例通过；全部不合格样例被拦下，并且每个都只改了一处
- [ ] 不合格样例覆盖每个动词，以及上面列出的 15 类
- [ ] `python -m unittest discover -s tools/tests` 全部通过

## 交付格式（必须遵守）

本任务的文件清单（按这个顺序）：

```
schemas/event.schema.json
schemas/ingest-receipt.schema.json
schemas/reward-entry.schema.json
tools/tests/fixtures/events/valid/<每个合格样例>.json
tools/tests/fixtures/receipts/<每个合格样例>.json
tools/tests/fixtures/rewards/<每个合格样例>.json
tools/tests/fixtures/invalid/events/<每个不合格样例>.json
tools/tests/test_event_schemas.py
```

文件名用小写字母、数字、点、下划线和连字符，并逐个写进清单。样例文件多，一个回答放不下时，按交付包规则分段。

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
