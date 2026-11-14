# 交接：新对话的 Claude 从这里接手

为了节省上下文，每到一个新阶段，Luka 会开一个新对话。新对话里的 Claude 不记得以前的事，**项目的全部状态都在仓库和 issue 里**。按下面的顺序读，就能接上。

## 0. 新对话怎么接上

Luka 在 claude.ai 的 Curio 项目里开新对话，第一句发：

> 接手 Curio。先读仓库里的 `docs/handoff.md`，再按它说的去看 issue。然后告诉我：现在卡在哪里、下一步你打算做什么。

新对话里的 Claude 应该：准备环境（第 2 节）→ 读第 1 节列的东西 → 用一两句话回答「卡在哪里、下一步做什么」→ 等 Luka 发「交付 #<号>」「审阅 #<号>」或新的要求。

**现在的做法**（2026-11-12 起，ADR-009 增补 2）：全部规则在 `AGENTS.md`「协作方式」一节，一页读完，照着做。Claude 写需求和规格、审查、整合，实现交给 Opus 子 agent；只有存下来的数据格式和科学事实要另一个子 agent 独立审；画面由 Luka 和舰长看。外部通道已冻结，`curio-intake-review`、`curio-dispatch-task`、`curio-arch-change` 三个技能和第 3 节是那时的做法，不再用。

每个对话结束前，Claude 要做一个**收尾里程碑**：把第 7 节的快照更新到当天，在 #13 留一条评论写明「这一轮做完了什么、还在等什么」，再告诉 Luka 可以开新对话了。

## 1. 先读什么

1. `AGENTS.md`：不能破坏的原则、产品规则、协作方式。
2. 本文件。
3. issue #13（路线图总览）：做到哪一步、哪些任务被谁卡着。
4. 正在流转的 issue：按标签查。`待派发`：外部通道是任务文件已交给 Luka、等外部模型，本地通道是等 Claude 开子 agent；`待审核`：交付已带回或子 agent 已交出产物，等 Claude 审核；`打回`：修改意见已发出，等重交；`待试玩`：等 Luka 验收或孩子试玩。issue 里写明走哪条通道。
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

## 3. 三件最常做的事（外部通道，已冻结，留档）

| 要做的事 | 怎么做 |
| --- | --- |
| 派发一个任务 | **本地通道（默认）**：写任务说明（基准提交、要读的规格路径；新设计才写设计说明），给子 agent 一个隔离的输出目录，另开一个子 agent 只读冻结的产物做审查。**外部通道**：按模板写 `prompts/<任务 id>.md`（平台任务用 `task-template.md`，讲解、挑战、反思用 `content-template.md`，实验用 `module-template.md`），高风险规则的验收用例自己先算好；开 `arch/` 分支 PR 合入；用 `python tools/make_task.py <任务 id>` 生成任务文件，发给 Luka；在 issue 里记下提交号、文件哈希和收货命令，贴 `待派发` 标签 |
| 收货和审核 | 本地通道不收货，用提交号绑定被审的版本，按勾选的项做检查，结论写进 PR 的审查记录。外部通道：`python tools/intake.py <交付包> --expect-issue '#<号>' --expect-task <任务 id> --expect-commit <派发时的提交号> --expect-version v1 --write <临时目录>`；在 `main` 的临时副本（`git worktree add`）里放入文件，跑全部测试；在临时副本里故意改坏几处规则，看测试能不能发现；按 `docs/collaboration.md` 的格式写审核评论，分「规格」「规范」两条线，每条标严重程度 |
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
- 需要他拍板时，一轮把问题问完，每个附上推荐答案，措辞成「回答『是』就采纳推荐」（ADR-009 原文第 1 条）。
- 每个交付都要附「怎么验收」：打开什么、点哪里、应该看到什么。
- 他会在对话里发「交付 #<号>」「审阅 #<号>」，附上实现 AI 或审阅模型的回复。
- 不要问孩子或家人在哪里使用。需要按地区做的技术选择，用「连通测试」让 Luka 自己选（见 #31）。
- DeepSeek 等服务的密钥不要让 Luka 发进对话，只让他填进中转服务的设置里。

## 6. 实现模型的特点（供选派参考）

| 模型 | 特点 |
| --- | --- |
| Kimi | 交付稳，打回后只改要求改的地方。适合内容和工具类任务。审阅时擅长发现设计层面的大问题 |
| GLM | 想得深，最会发现规格里没写清的地方，审阅时的系统性很强。交付格式和收尾不够细心，任务文件里要把格式要求写醒目 |

## 7. 截至 2026-11-14 的进行中事项

