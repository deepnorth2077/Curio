// CURIO-013 第 1 个 PR「认识」：answer.revealed、attempt.started 的 grader、合法性第 6 条（docs/specs/evidence.md）。
// 期望值按规格手写。跑法：node --test kernel/test/*.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createLog } from "../js/log.js";
import { attemptRule, projectMastery } from "../js/mastery.js";
import { checkEnvelope, checkVerb, SLICE_VERBS } from "../js/validate.js";

const LRN = "lrn_01H8ZK6P3M9Q2W5E8R7T4VY0XC";
const DEV = "dev_03J7Q2W5E8R7T4V6Y0XCA2BDFH";
const ATT = "att_0000000000000000000000001W";
const CONTENT = {
  node_id: "math.number.fraction-intro",
  activity_id: "act.quiz.fraction-intro-01",
  activity_kind: "quiz",
  activity_version: 1,
  content_release: "rel_" + "5e1f0c9a8b7d6e4f".repeat(4),
};
const evtId = (n) => "evt_" + String(n).padStart(26, "0");

/** 一条事件；seq 同时决定 event_id 和 device_seq。 */
function ev(seq, verb, payload, over = {}) {
  return {
    schema: "event/2", event_id: evtId(seq), learner_id: LRN, device_id: DEV, device_seq: seq,
    occurred_at: "2026-11-12T08:00:00.000Z", actor: { type: "learner", id: LRN },
    verb, attempt_id: ATT, content: CONTENT, payload, ...over,
  };
}
const started = (seq, extra = {}) => ev(seq, "attempt.started", { mode: "first", ...extra });
const answered = (seq, item_id, correct, t = 1) => ev(seq, "item.answered", { item_id, response: "a", correct, try: t, hints_used: 0 });
const revealed = (seq, item_id) => ev(seq, "answer.revealed", { item_id });
const completed = (seq) => ev(seq, "attempt.completed", { duration_ms: 1000 });

const verdict = (e) => checkEnvelope(e) || checkVerb(e);
const ingestAll = (events) => {
  const log = createLog();
  for (const e of events) log.ingest(JSON.stringify(e));
  return log;
};

// ---------------------------------------------------------------- 校验：answer.revealed

test("SLICE_VERBS 认 answer.revealed，不认 poe.predicted", () => {
  assert.ok(SLICE_VERBS.includes("answer.revealed"));
  assert.ok(!SLICE_VERBS.includes("poe.predicted"));
});

test("answer.revealed：合法的通过", () => {
  assert.equal(verdict(revealed(3, "q1")), null);
  assert.equal(createLog().check(JSON.stringify(revealed(3, "q1"))).result, "accepted");
});

test("answer.revealed：缺 item_id、多字段、item_id 不是字符串都拒收", () => {
  assert.notEqual(verdict(ev(3, "answer.revealed", {})), null);
  assert.notEqual(verdict(ev(3, "answer.revealed", { item_id: "q1", level: 1 })), null);
  assert.notEqual(verdict(ev(3, "answer.revealed", { item_id: 1 })), null);
});

test("answer.revealed：actor 只能是 learner", () => {
  assert.notEqual(verdict({ ...revealed(3, "q1"), actor: { type: "system", id: "sys:test" } }), null);
  assert.notEqual(verdict({ ...revealed(3, "q1"), actor: { type: "caregiver", id: "cg_02K9M4P7Q3R5T8V6WY0XCA1BDE" } }), null);
});

test("answer.revealed：必须带 attempt_id 和 content", () => {
  const a = revealed(3, "q1"); delete a.attempt_id;
  const c = revealed(3, "q1"); delete c.content;
  assert.notEqual(verdict(a), null);
  assert.notEqual(verdict(c), null);
});

// ---------------------------------------------------------------- 校验：grader

test("attempt.started：带和不带 grader 都通过", () => {
  assert.equal(verdict(started(1)), null);
  assert.equal(verdict(started(1, { grader: "grade/1" })), null);
  assert.equal(verdict(started(1, { grader: "grade/12" })), null);
});

