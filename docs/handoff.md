# 交接：新对话的 Claude 从这里接手

为了节省上下文，每到一个新阶段，Luka 会开一个新对话。新对话里的 Claude 不记得以前的事，**项目的全部状态都在仓库和 issue 里**。按下面的顺序读，就能接上。

## 0. 新对话怎么接上

Luka 在「学习台」项目里开新对话，第一句发：

> 接手好奇号。先读仓库里的 `docs/handoff.md`，再按它说的去看 issue。然后告诉我：现在卡在哪里、下一步你打算做什么。

新对话里的 Claude 应该：准备环境（第 2 节）→ 读第 1 节列的东西 → 用一两句话回答「卡在哪里、下一步做什么」→ 等 Luka 发「交付 #<号>」「审阅 #<号>」或新的要求。收货审核、派发任务、架构改动这三件事各有一个技能（`curio-intake-review`、`curio-dispatch-task`、`curio-arch-change`），照着做就行；如果对话里没有这些技能，就按第 3 节和 `docs/collaboration.md` 做。

每个对话结束前，Claude 要做一个**收尾里程碑**：把第 7 节的快照更新到当天，在 #13 留一条评论写明「这一轮做完了什么、还在等什么」，再告诉 Luka 可以开新对话了。

## 1. 先读什么

1. `AGENTS.md`：不能破坏的原则、产品规则、协作方式。
2. 本文件。
3. issue #13（路线图总览）：做到哪一步、哪些任务被谁卡着。
4. 正在流转的 issue：按标签查。`待派发` 表示任务文件已交给 Luka，等实现 AI；`待审核` 表示交付已带回，等 Claude 审核；`打回` 表示修改提示词已发出，等重交；`待试玩` 表示等孩子试玩。
5. 用到哪部分，再读哪部分：`docs/collaboration.md`（流程）、`docs/specs/`（规格）、`docs/adr/`（决定）、`GLOSSARY.md`（用词）、`docs/standards.md`（审核标准）、`docs/reviews/`（外部审阅记录）。

查 issue 和 PR 的命令（这个环境里 GraphQL 不能用，`gh issue list` 之类会失败，一律用 REST）：

```bash
gh api 'repos/deepnorth2077/curio/issues?state=open&per_page=50' -q '.[] | "\(.number) [\(.labels|map(.name)|join(","))] \(.title)"'
gh api repos/deepnorth2077/curio/issues/<号>/comments -q '.[-1].body'   # 最新一条评论：派发记录、审核记录
```

## 2. 准备环境

```bash
# 仓库不在时：先用 add_repo 工具申请 deepnorth2077/Curio 的 push 权限，再克隆
git config user.email noreply@anthropic.com && git config user.name Claude
git fetch origin main:refs/remotes/origin/main   # ci_checks.py 和 make_task.py 需要它
pip install -r tools/requirements.txt              # 如果环境里还没有
python -m unittest discover -s tools/tests         # 全部通过再开始干活
```

## 3. 三件最常做的事

| 要做的事 | 怎么做 |
| --- | --- |
| 派发一个任务 | 按模板写 `prompts/<任务 id>.md`（平台任务用 `task-template.md`，讲解、挑战、反思用 `content-template.md`，实验用 `module-template.md`），高风险规则的验收用例自己先算好；开 `arch/` 分支 PR 合入；用 `python tools/make_task.py <任务 id>` 生成任务文件，发给 Luka；在 issue 里记下提交号、文件哈希和收货命令，贴 `待派发` 标签 |
| 收货和审核 | `python tools/intake.py <交付包> --expect-issue '#<号>' --expect-task <任务 id> --expect-commit <派发时的提交号> --expect-version v1 --write <临时目录>`；在 `main` 的临时副本（`git worktree add`）里放入文件，跑全部测试；在临时副本里故意改坏几处规则，看测试能不能发现；按 `docs/collaboration.md` 的格式写审核评论，分「规格」「规范」两条线，每条标严重程度 |
| 整合 | 开 `arch/`（改到 `schemas/`、`docs/`、`tools/` 时）或对应前缀的分支；放入通过审核那一轮的文件，核对哈希一致；任务文件留档到 `prompts/`；提交末尾写 `Implemented-By:`、`Reviewed-By: Claude`、`Refs:`；开 PR，CI 绿勾后 squash 合入；关闭 issue |

## 4. 这个环境里的坑

