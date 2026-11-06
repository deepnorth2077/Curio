# 规格：内容格式与不可变发布（CURIO-002）

- 状态：提议，等外部审阅
- 依据：ADR-002（结构化内容优先）、ADR-003（发布不可变）、`docs/domain.md`
- 实现任务：CURIO-002a（schema 和样例内容）、CURIO-002b（发布构建器和 CI 校验）

这份规格回答三个问题：内容文件长什么样、怎么校验、怎么打成不可变的发布包。界面怎么显示这些内容，属于活动引擎（CURIO-005），不在这里。

## 1. 目录

```
content/
  nodes/<theme>/<知识点 id>.yaml              知识点卡（knode/1）
  activities/<活动 id>/activity.yaml          结构化活动（activity-def/1）
  activities/<活动 id>/manifest.yaml          自定义实验的描述（activity/1.1 契约）
  activities/<活动 id>/index.html             自定义实验的实现
  assets/<子目录>/<文件名>.svg                  配图等静态文件
```

- 一个活动目录里，**要么**只有 `activity.yaml`（结构化活动），**要么**是 `manifest.yaml` + `index.html`（自定义实验），不能混用。
- 所有文本文件用 UTF-8、LF 换行。仓库的 `.gitattributes` 强制 LF；构建器遇到含 CR 的文件直接报错。这样同一份内容在任何电脑上算出的哈希都一样。

## 2. 知识点卡（knode/1）

格式不变，见 `schemas/knode.schema.json`。新增一个可选字段：

| 字段 | 说明 |
| --- | --- |
| `sources` | 出处列表，每项 `{type, ref, url?}`。`type` 是 `curriculum`（课标）、`textbook`（教材）、`reference`（其他资料）。科学事实、数据类的内容必须注明出处 |

误区 `misconceptions` 的每一项有 `id` 和 `text`。`id` 在同一个知识点内唯一，用小写字母、数字和连字符。题目和实验通过这个 `id` 引用误区。

## 3. 结构化活动（activity-def/1）

讲解、挑战（测验）、反思这三类活动，内容全部是数据，由平台的通用引擎显示和判分。

### 3.1 公共字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | ✅ | `act.<kind>.<短名>`，例如 `act.quiz.fraction-intro-01`。必须和目录名一致 |
| `schema` | ✅ | 固定为 `activity-def/1` |
| `kind` | ✅ | `explain`（讲解）、`quiz`（挑战）、`reflection`（反思） |
| `version` | ✅ | 正整数。改内容就加一 |
| `title` | ✅ | 给孩子看的标题，不超过 20 个字 |
| `targets` | ✅ | 针对的知识点 id 列表，至少一个 |
| `age_band` | ✅ | 例如 `G3-4` |
| `duration_min` | ✅ | 预计分钟数，1～30 |
| `review` | ✅ | `pending`、`claude-reviewed`、`approved` |
| `sources` | | 出处，格式同知识点卡 |
| `body` | ✅ | 按 `kind` 不同，见下 |

### 3.2 题目（item）

挑战里的每道题，以及讲解中途的小问题，都用同一种结构：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | ✅ | 活动内唯一，例如 `q1` |
| `stem` | ✅ | 题干，不超过 80 个字 |
| `figure` | | 配图，见 3.6 |
| `answer` | ✅ | 答案和判定方式，见 3.3 |
| `hints` | ✅ | 提示阶梯，1～3 条，从轻到重，见 3.4 |
| `feedback` | | `{correct, wrong}`：答对、答错时给孩子看的话。不填就用引擎默认的 |

### 3.3 答案

第一版支持三种答案，每题只有一个正确答案。

**选择题**

```yaml
answer:
  type: choice
  choices:
    - {id: a, text: "1/4", correct: true}
    - {id: b, text: "1/3", misconception: part-vs-rest, feedback: 涂色的 1 份要和「一共 4 份」比。}
    - {id: c, text: "4/1", misconception: flip}
```

- 2～5 个选项，恰好一个 `correct: true`。
- 错误选项可以带 `misconception`（误区 id）和 `feedback`。

**数字题**

```yaml
answer:
  type: number
  value: 18
  tolerance: 0          # 允许的误差，默认 0
  unit: 厘米             # 可选，只用于显示
  common_wrong:
    - {value: 9, misconception: half-perimeter, feedback: 长方形有两条长、两条宽。}
```

**分数题**

```yaml
answer:
  type: fraction
  numerator: 1
  denominator: 4
  accept_equivalent: false    # true 时 2/8 也算对
  common_wrong:
    - {numerator: 1, denominator: 3, misconception: part-vs-rest}
```

