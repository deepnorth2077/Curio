// 挑战状态机的验收测试（竖切片 1 规格 6.1）。Claude 派发前写好，实现者不改（受保护路径）。
//
// 这份测试固定了规格 6.1 里没有逐字写出的几个 view 字段名（实现者照这个来）：
//   q.view.item_id   当前这道题的 item_id（starting、finishing、done 时可以是 null）
//   q.view.waiting   有 pending 时为 true
//   q.view.failed    最近一次 pending 收到 failed、还没再收到对应的 saved 时为 true
//   q.view.feedback  最近一次已存好的作答的反馈：{item_id, correct, text}；还没有时为 null
//   q.view.result    done 时为 {first_try_correct, total}，其他时候为 null
// pending 是 {id, verb, payload}；item.answered 的 payload 没有误区时不写 misconception 字段；
// attempt.completed 的 payload 是 {}（duration_ms 由外壳补，规格 6.1）。
// feedback.text 的取法照规格 6.3「作答」：答对用这道题的 feedback.correct；答错用这个选项的 feedback，
// 没有就用这道题的 feedback.wrong，再没有就用默认的话（默认的话这里只要求是非空字符串）。
// 状态必须是普通数据（能 structuredClone），「原样返回」用深比较检查。
import { test } from "node:test";
import assert from "node:assert/strict";
import { startQuiz, step } from "../js/quiz.js";

const ACT = {
  id: "act.quiz.fraction-intro-01", schema: "activity-def/1", kind: "quiz", version: 1, title: "分数小挑战",
  targets: ["math.number.fraction-intro"], engine: 1, review: "approved",
  body: {
    shuffle: false,
    items: [
      { id: "q1", stem: "涂色部分是这个圆的几分之几？", figure: { type: "pie", parts: 4, shaded: 1 },
        answer: { type: "choice", choices: [
          { id: "c", text: "4/1", misconception: "flip", feedback: "总份数写在横线下面，涂色份数写在横线上面。" },
          { id: "a", text: "1/4", correct: true },
          { id: "b", text: "1/3", misconception: "part-vs-rest", feedback: "涂色的 1 份要和整个圆的 4 份相比，不是和没涂色的 3 份比。" }] },
        feedback: { correct: "平均分成 4 份，涂了 1 份，就是 1/4。" } },
      { id: "q2", stem: "能直接用 1/3 表示吗？",
        answer: { type: "choice", choices: [
          { id: "a", text: "不能", correct: true },
          { id: "b", text: "能", misconception: "equal-parts", feedback: "只有平均分时，其中一份才是整体的 1/3。" }] } },
      { id: "q3", stem: "涂色部分是这张纸条的几分之几？",
        answer: { type: "choice", choices: [
          { id: "a", text: "4/3", misconception: "flip" },
          { id: "c", text: "3/4", correct: true }] } },
      { id: "q4", stem: "吃了这个西瓜的几分之几？",
        answer: { type: "choice", choices: [
          { id: "a", text: "1/7", misconception: "part-vs-rest" },
          { id: "b", text: "1/8", correct: true }] },
        feedback: { wrong: "再数一数，西瓜一共切成了几块？" } },
      { id: "q5", stem: "涂色部分是这个正方形的几分之几？",
        answer: { type: "choice", choices: [
          { id: "a", text: "2/1" },
          { id: "c", text: "1/2", correct: true }] } },
    ],
  },
};
const ORDER = ["q1", "q2", "q3", "q4", "q5"];
const RIGHT = { q1: "a", q2: "a", q3: "c", q4: "b", q5: "c" };
const WRONG = { q1: "b", q2: "b", q3: "a", q4: "a", q5: "a" };

const act = () => structuredClone(ACT);
const json = (x) => structuredClone(x);

/** 存好当前 pending。 */
function save(q) {
  assert.ok(q.pending, "这里应该有 pending");
  return step(q, { type: "saved", id: q.pending.id });
}
/** 作答并存好。 */
function answerSaved(q, response) {
  q = step(q, { type: "answer", response });
  assert.equal(q.pending?.verb, "item.answered");
  return save(q);
}
/** 开始并存好 started。 */
function begun(order = ORDER, mode = "first") {
  return save(startQuiz(act(), order, mode));
}

test("开始：phase 是 starting，pending 是 attempt.started，带 mode", () => {
  const q = startQuiz(act(), ORDER, "first");
  assert.equal(q.phase, "starting");
  assert.equal(q.pending.verb, "attempt.started");
  assert.deepEqual(q.pending.payload, { mode: "first" });
  assert.equal(q.view.waiting, true);
  assert.equal(q.view.result, null);
  const r = startQuiz(act(), ORDER, "retry");
  assert.deepEqual(r.pending.payload, { mode: "retry" });
});

