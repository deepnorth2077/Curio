// 提交一条事件的验收测试（竖切片 1 规格 6.2）。Claude 派发前写好，实现者不改（受保护路径）。
//
// 这份测试固定了规格 6.2、6.3 里没有逐字写出的两个接口（实现者照这个来）：
//   createCommitter(store, log, {nextSeq})
//     nextSeq 是外壳 loadAll 读到的值；之后每次 accepted 加 1。
//   openSession(store, {ids, now})   在 app/session.js
//     外壳拿到写锁以后调用：loadAll → 身份为空时 init（ids.learner()、ids.device()）→ 收件表按顺序 ingest
//     → 建 committer → 给本设备上没结束、也没被判为不一致的尝试各补一条 attempt.abandoned（走 committer）。
//     全部补写存好以后才 resolve，返回 {identity, log, committer, abandoned}，abandoned 是补写的 event_id 列表。
//     ids.event() 生成 event_id，now() 返回 occurred_at 用的 UTC 时间字符串；收据是 {event_id, received_at: now()}。
//     它不读发布包：补写需要的东西全从这次尝试的事件里复制。
import { test } from "node:test";
import assert from "node:assert/strict";
import { createLog } from "../../kernel/js/log.js";
import { projectMastery } from "../../kernel/js/mastery.js";
import { createCommitter } from "../commit.js";
import { openSession } from "../session.js";
import { createFakeStore, rebuild, fixtures, raw, receiptOf, checkInvariants, CONTENT_V1 } from "./fake-store.js";

const NODE = CONTENT_V1.node_id;
const ITEMS = ["q1", "q2", "q3", "q4", "q5"];

async function setup() {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  return { store, fx, s };
}

/** 组装并提交一条，返回 [原始文字, 结果]。 */
async function put(fx, s, spec) {
  const r = raw(fx, s.identity, s.committer, spec);
  return [r, await s.committer.submit(r, receiptOf(fx, r))];
}
const started = (att) => ({ verb: "attempt.started", attempt_id: att, payload: { mode: "first" } });
const answered = (att, item, correct, tr = 1) => ({ verb: "item.answered", attempt_id: att, payload: { item_id: item, response: correct ? "a" : "b", correct, try: tr, hints_used: 0 } });
const completed = (att) => ({ verb: "attempt.completed", attempt_id: att, payload: { duration_ms: 60000 } });

const storeSnap = (store) => JSON.stringify({ i: store.state.inbox, r: [...store.state.receipts], n: store.state.nextSeq });

test("空存储：openSession 生成身份，nextSeq 是 1，什么都不补", async () => {
  const { store, s } = await setup();
  assert.match(s.identity.learner_id, /^lrn_/);
  assert.match(s.identity.device_id, /^dev_/);
  assert.deepEqual(store.state.identity, s.identity);
  assert.equal(s.committer.nextSeq, 1);
  assert.deepEqual(s.abandoned, []);
  assert.equal(s.committer.frozen, false);
  checkInvariants(assert, store, s.log);
});

test("正常提交：accepted，nextSeq 加 1，日志和存储一致", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  const [, r] = await put(fx, s, started(att));
  assert.equal(r, "accepted");
  assert.equal(s.committer.nextSeq, 2);
  assert.equal(s.log.events().length, 1);
  checkInvariants(assert, store, s.log);
});

test("作答那条事务提交前中止：三样都没变，日志没变；同一条原始文字重试成功", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  await put(fx, s, started(att));
  const r = raw(fx, s.identity, s.committer, answered(att, "q1", true));
  const rc = receiptOf(fx, r);
  const before = storeSnap(store);
  const logBefore = JSON.stringify(s.log.raw());
  store.nextCommit = "abort";
  await assert.rejects(s.committer.submit(r, rc));
  assert.equal(storeSnap(store), before, "收件表、收据、nextSeq 都没变");
  assert.equal(JSON.stringify(s.log.raw()), logBefore, "日志没变");
  assert.equal(s.committer.nextSeq, 2, "nextSeq 没变");
  assert.equal(s.committer.frozen, false);
  assert.equal(await s.committer.submit(r, rc), "accepted", "同一条原始文字重试成功");
  checkInvariants(assert, store, s.log);
});

