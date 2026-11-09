# 维护交接：换环境或换模型接手时读

- 状态：**准备中**。这份文件把维护所需、原来只在 Claude 的会话、账号技能或平台功能里的东西整理进仓库，让另一位维护者（别的环境、别的模型）能独立核对和接手。**正式切换的时间、谁来维护、规则要不要改，都由 Luka 决定**，本文件不做这些决定（第 8 节列出要他决定的事）。
- 写于 2026-11-09，基于 `main` 的 `c60a0f2`（M7 交接快照）。写的人：Claude（Opus 5.5，claude.ai 里的云端会话）。
- 日常进度看 `docs/handoff.md` 第 7 节和 issue #13；这里不重复。

## 1. 怎么核对这份交接

接手的人在自己的环境里跑一遍，结果对得上，才说明仓库里的资料够用。下面的期望值是 2026-11-09 的。

| 核对什么 | 命令 | 应该看到 |
| --- | --- | --- |
| 检查脚本自测 | `python -m unittest discover -s tools/tests` | 211 条全部通过（要 `tools/requirements.txt` 的依赖） |
| 规则集没被改 | `gh api repos/deepnorth2077/curio/rules/branches/main` | 禁止删除、禁止强推、必须走 PR（审批 0、只许 squash）、必须通过 `检查`（来源 GitHub Actions，要求分支最新）、线性历史；和 `docs/collaboration.md`「一次性设置」一致 |
| 发给 Luka 的任务文件能复算 | `python tools/make_task.py review.relay --draft --commit 9c025ef4d5088b134dc3091b05711602294e9926 --out <临时目录>` | 81795 字节，SHA-256 `51d03c31818484b0b5333b59d0646fb0d94ec97f4073d2f2c954bd693d02291e`，和 #31 的记录一致 |
| 同上，另一份 | `python tools/make_task.py review.slice-1 --draft --commit 471d45a37ddbc5821980b4505f981632919e0f6d --out <临时目录>` | 208040 字节，SHA-256 `beb447846ae7f0481c636c19e6ff8dcd6edfaac7fdf0c7517f660e97504b6e26`，和 #24 的记录一致（这个提交不在 `main` 的历史里，要先 `git fetch origin 471d45a37ddbc5821980b4505f981632919e0f6d`） |
| 进行中的事 | 见第 2 节的命令 | 和第 2 节一致；不一致以 GitHub 为准 |
| 操作手册能照着走 | 读 `docs/runbooks/`，挑一件 D 类小事（比如更新 `docs/handoff.md` 第 7 节）从开分支走到 CI 绿勾 | 不需要问原来的维护者任何问题 |

## 2. 2026-11-09 核对过的现状

```bash
gh api 'repos/deepnorth2077/curio/issues?state=open&per_page=100' -q '.[] | "\(.number) [\(.labels|map(.name)|join(","))] \(.title)"'
gh api 'repos/deepnorth2077/curio/pulls?state=open' -q '.[] | "\(.number) \(.head.ref) \(.head.sha[0:7]) \(.title)"'
git ls-remote --heads origin
```

- **`main`**：`c60a0f2`，M7 以后没有新提交。最近的 CI 都是绿的。
- **开着的 PR**：只有 #62（`arch/relay`，头 `9c025ef`，ADR-010 和中转服务规格），等外部审阅；PR 上还没有评论，落后 `main` 16 个提交，合入前要先合 `main`。
- **开着的 issue**：#4、#5、#8–#12、#24–#28、#31、#13（路线图）、#54。**没有一个贴着 `待派发`、`待审核`、`打回`、`待试玩`**，也就是没有任务正在实现者手里。下一步能直接做的事见 `docs/handoff.md` 第 7 节（1a 的验收测试和实现任务、截图工具、「乘法的秘密」的讲解和挑战）。
- **远程分支**：除 `main` 和 `arch/relay` 外，还有 `arch/adr-baseline`（PR #14）和 `arch/collaboration-rules`（PR #1），都早已 squash 合入，是开启「自动删除分支」之前留下的。维护者的环境删不了远程分支，要删请 Luka 在网页上删。
- **未提交的工作**：写这份文件的会话是新开的，除本 PR 外没有本地改动。以前各个会话的临时目录（工作树、截图、收货目录）随会话消失了，**仓库以外没有留下需要移交的文件**：审查结论在 `docs/reviews/`，派发和审核记录在 issue 评论里，发出去的任务文件能按上表从提交复算。
- **复盘**：ADR-009 要求每个里程碑写 `docs/retros/<里程碑>.md`，M0–M7 都没写，这个目录还不存在。各里程碑的总结在 #13 的评论里。是否补写由 Luka 定。

