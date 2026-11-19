# 规格：知识点目录（catalog/1）

- 状态：提议，第 1 稿
- 任务：#188（星图迁移第 1 步）；顺序见 `docs/handoff.md`「下一版的顺序」
- 依据：`docs/specs/content.md`（发布包）、AGENTS.md「ID 永不复用、永不改动」

## 1. 为什么要有目录

发布包只收 `published` 的知识点卡。首页星图要画的 93 个知识点里，只有 3 个有已发布的卡，其余存在于 `prototype/index.html` 的 `RAW` 数组。正式星图需要一份**随发布包一起下发的目录**：每个点的名字、年级、主题、前置关系，以及它有没有课程。

占位不做成 `knode/1` 的卡：卡要有目标、误区、活动，占位没有这些；也不扩 `status` 枚举，免得改知识点卡的格式。

## 2. 文件

`content/catalog/points.yaml`，由 `schemas/catalog.schema.json` 校验：

```yaml
schema: catalog/1
version: 1                      # 每次改动加 1
points:                         # 现行的 93 个点
  - id: m.g1.count              # 沿用原型的 ID；格式同 release/1 的 nodeId
    title: 数一数
    grade: G1                   # G1～G12，同 knode/1
    theme: num                  # 同 knode/1 的 theme
    unit: 一上 · 准备课
    prerequisites: []           # 其他 points 的 id
retired:                        # 被新星接替的旧占位（原型里的 replacements，共 9 个）
  - id: m.g3.decimal
    title: <原型里的名字>
    grade: G3
    theme: num
    unit: <原型里的单元>
    replaced_by: math.decimal.tenths   # 必须是 points 里的 id
```

- **「有没有课程」不存。**一个点有课程，当且仅当 `content/nodes/` 里有同 ID 的卡；已开放，当且仅当那张卡是 `published`。这是读出来的，不是写进去的，所以不会和卡不一致。
- 23 个有课程的点，ID 就是卡的 ID。

## 3. 规则

1. `points` 和 `retired` 里的 ID 合起来不重复；同一个 ID 不能既在 `points` 又在 `retired`。
2. **ID 只增不减。**一个 ID 一旦进了 `main` 上的目录，之后任何版本里都必须还在（可以从 `points` 挪到 `retired`，不能消失）。已进 `main` 的条目，`grade`、`theme` 不得改。检查办法同 `ci_checks.py` 的其他检查，拿 `origin/main` 上的目录对比。
3. `prerequisites` 里的 ID 必须是 `points` 里的 ID。
4. `replaced_by` 必须是 `points` 里的 ID，且该点有同 ID 的卡。
5. 每张 `content/nodes/` 里的卡（不论状态）都必须在 `points` 里有同 ID 的条目，并且 `grade`、`theme` 与卡一致。
6. 占位 ID 一旦进了发布包就不再改。以后有课程接替它，把它挪进 `retired`，用 `replaced_by` 指过去（Luka 2026-11-19 定）。占位 ID 照搬原型的写法，不统一成 `math.number.xxx`（同上）。
7. 搜索旧名：`retired` 里的 `title` 要能被检索到，并指向 `replaced_by`。

## 4. 进发布包

`release/1` 增加一个**可选**的顶层字段 `catalog`，结构同 `fileEntry`（`path`、`sha256`、`bytes`、`json`）。

- `content/catalog/points.yaml` 存在时，构建器把它和它的 `.yaml.json` 一起收进发布包，并计入 `content_hash`。不存在时不写 `catalog`，旧发布包照常通过校验。
- 只有 `catalog` 一个新字段，`additionalProperties: false` 不放宽。
- 不改 `release_id` 的算法；目录进了 `content_hash`，所以 `release_id` 会变，这是对的。
- `app/` 读发布包的代码遇到有 `catalog` 的包不能报错。画星图用到它是第 3 步的事，这一步不改界面。

## 5. 不做

- 不改 `knode.schema.json`；不改事件和存储格式；不改 `app/` 的画面。
- 不把原型的 `RAW` 删掉，原型照旧读自己的数据。目录由一次性脚本 `tools/export_catalog.py` 导出，导出的结果提交进 `content/catalog/points.yaml`。
- 导出要做和原型一样的合并：原型的 `RAW` 本身有 82 行；23 张课程卡（3 张已发布、20 张草案）并进来，同 ID 的覆盖、没有的追加，得到 102 行。其中 `replacements` 里的 9 个是 `retired`，其余 93 个是 `points`。原型里 `trial.catalog` 指试玩活动清单，和这份目录无关。

## 6. 验收口径

- `points` 93 条，`retired` 9 条；原型合并课程卡之后的 `RAW`（共 102 行）每个 ID 都在这两处之一。
- 23 个有课程的点，每个都对上 `content/nodes/` 里的卡；其中 3 个是 `published`。
- 发布构建通过；`release.json` 里有 `catalog`；改一个目录条目，`content_hash` 变。
- 每条规则至少一个通过样例和一个失败样例（AGENTS.md 原则 8）。
