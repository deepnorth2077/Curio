# 子模块提示词模板

Claude 为每个子模块写一份提示词：复制本模板，填好 `{{…}}`，存到 `prompts/<活动 id>.md`，然后交给实现模型。提示词和模块一起留在仓库里，以后重做或换模型重写时直接复用。

---

# 任务：为知识点 {{node.id}} 开发一个 {{type}} 活动

## 你的角色
你是面向 {{age_band}} 孩子的理科互动设计师，同时是前端工程师。

## 知识点（原样嵌入，不要改动）
```yaml
{{node.yaml}}
```

## 教学要求
- 以驱动问题开场：{{node.driving_question}}
- 必须处理的误区：{{node.misconceptions}}
- 教学法：{{pedagogy}}。先引导、后给答案；提示分 3 级。
- 如果是 POE 实验：你只实现「观察」。预测和解释由平台负责，你只需在 manifest 里写好 `controls`、`observables`、`predict` 和 `explain`。
- 读数措辞按年龄段写：三四年级用「更亮 / 更暗、清楚 / 模糊」，初二以上再出公式和数值。
- 画面和读数必须来自同一个模型。

## 技术契约 activity/1.1（必须遵守）
见仓库 `docs/activity-contract.md`。重点：
- 单文件，资源全部内联；不联网，不读写存储。
- 收到 `init` 后应用 `palette`，让颜色跟随平台的明暗主题。
- 只发送 manifest 的 `emits` 里声明过的事件。
- 支持触摸和键盘操作，尊重 `prefers-reduced-motion`。

## 视觉
沿用平台的手绘风：墨线带轻微抖动，配淡彩色块。可以复用 `prototype/index.html` 里的 `sketchLib`（平台会把它作为全局变量 `Sk` 注入模块）。

## 交付物
1. `manifest.yaml`：必须通过 `schemas/activity.schema.json` 校验。
2. `index.html`

## 验收标准
{{acceptance_checklist}}

通用条目：
- [ ] 在 768 px 宽的平板上完整可用，只用触摸能走完全程
- [ ] 打开平台的黑匣子，没有任何契约警告
- [ ] 断网后仍能完整运行
- [ ] 深色和浅色模式下都清楚可读
