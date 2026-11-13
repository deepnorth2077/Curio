// 1b 的挑战状态机验收测试（竖切片 1 规格 6.4）。Claude 派发前写好，实现者不改（受保护路径）。
// 接口沿用 quiz.test.js 开头固定的 view 字段，6.4 再加：
//   view.item         {id, stem, figure}（没有配图时 figure 是 null）
//   view.answer_type  "choice" | "number" | "fraction"
//   view.choices      选择题是 [{id, text}]（不带 correct、misconception）
//   view.unit         数字题的 unit，没有时 null
//   view.hints        当前这道题已存好的提示原文，按顺序
//   view.can_hint、view.can_reveal   布尔值
//   看答案时 view.feedback = {item_id, correct: false, revealed: true, answer_text, text}，text 是这道题的
//   feedback.correct，没有时是默认的话（非空）
// 看答案先存再显示（CURIO-013，docs/specs/evidence.md 第 1 条）：reveal 被接受时产出 answer.revealed 意图
//   {item_id}，和 hint.used 走同一套 saved / failed / retry；存好以后才显示答案、进入下一题
import { test } from "node:test";
import assert from "node:assert/strict";
import { startQuiz, step } from "../js/quiz.js";

const ACT = {
  id: "act.quiz.fraction-intro-01", schema: "activity-def/1", kind: "quiz", version: 2, title: "分数小挑战",
  targets: ["math.number.fraction-intro"], engine: 1, review: "approved",
  body: {
    shuffle: false,
    items: [
      { id: "q1", stem: "涂色部分是这个圆的几分之几？", figure: { type: "pie", parts: 4, shaded: 1 },
        feedback: { correct: "平均分成 4 份，涂了 1 份，就是 1/4。" },
        answer: { type: "choice", choices: [
          { id: "c", text: "4/1", misconception: "flip", feedback: "总份数写在横线下面。" },
          { id: "a", text: "1/4", correct: true },
          { id: "b", text: "1/3", misconception: "part-vs-rest" }] },
        hints: ["先数一数一共几份。", "涂色的有几份？"] },
      { id: "q2", stem: "能直接用 1/3 表示吗？",
        answer: { type: "choice", choices: [
          { id: "a", text: "不能，因为三份不一样大", correct: true },
          { id: "b", text: "能", misconception: "equal-parts" }] },
        hints: ["这三份一样大吗？"] },
      { id: "q3", stem: "涂色部分是这张纸条的几分之几？",
        answer: { type: "fraction", numerator: 3, denominator: 4, accept_equivalent: false, common_wrong: [
          { numerator: 4, denominator: 3, misconception: "flip" },
          { numerator: 3, denominator: 1, misconception: "part-vs-rest" }] },
        hints: ["横线下面写总份数。", "横线上面写涂色的份数。", "一共几份？涂了几份？"] },
      { id: "q4", stem: "这个蛋糕一共切成了几块？",
        answer: { type: "number", value: 6, tolerance: 0, unit: "块", common_wrong: [{ value: 1, misconception: "flip" }] },
        hints: ["横线下面的数表示一共几份。", "每块是几分之一？"] },
      { id: "q5", stem: "一根绳子长多少米？",
        answer: { type: "number", value: 2.5, tolerance: 0 },
        hints: ["看看刻度。"] },
    ],
  },
};
const ORDER = ["q1", "q2", "q3", "q4", "q5"];
const RIGHT = { q1: "a", q2: "a", q3: "3/4", q4: "6", q5: "2.5" };
const WRONG = { q1: "b", q2: "b", q3: "4/3", q4: "1", q5: "3" };