## 3. 原来在仓库以外的东西

| 东西 | 在哪里 | 还用吗 | 仓库里有没有 | 处理 |
| --- | --- | --- | --- | --- |
| `curio-dispatch-task`、`curio-intake-review`、`curio-arch-change` | claude.ai 账号的插件技能（2026-11-06 版），只在 Luka 账号下的 Claude 会话里能用 | 步骤还用，文本过时了 | 规则大多在仓库；有几条只在技能里（见下） | 本 PR 补成 `docs/runbooks/` 三份，并按 M7 的做法更新；`.claude/skills/` 下放同名的薄技能指向它们 |
| `curio-anatomy` | 仓库 `.claude/skills/curio-anatomy/`（原件）；账号里另有一份 | 用 | 有 | 账号那份只是指回仓库，没有独有内容 |
| 项目索引 `claude/architecture-index.md` | claude.ai 项目「好奇号 Curio」的文档 | 只是索引 | 内容都指向仓库 | 不用移交 |
| 设计文档（含可评论的决策表） | claude.ai 的 artifact，只有 Luka 的账号能打开 | 历史版本 | `docs/architecture.md` 是现行版 | 不用移交 |
| 项目记忆 | claude.ai 的记忆功能，记的是 Luka 说过的话 | 私人资料 | — | **不移交**。核对过其中和产品有关的决定都已写在仓库里：AI 预算和中转（`docs/architecture.md`、PR #62）、只保留裁剪后的题图、错题本、宝可梦打卡数据导入（`docs/architecture.md`、`docs/domain.md`）、不避开性染色体（染色体知识点卡）、答疑先不做两个模型交叉核对（PR #62 的 `docs/specs/relay.md`）、开发顺序（`docs/handoff.md` 第 7 节） |

**只写在账号技能里、本 PR 补进仓库的规则**（都在 `docs/runbooks/`）：

1. 派发记录的固定格式（「派发 · 提示词 vX · 基于提交 …」，附字节数、SHA-256、验收用例、收货命令）。
2. 变异检查改坏 **3～6 处**；没被测试发现的算「重要」。
3. 打回的修改提示词：只列要改的问题；照抄原任务文件的交付包格式；`提示词版本` 加一；要求重交完整交付包。
4. 收货时把交付包放进新建的空目录，用 `python -I` 跑脚本。
5. Luka 要打分时按规格符合度、测试质量、格式细心程度。
6. 「跨模型」是相对维护者说的（第 5 节第 6 条）。这一条原来没写明，是本次补的说明。

**账号技能和仓库现行规则冲突的地方**（技能写于 M7 以前，以仓库为准）：只写了外部通道，没有本地通道；审核结果写进 issue，现行规则是写进 `docs/reviews/` 和 PR；所有改动都两条线审，现行规则是按 A/B/C 勾选；知识点一律等孩子试玩，现行规则是看实际影响。建议 Luka 在账号里停用或删除这三个技能，免得以后有两份分叉（第 8 节）。

## 4. 平台功能承担的事，和通用的替代做法

原来的环境是 claude.ai 里的 Claude 云端会话（底层是 Claude Code）。和本项目有关、换环境就没有的：

