# 独立审阅：docs/specs/evidence.md（CURIO-013，分支 arch/evidence）

- 审阅者：Claude Sonnet 5.5（Claude 会话里的子 agent），2026-11-12，审的是第 1 稿（`7430020`）。
- 处理：10 条全部采纳。第 3 条选了 (a)：`poe.predicted` 加可选字段，3.7 不变；第 4 条把 `engine` 换成 `grader`；第 7 条去掉 `corrections`，只留原则。第 1 条（模块在完成后又发事件）归到竖切片 5a：宿主在 `complete` 之后丢掉这次尝试的事件。

审阅范围：事件规格 2、3、6、7.3、8 节，`schemas/event.schema.json`，`kernel/js/{validate,mastery,log}.js`，`engine/js/quiz.js`，`app/{app,session,store,commit}.js`，竖切片 1 规格 6.4，三个已发布的模拟模块及 manifest。只读，未改动任何文件。

**结论：改完再合入。** 「只补记」的方向对，`answer.revealed` 本身没有破坏现有规则；但模拟猜测映射成 `item.answered` 会把已完成的尝试判成不一致，`engine` 字段名不副实，`corrections` 与内容不可变、投影纯函数两条现有原则冲突，这三处要先改。

---

## 1. 模拟模块的事件会落在 `attempt.completed` 之后，整次尝试被判「不一致」，奖励和掌握度一起丢掉

- 严重程度：重要
- 位置：evidence.md「3. 模拟模块里的猜测」；`content/activities/act.simulation.chromosome-pack-01/index.html` 第 214–219、325、406、515 行；事件规格 6.3 第 4 条
- 问题：chromosome-pack 在第一轮结尾发 `Host.complete`（第 693 行），点「再玩一次」进入第 2 轮后，`ask()` 里的 `Host.event("predicted"/"answered")` 和各站的 `Host.event("observed")` 没有「只在第一轮发」的判断（cell-zoom、dna-book 有，这个没有）。宿主照 evidence 把它们记成 `item.answered`，就会出现 `attempt.completed` 之后又有事件。6.3 第 4 条要求结束事件必须是最后一条，违反时整次尝试「不一致」：不计入掌握度，也不发 `activity-done` 奖励。也就是孩子认真做完、又玩了一遍，反而丢了第一遍应得的结果。`mastery.js` 的 `attemptRule` 就是这样写的，已核对。
- 建议：evidence.md 规定宿主在收到 `complete` 之后丢弃该尝试的后续事件，并计一条契约警告（诊断日志，不进事件流）。同时让 chromosome-pack 补上第一轮守卫（那是内容任务，不改已发布版本，出 version 2）。5a 规格要为这一点写测试。

## 2. 谁给 `try`、`hints_used`、`response` 赋值没有写，`item.answered` 的必填字段在模块消息里并不都有

- 严重程度：重要
- 位置：evidence.md「3.」；`validate.js` 的 `item.answered` 校验（`response` 必须是字符串、`try` 必须从 1 连续递增）；模块代码
- 问题：模块发的是 `{station, choice: 数字下标, correct, misconception: 可能是 null}`，`chromosome-pack` 的 `answered` 是 `{station:3, item:"pairing", correct:true, tries: 配错次数}`，没有 `choice`。要变成合法的 `item.answered`，宿主得自己：把数字下标转成字符串 `response`；`null` 的误区要省略（校验要求 `misconception` 是字符串）；`hints_used` 填 0；按 `item_id` 数 `try`（规则 5）；`pairing` 的 `response` 没有可填的值。其中 `tries`（配错次数）在 `item.answered` 里没有位置，会被丢掉，这是现在不记以后就拿不回的数据。另外 `correct` 在测验里是宿主判的，在模拟里是模块自己报的，两者可信程度不同，外壳边界（ADR-005）下不该混成同一个字段而不标明。
- 建议：在 evidence.md 里写清映射表（至少写出这四点和 `pairing` 怎么填 `response`），不要全推给 5a。`tries` 要么放进 `response`（例如 `"p3"` 之类短串），要么明确承认丢弃。写明「模拟里的 `correct` 是模块自报」，加在事件规格 3.1 那句话旁边。

## 3. 把 `predicted` 记成 `item.answered`，和已有契约相悖，也是这份文档里最难反悔的一条

