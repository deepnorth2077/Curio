# 操作手册

规则在 `AGENTS.md`、`docs/collaboration.md`、ADR-007 增补 1、ADR-009 增补 1 里；这里只写**操作顺序**。两边说法不一致时，以规则文档为准，并把这里改掉。

这三份原来是 claude.ai 账号里的插件技能（`curio-dispatch-task`、`curio-intake-review`、`curio-arch-change`，2026-11-06 版），2026-11-09 搬进仓库，并按 M7 以后的做法（本地通道默认、按影响勾选、审查记录进 `docs/reviews/`）改过。账号里那三份从此不再是原件。

| 什么时候 | 读哪份 |
| --- | --- |
| 一个 issue 要交给实现者（子 agent 或外部模型） | `dispatch-task.md` |
| 子 agent 交出产物，或 Luka 发「交付 #N」带回外部交付包 | `intake-review.md` |
| 维护者自己写勾了 A 的改动（规格、schema、ADR、CI 规则、流程文档），或 Luka 发「审阅 #N」带回审阅意见 | `arch-change.md` |
| 设计或审核任何一个活动 | `.claude/skills/curio-anatomy/SKILL.md` |

## 这几份里用到的说法

- **维护者**：`AGENTS.md` 里写的「Claude」。正式换人由 Luka 决定（见 `docs/maintainer-handoff.md`），这里的步骤谁当维护者都一样。
- **子 agent**：维护者另开的一个独立模型实例，能只读仓库的一个副本、写一个指定的输出目录、不碰 git。在 Claude Code 里是 Agent 工具；别的环境可以是另开的会话或命令行实例。**能不能用、能不能选模型、能不能上网和跑浏览器，换环境要先实测**，不要假定。
- **`<临时目录>`**：每个任务一个新建的空目录，放在仓库工作区以外。
- **交给 Luka**：把文件发到对话里（Claude 环境用 SendUserFile）。没有发文件的功能时，告诉 Luka 文件在分支上的路径，并在 issue 里记下字节数和 SHA-256，他下载后可以自己核对。
- **GitHub 操作**：下面的命令用 `gh api` 的 REST 接口，因为维护者原来的环境里 GraphQL 不能用。环境允许时用 `gh pr create` 之类也可以，结果一样。

## 每次对话收尾

原来环境里有一个平台自带的会话结束提醒（未提交、未推送、「Unverified」合并提交），它不在仓库里，换环境就没有了。所以结束前自己做一遍：

```bash
git status --short                       # 应为空，或者只有故意不提交的临时文件
git log --oneline @{u}..                 # 当前分支有没有没推送的提交
gh api 'repos/deepnorth2077/curio/pulls?state=open' -q '.[] | "\(.number) \(.head.ref) \(.title)"'
```

然后按 `docs/handoff.md` 开头写的做收尾里程碑（更新第 7 节快照、在 #13 留评论）。