以 issue 为准，下面只是快照。**流程已按 ADR-009 增补 2 减轻**（PR #113）：只有存下来的数据格式和科学事实要独立审（用子 agent 即可）；画面由 Luka 和舰长直接看；外部通道冻结。**2026-11-14 起设备上的记录算数**（恢复演练通过），改存储格式要带迁移和升级测试。Luka 定：Claude 只写需求和规格、审查和整合，实现交给 Opus 5.5 子 agent。

**工作顺序**（Luka 2026-11-13 确认，取代 2026-11-12 的顺序；一步做完验收了再开下一步）：

| 步 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 学习记录补记三样东西（`docs/specs/evidence.md`，#121） | 完成（PR #122、#125；Luka 2026-11-13 在 iPad 上试过，#121 已关闭） |
| 2 | 导出和恢复（#8），干净设备演练一次 | **完成**（规格 PR #129，6a PR #132，6b PR #134；Luka 2026-11-14 演练通过，记录在 `docs/retros/2026-11-14-restore-drill.md`，#8 已关闭）。恢复密钥 6 位数字；每季度照 `docs/retros/restore-drill-template.md` 演练一次，下一次 2027 年 2 月 |
| 3 | **下一件事。**「分数、小数、比与百分数」标杆星座：先用 `curio-anatomy` 拆解，再一组一组写任务说明，从第一组开始 | Luka 2026-11-12 提出。主 issue #127；拆解和六组任务说明（十九颗星）已存进仓库，从 `docs/constellations/zero-to-one/index.md` 看起。**第 1 颗星做完了，Luka 2026-11-14 验收通过**（这一颗由 Fable 直接实现）：知识点卡和「切分机」PR #136，挑战 PR #138，试玩页 https://deepnorth2077.github.io/Curio/preview/zero-to-one/ 。圆钮、分数写法、「1」记号、数线条已抽进 `references/starter.html`，`g1.md` C.0 按经验改过（v1.2）。**下一件事：第 2 颗星「数线跳跳」**（`g1.md` C.2），做之前先读 `docs/constellations/zero-to-one/notes-star1.md`；舰长试玩切分机时记四件事（`g1.md` 第 7 节第 6 步），按他的反应修后面的星。知识点还是 `draft`：发布门禁要一个讲解，等第 4 步定。其余十八颗星是草案，没有派发。拆解和任务说明不碰存储格式；模块做出来先放试玩页，第 4 步做完再接进正式外壳 |
| 4 | 动手探索进正式外壳，先做小的（沙箱、断网、消息白名单） | 规格 PR #110 要按审阅改小，审阅记录在该分支 `docs/reviews/pr-110.md`。顺手修染色体两道数字题只显示通用反馈 |
| 5 | 按 review 改设计稿（PR #106）：星图的盲猜和正常画面一致、一个点一颗星、三种星的状态、点完回应在第一屏、字号；领航员文案和几处表情；大图细线 | 任务说明在 #105 第 2 轮评论。改完 Luka 和舰长看、玩盲猜 |
| 6 | 问领航员（#86）：在对话里提问、问答存进信号站 | 中转服务已通（#31）。问答要存下来，所以排在第 2 步之后 |
| 7 | 能挑、能换领航员（小灯、小环） | 从 PR #112 摘出一页任务；依赖第 5 步的设计稿。不设计第三位（Luka 2026-11-12：「小彗」「小荚」都不采用，草稿在 PR #106 的 `prototype/design/navigator3.html` 留作参考），只把领航员做成标准化的接口：加一位就是加一份内容，不改代码 |
| 8 | 零件库和颜色下发 | 规格 PR #108 要按审阅改小。Luka 2026-11-12 定：深色强调色统一用**紫**（外壳现在的 `#A797F7`），模块跟着改 |

**暂不排期**：PR #80（交接给别的维护者，等 Luka 定时间）；#99、#54；#25～#28、#9～#12 在第 2 步之后再排。

**挂着的 PR**：#106 设计稿（先按第 5 步改，再给 Luka 和舰长看）；#108、#110、#112 三份规格（审阅原文和逐条答复各在自己分支的 `docs/reviews/`，都没按答复改，轮到时改小再合）。

**已知的小毛病**：染色体两道数字题答错只显示通用反馈（内容里那两条没写误区 id）；星的顺序是细胞、染色体、DNA；星下面的标题偏长。

**Luka 2026-11-12 的答复**：#118 确认；深色强调色用紫；第三位领航员两个候选都不要，留标准化接口；基础设施审查（2026-11-08，Codex）原文**不放进仓库**，只引用编号 F1～F8；小彗、小荚的草稿可以放进仓库。

**领航员**：每一位必须原创，不以任何现成角色为原型（孩子喜欢的宝可梦角色不能用，只取「勇敢、有时候很萌」这样的性格）。