- 严重程度：重要
- 位置：evidence.md「3.」最后两条；事件规格 3.7 表；`poe.predicted` 的 schema（已有 `choice` 字符串，最多 32 字）
- 问题：事件规格 3.7 和活动契约已经规定 `predicted → poe.predicted`，现在要改成 `item.answered`。理由「不用给 `poe.predicted` 加字段」站不住：同一份文档里给 `attempt.started` 加字段是可以的，给 `poe.predicted` 加一个可选的 `misconception` 同样是只增不改。后果是：「预测」（动作发生在观察之前）和「作答」混在一个动词里，靠 `sim:` 前缀才能分开；事件不可变，记下去就不能改成别的动词。以后任何不看前缀的统计（首答正确率、家长端的「答对几道」）都会混入猜测。`sim:` 前缀其实多余：信封里已有 `content.activity_kind: "simulation"`，投影应该按它区分，而不是靠 ID 的写法（前缀和 `repairs/1` 的关系见第 7 条）。
- 建议：二选一。(a) 推荐：`poe.predicted` 加可选 `misconception`（和 `item_id` 如果需要），保持 3.7 不变；(b) 若坚持 `item.answered`，则必须在事件规格里写明「`activity_kind = simulation` 的 `item.answered` 是模块自报的猜测，任何投影不得与测验作答合算」，并把区分依据写成 `activity_kind`，前缀只作显示。无论哪种，把「已存储的事件无法改动动词」这一点写进决定的理由里。

## 4. `engine` 字段回答不了它声称要回答的问题

- 严重程度：重要
- 位置：evidence.md「2. 记下是哪一版程序判的分」；`app/app.js` 第 13 行 `ENGINE_LEVEL = 1`、第 70–71 行
- 问题：`ENGINE_LEVEL` 是「发布包要求的最低引擎等级」（`engine_min`），只有出现不兼容能力时才加一。`grade.js` 改了一个判分 bug，等级不会变，所以「当时用哪一版程序判的分」说不清，修了判分 bug 之前和之后的作答仍然是同一个 `engine: 1`。文档里还说「没有这个字段的旧事件按 `engine: 1` 理解」，这等于把现在所有旧事件固定为等级 1，以后等级升到 2 时依旧成立，但没有信息量。要回溯判分，现在已经有 `response`（最多 32 字，已记录），重判只需要 `content_release` 里的答案和判分程序的版本。
- 建议：要么改成能区分判分行为的东西（例如判分程序的版本串或外壳构建号，由 `grade.js` 导出常量），要么承认这个字段只是「引擎能力等级」，把理由改写成它真正能说明的事，别再声称能还原判分程序。若采用前者，字段名也不要叫 `engine`，免得和 `engine_min` 混淆。

## 5. 「全部只增不改」对旧代码并不成立：新代码写的事件，旧代码会把整次尝试判成不一致

- 严重程度：重要
- 位置：evidence.md「一句话」「验收 2」；`validate.js` 的 `keys()`（不认识的 payload 键直接 `invalid`）、`SCHEMA_VERBS`、`checkVerb`；`schemas/event.schema.json` 里 `attempt.started` 的 `additionalProperties: false`；事件规格第 8 节「payload 只做向后兼容的改动（加可选字段）」
- 问题：数据方向没有问题：已存储的旧事件（没有 `engine`、没有 `answer.revealed`）新代码照常读，不用改。反方向有问题：旧代码读到带 `engine` 的 `attempt.started`，会判为 `invalid` 放进隔离区；这一条一缺，同一 `attempt_id` 的其余事件首条不是 `attempt.started`，`attemptRule` 返回 4，整次尝试进 `conflicts`，掌握度和奖励都不算。`answer.revealed` 对旧代码只是被隔离，尝试本身不受影响。好在原始文字仍留在 `inbox`（`store.js`/`session.js` 启动时按原文重放，`device_seq` 存在 `meta`，不会复用），升级后重新读就恢复，所以不是不可逆；但「旧页面缓存、两个窗口、回滚、以后的 Python 参考内核和导入工具」都会碰到。第 8 节的「只加可选字段」只对「读的一方容忍未知字段」成立，而现在所有读者都不容忍。
- 建议：(a) 在第 8 节明确写出：加可选字段的前提是先让所有读者认识该字段，发布顺序是「先发能读的版本，再发会写的版本」，并把这条写进实现任务（`validate.js`/schema 先合入并发布，`quiz.js` 写入随后）；(b) 或者让校验器对 payload 里「形如可选字段但未知」的键放行，这会放松校验，要另做决定，这里不建议；(c) 验收 2 补一条：旧版校验器读新事件的预期行为（整次尝试进 `conflicts`）要写进向量，让这个已知行为有据可查。

