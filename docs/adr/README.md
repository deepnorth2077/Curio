# 架构决策记录（ADR）

每份 ADR 记一个影响长期的架构决定：当时的背景、决定了什么、放弃了什么、会带来什么后果。

ADR 一旦接受就不改写。要推翻某个决定，就写一份新的 ADR，在里面注明「取代 ADR-00x」，旧的那份状态改为「已被取代」。这样十年后还能查到当初为什么这么做。

## 状态

- **提议**：Claude 起草，等 Luka 拍板。
- **已接受**：Luka 确认，开始照此执行。
- **已被取代**：被后来的 ADR 推翻，原文保留。

## 一览

| 编号 | 决定 | 状态 |
| --- | --- | --- |
| [ADR-001](0001-kernel-and-shell.md) | 平台内核与产品外壳分离 | 提议 |
| [ADR-002](0002-structured-content-first.md) | 结构化内容优先，自定义 HTML 是例外 | 提议 |
| [ADR-003](0003-immutable-releases.md) | 内容发布不可变，事件引用内容版本 | 提议 |
| [ADR-004](0004-events-as-source-of-truth.md) | 事件是事实来源，状态由投影产生 | 提议 |
| [ADR-005](0005-activity-host-boundary.md) | 活动宿主是唯一的权限边界 | 提议 |
| [ADR-006](0006-recoverability-gate.md) | 可恢复性是发布的前提 | 提议 |
| [ADR-007](0007-verifiable-task-packages.md) | 协作以可校验的任务包为准 | 提议 |
| [ADR-008](0008-frontend-stack.md) | 前端不用框架、不需要构建就能运行 | 提议 |

ADR-001～007 来自架构审查（见 #13）。ADR-008 是 Claude 补充的。

领域模型和非目标清单见 `docs/domain.md`。

## 等 Luka 拍板的问题

每份 ADR 末尾的「待拍板」一节列出了需要 Luka 决定的地方，都是产品或运维上的选择，不涉及技术细节。拍板后，Claude 把答案写进对应的 ADR，并把状态改为「已接受」。