const act = () => structuredClone(ACT);
const snap = (x) => structuredClone(x);
const save = (q) => { assert.ok(q.pending, "这里应该有 pending"); return step(q, { type: "saved", id: q.pending.id }); };
const answerSaved = (q, r) => { q = step(q, { type: "answer", response: r }); assert.equal(q.pending?.verb, "item.answered"); return save(q); };
const hintSaved = (q) => { q = step(q, { type: "hint" }); assert.equal(q.pending?.verb, "hint.used"); return save(q); };
const revealSaved = (q) => { q = step(q, { type: "reveal" }); assert.equal(q.pending?.verb, "answer.revealed"); return save(q); };
const begun = (a = act(), order = ORDER) => save(startQuiz(a, order, "first"));
/** 前面几题一次答对，停在 id 这一题。 */
function at(id) {
  let q = begun();
  for (const k of ORDER) { if (k === id) break; q = answerSaved(q, RIGHT[k]); }
  assert.equal(q.view.item_id, id);
  return q;
}

test("view.item 是 {id, stem, figure}；没有配图时 figure 是 null", () => {
  let q = begun();
  assert.deepEqual(q.view.item, { id: "q1", stem: "涂色部分是这个圆的几分之几？", figure: { type: "pie", parts: 4, shaded: 1 } });
  q = answerSaved(q, RIGHT.q1);
  assert.deepEqual(q.view.item, { id: "q2", stem: "能直接用 1/3 表示吗？", figure: null });
});

test("选择题的 view：answer_type、choices 只有 id 和 text；一开始不能要提示、不能看答案", () => {
  const q = begun();
  assert.equal(q.view.answer_type, "choice");
  assert.deepEqual(q.view.choices, [{ id: "c", text: "4/1" }, { id: "a", text: "1/4" }, { id: "b", text: "1/3" }]);
  assert.deepEqual(q.view.hints, []);
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, false);
});

test("还没有已存好的作答：hint、reveal 原样返回", () => {
  const q = begun();
  const s = snap(q);
  assert.deepEqual(step(q, { type: "hint" }), s);
  assert.deepEqual(step(q, { type: "reveal" }), s);
});

test("答错存好以后能要提示：level 从 1 递增，存好才显示，用完就不能再要", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  assert.equal(q.view.can_hint, true);
  assert.equal(q.view.can_reveal, true);
  q = step(q, { type: "hint" });
  assert.deepEqual(q.pending.payload, { item_id: "q1", level: 1 });
  assert.equal(q.pending.verb, "hint.used");
  assert.equal(q.view.waiting, true);
  assert.deepEqual(q.view.hints, [], "没存好不显示");
  q = save(q);
  assert.deepEqual(q.view.hints, ["先数一数一共几份。"]);
  assert.equal(q.view.can_hint, true);
  q = step(q, { type: "hint" });
  assert.deepEqual(q.pending.payload, { item_id: "q1", level: 2 });
  q = save(q);
  assert.deepEqual(q.view.hints, ["先数一数一共几份。", "涂色的有几份？"]);
  assert.equal(q.view.can_hint, false, "两条都用完了");
  const s = snap(q);
  assert.deepEqual(step(q, { type: "hint" }), s, "用完以后原样返回");
});

test("三条提示的题：level 依次是 1、2、3", () => {
  let q = at("q3");
  q = answerSaved(q, WRONG.q3);
  const levels = [];
  for (let i = 0; i < 3; i++) {
    q = step(q, { type: "hint" });
    levels.push(q.pending.payload.level);
    q = save(q);
  }
  assert.deepEqual(levels, [1, 2, 3]);
  assert.equal(q.view.hints.length, 3);
  assert.equal(q.view.can_hint, false);
});

test("hints_used 是这道题已存好的提示条数（累计）；提示不改 try", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  q = hintSaved(q);
  q = step(q, { type: "answer", response: "c" });
  assert.deepEqual(q.pending.payload, { item_id: "q1", response: "c", correct: false, try: 2, hints_used: 1, misconception: "flip" });
  q = save(q);
  q = hintSaved(q);
  q = step(q, { type: "answer", response: RIGHT.q1 });
  assert.deepEqual(q.pending.payload, { item_id: "q1", response: "a", correct: true, try: 3, hints_used: 2 });
  q = save(q);
  q = answerSaved(q, WRONG.q2);
  q = step(q, { type: "answer", response: RIGHT.q2 });
  assert.equal(q.pending.payload.hints_used, 0, "换了一道题，从 0 算起");
});

