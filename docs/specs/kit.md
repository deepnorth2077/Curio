# 规格：画风与手感的唯一出处 · 零件库、配色下发与程序化微音效（CURIO-010 / #107）

- 状态：已定（按 `docs/reviews/pr-108.md` 12 条审阅意见，及 Luka 2026-11-21、2026-11-25 拍板修订）
- 依据：ADR-011、ADR-003（含增补 1）、ADR-005、ADR-008、`docs/activity-contract.md`、`docs/specs/navigators.md`、内容规格 3.8、`docs/handoff.md` 主线第 5 步
- 实现任务：主线第 5 步（分 5a、5b 两步交付，见「怎么分步」）

## 问题

- **维护与实现上**：颜色变量、手绘线 `sketchLib`、宿主通信 `Host`、圆钮 `grip`、上下分数 `fracS` 和页面骨架在二十多个模块里重复抄写，且外壳与模块深色值不一致（外壳紫 `#A797F7`、模块赭 `#E0876A`）。
- **视觉体验上**：在外壳切换明暗模式或调整配色时，沙箱内的模块不能完整跟着切换。
- **听觉触感上**：全站完全静音，小火箭跳步、掰开巧克力、转动圆钮棘轮、点亮星星都缺少物理微音效反馈；而模块在沙箱内既不能联网加载音频，也不能读存储里的静音开关。

## 方案

1. **运行时状态由宿主下发（`activity/1.2`）**：颜色表（20 个平台键）、明暗模式（`scheme`）、静音开关（`muted`）与领航员（`navigator`）由外壳在 `init` 下发；运行中途切明暗或静音时，外壳通过 `theme`、`mute` 消息实时同步给沙箱。
2. **颜色表与冻结代码分文件存放**：`kit/tokens.css` 存可演进的平台颜色变量，同步进外壳；`kit/<版本号>/`（`kit.css`、`kit.js`）存按版本冻结的骨架、手绘线、圆钮分数零件和**程序化微音效引擎 `Sfx`**，由 `tools/kit.py` 写进模块标记段并由 CI 逐字节核对。
3. **原生 Web Audio 程序化微音效（无背景音乐）**：外壳（`app/sfx.js`）与模块（`kit/<版本号>/kit.js`）共用 7 个克制的物理「声位」，零外部音频文件，附全局静音开关。

## 用户故事

1. 作为舰长，我在外壳切换深浅模式后进入动手探索，或在探索中途切换，里面的底色、卡片、按钮和强调色都和外面一致。
2. 作为舰长，我拨动圆钮、让火箭跳步、掰开巧克力、答对题目和点亮星星时，能听到轻柔干净的物理声响；想安静时点一下静音开关，外面和活动里立刻都安静下来。
3. 作为家长，已发布的旧模块（`activity/1.1`）不被悄悄改坏，画面与进度照旧。
4. 作为维护者，改配色只改 `kit/tokens.css` 一处；CI 自动拦截手改库代码、漏写 `kit` 版本或引入外部音频资源。

## 实现上的决定

### 1. 契约 `activity/1.2`

#### 1.1 `init` 的 payload

| 字段 | `1.1` | `1.2` |
| --- | --- | --- |
| `age_band`、`lang`、`phase`、`mastery` | 有 | 不变 |
| `completed_stations`、`activity_completed`、`question_available` | 可选（slice-5a） | 可选，不变 |
| `navigator` | 可选（`navigators.md`） | 可选：`{id, faces: {curious, waiting, surprised, clap, think, wrong}}` |
| `palette` | 键名未规定 | 必填对象，包含下面 20 个平台键，值为十六进制颜色 |
| `scheme` | 无 | `"light"` 或 `"dark"` |
| `muted` | 无 | 布尔值（`true` 静音，`false` 有声；缺省按 `false`） |

#### 1.2 运行期宿主 → 模块增量消息（`1.2` 新增）

- `{ contract: "activity/1.2", type: "theme", payload: { scheme: "light"|"dark", palette: { …20 键… } } }`：外壳在活动打开期间切换明暗时发送，模块即时更新 `.kit-dark`、`color-scheme` 和 CSS 变量。
- `{ contract: "activity/1.2", type: "mute", payload: { muted: true|false } }`：外壳切换静音开关时发送，模块即时调用 `Sfx.setMuted(p.muted)`。

#### 1.3 `palette` 的 20 个平台键