test("started 存好以后进入 answering，停在 order 的第一道题", () => {
  let q = begun();
  assert.equal(q.phase, "answering");
  assert.equal(q.pending, null);
  assert.equal(q.view.waiting, false);
  assert.equal(q.view.item_id, "q1");
  q = begun(["q3", "q1", "q2", "q5", "q4"]);
  assert.equal(q.view.item_id, "q3");
});

test("正常做完：每题一次答对，意图依次是 started、5 条 answered、1 条 completed，id 递增", () => {
  let q = startQuiz(act(), ORDER, "first");
  const seen = [q.pending];
  q = save(q);
  for (const id of ORDER) {
    q = step(q, { type: "answer", response: RIGHT[id] });
    seen.push(q.pending);
    assert.deepEqual(q.pending.payload, { item_id: id, response: RIGHT[id], correct: true, try: 1, hints_used: 0 });
    q = save(q);
  }
  assert.equal(q.phase, "finishing");
  assert.equal(q.pending.verb, "attempt.completed");
  assert.deepEqual(q.pending.payload, {}, "意图不带时间，duration_ms 由外壳补");
  seen.push(q.pending);
  q = save(q);
  assert.equal(q.phase, "done");
  assert.equal(q.pending, null);
  assert.deepEqual(q.view.result, { first_try_correct: 5, total: 5 });
  assert.deepEqual(seen.map((p) => p.verb), ["attempt.started", ...ORDER.map(() => "item.answered"), "attempt.completed"]);
  const ids = seen.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length, "意图 id 不重复");
  for (let i = 1; i < ids.length; i++) assert.ok(ids[i] > ids[i - 1], "意图 id 递增");
});

test("答错：payload 带这个选项的误区；存好后停在这道题，再答时 try 是 2", () => {
  let q = begun();
  q = step(q, { type: "answer", response: WRONG.q1 });
  assert.deepEqual(q.pending.payload, { item_id: "q1", response: "b", correct: false, try: 1, hints_used: 0, misconception: "part-vs-rest" });
  q = save(q);
  assert.equal(q.phase, "answering");
  assert.equal(q.view.item_id, "q1", "只存好了一次答错的作答，停在这道题");
  assert.deepEqual(q.view.feedback, { item_id: "q1", correct: false, text: "涂色的 1 份要和整个圆的 4 份相比，不是和没涂色的 3 份比。" });
  q = step(q, { type: "answer", response: "c" });
  assert.equal(q.pending.payload.try, 2);
  assert.equal(q.pending.payload.misconception, "flip");
  q = save(q);
  q = step(q, { type: "answer", response: RIGHT.q1 });
  assert.equal(q.pending.payload.try, 3);
  assert.equal(q.pending.payload.correct, true);
  assert.equal("misconception" in q.pending.payload, false, "答对时不写误区");
  q = save(q);
  assert.equal(q.view.item_id, "q2");
  assert.equal(q.view.feedback.item_id, "q1");
  assert.equal(q.view.feedback.correct, true);
});

test("错误选项没有误区、不是任何选项的 id：判错，payload 不写 misconception", () => {
  let q = begun(["q5", "q1", "q2", "q3", "q4"]);
  q = step(q, { type: "answer", response: "a" });
  assert.deepEqual(q.pending.payload, { item_id: "q5", response: "a", correct: false, try: 1, hints_used: 0 });
  q = save(q);
  q = step(q, { type: "answer", response: "zz" });
  assert.deepEqual(q.pending.payload, { item_id: "q5", response: "zz", correct: false, try: 2, hints_used: 0 });
});

test("最后一道的正确作答没存上：不产出完成；失败、再试时 pending 不变", () => {
  let q = begun();
  for (const id of ORDER.slice(0, 4)) q = answerSaved(q, RIGHT[id]);
  q = step(q, { type: "answer", response: RIGHT.q5 });
  const p = structuredClone(q.pending);
  q = step(q, { type: "failed", id: p.id });
  assert.equal(q.phase, "answering");
  assert.deepEqual(q.pending, p, "failed 后 pending 原样保留");
  assert.equal(q.view.failed, true);
  assert.equal(q.view.waiting, true);
  const beforeRetry = json(q);
  q = step(q, { type: "retry" });
  assert.deepEqual(q, beforeRetry, "retry 不改状态");
  q = step(q, { type: "failed", id: p.id });
  assert.deepEqual(q.pending, p);
  q = step(q, { type: "saved", id: p.id });
  assert.equal(q.view.failed, false);
  assert.equal(q.phase, "finishing");
  assert.equal(q.pending.verb, "attempt.completed");
});