孩子输入 `1/4` 或 `4分之1` 都能识别，由引擎负责解析。

### 3.4 提示阶梯（hint ladder）

每道题 1～3 条提示，从轻到重。规则：

- 最后一条也**不能直接说出答案**。CI 做一个保守的检查：选择题的最后一条提示里不能出现正确选项的原文；数字题、分数题的最后一条提示里不能出现正确答案的数字写法。
- 提示用完以后，引擎会给出答案和解释，这一步不由提示负责。

### 3.5 三种活动的 body

**讲解（explain）**：3～20 个步骤，按顺序显示。

```yaml
body:
  steps:
    - {type: text, text: 一块蛋糕，平均切成 4 份。}
    - {type: figure, figure: {type: pie, parts: 4, shaded: 1}, caption: 涂色的是其中 1 份。}
    - {type: check, item: {id: c1, stem: …, answer: …, hints: […]}}
```

`check` 是讲解中途的小问题，结构和 3.2 的题目一样。

**挑战（quiz）**

```yaml
body:
  items: [ …题目… ]
  shuffle: true     # 是否打乱题目顺序，默认 false
```

至少 1 道题；**发布前**至少 5 道（见第 5 节）。

**反思（reflection）**

```yaml
body:
  prompt: 用一句话说说你发现了什么。
  starters: [我发现……, 原来……]    # 可选，给不知道怎么开头的孩子
  max_chars: 120
```

### 3.6 配图

第一版支持五种，由引擎画成手绘风格：

| `type` | 参数 | 用途 |
| --- | --- | --- |
| `pie` | `parts`（2～12）、`shaded`（0～parts） | 圆平均分成几份 |
| `rect` | `parts`（2～12）、`shaded`、`direction`（`h` 或 `v`） | 长方形平均分成几份 |
| `rect-unequal` | `widths`（2～6 个正整数）、`shaded`（下标列表） | 没有平均分的长方形，用来考「平均分」这个误区 |
| `number-line` | `from`、`to`、`step`、`marks`（`{at, label}` 列表） | 数轴 |
| `svg` | `src`（`content/assets/` 下的 `.svg` 文件） | 以上画不了的图 |

SVG 文件必须是「干净」的：不能有 `<script>`、`<foreignObject>`、`on…` 事件属性、外部链接（`href` 只能指向文件内的 `#id`）。CI 检查。

### 3.7 文字规则

- 纯文本，不允许 HTML。分数写成 `1/4`，由引擎排成上下结构。
- 给孩子看的字段（`title`、`stem`、`choices.text`、`feedback`、`hints`、`steps.text`、`caption`、`prompt`、`starters`）不出现「学习」二字。
- 题干不超过 80 个字，提示和反馈不超过 60 个字。

## 4. 自定义实验

只有通用引擎表达不了的模拟和实验，才用「`manifest.yaml` + `index.html`」，消息协议见 `docs/activity-contract.md`。相对现有格式的变化：

- 新增必填字段 `version`（正整数）。
- `type` 只允许 `experiment`（实验）或 `simulation`（模拟）。讲解、测验一律用结构化活动。
- `misconceptions` 继续是**声明**：实验没有题目数据，覆盖关系只能由 manifest 声明，并在审核时人工核对。

## 5. 校验规则（CI）

| 规则 | 说明 |
| --- | --- |
| 形态 | 活动目录要么是结构化（只有 `activity.yaml`），要么是自定义（`manifest.yaml` + `index.html`） |
| schema | 结构化活动按 `kind` 校验 body；自定义实验按 activity/1.1 的 manifest 校验 |
| 引用 | 知识点的 `activities` 和活动的 `targets` 双向一致；题目里引用的误区 id 必须出自目标知识点；`svg` 配图引用的文件必须存在 |
| 题目 | 选择题恰好一个正确选项；同一活动内题目 id 唯一；提示阶梯的保守检查（3.4） |
| 文字 | 3.7 的字数和用词规则 |
| SVG | 3.6 的「干净」规则 |
| 误区覆盖 | **从数据计算**：结构化活动里，被错误选项或 `common_wrong` 引用过的误区，算作已覆盖；自定义实验以 manifest 声明为准 |
| 发布门禁 | 知识点 `published` 时：所有活动 `approved`；至少一个 `explain` 和一个 `quiz`；每个 `quiz` 至少 5 道题；每个误区都已覆盖 |