去掉领域专用色 `dad`、`mom`（留在遗传模块自身样式里），保留平台通用的中性色、强调色、圆钮控件色、4 个淡彩色位（含 `sage-bg`）和正误状态色，共 20 个键：

`bg`、`pane`、`hover`、`rule`、`ink`、`text`、`muted`、`accent`、`accent-soft`、`grip`、`grip-soft`、`sage`、`sage-bg`、`sky`、`apricot`、`paper`、`good`、`good-soft`、`bad`、`bad-soft`

- **深色基准值**（Luka 2026-11-21 定）：强调色沿用外壳紫色 `--accent: #A797F7`、`--accent-soft: #2D2943`；纸色沿用外壳 `--paper: #2A2738`；圆钮色保持 `--grip: #5FC4BE`、`--grip-soft: #1F3634`（圆钮规格 G2：强调色不上控件，圆钮色不外借）。
- **颜色值校验（两端同规则）**：只允许确定能解析的十六进制颜色 `/^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/`，免得非法值令 CSS 变量失效。宿主自检发出的每个值；模块对不认识的键或不合格的值忽略，缺键回退到库里的默认值。以后在 `1.2` 内增加新键属于向后兼容扩展，不必升主/次版本。

#### 1.4 模块与宿主的兼容规则

- **宿主同时认 `activity/1.1` 和 `activity/1.2`**：消息信封的 `contract` 字段严格按该模块 `manifest.yaml` 声明的版本收发。
- **冻结 `1.1` 现状**：对未迁移的 `activity/1.1` 模块，正式外壳和试玩壳保持现有 `init` 下发行为不变（不强灌紫色 `--accent`，不改 `1.1` 模块画面）；只对 `activity/1.2` 模块发 20 键 `palette`、`scheme` 和 `muted`。
- **首帧不闪烁**：在 iframe 内运行时（`window.parent !== window`），`Kit.start(enter)` 先发 `ready`，等待 `init` 到达后再应用配色/明暗并调用 `enter()`；若 `300ms` 内未收到 `init`（如简易测试容器），超时后用默认配色进入 `enter()`。独立打开时（不在 iframe 内）直接调用 `enter()`。
- **Schema 与门禁**：`schemas/activity.schema.json` 中 `contract` 改为 `enum: ["activity/1.1", "activity/1.2"]`；新增正整数字段 `kit`；当 `contract` 为 `"activity/1.2"` 时 `kit` 必填，当 `contract` 为 `"activity/1.1"` 时禁止出现 `kit`。通过分站模拟承担正式讲解的 1.2 活动，在清单中声明 `station_count`，供宿主验证并恢复进度。`docs/specs/content.md` 第 5 节、`docs/activity-contract.md`、`tools/ci_checks.py`（`explains_node`）与 `app/app.js`、`app/exploration.js`、`preview/template.html` 同步认 `"activity/1.2"`。

---

### 2. 程序化微音效零件（`Sfx`）

#### 2.1 设计边界

- **无背景音乐、无循环音、无外部音频文件**：只用浏览器原生 `AudioContext`（`OscillatorNode`、`GainNode`、短噪声 `AudioBuffer` + `BiquadFilterNode`）实时合成一次性物理微音效。
- **克制不吵耳**：单次发声时长控制在 `15ms～600ms`，峰值增益上限 `<= 0.12`（高频触发的 `tick` 上限 `<= 0.05`），播完立即断开节点回收。
- **静音与环境降级**：
  - 外壳在 `localStorage`（键 `curio.muted`，`"1"` 为静音，默认有声；主题键 `curio.theme`，`"light" | "dark"`，未设时跟随系统）保存偏好——这两项是设备界面偏好，不是学习事实，不写学习事件，也不改变备份格式。
  - 外壳左侧导航栏底部（桌面端 `.ribbon` 锁图标上方、移动端顶栏/家长页旁，不增加页面导航项）提供轻量的**声音开关**与**明暗切换**按钮，带清晰 `aria-label` 与 `aria-pressed`。
  - `muted === true`、环境无 `AudioContext`（如 Node 单测）、或浏览器尚未收到用户手势解锁音频时，所有 `Sfx.*()` 静默无操作，不抛错。
  - 在 `pointerdown`、`keydown`、`touchend` 或 `click` 的用户手势中，若 `AudioContext.state === "suspended"`，自动调用 `resume()`。

#### 2.2 七个语义「声位」

