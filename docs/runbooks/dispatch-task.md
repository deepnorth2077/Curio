# 派发任务

依据：`AGENTS.md`「协作方式」、`docs/collaboration.md`、ADR-007 增补 1、ADR-009 原文第 5、6 条和增补 1。

**输入**：一个要交给实现者的 issue（或者要新建的事）。
**输出**：issue 里有通道、勾选和派发记录；外部通道还多一个从 `main` 生成、记了哈希的任务文件。

## 1. 先有 issue

- 按 `.github/ISSUE_TEMPLATE/task.md` 写：给 Luka 的一句话、通道（本地 / 外部和原因）、勾了 A/B/C 中的哪几项和理由、规格、验收标准。
- 平台任务按竖切片拆：一个任务交付一个能演示的行为；太大就缩窄行为，不按层拆。写清「被谁阻塞」。拆分方案先交 Luka 确认。
- 知识点一个主 issue，每个活动一个子 issue。

## 2. 验收用例先行

高风险规则（哈希、排序、去重、计分、事件、奖励、投影）由维护者自己手算期望值，写成黄金向量或验收测试，放进 `tools/tests/fixtures/expected/`、`kernel/vectors/`、`engine/vectors/` 或对应的测试文件。期望值不能由被测代码算出来；每条写明输入、完整输出和手算依据。能跑的，先确认它们在旧代码或空实现上**失败**。

## 3a. 本地通道（默认）

1. 写**任务说明**：基准提交（完整提交号）、要读的规格和契约的路径、验收标准、测试接缝、交付哪些文件、输出目录。只有新设计才另写设计说明：活动放 `prompts/<活动 id>.md`（`kp/` 分支），平台任务写在 PR 正文里，规格级设计走 `arch/` 写进 `docs/specs/`。
2. 建 `<临时目录>`，给子 agent：任务说明、一份只读的仓库副本（例如 `git worktree add <临时目录>/base <基准提交>`）、输出目录。几个子 agent 同时做时，文件归属不能重叠。
3. 要求子 agent 能跑测试就先红后绿；做活动的按 `curio-anatomy` 自己走查、迭代；最终回复列出：做了什么、验收标准逐条结论、疑问。
4. issue 贴 `待派发`（子 agent 开始做）→ 交出产物后改 `待审核`，转 `intake-review.md`。

## 3b. 外部通道

只在 ADR-009 增补 1 第 6 条列的情况用：要求跨模型的 A 审阅、触发条件下的 B 跨模型核对、里程碑抽查、Luka 想试新模型。

1. 写 `prompts/<任务 id>.md`。任务 id 的格式由 `tools/make_task.py` 检查：`curio-NNN[a-z]`、`act.<活动 id>`、`review.<名字>`。
   - 模板：平台任务 `prompts/task-template.md`；讲解、挑战、反思 `prompts/content-template.md`；实验、模拟 `prompts/module-template.md`。
   - 开头 YAML：`task`、`issue`、`version`（从 v1 起）。
   - 用 `{{embed: 路径}}` 或 `{{embed: 路径#二级标题}}` 原样嵌入需要的规格、schema、契约、术语表章节（「协作」一节每份都带）；`{{commit}}` 换成提交号；字面的两个左花括号写 `\{{`。写法详见 `tools/make_task.py` 开头。
   - 只放这个任务用得到的东西；测试接缝写明；`docs/submission.md` 的交付包格式放在醒目的位置（派给格式不细心的模型时尤其要醒目）；要求实现者交付前逐条对照验收标准、列出疑问。
2. 先试生成：`python tools/make_task.py <任务 id> --draft --out <临时目录>`，打开看嵌入是否完整。
3. 提示词走 `arch/<名字>` 分支 PR 合入（`prompts/` 是受保护路径；知识点活动的提示词可以走 `kp/`）。CI「检查」绿勾后 squash 合入。
4. 从 `main` 生成正式任务文件：
   ```bash
   git fetch origin main:refs/remotes/origin/main && git checkout main && git pull
   python tools/make_task.py <任务 id> --out <临时目录>
   wc -c <临时目录>/<任务 id>.task.md && sha256sum <临时目录>/<任务 id>.task.md
   ```
   不手工拼任务文件。同一个提交生成的文件逐字节相同，任何人都能复算哈希核对。
5. 在 issue 里写**派发记录**（下面的格式），贴 `待派发`。
6. 把任务文件交给 Luka，一句话说明：交给哪个模型、让它把交付包整份带回、回来时发「交付 #<N>」。

### 派发记录格式（issue 评论）

```
派发 · 提示词 v<X> · 基于提交 <完整提交号>

任务文件 `<任务 id>.task.md` 由 `tools/make_task.py <任务 id>` 从已合入 main 的 <短提交号> 生成，已交给 Luka。建议用 <模型>。
- 字节数：<n>
- SHA-256：`<hash>`

验收用例：<维护者事先写好的用例>

收货命令：
python -I tools/intake.py <交付包…> --expect-issue '#<N>' --expect-task <任务 id> --expect-commit <完整提交号> --expect-version v<X> --write <临时目录>
```

## 规格改了怎么办

规格的原件只在仓库里。规格改了：改提示词、`version` 加一、重新合入、重新生成，派发记录写新版本，旧任务文件作废。本地通道的任务说明换新的基准提交即可。

## 选模型

是操作上的默认，不是规则（`docs/collaboration.md`「用哪个模型」，`docs/handoff.md` 第 6 节有各模型的特点）。规则只要求：能力合适；制作和审查不是同一个实例；记下**实际**用的模型，看不到版本就写「未提供」。
