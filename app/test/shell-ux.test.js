// 正式外壳体验打磨的正反测试：题号时机、看答案文案清理、分母为 0 拦截、知识索引「只看已开放」、知识地铁「图鉴」标本墙、任务主次样式。
// 跑法：node --test app/test/shell-ux.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { startQuiz, step, DEFAULT_FEEDBACK } from "../../engine/js/quiz.js";
import { buildChart } from "../starchart.js";
import { aliasIndex, treeHtml, noteHtml } from "../explorer.js";
import { metroCardsHtml } from "../metro.js";
import { quizProgress, cleanRevealText, isZeroDenominator, ZERO_DENOM_TEXT } from "../app.js";

function readCatalog() {
  const text = readFileSync(new URL("../../content/catalog/points.yaml", import.meta.url), "utf8");
  const out = { points: [], retired: [] };
  let list = null, cur = null, inPre = false;
  for (const line of text.split("\n")) {
    if (/^points:/.test(line)) { list = out.points; continue; }
    if (/^retired:/.test(line)) { list = out.retired; continue; }
    if (!list) continue;
    const head = line.match(/^- id:\s*(.+)$/);
    if (head) { cur = { id: head[1].trim(), prerequisites: [] }; list.push(cur); inPre = false; continue; }
    const kv = line.match(/^  (title|grade|theme|unit|replaced_by|prerequisites):\s*(.*)$/);
    if (kv) {
      inPre = kv[1] === "prerequisites";
      if (inPre) cur.prerequisites = [];
      else cur[kv[1]] = kv[2].trim().replace(/^["']|["']$/g, "");
      continue;
    }
    const item = line.match(/^  - (.+)$/);
    if (item && inPre) cur.prerequisites.push(item[1].trim());
  }
  return out;
}

const sampleActivity = {
  id: "act.quiz.sample-01",
  kind: "quiz",
  version: 1,
  title: "测试挑战",
  body: {
    shuffle: false,
    items: [
      { id: "q1", stem: "第 1 题", answer: { type: "number", value: 5 }, feedback: { correct: "对。5 个五分之一。" }, hints: ["提示 1"] },
      { id: "q2", stem: "第 2 题", answer: { type: "fraction", numerator: 2, denominator: 4, accept_equivalent: true }, feedback: { correct: "对。从四分之一跳 1 步就到中间。" }, hints: ["提示 1"] },
      { id: "q3", stem: "第 3 题", answer: { type: "number", value: 8 }, feedback: { correct: "答对了！" }, hints: ["提示 1"] },
    ],
  },
};

test("题号时机：刚答对或刚点看答案还在看解析时，题号留在当前题；点下一题后才跳号", () => {
  let q = startQuiz(sampleActivity, ["q1", "q2", "q3"], "first");
  q = step(q, { type: "saved", id: q.pending.id }); // 进入第 1 题
  assert.deepEqual(quizProgress(q, null), { current: 1, total: 3, solvedBars: 0 });

  // 答错第 1 题：仍在第 1 题，0 格亮
  q = step(q, { type: "answer", response: "4" });
  q = step(q, { type: "saved", id: q.pending.id });
  assert.deepEqual(quizProgress(q, null), { current: 1, total: 3, solvedBars: 0 });

  // 答对第 1 题并存好：状态机内部已推进到 index=1，但界面 solvedId="q1" 仍在展示第 1 题解析
  q = step(q, { type: "answer", response: "5" });
  q = step(q, { type: "saved", id: q.pending.id });
  assert.deepEqual(quizProgress(q, "q1"), { current: 1, total: 3, solvedBars: 1 });

  // 孩子点「下一题」（solvedId 清空）：题号正式跳到 2 / 3
  assert.deepEqual(quizProgress(q, null), { current: 2, total: 3, solvedBars: 1 });

  // 第 2 题答错后点「看答案」：看解析时题号仍是 2 / 3，点下一题才变 3 / 3
  q = step(q, { type: "answer", response: "1/3" });
  q = step(q, { type: "saved", id: q.pending.id });
  q = step(q, { type: "reveal" });
  q = step(q, { type: "saved", id: q.pending.id });
  assert.deepEqual(quizProgress(q, "q2"), { current: 2, total: 3, solvedBars: 2 });
  assert.deepEqual(quizProgress(q, null), { current: 3, total: 3, solvedBars: 2 });

  // 最后一题答对存好并完成：点「看看结果」之前，题号仍是 3 / 3、满 3 格
  q = step(q, { type: "answer", response: "8" });
  q = step(q, { type: "saved", id: q.pending.id });
  q = step(q, { type: "saved", id: q.pending.id }); // attempt.completed
  assert.equal(q.phase, "done");
  assert.deepEqual(quizProgress(q, "q3"), { current: 3, total: 3, solvedBars: 3 });
});

test("看答案文案清理：剥除「对。」「答对了！」「你看出了」等答对夸奖前缀，保留数学与科学解释", () => {
  assert.equal(cleanRevealText("对。从四分之一跳 1 步就到中间。它和二分之一是同一个点。"), "从四分之一跳 1 步就到中间。它和二分之一是同一个点。");
  assert.equal(cleanRevealText("没错，4 个六分之一合起来是六分之四。"), "4 个六分之一合起来是六分之四。");
  assert.equal(cleanRevealText("你看出了掰开以后两块都还是 4 排。"), "掰开以后两块都还是 4 排。");
  assert.equal(cleanRevealText("你把 14 掰成 10 和 4，两块都乘了 6：60 + 24 = 84。"), "把 14 掰成 10 和 4，两块都乘了 6：60 + 24 = 84。");
  // 原本只有「答对了！」没有解释时，回退到默认揭晓文案
  assert.equal(cleanRevealText("答对了！"), DEFAULT_FEEDBACK.revealed);
  assert.equal(cleanRevealText(""), DEFAULT_FEEDBACK.revealed);
  // 本来就是中性解释的句子原样保留（反例）
  assert.equal(cleanRevealText("每一格都是七分之一杯，2 格再加 3 格，是七分之五杯。"), "每一格都是七分之一杯，2 格再加 3 格，是七分之五杯。");
  assert.doesNotMatch(ZERO_DENOM_TEXT, /学习/);
});

test("分母为 0 判断：半角、全角、多个零都拦住，合法正整数和空串不误拦", () => {
  assert.equal(isZeroDenominator("0"), true);
  assert.equal(isZeroDenominator("00"), true);
  assert.equal(isZeroDenominator(" ０ "), true);
  assert.equal(isZeroDenominator("4"), false);
  assert.equal(isZeroDenominator("10"), false);
  assert.equal(isZeroDenominator(""), false);
});

test("知识索引「只看已开放」：开启后只显示已开放的星座和星球，搜索也同步过滤", () => {
  const catalog = readCatalog();
  const nodes = [
    { id: "math.decimal.tenths", activities: ["act.x"] },
    { id: "biology.genetics.dna-intro", activities: ["act.y"] },
  ];
  const mastery = { nodes: { "math.decimal.tenths": { state: "lit" } } };
  const model = buildChart({ catalog, nodes, mastery, grade: 3 });
  const aliases = aliasIndex(catalog, model.byId);

  // 关闭时：全部 28 个星座都在
  const full = treeHtml(model, { query: "", isOpen: () => false, aliases, onlyOpen: false });
  assert.equal((full.match(/class="grp"/g) || []).length, 28);
  assert.match(full, /data-treeopen aria-pressed="false">只看已开放 · <span class="mono">2<\/span>/);

  // 开启时：只剩含已开放星的 2 个星座、2 个叶子，不再出现 closed 叶子
  const filtered = treeHtml(model, { query: "", isOpen: () => true, aliases, onlyOpen: true });
  assert.match(filtered, /data-treeopen aria-pressed="true">/);
  assert.equal((filtered.match(/class="grp"/g) || []).length, 2);
  assert.equal((filtered.match(/class="leaf"/g) || []).length, 2);
  assert.doesNotMatch(filtered, /data-state="closed"/);
  assert.match(filtered, /数学星系 · <span class="mono">1\/1<\/span>/);
  assert.match(filtered, /科学星系 · <span class="mono">0\/1<\/span>/);

  // 搜索时开启 onlyOpen 也只留已开放的星
  const qAll = treeHtml(model, { query: "分数", isOpen: () => false, aliases, onlyOpen: false });
  const qOpen = treeHtml(model, { query: "分数", isOpen: () => false, aliases, onlyOpen: true });
  assert.ok((qAll.match(/class="leaf/g) || []).length > 0);
  assert.match(qOpen, /找到 0 颗星球/);
  assert.doesNotMatch(filtered, /学习/);
});

test("知识地铁「图鉴」标本墙：102 张卡齐全，已点亮盖「已收集」章，高学段未开放隐藏名字", () => {
  const catalog = readCatalog();
  const nodes = [
    { id: "math.decimal.tenths", activities: ["act.x"] },
    { id: "biology.genetics.dna-intro", activities: ["act.y"] },
  ];
  const mastery = { nodes: { "math.decimal.tenths": { state: "lit" } } };
  const model = buildChart({ catalog, nodes, mastery, grade: 3 });
  const html = metroCardsHtml(model, { selected: "math.decimal.tenths" });

  assert.equal((html.match(/data-spec="/g) || []).length, 102);
  assert.equal((html.match(/class="stamp"/g) || []).length, 1);
  assert.match(html, /class="spec sel" data-spec="math\.decimal\.tenths" aria-current="true"/);
  // 初二已开放的 DNA 星虽然高于三年级，但已开放，显示真名
  assert.match(html, /DNA：细胞里的说明书/);
  // 高中未开放的星对三年级舰长显示「？？？」
  assert.match(html, /？？？/);
  assert.doesNotMatch(html, /学习/);
});

test("星球笔记任务主次样式：primary=false 渲染次级按钮，并带「看图鉴」跳转链接", () => {
  const catalog = readCatalog();
  const model = buildChart({ catalog, nodes: [{ id: "math.decimal.tenths", activities: ["act.sim", "act.quiz"] }], mastery: null, grade: 3 });
  const p = model.byId.get("math.decimal.tenths");
  const html = noteHtml(p, {
    card: { driving_question: "十份里的一份？" },
    model,
    tasks: [
      { id: "act.sim", title: "百格板", meta: "动手探索 · 3 站", go: "开始", primary: true },
      { id: "act.quiz", title: "小数大挑战", meta: "挑战 · 5 道题", go: "开始", primary: false },
    ],
    canStart: true,
  });
  assert.match(html, /class="btn ink" data-start="act\.sim">开始<\/button>/);
  assert.match(html, /class="btn" data-start="act\.quiz">开始<\/button>/);
  assert.match(html, /data-specjump="math\.decimal\.tenths">看图鉴<\/a>/);
});
