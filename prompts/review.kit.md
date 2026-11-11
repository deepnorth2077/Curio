---
task: review.kit
issue: 107
version: v1
---

# 审阅任务：Curio 的画风只留一个出处（ADR-011 和零件库规格）

## 背景

「Curio」是一个家庭自用的理科探索网站，陪一个孩子从 2026 年小学三年级用到 2036 年高三。仓库只有一个维护者 Claude；Luka（家长，不写代码）负责验收和传话。互动模块是「`manifest.yaml` + 单文件 `index.html`」，运行在沙箱 iframe 里，只通过契约 activity/1.1 的消息和平台通信。

现在同一套画风（颜色、手绘线、页面骨架）抄在外壳、试玩页、骨架和每个模块里，而且已经抄出了不一致。一个具体的例子：契约说颜色由宿主通过 `init.palette` 下发，但没规定键名。原型里的宿主是这样取的：

```js
return {bg:g("--bg"),pane:g("--pane"),hover:g("--hover"),rule:g("--rule"),ink:g("--ink"),text:g("--text"),muted:g("--muted"),accent:g("--accent"),accentSoft:g("--accent-soft"),sci:g("--c-sci"),sci2:g("--c-sci-2"),sciBg:g("--c-sci-bg"),math:g("--c-math"), …}
```

而模块骨架是这样用的（只接受全小写加连字符的键，并且变量叫 `--sage`、`--apricot`）：

```js
Host.on("init", p => {
  if (p && p.palette) for (const [k, v] of Object.entries(p.palette)) if (/^[a-z-]+$/.test(k)) document.documentElement.style.setProperty("--" + k, v);
});
```

所以淡彩色块实际上没有跟着宿主变。

Claude 写了 ADR-011（提议）和一份规格 `docs/specs/kit.md`：颜色和明暗模式由宿主发全，契约升到 activity/1.2；骨架和手绘线放进按版本管理的 `kit/`，由工具写进模块里标好的两段，CI 逐字节核对。这次只写了决定和规格，还没有实现。Claude 写的架构改动不能自己审，所以请你来审。

## 你的角色

资深前端架构师，熟悉长期维护的内容平台、沙箱 iframe、设计令牌和版本兼容。请挑刺，不要客气。这个项目只有一个家庭在用、维护者不写代码，所以「部件少、十年后还看得懂」比「灵活」重要。

## 请重点看这些问题

1. **分法对不对**：「数值运行时下发、代码按版本抄进模块」这条线划得对吗？有没有哪样东西放错了边？线宽、字号、动效留在库里而不进契约，十年里会不会后悔？
2. **契约 1.2 的兼容性**：宿主对 1.1 的模块也发 20 个键和 `scheme`，已发布的 1.1 模块会不会出现画面变化或别的意外？「只增不改」站得住吗？升版本和「当作澄清」哪个更对？
3. **`palette` 的值只接受十六进制颜色**：够不够安全？会不会太严（以后想用别的颜色写法）？
4. **标记加同步工具**：把库的内容写进已提交的文件、再由 CI 逐字节核对，这个办法和 ADR-008（不打包、提交的就是能运行的）、ADR-003（发布不可变）有没有冲突？有没有更简单的办法达到同样的效果？「已有模块在用的版本不能改」这条 CI 规则可行吗？
5. **被放弃的方案**：运行时由宿主注入库，这个方案放弃得对不对？理由有没有漏洞？
6. **分步和验收**：三步的顺序对吗？「迁移前后消息序列相同、截图差异不超过 0.5%」作为「行为没变」的证据够不够？验收用例有没有漏掉重要的情况（比如深色模式、单独打开、`reduced-motion`）？
7. **名字**：颜色统一叫 `sage`、`sky`、`apricot`、`paper`，外壳旧名字留作别名。十年里换了配色以后，`sage` 这个名字不再是鼠尾草绿了怎么办？有没有更好的命名办法，又不必现在就大改？
8. **和已有文档有没有矛盾**：ADR-003、ADR-005、ADR-008、契约、manifest 的 schema。

## 资料

以下文件全部取自同一个提交，原样贴入。

{{embed: docs/adr/0011-single-source-style.md}}

{{embed: docs/specs/kit.md}}

{{embed: docs/activity-contract.md}}

{{embed: schemas/activity.schema.json}}

{{embed: docs/adr/0003-immutable-releases.md}}

{{embed: docs/adr/0005-activity-host-boundary.md}}

{{embed: docs/adr/0008-frontend-stack.md}}

{{embed: .claude/skills/curio-anatomy/references/starter.html}}

## 输出格式

用简体中文，按下面的格式输出，不要写补丁，说清楚问题和建议即可：

```
# 审阅意见 · issue #107 · 审阅者：<模型名和版本>

## 结论
可以合入 / 改完再合入 / 需要大改（一句话说明）

## 问题
### 1. <一句话标题>
- 严重程度：阻断 / 重要 / 建议
- 位置：<文件和章节>
- 问题：<具体说明>
- 建议：<怎么改>

## 对三个拍板问题的看法
（ADR-011 末尾的三个问题，各一句话：同意推荐，或者不同意和理由）
```