test("缺任何一道已存好的作答都不完成：前几题没存上时，最后一题答对也不完成", () => {
  // 每一题都先答一次、收到 failed、再存好；看中间任何时刻都没有 completed
  let q = begun();
  for (const id of ORDER) {
    q = step(q, { type: "answer", response: RIGHT[id] });
    q = step(q, { type: "failed", id: q.pending.id });
    assert.notEqual(q.phase, "finishing");
    assert.equal(q.pending.verb, "item.answered");
    assert.equal(q.view.item_id, id, "没存好就不前进");
    q = save(q);
  }
  assert.equal(q.phase, "finishing");
});

test("等待存储时再作答、过期的 saved、failed 都不产生新意图", () => {
  let q = begun();
  q = step(q, { type: "answer", response: WRONG.q1 });
  const p = structuredClone(q.pending);
  const s1 = json(q);
  q = step(q, { type: "answer", response: RIGHT.q1 });
  assert.deepEqual(q, s1, "等待存储时作答原样返回");
  q = step(q, { type: "saved", id: p.id + 100 });
  assert.deepEqual(q, s1, "id 对不上的 saved 忽略");
  q = step(q, { type: "failed", id: p.id - 1 });
  assert.deepEqual(q, s1, "id 对不上的 failed 忽略");
  q = save(q);
  const s2 = json(q);
  q = step(q, { type: "saved", id: p.id });
  assert.deepEqual(q, s2, "已经确认过的 saved 再来一次，忽略");
});

test("starting 时作答原样返回", () => {
  const q = startQuiz(act(), ORDER, "first");
  const s = json(q);
  assert.deepEqual((step(q, { type: "answer", response: "a" })), s);
});

test("完成只产出一次；finishing、done 以后作答和多余的 saved 都不产生意图", () => {
  let q = begun();
  for (const id of ORDER) q = answerSaved(q, RIGHT[id]);
  assert.equal(q.phase, "finishing");
  const cid = q.pending.id;
  const s = json(q);
  assert.deepEqual((step(q, { type: "answer", response: "a" })), s, "finishing 时作答原样返回");
  q = step(q, { type: "saved", id: cid });
  assert.equal(q.phase, "done");
  const d = json(q);
  q = step(q, { type: "saved", id: cid });
  assert.deepEqual(q, d);
  q = step(q, { type: "answer", response: "a" });
  assert.deepEqual(q, d);
  assert.equal(q.pending, null);
});

test("结果的分母是活动题数，分子是 try=1 答对的题数", () => {
  let q = begun();
  // q1、q3 先错后对，其余一次答对：try=1 答对的是 q2、q4、q5，共 3 道；5 道题都有作答
  for (const id of ORDER) {
    if (id === "q1" || id === "q3") q = answerSaved(q, WRONG[id]);
    q = answerSaved(q, RIGHT[id]);
  }
  q = save(q);
  assert.equal(q.phase, "done");
  assert.deepEqual(q.view.result, { first_try_correct: 3, total: 5 });
});

test("全部先错后对：0/5，分母还是 5", () => {
  let q = begun();
  for (const id of ORDER) { q = answerSaved(q, WRONG[id]); q = answerSaved(q, RIGHT[id]); }
  q = save(q);
  assert.deepEqual(q.view.result, { first_try_correct: 0, total: 5 });
});

test("step 是纯函数：不改传进去的旧状态", () => {
  let q = begun();
  const s = json(q);
  step(q, { type: "answer", response: RIGHT.q1 });
  assert.deepEqual(q, s);
  const a = act();
  const before = json(a);
  let r = startQuiz(a, ORDER, "first");
  r = save(r);
  r = answerSaved(r, WRONG.q1);
  assert.deepEqual(a, before, "不改传进去的活动");
});

test("order 不是活动全部 item_id 的一个排列：抛错", () => {
  assert.doesNotThrow(() => startQuiz(act(), ["q5", "q4", "q3", "q2", "q1"], "first"), "完整排列不抛错");
  assert.throws(() => startQuiz(act(), ["q1", "q2", "q3", "q4"], "first"), undefined, "少一个");
  assert.throws(() => startQuiz(act(), [...ORDER, "q6"], "first"), undefined, "多一个");
  assert.throws(() => startQuiz(act(), ["q1", "q1", "q2", "q3", "q4"], "first"), undefined, "重复");
  assert.throws(() => startQuiz(act(), ["q1", "q2", "q3", "q4", "q5", "q5"], "first"), undefined, "重复且多");
  assert.throws(() => startQuiz(act(), [], "first"), undefined, "空");
});

