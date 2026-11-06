> 基于 Curio 仓库提交 `672c37513f9bf88bf60f1c320341c18d72cc6a5d` 生成 · 任务 `curio-002b` · issue #17 · 提示词版本 v1
> 交付包开头信息请照抄：`issue: #17`、`任务: curio-002b`、`提示词版本: v1`、`基于提交: 672c37513f9b`


# 任务：为「好奇号」写内容发布构建器，并按新的内容格式升级 CI 检查

## 项目背景

你在为「好奇号 Curio」工作：这是一个家庭自用的理科探索网站，陪一个孩子从小学三年级用到高中。网站运行在平板、电脑和手机的浏览器里，界面文字是简体中文。

这个平台的原则是「内容即数据」：知识点、讲解、挑战、反思都是带版本号的 YAML 数据文件，由平台的通用引擎显示和判分；只有通用引擎做不了的实验和模拟，才写成自定义的 HTML 小程序。所有内容合入仓库前都要过 CI 检查；上线时，构建器把通过检查的内容打成一份**不可变的发布包**，用内容哈希作为身份。

上一个任务（CURIO-002a）已经写好了内容格式的 schema 和第一份样例「分数的初步认识」。现在有两件事还没做，就是本任务：

1. **发布构建器**还不存在；
2. **CI 检查**还停留在旧格式上：它只认得「`manifest.yaml` + `index.html`」的自定义活动，不认得结构化活动（`activity.yaml`）。所以现在任何知识点都发布不了，测试里有一条标明「过渡期」的反例，等你恢复成正例。

## 你的角色

严谨的 Python 工具工程师，写过构建系统和代码检查工具，重视测试。

## 你需要的资料

### 1. 内容规格（唯一依据，不要改动）

> 出处：`docs/specs/content.md`（提交 `672c375`）

````text
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
  "nodes": [{"id": "…", "version": 1, "path": "content/nodes/num/….yaml", "sha256": "…"}],
  "activities": [{"id": "…", "version": 1, "kind": "quiz", "files": [{"path": "…", "sha256": "…", "bytes": 1234}]}],
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

1. 每个文件：对仓库里的原始字节算 SHA-256（文件已保证是 LF）。
2. 三个列表各自排序：`nodes`、`activities` 按 `id`，`files`、`assets` 按 `path`。
3. 把 `{"engine_min": …, "contracts": …, "nodes": …, "activities": …, "assets": …}` 转成**规范 JSON**：键按字母排序，不留空白（分隔符为 `,` 和 `:`），不转义非 ASCII 字符，编码为 UTF-8。用 Python 写就是 `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`。
   - 这样写之所以跨语言可复现，是因为清单的取值受到严格限制：只有字符串和非负整数（不超过 2^53−1），没有小数、布尔值和 null；所有键名、id、路径都是 ASCII，所以「按字母排序」在任何语言里都是同一个顺序（id 是 ASCII 由 schema 的正则保证：知识点 id 只有小写字母、数字、点、连字符，活动 id 同理；路径由第 1 节的规则保证）；哈希是十六进制小写。在这些限制下，结果和 JSON 规范化方案 RFC 8785 一致。
   - 发布哈希只由 Python 构建器计算。其他语言要验证时，按 RFC 8785 实现即可。
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
- `tools/tests/fixtures/` 下的样例内容**只做 schema 校验和构建器测试**，不参加针对 `content/` 的 CI 规则（发布门禁、引用、地盘），CURIO-002b 要写明这一点。
- 现有 CI 里「每个活动都要有 `index.html`」的过渡规则，在 CURIO-002b 合入时改为按形态校验（见 ADR-002「过渡期」）。

## 8. 任务拆分

| 任务 | 做什么 | 交付 | 依赖 |
| --- | --- | --- | --- |
| **CURIO-002a** | 写 schema 和样例内容 | `schemas/activity-def.schema.json`、`schemas/release.schema.json`、更新 `schemas/activity.schema.json`（加 `version`，限制 `type`）、`schemas/knode.schema.json`（加 `sources`）；样例（放在 `tools/tests/fixtures/content/`）：「分数的初步认识」知识点卡及其讲解、挑战、反思各一个；schema 的正反测试 | 本规格合入 |
| **CURIO-002b** | 写发布构建器，并把第 5 节的校验加进 CI | `tools/build_release.py`、`tools/ci_checks.py` 的修改、测试（含「同一内容构建两次哈希一致」「文件顺序不同哈希一致」「草稿不进发布」「前置知识点是草稿时构建失败」「共享活动有草稿目标时构建失败」「大小写冲突的路径报错」「SVG 白名单」「提示泄露的两层检查」） | CURIO-002a 合入 |
````


### 2. 术语表

> 出处：`GLOSSARY.md · 「内容」一节`（提交 `672c375`）

````text
## 内容

**知识点**：
一个可以独立掌握的概念，例如「分数的初步认识」，是星图上的一颗星。
_避免_：课、题、节点（「节点」只在图论语境下用）

**活动**：
围绕知识点的一次互动，分讲解、挑战、反思、实验、模拟五种。
_避免_：模块、练习、课件

**讲解**：
按步骤展示、中途可以穿插小问题的活动。
_避免_：教程、课文

**挑战**：
一组题目，由平台判分。
_避免_：测验、考试、作业

**反思**：
请孩子用一句话写下发现的活动。
_避免_：总结、作文

**实验**、**模拟**：
平台通用引擎做不了、需要单独编写、运行在沙箱里的互动。实验对应真实世界的操作，模拟展示看不见的过程。
_避免_：小游戏、动画

**误区**：
孩子在一个知识点上常有的错误想法，每个都有 ID，题目的错误选项会标明它对应哪个误区。
_避免_：错因、易错点

**提示阶梯**：
一道题的 1～3 条提示，从轻到重，最后一条也不直接说出答案。
_避免_：答案解析、hint

**预测 → 观察 → 解释**：
实验的三步：先猜，再看，再说为什么。前后两步由平台负责，实验只做「观察」。
_避免_：POE（只在技术文档里作为缩写）

**发布**：
一组已审核内容的快照，用内容哈希作为身份。
_避免_：版本、上线

**部署**：
「现在生效的是哪个发布」这个可以切换、可以回滚的指针。
_避免_：发布（两者不能混用）

**引擎等级**：
共享引擎支持哪些内容格式的编号。
_避免_：版本号

**宿主**：
平台里负责运行自定义活动的那部分：把活动放进沙箱、转发消息、记下事件。
_避免_：容器、播放器

**契约**：
自定义活动和宿主之间允许传递哪些消息、每条长什么样的约定，例如 activity/1.1。
_避免_：接口协议、API
````


> 出处：`GLOSSARY.md · 「协作」一节`（提交 `672c375`）

````text
## 协作

**任务文件**：
发给实现 AI 的、自成一体的提示词文件，由 `tools/make_task.py` 从已合入的提交生成。
_避免_：工单、prompt

**交付包**：
实现 AI 按固定格式交回来的全部文件和说明。
_避免_：提交、PR（这两个词只指 git 里的东西）

**收货**：
用 `tools/intake.py` 检查交付包是否完整，并记下每个文件的指纹。
_避免_：验收（「验收」指 Luka 按步骤亲自检查）

**打回**：
审核没通过，附上修改提示词，请同一个实现 AI 重交。
_避免_：拒绝、驳回

**竖切片**：
一个从内容、内核到界面都打通的窄任务，单独完成后就能演示或验收。打通全链路的第一条竖切片叫「曳光弹」。
_避免_：模块任务、分层任务

**测试接缝**：
测试观察行为的公开接口，在规格和任务文件里事先定好。
_避免_：测试点、钩子
````


### 3. 结构化活动和发布清单的 schema（已合入，不要改动）

> 出处：`schemas/activity-def.schema.json`（提交 `672c375`）

