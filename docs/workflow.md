# 知识点工作流

> 2026-11-12 起流程已减轻（ADR-009 增补 2），以 `AGENTS.md`「协作方式」「知识点工作流」两节为准。下面的八步是之前的做法，留作参考。

所有知识点都按这条流水线完善：**一个知识点一个 PR**，PR 里装着这个知识点的全部文件，合入就算上线。

活动的实现走 `docs/collaboration.md` 的协作流程：**默认是本地通道**，Claude 在自己的会话里开子 agent 做、另一个子 agent 审查，Claude 整合；需要外部模型时才走外部通道，由 Luka 传话（两条通道见 ADR-007 增补 1）。审什么按影响勾选 A、B、C（ADR-009 增补 1）。Luka 全程不写代码、不碰 git，主要做三件事：提供教材页、在 iPad 上短验收和组织孩子试玩、告诉 Claude 结果；需要外部模型时传话。

## 角色

| 角色 | 做什么 |
| --- | --- |
| Luka | 告诉 Claude 学校进度并拍教材页；在 iPad 上短验收、需要时组织孩子试玩，告诉 Claude 结果；外部通道时把任务文件交给外部模型、把交付包带回 |
| Claude | 选点、写知识点卡、定活动形式、写 issue 和提示词、审核、整合进仓库、合入、上线后复盘 |
| 实现者 | 默认是子 agent（本地通道，写进隔离的输出目录）；也可以是外部模型（外部通道，按 `docs/submission.md` 交付）。讲解、挑战、反思交 `activity.yaml` 和配图；实验、模拟交 `manifest.yaml` + `index.html`。都不操作 git |
| GitHub 自动校验 | 已上线：地盘、形态、schema、引用、题目、SVG、路径、引擎等级、发布门禁、ID、文案、署名（`tools/ci_checks.py`，见 `docs/collaboration.md`「CI 检查什么」）。P1 建设中：契约测试、断网运行、平板截图 |

## 文件放在哪里

```
content/
  nodes/<theme>/<知识点 id>.yaml            # 知识点卡，格式 schemas/knode.schema.json
  activities/<活动 id>/activity.yaml       # 讲解、挑战、反思，格式 schemas/activity-def.schema.json
  activities/<活动 id>/manifest.yaml       # 实验、模拟的描述，格式 schemas/activity.schema.json
  activities/<活动 id>/index.html          # 实验、模拟的实现，协议 docs/activity-contract.md
  assets/<知识点 id>/<文件名>.svg            # 这个知识点的配图（内容规格 3.6 的白名单）
prompts/<活动 id>.md                       # 这个活动的提示词或设计说明：讲解、挑战、反思用 prompts/content-template.md，实验用 prompts/module-template.md
docs/reviews/<活动 id>.md                  # 这个活动的审查、核对记录（kp/ 分支可以新增和修改，不能删）
docs/reviews/<知识点 id>.md                # 知识点卡的核对记录
```

完整格式见 `docs/specs/content.md`。

- 一个知识点一个主 issue；知识点下的每个活动一个子 issue，提示词就在子 issue 里（见 `docs/collaboration.md` 的「issue 怎么分」）。
- 分支名：`kp/<知识点 id>`，例如 `kp/math.number.fraction-intro`。这个分支只能改这个知识点自己的文件，CI 会检查。
- PR 标题：`知识点：<标题>（<知识点 id>）`。
- PR 描述用仓库里的 PR 模板，完成标准就是模板里的勾选框。

## 八步

1. **选点**（Claude）
   - 一个教材单元为一批，每批 3–5 个知识点，比学校进度提前 2–3 周。
   - 优先选维修舱里错题多、信号站里问题多的点。
   - 输入：Luka 告诉 Claude 学到哪个单元，最好附上课本那几页的照片。
2. **知识点卡**（Claude）
   - 写 `content/nodes/…/<id>.yaml`：驱动问题、目标、误区（每个带 ID）、年龄镜头、前置关系、课标和教材映射、出处。
   - **知识点卡先合入**：状态 `draft`，`activities` 先留空，单独开一个 PR 合入 `main`。这样活动任务的提示词才能从已合入的提交里嵌入知识点卡（`tools/make_task.py` 只读已合入的内容）。卡片合入后，ID 就固定了。
   - 卡片和后面的活动都勾 B，按 ADR-009 增补 1 第 3 条核对事实（没参与制作的子 agent 查出处；触发条件出现时，例如新概念、学科第一个知识点，再请别家模型核对）。**卡片要先核对、改好，再合入**：核对意见和逐条答复存进 `docs/reviews/<知识点 id>.md`，和卡片放在同一个 PR 里合入。这样 `main` 上不会出现还没核对过的卡片。