| 做什么 | 原来靠什么 | 输入 → 输出 | 换环境怎么做 | 需实测 |
| --- | --- | --- | --- | --- |
| 拿到仓库和 GitHub 权限 | 会话的 `add_repo` 工具；出站代理替 `git`、`gh` 注入凭据（环境变量里的 `GH_TOKEN` 反而是坏的，要 `unset GH_TOKEN`） | 仓库名 → 能推分支、开 PR、合入的克隆 | 普通 `git clone` 加 `gh auth login`，用 Luka 授权的令牌；令牌不进仓库、不进对话 | 是 |
| GitHub 操作 | `gh api` REST（这个环境 GraphQL 被拦，`gh issue list`、`gh pr create` 会失败；Pages 设置接口也被拦） | — | REST 命令哪里都能用；能用 GraphQL 的环境用 `gh pr create` 等也行 | 否 |
| 自动加载规则 | `CLAUDE.md` 只有一行 `@AGENTS.md` | — | Codex 等直接读 `AGENTS.md`，内容一样 | 否 |
| 按关键词进入流程（「交付 #N」「审阅 #N」） | 账号插件技能按描述自动加载 | Luka 的一句话 → 对应的操作顺序 | `AGENTS.md` 已指向 `docs/runbooks/`；维护者看到关键词就读对应手册 | 否 |
| 开子 agent 做和审 | Claude Code 的 Agent 工具，可以指定 Opus、Sonnet | 任务说明 + 只读副本 + 输出目录 → 产物和最终回复 | 另开一个独立会话或命令行实例，给同样的三样东西；做不到就请 Luka 开一个新会话 | **是**：能不能并行、能不能选模型、能不能只读、能不能上网、能不能跑浏览器 |
| 把任务文件交给 Luka | SendUserFile 发到对话 | 任务文件 → Luka 手里的文件 | 提交在任务分支上，告诉他路径；issue 里记字节数和 SHA-256 | 否 |
| 查出处（B 核对、真相表） | WebSearch、WebFetch | 问题 → 原始出处 | 任何能上网的工具；不能上网的环境不能做 B 核对 | 是 |
| 截图走查（C） | 环境里装好的 Python Playwright 和 Chromium；`references/walk.py` 是样例 | 模块 → 三种屏幕、浅深色、reduced-motion 的截图 | 任何无头浏览器 | 是 |
| 提交签名 | 平台的签名程序（`~/.gitconfig` 里 `gpg.ssh.program`） | — | 规则集不要求签名（2026-11-09 读过规则集，没有签名规则），不签也能合 | 否 |
| 会话结束提醒 | 平台的结束钩子：提醒未提交、未推送，以及 `main` 上的合并提交「Unverified」 | — | 自己做 `docs/runbooks/README.md`「每次对话收尾」 | 否 |
| 署名 | 平台在提交和 PR 末尾自动加 Claude 的署名行 | — | CI 只提醒不拦截；`Implemented-By:`、`Reviewed-By:`、`Refs:` 自己写 | 否 |
| 记下 Luka 的决定 | claude.ai 的记忆功能在每轮后自动记 | — | 决定当场写进 issue、PR、`docs/reviews/` 或文档（本来就该这样） | 否 |
| 部署 | GitHub Actions 的 `pages.yml`，`main` 上 `prototype/` 一变就发布 | — | 和环境无关 | 否 |

仓库里**没有**配置任何钩子、斜杠命令或 MCP 工具；没有平台功能在替我们做版本检查、收货或审核。这些都由仓库里的脚本做：`tools/make_task.py`（任务文件和哈希）、`tools/intake.py`（收货）、`tools/ci_checks.py`（地盘、校验、ID、门禁，CI 强制）、`tools/build_release.py`、`preview/build.py`。截图工具还没做（ADR-009 增补 1 第 4 条），现在是手动截。

## 5. 换成 Codex（或别的模型）以后会悄悄消失的东西

1. **技能不会自动出现**。账号技能只在 Claude 里有；仓库 `.claude/skills/` 只有支持这种目录的工具会读。补救：`AGENTS.md` 的指针。
2. **子 agent 不一定有**，有也不一定能选模型、能并行、能上网。本地通道的前提就没了。补救：先实测；不行就用独立会话代替，或者对这件事改走外部通道。不能因为环境做不到，就让同一个实例既做又审。
3. **会话结束提醒没了**。补救：收尾检查。
4. **平台自动加的署名行没了**。补救：自己写三行署名。
5. **对话后自动记忆没了**。补救：决定当场落到仓库或 issue。
6. **「跨模型」的含义会反过来**。现在维护者是 Claude，Codex、GLM、Kimi 算别家；维护者换成 Codex（GPT）以后，Codex 自己开的子 agent 就是同家，长期契约的审阅要请 Claude、GLM 或 Kimi。`docs/runbooks/arch-change.md` 第 3 节已写明。
7. **出站网络不一样**。原来的环境 shell 不能装包、只能经代理访问 GitHub；别的环境可能反过来（能装包，但 GitHub 写权限要另外配）。
8. **能看到的东西不一样**。Luka 账号下的 artifact、项目文档、记忆，别的环境看不到；都不是必需的（第 3 节）。