test("attempt.started：grader 格式不对、太长、不是字符串都拒收", () => {
  for (const g of ["", "grade", "Grade/1", "grade/v1", "grade/1/2", "1grade/1", "grade/1 ", "grade/1\n", "grade/0", "grade/01", "a".repeat(31) + "/1", 1, null]) {
    assert.notEqual(verdict(started(1, { grader: g })), null, `grader=${JSON.stringify(g)}`);
  }
  // 恰好 32 个字符可以
  assert.equal(verdict(started(1, { grader: "a".repeat(30) + "/1" })), null);
});

test("attempt.started：其他多余的键仍然拒收", () => {
  assert.notEqual(verdict(started(1, { grader: "grade/1", extra: 1 })), null);
});

// ---------------------------------------------------------------- 合法性第 6 条

test("第 6 条：答过再看答案，合法", () => {
  assert.equal(attemptRule([started(1), answered(2, "q1", false), revealed(3, "q1"), completed(4)]), 0);
});

test("第 6 条：之前没有同题作答 → 6", () => {
  assert.equal(attemptRule([started(1), revealed(2, "q1"), answered(3, "q1", false), completed(4)]), 6);
  assert.equal(attemptRule([started(1), answered(2, "q2", false), revealed(3, "q1"), completed(4)]), 6);
});

test("第 6 条：同一题两条 → 6", () => {
  assert.equal(attemptRule([started(1), answered(2, "q1", false), revealed(3, "q1"), revealed(4, "q1"), completed(5)]), 6);
});

test("第 6 条：看答案之后又答同一题 → 6；答别的题不算", () => {
  assert.equal(attemptRule([started(1), answered(2, "q1", false), revealed(3, "q1"), answered(4, "q1", true, 2), completed(5)]), 6);
  assert.equal(attemptRule([started(1), answered(2, "q1", false), revealed(3, "q1"), answered(4, "q2", true), completed(5)]), 0);
});

test("第 6 条按 device_seq 判断，和到达顺序无关", () => {
  const evs = [completed(4), revealed(3, "q1"), started(1), answered(2, "q1", false)];
  assert.deepEqual(projectMastery(evs).conflicts, []);
  const bad = [completed(4), answered(3, "q1", false), started(1), revealed(2, "q1")];
  assert.deepEqual(projectMastery(bad).conflicts, [{ attempt_id: ATT, rule: 6 }]);
});

test("同时违反更小编号的规则时，记编号最小的", () => {
  // 第 5 条（try 跳号）和第 6 条（之前没作答）同时违反 → 5
  assert.equal(attemptRule([started(1), revealed(2, "q1"), answered(3, "q2", false, 2), completed(4)]), 5);
});

test("经过日志摄入：第 6 条不一致的尝试列进 conflicts，不计入掌握度", () => {
  const log = ingestAll([started(1), revealed(2, "q1"), answered(3, "q1", true), completed(4)]);
  assert.equal(log.events().length, 4);
  const m = projectMastery(log.events());
  assert.deepEqual(m.conflicts, [{ attempt_id: ATT, rule: 6 }]);
  assert.deepEqual(m.nodes[CONTENT.node_id], { state: "untouched", best: null });
});

// ---------------------------------------------------------------- 掌握度不变

test("看答案不改变掌握度：和不看答案时相同", () => {
  const plain = [started(1, { grader: "grade/1" }), answered(2, "q1", false), answered(3, "q2", true), answered(4, "q3", true), completed(5)];
  const withReveal = [started(1, { grader: "grade/1" }), answered(2, "q1", false), revealed(3, "q1"), answered(4, "q2", true), answered(5, "q3", true), completed(6)];
  const a = projectMastery(ingestAll(plain).events());
  const b = projectMastery(ingestAll(withReveal).events());
  assert.equal(ingestAll(withReveal).events().length, 6);
  assert.deepEqual(b, a);
  assert.deepEqual(a.nodes[CONTENT.node_id], { state: "explored", best: { correct: 2, answered: 3 } });
});

test("不带 grader 的旧 attempt.started 照常读，掌握度和带 grader 时相同", () => {
  const evs = (g) => [started(1, g), answered(2, "q1", true), answered(3, "q2", true), completed(4)];
  const a = projectMastery(ingestAll(evs({})).events());
  const b = projectMastery(ingestAll(evs({ grader: "grade/1" })).events());
  assert.deepEqual(a, b);
  assert.equal(a.nodes[CONTENT.node_id].state, "lit");
});
