# 知识点工作流

所有知识点都按这条流水线完善：**一个知识点一个 PR**，PR 里装着这个知识点的全部文件，合入就算上线。

活动的实现走 `docs/collaboration.md` 的协作流程：Claude 写提示词，Luka 交给实现 AI，再把交付包带回来，由 Claude 审核、整合。Luka 全程不写代码、不碰 git，只做四件事：提供教材页、在 Claude 和实现 AI 之间传话、组织孩子试玩、告诉 Claude 试玩结果。

## 角色

| 角色 | 做什么 |
| --- | --- |
| Luka | 告诉 Claude 学校进度并拍教材页；把提示词交给实现 AI，把交付包带回给 Claude；组织孩子试玩，告诉 Claude 结果 |
| Claude | 选点、写知识点卡、定活动形式、写 issue 和提示词、审核、整合进仓库、合入、上线后复盘 |
| 实现 AI | 按提示词做活动，按 `docs/submission.md` 交付活动包（`manifest.yaml` + `index.html`）；碰不到仓库 |
| GitHub 自动校验 | 已上线：地盘、schema、图谱、ID、文案、署名（`tools/ci_checks.py`）。P1 建设中：契约测试、断网运行、平板截图 |

## 文件放在哪里

```
content/
  nodes/<theme>/<知识点 id>.yaml            # 知识点卡，格式 schemas/knode.schema.json
  activities/<活动 id>/manifest.yaml       # 活动描述，格式 schemas/activity.schema.json
  activities/<活动 id>/index.html          # 活动实现，协议 docs/activity-contract.md
prompts/<活动 id>.md                       # 这个活动的提示词，从 prompts/module-template.md 复制
```

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
   - 写 `content/nodes/…/<id>.yaml`：驱动问题、目标、误区（每个带 ID）、年龄镜头、前置关系、课标和教材映射。
   - 状态设为 `draft`，通过 schema 校验和图谱检查后改为 `reviewed`。
3. **定形式**（Claude）
   - **讲解**：每个点都做，时长不超过 5 分钟。
   - **挑战**：每个点都做，至少 5 题，每个错误选项都对应一个误区 ID。
   - **实验**：只有能动手调、能观察的点才做（科学、几何、测量），走「预测 → 观察 → 解释」。
4. **写 issue 和提示词**（Claude）
   - 每个活动一个子 issue，用 `prompts/module-template.md` 写出自成一体的提示词，贴进子 issue，同时存为 `prompts/<活动 id>.md`。
   - 在活动 manifest 的 `misconceptions` 里写明它针对哪些误区。知识点的每个误区都要被至少一个活动针对，否则 CI 不允许发布。
   - 写这个活动专属的验收清单。子 issue 打上 `待派发` 标签，主 issue 用勾选框列出全部子 issue。
5. **实现**（实现 AI，Luka 传话）
   - Claude 在对话里发给 Luka 任务文件，Luka 原样上传给实现 AI；拿到交付包后在对话里发「交付 #<issue 号>」。
6. **Claude 审核**
   - 按 `docs/collaboration.md` 的审核清单检查：完整、规格、契约、验收标准、科学准确性、是否适龄、文案规则、误区覆盖。
   - 不通过：在 issue 里贴修改提示词，Luka 交回同一个实现 AI。最多两轮；仍不通过，说明提示词有问题，Claude 重写提示词，从第 4 步重来。
7. **整合与自动校验**（Claude）
   - Claude 把交付包放进 `kp/<知识点 id>` 分支，manifest 的 `review` 设为 `claude-reviewed`，开 PR。
   - PR 上出现绿色对勾，才能进入下一步。
8. **孩子试玩，Claude 合入**
   - 孩子玩 10 分钟，大人只看不帮。只记三件事：
     - 实验时，他是先猜再看，还是直接去看答案？
     - 他有没有问「为什么」？
     - 没人帮忙，他能不能独立玩完？
   - Claude 提供一个能直接打开的预览。Luka 在对话里告诉 Claude 这三件事，Claude 写进 PR。
   - Claude 把知识点状态改为 `published`、活动的 `review` 改为 `approved`，然后合入。

## 完成标准

前三条由 CI 的「发布门禁」自动检查，状态改成 `published` 的那一刻就会验证。

一个知识点同时满足以下几条，才算完成：

- [ ] 知识点卡通过校验，状态为 `published`
- [ ] 至少有讲解和挑战两个活动，并且都通过契约测试
- [ ] 每个误区都至少被一道题或一个实验步骤针对
- [ ] PR 里有一句孩子的试玩记录
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