test("完成那条事务提交前中止：同上", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  await put(fx, s, started(att));
  for (const it of ITEMS) await put(fx, s, answered(att, it, true));
  const r = raw(fx, s.identity, s.committer, completed(att));
  const rc = receiptOf(fx, r);
  const before = storeSnap(store);
  store.nextCommit = "abort";
  await assert.rejects(s.committer.submit(r, rc));
  assert.equal(storeSnap(store), before);
  assert.equal(projectMastery(s.log.events()).nodes[NODE].state, "untouched", "完成没存上，星星不亮");
  assert.equal(await s.committer.submit(r, rc), "accepted");
  assert.equal(projectMastery(s.log.events()).nodes[NODE].state, "lit");
  checkInvariants(assert, store, s.log);
});

test("事务提交以后、ingest 之前页面关掉：重放能读到这条；启动时补一条 abandoned", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  await put(fx, s, started(att));
  const r = raw(fx, s.identity, s.committer, answered(att, "q1", true));
  store.nextCommit = "close";
  s.committer.submit(r, receiptOf(fx, r)); // 永远不结束：页面关掉了
  await new Promise((res) => setTimeout(res, 20));
  assert.ok(store.state.inbox.includes(r), "事务已提交");
  const s2 = await openSession(store, fx);
  assert.ok(s2.log.raw().includes(r), "重放读到了这条作答");
  assert.equal(s2.abandoned.length, 1, "没有结束事件，补一条 abandoned");
  const ab = s2.log.events().find((e) => e.event_id === s2.abandoned[0]);
  assert.equal(ab.verb, "attempt.abandoned");
  assert.equal(ab.attempt_id, att);
  assert.equal(ab.device_seq, 3);
  assert.deepEqual(projectMastery(s2.log.events()).conflicts, []);
  checkInvariants(assert, store, s2.log);
});

test("完成那条提交以后、saved 之前页面关掉：重放后尝试已完成，不补 abandoned，掌握度对", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  await put(fx, s, started(att));
  await put(fx, s, answered(att, "q1", false));
  await put(fx, s, answered(att, "q1", true, 2));
  for (const it of ITEMS.slice(1)) await put(fx, s, answered(att, it, true));
  const r = raw(fx, s.identity, s.committer, completed(att));
  store.nextCommit = "close";
  s.committer.submit(r, receiptOf(fx, r));
  await new Promise((res) => setTimeout(res, 20));
  const s2 = await openSession(store, fx);
  assert.deepEqual(s2.abandoned, []);
  assert.deepEqual(projectMastery(s2.log.events()).nodes[NODE], { state: "lit", best: { correct: 4, answered: 5 } });
  assert.equal(s2.committer.nextSeq, 9);
  checkInvariants(assert, store, s2.log);
});

test("双击「再试」：同一条原始文字正在处理时又提交，只调用一次 store.commit，返回同一个 Promise", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  await put(fx, s, started(att));
  const r = raw(fx, s.identity, s.committer, answered(att, "q1", true));
  const rc = receiptOf(fx, r);
  const callsBefore = store.calls.commit;
  store.nextCommit = "gate";
  const p1 = s.committer.submit(r, rc);
  await new Promise((res) => setTimeout(res, 5));
  const p2 = s.committer.submit(r, rc);
  assert.strictEqual(p2, p1, "返回同一个 Promise");
  store.release();
  assert.equal(await p1, "accepted");
  assert.equal(store.calls.commit - callsBefore, 1, "只调用一次 store.commit");
  checkInvariants(assert, store, s.log);
});

test("已经存好的原文再提交：返回 duplicate，不碰存储", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  const [r] = await put(fx, s, started(att));
  const n = store.calls.commit;
  assert.equal(await s.committer.submit(r, receiptOf(fx, r)), "duplicate");
  assert.equal(store.calls.commit, n);
  assert.equal(s.committer.nextSeq, 2);
  checkInvariants(assert, store, s.log);
});