````text
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/deepnorth2077/curio/schemas/activity-def.schema.json",
  "title": "activity-def/1 · 结构化活动",
  "type": "object",
  "required": ["id", "schema", "kind", "version", "title", "targets", "age_band", "duration_min", "review", "engine", "body"],
  "additionalProperties": false,
  "properties": {
    "id": { "type": "string", "pattern": "^act\\.[a-z]+\\.[a-z0-9-]+$" },
    "schema": { "const": "activity-def/1" },
    "kind": { "enum": ["explain", "quiz", "reflection"] },
    "version": { "type": "integer", "minimum": 1 },
    "title": { "allOf": [{ "$ref": "#/$defs/childText" }], "maxLength": 20 },
    "targets": { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/nodeId" } },
    "age_band": { "type": "string", "pattern": "^G\\d{1,2}(-\\d{1,2})?$" },
    "duration_min": { "type": "integer", "minimum": 1, "maximum": 30 },
    "review": { "enum": ["pending", "claude-reviewed", "approved"] },
    "engine": { "type": "integer", "minimum": 1 },
    "sources": {
      "type": "array",
      "items": { "$ref": "#/$defs/source" }
    },
    "body": { "type": "object" }
  },
  "allOf": [
    {
      "if": { "properties": { "kind": { "const": "explain" } } },
      "then": { "properties": { "body": { "$ref": "#/$defs/explainBody" } } }
    },
    {
      "if": { "properties": { "kind": { "const": "quiz" } } },
      "then": { "properties": { "body": { "$ref": "#/$defs/quizBody" } } }
    },
    {
      "if": { "properties": { "kind": { "const": "reflection" } } },
      "then": { "properties": { "body": { "$ref": "#/$defs/reflectionBody" } } }
    }
  ],
  "$defs": {
    "nodeId": { "type": "string", "pattern": "^[a-z]+(\\.[a-z0-9-]+)+$" },
    "childText": { "type": "string", "not": { "pattern": "学习" } },
    "misconceptionRef": {
      "type": "string",
      "pattern": "^([a-z0-9-]+|[a-z]+(\\.[a-z0-9-]+)+:[a-z0-9-]+)$"
    },
    "source": {
      "type": "object",
      "required": ["type", "ref"],
      "additionalProperties": false,
      "properties": {
        "type": { "enum": ["curriculum", "textbook", "reference"] },
        "ref": { "type": "string" },
        "url": { "type": "string" }
      }
    },
    "feedback": {
      "type": "object",
      "required": ["correct", "wrong"],
      "additionalProperties": false,
      "properties": {
        "correct": { "allOf": [{ "$ref": "#/$defs/childText" }], "maxLength": 60 },
        "wrong": { "allOf": [{ "$ref": "#/$defs/childText" }], "maxLength": 60 }
      }
    },
    "figure": {
      "oneOf": [
        {
          "type": "object",
          "required": ["type", "parts", "shaded"],
          "additionalProperties": false,
          "properties": {
            "type": { "const": "pie" },
            "parts": { "type": "integer", "minimum": 2, "maximum": 12 },
            "shaded": { "type": "integer", "minimum": 0 }
          }
        },
        {
          "type": "object",
          "required": ["type", "parts", "shaded", "direction"],
          "additionalProperties": false,
          "properties": {
            "type": { "const": "rect" },
            "parts": { "type": "integer", "minimum": 2, "maximum": 12 },
            "shaded": { "type": "integer", "minimum": 0 },
            "direction": { "enum": ["h", "v"] }
          }
        },
        {
          "type": "object",
          "required": ["type", "widths", "shaded"],
          "additionalProperties": false,
          "properties": {
            "type": { "const": "rect-unequal" },
            "widths": {
              "type": "array",
              "minItems": 2,
              "maxItems": 6,
              "items": { "type": "integer", "minimum": 1 }
            },
            "shaded": {
              "type": "array",
              "uniqueItems": true,
              "items": { "type": "integer", "minimum": 0 }
            }
          }
        },
        {
          "type": "object",
          "required": ["type", "from", "to", "step", "marks"],
          "additionalProperties": false,
          "properties": {
            "type": { "const": "number-line" },
            "from": { "type": "number" },
            "to": { "type": "number" },
            "step": { "type": "number", "exclusiveMinimum": 0 },
            "marks": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["at", "label"],
                "additionalProperties": false,
                "properties": {
                  "at": { "type": "number" },
                  "label": { "type": "string" }
                }
              }
            }
          }
        },
        {
          "type": "object",
          "required": ["type", "src"],
          "additionalProperties": false,
          "properties": {
            "type": { "const": "svg" },
            "src": {
              "type": "string",
              "pattern": "^content/assets/([A-Za-z0-9_-][A-Za-z0-9._-]*/)*[A-Za-z0-9_-][A-Za-z0-9._-]*\\.svg$"
            }
          }
        }
      ]
    },
    "choiceAnswer": {
      "type": "object",
      "required": ["type", "choices"],
      "additionalProperties": false,
      "properties": {
        "type": { "const": "choice" },
        "choices": {
          "type": "array",
          "minItems": 2,
          "maxItems": 5,
          "contains": {
            "type": "object",
            "required": ["correct"],
            "properties": { "correct": { "const": true } }
          },
          "minContains": 1,
          "maxContains": 1,
          "items": {
            "type": "object",
            "required": ["id", "text"],
            "additionalProperties": false,
            "properties": {
              "id": { "type": "string" },
              "text": { "$ref": "#/$defs/childText" },
              "correct": { "type": "boolean" },
              "misconception": { "$ref": "#/$defs/misconceptionRef" },
              "feedback": { "allOf": [{ "$ref": "#/$defs/childText" }], "maxLength": 60 }
            }
          }
        }
      }
    },
    "wrongNumber": {
      "type": "object",
      "required": ["value"],
      "additionalProperties": false,
      "properties": {
        "value": { "type": "number" },
        "misconception": { "$ref": "#/$defs/misconceptionRef" },
        "feedback": { "allOf": [{ "$ref": "#/$defs/childText" }], "maxLength": 60 }
      }
    },
    "wrongFraction": {
      "type": "object",
      "required": ["numerator", "denominator"],
      "additionalProperties": false,
      "properties": {
        "numerator": { "type": "integer" },
        "denominator": { "type": "integer", "exclusiveMinimum": 0 },
        "misconception": { "$ref": "#/$defs/misconceptionRef" },
        "feedback": { "allOf": [{ "$ref": "#/$defs/childText" }], "maxLength": 60 }
      }
    },
    "numberAnswer": {
      "type": "object",
      "required": ["type", "value"],
      "additionalProperties": false,
      "properties": {
        "type": { "const": "number" },
        "value": { "type": "number" },
        "tolerance": { "type": "number", "minimum": 0, "default": 0 },
        "unit": { "type": "string" },
        "common_wrong": {
          "type": "array",
          "items": { "$ref": "#/$defs/wrongNumber" }
        }
      }
    },
    "fractionAnswer": {
      "type": "object",
      "required": ["type", "numerator", "denominator", "accept_equivalent"],
      "additionalProperties": false,
      "properties": {
        "type": { "const": "fraction" },
        "numerator": { "type": "integer" },
        "denominator": { "type": "integer", "exclusiveMinimum": 0 },
        "accept_equivalent": { "type": "boolean" },
        "common_wrong": {
          "type": "array",
          "items": { "$ref": "#/$defs/wrongFraction" }
        }
      }
    },
    "answer": {
      "oneOf": [
        { "$ref": "#/$defs/choiceAnswer" },
        { "$ref": "#/$defs/numberAnswer" },
        { "$ref": "#/$defs/fractionAnswer" }
      ]
    },
    "item": {
      "type": "object",
      "required": ["id", "stem", "answer", "hints"],
      "additionalProperties": false,
      "properties": {
        "id": { "type": "string" },
        "stem": { "allOf": [{ "$ref": "#/$defs/childText" }], "maxLength": 80 },
        "figure": { "$ref": "#/$defs/figure" },
        "answer": { "$ref": "#/$defs/answer" },
        "hints": {
          "type": "array",
          "minItems": 1,
          "maxItems": 3,
          "items": { "allOf": [{ "$ref": "#/$defs/childText" }], "maxLength": 60 }
        },
        "feedback": { "$ref": "#/$defs/feedback" }
      }
    },
    "explainBody": {
      "type": "object",
      "required": ["steps"],
      "additionalProperties": false,
      "properties": {
        "steps": {
          "type": "array",
          "minItems": 3,
          "maxItems": 20,
          "items": {
            "oneOf": [
              {
                "type": "object",
                "required": ["type", "text"],
                "additionalProperties": false,
                "properties": {
                  "type": { "const": "text" },
                  "text": { "$ref": "#/$defs/childText" }
                }
              },
              {
                "type": "object",
                "required": ["type", "figure"],
                "additionalProperties": false,
                "properties": {
                  "type": { "const": "figure" },
                  "figure": { "$ref": "#/$defs/figure" },
                  "caption": { "$ref": "#/$defs/childText" }
                }
              },
              {
                "type": "object",
                "required": ["type", "item"],
                "additionalProperties": false,
                "properties": {
                  "type": { "const": "check" },
                  "item": { "$ref": "#/$defs/item" }
                }
              }
            ]
          }
        }
      }
    },
    "quizBody": {
      "type": "object",
      "required": ["items"],
      "additionalProperties": false,
      "properties": {
        "items": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/item" }
        },
        "shuffle": { "type": "boolean", "default": false }
      }
    },
    "reflectionBody": {
      "type": "object",
      "required": ["prompt", "max_chars"],
      "additionalProperties": false,
      "properties": {
        "prompt": { "$ref": "#/$defs/childText" },
        "starters": {
          "type": "array",
          "items": { "$ref": "#/$defs/childText" }
        },
        "max_chars": { "type": "integer", "minimum": 1 }
      }
    }
  }
}
````


> 出处：`schemas/release.schema.json`（提交 `672c375`）

````text
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/deepnorth2077/curio/schemas/release.schema.json",
  "title": "release/1 · 不可变发布清单",
  "type": "object",
  "required": ["schema", "release_id", "content_hash", "source_commit", "engine_min", "contracts", "nodes", "activities", "assets"],
  "additionalProperties": false,
  "properties": {
    "schema": { "const": "release/1" },
    "release_id": { "type": "string", "pattern": "^rel_[0-9a-f]{64}$" },
    "content_hash": { "$ref": "#/$defs/sha256" },
    "source_commit": { "type": "string", "pattern": "^[0-9a-f]{40}$" },
    "engine_min": { "type": "integer", "minimum": 1 },
    "contracts": {
      "type": "array",
      "uniqueItems": true,
      "items": { "type": "string", "pattern": "^activity/[0-9]+\\.[0-9]+$" }
    },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "version", "path", "sha256"],
        "additionalProperties": false,
        "properties": {
          "id": { "$ref": "#/$defs/nodeId" },
          "version": { "type": "integer", "minimum": 1 },
          "path": { "$ref": "#/$defs/path" },
          "sha256": { "$ref": "#/$defs/sha256" }
        }
      }
    },
    "activities": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "version", "kind", "files"],
        "additionalProperties": false,
        "properties": {
          "id": { "$ref": "#/$defs/activityId" },
          "version": { "type": "integer", "minimum": 1 },
          "kind": { "enum": ["explain", "quiz", "reflection", "experiment", "simulation"] },
          "files": {
            "type": "array",
            "items": { "$ref": "#/$defs/fileEntry" }
          }
        }
      }
    },
    "assets": {
      "type": "array",
      "items": { "$ref": "#/$defs/fileEntry" }
    }
  },
  "$defs": {
    "nodeId": { "type": "string", "pattern": "^[a-z]+(\\.[a-z0-9-]+)+$" },
    "activityId": { "type": "string", "pattern": "^act\\.[a-z]+\\.[a-z0-9-]+$" },
    "sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
    "path": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-][A-Za-z0-9._-]*(/[A-Za-z0-9_-][A-Za-z0-9._-]*)*$"
    },
    "fileEntry": {
      "type": "object",
      "required": ["path", "sha256", "bytes"],
      "additionalProperties": false,
      "properties": {
        "path": { "$ref": "#/$defs/path" },
        "sha256": { "$ref": "#/$defs/sha256" },
        "bytes": { "type": "integer", "minimum": 0, "maximum": 9007199254740991 }
      }
    }
  }
}
````


