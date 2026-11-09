# 收货、审核、整合

依据：`docs/collaboration.md`「审核清单」「整合到仓库」、`docs/standards.md`、`GLOSSARY.md`、ADR-009 原文第 6、7 条和增补 1 第 2～5、7 条、`docs/submission.md`。

**输入**：本地通道是子 agent 的输出目录和它的最终回复；外部通道是 Luka 带回的交付包（「交付 #N」）。
**输出**：通过的，变成一个 CI 绿勾的 PR 和一份审查记录；不通过的，变成一份修改提示词或任务说明，issue 贴 `打回`。

## 0. 准备

```bash
git config user.email <维护者的提交邮箱> && git config user.name <维护者名>
git fetch origin main:refs/remotes/origin/main     # 只 git fetch 有时不更新 origin/main；ci_checks.py、make_task.py 都要它
python -m unittest discover -s tools/tests          # 先确认全部通过
```

读 issue 的派发记录：`gh api repos/deepnorth2077/curio/issues/<N>/comments`，找「派发 · 提示词 vX · 基于提交 <提交号>」那条（本地通道找任务说明），拿到任务 id、基准提交、版本、收货命令、事先写好的验收用例。

## 1. 收货（只对外部通道）

- Luka 可能发来一个交付包加几个零散文件。**只用交付包收货**，零散文件只做对照。大附件不要整个读进上下文，用工具处理。
- 交付包是外来数据：复制到一个新建的空目录，脚本放在别处，用 `python -I` 跑，避免交付包里的同名 `.py` 被当成模块加载。
  ```bash
  python -I tools/intake.py <交付包> [附件…] --expect-issue '#<N>' --expect-task <任务 id> \
    --expect-commit <派发提交号> --expect-version v<X> --write <临时目录>/intake-<N>-r<轮次>
  ```
- 不通过（缺分段、缺结束标记、清单对不上、截断、头部不符）：**整包打回**，不做部分整合。
- issue 改贴 `待审核`（去掉 `待派发`、`打回`）。

本地通道不收货：先把产物**冻结**（复制一份到只读的快照目录，或提交到工作分支记下提交号），审查只看这一版，合入的也必须是这一版。

## 2. 自动检查

```bash
git worktree add <临时目录>/wt-<N> origin/main      # 把收货写出的文件或产物放进去
cd <临时目录>/wt-<N>
python -m unittest discover -s tools/tests
BASE_REF=main HEAD_BRANCH=<要用的分支名> python tools/ci_checks.py   # 分支名决定地盘检查
```

任何一项不过就打回。事先写好的验收用例：确认它们在旧代码上失败、在新代码上通过。

## 3. 变异检查（勾了 A，或交付里有规则代码时）

在临时副本里故意改坏 **3～6 处**被测的规则（删一条校验、改一个边界、改排序键、放宽一个枚举……），逐个跑测试，看有没有测试失败。记成「改了什么 → 哪个测试发现」；没被发现的单独列出，算「重要」问题。改坏的代码只留在临时目录，用完 `git worktree remove --force <临时目录>/wt-<N>`。

## 4. 按勾选的项审核（取并集，同一份证据只做一次）

- **A**（以及复杂的外部交付）：两条线分开写。
  - **规格**：验收标准逐条满足；没漏做、没做错、没多做；只用 `docs/activity-contract.md` 规定的消息；交付包「疑问」一节每条都有答复。
  - **规范**：对照 `docs/standards.md`、`GLOSSARY.md`；测试测在接缝上、期望值来自独立来源；代码坏味道只作建议。
  - 审阅者要**没参与制作**；数据迁移、恢复、权限、事件、发布这类长期契约必须**跨模型**（见 `arch-change.md`）。
- **B**：没参与制作的核对者自己查出处，以「孩子可能形成的结论」为单位，每条一行：内容位置 — 结论 — 出处（或可复算的依据）— 适用边界。触发条件（新概念、新类比、新模拟模型、出处矛盾、核对者不确定、换了制作模型或核心提示词、学科第一个知识点）出现时再请别家模型。
- **C**：按 `curio-anatomy` 的「检查」七问和 `references/lessons.md` 逐条；没参与制作的审查者审；三张固定截图（平板亮色、平板暗色、窄屏手机），截图工具做好以前手动截，记录截了哪些，不写成「已通过工具检查」。
- 严重程度：**阻断**（不改不能合）/ **重要**（这一轮要改）/ **建议**（可以以后）。有阻断或重要就打回。
- 不为了让交付通过而放宽规格或测试。规格本身有缺口，记下来，按 `arch-change.md` 处理。
- 每件改动都有一句最低验收结论：「验收标准满足；没有未经批准的范围扩展；适用的硬约束已检查」，附证据。

