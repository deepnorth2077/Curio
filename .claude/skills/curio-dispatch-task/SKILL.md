---
name: curio-dispatch-task
description: "Use when a Curio issue needs an implementer (local sub-agent by default, external model when cross-model is required): write the task description or self-contained prompt, precompute acceptance cases, generate the task file with make_task.py, record the dispatch."
---

# 好奇号 · 派发任务

步骤的原件在仓库的 `docs/runbooks/dispatch-task.md`，先读它，照着做；规则以 `AGENTS.md`、`docs/collaboration.md`、ADR-007 增补 1、ADR-009 增补 1 为准。本文件只是让支持技能的环境能自动找到那份手册，不另写规则。

claude.ai 账号里同名的插件技能是 2026-11-06 的旧版，早于本地通道和按影响勾选，和仓库不一致时以仓库为准。