### 4. 现有的 CI 检查脚本（你要修改它，交付完整的新文件）

> 出处：`tools/ci_checks.py`（提交 `672c375`）

````text
#!/usr/bin/env python3
"""好奇号 Curio 的 PR 检查。工作流见 docs/collaboration.md。

用法：python tools/ci_checks.py [仓库目录]
环境变量（GitHub Actions 自动提供，本地可手动设置）：
  BASE_REF     目标分支，默认 main
  HEAD_BRANCH  PR 的分支名，默认取当前分支
  PR_LABELS    PR 标签，用逗号分隔
依赖见 tools/requirements.txt。自测：python -m unittest discover -s tools/tests
"""
import fnmatch, json, os, re, subprocess, sys
from pathlib import Path

PROTECTED = ["schemas/*", "docs/*", "tools/*", ".github/*", "AGENTS.md", "CLAUDE.md", "README.md", "GLOSSARY.md", "prompts/module-template.md", "prompts/task-template.md"]
BRANCH_KINDS = ["kp/", "arch/", "feat/", "fix/", "chore/"]
OVERRIDE_LABEL = "越界-已批准"
KID_FACING_NODE = ["title", "driving_question", "lenses"]
KID_FACING_ACT = ["title", "predict", "explain"]
FORBIDDEN_WORD = "学习"
PUBLISH_REQUIRED_TYPES = ["explain", "quiz"]


class Result:
    def __init__(self):
        self.errors, self.warnings, self.info = [], [], []

    def err(self, msg, file=None): self.errors.append((file, msg))
    def warn(self, msg, file=None): self.warnings.append((file, msg))


def git(repo, *args, check=False):
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p