test("提示没存上：不显示、不计入 hints_used；再试存好以后才算", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  q = step(q, { type: "hint" });
  const p = snap(q.pending);
  q = step(q, { type: "failed", id: p.id });
  assert.deepEqual(q.pending, p);
  assert.equal(q.view.failed, true);
  assert.deepEqual(q.view.hints, []);
  const s = snap(q);
  assert.deepEqual(step(q, { type: "answer", response: RIGHT.q1 }), s, "提示还在等存储，作答原样返回");
  assert.deepEqual(step(q, { type: "hint" }), s, "等存储时再要提示原样返回");
  assert.deepEqual(step(q, { type: "reveal" }), s, "等存储时看答案原样返回");
  q = step(q, { type: "retry" });
  q = step(q, { type: "saved", id: p.id });
  assert.deepEqual(q.view.hints, ["先数一数一共几份。"]);
  q = step(q, { type: "answer", response: RIGHT.q1 });
  assert.equal(q.pending.payload.hints_used, 1);
});

test("换到下一题：提示清空，下一题一开始不能要提示", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  q = hintSaved(q);
  q = answerSaved(q, RIGHT.q1);
  assert.equal(q.view.item_id, "q2");
  assert.deepEqual(q.view.hints, []);
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, false);
});

test("看答案：产出 answer.revealed 意图 {item_id}；存好以后进入下一题，feedback 带 revealed 和 answer_text", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  q = step(q, { type: "reveal" });
  assert.equal(q.pending?.verb, "answer.revealed", "看答案要先写事件");
  assert.deepEqual(q.pending.payload, { item_id: "q1" });
  q = save(q);
  assert.equal(q.pending, null);
  assert.equal(q.phase, "answering");
  assert.equal(q.view.item_id, "q2");
  assert.deepEqual(q.view.feedback, { item_id: "q1", correct: false, revealed: true, answer_text: "1/4",
    text: "平均分成 4 份，涂了 1 份，就是 1/4。" }, "有 feedback.correct 时用它");
  assert.deepEqual(q.view.hints, [], "下一题的提示是空的");
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, false);
});

test("看答案等存储时：还停在这道题，答案不显示；answer、hint、reveal 都原样返回", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  const before = snap(q.view.feedback);
  assert.equal(before.item_id, "q1", "前提：feedback 是那次答错的反馈");
  assert.equal(before.revealed, undefined);
  assert.equal(before.answer_text, undefined);
  q = step(q, { type: "reveal" });
  assert.equal(q.pending?.verb, "answer.revealed");
  assert.equal(q.phase, "answering");
  assert.equal(q.view.item_id, "q1", "没存好之前不进入下一题");
  assert.equal(q.view.waiting, true);
  assert.equal(q.view.failed, false);
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, false);
  assert.deepEqual(q.view.feedback, before, "没存好之前答案不显示，feedback 还是那次答错的");
  const s = snap(q);
  assert.deepEqual(step(q, { type: "answer", response: RIGHT.q1 }), s, "等存储时作答原样返回");
  assert.deepEqual(step(q, { type: "hint" }), s, "等存储时要提示原样返回");
  assert.deepEqual(step(q, { type: "reveal" }), s, "等存储时再看答案原样返回");
  assert.deepEqual(step(q, { type: "saved", id: q.pending.id + 1 }), s, "过期或不对的 saved 原样返回");
});

