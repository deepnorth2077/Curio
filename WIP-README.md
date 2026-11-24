# wip/lever-v4

杠杆星 v3 被 Luka 和舰长打回（每站目标不明）。这个分支是 v4 任务说明重写：

- prompts/act.simulation.lever-dock-01.md：v4 动手探索任务（每站目标卡，分 A/B/C 三次交付）
- docs/constellations/energy-dock/lever-challenge.md：配套五题
- 知识点卡 v4、brief-template 加目标卡、lessons 加两条

设计审查：Sonnet 子 agent，修改后通过，十项必改已改（提交 20588cd）。

2026-11-23 Luka 决定这颗星的交付 A 交外部模型实现、Claude 审核（AGENTS.md 里外部通道已冻结，这次是 Luka 指定的例外）。
任务文件由 `python tools/make_task.py act.simulation.lever-dock-01 --draft` 从本分支 e34e204 生成（v6，作废 v5）。本会话 gh 登录失效，开不了 PR，所以没从 main 生成；收货后整合时一起开 PR。

收货命令：
python tools/intake.py <交付包…> --expect-issue #195 --expect-task act.simulation.lever-dock-01 --expect-commit e34e204f8d890b60c8f908e6726bf64e5d9de43b --expect-version v6

接下来：交付回来 → curio-intake-review → 跑走查（tools/walks/act.simulation.lever-dock-01.py 要按 v4 重写，旧的是 v3）。