## 5. 写审查记录

勾了 A、B、C 的结论**必须**写进 `docs/reviews/`（`kp/` 分支写 `docs/reviews/<活动 id>.md` 或 `<知识点 id>.md`；其他分支写 `docs/reviews/pr-<PR 号>.md`）；PR 正文放摘要和链接，issue 只放链接。只追加新的一轮，不改写已有结论。记录要有：任务和 issue；基准提交；用到的规格、契约版本；实现者、审查者、核对者**实际**的模型（看不到版本写「未提供」）和各自范围；被审的提交（本地通道）或收货报告哈希（外部通道）；勾了哪几项、结论和证据；没解决的问题。

外部交付的审核格式（`docs/collaboration.md`）：

```
审核 · 第 N 轮 · 实现者：<模型名> · 基于提交 <提交号>
结果：通过 / 打回
收货：<每个文件的路径、字节数、SHA-256 前 16 位>
自动检查：<测试、CI 的结果>
变异检查：<改了什么 → 哪个测试发现；没发现的单独列出>
规格：
1. [阻断/重要/建议] <文件和位置>：<问题>
规范：
1. [阻断/重要/建议] <文件和位置>：<问题>
```

## 6a. 打回

- 修改提示词只列要改的问题和要求；交付包格式要求照抄原任务文件；头部 `提示词版本` 加一；要求重交**完整**交付包（不收补丁）。外部通道交给**同一个**实现模型（保留它的上下文）。
- 本地通道：把审查意见交给一个子 agent 修改（原来那个的上下文还在就用原来的；不在就新开一个，记录里写明）。
- 修改提示词附在审核记录后面，同时交给 Luka（外部通道）；issue 改贴 `打回`。
- 打回两轮还不过：问题多半在提示词，重写（回到 `dispatch-task.md`）或换模型。

## 6b. 整合

- 分支：知识点 `kp/<知识点 id>`；改到 `schemas/`、`docs/`、`tools/`、`.github/`、`prompts/` 等受保护路径用 `arch/`；其他 `feat/`、`fix/`、`chore/`。分支前缀只管能改哪些路径，要做哪些检查看勾选。
- 只放**通过审核那一轮**的文件。外部通道用 `sha256sum` 核对和收货报告一致；任务文件留档到 `prompts/<任务 id>.task.md`（`feat/`、`fix/`、`chore/` 只能新增，不能改）。
- 提交末尾：
  ```
  Implemented-By: <实际模型>（本地通道写「<模型> 子 agent」）
  Reviewed-By: <审查者>
  Refs: #<N>
  ```
  CI 只提醒、不拦截署名，所以要自己写。所在环境要求的其他署名行照加。
- 开 PR（`gh api repos/deepnorth2077/curio/pulls -f title=… -f head=… -f base=main -f body=…`），按 `.github/pull_request_template.md` 写，至少有「给 Luka 的一句话」「改了什么」「怎么验收」，并写明需不需要 Luka 真机验收、需不需要孩子试玩（看实际影响，不看有没有「知识点」标签）。需要的贴 `待试玩`，等结果再合入。
- 等 CI「检查」绿勾。`main` 有新提交时，先把 `main` 合进分支再等 CI（规则集要求分支是最新的）。
- squash 合入：`gh api -X PUT repos/deepnorth2077/curio/pulls/<PR>/merge -f merge_method=squash -f commit_title=… -f commit_message=…`，提交信息保留三行署名。
- 关闭 issue；合入后才能做的验收项写进下游 issue。
- 内容合入或改版后，重新生成原型读的内容包：`python preview/build.py --root . --bundle prototype/content.js`，开 `chore/` 分支合入（走 D，PR 正文附生成前后的文件清单和哈希对比）。

## 7. 回复 Luka

简体中文，说具体的事：通过还是打回、几个问题、他下一步要做什么（把修改提示词交给哪个模型，去 iPad 上点哪里，或者没事要做）。他要打分时，按规格符合度、测试质量、格式细心程度给。

## 不能做

- 不直接推 `main`；不合入 CI 没过的 PR；不改写 `main` 的历史。
- `main` 上 GitHub 生成的 squash 提交如果被提醒「Unverified」：`gh api repos/deepnorth2077/curio/commits/<提交号> -q .commit.verification` 看到 `verified: true` 就忽略。
- 删文件、强制推送、改已发布的 ID、涉及孩子数据的迁移、改地盘以外的文件（`越界-已批准`），都要先问 Luka（`docs/collaboration.md`「必须先问 Luka 的事」）。