模块与外壳只调用语义声位，不在业务代码里手写频率和包络：

| 声位 | 时长与合成特征 | 触发场景 |
| --- | --- | --- |
| `Sfx.tick(step = 0)` | `~18ms` 带通瞬态短脉冲，音高随 `step` 在小范围内微移；内置 `35ms` 最小间隔节流 | 拨动圆钮过刻度、拖滑尺过格、按住连跳 |
| `Sfx.hop(step = 0)` | `~55ms` 正弦/三角波快衰减，基频随 `step` 温和上扬（最多 12 阶封顶） | 数线小火箭跳一步、挂砝码、向前走一格 |
| `Sfx.snap()` | `~40ms` 清脆高通咔哒瞬态叠短木腔低音 | 掰开巧克力、切分一刀、拉开小门、拼合卡槽 |
| `Sfx.tap()` | `~22ms` 柔和纸面轻点 | 点选按钮、切换站点、切换领航员 |
| `Sfx.right()` | `~180ms` 纯五度双音上行轻拨（如 `C5 → G5`） | 挑战答对一题、探索猜对、完成一站 |
| `Sfx.nudge()` | `~90ms` 低柔木质双轻叩（不用刺耳蜂鸣器） | 答错触发误区引导、分母填 0 等温和提醒 |
| `Sfx.lit()` | `~550ms` 温暖四音泛音琶音和弦（如 `C5–E5–G5–C6`），配 1.2 秒点亮动效；`prefers-reduced-motion` 下照常发声（除非静音） | 星星首次点亮、动手探索全部站完成领星卡 |

- **测试接缝**：`createSfx({ AudioCtx, nowMs })` 纯工厂函数（以最新 `kit/<N>/kit.js` 的 `curio-sfx` 标记段为原件，工具同步到 `app/sfx.js` 导出）支持在 `node:test` 注入假 `AudioCtx` 与假时钟，精确验证：静音时不建节点、`35ms` 节流生效、7 个声位参数合法且自动清理节点、无 `AudioCtx` 时不抛错。

---

### 3. 库的目录、标记与检查工具

```
kit/
  tokens.css    不分版本的 20 个平台色位变量（浅色 :root 与深色规则），同步进外壳
  1/
    kit.css     模块独立运行时的后备色位（浅色 + .kit-dark）、字体、三种手绘线、卡片、气泡、按钮、圆钮（kit:grip）、上下分数（kit:frac）
    kit.js      Host（activity/1.2，支持 palette/scheme/muted/navigator 及运行期 theme/mute 消息）、sketchLib、fracS/oneMark/grip/lineStrip、Sfx 七声位、选站重玩外壳与 Kit.start
    README.md   元数据（contract: activity/1.2）与本版说明
```

#### 3.1 同步标记与 `tools/kit.py`

- 模块文件（`index.html`）样式与脚本各一段：
  `/* curio-kit:1 begin */` … `/* curio-kit:1 end */`
- 外壳文件（`app/index.html`、`preview/template.html`）颜色变量段：
  `/* curio-tokens begin */` … `/* curio-tokens end */`
  系统深色和手动深色都从同一份深色色值生成。同步工具按平台色表生成 `--curio-palette-keys`，宿主读取这些键并校验各值。深浅两套色表使用同一组键。
  段后保留外壳别名：`--c-sci: var(--sage); --c-sci-bg: var(--sage-bg); --c-math: var(--apricot); --c-sky: var(--sky); --wash: var(--paper);`（`--c-sci-2`、`--c-math-2`、`--c-math-bg` 留在外壳自身）。
- **明确扫描白名单**（不扫 `docs/`、`prompts/` 或构建产物）：
  - `app/sfx.js` 的 `curio-sfx` 段
  - `app/index.html`、`preview/template.html`（原型 `prototype/index.html` 已冻结，不强改）
  - `.claude/skills/curio-anatomy/references/starter.html`（改为基于 `curio-kit:1` 的薄骨架）
  - `content/activities/*/index.html` 中对应 `manifest.yaml` 声明了 `kit` 的模块
- `python tools/kit.py sync [文件…]`：按标记写入对应文件（LF 换行）。
- `python tools/kit.py check`：逐字节核对白名单内所有带标记文件与 `kit/` 原件一致，不一致返回非零退出码。

#### 3.2 `tools/ci_checks.py` 与 `tools/module_lint.py` 新增规则