## 6. `curio-anatomy` 里哪些是要求，哪些是当时的工具

| 写在技能里的 | 是什么 | 说明 |
| --- | --- | --- |
| 实物就是解释；工作顺序 1～5（谜题、带出处的真相表、一句话实物、零件清单、三拍加结尾）；「哇」时刻；成就物；挑战有难度 | 质量要求 | 方法本身，换谁做都一样 |
| 「Claude 画风」一节（暖纸面 `#F5F4EE`、墨线、淡彩、陶土红只给主角、衬线标题、等宽读数、卡片四角、动效克制、`prefers-reduced-motion`、留白） | 质量要求 | 这是视觉风格的名字和规格，和用哪家模型无关。标题被提示词按名字嵌入，所以不改名 |
| 适龄规则；不出现「学习」；48 px 控件 | 质量要求 | 也在 `AGENTS.md`、`docs/standards.md` |
| 「检查」七问；三种屏幕、浅深色、reduced-motion 的截图逐张看；至少两轮走查 | 质量要求 | ADR-009 增补 1 第 4 条也规定了三张固定截图 |
| `lessons.md`、`starter.html`、三个标杆模块 | 质量要求 | 新模块从骨架起步，和标杆对照 |
| 制作和审查不是同一个实例，审查者没看过制作过程 | 质量要求 | ADR-009 增补 1 第 4 条 |
| 实现用 Opus | 当时的工具选择 | 依据是「掰巧克力」多模型对比（`docs/reviews/bench.chocolate-split-01.md`：Opus 95.5，GPT 94，其余更低），差距不大。换模型要按 ADR-009 增补 1 第 3 条触发跨模型的事实核对，并和三个标杆并排对照画面 |
| 审查用 Sonnet | 当时的工具选择 | 规则只要求独立 |
| 「派子 agent」 | 当时的工具 | 见第 4 节 |
| Playwright、`walk.py` 里的 `/home/claude/...` 路径 | 当时的工具和环境 | 要求的是视图和截图；路径复制后要改 |
| 「上网核对」用 WebSearch | 当时的工具 | 要求的是查到原始出处 |

本 PR 已在技能和两个模板里把这几处写成「当前默认，操作选择」，嵌入提示词的三节（「Claude 画风」「适龄」「检查」）一字未改，旧任务文件的哈希不受影响。

## 7. 新环境要先实测的事

每一项测完，把结果（能 / 不能、用了什么）写进这一节或 `docs/handoff.md`：

- [ ] 能克隆、推分支、用 REST 开 PR 和 squash 合入（拿一件 D 类小事试）。
- [ ] `python -m unittest discover -s tools/tests` 全过；`node --test` 能跑（竖切片 1 要用，Node 22 测过）。
- [ ] 能开独立的子 agent 或会话：能只读一份副本、写指定目录、不碰 git；能不能指定模型；能不能并行。
- [ ] 子 agent 能上网查出处。
- [ ] 有无头浏览器，能按 `walk.py` 的三种视图截图。
- [ ] 维护者自己是哪家模型，据此确定哪些审阅者算「跨模型」。

## 8. 要 Luka 决定的事（本次不改）

都写成「回答『是』就采纳推荐」：

1. **本 PR 怎么审**：它改了流程文档的文字（勾 A，不涉及数据、事件、发布这类长期契约），推荐请一个没参与过的模型会话独立审阅一次，处理完再合入。回答「是」就这样办。
2. **账号里的三个旧技能**：推荐本 PR 合入后在 claude.ai 里停用或删除，以仓库 `docs/runbooks/` 为准。回答「是」就采纳。
3. **正式切换**：时间、新维护者是谁、在哪个环境，由你定。切换时 `AGENTS.md`「Claude 是本仓库唯一的维护者」、提交署名 `Reviewed-By: Claude`、`docs/collaboration.md` 的角色表要跟着改，这是勾 A 的规则改动，要单独开 PR、独立审阅、你确认。推荐切换前先在新环境把第 7 节测完。回答「是」就按这个顺序。
4. **两个旧远程分支**（`arch/adr-baseline`、`arch/collaboration-rules`）：推荐你在 GitHub 网页上删掉。回答「是」就采纳。
5. **复盘**：M0–M7 没写 `docs/retros/`。推荐不补旧的，从下一个里程碑开始写，四个量照 ADR-009 增补 1。回答「是」就采纳。
