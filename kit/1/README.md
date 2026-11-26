# 共用零件库第 1 版（kit/1）

contract: activity/1.2

依据：`docs/specs/kit.md`（CURIO-010 / #107）、ADR-011、ADR-003（增补 1）。

## 包含内容

- `kit.css`：长按不选字规则（#156）、模块独立打开时的 20 个平台色位后备值（`:root` 浅色与 `:root.kit-dark` 深色，深色强调色为 `#A797F7`）、字体变量、卡片与对话气泡、按钮、圆钮（`kit:grip`）与上下结构分数（`kit:frac`）。
- `kit.js`：
  - `Host`（`activity/1.2`）与 `Kit.start(enter)`：接收 `init`（`palette`、`scheme`、`muted`、`navigator`、`completed_stations`、`activity_completed`、`question_available`）及运行期 `theme`、`mute` 增量消息；沙箱内等待 `init`（最多 `300ms`）后再渲染首帧，避免闪白。
  - `Sfx`：7 个原生 Web Audio 程序化微音效声位（`tick`、`hop`、`snap`、`tap`、`right`、`nudge`、`lit`），无外部音频资源，受宿主 `muted` 控制。
  - `sketchLib` / `Sk`、`fracS`、`oneMark`、`grip`、`lineStrip` 及选站重玩页面外壳。

## 不可变约定

一旦 `main` 分支上已有模块声明 `kit: 1`，本目录下的文件不得修改；后续不兼容演进请新建 `kit/2/`。由 `tools/kit.py` 同步并由 CI 逐字节核对。
