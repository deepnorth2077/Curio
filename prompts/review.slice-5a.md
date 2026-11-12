---
task: review.slice-5a
issue: 109
version: v1
---

# 审阅任务：Curio 竖切片 5a 的规格（「生命的说明书」进正式外壳）

## 背景

「Curio」是一个家庭自用的理科探索网站，陪一个孩子从 2026 年小学三年级用到 2036 年高三。仓库只有一个维护者 Claude；Luka（家长，不写代码）负责验收和传话。

平台分内核（事件摄入、掌握度投影）、活动引擎和外壳。学习记录是只追加的事件流（`event/2`），掌握度从事件算出来。互动模块是「`manifest.yaml` + 单文件 `index.html`」，按契约 activity/1.1 通过 `postMessage` 和平台通信。竖切片 1 已经做完：正式外壳里可以做一个挑战（选择题、数字题、分数题），作答存进浏览器，星星会亮。

现在有三个已发布的知识点（细胞、DNA、染色体），各有一个动手探索的模拟模块和一个挑战，孩子很喜欢，但它们只能在原型和试玩页里玩，不留记录。这份规格要把它们接进正式外壳：第一次在正式外壳里做活动宿主（ADR-005），并写明「模块发的消息怎么换成事件」。

写规格时发现两件事，请特别留意：

1. 事件规格 3.7 只写了动词怎么对应（`predicted` → `poe.predicted`），没写 payload 怎么换。已发布的模块发的是 `{station, choice, correct, misconception}`，而 `poe.predicted` 的 payload 只允许 `{choice?, text_id?}`。规格提议给 `poe.predicted` 加三个可选字段。
2. ADR-006 规定真实孩子的数据进入系统之前要先有导出、导入、备份、迁移、恢复，这些还没做。规格把本切片的记录定为「试玩记录」。

Claude 写的架构改动不能自己审，所以请你来审。实现还没开始。

## 你的角色

资深工程师，熟悉事件溯源、浏览器沙箱（iframe sandbox、CSP、postMessage）和长期数据格式的演进。请挑刺，不要客气。这个项目只有一个家庭在用、维护者不写代码，所以「规则少、十年后还读得懂、数据丢不了」比「功能多」重要。

## 请重点看这些问题

1. **消息换成事件的表（规格第 3 节）**：每一行换得对吗？`observed {station}` 换成 `sim.observed {observable: "station", value}`、`answered` 换成 `item.answered`（`item_id` 用 `"station-N"`，`try` 由宿主数）有没有隐患？十年后回头读这些事件，还读得懂吗？
2. **给 `poe.predicted` 加可选字段**：这算「只增不改」吗？有没有更好的办法保住误区 id（比如换一个动词），又不动已发布的模块？加了以后，旧的投影、导出、升级器会不会受影响？
3. **宿主的校验和数值（规格第 2 节）**：状态表有没有漏掉的转移？配额的数值合理吗（已发布的模块在拖动时会连续发 `state`）？CSP 用 `<meta>` 插进 `srcdoc`，在 `sandbox="allow-scripts"`、不给 `allow-same-origin` 的 iframe 里够不够？有没有绕过的办法？
4. **和 ADR-005 的两处字面差别**：不带 `run_id`（改用「一次运行一个 iframe，按窗口对象认」）、不做心跳。这是合理的实现方式，还是应该写成 ADR-005 的增补？
5. **试玩记录（规格第 5 节）**：这样处理符合 ADR-006 吗？「试玩记录以后可以留下来算数」有没有风险（比如这期间事件格式又改了）？页面上那行提示够不够？
6. **验收用例**：9 个用例里的期望值有没有算错？有没有漏掉重要的情况（重复的 `ready`、`init` 之前模块就发消息、`complete` 和离开同时发生、页面刷新后恢复）？
7. **分步**：先做「三颗真实的星加挑战」，再做「动手探索进沙箱」，顺序对吗？每一步能不能独立演示？
8. **和已有文档有没有矛盾**：事件规格、ADR-005、ADR-006、活动契约。

## 资料

以下文件全部取自同一个提交，原样贴入。事件规格只贴了相关的四节。

{{embed: docs/specs/slice-5a.md}}

{{embed: docs/activity-contract.md}}

{{embed: docs/adr/0005-activity-host-boundary.md}}

{{embed: docs/adr/0006-recoverability-gate.md}}

{{embed: docs/specs/events.md#2. 事件信封（event/2）}}

{{embed: docs/specs/events.md#3. 动词表}}

{{embed: docs/specs/events.md#6. 投影}}

{{embed: docs/specs/events.md#8. 升级器}}

{{embed: content/activities/act.simulation.chromosome-pack-01/manifest.yaml}}

## 输出格式

用简体中文，按下面的格式输出，不要写补丁，说清楚问题和建议即可：

```
# 审阅意见 · issue #109 · 审阅者：<模型名和版本>

## 结论
可以合入 / 改完再合入 / 需要大改（一句话说明）

## 问题
### 1. <一句话标题>
- 严重程度：阻断 / 重要 / 建议
- 位置：<文件和章节>
- 问题：<具体说明>
- 建议：<怎么改>

## 对拍板问题的看法
（规格末尾的四个问题里的前三个，各一句话：同意推荐，或者不同意和理由）
```
