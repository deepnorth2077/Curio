// 启动恢复的验收测试（竖切片 1 规格 6.3「正在恢复」）。Claude 派发前写好，实现者不改（受保护路径）。
// openSession 的接口见 commit.test.js 开头。它不读发布包，所以「用发布 R2 启动，R2 里活动是 v2 或者
// 干脆没有这个活动」在这里就是：补写只能从 R1 时写下的事件里复制 content。
import { test } from "node:test";
import assert from "node:assert/strict";
import { projectMastery } from "../../kernel/js/mastery.js";
import { openSession } from "../session.js";
import { createFakeStore, fixtures, raw, receiptOf, checkInvariants, CONTENT_V1 } from "./fake-store.js";

const NODE = CONTENT_V1.node_id;

async function put(fx, s, spec) {
  const r = raw(fx, s.identity, s.committer, spec);
  await s.committer.submit(r, receiptOf(fx, r));
  return JSON.parse(r);
}
const started = (att) => ({ verb: "attempt.started", attempt_id: att, payload: { mode: "first" } });
const answered = (att, item, correct, tr = 1) => ({ verb: "item.answered", attempt_id: att, payload: { item_id: item, response: correct ? "a" : "b", correct, try: tr, hints_used: 0 } });

test("R1 的 v1 做到一半关掉，换发布启动：补一条 abandoned，复制 v1 的 content，合法放弃；再启动不重复补", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  const s1 = await openSession(store, fx);
  const att = fx.ids.attempt();
  const first = await put(fx, s1, started(att));
  await put(fx, s1, answered(att, "q1", false));
  await put(fx, s1, answered(att, "q1", true, 2));
  // 关掉页面；发布更新到 R2（活动 v2，或者没有这个活动）。openSession 不看发布包。
  const s2 = await openSession(store, fx);
  assert.equal(s2.abandoned.length, 1);
  assert.equal(store.calls.init, 1, "已经有身份，不再 init");
  assert.deepEqual(s2.identity, s1.identity);
  const ab = s2.log.events().at(-1);
  assert.equal(ab.event_id, s2.abandoned[0]);
  assert.equal(ab.verb, "attempt.abandoned");
  assert.deepEqual(ab.payload, { reason: "left" });
  assert.deepEqual(ab.actor, { type: "system", id: "sys:shell" });
  assert.deepEqual(ab.content, first.content, "复制的是 v1 时的 content，包括 content_release 和 activity_version");
  assert.deepEqual(ab.content, CONTENT_V1);
  assert.equal(ab.learner_id, first.learner_id);
  assert.equal(ab.device_id, first.device_id);
  assert.equal(ab.attempt_id, att);
  assert.equal(ab.device_seq, 4);
  assert.equal(ab.schema, "event/2");
  assert.match(ab.event_id, /^evt_[0-7][0-9A-HJKMNP-TV-Z]{25}$/);
  assert.match(ab.occurred_at, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/);
  const m = projectMastery(s2.log.events());
  assert.deepEqual(m.conflicts, [], "合法放弃，没有规则 3 的冲突");
  assert.deepEqual(m.nodes[NODE], { state: "untouched", best: null }, "放弃的不算完成");
  checkInvariants(assert, store, s2.log);

  const s3 = await openSession(store, fx);
  assert.deepEqual(s3.abandoned, [], "已经有结束事件，不重复补");
  assert.equal(store.state.inbox.length, 4);
  assert.equal(s3.committer.nextSeq, 5);
  checkInvariants(assert, store, s3.log);
});

test("已完成的、已放弃的尝试不补", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  const a = fx.ids.attempt();
  await put(fx, s, started(a));
  await put(fx, s, answered(a, "q1", true));
  await put(fx, s, { verb: "attempt.completed", attempt_id: a, payload: { duration_ms: 1000 } });
  const b = fx.ids.attempt();
  await put(fx, s, started(b));
  await put(fx, s, { verb: "attempt.abandoned", attempt_id: b, payload: { reason: "left" } });
  const s2 = await openSession(store, fx);
  assert.deepEqual(s2.abandoned, []);
  assert.equal(projectMastery(s2.log.events()).nodes[NODE].state, "lit", "1/1 完成会点亮");
  checkInvariants(assert, store, s2.log);
});

test("被判为不一致的尝试不补", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  const a = fx.ids.attempt();
  await put(fx, s, started(a));
  await put(fx, s, answered(a, "q1", true, 2)); // 第一条就是 try=2：违反规则 5
  const s2 = await openSession(store, fx);
  assert.deepEqual(s2.abandoned, []);
  assert.deepEqual(projectMastery(s2.log.events()).conflicts, [{ attempt_id: a, rule: 5 }]);
  checkInvariants(assert, store, s2.log);
});

test("别的设备上没结束的尝试不补", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  const other = { learner_id: s.identity.learner_id, device_id: fx.ids.device() };
  const a = fx.ids.attempt();
  const r = raw(fx, other, { nextSeq: 1 }, started(a));
  await store.putInbox(r); // 以后导入或同步来的
  const s2 = await openSession(store, fx);
  assert.deepEqual(s2.abandoned, []);
  assert.ok(s2.log.raw().includes(r));
  assert.equal(s2.committer.nextSeq, 1);
  checkInvariants(assert, store, s2.log);
});

test("两次没结束的尝试：各补一条，序号连续，各自复制自己的 content", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  const a = fx.ids.attempt();
  const b = fx.ids.attempt();
  const contentB = { ...CONTENT_V1, activity_version: 2, content_release: "rel_" + "2".repeat(64) };
  await put(fx, s, started(a));
  await put(fx, s, { ...started(b), content: contentB });
  await put(fx, s, { ...answered(b, "q1", true), content: contentB });
  const s2 = await openSession(store, fx);
  assert.equal(s2.abandoned.length, 2);
  const abs = s2.log.events().filter((e) => e.verb === "attempt.abandoned");
  assert.deepEqual(abs.map((e) => e.device_seq).sort(), [4, 5]);
  const byAtt = Object.fromEntries(abs.map((e) => [e.attempt_id, e.content]));
  assert.deepEqual(byAtt[a], CONTENT_V1);
  assert.deepEqual(byAtt[b], contentB);
  assert.deepEqual(projectMastery(s2.log.events()).conflicts, []);
  checkInvariants(assert, store, s2.log);
});
