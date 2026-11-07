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
| 整合 | 开 `arch/`（改到 `schemas/`、`docs/`、`tools/` 时）或对应前缀的分支；放入通过审核那一轮的文件，核对哈希一致；任务文件留档到 `prompts/`（`feat/`、`fix/`、`chore/` 分支只能新增 `<任务 id>.task.md`，`kp/` 分支只能放自己活动的）；提交末尾写 `Implemented-By:`、`Reviewed-By: Claude`、`Refs:`；开 PR，CI 绿勾后 squash 合入；关闭 issue |

## 4. 这个环境里的坑

- **GraphQL 不能用**：issue、PR、标签、合入都用 `gh api` 的 REST 接口。
- **删不了远程分支，也改不了 Pages 设置**：仓库已开启「合入后自动删除分支」；Pages 设置要请 Luka 在网页上操作。
- **Pages 部署可能报「失败」，其实已经发布**：`deploy-pages` 有时等状态超时，Actions 里显示失败，但网站已经更新（2026-11-06 PR #50 就是这样）。这个环境打不开 github.io，以 Luka 在仓库 Settings → Pages 看到的「Last deployed」或在 iPad 上打开为准，不要去改 Pages 设置。
- **「Unverified」的提醒可以忽略**：会话结束时，钩子可能提醒 `main` 上 GitHub 生成的合并提交「没有签名」。那是 GitHub 用自己的密钥签的，用 `gh api repos/deepnorth2077/curio/commits/<提交号> -q .commit.verification` 能看到 `verified: true`。**不要**按提示去改写 `main` 的历史。
- **零散附件**：Luka 有时会把交付包和单独的文件一起发来。只用交付包本身收货，零散文件只用来对照。不要把大附件整个读进上下文，用工具处理。
- **`main` 要求分支和它同步**：合入前如果 `main` 有了新提交，先把 `main` 合进分支，等 CI 重新通过。
- **内容改了要重新生成内容包**：原型读的是 `prototype/content.js`，不是 `content/`。知识点或活动合入、改版以后，跑 `python preview/build.py --root . --bundle prototype/content.js`，开 `chore/` 分支合入，否则网上的原型还是旧内容。

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

## 7. 截至 2026-11-07（M6）的进行中事项

以 issue 为准，下面只是写这份文件时的快照。上一个对话在这里收尾（里程碑 M6：「生命的说明书」三个知识点接进原型的星图和地铁，点开就能玩）。

- **先放一放（Luka 2026-11-07 说的）**：PR #60、#62 暂不处理，等 Luka 再提。下面是它们原来在等什么：
  - **PR #60 竖切片 1**（#24）：`docs/specs/slice-1.md`、内容规格 6.3（构建器给每个 YAML 写 `.json`，已实现）、手算黄金向量 `kernel/vectors/`（9 个）和 `engine/vectors/grading.json`（60 条）、`tools/tests/test_vectors.py`（独立的 Python 对照实现复核手算值）。审阅任务 `review.slice-1` 给 GLM，基于 `471d45a`。回来后：逐条答复存 `docs/reviews/pr-60.md`，改完合入；把切片规格里对事件规格 6.3 的两处补充（只有一条 started；`rule` 取编号最小的）补回事件规格；然后写实现任务、派发。
  - **PR #62 ADR-010 和中转服务规格**（#31）：家里没有 NAS，后端改为云上的无服务器函数加对象存储（腾讯云云函数 / Cloudflare Workers，连通测试决定）；ADR-006、ADR-008 增补 1；`docs/specs/relay.md`（#31 第一段：中转服务、连通测试、用量、部署手册）。审阅任务 `review.relay` 给 Kimi，基于 `9c025ef`。回来后处理意见，再向 Luka 问这几件事（推荐都是「是」）：云上同步端到端加密、恢复密钥打印一份放家里；DeepSeek 先充 50 元，中转服务每月上限 20 元、每天 30 次；第二份备份每月下载到自己的电脑或网盘；#31 拆成两段（先做中转服务，不等 #25）。确认后合入，更新 #11 的描述（Python 参考内核改作交叉验证用）。
- **「乘法的秘密」星座**（#54）：#55 已关闭。多模型对比第一名 Claude Opus 5.5 的第 1 轮按 Luka 要求直接合入（PR #71），没有打回；知识点还是 `draft`。下一步：给这个知识点写讲解和挑战（发布门禁至少要这两个，误区 `split-both` 还没有活动针对），然后孩子试玩、发布。改版时顺手改掉评语里的三处小问题，并回答实现者的两个规格疑问（见 #55 最后一条评论）。
- **原型能玩「生命的说明书」**（PR #75，#74 已关闭）：`preview/build.py --bundle` 把所有已发布知识点打成 `prototype/content.js`，原型合并进星图和地铁（替换示例星球 `b.g7.cell`；细胞在初一，DNA、染色体在初二；图上用短名）。右栏「任务」点「开始」进全屏活动：动手探索走沙箱和契约，讲解、挑战、反思由原型里的 `Player` 照数据画，判分和试玩页 `preview/template.html` 是同一套（两份代码，改一处要同步改另一处）。**这一版先不记进度**：不写学习事件、不加能量、不改星球状态、不进维修舱，留给竖切片 1、4；那时在 `Player` 里接 `logEvent`。问领航员的问题发到信号站，不挂星球。等 Luka 反馈孩子玩的情况。
- **原型**（PR #58、#61、#64，#57 已关闭）：指挥中心有了「设置」（名字、年级、生日、教材、家长 PIN、AI 中转地址和家庭口令；年级存入学学年，每年 9 月自动升级；数据格式 v2 带迁移）；首页右栏变主栏，一开始不显示，点星球、地铁站或索引里的知识点才弹出（× 或 Esc 收起）；左上角、星图、地铁都不再写年级（Luka 不希望给孩子贴年级标签）。密钥不进页面，只填中转地址和口令。
- **「生命的说明书」已发布**（PR #68、#69、#70，#34–#43 已关闭；试玩页 PR #72 重新生成）。旧版讲解还留着，删不删以后再定。孩子试玩时说「挑战的答案全是 A」：规格只规定打乱题目顺序，没规定选项怎么排，实现 AI 都把正确选项写在第一个。已在三个知识点里调整了选项先后（id 和文字不变）；`prompts/content-template.md` 加了一句「正确选项的位置尽量分散」。Luka 说都选 A 也不是不能接受，所以**不加 CI 报错**。
- **事实核对剩下的建议 7、8**：`docs/constellations/life-manual.md` 的出处和配图说明，下次开 `arch/` 时改；「人的性别决定」的节名要对照 2024 年版实体书。
- 以后加进 `prompts/content-template.md`：挑战打乱题目顺序时，数字题的答案不能出现在其他题的题干、选项、提示、反馈里（#42 第 1 轮）。DNA 第 1 题「几种字母」的两个错误选项还没有对应的误区 id，要先加进知识点卡。
- **以后的小改进**：`tools/ci_checks.py` 的提示泄露检查，中文数字的分数写法没有前后边界（答案 1/4 时「十四分之一」会被误判），见 #17 第 1 轮审核。
