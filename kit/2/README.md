# 共用零件库第 2 版（kit/2）

contract: activity/1.2

依据：`docs/specs/kit.md`（CURIO-010 / #107）、ADR-011、ADR-003（增补 1）。

## 包含内容

- `kit.css`：长按不选字规则（#156）、模块独立打开时的 20 个平台色位后备值（`:root` 浅色与 `:root.kit-dark` 深色，深色强调色为 `#A797F7`）、字体变量、卡片与对话气泡、按钮、圆钮（`kit:grip`）与上下结构分数（`kit:frac`）。
- `kit.js`：
  - `Host`（`activity/1.2`）与 `Kit.start(enter)`：接收 `init`（`palette`、`scheme`、`muted`、`navigator`、`completed_stations`、`activity_completed`、`question_available`）及运行期 `theme`、`mute` 增量消息；沙箱内等待 `init`（最多 `300ms`）后再渲染首帧，避免闪白。
  - `Sfx`：8 个原生 Web Audio 程序化微音效声位（`tick`、`hop`、`snap`、`tap`、`discover`、`right`、`nudge`、`lit`）。宿主静音时，已排队的声部也会停止。`tools/kit.py sync` 从最新整数版本的 `kit.js` 读取 `curio-sfx` 标记段，将同一份 `createSfx` 同步到 `app/sfx.js`。
  - `sketchLib` / `Sk`、`fracS`、`oneMark`、`grip`、`lineStrip` 及选站重玩页面外壳。

猜测题统一由 `ask()` 发轻点声。操作完成一轮或看到结果时调用 `Sfx.discover()`。首次完成一站由 `observedOnce(n)` 发完成音，首次拿星卡由 `Host.complete()` 发琶音。模块只上报相应进度。总音量固定为 3×，声音通过压缩器输出。详细参数和使用场景见 `docs/specs/kit.md` 第 2.3 节。

## 活动怎样接入

普通 HTML 或 Canvas 活动可直接使用 `Kit.start(enter)`、`Host` 和 `Sfx`。在单文件 HTML 的 style 与 script 元素中各放一对库标记，再运行 `tools/kit.py sync` 内联样式和脚本。把模块逻辑放在脚本标记之后。下面的活动会根据年级渲染首屏，收到阶段变化时更新操作状态。

```js
const stopPhase = Host.on("phase", p => setPhase(p.phase));
Kit.start(p => render(p.age_band || "G3-4"));
```

`enter` 只调用一次。独立打开或等待 300 ms 超时后，它收到空对象。迟到的 `init` 仍会更新配色和静音。活动可同时订阅 `init`、`theme`、`mute`、`phase` 和 `hint`。每个订阅独立生效，调用返回的函数（如 `stopPhase()`）即可退订。使用 `Host.requestHint()` 请求提示，使用 `Host.noteQuestion(text)` 提问。

采用 starter 站卡布局时，传入 `{ stations: {} }` 启用画布尺寸适配、提问按钮和选站重玩。部分活动允许从首次未完成的一站继续，可提供该站的正常入口。重玩仍使用活动的 `REPLAY[n]`。

```js
Kit.start(enter1, { stations: { resume: n => enterStation(n) } });
```

`resume(n)` 收到从 1 开始的站号。只有连续完成的站后面仍有新站时，选站页才显示「继续第 n 站」。省略回调时沿用「重玩」和「从头玩」两个选择。

## 不可变约定

一旦 `main` 分支上已有模块声明 `kit: 2`，本目录下的文件不得修改；后续不兼容演进请新建 `kit/3/`。由 `tools/kit.py` 同步并由 CI 逐字节核对。
