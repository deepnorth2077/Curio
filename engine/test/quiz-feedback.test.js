// 孩子看到的反馈由实际命中的错答决定。误区是独立的、可选的事件字段。
import { test } from "node:test";
import assert from "node:assert/strict";
import { startQuiz, step } from "../js/quiz.js";

function answerOnce(answer, response) {
  const item = { id: "q", stem: "试一试", answer, feedback: { wrong: "再数一数。", correct: "数量对上了。" } };
  let q = startQuiz({ kind: "quiz", body: { items: [item] } }, ["q"], "first");
  q = step(q, { type: "saved", id: q.pending.id });
  q = step(q, { type: "answer", response });
  assert.equal(q.pending.verb, "item.answered");
  assert.equal(q.view.feedback, null);
  const payload = q.pending.payload;
  q = step(q, { type: "saved", id: q.pending.id });
  return { text: q.view.feedback.text, payload };
}

test("染色体条数和对数各用自己那道题的错答反馈，未命中时用通用反馈", () => {
  for (const [value, other, feedback] of [
    [46, 23, "你想到的是对数；题目问的是一条一条数，共有多少条。"],
    [23, 46, "你数的是一条一条的总数；两两配好以后，要数有多少对。"],
  ]) {
    const answer = { type: "number", value, tolerance: 0, common_wrong: [{ value: other, feedback }] };
    const response = String(other);
    assert.deepEqual(answerOnce(answer, response), {
      text: feedback, payload: { item_id: "q", response, correct: false, try: 1, hints_used: 0 },
    });
    assert.equal(answerOnce(answer, "24").text, "再数一数。");
    assert.equal(answerOnce(answer, String(value)).text, "数量对上了。");
  }
});

test("两个错答标同一误区时取实际命中的反馈，容差边界与判分一致", () => {
  const answer = { type: "number", value: 10, tolerance: 0.1, common_wrong: [
    { value: 4, misconception: "same", feedback: "再数左边。" },
    { value: 7, misconception: "same", feedback: "再数右边。" },
    { value: 10.1, feedback: "先看对错。" },
  ] };
  const hit = answerOnce(answer, "７．１０００００");
  assert.equal(hit.text, "再数右边。");
  assert.equal(hit.payload.misconception, "same");
  assert.equal(answerOnce(answer, "7.100001").text, "再数一数。");
  assert.equal(answerOnce(answer, "10.1").text, "数量对上了。");
});

test("分数错答沿用等值与指定写法的判定，没有误区也能解释", () => {
  const answer = { type: "fraction", numerator: 3, denominator: 4, accept_equivalent: true,
    common_wrong: [{ numerator: 1, denominator: 2, feedback: "还有一块要算进去。" }] };
  assert.equal(answerOnce(answer, "４分之２").text, "还有一块要算进去。");
  assert.equal(answerOnce({ ...answer, accept_equivalent: false }, "2/4").text, "再数一数。");
  assert.equal(answerOnce(answer, "1/0").text, "再数一数。");
});