## 6. `answer.revealed` 对状态机的改动被低估，而且「同一道题只记一次」没有任何规则保证

- 严重程度：重要
- 位置：evidence.md「1. 看答案」「要改的东西」；`engine/js/quiz.js` 的 `reveal` 分支和 `advance`；`app/app.js` 第 515–525 行 `revealAnswer`；slice-1.md 第 15、196、266–298、396 行；`engine/test/quiz-1b.test.js`
- 问题：现在 `reveal` 是同步的，不产生意图，不经过「写入、存好、失败」这套流程。要写事件，就必须和 `hint` 一样走 `pending → saved/failed → inflight`，而且答案要等事件存好以后才显示，否则「答案已经被看到、但事件没存上」，恰好是这份文档要避免的丢失。最后一题还要先存 `answer.revealed` 再产出 `attempt.completed`。这是对 1b 验收测试的实质修改（现有测试断言「看答案不产生意图」），evidence.md 一句「看答案时写」低估了。另外，合法性规则（6.3）没有为 `answer.revealed` 写任何要求，「同一次尝试里同一道题只记一次」只是文字，另一台设备、导入工具或 bug 写出来的重复事件、在没有任何作答之前的 `answer.revealed`、或者 `answer.revealed` 之后又有该题的 `item.answered`，内核都会照单全收。mastery 不读它，所以不会算错，但家长端以后拿它做「看过答案」统计时会出错。
- 建议：evidence.md 明确要求：看答案走和提示同样的「存好才显示」流程，失败可以重试；列出要同步修改的 slice-1.md 位置和 `quiz-1b.test.js`。在 6.3 末尾加第 6 条合法性规则（编号最大，不会改变现有的「记编号最小」行为；现有已存储的尝试里没有这个动词，所以不会让任何已有尝试变成不一致）：「`answer.revealed` 的 `item_id` 必须已有 `item.answered`，同一 `item_id` 最多一条，且之后不再有该题的 `item.answered`」；否则就写明「不做合法性检查，投影必须容忍重复」。

## 7. `corrections` 现在就承诺下来，与内容不可变和投影纯函数两条现有原则冲突

- 严重程度：重要
- 位置：evidence.md「4. 答案写错了怎么改」；ADR-003 第 2、4、7 条；事件规格 6.2、`mastery.js` 文件头（「不读……发布包」）
- 问题：(a) 「旧版本在内容里加一条 `corrections`」是原地修改已发布的活动版本。ADR-003 规定发布不可变，事件里的 `content_release` 指向的就是那一份哈希；要改只能出新发布，而新发布里不一定还带着旧的活动版本，也就不知道对旧版本如何套用 `corrections`。(b) 投影变成要读内容，6.2 要求输出只取决于「事件集合 + 算法版本号」；两台设备装了不同的发布，同一批事件算出不同掌握度，「和到达顺序无关」「增量等于全量」两条性质无从保证。(c) 漏了关联影响：答错的作答在做题时已经产生了 `repair.opened`，掌握度「没有未修好错题才点亮」。只改掌握度的判分，错题还开着，星星仍然亮不了；`corrections` 没有说怎么处理这些错题。(d) 事实上现在不需要它：`item.answered` 已经记了 `response`，将来重判的原料没有丢。
- 建议：从「定下来的」里去掉第 4 条，改写成一句原则：「原事件永不改；`response` 已记录，足够重判；具体机制（很可能是一条由家长或系统发出的更正**事件**，这样它同步、可审计、不引入新的投影输入）等第一次真的发现答案键写错时再设计，并先走 ADR」。保留「原事件里的 `correct` 一字不动、表示当时系统认为」这一句，那句是对的。

## 8. 旧数据其实可以推出「看过答案」，文档说「永远分不清」有点过头