def match(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def load_yaml_text(text):
    import yaml
    return yaml.safe_load(text)


def run(repo, base="origin/main", branch="", labels=()):
    """对 repo 的 HEAD 相对 base 做全部检查，返回 Result。"""
    repo = Path(repo)
    r = Result()
    labels = set(labels)
    override = OVERRIDE_LABEL in labels

    diff = git(repo, "diff", "--name-status", "-M", f"{base}...HEAD")
    if diff.returncode != 0:
        raise RuntimeError(f"无法和 {base} 比较：{diff.stderr.strip()}")
    changes = []  # (status, path, old_path)
    for line in diff.stdout.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0]:
            continue
        st = parts[0][0]
        changes.append(("R", parts[2], parts[1]) if st == "R" else (st, parts[1], None))
    changed = [p for _, p, _ in changes] + [o for _, _, o in changes if o]
    r.info.append(f"分支：{branch}　对比：{base}　改动文件：{len(changed)}　标签：{', '.join(sorted(labels)) or '无'}")

    def base_text(path):
        p = git(repo, "show", f"{base}:{path}")
        return p.stdout if p.returncode == 0 else None

    def manifest_targets(act_dir):
        """活动归属：先看当前版本的 manifest，被删掉时看 base 里的版本。"""
        for text in ((repo / act_dir / "manifest.yaml").read_text(encoding="utf-8") if (repo / act_dir / "manifest.yaml").exists() else None,
                     base_text(f"{act_dir}/manifest.yaml")):
            if text is None:
                continue
            try:
                d = load_yaml_text(text)
            except Exception:
                return None
            return d.get("targets", []) if isinstance(d, dict) else None
        return None

    # ---------- 1. 地盘检查 ----------
    prefix = branch.split("/", 1)[0] + "/" if "/" in branch else branch
    if prefix not in BRANCH_KINDS:
        r.err(f"分支名「{branch}」不符合规则，必须以 {'、'.join(BRANCH_KINDS)} 开头（见 docs/collaboration.md）")
    elif prefix != "arch/":
        node_id = branch.split("/", 1)[1] if prefix == "kp/" else None
        if node_id is not None:
            exists = list((repo / "content/nodes").rglob(f"{node_id}.yaml")) if (repo / "content/nodes").exists() else []
            in_base = any(p.endswith(f"/{node_id}.yaml") for p in git(repo, "ls-tree", "-r", "--name-only", base, "content/nodes").stdout.splitlines())
            if not exists and not in_base:
                r.err(f"分支名里的知识点「{node_id}」不存在。知识点分支一律叫 kp/<知识点 id>，改版也用同一个名字")
        for p in changed:
            shared = None
            if prefix == "kp/":
                ok = (p.startswith("content/") or fnmatch.fnmatch(p, "prompts/act.*.md")) and not match(p, PROTECTED)
                targets = None
                if ok and p.startswith("content/nodes/"):
                    ok = Path(p).stem == node_id
                elif ok and p.startswith("content/activities/"):
                    parts = Path(p).parts
                    targets = manifest_targets("/".join(parts[:3])) if len(parts) >= 3 else None
                elif ok and p.startswith("content/"):
                    ok = False
                elif ok and p.startswith("prompts/"):
                    targets = manifest_targets(f"content/activities/{Path(p).stem}")
                if ok and (p.startswith("content/activities/") or p.startswith("prompts/")):
                    # kp/ 分支只能改「只针对这一个知识点」的活动；共享活动会影响别的知识点，要单独开 PR
                    ok = isinstance(targets, list) and targets == [node_id]
                    if isinstance(targets, list) and node_id in targets and len(targets) > 1:
                        shared = targets
            else:
                ok = not match(p, PROTECTED) and not p.startswith("content/")
            if not ok and shared:
                msg = (f"这是共享活动，同时影响 {'、'.join(shared)}。kp/ 分支只能改只针对 {node_id} 的活动；"
                       f"共享活动要单独开 PR，覆盖所有受影响知识点的审核和试玩，并在征得 Luka 同意后加「{OVERRIDE_LABEL}」标签")
                if override:
                    r.warn(f"共享活动改动（已由「{OVERRIDE_LABEL}」标签放行），受影响的知识点：{'、'.join(shared)}", p)
                else:
                    r.err(msg, p)
            elif not ok:
                if override:
                    r.warn(f"越界改动（已由「{OVERRIDE_LABEL}」标签放行）：{p}", p)
                else:
                    r.err(f"分支「{branch}」不能改这个文件。确需修改，先在对话里征得 Luka 同意，再给 PR 加「{OVERRIDE_LABEL}」标签并在评论里注明", p)

    # ---------- 2. 规格校验 ----------
    from jsonschema import Draft202012Validator
    schemas = {}
    for f in sorted((repo / "schemas").glob("*.schema.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(s)
            schemas[f.name] = s
        except Exception as e:
            r.err(f"不是合法的 JSON Schema：{e}", rel(repo, f))

    def validate(doc, schema_name, path):
        if schema_name not in schemas or doc is None:
            return
        for e in Draft202012Validator(schemas[schema_name]).iter_errors(doc):
            loc = "/".join(str(x) for x in e.absolute_path) or "(根)"
            r.err(f"{loc}：{e.message}", rel(repo, path))

    def load(path):
        try:
            return load_yaml_text(path.read_text(encoding="utf-8"))
        except Exception as e:
            r.err(f"YAML 解析失败：{e}", rel(repo, path))
            return None

    nodes, acts = {}, {}
    for f in sorted((repo / "content/nodes").rglob("*.yaml")) if (repo / "content/nodes").exists() else []:
        d = load(f)
        validate(d, "knode.schema.json", f)
        if isinstance(d, dict) and "id" in d:
            if f.stem != d["id"]:
                r.err(f"文件名必须和 id 一致：{d['id']}.yaml", rel(repo, f))
            if d["id"] in nodes:
                r.err(f"知识点 ID 重复：{d['id']}", rel(repo, f))
            nodes[d["id"]] = (f, d)
    for f in sorted((repo / "content/activities").glob("*/manifest.yaml")) if (repo / "content/activities").exists() else []:
        d = load(f)
        validate(d, "activity.schema.json", f)
        if isinstance(d, dict) and "id" in d:
            if f.parent.name != d["id"]:
                r.err(f"活动目录名必须和 id 一致：content/activities/{d['id']}/", rel(repo, f))
            if d["id"] in acts:
                r.err(f"活动 ID 重复：{d['id']}", rel(repo, f))
            acts[d["id"]] = (f, d)
            if not (f.parent / "index.html").exists():
                r.err("缺少 index.html", rel(repo, f))

    # 引用：知识点之间、知识点和活动之间（双向）
    for nid, (f, d) in nodes.items():
        for p in d.get("prerequisites", []) + d.get("related", []):
            if p not in nodes:
                r.err(f"引用了不存在的知识点：{p}", rel(repo, f))
        for a in d.get("activities", []):
            if a not in acts:
                r.err(f"activities 里的活动不存在：{a}", rel(repo, f))
            elif nid not in acts[a][1].get("targets", []):
                r.err(f"活动 {a} 的 targets 里没有这个知识点，两边要互相写上", rel(repo, f))
    for aid, (f, d) in acts.items():
        for t in d.get("targets", []):
            if t not in nodes:
                r.err(f"targets 指向不存在的知识点：{t}", rel(repo, f))
            elif aid not in nodes[t][1].get("activities", []):
                r.err(f"知识点 {t} 的 activities 里没有这个活动，两边要互相写上", rel(repo, f))
        target_mis = {m["id"] for t in d.get("targets", []) if t in nodes for m in nodes[t][1].get("misconceptions", []) if isinstance(m, dict) and "id" in m}
        for m in d.get("misconceptions", []):
            if m not in target_mis:
                r.err(f"misconceptions 里的误区 {m} 不在目标知识点的误区列表里", rel(repo, f))

    # 前置关系无环
    state = {}
    def dfs(n, stack):
        state[n] = 1
        for p in nodes[n][1].get("prerequisites", []):
            if p not in nodes:
                continue
            if state.get(p) == 1:
                r.err(f"前置关系有环：{' → '.join(stack + [p])}", rel(repo, nodes[n][0]))
                continue
            if not state.get(p):
                dfs(p, stack + [p])
        state[n] = 2
    for n in nodes:
        if not state.get(n):
            dfs(n, [n])

    # 发布门禁
    for nid, (f, d) in nodes.items():
        if d.get("status") != "published":
            continue
        own = [acts[a][1] for a in d.get("activities", []) if a in acts]
        for a in d.get("activities", []):
            if a in acts and acts[a][1].get("review") != "approved":
                r.err(f"已发布的知识点只能引用已批准（review: approved）的活动，{a} 还是 {acts[a][1].get('review')}", rel(repo, f))
        types = {a.get("type") for a in own}
        for t in PUBLISH_REQUIRED_TYPES:
            if t not in types:
                r.err(f"发布前必须至少有一个 {t} 类活动", rel(repo, f))
        covered = {m for a in own for m in a.get("misconceptions", [])}
        for m in d.get("misconceptions", []):
            mid = m.get("id") if isinstance(m, dict) else None
            if mid and mid not in covered:
                r.err(f"误区 {mid} 还没有任何活动针对，不能发布", rel(repo, f))

    # ---------- 3. ID 检查 ----------
    for st, p, old in changes:
        src = old or p
        is_node = src.startswith("content/nodes/") and src.endswith(".yaml")
        is_act = src.startswith("content/activities/") and src.endswith("/manifest.yaml")
        if not (is_node or is_act):
            continue
        if st in ("D", "R"):
            msg = f"删除或改名了已有的{'知识点' if is_node else '活动'}文件：{src}。ID 永不改动"
            r.warn(msg + "（已放行）", src) if override else r.err(msg, src)
            continue
        if st == "M":
            def yaml_id(text):
                try:
                    d = load_yaml_text(text or "")
                except Exception:
                    return None
                return d.get("id") if isinstance(d, dict) else None
            old_id = yaml_id(base_text(src))
            new_id = yaml_id((repo / p).read_text(encoding="utf-8"))
            if old_id is not None and old_id != new_id:
                r.err(f"id 从 {old_id} 改成了 {new_id}。ID 永不改动", p)

    # ---------- 4. 文案检查 ----------
    for nid, (f, d) in nodes.items():
        for k in KID_FACING_NODE:
            if any(FORBIDDEN_WORD in t for t in texts(d.get(k))):
                r.err(f"给孩子看的「{k}」里出现了「{FORBIDDEN_WORD}」", rel(repo, f))
    for aid, (f, d) in acts.items():
        for k in KID_FACING_ACT:
            if any(FORBIDDEN_WORD in t for t in texts(d.get(k))):
                r.err(f"给孩子看的「{k}」里出现了「{FORBIDDEN_WORD}」", rel(repo, f))
        html = f.parent / "index.html"
        if html.exists():
            visible = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", html.read_text(encoding="utf-8"), flags=re.S | re.I)
            visible = re.sub(r"<[^>]+>", " ", visible)
            if FORBIDDEN_WORD in visible:
                r.err(f"页面文字里出现了「{FORBIDDEN_WORD}」", rel(repo, html))

    # ---------- 5. 署名提醒 ----------
    log = git(repo, "log", f"{base}..HEAD", "--format=%h%x00%s%x00%B%x1e").stdout
    for block in log.split("\x1e"):
        block = block.strip()
        if not block:
            continue
        sha, subject, body = (block.split("\x00") + ["", ""])[:3]
        if not re.search(r"^(Implemented-By|Agent|Co-Authored-By):", body, re.M | re.I):
            r.warn(f"提交 {sha}「{subject}」没有署名（Implemented-By:、Agent: 或 Co-Authored-By:）")

    r.info.append(f"知识点 {len(nodes)} 个，活动 {len(acts)} 个")
    return r


def rel(repo, path):
    try:
        return str(Path(path).resolve().relative_to(Path(repo).resolve()))
    except ValueError:
        return str(path)


def texts(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from texts(x)
    elif isinstance(v, list):
        for x in v:
            yield from texts(x)


def main():
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    base = "origin/" + os.environ.get("BASE_REF", "main")
    branch = os.environ.get("HEAD_BRANCH") or git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    labels = {l.strip() for l in os.environ.get("PR_LABELS", "").split(",") if l.strip()}
    try:
        r = run(repo, base, branch, labels)
    except RuntimeError as e:
        print(f"检查没有运行：{e}")
        print(f"本地运行前先执行：git fetch origin {base.split('/', 1)[1]}:refs/remotes/{base}")
        return 2
    for line in r.info:
        print(line)
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    for kind, items in (("warning", r.warnings), ("error", r.errors)):
        for f, msg in items:
            if gha:
                print(f"::{kind}{' file=' + f if f else ''}::{msg}")
            else:
                print(f"[{'提醒' if kind == 'warning' else '错误'}] {f + '：' if f else ''}{msg}")
    print("通过" if not r.errors else f"未通过：{len(r.errors)} 个错误")
    return 1 if r.errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
````


### 5. 现有的 CI 检查测试（你要修改它，交付完整的新文件）

> 出处：`tools/tests/test_ci_checks.py`（提交 `672c375`）

````text
"""tools/ci_checks.py 的正反测试。运行：python -m unittest discover -s tools/tests"""
import os, shutil, subprocess, sys, tempfile, textwrap, unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import ci_checks  # noqa: E402


def node(nid, status="draft", activities=(), mis=(), prereq=(), dq="一块蛋糕平均分给 3 个人，每人分到多少？", theme="num"):
    mis_y = "".join(f"\n  - {{id: {m}, text: 说明}}" for m in mis)
    return textwrap.dedent(f"""\
        id: {nid}
        schema: knode/1
        title: 测试知识点
        subjects: [math]
        theme: {theme}
        grade: G3
        prerequisites: [{', '.join(prereq)}]
        driving_question: {dq}
        activities: [{', '.join(activities)}]
        status: {status}
        version: 1
        """) + (f"misconceptions:{mis_y}\n" if mis else "")


def activity(aid, targets, type_="experiment", review="pending", mis=(), extra=""):
    return textwrap.dedent(f"""\
        id: {aid}
        contract: activity/1.1
        type: {type_}
        version: 1
        title: 测试活动
        targets: [{', '.join(targets)}]
        age_band: G3-4
        entry: index.html
        pedagogy: hint-ladder
        emits: [started, answered]
        review: {review}
        misconceptions: [{', '.join(mis)}]
        """) + extra


class Repo:
    """临时 git 仓库：main 上放好基线，再在分支上改。"""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="curio-ci-"))
        shutil.copytree(REPO / "schemas", self.dir / "schemas")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "测试")

    def git(self, *args):
        p = subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True, encoding="utf-8")
        if p.returncode != 0:
            raise RuntimeError(p.stderr)
        return p.stdout

    def write(self, path, text):
        f = self.dir / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    def delete(self, path):
        (self.dir / path).unlink()

    def commit(self, msg="改动\n\nImplemented-By: 测试模型"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)

    def baseline(self):
        self.commit("基线")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")

    def branch(self, name):
        self.git("checkout", "-q", "-b", name)
        self.name = name

    def check(self, labels=()):
        return ci_checks.run(self.dir, "origin/main", self.name, labels)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


N1, N2 = "math.number.division-meaning", "math.number.fraction-intro"
NODE_DIR = "content/nodes/num"


class Base(unittest.TestCase):
    def setUp(self):
        self.r = Repo()

    def tearDown(self):
        self.r.close()

    def ok(self, res):
        self.assertEqual(res.errors, [], f"本应通过，却报错：{res.errors}")

    def fails(self, res, text):
        msgs = [m for _, m in res.errors]
        self.assertTrue(any(text in m for m in msgs), f"本应报「{text}」，实际：{msgs}")

    def add_html(self, aid, body="<p>分蛋糕</p>"):
        self.r.write(f"content/activities/{aid}/index.html", f"<!doctype html><html><body>{body}</body></html>\n")

    def published_set(self, review="approved", types=("experiment", "simulation"), cover=("denominator-bigger",)):
        acts = [f"act.{t}.frac-{i}" for i, t in enumerate(types)]
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, status="published", activities=acts, mis=("denominator-bigger",)))
        for i, (a, t) in enumerate(zip(acts, types)):
            self.r.write(f"content/activities/{a}/manifest.yaml", activity(a, [N2], type_=t, review=review, mis=cover if i == len(acts) - 1 else ()))
            self.add_html(a)
        return acts


