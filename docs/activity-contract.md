# 互动模块契约 activity/1.1

互动模块是讲解、实验、测验等可插拔的小程序。每个模块由两个文件组成：

- `manifest.yaml`：描述模块，格式见 `schemas/activity.schema.json`；
- `index.html`：单文件实现。

平台把模块放进 `sandbox="allow-scripts"` 的 iframe 里运行，双方只通过 `postMessage` 通信。每条消息都带 `contract: "activity/1.1"`，不带的一律忽略。

## 硬性约束

- 不发起任何网络请求，不读写 `localStorage` 或 IndexedDB。
- 不依赖外部 CDN，所需的库全部内联。
- 在 768 px 宽的平板上完整可用，只用触摸也能操作。
- 支持键盘操作，尊重 `prefers-reduced-motion`。
- 实验类：画面和读数必须来自同一个模型。读数措辞按 `age_band` 选择，三四年级用「更亮 / 更暗、清楚 / 模糊」，初二以上再显示公式和数值。

## 消息

| 方向 | type | payload | 说明 |
| --- | --- | --- | --- |
| 模块 → 平台 | `ready` | — | 模块加载完成。平台 3 秒内没收到 `ready`，会记一条契约警告。 |
| 平台 → 模块 | `init` | `{age_band, lang, phase, palette, mastery}` | `palette` 是当前主题的颜色表，模块据此设置自己的 CSS 变量，保证和平台的明暗主题一致。 |
| 平台 → 模块 | `phase` | `{phase}` | 实验类的阶段：`predict`（锁定操作）、`observe`（解锁）。 |
| 模块 → 平台 | `event` | `{verb, result}` | 一条学习事件。`verb` 必须在 manifest 的 `emits` 里声明过，否则平台会记一条契约警告。 |
| 模块 → 平台 | `state` | 可观测量的当前值 | 实验类在每次变化时发送，平台用它生成「解释」一步里的对比，例如亮度从「很暗」变成「较亮」。 |
| 模块 → 平台 | `request_hint` | — | 请求下一级提示。 |
| 平台 → 模块 | `hint` | `{level}` | 允许显示第 `level` 级提示。 |
| 模块 → 平台 | `note_question` | `{text}` | 把孩子的疑问发到信号站。 |
| 模块 → 平台 | `complete` | `{score, total}` 或 `{}` | 模块结束。`score`、`total` 只用于诊断，宿主不把它们记进事件：分数一律由平台从作答事件算出（`docs/specs/events.md` 第 3.1 节）。 |
| 模块 → 平台 | `resize` | `{h}` | 内容高度变化时发送，平台据此调整 iframe 高度。 |
| 模块 → 平台 | `ai_request` | `{capability, input}` | **计划中**：申请调用 AI 能力，必须先在 manifest 的 `capabilities` 里声明 `ai:<能力名>`。 |

## 「预测 → 观察 → 解释」由谁做

`pedagogy: POE` 的实验，三步之中只有「观察」由模块实现。

1. **预测**：平台根据 manifest 的 `predict` 出题，这时模块处于锁定状态。
2. **观察**：平台发送 `phase: observe`，模块解锁。孩子操作，模块持续发送 `state`；孩子点「观察完了」，模块发送 `event: observed`。
3. **解释**：平台对比预测和观察结果，展示 `explain` 里的解释，并收集一句反思。

## 最小实现

```html
<script>
const Host = (() => {
  const h = {};
  addEventListener("message", e => { const m = e.data; if (m && m.contract === "activity/1.1" && h[m.type]) h[m.type](m.payload || {}); });
  const send = (type, payload) => parent.postMessage({ contract: "activity/1.1", type, payload: payload || {} }, "*");
  if (window.ResizeObserver) new ResizeObserver(() => send("resize", { h: document.documentElement.scrollHeight })).observe(document.body);
  return {
    on: (k, f) => { h[k] = f },
    ready: () => send("ready"),
    event: (verb, result) => send("event", { verb, result }),
    state: o => send("state", o),
    requestHint: () => send("request_hint"),
    noteQuestion: text => send("note_question", { text }),
    complete: r => send("complete", r)
  };
})();

Host.on("init", p => { /* 应用 p.palette，按 p.age_band 选读数措辞 */ });
Host.on("phase", p => { if (p.phase === "observe") { /* 解锁操作 */ } });
Host.ready();
</script>
```

完整样例：`prototype/index.html` 里的 `MODULES.pinholeModule`（小孔成像实验）和 `MODULES.quizModule`（分数挑战）。
