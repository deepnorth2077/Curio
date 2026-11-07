# 规格：内容格式与不可变发布（CURIO-002）

- 状态：提议，第 3 稿（已按两轮外部审阅修改，见 `docs/reviews/pr-21.md`）
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
- **路径**：只用正斜杠；每一段只含 ASCII 字母、数字、点、下划线、连字符，不以点开头；不允许 `.`、`..`。两个路径只差大小写的，构建器报错（有的电脑不区分大小写，会把它们当成同一个文件）。路径全是 ASCII，所以不存在 Unicode 规范化（NFC、NFD）的差异。
- **正文不做 Unicode 规范化**：哈希按文件的原始字节算，构建器不改动任何文字。审核过的是什么字节，发布的就是什么字节。

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
| `engine` | ✅ | 显示这个活动至少需要几级引擎，正整数，见 3.8 |
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
- 活动只针对一个知识点时，误区写它的 `id`（例如 `flip`）；针对多个知识点时，写成 `<知识点 id>:<误区 id>`，避免两个知识点的误区同名时分不清。数字题、分数题的 `common_wrong` 同理。

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

- 最后一条也**不能直接说出答案**。CI 分两层检查：
  - **数字题、分数题：不通过就报错。**任何一条提示里出现正确答案的数字写法（例如 `18`、`1/4`、`4分之1`、`四分之一`），CI 报错。数字按「前后不是数字」匹配，`18` 不会命中 `180`。
  - **选择题：只提醒。**正确选项的原文出现在任何一条提示里时，CI 给出警告，由审核者判断是不是真的泄露了答案。选项很短（例如「是」「一样大」）时很容易误报，所以不拦截。
- 两层都要有测试：「确实泄露」的样例和「含有相同字但没有泄露」的样例。
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

讲解可以选择**领航员对话**的样子显示（2026-11-06 加入，先在「生命的说明书」星座试用）：

```yaml
body:
  style: tutor        # 可选：plain（默认，按页显示）或 tutor（领航员对话）
  steps: [ … ]
```

- `style: tutor` 时，引擎把讲解显示成领航员和舰长的对话：`text` 步骤是领航员说的话；`figure` 是领航员拿出来给舰长看的图；`check` 是领航员停下来提问，错误选项的 `feedback` 是领航员针对这个误区的回应，提示阶梯照常可用。
- 领航员说的 `feedback` 和 `hints` 照样受 3.7 的用词和字数规则约束。提示阶梯和普通讲解一样一级一级给：舰长点一次「要个提示」（和挑战里的按钮同名），领航员说下一级，不一次全说出来。
- 这只是显示方式，内容结构和判分都和普通讲解一样。所以 `tutor` 不提高引擎等级：引擎不认识 `tutor` 时，按 `plain` 显示，内容照样能看。
- 对话模式下，引擎始终提供「我有个问题」的入口，孩子的问题记成 `question.asked`，进信号站（事件规格 3.2）。
- 写成对话时，每个 `text` 步骤只说一两句话，像对着孩子说话。

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

SVG 文件按**白名单**检查，名单以外的一律报错（CI 检查）：

- **元素**：`svg`、`g`、`defs`、`title`、`desc`、`path`、`rect`、`circle`、`ellipse`、`line`、`polyline`、`polygon`、`text`、`tspan`、`use`、`linearGradient`、`radialGradient`、`stop`、`clipPath`。
- **属性**：几何和外观属性（`x`、`y`、`width`、`height`、`d`、`points`、`cx`、`cy`、`r`、`rx`、`ry`、`x1`、`y1`、`x2`、`y2`、`transform`、`viewBox`、`fill`、`stroke`、`stroke-width`、`stroke-linecap`、`stroke-linejoin`、`stroke-dasharray`、`opacity`、`fill-opacity`、`stroke-opacity`、`font-size`、`font-weight`、`text-anchor`、`dominant-baseline`、`offset`、`stop-color`、`stop-opacity`、`gradientUnits`、`clip-path`、`id`、`class`、`xmlns`、`aria-label`、`role`），以及 `href` / `xlink:href`。
- `href`、`xlink:href` 只能是文件内的 `#id`；属性值里的 `url(…)` 只能是 `url(#id)`。
- 不允许 `<style>` 元素和 `style` 属性（这样就不会有 CSS 里的 `url()`、`@import`）；不允许 XML 处理指令（第一行的 `<?xml …?>` 声明除外）、`<!DOCTYPE>` 和实体。

### 3.7 文字规则

- 纯文本，不允许 HTML。分数写成 `1/4`，由引擎排成上下结构。
- 给孩子看的字段（`title`、`stem`、`choices.text`、`feedback`、`hints`、`steps.text`、`caption`、`prompt`、`starters`）不出现「学习」二字。
- 题干不超过 80 个字，提示和反馈不超过 60 个字。