- 严重程度：建议
- 位置：evidence.md 「1.」的「原因」一句；`quiz.js` 的 `advance`
- 问题：一次已完成的测验里，每题都必须有结果，要么答对存好，要么看过答案。所以对于已存储的、带 `attempt.completed` 的尝试，某道题最后一条 `item.answered` 是错的、之后没有该题的答对，就一定是看了答案（`reveal` 出现前也只有这一条路）。差别只是未完成（放弃）的尝试里看过答案但又离开，这一部分确实回不来。
- 建议：文档把「永远分不清」改成准确的说法（已完成的尝试可以推断，放弃的尝试无法推断），并在 `answer.revealed` 的说明里写一句「旧尝试按此规则推断」，这样 F3 的分析不会因为早期数据缺口而被当成完全断层。

## 9. 「先不定」清单整体安全，但有两项要补一句

- 严重程度：建议
- 位置：evidence.md「先不定的，以及什么时候定」表
- 问题：逐项检查「现在不记就以后拿不回来」：F1（学习目标 ID、年龄层次）：事件里有 `activity_id` + `activity_version` + `content_release`，发布永久保留（ADR-003 第 7 条），将来可以从发布里查到每条作答属于哪一层；安全。F4（矛盾事件收敛）、F5（统一核对入口）：不涉及记录，安全。F3 后半（首答、提示、重做的权重）：`try`、`hints_used`、`hint.used` 都已记录；安全。两处需要补充：(a) 第 2 条里提到的模拟 `tries` 丢失（见问题 2）没有出现在「先不定」表里，应该明确写成「已知丢弃」或者想办法记下；(b) 题序（`startQuiz` 的 `order` 参数）、模拟里的 `item`/`station` 具体含义不在事件里，现在固定题序（slice-1 1a），将来一旦改成随机题序，题序就需要记。这条不用现在定，但应该写进「什么时候必须定」：「第一次让题序随机之前」。
- 建议：在表里加这两行。

## 10. 与事实不符或遗漏的小地方

- 严重程度：建议
- 位置：evidence.md「要改的东西」「验收」
- 问题：(1) 「`validate.js`：认 `answer.revealed`」要同时改 `SLICE_VERBS`（`checkVerb` 用）和 `SCHEMA_VERBS`（信封用），以及 `schemas/event.schema.json` 的 `verb` 枚举；只改一处，事件会在信封通过、在 `checkVerb` 被拒，或者反过来。(2) `ingest-invalid.json` 现有向量里「信封多了 `recorded_at`」是拿 `attempt.started` 的信封作反例，不受影响；但 `fixtures/invalid/events.json` 里如果有「payload 多了一个键」的反例用的是 `engine` 以外的键名，没有冲突；实现者要确认没有现成反例恰好用 `engine` 当「多余键」。(3) 黄金向量清单要多加：`answer.revealed` 放在 `attempt.completed` 之后、没有对应 `item.answered`、重复两条这三种（取决于问题 6 的决定）。(4) 「`sim:` 开头的作答不生成错题」：`repairs/1` 本来就不从 `item.answered` 生成错题，`repair.opened` 由外壳写，这句话是对一个不存在的规则作出承诺，容易让实现者以为有这个规则要写；真正要写的是外壳在模拟尝试里不要开错题。
- 建议：按以上逐条补进「要改的东西」。

---

## 已核对、没有问题的部分

- `mastery/1`：`firstTryScore` 和 `projectMastery` 只读 `item.answered`，且只对 `activity_kind: "quiz"` 的尝试计分；`answer.revealed` 不影响它，`sim:` 的作答不进入任何测验尝试，所以不改变既有掌握度。「`mastery.js` 不改」成立。
- 奖励：`activity-done`、`repair-resolved` 等规则不读 `correct`，看答案、模拟作答都不影响，文档的说法正确。
- 「每道题都已作答才完成」：这是 `quiz.js` 状态机的规则（`advance`），不是内核规则；`reveal` 现在已经满足它（只有已有存好的作答才出现），加事件不改变这一点。
- 旧事件读新代码：新增的是可选字段和新动词，已存储的事件不受影响，`device_seq` 存在 `meta`，也不会被新旧代码混用而复用。
- 看答案的位置：`can_reveal` 要求本题已有 `tries ≥ 1`，所以首答先于 `answer.revealed`，「首答已定」成立。