1. `contract: "activity/1.2"` 的模块必填 `kit: N`，`index.html` 必须包含样式与脚本两段 `curio-kit:N`，且逐字节等于 `kit/<N>/` 原件，且 `kit/<N>/README.md` 声明的契约等于 `"activity/1.2"`。
2. `1.2` 模块的 `<style>` 里不得出现 `prefers-color-scheme`（明暗一律走 `.kit-dark` 类），模块自己的深色变量写在 `.kit-dark` 下。
3. 标记段以外不得重新声明 `kit` 导出的顶层名字（`Host`、`Kit`、`Sk`、`sketchLib`、`Sfx`、`fracS`、`oneMark`、`grip`、`lineStrip` 等）。允许函数内部定义独立的局部变量。
4. 模块内禁止 `<audio>`、`<video>` 或外部音频引用（`module_lint.py`），声音统一走 `Sfx`。
5. 版本首次发布前，检查后备色与当时平台色表一致。主线上的活动一旦使用过某一版，该版目录就永久冻结，即使使用它的最后一个活动已迁走。之后平台可以改色和增加色位，只同步外壳。独立打开的旧活动继续使用其发版时的后备色。

---

## 怎么分步（按 `docs/handoff.md` 主线第 5 步）

| 步 | 做完以后能看到什么 | 改到哪里 |
| --- | --- | --- |
| **5a** | 1. 正式外壳有「明暗切换」和「声音开关」；挑战答对、误区提醒、点亮星星有轻柔微音效，点静音立刻安静。<br>2. 建立 `kit/tokens.css`、`kit/1/`、`tools/kit.py`、CI 与 schema 门禁，正式宿主支持 `1.2`。<br>3. 迁移两颗代表星（《几分之几：数线跳跳》验证火箭跳步 `hop` 与拨片，《乘法分配律：掰巧克力》验证掰开 `snap` 与拖拽 `tick`）到 `activity/1.2` + `kit: 1`：在外壳切明暗或切静音后进入（或中途切换），模块配色、强调色 `#A797F7` 与微音效全部跟着切换；四个生命/其他 `1.1` 模块零改动照常可玩。 | `schemas/activity.schema.json`、`docs/`、`GLOSSARY.md`、`kit/`、`tools/kit.py`、`tools/ci_checks.py`、`tools/module_lint.py` 及正反测试、`app/`、`preview/template.html`、`starter.html`、两颗标杆活动模块 |
| **5b** | Luka 与舰长试玩确认 5a 的深浅配色与微音效音量/音色满意后，其余需改版或新建的模块直接用薄骨架 `kit: 1`（目标单模块自有代码 400 行以内）。 | 后续新星或改版星的 `kp/` 分支 |

---

## 测试接缝与验收用例

| 接缝 | 验证什么 |
| --- | --- |
| `tools/kit.py check` + `test_kit.py`（正反例） | 原样通过；手改标记段内 1 个字符报错；缺半边标记报错；不存在的 `kit: 99` 报错；已上 `main` 的 `kit/1/` 被改动报错；`1.2` 模块写了 `prefers-color-scheme` 或重声明 `Sfx`/`Host` 报错 |
| `app/test/sfx.test.js`（假 `AudioContext`） | 7 个声位正常合成并自动断开节点；`muted: true` 时零节点创建；`tick` 在 `35ms` 内连续调用只响一次；无 `AudioContext` 环境不抛错 |
| `app/test/exploration.test.js`（宿主契约测试） | `1.2` 模块收到 20 键十六进制 `palette`、`scheme`、`muted`；外壳切明暗发 `theme`、切静音发 `mute`；`1.1` 模块仍按原样收到 `activity/1.1` 消息且不被强灌紫色强调色 |
| 走查与浏览器实测 | 迁移后的《数线跳跳》和《掰巧克力》走查全绿；外壳切浅色/深色进入同一活动，按钮、选中态和紫色强调色 `#A797F7` 跟着切换；静音开关对挑战和探索同时生效 |

## 不做什么

- 不加背景音乐、环境白噪音或语音朗读，不引入任何音频资源文件。
- 不为明暗模式或静音开关写学习事件（它们是本机界面偏好，不是学习事实）。
- 不往已冻结的 `prototype/index.html` 加新功能。
- 不在 5a 一次性强迁全部 23 颗已发布模块，先用 2 颗代表星让 Luka 和舰长真机验收手感与音量。