test("看答案没存上：failed 后答案仍不显示；retry 不改状态；再 saved 才显示、进入下一题", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  const before = snap(q.view.feedback);
  q = step(q, { type: "reveal" });
  const p = snap(q.pending);
  assert.equal(p.verb, "answer.revealed");
  q = step(q, { type: "failed", id: p.id });
  assert.deepEqual(q.pending, p, "pending 原样保留");
  assert.equal(q.view.failed, true);
  assert.equal(q.view.waiting, true);
  assert.equal(q.view.item_id, "q1");
  assert.deepEqual(q.view.feedback, before, "没存上，答案不显示");
  const s = snap(q);
  assert.deepEqual(step(q, { type: "answer", response: RIGHT.q1 }), s);
  assert.deepEqual(step(q, { type: "hint" }), s);
  assert.deepEqual(step(q, { type: "reveal" }), s);
  q = step(q, { type: "retry" });
  assert.deepEqual(q, s, "retry 不改状态");
  q = step(q, { type: "saved", id: p.id });
  assert.equal(q.pending, null);
  assert.equal(q.view.failed, false);
  assert.equal(q.view.item_id, "q2");
  assert.deepEqual(q.view.feedback, { item_id: "q1", correct: false, revealed: true, answer_text: "1/4",
    text: "平均分成 4 份，涂了 1 份，就是 1/4。" });
});

test("看答案的 answer_text：分数题是「分子/分母」，数字题带单位，没有单位时只有数", () => {
  let q = at("q3");
  q = answerSaved(q, WRONG.q3);
  q = revealSaved(q);
  assert.equal(q.view.feedback.answer_text, "3/4");
  assert.ok(typeof q.view.feedback.text === "string" && q.view.feedback.text.length > 0, "没有 feedback.correct 时用默认的话");
  q = answerSaved(q, WRONG.q4);
  q = revealSaved(q);
  assert.equal(q.view.feedback.answer_text, "6 块");
  q = answerSaved(q, WRONG.q5);
  q = revealSaved(q);
  assert.equal(q.view.feedback.answer_text, "2.5");
});

test("最后一题看答案：先存 answer.revealed，再进入 finishing、只产出一次完成；分母不变，看过答案的题不计入分子", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  q = revealSaved(q); // q1 看答案
  for (const id of ["q2", "q3", "q4"]) q = answerSaved(q, RIGHT[id]);
  q = answerSaved(q, WRONG.q5);
  q = hintSaved(q);
  q = step(q, { type: "reveal" });
  assert.equal(q.phase, "answering", "answer.revealed 没存好之前不进入 finishing");
  assert.equal(q.pending?.verb, "answer.revealed");
  assert.deepEqual(q.pending.payload, { item_id: "q5" });
  assert.equal(q.view.item_id, "q5");
  assert.equal(q.view.feedback?.revealed, undefined, "没存好之前答案不显示");
  const p = snap(q.pending);
  q = step(q, { type: "failed", id: p.id });
  assert.equal(q.phase, "answering", "没存上也不进入 finishing");
  assert.equal(q.view.feedback?.revealed, undefined);
  q = step(q, { type: "saved", id: p.id });
  assert.equal(q.phase, "finishing");
  assert.equal(q.pending.verb, "attempt.completed");
  assert.deepEqual(q.pending.payload, {});
  assert.equal(q.pending.id, p.id + 1, "完成的意图 id 紧接着 answer.revealed");
  const fb = q.view.feedback;
  assert.deepEqual({ ...fb, text: undefined }, { item_id: "q5", correct: false, revealed: true, answer_text: "2.5", text: undefined }, "存好以后才显示答案");
  assert.ok(typeof fb.text === "string" && fb.text.length > 0, "没有 feedback.correct 时用默认的话");
  const s = snap(q);
  assert.deepEqual(step(q, { type: "reveal" }), s, "finishing 时看答案原样返回");
  assert.deepEqual(step(q, { type: "hint" }), s);
  q = save(q);
  assert.equal(q.phase, "done");
  assert.deepEqual(q.view.result, { first_try_correct: 3, total: 5 });
  assert.equal(q.pending, null);
});

