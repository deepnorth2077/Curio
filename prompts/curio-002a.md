---
task: curio-002a
issue: 16
version: v1
---

# 任务：为「好奇号」的内容格式写 JSON Schema 和第一份样例内容

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中，覆盖数学、物理、化学、生物。孩子是飞船舰长，知识点是星图上的星球。网站运行在平板、电脑和手机的浏览器里，界面文字是简体中文。

这个平台的原则是「内容即数据」：知识点、讲解、挑战（测验）、反思都是带版本号的 YAML 数据文件，由平台的通用引擎显示和判分。只有通用引擎做不了的实验，才写成自定义的 HTML 小程序。所有数据文件必须先通过 JSON Schema 校验，才能进入仓库。

现在还没有这些 schema。你的任务就是把下面「内容规格」里定义的格式写成 JSON Schema，并做出第一份完整的样例内容，再写测试证明 schema 既放行合格的数据，也拦得住不合格的数据。

## 你的角色

严谨的数据格式工程师，熟悉 JSON Schema 2020-12 和 Python 的 `jsonschema` 库。

## 你需要的资料

### 1. 内容规格（唯一依据，不要改动）

{{embed: docs/specs/content.md}}

### 2. 现有的知识点 schema（你要在它基础上加 `sources` 字段）

{{embed: schemas/knode.schema.json}}

### 3. 现有的自定义实验 manifest schema（你要加 `version`、限制 `type`）

{{embed: schemas/activity.schema.json}}

## 要交付的文件

1. `schemas/activity-def.schema.json`：结构化活动（规格第 3 节），含必填的 `engine`（正整数）。误区引用的写法有两种（规格 3.3）：只针对一个知识点时写误区 id，针对多个时写 `<知识点 id>:<误区 id>`；schema 两种都放行，至于该用哪种，由 CI 按 `targets` 的个数检查，不在 schema 里做。
2. `schemas/release.schema.json`：发布清单（规格第 6.1 节），含 `engine_min`。`release_id` 必须等于 `rel_` 加 `content_hash`，这一条 schema 表达不了，不用管，只校验各自的格式。清单里的路径按规格第 1 节的路径规则写正则（ASCII、正斜杠、不允许 `.` 和 `..` 段）。
3. `schemas/knode.schema.json`：在现有文件基础上加可选字段 `sources`（规格第 2 节）。其他内容一个字都不要动。
4. `schemas/activity.schema.json`：在现有文件基础上加必填字段 `version`（正整数），把 `type` 改成只允许 `experiment` 和 `simulation`（规格第 4 节）。其他内容不要动。
5. 样例内容，目录结构和规格第 1 节相同，但放在 `tools/tests/fixtures/content/` 下面：
   - `tools/tests/fixtures/content/nodes/num/math.number.fraction-intro.yaml`：知识点「分数的初步认识」（人教版三年级上册），`status: published`，至少 3 个误区，其中必须有「没有平均分也当成几分之一」和「把涂色的份数和没涂色的份数相比」这两个。
   - `tools/tests/fixtures/content/activities/act.explain.fraction-intro-01/activity.yaml`：讲解，6～10 步，至少一个 `check` 小问题，至少用到 `pie` 和 `rect-unequal` 两种配图。
   - `tools/tests/fixtures/content/activities/act.quiz.fraction-intro-01/activity.yaml`：挑战，5～8 道题，三种答案类型（选择、数字、分数）都要有。知识点的每个误区，都要被至少一个错误选项或 `common_wrong` 引用。
   - `tools/tests/fixtures/content/activities/act.reflection.fraction-intro-01/activity.yaml`：反思。
   - 三个活动的 `review` 都写 `approved`，`engine` 都写 `1`，`targets` 都是 `[math.number.fraction-intro]`；知识点的 `activities` 列出这三个活动 id。最后一条提示不能说出答案（规格 3.4）。
6. 不合格样例：全部写在**一个文件** `tools/tests/fixtures/invalid/content.json` 里，格式见下面「测试怎么写」。
7. `tools/tests/test_content_schemas.py`：测试。

## 测试怎么写

