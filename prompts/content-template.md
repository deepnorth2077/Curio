# 结构化内容提示词模板

Claude 用这个模板写**讲解、挑战、反思**的提示词。这三类是结构化内容：实现 AI 交的是数据文件 `activity.yaml`（加上配图），由平台的通用引擎显示和判分，不写程序。实验、模拟用 `prompts/module-template.md`。

生成方法：
- 复制本文件「---」以下的部分，存为 `prompts/<活动 id>.md`，开头加一段 YAML 头：`task: <活动 id>`、`issue: <issue 号，只写数字>`、`version: v1`，用 `---` 上下包起来。
- 知识点卡必须已经合入 `main`（`docs/workflow.md` 第 2 步），才能用 `{{embed: …}}` 嵌入。
- 把 `{{…}}` 占位符换成具体内容。运行 `python tools/make_task.py <活动 id>` 生成任务文件。

---

# 任务：为知识点「{{知识点标题}}」写一份{{讲解 / 挑战 / 反思}}

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。孩子是飞船舰长，知识点是星图上的星星。讲解、挑战、反思都写成数据文件，由平台的通用引擎显示和判分，所以你的任务是**写内容**，不是写程序。

## 你的角色

{{例如：熟悉小学生认知特点的科学教育编辑，擅长用孩子听得懂的话讲清楚一个概念，同时保证科学上准确}}

## 知识点卡（不要改动）

{{embed: content/nodes/<theme>/<知识点 id>.yaml}}

## 这份活动要做到什么

{{具体要求：讲哪几件事、按什么顺序、要用到哪些配图、针对哪些误区、讲解用不用领航员对话（style: tutor）、挑战几道题、三种答案类型怎么分配……}}

## 写给孩子的内容要求

{{embed: docs/standards.md#给孩子看的内容}}

另外：
- 句子短，说具体的事，不出现「学习」二字。
- 科学事实要有出处，写在活动的 `sources` 里。
- 简化的讲法不能和以后要教的内容矛盾，例如可以说「大约」「一般」，不能说错。

## 内容格式（必须遵守）

{{embed: docs/specs/content.md}}

{{embed: schemas/activity-def.schema.json}}

## 术语表

{{embed: GLOSSARY.md#给孩子看的世界}}

{{embed: GLOSSARY.md#内容}}

{{embed: GLOSSARY.md#协作}}

## 配图

{{需要哪些 SVG 配图、各画什么。没有就写「不需要」。}}

配图存为 `content/assets/<知识点 id>/<文件名>.svg`，按内容规格 3.6 的白名单写：手绘风格的线条和淡彩色块，不用 `<style>` 和 `style` 属性，颜色写在 `fill`、`stroke` 属性里；`viewBox` 写好，不写死 `width`、`height`。

## 怎么自己验证

- 能运行代码的话：用 Python 的 jsonschema（Draft 2020-12）拿上面的 schema 校验你的 `activity.yaml`，必须通过。
- 逐条核对内容规格第 5 节的校验规则：题目 id 唯一、`shaded` 不超过 `parts`、提示不说出答案、误区引用出自知识点卡、文字长度。
- 把每个科学事实和出处对一遍。

## 验收标准

- [ ] `activity.yaml` 通过 schema 校验，满足内容规格第 5 节的规则
- [ ] {{本活动专属的条目}}
- [ ] 配图通过内容规格 3.6 的白名单

## 交付格式（必须遵守）

本任务的文件清单：
{{逐行列出：content/activities/<活动 id>/activity.yaml，以及每张配图的路径}}

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。所有文件都写在交付包文字里。分段时，**每一段的第一行都必须是段首标记**。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