test("带看答案做完：意图依次是 started、answered、revealed……completed，id 从 1 连续递增，completed 只有一次", () => {
  let q = startQuiz(act(), ORDER, "first");
  const seen = [snap(q.pending)];
  q = save(q);
  const push = (x) => { seen.push(snap(x.pending)); return save(x); };
  q = push(step(q, { type: "answer", response: WRONG.q1 }));
  q = push(step(q, { type: "reveal" }));
  q = push(step(q, { type: "answer", response: RIGHT.q2 }));
  q = push(step(q, { type: "answer", response: WRONG.q3 }));
  q = push(step(q, { type: "hint" }));
  q = push(step(q, { type: "reveal" }));
  q = push(step(q, { type: "answer", response: RIGHT.q4 }));
  q = push(step(q, { type: "answer", response: WRONG.q5 }));
  q = push(step(q, { type: "reveal" }));
  assert.equal(q.phase, "finishing");
  seen.push(snap(q.pending));
  q = save(q);
  assert.equal(q.phase, "done");
  assert.equal(q.pending, null);
  assert.deepEqual(seen.map((p) => [p.id, p.verb]), [
    [1, "attempt.started"],
    [2, "item.answered"], [3, "answer.revealed"],
    [4, "item.answered"],
    [5, "item.answered"], [6, "hint.used"], [7, "answer.revealed"],
    [8, "item.answered"],
    [9, "item.answered"], [10, "answer.revealed"],
    [11, "attempt.completed"],
  ]);
  assert.deepEqual(seen.filter((p) => p.verb === "answer.revealed").map((p) => p.payload), [{ item_id: "q1" }, { item_id: "q3" }, { item_id: "q5" }]);
  assert.deepEqual(q.view.result, { first_try_correct: 2, total: 5 });
});

test("数字题：view 有 unit；判分走 grade，误区来自 common_wrong；全角数字也认", () => {
  let q = at("q4");
  assert.equal(q.view.answer_type, "number");
  assert.equal(q.view.unit, "块");
  q = step(q, { type: "answer", response: "1" });
  assert.deepEqual(q.pending.payload, { item_id: "q4", response: "1", correct: false, try: 1, hints_used: 0, misconception: "flip" });
  q = save(q);
  q = step(q, { type: "answer", response: "６" });
  assert.equal(q.pending.payload.correct, true);
  assert.equal(q.pending.payload.response, "６", "事件里记孩子原样的作答");
  q = save(q);
  assert.equal(q.view.item_id, "q5");
  assert.equal(q.view.unit, null, "没有单位时是 null");
});

test("分数题：view.answer_type 是 fraction；3/4 对，4/3、3/1 各是自己的误区，6/8 不接受等值", () => {
  let q = at("q3");
  assert.equal(q.view.answer_type, "fraction");
  q = step(q, { type: "answer", response: "4/3" });
  assert.equal(q.pending.payload.misconception, "flip");
  q = save(q);
  q = step(q, { type: "answer", response: "3/1" });
  assert.equal(q.pending.payload.misconception, "part-vs-rest");
  q = save(q);
  q = step(q, { type: "answer", response: "6/8" });
  assert.deepEqual(q.pending.payload, { item_id: "q3", response: "6/8", correct: false, try: 3, hints_used: 0 });
  q = save(q);
  q = step(q, { type: "answer", response: "3/4" });
  assert.equal(q.pending.payload.correct, true);
});

test("作答超过 32 个码点原样返回；正好 32 个补充平面字符可以", () => {
  const q = begun();
  const s = snap(q);
  assert.deepEqual(step(q, { type: "answer", response: "𝟘".repeat(33) }), s);
  const ok = step(q, { type: "answer", response: "𝟘".repeat(32) });
  assert.equal(ok.pending.verb, "item.answered");
  assert.equal(ok.pending.payload.correct, false);
});