- 用 Python 3.12 标准库 `unittest`，依赖只有 `PyYAML==6.0.3` 和 `jsonschema==4.26.0`，不要加别的库。运行方式是在仓库根目录执行 `python -m unittest discover -s tools/tests`。
- 用 `jsonschema.Draft202012Validator`。先对每个 schema 调用 `check_schema`。
- **合格样例**：`tools/tests/fixtures/content/` 下每个 YAML 文件都按对应的 schema 校验通过（知识点用 knode，`activity.yaml` 用 activity-def）；`release.json` 按 release、`experiment-manifest.json` 按 activity 校验通过。
- **不合格样例**用「合格样例加一个补丁」的方式写，保证它只错在你想测的那一处，而不是因为别的地方写错了才不通过。`tools/tests/fixtures/invalid/content.json` 是一个数组，每一项是：

  ```json
  {
    "name": "quiz-two-correct",
    "why": "选择题有两个正确选项",
    "schema": "activity-def",
    "base": "content/activities/act.quiz.fraction-intro-01/activity.yaml",
    "patch": [{"op": "replace", "path": "/body/items/0/answer/choices/1/correct", "value": true}]
  }
  ```

  `name` 在文件内唯一，用小写字母、数字、连字符；`schema` 是 `activity-def`、`knode`、`activity` 或 `release`；`base` 是相对 `tools/tests/fixtures/` 的路径。发布清单没有现成的合格 YAML，请另外写一个合格的 `tools/tests/fixtures/content/release.json`（数据是虚构的，格式要对）作为它的 base。`patch` 支持 `replace`、`add`、`remove` 三种操作，路径写法同 JSON Pointer（RFC 6901）。在测试文件里自己实现这三种操作（几十行），不要引入库。测试读出 base、应用补丁、断言校验**不通过**；同时断言补丁的每一步都真的生效了（`replace` 和 `remove` 的路径原本存在）。
- 不合格样例至少覆盖下面每一条，每条一项（一条里有几种情况，就写几项）：
  1. 缺必填字段（`id`、`kind`、`version`、`targets` 各一个）
  2. `kind` 不在三种之内
  3. `schema` 不是 `activity-def/1`
  4. 选择题没有正确选项；有两个正确选项；只有 1 个选项；有 6 个选项
  5. 数字题缺 `value`；分数题分母为 0
  6. 提示 0 条；提示 4 条
  7. 题干超过 80 个字；提示超过 60 个字；标题超过 20 个字
  8. 配图类型不认识；`pie` 的 `parts` 为 1 或 13
  9. 讲解只有 2 步；讲解有 21 步
  10. 反思缺 `prompt`
  11. 出现规格里没有的字段（`additionalProperties`）
  12. 知识点 `sources` 的 `type` 不在三种之内
  13. 自定义实验 manifest 缺 `version`；`type` 是 `quiz`（自定义实验没有现成的合格样例，请另外写一个合格的 `tools/tests/fixtures/content/experiment-manifest.json` 作为 base）
  14. 发布清单的 `release_id` 不是 `rel_` 加 64 位小写十六进制；文件条目缺 `sha256`；`bytes` 是小数；缺 `engine_min`；路径含 `..`；路径含反斜杠
  15. 结构化活动缺 `engine`；`engine` 为 0
  16. 误区引用写成大写字母或含空格（两种合法写法以外的格式）
- 可以多写，但不要少写。

## 约束

- 规格是唯一依据。规格里没写的，不要自己加字段；觉得规格不清楚、不合理或互相矛盾，**不要自己改**，写进交付包「说明」里的「疑问」。
- 规格第 7 节说明了哪些规则写在 schema 里、哪些留给 CI。留给 CI 的那些（`shaded` 不超过 `parts`、提示泄露答案、SVG 白名单、路径大小写冲突、引擎等级是否够用、跨文件引用、发布门禁、引用闭包）**不要**在 schema 里勉强实现。
- 「恰好一个正确选项」用 2020-12 的 `contains` 加 `minContains`、`maxContains` 表达。
- 长度限制用 `maxLength`，它按字符数算，一个汉字算一个。
- 样例内容是真给三年级孩子看的：科学上准确，句子短，说具体的事，不出现「学习」二字。分数写成 `1/4` 这样，界面会排成上下结构。
- 所有文本文件用 UTF-8、LF 换行。

## 验收标准

- [ ] 四个 schema 都通过 `check_schema`
- [ ] 全部合格样例通过校验；全部不合格样例被拦下，并且每个都只改了一处
- [ ] 不合格样例覆盖上面列出的 16 类，每类至少一项
- [ ] `schemas/knode.schema.json` 和 `schemas/activity.schema.json` 除了规定的改动，其余内容和原文完全一致
- [ ] 挑战覆盖了知识点的全部误区；三种答案类型都有
- [ ] `python -m unittest discover -s tools/tests` 全部通过

## 交付格式（必须遵守）

本任务的文件清单（按这个顺序）：

```
schemas/activity-def.schema.json
schemas/release.schema.json
schemas/knode.schema.json
schemas/activity.schema.json
tools/tests/fixtures/content/nodes/num/math.number.fraction-intro.yaml
tools/tests/fixtures/content/activities/act.explain.fraction-intro-01/activity.yaml
tools/tests/fixtures/content/activities/act.quiz.fraction-intro-01/activity.yaml
tools/tests/fixtures/content/activities/act.reflection.fraction-intro-01/activity.yaml
tools/tests/fixtures/content/release.json
tools/tests/fixtures/content/experiment-manifest.json
tools/tests/fixtures/invalid/content.json
tools/tests/test_content_schemas.py
```

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
