---
task: curio-002b
issue: 17
version: v1
---

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

{{embed: docs/specs/content.md}}

### 2. 术语表

{{embed: GLOSSARY.md#内容}}

{{embed: GLOSSARY.md#协作}}

### 3. 结构化活动和发布清单的 schema（已合入，不要改动）

{{embed: schemas/activity-def.schema.json}}

{{embed: schemas/release.schema.json}}

### 4. 现有的 CI 检查脚本（你要修改它，交付完整的新文件）

{{embed: tools/ci_checks.py}}

### 5. 现有的 CI 检查测试（你要修改它，交付完整的新文件）

{{embed: tools/tests/test_ci_checks.py}}

### 6. 依赖（不能加新依赖）

{{embed: tools/requirements.txt}}

### 7. 样例内容（已合入，不要改动；放在 `tools/tests/fixtures/content/` 下，目录结构和 `content/` 相同）

{{embed: tools/tests/fixtures/content/nodes/num/math.number.fraction-intro.yaml}}

{{embed: tools/tests/fixtures/content/activities/act.explain.fraction-intro-01/activity.yaml}}

{{embed: tools/tests/fixtures/content/activities/act.quiz.fraction-intro-01/activity.yaml}}

{{embed: tools/tests/fixtures/content/activities/act.reflection.fraction-intro-01/activity.yaml}}

`tools/tests/fixtures/content/` 下另有 `release.json`、`experiment-manifest.json` 两个文件，是 schema 测试用的，不在 `nodes/`、`activities/`、`assets/` 里，构建器不要收录它们。

### 8. Claude 写好的验收用例：分数样例的期望发布清单

下面是 Claude 按内容规格 6.2 节，用独立的程序手算出来的结果（没有用你的构建器）。用你的构建器构建 `tools/tests/fixtures/content/` 得到的清单，**去掉 `source_commit` 之后**，必须和它完全相同，包括 `content_hash`。这个文件里故意没有 `source_commit`，因为它每次构建都不一样。

{{embed: tools/tests/fixtures/expected/fraction-release.json}}

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

{{embed: docs/submission.md#格式}}

{{embed: docs/submission.md#规则}}