3. **定形式**（Claude）
   - **先用 `.claude/skills/curio-anatomy/` 拆解**：谜题、带出处的真相表、一句话实物、零件清单、站点（猜 → 动手 → 揭晓，结尾有成就物）。能做成动手探索的，讲解就做成模拟模块（`manifest.yaml` + `index.html`，按设计说明模板 `references/brief-template.md` 写提示词）。2026-11-06 的复盘：只有「一句话 + 静态图 + 选择题」的讲解，事实都对，孩子却没有乐趣、没有成就感。
   - **讲解**：每个点都做，时长不超过 5 分钟。可以选领航员对话的样子（`style: tutor`，内容规格 3.5）。
   - **挑战**：每个点都做，至少 5 题，每个错误选项都对应一个误区 ID。
   - **实验**：只有能动手调、能观察的点才做（科学、几何、测量），走「预测 → 观察 → 解释」。
4. **写 issue 和提示词**（Claude）
   - 每个活动一个子 issue，写明走哪条通道、勾了哪几项。讲解、挑战、反思用 `prompts/content-template.md`，实验、模拟用 `prompts/module-template.md`，存为 `prompts/<活动 id>.md`。外部通道合入后用 `tools/make_task.py` 生成任务文件；本地通道直接把任务说明交给子 agent。
   - 知识点的每个误区都要被至少一个活动针对：挑战里由错误选项和 `common_wrong` 引用误区，CI 从数据计算覆盖；实验在 manifest 的 `misconceptions` 里声明。
   - 写这个活动专属的验收清单。子 issue 打上 `待派发` 标签，主 issue 用勾选框列出全部子 issue。
5. **实现**
   - 本地通道（默认）：Claude 开子 agent，给它任务说明和一个隔离的输出目录；另一个子 agent 只读冻结的产物做审查和核对。
   - 外部通道：Claude 在对话里发给 Luka 任务文件，Luka 原样上传给外部模型；拿到交付包后在对话里发「交付 #<issue 号>」。
6. **Claude 审核**
   - 按 `docs/collaboration.md` 的审核清单检查：完整、规格、契约、验收标准、科学准确性、是否适龄、文案规则、误区覆盖。
   - B 的核对、C 的审查和截图按 ADR-009 增补 1 第 3、4 条做，结论写进 `docs/reviews/<活动 id>.md`。
   - 不通过：写修改意见，交回同一个实现者（外部通道由 Luka 传话）。最多两轮；仍不通过，说明提示词有问题，Claude 重写提示词，从第 4 步重来。
7. **整合与自动校验**（Claude）
   - Claude 把交付包放进 `kp/<知识点 id>` 分支，把活动 id 补进知识点卡的 `activities`，活动的 `review` 设为 `claude-reviewed`，开 PR。
   - PR 上出现绿色对勾，才能进入下一步。
8. **真机验收、孩子试玩，Claude 合入**
   - PR 里写明需不需要 Luka 在 iPad 上短验收、需不需要孩子试玩，理由看实际影响（ADR-009 增补 1 第 4 条）。新的知识点通常会改变探索体验，一般需要试玩；只改了错别字、颜色的改版不需要。
   - 需要试玩时，孩子玩 10 分钟，大人只看不帮。记四件事（ADR-009 增补 1 第 8 条）：孩子能不能自己开始；有没有主动改一个条件再试；在哪里卡住、要不要大人提示；能不能用自己的话说出一个发现。记一句原话或一个实际操作。
   - Claude 提供一个能直接打开的预览。Luka 在对话里告诉 Claude 结果，Claude 写进 PR。
   - Claude 把知识点状态改为 `published`、活动的 `review` 改为 `approved`，然后合入。

## 完成标准

前三条由 CI 的「发布门禁」自动检查，状态改成 `published` 的那一刻就会验证。

一个知识点同时满足以下几条，才算完成：

- [ ] 知识点卡通过校验，状态为 `published`
- [ ] 至少有讲解和挑战两个活动，都通过 CI；实验、模拟还要通过契约测试
- [ ] 每个误区都至少被一道题或一个实验步骤针对
- [ ] PR 里写明需不需要试玩；需要的，有一句孩子的试玩记录
- [ ] 每个活动的提示词都存进了 `prompts/`

## 上线后复盘

上线两周后，Claude 看一次这个知识点的数据：

- 提示用到了第几级；
- 错误选项集中在哪个误区；
- 有多少题进了维修舱。

需要修改时：开一个改版的主 issue，分支仍然叫 `kp/<知识点 id>`（不加 `-v2` 之类的后缀），知识点卡或活动的 `version` 加一，从第 4 步走到第 8 步。旧版本留在 git 历史里，ID 不变。

## 节奏

一周一个单元：

| 时间 | 做什么 | 谁 |
| --- | --- | --- |
| 周一 | 交本周这批知识点卡和提示词 | Claude |
| 周二到周四 | 实现、自动校验、审核 | 实现模型、Claude |
| 周末 | 孩子试玩、合入 | Luka |

一学期大约能完成一册书。孩子学校进度有变时，以学校为准调整选点。