test("串行：两条一起提交，第二条等第一条结束才开始，存储里没有并发事务", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  const a = raw(fx, s.identity, s.committer, { ...started(att), device_seq: 1 });
  const b = raw(fx, s.identity, s.committer, { ...answered(att, "q1", true), device_seq: 2 });
  store.nextCommit = "gate";
  const pa = s.committer.submit(a, receiptOf(fx, a));
  const pb = s.committer.submit(b, receiptOf(fx, b));
  await new Promise((res) => setTimeout(res, 10));
  assert.equal(store.calls.commit, 1, "第一条还没结束，第二条还没开始");
  store.release();
  assert.deepEqual(await Promise.all([pa, pb]), ["accepted", "accepted"]);
  assert.equal(store.maxConcurrentCommits, 1);
  assert.deepEqual(s.log.raw(), [a, b]);
  checkInvariants(assert, store, s.log);
});

test("启动补写还没完成就开始挑战：openSession 等补写存好才 resolve，挑战的 started 排在后面，序号连续", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  const old1 = fx.ids.attempt();
  const old2 = fx.ids.attempt();
  await put(fx, s, started(old1));
  await put(fx, s, started(old2));
  await put(fx, s, answered(old2, "q1", true));
  store.nextCommit = "gate"; // 第一条补写卡住
  let resolved = false;
  const p = openSession(store, fx).then((x) => { resolved = true; return x; });
  await new Promise((res) => setTimeout(res, 20));
  assert.equal(resolved, false, "补写没存好之前不 resolve，外壳还不能开始挑战");
  store.release();
  const s2 = await p;
  assert.equal(s2.abandoned.length, 2);
  assert.equal(s2.committer.nextSeq, 6);
  const att = fx.ids.attempt();
  const [r] = await put(fx, s2, started(att));
  assert.equal(JSON.parse(r).device_seq, 6);
  assert.equal(s2.log.raw().at(-1), r);
  checkInvariants(assert, store, s2.log);
});

test("隔离的原文：存进收件表，抛错，不推进 nextSeq；重放后隔离区里有它", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  await put(fx, s, started(att));
  const bad = raw(fx, s.identity, s.committer, { verb: "item.answered", attempt_id: att, payload: { item_id: "q1", response: "a", correct: 1, try: 1, hints_used: 0 } });
  const commits = store.calls.commit;
  await assert.rejects(s.committer.submit(bad, receiptOf(fx, bad)));
  assert.equal(store.calls.commit, commits, "不合格的不走 commit");
  assert.equal(store.calls.putInbox, 1);
  assert.equal(store.state.inbox.at(-1), bad);
  assert.equal(s.committer.nextSeq, 2);
  assert.equal(store.state.receipts.has(JSON.parse(bad).event_id), false, "隔离的原文没有收据");
  const fresh = rebuild(store);
  assert.deepEqual(fresh.quarantined().map((q) => [q.raw, q.reason]), [[bad, "invalid"]]);
  const s2 = await openSession(store, fx);
  assert.deepEqual(s2.log.quarantined().map((q) => [q.raw, q.reason]), [[bad, "invalid"]]);
  checkInvariants(assert, store, s2.log);
});

test("commit 时存储里的 nextSeq 和 device_seq 对不上：事务中止，什么都没写，抛错", async () => {
  const { store, fx, s } = await setup();
  const att = fx.ids.attempt();
  await put(fx, s, started(att));
  store.state.nextSeq = 5; // 别人动过存储
  const r = raw(fx, s.identity, s.committer, answered(att, "q1", true));
  const before = storeSnap(store);
  await assert.rejects(s.committer.submit(r, receiptOf(fx, r)));
  assert.equal(storeSnap(store), before, "什么都没写");
  assert.equal(s.log.raw().length, 1, "日志没变");
});

test("freeze() 以后 submit 一律抛错，不碰存储", async () => {
  const { store, fx, s } = await setup();
  s.committer.freeze();
  assert.equal(s.committer.frozen, true);
  const r = raw(fx, s.identity, s.committer, started(fx.ids.attempt()));
  const n = store.calls.commit;
  await assert.rejects(s.committer.submit(r, receiptOf(fx, r)));
  assert.equal(store.calls.commit, n);
  assert.equal(store.calls.putInbox, 0);
});

test("createCommitter 可以单独用：nextSeq 取传进来的值", async () => {
  const store = createFakeStore();
  await store.init({ learner_id: "lrn_" + "0".repeat(26), device_id: "dev_" + "0".repeat(26) });
  const c = createCommitter(store, createLog(), { nextSeq: 1 });
  assert.equal(c.nextSeq, 1);
  assert.equal(c.frozen, false);
});