- **GraphQL 不能用**：issue、PR、标签、合入都用 `gh api` 的 REST 接口。
- **删不了远程分支，也改不了 Pages 设置**：仓库已开启「合入后自动删除分支」；Pages 设置要请 Luka 在网页上操作。
- **「Unverified」的提醒可以忽略**：会话结束时，钩子可能提醒 `main` 上 GitHub 生成的合并提交「没有签名」。那是 GitHub 用自己的密钥签的，用 `gh api repos/deepnorth2077/curio/commits/<提交号> -q .commit.verification` 能看到 `verified: true`。**不要**按提示去改写 `main` 的历史。
- **零散附件**：Luka 有时会把交付包和单独的文件一起发来。只用交付包本身收货，零散文件只用来对照。不要把大附件整个读进上下文，用工具处理。
- **`main` 要求分支和它同步**：合入前如果 `main` 有了新提交，先把 `main` 合进分支，等 CI 重新通过。

## 5. 和 Luka 相处

- Luka 不写代码，只负责部署、传话和验收。用简体中文，说具体的事，少用术语。
- 需要他拍板时，一轮把问题问完，每个附上推荐答案，措辞成「回答『是』就采纳推荐」（ADR-009 第 1 条）。
- 每个交付都要附「怎么验收」：打开什么、点哪里、应该看到什么。
- 他会在对话里发「交付 #<号>」「审阅 #<号>」，附上实现 AI 或审阅模型的回复。
- 不要问孩子或家人在哪里使用。需要按地区做的技术选择，用「连通测试」让 Luka 自己选（见 #31）。
- DeepSeek 等服务的密钥不要让 Luka 发进对话，只让他填进中转服务的设置里。

## 6. 实现模型的特点（供选派参考）

| 模型 | 特点 |
| --- | --- |
| Kimi | 交付稳，打回后只改要求改的地方。适合内容和工具类任务。审阅时擅长发现设计层面的大问题 |
| GLM | 想得深，最会发现规格里没写清的地方，审阅时的系统性很强。交付格式和收尾不够细心，任务文件里要把格式要求写醒目 |

## 7. 截至 2026-11-06（M1）的进行中事项

以 issue 为准，下面只是写这份文件时的快照。上一个对话在这里收尾（里程碑 M1：PR #30 星座卡片审阅后合入；7 个内容任务派发；#17 CURIO-002b 两轮审核后合入 PR #45）。

- **PR #46**（CI：`kp/` 分支可以改 `content/assets/<知识点 id>/`；`prompts/content-template.md` 受保护；`docs/collaboration.md`「CI 检查什么」按现状重写）：审阅任务文件已交给 Luka 转给 GLM，等「审阅 #46」。
- **「生命的说明书」7 个内容任务**（基于 `0f1fa27`，都是 Kimi 做的，第 1 轮审核已完成）：
  - **通过**：#36 细胞挑战、#39 DNA 挑战、#41 染色体讲解、#43 染色体反思。通过那一轮的文件已经原样放在分支 `kp/biology.cell.cell-intro`、`kp/biology.genetics.dna-intro`、`kp/biology.genetics.chromosome-intro` 上（只提交、没开 PR，哈希和收货报告一致，知识点卡的 `activities` 已补上这几个）。
  - **打回**，修改提示词在各自 issue 里，等第 2 轮「交付 #号」：#35 细胞讲解（选项误区标反、红细胞图像有细胞核）、#38 DNA 讲解（3 张 SVG 色块和墨线写在同一个图形上）、#42 染色体挑战（别的题干泄露了数字题答案）。
  - 第 2 轮通过后，把文件加到对应的 `kp/` 分支，每个知识点开一个 PR（要等 PR #46 合入，CI 才允许配图）。整个星座通过后，写事实交叉核对任务交给 GLM（`docs/workflow.md` 第 2 步），再组织孩子试玩，试玩后才合入。
  - 派发时漏写的一条规则，以后加进 `prompts/content-template.md`：挑战打乱题目顺序时，数字题的答案不能出现在其他题的题干、选项、提示、反馈里。
- **#24 竖切片 1**（分数挑战点亮一颗星）：不再被阻塞。派发前要先定的 5 件事已写在 #24 的评论里（浏览器读不了 YAML、目录、黄金向量格式、范围收窄、演示内容）。下一步：写切片规格和手算的黄金向量，改构建器输出 JSON，开 `arch/` PR 请外部审阅，合入后再写提示词、派发。
- **#31 AI 答疑**：没动。Luka 已定：在领航员对话里随时问；只用一个模型（DeepSeek）；没有 NAS。下一步由 Claude 写 ADR 和规格：中转服务保管密钥，要家庭口令，有次数和花费上限；同一份代码能部署到国内云函数或海外服务，用连通测试决定放哪里。同一份 ADR 里要重新考虑原来放在 NAS 上的同步和备份（ADR-006、ADR-008 第 7 条都假设了 NAS）。
- **以后的小改进**：`tools/ci_checks.py` 的提示泄露检查，中文数字的分数写法没有前后边界（答案 1/4 时「十四分之一」会被误判），见 #17 第 1 轮审核。