class TestBranches(Base):
    def test_bad_prefix_fails(self):
        self.r.baseline(); self.r.branch("patch-1"); self.r.commit()
        self.fails(self.r.check(), "不符合规则")

    def test_arch_may_touch_docs(self):
        self.r.baseline(); self.r.branch("arch/x"); self.r.write("docs/a.md", "x"); self.r.commit()
        self.ok(self.r.check())

    def test_feat_may_not_touch_schemas_or_content(self):
        self.r.baseline(); self.r.branch("feat/x")
        self.r.write("schemas/extra.md", "x"); self.r.write("content/nodes/num/z.yaml", "x"); self.r.commit()
        res = self.r.check()
        self.assertEqual(sum("不能改这个文件" in m for _, m in res.errors), 2)

    def test_glossary_only_on_arch(self):
        self.r.baseline(); self.r.branch("feat/x"); self.r.write("GLOSSARY.md", "x"); self.r.commit()
        self.fails(self.r.check(), "不能改这个文件")
        self.r.branch("arch/glossary"); self.r.write("GLOSSARY.md", "y"); self.r.commit()
        self.ok(self.r.check())

    def test_feat_may_touch_prototype(self):
        self.r.baseline(); self.r.branch("feat/x"); self.r.write("prototype/index.html", "<html></html>"); self.r.commit()
        self.ok(self.r.check())

    def test_override_label_turns_error_into_warning(self):
        self.r.baseline(); self.r.branch("feat/x"); self.r.write("docs/a.md", "x"); self.r.commit()
        res = self.r.check(labels={"越界-已批准"})
        self.ok(res)
        self.assertTrue(any("越界改动" in m for _, m in res.warnings))


class TestKnowledgePointBranch(Base):
    def test_new_node_on_its_own_branch_passes(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, prereq=[N1])); self.r.commit()
        self.ok(self.r.check())

    def test_kp_branch_may_not_touch_other_node(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, dq="改了别人的问题？")); self.r.commit()
        self.fails(self.r.check(), "不能改这个文件")

    def test_revision_branch_with_suffix_fails(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch(f"kp/{N2}-v2"); self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, dq="新的问题？")); self.r.commit()
        self.fails(self.r.check(), "不存在")

    def test_revision_of_published_node_passes(self):
        acts = self.published_set(); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, status="published", activities=acts, mis=("denominator-bigger",), dq="改版后的问题？"))
        self.r.write(f"content/activities/{acts[0]}/index.html", "<!doctype html><html><body>新版</body></html>\n"); self.r.commit()
        # 只看地盘：过渡期发布门禁通不过（见 TestPublishGate），这里只证明改版自己的知识点不越界
        self.assertFalse([m for _, m in self.r.check().errors if "不能改这个文件" in m])

    def test_unrelated_activity_mentioning_id_in_comment_fails(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=["act.quiz.other"]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write("content/activities/act.quiz.other/manifest.yaml", activity("act.quiz.other", [N1]))
        self.add_html("act.quiz.other"); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write("content/activities/act.quiz.other/manifest.yaml", activity("act.quiz.other", [N1], extra=f"# 参考 {N2}\n")); self.r.commit()
        self.fails(self.r.check(), "不能改这个文件")

    def test_own_activity_and_prompt_pass(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.frac"]))
        self.r.write("content/activities/act.quiz.frac/manifest.yaml", activity("act.quiz.frac", [N2]))
        self.add_html("act.quiz.frac")
        self.r.write("prompts/act.quiz.frac.md", "# 提示词"); self.r.commit()
        self.ok(self.r.check())

    def test_prompt_of_other_activity_fails(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=["act.quiz.other"]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write("content/activities/act.quiz.other/manifest.yaml", activity("act.quiz.other", [N1]))
        self.add_html("act.quiz.other"); self.r.baseline()
        self.r.branch(f"kp/{N2}"); self.r.write("prompts/act.quiz.other.md", "# 改别人的提示词"); self.r.commit()
        self.fails(self.r.check(), "不能改这个文件")


class TestSharedActivity(Base):
    def setUp(self):
        super().setUp()
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, activities=["act.quiz.shared"]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.shared"]))
        self.r.write("content/activities/act.quiz.shared/manifest.yaml", activity("act.quiz.shared", [N1, N2]))
        self.add_html("act.quiz.shared"); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.add_html("act.quiz.shared", body="<p>改过的共享活动</p>"); self.r.commit()

    def test_kp_branch_may_not_change_shared_activity(self):
        res = self.r.check()
        self.fails(res, "共享活动")
        self.assertTrue(any(N1 in m for _, m in res.errors), "错误信息应列出受影响的其他知识点")

    def test_shared_activity_with_override_lists_affected_nodes(self):
        res = self.r.check(labels={"越界-已批准"})
        self.ok(res)
        self.assertTrue(any("共享活动改动" in m and N1 in m and N2 in m for _, m in res.warnings))


class TestReferences(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/refs")

    def test_node_lists_activity_that_does_not_target_it(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"]))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N1]))
        self.add_html("act.quiz.a"); self.r.commit()
        res = self.r.check()
        self.fails(res, "两边要互相写上")

    def test_activity_targets_node_that_does_not_list_it(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2]))
        self.add_html("act.quiz.a"); self.r.commit()
        self.fails(self.r.check(), "两边要互相写上")

    def test_missing_prerequisite_and_cycle(self):
        self.r.write(f"{NODE_DIR}/{N1}.yaml", node(N1, prereq=[N2]))
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, prereq=[N1, "math.number.nope"])); self.r.commit()
        res = self.r.check()
        self.fails(res, "不存在的知识点")
        self.fails(res, "有环")

    def test_filename_must_match_id(self):
        self.r.write(f"{NODE_DIR}/wrong-name.yaml", node(N2)); self.r.commit()
        self.fails(self.r.check(), "文件名必须和 id 一致")

    def test_schema_violation(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2).replace("theme: num", "theme: history")); self.r.commit()
        self.fails(self.r.check(), "theme")

    def test_activity_misconception_must_exist_in_node(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"], mis=("denominator-bigger",)))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2], mis=("made-up",)))
        self.add_html("act.quiz.a"); self.r.commit()
        self.fails(self.r.check(), "不在目标知识点的误区列表里")


class TestPublishGate(Base):
    def setUp(self):
        super().setUp(); self.r.baseline(); self.r.branch("arch/publish")

    def test_publish_waits_for_structured_activities(self):
        # 过渡期：activity schema 只允许 experiment/simulation，讲解和挑战改为结构化活动，
        # 而 CI 要到 CURIO-002b 才认得结构化活动。在那之前，任何知识点都发布不了。
        # CURIO-002b 必须恢复「完整的已发布知识点通过」这个正例。
        self.published_set(); self.r.commit()
        self.fails(self.r.check(), "至少有一个 explain")

    def test_published_with_pending_activity_fails(self):
        self.published_set(review="pending"); self.r.commit()
        self.fails(self.r.check(), "只能引用已批准")

    def test_published_without_quiz_fails(self):
        self.published_set(types=("experiment",)); self.r.commit()
        self.fails(self.r.check(), "至少有一个 quiz")

    def test_published_with_uncovered_misconception_fails(self):
        self.published_set(cover=()); self.r.commit()
        self.fails(self.r.check(), "还没有任何活动针对")


class TestIdsCopyTrailers(Base):
    def test_changing_id_fails(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch("arch/rename"); self.r.write(f"{NODE_DIR}/{N2}.yaml", node("math.number.fraction-renamed")); self.r.commit()
        self.fails(self.r.check(), "ID 永不改动")

    def test_quoting_id_is_not_a_change(self):
        quoted = node(N2).replace(f"id: {N2}", f'id: "{N2}"')
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch("arch/quote"); self.r.write(f"{NODE_DIR}/{N2}.yaml", quoted); self.r.commit()
        self.ok(self.r.check())

    def test_unquoting_id_is_not_a_change(self):
        quoted = node(N2).replace(f"id: {N2}", f"id: '{N2}'")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", quoted); self.r.baseline()
        self.r.branch("arch/unquote"); self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.commit()
        self.ok(self.r.check())

    def test_deleting_node_fails(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch("arch/delete"); self.r.delete(f"{NODE_DIR}/{N2}.yaml"); self.r.commit()
        self.fails(self.r.check(), "ID 永不改动")

    def test_forbidden_word_in_kid_facing_text_fails(self):
        self.r.baseline(); self.r.branch("arch/copy")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, dq="一起来学习分数吧？")); self.r.commit()
        self.fails(self.r.check(), "出现了「学习」")

    def test_forbidden_word_only_in_script_passes(self):
        self.r.baseline(); self.r.branch("arch/copy")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"]))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2]))
        self.add_html("act.quiz.a", body="<p>分蛋糕</p><script>// 学习事件</script>"); self.r.commit()
        self.ok(self.r.check())

    def test_forbidden_word_in_page_text_fails(self):
        self.r.baseline(); self.r.branch("arch/copy")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, activities=["act.quiz.a"]))
        self.r.write("content/activities/act.quiz.a/manifest.yaml", activity("act.quiz.a", [N2]))
        self.add_html("act.quiz.a", body="<p>一起学习</p>"); self.r.commit()
        self.fails(self.r.check(), "页面文字里出现了")

    def test_missing_trailer_warns_but_passes(self):
        self.r.baseline(); self.r.branch("arch/x"); self.r.write("docs/a.md", "x"); self.r.commit("没有署名的中文提交")
        res = self.r.check()
        self.ok(res)
        self.assertTrue(any("没有署名" in m for _, m in res.warnings))

    def test_trailer_present_no_warning(self):
        self.r.baseline(); self.r.branch("arch/x"); self.r.write("docs/a.md", "x"); self.r.commit()
        self.assertFalse(any("没有署名" in m for _, m in self.r.check().warnings))


