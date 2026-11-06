# 好奇号 Curio

一个陪孩子从小学三年级用到高中的理科探索平台，覆盖数学、物理、化学、生物。

孩子是飞船舰长，知识点是待登陆的星球。在星图上探索，在知识地铁上看清楚每个大概念是怎么从一年级一路通到高中的。做实验时先猜、再看、再解释。做错的题进维修舱，修好才算数。

界面里不出现「学习」二字。

## 现在的状态

处于 **P0 架构定稿** 阶段（见 [路线图](docs/architecture.md#路线图与里程碑)）。

- `prototype/index.html` 是可以点着玩的前端原型 v0.3，双击就能在浏览器里打开。里面的数据都是示例，AI 网关是模拟的。
- 正式的内容仓库、构建管线和家用后端还没开始做。

## 目录

| 路径 | 内容 |
| --- | --- |
| `docs/architecture.md` | 总体架构设计：原则、决策记录（D1–D25）、分层架构、数据模型、模块契约、AI 能力层、路线图 |
| `docs/collaboration.md` | 协作工作流：Claude 维护仓库，其他 AI 按提示词实现，Luka 传话 |
| `docs/submission.md` | 实现 AI 的交付包格式 |
| `tools/ci_checks.py` | PR 自动检查（地盘、规格、ID、文案、署名） |
| `docs/workflow.md` | 每个知识点从选点到上线的八步工作流、完成标准和每周节奏 |
| `docs/activity-contract.md` | 互动模块与平台之间的消息协议 `activity/1.1`，附实现样例 |
| `schemas/` | 三份 JSON Schema：知识点 `knode/1`、互动模块 `activity/1.1`、学习事件 `event/1` |
| `prompts/` | 提示词模板（`task-template.md`、`module-template.md`），以及每个任务实际用过的提示词 |
| `prototype/index.html` | 前端原型 v0.3（单文件） |
| `AGENTS.md` | 给接手这个仓库的任何 AI 模型看的工作规则 |

## 怎么打开原型

直接用浏览器打开 `prototype/index.html`。

- 家长入口的 PIN 是 `1234`，从左侧工具条底部的锁形图标进入。
- 学习记录只存在这台设备的浏览器里。
- 字体从 Google Fonts 加载；连不上时会退回系统字体，功能不受影响。

## 分工

- **Luka**：产品负责人。在 Claude 和实现 AI 之间传话，组织孩子试玩，拍板。
- **Claude**：架构师、总设计师，也是唯一的仓库维护者。写 issue 和提示词，审核交付物，整合、提交、合入。
- **其他模型**：只做实现，不碰仓库。按 issue 里的提示词做，按 `docs/submission.md` 的格式交付。

想提想法或反馈问题，用 Issues 里的「想法或问题」模板，Claude 会把它整理成任务。
