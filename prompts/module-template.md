# 活动模块提示词模板

Claude 用这个模板写活动模块（讲解、挑战、实验）的提示词。

生成方法：
- 复制本文件「---」以下的部分，存为 `prompts/<任务 id>.md`，开头加一段 YAML 头：`task: <任务 id>`、`issue: <issue 号，只写数字>`、`version: v1`，用 `---` 上下包起来。
- 把 `{{…}}` 占位符换成具体内容。需要原样贴入的仓库文件，写 `{{embed: 路径}}`（整个文件）或 `{{embed: 路径#二级标题}}`（一节）；需要提交号的地方写 `{{commit}}`。
- 规格合入 `main` 之后，运行 `python tools/make_task.py <任务 id>` 生成任务文件 `<任务 id>.task.md`：它从已合入的提交里读文件、展开指令、在开头写明「基于提交」，末尾列出嵌入文件的 SHA-256。任何没换掉的 `{{…}}` 都会报错，不会被发出去。
- 提示词必须**自成一体**：实现 AI 看不到仓库。需要的规格、已有代码、接口，都用 `{{embed: …}}` 嵌进来，不要写「见某某文件」。

---

> 契约 activity/1.1

# 任务：为知识点「{{node.title}}」做一个{{类型：讲解 / 挑战 / 实验}}

## 项目背景
你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。孩子是飞船舰长，知识点是星图上的星球。你要做的是其中一个可以插进平台的互动小程序。它运行在平台提供的沙箱 iframe 里，只通过固定的消息和平台通信。

## 你的角色
你同时是面向 {{age_band}} 孩子的理科互动设计师和前端工程师。

## 知识点（不要改动）
```yaml
{{知识点卡全文}}
```

## 教学要求
- 用驱动问题开场：{{node.driving_question}}
- 必须针对的误区（每个误区至少有一道题或一个实验步骤针对，在事件里带上误区 id，并在 manifest 的 `misconceptions` 里列出这个活动针对的全部误区 id）：
  {{误区列表，每条写成「id：说明」}}
- 教学法：{{pedagogy}}。先引导，后给答案；提示分 3 级，最后一级也不直接说出答案。
- 如果是实验（POE）：「预测」和「解释」两步由平台负责，你只实现「观察」。在 manifest 里写好 `controls`、`observables`、`predict` 和 `explain`。
- 读数的措辞按年龄段：三四年级用「更亮 / 更暗」「清楚 / 模糊」这样的词，初二以上才出公式和数值。
- 画面和读数必须来自同一个模型。
- 文字给三年级孩子看：句子短，说具体的事，不出现「学习」二字。

## 写给孩子的内容要求（原样贴入）
{{embed: docs/standards.md#给孩子看的内容}}

## 术语表（界面文字、注释都用这里的词）
{{embed: GLOSSARY.md#给孩子看的世界}}

{{embed: GLOSSARY.md#内容}}

{{embed: GLOSSARY.md#协作}}

## 技术契约 activity/1.1（必须遵守，原样贴入）
{{embed: docs/activity-contract.md}}

## manifest 格式（原样贴入）
{{embed: schemas/activity.schema.json}}

## 视觉
- 手绘风：墨线带轻微抖动，配淡彩色块，留白多。下面是平台的手绘线条库，原样内联进你的 `index.html` 使用：
  ```js
  {{prototype/index.html 里 sketchLib 函数的全文}}
  ```
- 颜色全部用 CSS 变量。收到 `init` 消息后，用其中的 `palette` 覆盖这些变量，这样颜色会跟随平台的深浅色模式。
- 动效要克制，并尊重 `prefers-reduced-motion`。

## 本活动的具体要求
{{题目数量、实验要调的量和要观察的量、讲解的分段等}}

## 验收标准
- [ ] {{本活动专属的条目}}
- [ ] 在 768 px 宽的平板上能完整使用，只用触摸就能走完全程
- [ ] 只发送 manifest 里 `emits` 声明过的事件，最后发出 `complete`
- [ ] 不发起任何网络请求，不使用 localStorage，不依赖外部 CDN
- [ ] 深色和浅色两种模式下都清楚可读
- [ ] manifest 符合上面的格式

## 交付格式（必须遵守）
文件清单：
- `content/activities/{{活动 id}}/manifest.yaml`
- `content/activities/{{活动 id}}/index.html`

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