test("三种题型都能开始；数不满足规则时抛错", () => {
  assert.doesNotThrow(() => startQuiz(act(), ORDER, "first"));
  const bad = [
    (a) => { a.body.items[3].answer.value = Number.NaN; },
    (a) => { a.body.items[3].answer.value = Number.POSITIVE_INFINITY; },
    (a) => { a.body.items[3].answer.value = 0.1234567; },
    (a) => { a.body.items[3].answer.value = 1e9; },
    (a) => { a.body.items[3].answer.value = "6"; },
    (a) => { a.body.items[3].answer.tolerance = -1; },
    (a) => { a.body.items[3].answer.tolerance = 1.5e-7; },
    (a) => { a.body.items[3].answer.common_wrong[0].value = 1e9; },
    (a) => { a.body.items[2].answer.denominator = 0; },
    (a) => { a.body.items[2].answer.denominator = 1000000; },
    (a) => { a.body.items[2].answer.numerator = 1.5; },
    (a) => { a.body.items[2].answer.common_wrong[0].denominator = 0; },
  ];
  bad.forEach((f, i) => { const a = act(); f(a); assert.throws(() => startQuiz(a, ORDER, "first"), undefined, `第 ${i + 1} 种`); });
  const okA = act();
  okA.body.items[4].answer.tolerance = 0.5;
  okA.body.items[2].answer.denominator = 999999;
  okA.body.items[3].answer.value = -999999999.5;
  assert.doesNotThrow(() => startQuiz(okA, ORDER, "first"), "边界上的数可以");
});

test("没有 hints 的题：can_hint 一直是 false", () => {
  const a = act();
  delete a.body.items[0].hints;
  let q = begun(a);
  q = answerSaved(q, WRONG.q1);
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, true);
  const s = snap(q);
  assert.deepEqual(step(q, { type: "hint" }), s);
});

test("等作答存储时：hint、reveal 原样返回，can_hint、can_reveal 都是 false", () => {
  let q = begun();
  q = answerSaved(q, WRONG.q1);
  q = step(q, { type: "answer", response: "c" });
  assert.equal(q.pending.verb, "item.answered");
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, false);
  const s = snap(q);
  assert.deepEqual(step(q, { type: "hint" }), s);
  assert.deepEqual(step(q, { type: "reveal" }), s);
});

test("starting、finishing、done 时 can_hint、can_reveal 都是 false", () => {
  let q = startQuiz(act(), ORDER, "first");
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, false);
  q = save(q);
  for (const id of ORDER) q = answerSaved(q, RIGHT[id]);
  assert.equal(q.phase, "finishing");
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, false);
  q = save(q);
  assert.equal(q.phase, "done");
  assert.equal(q.view.can_hint, false);
  assert.equal(q.view.can_reveal, false);
});

test("提示多于 3 条时只用前 3 条", () => {
  const a = act();
  a.body.items[0].hints = ["一", "二", "三", "四"];
  let q = begun(a);
  q = answerSaved(q, WRONG.q1);
  for (let i = 1; i <= 3; i++) { q = step(q, { type: "hint" }); assert.equal(q.pending.payload.level, i); q = save(q); }
  assert.deepEqual(q.view.hints, ["一", "二", "三"]);
  assert.equal(q.view.can_hint, false);
  const s = snap(q);
  assert.deepEqual(step(q, { type: "hint" }), s);
});

test("分数题的分子可以是 0；分子、分母（含 common_wrong）越界时抛错", () => {
  const ok = act();
  ok.body.items[2].answer.common_wrong[0].numerator = 0;
  assert.doesNotThrow(() => startQuiz(ok, ORDER, "first"), "common_wrong 的分子是 0 可以");
  const zero = act();
  zero.body.items[2].answer.numerator = 0;
  assert.doesNotThrow(() => startQuiz(zero, ORDER, "first"), "分子是 0 可以（0/4）");
  const bad = [
    (a) => { a.body.items[2].answer.numerator = -1; },
    (a) => { a.body.items[2].answer.numerator = 1000000; },
    (a) => { a.body.items[2].answer.common_wrong[0].numerator = -1; },
    (a) => { a.body.items[2].answer.common_wrong[0].numerator = 1000000; },
    (a) => { a.body.items[2].answer.common_wrong[1].denominator = 1000000; },
    (a) => { a.body.items[2].answer.denominator = 4.5; },
  ];
  bad.forEach((f, i) => { const a = act(); f(a); assert.throws(() => startQuiz(a, ORDER, "first"), undefined, `第 ${i + 1} 种`); });
});
