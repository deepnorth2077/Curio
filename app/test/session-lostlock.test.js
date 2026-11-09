// 实现者补的测试：openSession 进行中失去写锁（规格 6.3「失去写锁」：立刻只读，不再写）。
// 外壳用 guardDeps 给 openSession 的 ids、now 包一层，失锁以后再要 ID 或时间就抛 LockLostError。
import { test } from "node:test";
import assert from "node:assert/strict";
import { openSession, guardDeps, LockLostError } from "../session.js";
import { createFakeStore, fixtures, raw, receiptOf, checkInvariants, until } from "./fake-store.js";

const snap = (store) => JSON.stringify({ id: store.state.identity, i: store.state.inbox, r: [...store.state.receipts], n: store.state.nextSeq });

/** 存储里放好 n 次没结束的尝试。 */
async function withUnfinished(n) {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  for (let k = 0; k < n; k++) {
    const r = raw(fx, s.identity, s.committer, { verb: "attempt.started", attempt_id: fx.ids.attempt(), payload: { mode: "first" } });
    await s.committer.submit(r, receiptOf(fx, r));
  }
  return { store, fx };
}

test("openSession 进行中失锁（loadAll 期间）：抛 LockLostError，存储里不多出事件", async () => {
  const { store, fx } = await withUnfinished(1);
  const before = snap(store);
  let lost = false;
  const p = openSession(store, guardDeps(fx, () => lost));
  lost = true; // loadAll 还没返回时锁被收回
  await assert.rejects(p, LockLostError);
  assert.equal(snap(store), before, "没有补写 abandoned，收件表、收据、nextSeq 都没变");
  assert.equal(store.calls.commit, 1, "只有准备数据时那一次 commit");
  checkInvariants(assert, store, null);
});

test("空存储上 openSession 进行中失锁：不建身份", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  let lost = false;
  const p = openSession(store, guardDeps(fx, () => lost));
  lost = true;
  await assert.rejects(p, LockLostError);
  assert.equal(store.state.identity, null);
  assert.equal(store.calls.init, 0);
  assert.equal(store.state.inbox.length, 0);
});

test("补写到一半失锁：正在进行的那一个事务照常结束，之后不再补写", async () => {
  const { store, fx } = await withUnfinished(2);
  const n0 = store.state.inbox.length;
  let lost = false;
  store.nextCommit = "gate"; // 第一条补写停在事务里
  const p = openSession(store, guardDeps(fx, () => lost));
  await until(() => store.gated);
  lost = true;
  store.release();
  await assert.rejects(p, LockLostError);
  assert.equal(store.state.inbox.length, n0 + 1, "只多出已经交给存储的那一条，第二条没有补");
  checkInvariants(assert, store, null);
});

test("没失锁时包一层不改变结果", async () => {
  const { store, fx } = await withUnfinished(2);
  const s = await openSession(store, guardDeps(fx, () => false));
  assert.equal(s.abandoned.length, 2);
  checkInvariants(assert, store, s.log);
});