### 3.8 引擎等级

共享引擎会不断增加能力（以后会有多空题、带单位的物理量、表达式、作图题）。离线的旧设备可能还在用旧引擎，拿到新内容会显示不出来。所以：

- 每个结构化活动写明 `engine`：显示它至少需要几级引擎。
- 发布清单写明 `engine_min`：收录的活动里最大的 `engine`。
- 设备上的引擎比 `engine_min` 低时，**不切换**到这个发布，继续用当前发布，并提示「需要更新」。
- 每增加一种 `kind`、答案 `type` 或配图 `type`，引擎等级加一，并在下表登记。现在只有第 1 级：

| 等级 | 支持 |
| --- | --- |
| 1 | `kind`：`explain`、`quiz`、`reflection`；答案：`choice`、`number`、`fraction`；配图：`pie`、`rect`、`rect-unequal`、`number-line`、`svg` |

自定义实验不需要 `engine`，它们运行在沙箱里，只依赖契约版本（manifest 的 `contract`，例如 `activity/1.1`）。发布清单的 `contracts` 列出收录的实验用到的全部契约版本；设备的宿主不支持其中任何一个时，同样**不切换**到这个发布，并提示「需要更新」。

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
| 题目 | 选择题恰好一个正确选项；同一活动内题目 id 唯一；配图 `shaded` 不超过 `parts`、下标不越界；提示泄露检查（3.4：数字题和分数题报错，选择题警告） |
| 文字 | 3.7 的字数和用词规则 |
| SVG | 3.6 的白名单 |
| 路径 | 第 1 节的路径规则，含大小写冲突 |
| 引擎 | `engine` 不低于这个活动用到的能力所需的等级（按 3.8 的表） |
| 误区覆盖 | **从数据计算**：结构化活动里，被错误选项或 `common_wrong` 引用过的误区，算作已覆盖；自定义实验以 manifest 声明为准 |
| 发布门禁 | 只看**会被收录**的活动，也就是 `approved` 的那些；`pending`、`claude-reviewed` 的活动不收录，也不阻断发布。知识点 `published` 时，它被收录的活动里：至少一个 `explain` 和一个 `quiz`；每个 `quiz` 至少 5 道题；每个误区都被覆盖。另外**引用闭包**（6.1）要成立 |

## 6. 不可变发布（release/1）

### 6.1 发布清单

构建器读取 `content/`，把通过发布门禁的内容打成一份清单 `release.json`：

```json
{
  "schema": "release/1",
  "release_id": "rel_<64 位十六进制>",
  "content_hash": "<64 位十六进制>",
  "source_commit": "<40 位十六进制，只作参考>",
  "engine_min": 1,
  "contracts": ["activity/1.1"],
  "nodes": [{"id": "…", "version": 1, "path": "content/nodes/num/….yaml", "sha256": "…", "json": {"path": "content/nodes/num/….yaml.json", "sha256": "…", "bytes": 789}}],
  "activities": [{"id": "…", "version": 1, "kind": "quiz", "files": [{"path": "…/activity.yaml", "sha256": "…", "bytes": 1234, "json": {"path": "…/activity.yaml.json", "sha256": "…", "bytes": 1100}}]}],
  "assets": [{"path": "content/assets/….svg", "sha256": "…", "bytes": 567}]
}
```

- **收录范围**：只收 `published` 的知识点、它们引用的活动里 `approved` 的那些，以及这些活动引用的配图文件。草稿知识点、没批准的活动都不进发布，也不影响其他内容的发布。所以给已发布的知识点新加一个还在审核的活动，不会卡住整个发布。
- **引用闭包**：发布包里不能有指向包外的硬引用。下面任何一条不满足，构建失败（CI 的发布门禁也检查同样的规则）：
  - 已发布知识点的每个 `prerequisites` 都必须已发布；
  - 收录的每个活动，它的**全部** `targets` 都必须已发布。共享活动的某个目标还是草稿时，要么等它发布，要么把活动拆开。
- `related` 是软引用：允许指向未发布的知识点。外壳只显示发布包里有的那些，其余的不显示。
- `engine_min`、`contracts`：见 3.8。`contracts` 按字符串排序、不重复；没有收录自定义实验时是空列表。
- 自定义实验的 `kind` 写成它的 `type`（`experiment` 或 `simulation`）。

### 6.2 哈希怎么算