test("1b 起数字题、分数题也能开始（细则见 quiz-1b.test.js）", () => {
  const a = act();
  a.body.items[2].answer = { type: "number", value: 3 };
  assert.doesNotThrow(() => startQuiz(a, ORDER, "first"));
  const b = act();
  b.body.items[0].answer = { type: "fraction", numerator: 1, denominator: 4, accept_equivalent: false };
  assert.doesNotThrow(() => startQuiz(b, ORDER, "first"));
});

/** 只留前 n 道题的活动。 */
function actOf(ids) {
  const a = act();
  a.body.items = a.body.items.filter((it) => ids.includes(it.id));
  return a;
}

test("乱序 order 做完整的一遍：逐题按 order 走，最后一题是 order 的最后一个", () => {
  const order = ["q3", "q5", "q1", "q2", "q4"];
  let q = begun(order);
  for (const [k, id] of order.entries()) {
    assert.equal(q.view.item_id, id, `第 ${k + 1} 题应是 ${id}`);
    if (k < order.length - 1) {
      q = answerSaved(q, RIGHT[id]);
      assert.equal(q.phase, "answering");
    }
  }
  q = answerSaved(q, RIGHT.q4);
  assert.equal(q.phase, "finishing", "答完 order 的最后一个才进入 finishing");
});

test("单题活动：1/1，存好这一道就完成", () => {
  let q = save(startQuiz(actOf(["q2"]), ["q2"], "first"));
  q = answerSaved(q, RIGHT.q2);
  assert.equal(q.phase, "finishing");
  q = save(q);
  assert.deepEqual(q.view.result, { first_try_correct: 1, total: 1 });
});

test("三题活动：分母是 3，三道都存好才完成", () => {
  const ids = ["q1", "q3", "q5"];
  let q = save(startQuiz(actOf(ids), ids, "first"));
  q = answerSaved(q, WRONG.q1);
  q = answerSaved(q, RIGHT.q1);
  q = answerSaved(q, RIGHT.q3);
  assert.equal(q.phase, "answering");
  q = answerSaved(q, RIGHT.q5);
  assert.equal(q.phase, "finishing");
  q = save(q);
  assert.deepEqual(q.view.result, { first_try_correct: 2, total: 3 });
});

test("最后一题答错并存好：停在 answering、停在这道题，不产出完成", () => {
  let q = begun();
  for (const id of ORDER.slice(0, 4)) q = answerSaved(q, RIGHT[id]);
  q = answerSaved(q, WRONG.q5);
  assert.equal(q.phase, "answering");
  assert.equal(q.view.item_id, "q5");
  assert.equal(q.pending, null);
});

test("failed 以后、没存好之前再作答：原样返回", () => {
  let q = begun();
  q = step(q, { type: "answer", response: WRONG.q1 });
  q = step(q, { type: "failed", id: q.pending.id });
  const s = json(q);
  assert.deepEqual(step(q, { type: "answer", response: RIGHT.q1 }), s);
});

test("order 长度对、但有不是活动里的 id：抛错", () => {
  assert.throws(() => startQuiz(act(), ["q1", "q2", "q3", "q4", "q9"], "first"));
});

test("反馈文字：答对用 feedback.correct；答错用选项的 feedback，没有就用 feedback.wrong，再没有用默认的话", () => {
  let q = begun(["q1", "q2", "q4", "q3", "q5"]);
  q = answerSaved(q, RIGHT.q1);
  assert.deepEqual(q.view.feedback, { item_id: "q1", correct: true, text: "平均分成 4 份，涂了 1 份，就是 1/4。" });
  q = answerSaved(q, RIGHT.q2);
  assert.equal(q.view.feedback.correct, true);
  assert.equal(typeof q.view.feedback.text, "string");
  assert.ok(q.view.feedback.text.length > 0, "没有 feedback.correct 时用默认的话");
  q = answerSaved(q, WRONG.q4);
  assert.deepEqual(q.view.feedback, { item_id: "q4", correct: false, text: "再数一数，西瓜一共切成了几块？" });
  q = answerSaved(q, RIGHT.q4);
  q = answerSaved(q, WRONG.q3);
  assert.equal(q.view.feedback.correct, false);
  assert.ok(typeof q.view.feedback.text === "string" && q.view.feedback.text.length > 0, "都没有时用默认的话");
});