## 6. 不可变发布（release/1）

### 6.1 发布清单

构建器读取 `content/`，把通过发布门禁的内容打成一份清单 `release.json`：

```json
{
  "schema": "release/1",
  "release_id": "rel_<64 位十六进制>",
  "content_hash": "<64 位十六进制>",
  "source_commit": "<40 位十六进制，只作参考>",
  "nodes": [{"id": "…", "version": 1, "path": "content/nodes/num/….yaml", "sha256": "…"}],
  "activities": [{"id": "…", "version": 1, "kind": "quiz", "files": [{"path": "…", "sha256": "…", "bytes": 1234}]}],
  "assets": [{"path": "content/assets/….svg", "sha256": "…", "bytes": 567}]
}
```

- **收录范围**：只收 `published` 的知识点、它们引用的活动（必须 `approved`），以及这些活动引用的配图文件。草稿不进发布。
- 自定义实验的 `kind` 写成它的 `type`（`experiment` 或 `simulation`）。

### 6.2 哈希怎么算

1. 每个文件：对仓库里的原始字节算 SHA-256（文件已保证是 LF）。
2. 三个列表各自排序：`nodes`、`activities` 按 `id`，`files`、`assets` 按 `path`。
3. 把 `{"nodes": …, "activities": …, "assets": …}` 转成**规范 JSON**：键按字母排序，不留空白（分隔符为 `,` 和 `:`），不转义非 ASCII 字符，编码为 UTF-8。清单里只有字符串和整数，没有小数，避免浮点数写法不一致。用 Python 写就是 `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`。
4. `content_hash` = 上一步字节的 SHA-256；`release_id` = `rel_` + `content_hash`。

`source_commit` 和 `release_id` 本身都不参与哈希。所以同样的内容，不管哪天、在哪台电脑、从哪个提交构建，`release_id` 都一样。

### 6.3 构建产物

构建器输出一个目录：`release.json`，加上清单里每个文件（按原路径存放）。怎么托管、怎么缓存，属于 CURIO-007。

### 6.4 部署记录（deploy/1）

「现在生效的是哪个发布」由一条只追加的部署记录表示，每次切换追加一条：

| 字段 | 说明 |
| --- | --- |
| `deployment_id` | `dep_<ULID>` |
| `release_id` | 指向的发布 |
| `state` | `preview`（预览）、`active`（生效）、`rolled-back`（被回滚） |
| `at` | UTC 时间 |
| `by` | 谁操作的（`claude` 或 `luka`） |
| `note` | 一句话说明 |

当前生效的发布 = 最后一条 `state: active` 的记录。回滚 = 追加一条指向旧发布的 `active` 记录。发布本身从不改动。存放方式属于 CURIO-007。

## 7. 和现有约定的关系

- 原型里的「分蛋糕小挑战」改写成结构化挑战，作为第一份样例内容（CURIO-002a）。样例先放在 `tools/tests/fixtures/content/`（目录结构和 `content/` 相同），作为构建器和 CI 的测试夹具；等 CURIO-002b 合入、CI 认得结构化活动之后，真正的知识点才进 `content/`（CURIO-009a）。
- **哪些规则写在 schema 里，哪些写在 CI 里**：单个文件内部能表达的（字段、类型、枚举、长度、个数、「恰好一个正确选项」）写在 schema 里；要跨文件或要做计算的（引用、`shaded` 不超过 `parts`、提示泄露答案、SVG 是否干净、发布门禁）写在 CI 里。
- 现有 CI 里「每个活动都要有 `index.html`」的过渡规则，在 CURIO-002b 合入时改为按形态校验（见 ADR-002「过渡期」）。

## 8. 任务拆分

| 任务 | 做什么 | 交付 | 依赖 |
| --- | --- | --- | --- |
| **CURIO-002a** | 写 schema 和样例内容 | `schemas/activity-def.schema.json`、`schemas/release.schema.json`、更新 `schemas/activity.schema.json`（加 `version`，限制 `type`）、`schemas/knode.schema.json`（加 `sources`）；样例（放在 `tools/tests/fixtures/content/`）：「分数的初步认识」知识点卡及其讲解、挑战、反思各一个；schema 的正反测试 | 本规格合入 |
| **CURIO-002b** | 写发布构建器，并把第 5 节的校验加进 CI | `tools/build_release.py`、`tools/ci_checks.py` 的修改、测试（含「同一内容构建两次哈希一致」「文件顺序不同哈希一致」「草稿不进发布」） | CURIO-002a 合入 |
