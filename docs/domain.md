# 领域模型

> 状态：**提议**，等 Luka 拍板（CURIO-001）。相关决策见 `docs/adr/`。

这里定义 Curio 平台内核里的对象：它们是什么、谁拥有、怎么变化、版本边界在哪里。界面怎么呈现这些对象（星图、地铁、维修舱、主题），不在这份文档的范围内。

## 对象一览

| 对象 | 是什么 | ID | 谁拥有 | 生命周期 | 版本边界 |
| --- | --- | --- | --- | --- | --- |
| **Family** 家庭 | 数据的边界。一套 Curio 只服务一个家庭 | `fam_<ULID>` | 系统 | 安装时创建 | 无 |
| **Learner** 学习者 | 一个孩子 | `lrn_<ULID>` | Family | 在用 → 归档（不删除） | 档案字段可改，ID 不变 |
| **Caregiver** 家长 | 能看进度、设奖励、确认兑换的大人 | `cg_<ULID>` | Family | 在用 → 停用 | 无 |
| **Device** 设备 | 一个浏览器上的一份安装。产生事件，参与同步 | `dev_<ULID>` | Family | 配对 → 在用 → 注销 | 自带递增序号 `device_seq` |
| **KnowledgeNode** 知识点 | 要懂的一件事，例如「分数的初步认识」 | `math.number.fraction-intro` | 内容仓库 | 草稿 → 已审 → 已发布 → 弃用（不删除） | `version` 整数，改内容就加一 |
| **ActivityDefinition** 活动定义 | 围绕知识点的一个讲解、挑战、实验，可以反复做 | `act.quiz.fraction-intro-01` | 内容仓库 | 待审 → Claude 已审 → 已批准 → 弃用 | `version` 整数 |
| **ContentRelease** 内容发布 | 某一时刻全部已发布内容的不可变快照 | `rel_<日期>_<哈希前 8 位>` | 构建管线 | 已构建 → 已预览 → 生效 → 被取代 | 本身不可变，修订就产生新发布 |
| **Attempt** 尝试 | 某个孩子在某台设备上，把某个活动从头做一遍 | `att_<ULID>` | Learner | 开始 → 完成 / 放弃 | 固定引用一个 ContentRelease 和活动版本 |
| **LearningEvent** 学习事件 | 一件已经发生的事实，例如「预测选了 B」「答错第 3 题」 | `evt_<ULID>` | Learner | 只追加，永不修改或删除 | 带 `schema_version`，旧事件靠升级器读取 |
| **Question** 问题 | 信号站里孩子提的一个「为什么」 | `q_<ULID>` | Learner | 提出 → 已回答 → 已归档 | 状态变化都记成事件 |
| **RepairTicket** 错题 | 维修舱里的一道题 | `rep_<ULID>` | Learner | 待修 → 复练中 → 已修好 | 状态变化都记成事件 |
| **Plan** 航线 | 某一天选的 2 个主线和 1 个自由探索 | `plan_<日期>_<学习者>` | Learner | 规划 → 进行中 → 结束 | 状态变化都记成事件 |
| **Reward** 奖励 | 能量、补给点、兑换记录 | 以「奖励事件」形式存在 | Learner | 发放 → 兑换 | 每次发放都指向触发它的事件，防止重复发放 |
| **Projection** 投影 | 从事件算出来的状态：掌握度、点亮、复习计划 | 无，随时可重算 | 系统 | 随时重算 | 带 `algorithm_version` |

运行时对象一律用 ULID：设备离线时自己就能生成，不会和别的设备撞号，而且按时间排序。内容对象的 ID 用人能读懂的点分路径，一旦发布就永不改动。

## 四个容易混的概念

- **KnowledgeNode**：要懂的东西。它不知道孩子做过什么。
- **ActivityDefinition**：帮孩子弄懂这件事的一种方式。一个知识点通常有讲解、挑战，有时还有实验。它也不知道孩子做过什么。
- **Attempt**：孩子某一次做某个活动。同一个活动做三遍，就是三个 Attempt。Attempt 锁定当时的内容版本：内容后来改了，旧 Attempt 依然指向孩子当时看到的那一版。
- **LearningEvent**：Attempt 里（或者 Attempt 之外，例如提问、打卡）发生的一件具体的事。事件是唯一的事实来源；掌握度、点亮、奖励余额全部由事件算出来。

## 关系

```mermaid
erDiagram
  Family ||--|{ Learner : "有"
  Family ||--|{ Caregiver : "有"
  Family ||--|{ Device : "有"
  KnowledgeNode }|--|{ ActivityDefinition : "被针对（targets）"
  KnowledgeNode }o--o{ KnowledgeNode : "前置"
  ContentRelease ||--|{ KnowledgeNode : "收录（某版本）"
  ContentRelease ||--|{ ActivityDefinition : "收录（某版本）"
  Learner ||--o{ Attempt : "做"
  Device ||--o{ Attempt : "在其上进行"
  Attempt }o--|| ActivityDefinition : "做的是（某版本）"
  Attempt }o--|| ContentRelease : "当时生效的发布"
  Attempt ||--|{ LearningEvent : "产生"
  Learner ||--o{ LearningEvent : "属于"
  Device ||--o{ LearningEvent : "记录于"
  Learner ||--o{ Question : "提出"
  Learner ||--o{ RepairTicket : "拥有"
  RepairTicket }o--|| KnowledgeNode : "挂在"
```

## 单家庭，不等于省掉 ID

Curio 只服务一个家庭、目前只有一个孩子，但 `learner_id` 和 `device_id` 从第一天起就写进每一条事件。原因：

- 平板、电脑、手机三台设备要同步，没有 `device_id` 和 `device_seq`，就无法去重，也发现不了漏传。
- 以后多一个孩子，或者换一台设备，历史数据不用迁移。
- 补上这两个字段几乎没有成本；以后再补，就要改写全部历史事件。

## 平台内核和产品外壳

| 平台内核（长期稳定，改动要走 ADR） | Curio 产品外壳（可以替换，不影响数据） |
| --- | --- |
| 上表里的全部对象和它们的 ID | 星图、知识地铁、维修舱、信号站、航线这些叫法和界面 |
| 内容格式、发布格式、事件格式 | 手绘风格、配色、字体、宝可梦等主题 |
| 活动宿主和契约 | 每个具体的讲解、挑战、实验 |
| 存储、同步、导出、恢复 | 激励规则的参数（几点能量换什么） |
| 投影算法的接口 | 具体用哪个掌握度算法 |
| AI 网关的能力契约 | 具体接哪家模型 |

判断标准：**换掉它之后，孩子的历史数据还能不能原样读出来**。能，就属于外壳；不能，就属于内核。

## 非目标

下面这些不做。以后真需要，再单独开 ADR：

- 多租户：一套部署服务多个家庭；
- 公开账户体系、注册登录、第三方登录；
- 公开的插件市场，或者让外人上传活动；
- 复杂的权限体系（Caregiver 都是同等权限）；
- 黑盒的知识追踪模型；
- AI 自动出题后不经审核直接发布；
- 微服务、消息队列、分布式数据库。