class TestCli(Base):
    def test_chinese_commit_under_c_locale_does_not_crash(self):
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2)); self.r.baseline()
        self.r.branch(f"kp/{N2}")
        self.r.write(f"{NODE_DIR}/{N2}.yaml", node(N2, dq="中文改动？")); self.r.commit("中文标题\n\n中文正文，带「引号」。\n\nImplemented-By: 测试模型")
        env = {k: v for k, v in os.environ.items() if k not in ("LANG", "LC_ALL", "PYTHONIOENCODING", "PYTHONUTF8")}
        # 关掉 Python 的 UTF-8 模式和 C 区域强制转换，模拟真正的非 UTF-8 环境（例如 Windows 的 GBK）
        env.update(LANG="C", LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", BASE_REF="main", HEAD_BRANCH=f"kp/{N2}")
        p0 = subprocess.run([sys.executable, "-c", "import locale;print(locale.getpreferredencoding(False))"], capture_output=True, text=True, env=env)
        self.assertNotIn("utf", p0.stdout.lower(), "测试环境没能切到非 UTF-8")
        p = subprocess.run([sys.executable, str(TOOLS / "ci_checks.py"), str(self.r.dir)], capture_output=True, env=env)
        out = p.stdout.decode("utf-8", errors="replace") + p.stderr.decode("utf-8", errors="replace")
        self.assertNotIn("Traceback", out)
        self.assertEqual(p.returncode, 0, out)

    def test_missing_base_exits_2(self):
        self.r.commit("只有一个提交")
        env = dict(os.environ, BASE_REF="main", HEAD_BRANCH="arch/x")
        p = subprocess.run([sys.executable, str(TOOLS / "ci_checks.py"), str(self.r.dir)], capture_output=True, env=env)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
````


### 6. 依赖（不能加新依赖）

> 出处：`tools/requirements.txt`（提交 `672c375`）

````text
# tools/ 下脚本的依赖，版本锁定。升级时整组一起改，并跑一遍 python -m unittest discover -s tools/tests
PyYAML==6.0.3
jsonschema==4.26.0
````


### 7. 样例内容（已合入，不要改动；放在 `tools/tests/fixtures/content/` 下，目录结构和 `content/` 相同）

> 出处：`tools/tests/fixtures/content/nodes/num/math.number.fraction-intro.yaml`（提交 `672c375`）

````text
id: math.number.fraction-intro
schema: knode/1
title: 分数的初步认识
subjects: [math]
theme: num
grade: G3
unit: 三上 · 分数的初步认识
curriculum:
  - textbook: 人教版三年级上册
    unit: 分数的初步认识
prerequisites: []
related: []
driving_question: 一块蛋糕怎样公平地分给大家？
objectives:
  - 知道平均分是认识分数的前提。
  - 能用分数表示平均分成若干份后的一份或几份。
  - 能说出分子和分母各表示什么。
misconceptions:
  - id: equal-parts
    text: 没有平均分也当成几分之一。
  - id: part-vs-rest
    text: 把涂色的份数和没涂色的份数相比。
  - id: flip
    text: 把分子和分母写反。
sources:
  - type: curriculum
    ref: 《义务教育数学课程标准（2022 年版）》第二学段“数与运算”
  - type: textbook
    ref: 人教版三年级上册“分数的初步认识”
lenses:
  - band: G3-4
    approach: 从平均分蛋糕和纸条入手，用涂色部分认识几分之一和几分之几。
activities:
  - act.explain.fraction-intro-01
  - act.quiz.fraction-intro-01
  - act.reflection.fraction-intro-01
status: published
version: 1
# END OF FILE
````


> 出处：`tools/tests/fixtures/content/activities/act.explain.fraction-intro-01/activity.yaml`（提交 `672c375`）

````text
id: act.explain.fraction-intro-01
schema: activity-def/1
kind: explain
version: 1
title: 分蛋糕里的分数
targets: [math.number.fraction-intro]
age_band: G3-4
duration_min: 8
review: approved
engine: 1
sources:
  - type: textbook
    ref: 人教版三年级上册“分数的初步认识”
body:
  steps:
    - type: text
      text: 一块蛋糕，平均切成 4 份，每份都一样大。
    - type: figure
      figure: {type: pie, parts: 4, shaded: 1}
      caption: 涂色的是其中 1 份。
    - type: text
      text: 涂色部分是这块蛋糕的 1/4，读作四分之一。
    - type: figure
      figure: {type: rect-unequal, widths: [1, 1, 2], shaded: [0]}
      caption: 这三份不一样大，涂色部分不能用 1/3 表示。
    - type: check
      item:
        id: c1
        stem: 哪种分法能用 1/4 表示涂色部分？
        answer:
          type: choice
          choices:
            - id: a
              text: 平均分成 4 份，涂其中 1 份
              correct: true
            - id: b
              text: 分成大小不同的 4 份，涂其中 1 份
              misconception: equal-parts
              feedback: 用分数表示这样的部分时，每一份要一样大。
            - id: c
              text: 平均分成 4 份，把涂色 1 份和剩下 3 份相比
              misconception: part-vs-rest
              feedback: 要和整块平均分成的总份数相比。
        hints:
          - 先看看每一份是不是一样大。
          - 再看一共分成几份，涂色的是几份。
        feedback:
          correct: 你找到了平均分，也看清了总份数和涂色份数。
          wrong: 先检查是不是平均分，再数一数总份数。
    - type: text
      text: 写 1/4 时，横线下面的数叫分母，表示平均分成的总份数；横线上面的数叫分子，表示涂色的份数。
    - type: figure
      figure: {type: rect, parts: 4, shaded: 3, direction: h}
      caption: 平均分成 4 份，涂色 3 份。
    - type: text
      text: 涂色 3 份就是 3/4，读作四分之三。
# END OF FILE
````


> 出处：`tools/tests/fixtures/content/activities/act.quiz.fraction-intro-01/activity.yaml`（提交 `672c375`）

````text
id: act.quiz.fraction-intro-01
schema: activity-def/1
kind: quiz
version: 1
title: 分数小挑战
targets: [math.number.fraction-intro]
age_band: G3-4
duration_min: 10
review: approved
engine: 1
sources:
  - type: textbook
    ref: 人教版三年级上册“分数的初步认识”
body:
  items:
    - id: q1
      stem: 涂色部分是这个圆的几分之几？
      figure: {type: pie, parts: 4, shaded: 1}
      answer:
        type: choice
        choices:
          - {id: a, text: 1/4, correct: true}
          - id: b
            text: 1/3
            misconception: part-vs-rest
            feedback: 涂色部分要和整个圆的总份数相比。
          - id: c
            text: 4/1
            misconception: flip
            feedback: 总份数写在横线下面，涂色份数写在横线上面。
      hints:
        - 分母表示平均分成的总份数。
        - 分子表示涂色的份数。
      feedback:
        correct: 总份数和涂色份数都找对了。
        wrong: 先数总份数，再数涂色份数。
    - id: q2
      stem: 长方形被分成三份，涂色部分能直接用 1/3 表示吗？
      figure: {type: rect-unequal, widths: [1, 2, 1], shaded: [0]}
      answer:
        type: choice
        choices:
          - id: a
            text: 不能，因为三份不一样大
            correct: true
          - id: b
            text: 能，因为一共分成三份
            misconception: equal-parts
            feedback: 只有平均分时，其中一份才是整体的 1/3。
          - id: c
            text: 能，涂色一份和没涂色两份比较即可
            misconception: part-vs-rest
            feedback: 分母要表示整个图形平均分成的总份数。
      hints:
        - 比较三份的大小。
        - 用分数表示这样的部分前，先检查是不是平均分。
    - id: q3
      stem: 一张纸条平均分成 4 份，涂其中 3 份，所得分数的分子是几？
      answer:
        type: number
        value: 3
        tolerance: 0
        common_wrong:
          - value: 4
            misconception: flip
            feedback: 分子表示涂色份数，不是总份数。
      hints:
        - 看横线上面的数。
        - 横线上面的数表示涂色的份数。
    - id: q4
      stem: 一张正方形纸平均分成 8 份，涂其中 2 份，涂色部分用分数怎样表示？
      figure: {type: rect, parts: 8, shaded: 2, direction: v}
      answer:
        type: fraction
        numerator: 2
        denominator: 8
        accept_equivalent: true
        common_wrong:
          - numerator: 2
            denominator: 6
            misconception: part-vs-rest
            feedback: 分母是总份数，不是没涂色的份数。
          - numerator: 8
            denominator: 2
            misconception: flip
            feedback: 总份数写在横线下面，涂色份数写在横线上面。
      hints:
        - 先数平均分成的总份数，写在横线下面。
        - 再数涂色的份数，写在横线上面。
    - id: q5
      stem: 一张长方形纸平均分成 6 份，涂其中 1 份，涂色部分用分数怎样表示？
      figure: {type: rect, parts: 6, shaded: 1, direction: h}
      answer:
        type: fraction
        numerator: 1
        denominator: 6
        accept_equivalent: false
        common_wrong:
          - numerator: 1
            denominator: 5
            misconception: part-vs-rest
            feedback: 分母要对应全部份数。
      hints:
        - 分母要把涂色和没涂色的份数都算上。
        - 分子只数涂色的份数。
  shuffle: true
# END OF FILE
````


> 出处：`tools/tests/fixtures/content/activities/act.reflection.fraction-intro-01/activity.yaml`（提交 `672c375`）

````text
id: act.reflection.fraction-intro-01
schema: activity-def/1
kind: reflection
version: 1
title: 我的分数发现
targets: [math.number.fraction-intro]
age_band: G3-4
duration_min: 3
review: approved
engine: 1
body:
  prompt: 用一句话说说，怎样分才能用分数表示其中的一份或几份？
  starters: [我发现……, 原来……]
  max_chars: 120
# END OF FILE
````


`tools/tests/fixtures/content/` 下另有 `release.json`、`experiment-manifest.json` 两个文件，是 schema 测试用的，不在 `nodes/`、`activities/`、`assets/` 里，构建器不要收录它们。

### 8. Claude 写好的验收用例：分数样例的期望发布清单

下面是 Claude 按内容规格 6.2 节，用独立的程序手算出来的结果（没有用你的构建器）。用你的构建器构建 `tools/tests/fixtures/content/` 得到的清单，**去掉 `source_commit` 之后**，必须和它完全相同，包括 `content_hash`。这个文件里故意没有 `source_commit`，因为它每次构建都不一样。

> 出处：`tools/tests/fixtures/expected/fraction-release.json`（提交 `672c375`）

````text
{
  "schema": "release/1",
  "release_id": "rel_b12263a7dba6595337ca156c88d0b1a3d313edf2e00a672b66ee32f1269b94fe",
  "content_hash": "b12263a7dba6595337ca156c88d0b1a3d313edf2e00a672b66ee32f1269b94fe",
  "engine_min": 1,
  "contracts": [],
  "nodes": [
    {
      "id": "math.number.fraction-intro",
      "version": 1,
      "path": "content/nodes/num/math.number.fraction-intro.yaml",
      "sha256": "21b3a1f15adeef754f5bf1844d88cc87ba43eba1d1f9efe996c7b607f4fa2271"
    }
  ],
  "activities": [
    {
      "id": "act.explain.fraction-intro-01",
      "version": 1,
      "kind": "explain",
      "files": [
        {
          "path": "content/activities/act.explain.fraction-intro-01/activity.yaml",
          "sha256": "3b31d671d5a7ec3c65c2a3d1cd6cfd27fa4a427ca56e7ede64aa6f44650e8484",
          "bytes": 2130
        }
      ]
    },
    {
      "id": "act.quiz.fraction-intro-01",
      "version": 1,
      "kind": "quiz",
      "files": [
        {
          "path": "content/activities/act.quiz.fraction-intro-01/activity.yaml",
          "sha256": "a9c04f4979096edd843691b3cbb6c3e07c396a442c9a8ad60dcf872eab4ea2f8",
          "bytes": 3689
        }
      ]
    },
    {
      "id": "act.reflection.fraction-intro-01",
      "version": 1,
      "kind": "reflection",
      "files": [
        {
          "path": "content/activities/act.reflection.fraction-intro-01/activity.yaml",
          "sha256": "244225117db8b8957a9c680e5a8e78e4738f4640123872cf3aefcd204d2497cb",
          "bytes": 380
        }
      ]
    }
  ],
  "assets": []
}
````


## 要做的事

### 一、发布构建器 `tools/build_release.py`

按内容规格第 6 节实现。

- **公开接口**（测试接缝）：`build(content_root, source_commit) -> dict`，返回完整的发布清单（含 `source_commit`）。出错时抛出 `BuildError`，错误信息用中文写清楚是哪个文件、违反了哪条规则。另外提供 `write_release(manifest, content_root, out_dir)`，把 `release.json` 和清单里的每个文件按 `path` 写进 `out_dir`。
- **命令行**：`python tools/build_release.py --content <内容目录> --out <输出目录> [--commit <提交号>]`。不给 `--commit` 时，用 `git rev-parse HEAD`。成功时打印 `release_id`，失败时打印错误、退出码为 1。
- **清单里的路径**一律写成 `content/` 开头，相对内容目录。也就是说，构建 `tools/tests/fixtures/content/` 时，路径也写成 `content/nodes/…`，和构建真正的 `content/` 一样。
- **收录范围**、**引用闭包**、**`engine_min`**、**`contracts`**、**哈希算法**：严格按规格 6.1、6.2 和 3.8 节实现。
- **构建前的检查**：文件含 CR、路径不合规则、两个路径只差大小写（规格第 1 节），一律报错。收录的知识点和活动必须通过发布门禁（规格第 5 节），这部分直接调用 `ci_checks.py` 里的函数，不要另写一份。
- 只用标准库，加上 PyYAML 和 jsonschema。

### 二、升级 `tools/ci_checks.py`

在保留现有全部检查（地盘、ID 不变、文案、署名提醒等）的前提下，按内容规格第 5 节加上新规则：

1. **形态**：活动目录要么只有 `activity.yaml`，要么有 `manifest.yaml` + `index.html`；混用、或者两者都没有，都报错。删掉旧的「每个活动都必须有 `index.html`」这条过渡规则。
2. **schema**：`activity.yaml` 按 `schemas/activity-def.schema.json` 校验；`manifest.yaml` 按 `schemas/activity.schema.json` 校验。
3. **引用**：
   - 知识点的 `activities` 和活动的 `targets` 双向一致，两种形态的活动都算；
   - 题目里引用的误区出自目标知识点：只有一个 target 时写误区 id，有多个时必须写成 `<知识点 id>:<误区 id>`（规格 3.3）；
   - `svg` 配图的文件存在于 `content/assets/` 下。
4. **题目**：同一个活动里题目 id 唯一，讲解里 `check` 小问题的 id 也算在内；`pie`、`rect` 的 `shaded` 不超过 `parts`；`rect-unequal` 的 `shaded` 下标都小于 `widths` 的长度。
5. **提示泄露**（规格 3.4，分两层）：
   - 数字题、分数题报错：任何一条提示里出现正确答案的写法。数字题检查 `value` 的十进制写法；分数题检查 `a/b`、`b分之a`、中文数字的「b分之a」（例如「四分之一」，中文数字只需支持 0～99），`accept_equivalent: true` 时还要检查最简分数的这几种写法。匹配时，数字前后不能紧挨着别的数字，所以 `18` 不会命中 `180`。
   - 选择题只给警告：正确选项的原文出现在任何一条提示里。
6. **SVG 白名单**（规格 3.6）：元素、属性白名单；`href`、`xlink:href` 只能是 `#id`；属性值里的 `url(…)` 只能是 `url(#id)`；不允许 `<style>`、`style` 属性、`<!DOCTYPE>`、实体，也不允许 XML 声明以外的处理指令。
7. **路径**（规格第 1 节）：`content/` 下的所有文件：每一段只含 ASCII 字母、数字、点、下划线、连字符，不以点开头，不允许 `.`、`..`；任意两个路径只差大小写时报错。
8. **引擎等级**（规格 3.8）：用一张常量表写明每种 `kind`、答案 `type`、配图 `type` 需要几级引擎；活动的 `engine` 低于它用到的最高等级时报错。现在全部是第 1 级；测试里可以临时改这张表，验证规则会生效。
9. **误区覆盖从数据计算**：结构化活动里，被错误选项或 `common_wrong` 引用的误区算作已覆盖；自定义实验以 manifest 的 `misconceptions` 为准。
10. **发布门禁**：只看会被收录的活动（`approved` 的）。知识点 `published` 时，它被收录的活动里至少有一个 `explain` 和一个 `quiz`，每个 `quiz` 至少 5 道题，每个误区都被覆盖。没批准的活动不收录，也不阻断。
11. **引用闭包**（规格 6.1）：已发布知识点的 `prerequisites` 都已发布；被收录活动的全部 `targets` 都已发布。
12. **样例目录不参加**：`tools/tests/fixtures/` 下的内容只做 schema 校验和构建器测试，不跑上面这些针对 `content/` 的规则（规格第 7 节）。

旧格式的活动（只有 `manifest.yaml` + `index.html`，`type` 是 `experiment` 或 `simulation`）照常支持，原有的地盘规则、共享活动规则不变。

## 验收用例和测试

- **测试接缝**（测试只写在这里）：
  - `build_release.build(content_root, source_commit)` 和 `BuildError`：能发现收录范围、闭包、哈希、路径和 CR 方面的错误；发现不了 CI 层面的问题。
  - 构建器的命令行：能发现参数和退出码的问题。
  - `ci_checks.run(repo, base, branch, labels)` 返回的 `errors` 和 `warnings`：沿用现有测试里用临时 git 仓库的写法（`Repo` 类）。
- **必须通过的验收用例**（期望值是 Claude 写的，不要由你的代码生成）：
  1. 构建 `tools/tests/fixtures/content/` 的结果去掉 `source_commit` 后，和上面第 8 节的期望清单完全相同（`release_id` 是 `rel_b12263a7dba6595337ca156c88d0b1a3d313edf2e00a672b66ee32f1269b94fe`）。
  2. 同一份内容构建两次，以及把内容复制到另一个目录再构建，`release_id` 都和第 1 条相同。
  3. 在样例的复制品上把知识点改成 `draft`：发布包里没有任何知识点和活动，`nodes`、`activities`、`assets` 都是空列表。
  4. 在样例的复制品上把挑战的 `review` 改成 `pending`：挑战不收录；因为这个知识点被收录的活动里没有 `quiz` 了，发布门禁报错，构建失败。
  5. 已发布的知识点 A 的前置知识点 B 是草稿：构建失败，错误信息里出现 B 的 id。
  6. 一个已批准的活动同时针对已发布的 A 和草稿 B：构建失败，错误信息里出现这个活动的 id 和 B 的 id。
  7. 一个文件里含有 CR：构建失败，错误信息里出现文件路径。
  8. `content/assets/a/Fig.svg` 和 `content/assets/a/fig.svg` 同时存在：构建失败，CI 也报错。
  9. 分数题答案 1/4、`accept_equivalent: false`，最后一条提示写「涂了四分之一」：CI 报错；提示写「先数一数一共几份」：不报错。
  10. 数字题答案 18，提示里出现「180 页」：不报错；出现「18 厘米」：报错。
  11. 选择题正确选项「1/4」出现在提示里：CI 给警告，不报错。
  12. 恢复正例：一个已发布的知识点，有已批准的讲解和挑战（挑战 5 题、覆盖全部误区），CI 通过。现有测试里的 `test_publish_waits_for_structured_activities` 改回这个正例。
- 你自己写的测试也只通过接缝检查行为。测试名写清检查的是什么，例如「草稿知识点不进发布包」。期望值写成字面值，或者引用上面的规格和验收用例。
- 第二节的 12 条规则，每条至少一个应该通过的例子和一个应该失败的例子。
- 怎么自己验证：在仓库根目录运行 `python -m unittest discover -s tools/tests`，全部通过；再运行 `python tools/build_release.py --content tools/tests/fixtures/content --out /tmp/rel --commit 0000000000000000000000000000000000000000`，打印出的 `release_id` 等于第 1 条里的那个。不能运行代码的话，就逐条对照验收用例核对。

## 约束

- 规格是唯一依据。规格里没写的，不要自己加规则；觉得规格不清楚、不合理或互相矛盾，**不要自己改**，写进交付包「说明」里的「疑问」。
- `tools/ci_checks.py` 和 `tools/tests/test_ci_checks.py` 交付**完整文件**，不要只给改动的片段。原有的测试除了第 12 条要改回正例的那一个，一个都不要删、不要放宽。
- 现有测试里用到旧格式 manifest 的地方（`type: experiment`、带 `version`）保持可用。
- 错误信息、注释用简体中文；用术语表里的词。
- 不加依赖。所有文本文件用 UTF-8、LF 换行。

## 验收标准

- [ ] 上面 12 条验收用例全部通过
- [ ] 第二节的 12 条 CI 规则，每条都有正例和反例
- [ ] 原有测试全部保留并通过（第 12 条那一个改回正例）
- [ ] `python -m unittest discover -s tools/tests` 全部通过

## 交付格式（必须遵守）

本任务的文件清单（按这个顺序）：

```
tools/tests/test_build_release.py
tools/tests/test_ci_checks.py
tools/build_release.py
tools/ci_checks.py
```

测试文件放在前面。如果你为测试加了新的样例文件，写在 `tools/tests/fixtures/build/` 下，并逐个列进清单；`tools/tests/fixtures/content/` 和 `tools/tests/fixtures/expected/` 下的文件不要改。

文件比较大，一个回答放不下时就分段。**每一段的第一行都必须是段首标记**「=== CURIO 交付包 · 第 k/n 段 ===」，最后一行是「=== 第 k/n 段完 ===」，少一个就会整包打回。所有文件都写在交付包文字里，不要另外附带单独的文件。

开头信息里的 issue、任务、提示词版本、基于提交，照抄本文件最开头给出的值。

> 出处：`docs/submission.md · 「格式」一节`（提交 `672c375`）

``````text
## 格式

一段交付包长这样（`````里面的就是要输出的内容）：

`````
=== CURIO 交付包 · 第 1/2 段 ===
issue: #12
任务: act.quiz.fraction-intro-01
实现者: <模型名和版本，例如 GPT-5.1、Gemini 3 Pro>
提示词版本: v1
基于提交: <提示词开头写的提交号>
轮次: 1

## 文件清单
- content/activities/act.quiz.fraction-intro-01/manifest.yaml
- content/activities/act.quiz.fraction-intro-01/index.html

## 文件

### FILE: content/activities/act.quiz.fraction-intro-01/manifest.yaml
```yaml
id: act.quiz.fraction-intro-01
…
# END OF FILE
```

=== 第 1/2 段完 ===
`````

最后一段：

`````
=== CURIO 交付包 · 第 2/2 段 ===

### FILE: content/activities/act.quiz.fraction-intro-01/index.html
```html
<!doctype html>
…
</html>
<!-- END OF FILE -->
```

## 自查
- [x] 提示词里「验收标准」的每一条
- [x] …

## 说明
- 做了哪些决定，为什么：
- 没做什么：
- 疑问（规格不清楚、互相矛盾，或者觉得不合理的地方）：

=== END ===
=== 第 2/2 段完 ===
`````

一个回答放得下时，就只有一段：写成「第 1/1 段」，开头信息、清单、文件、自查、说明、`=== END ===` 都在这一段里。
``````


> 出处：`docs/submission.md · 「规则」一节`（提交 `672c375`）

````text
## 规则

1. **分段**：每段以 `=== CURIO 交付包 · 第 k/n 段 ===` 开头，以 `=== 第 k/n 段完 ===` 结尾，n 是总段数，每段都写同一个 n。
   - 开头信息和「文件清单」只写在第 1 段。开头信息六项**全部必填**，格式如下，照抄任务文件里给的值：
     - `issue: #12`
     - `任务: act.quiz.fraction-intro-01`
     - `实现者: <模型名和版本>`
     - `提示词版本: v1`
     - `基于提交: <任务文件开头写的提交号>`
     - `轮次: 1`（正整数，打回一次加一）
   - 「自查」「说明」和 `=== END ===` 只写在最后一段。
2. **一个文件不能拆到两段里。**单个文件长到一个回答放不下时，把它改为附件交付（见第 6 条），清单里照常列出。
3. **文件路径**：每个文件用 `### FILE: <路径>` 开头。路径必须和「文件清单」完全一致，也必须是提示词里指定的路径。
4. **结束标记**：每个文件的最后一行写结束标记，按文件类型选择对应的注释写法：
   - YAML、Python：`# END OF FILE`
   - HTML、Markdown、SVG：`<!-- END OF FILE -->`
   - JavaScript、CSS：`/* END OF FILE */`
   - JSON 不能写注释，所以不加结束标记；收货时会检查它能不能完整解析。
5. **交付完整文件**：每次都给出完整文件，不要只给改动的片段，也不要写「其余部分不变」。
6. **附件**：文件太长、需要做成附件时，附件的文件名必须是**完整路径**，把其中的 `/` 换成 `__`。例如 `content/activities/act.x/index.html` 的附件名是 `content__activities__act.x__index.html`。只写 `index.html` 会被打回，因为几个活动的同名文件会对不上号。
7. **疑问写在「说明」里**：不要为了让自己的实现能跑通，就去改规格、字段或消息格式。
8. **打回之后**：交付完整的新一轮交付包，「轮次」加一，并在「说明」里逐条写出改了什么。
````

---

## 附：本任务文件嵌入的仓库文件

| 文件 | 范围 | SHA-256（整个文件） |
| --- | --- | --- |
| `docs/specs/content.md` | 全文 | `45b7fb205858237e43b33f74a875f52db8fd62e11cfedb7f56062f470624357e` |
| `GLOSSARY.md` | 内容 | `c84d43b7672e0f470cd495a107a0d02441ccea41db687402f574174677d58590` |
| `GLOSSARY.md` | 协作 | `c84d43b7672e0f470cd495a107a0d02441ccea41db687402f574174677d58590` |
| `schemas/activity-def.schema.json` | 全文 | `42e2ac573b682ec5d2befe3527821b7e98925ed1b66bf9df8a4f32e739417fd3` |
| `schemas/release.schema.json` | 全文 | `e8ba52f390d983107a16ae03ebfc3b0e47701c04d56af35931ee931793189630` |
| `tools/ci_checks.py` | 全文 | `92ccc4192f9b958655bb32c70f6d26cf289c4e3920eb13b68b726eca5cbc1240` |
| `tools/tests/test_ci_checks.py` | 全文 | `d0628b9d99a18fcc0e50706d60a3bbc49f92abee3f27dd6602d6b9de14d31999` |
| `tools/requirements.txt` | 全文 | `0ef193531a3411e824ec8a2275abc95a34561c83964d51297d784f90e524173d` |
| `tools/tests/fixtures/content/nodes/num/math.number.fraction-intro.yaml` | 全文 | `21b3a1f15adeef754f5bf1844d88cc87ba43eba1d1f9efe996c7b607f4fa2271` |
| `tools/tests/fixtures/content/activities/act.explain.fraction-intro-01/activity.yaml` | 全文 | `3b31d671d5a7ec3c65c2a3d1cd6cfd27fa4a427ca56e7ede64aa6f44650e8484` |
| `tools/tests/fixtures/content/activities/act.quiz.fraction-intro-01/activity.yaml` | 全文 | `a9c04f4979096edd843691b3cbb6c3e07c396a442c9a8ad60dcf872eab4ea2f8` |
| `tools/tests/fixtures/content/activities/act.reflection.fraction-intro-01/activity.yaml` | 全文 | `244225117db8b8957a9c680e5a8e78e4738f4640123872cf3aefcd204d2497cb` |
| `tools/tests/fixtures/expected/fraction-release.json` | 全文 | `8b9df9ad721a064aa6cb2fe25ead2b7020cc2631855922f178a28f460aaac4c8` |
| `docs/submission.md` | 格式 | `ea8f185947df7a9b176193b27dd2c5c334c04351acf5cacf91087a9171ba31bf` |
| `docs/submission.md` | 规则 | `ea8f185947df7a9b176193b27dd2c5c334c04351acf5cacf91087a9171ba31bf` |