1. 每个文件：对仓库里的原始字节算 SHA-256（文件已保证是 LF）。每个 `.yaml` 条目带一个 `json` 对象，是 6.3 那份 `.json` 的路径、SHA-256、字节数；它在条目里，所以也参与下一步的哈希。
2. 三个列表各自排序：`nodes`、`activities` 按 `id`，`files`、`assets` 按 `path`。
3. 把 `{"engine_min": …, "contracts": …, "nodes": …, "activities": …, "assets": …}` 转成**规范 JSON**：键按字母排序，不留空白（分隔符为 `,` 和 `:`），不转义非 ASCII 字符，编码为 UTF-8。用 Python 写就是 `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`。
   - 这样写之所以跨语言可复现，是因为清单的取值受到严格限制：只有字符串和非负整数（不超过 2^53−1；构建器把 `version: 1.0` 这类整数值的小数写法统一转成整数，否则 Python 写成 `1.0`、JavaScript 写成 `1`，哈希会不同），没有小数、布尔值和 null；所有键名、id、路径都是 ASCII，所以「按字母排序」在任何语言里都是同一个顺序（id 是 ASCII 由 schema 的正则保证：知识点 id 只有小写字母、数字、点、连字符，活动 id 同理；路径由第 1 节的规则保证）；哈希是十六进制小写。在这些限制下，结果和 JSON 规范化方案 RFC 8785 一致。
   - 发布哈希只由 Python 构建器计算。其他语言要验证时，按 RFC 8785 实现即可。
4. `content_hash` = 上一步字节的 SHA-256；`release_id` = `rel_` + `content_hash`。

`source_commit` 和 `release_id` 本身都不参与哈希。所以同样的内容，不管哪天、在哪台电脑、从哪个提交构建，`release_id` 都一样。

### 6.3 构建产物

构建器输出一个目录：`release.json`，加上清单里每个文件（按原路径存放）。怎么托管、怎么缓存，属于 CURIO-007。

浏览器没有现成的 YAML 解析器，又不引入依赖（ADR-008），所以构建器在每个 `.yaml` 文件旁边多写一份同名加 `.json` 的文件（例如 `activity.yaml.json`），外壳读它（2026-11-07 加入，竖切片 1）：

- 内容是这个 YAML 解析后的值，写成 JSON：键按字母排序，不留空白，不转义非 ASCII 字符，UTF-8 编码，末尾一个 LF。用 Python 写就是 `json.dumps(值, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"`。
- 它由 YAML 确定性地算出。审核的对象仍然是 YAML 的原始字节；清单里同时登记 YAML 和这份 JSON 的哈希，**两者都参与 `content_hash`**（6.2）。这样外壳不用解析 YAML，也能用 `release_id` 核对自己实际读到的 JSON 是不是这个发布的那一份：读到的字节数或 SHA-256 和清单对不上，就不能用。（2026-11-07 第 2 轮修订：第 1 稿说 JSON 不进清单，外部审阅指出那样 `release_id` 绑定不了浏览器读的内容，见 `docs/reviews/pr-60.md`。`release/1` 当时还没有发布过任何一份，所以直接改定义。）
- **构建只读一次文件**：审核、算哈希、转 JSON、写出都用同一份字节快照，写出前逐个核对哈希。先写进输出目录旁边的临时目录，全部写好、核对通过后再改名成输出目录；输出目录已经存在并且不是空目录时，构建失败，不覆盖。所以构建中途失败不会留下半个发布包。
- YAML 里有 JSON 表示不了的值时构建失败：没加引号的日期（YAML 会把 `2026-11-07` 读成日期）、`.inf`、`.nan`、不是字符串的键、绝对值超过 2^53−1 的整数。

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
- `tools/tests/fixtures/` 下的样例内容**只做 schema 校验和构建器测试**，不参加针对 `content/` 的 CI 规则（发布门禁、引用、地盘），CURIO-002b 要写明这一点。
- 现有 CI 里「每个活动都要有 `index.html`」的过渡规则，在 CURIO-002b 合入时改为按形态校验（见 ADR-002「过渡期」）。

## 8. 任务拆分

| 任务 | 做什么 | 交付 | 依赖 |
| --- | --- | --- | --- |
| **CURIO-002a** | 写 schema 和样例内容 | `schemas/activity-def.schema.json`、`schemas/release.schema.json`、更新 `schemas/activity.schema.json`（加 `version`，限制 `type`）、`schemas/knode.schema.json`（加 `sources`）；样例（放在 `tools/tests/fixtures/content/`）：「分数的初步认识」知识点卡及其讲解、挑战、反思各一个；schema 的正反测试 | 本规格合入 |
| **CURIO-002b** | 写发布构建器，并把第 5 节的校验加进 CI | `tools/build_release.py`、`tools/ci_checks.py` 的修改、测试（含「同一内容构建两次哈希一致」「文件顺序不同哈希一致」「草稿不进发布」「前置知识点是草稿时构建失败」「共享活动有草稿目标时构建失败」「大小写冲突的路径报错」「SVG 白名单」「提示泄露的两层检查」） | CURIO-002a 合入 |
