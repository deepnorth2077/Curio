// 假存储和测试用的小工具（竖切片 1 规格 6.2、6.3）。Claude 写，实现者不改（受保护路径）。
//
// 它照规格 6.2 的 store 接口模拟 IndexedDB 的事务语义：每个方法要么整个生效，要么什么都不写。
// 注意：「序号对不上就中止」在这里是假存储自己的检查；真的 app/store.js 的事务逻辑靠整合时的浏览器冒烟测试。
// 测试可以在下一次 commit 上安排一种故障：
//   store.nextCommit = "abort"   事务提交前中止：什么都不写，Promise reject
//   store.nextCommit = "close"   事务已提交（三样都写了），然后页面关掉：Promise 永远不结束
//   store.nextCommit = "gate"    写之前停住，等 store.release() 才继续（用来测并发和双击）
import { createLog } from "../../kernel/js/log.js";

export function createFakeStore() {
  const state = { identity: null, nextSeq: null, inbox: [], receipts: new Map() };
  const calls = { loadAll: 0, init: 0, putInbox: 0, commit: 0 };
  let active = 0;
  let maxActive = 0;
  let gate = null;
  let released = false;
  const store = {
    state,
    calls,
    nextCommit: null,
    get maxConcurrentCommits() { return maxActive; },
    /** 有一个 commit 正停在 gate 上。 */
    get gated() { return gate !== null; },
    release() { if (gate) { const g = gate; gate = null; g(); } else released = true; },
    async loadAll() {
      calls.loadAll++;
      await tick();
      return { identity: state.identity ? { ...state.identity } : null, nextSeq: state.nextSeq, inbox: [...state.inbox] };
    },
    async init(identity) {
      calls.init++;
      await tick();
      if (state.identity) throw new Error("假存储：已经有身份，事务中止");
      state.identity = { learner_id: identity.learner_id, device_id: identity.device_id };
      state.nextSeq = 1;
    },
    async putInbox(raw) {
      calls.putInbox++;
      await tick();
      state.inbox.push(raw);
    },
    async commit(raw, receipt) {
      calls.commit++;
      const mode = store.nextCommit;
      store.nextCommit = null;
      active++;
      maxActive = Math.max(maxActive, active);
      try {
        if (mode === "gate" && !released) await new Promise((r) => { gate = r; });
        if (mode === "gate") released = false;
        await tick();
        if (mode === "abort") throw new Error("假存储：事务中止");
        const ev = JSON.parse(raw);
        if (state.nextSeq !== ev.device_seq) throw new Error(`假存储：下一个序号是 ${state.nextSeq}，不是 ${ev.device_seq}，事务中止`);
        state.inbox.push(raw);
        state.receipts.set(ev.event_id, receipt);
        state.nextSeq = ev.device_seq + 1;
        if (mode === "close") { active--; return new Promise(() => {}); }
      } finally {
        if (mode !== "close") active--;
      }
    },
  };
  return store;
}

const tick = () => new Promise((r) => setTimeout(r, 0));

/** 等到条件成立（最多 2 秒），不靠固定的等待时间。 */
export async function until(cond, ms = 2000) {
  const end = Date.now() + ms;
  while (!cond()) {
    if (Date.now() > end) throw new Error("等了 2 秒，条件还没成立");
    await new Promise((r) => setTimeout(r, 1));
  }
}

/** 用存储里的收件表按到达顺序新建一个日志（模拟刷新后的重放）。 */
export function rebuild(store) {
  const log = createLog();
  for (const raw of store.state.inbox) log.ingest(raw);
  return log;
}

/** 合法的 26 位 ULID 主体（首位 0，只用数字），后缀是计数器。 */
const body = (n) => "01JC" + String(n).padStart(22, "0");

/** 确定性的 ID 生成器和时钟。 */
export function fixtures() {
  let n = 0;
  let t = Date.UTC(2026, 10, 9, 2, 0, 0);
  return {
    ids: {
      learner: () => "lrn_" + body(++n),
      device: () => "dev_" + body(++n),
      event: () => "evt_" + body(++n),
      attempt: () => "att_" + body(++n),
    },
    now: () => new Date((t += 1000)).toISOString(),
  };
}

export const CONTENT_V1 = {
  node_id: "math.number.fraction-intro",
  activity_id: "act.quiz.fraction-intro-01",
  activity_kind: "quiz",
  activity_version: 1,
  content_release: "rel_" + "1".repeat(64),
};

/** 组装一条本机事件的原始文字（序号取 committer.nextSeq）。 */
export function raw(fx, identity, committer, { verb, attempt_id, payload, content = CONTENT_V1, actor, device_seq }) {
  return JSON.stringify({
    schema: "event/2",
    event_id: fx.ids.event(),
    learner_id: identity.learner_id,
    device_id: identity.device_id,
    device_seq: device_seq ?? committer.nextSeq,
    occurred_at: fx.now(),
    actor: actor ?? { type: "learner", id: identity.learner_id },
    verb,
    attempt_id,
    content,
    payload,
  });
}

export const receiptOf = (fx, r) => ({ event_id: JSON.parse(r).event_id, received_at: fx.now() });

/** 每种情况结束都查的三件事（规格 6.2 表下）。log 为 null 时只查存储。opts.quarantined：收件表里应有几条隔离的原文。 */
export function checkInvariants(assert, store, log, opts = {}) {
  const fresh = rebuild(store);
  if (log) assert.deepEqual(fresh.raw(), log.raw(), "用存储新建的日志和内存日志的 raw() 应完全相同");
  assert.equal(fresh.quarantined().length, opts.quarantined ?? 0, "收件表里隔离的原文条数");
  assert.equal(store.state.inbox.length, fresh.events().length + fresh.quarantined().length,
    "收件表里每条原文只存一份：条数 = 接收的 + 隔离的（每个 event_id 只出现一次）");
  const ids = fresh.events().map((e) => e.event_id);
  assert.equal(new Set(ids).size, ids.length, "每个 event_id 只出现一次");
  const dev = store.state.identity?.device_id;
  const mine = fresh.events().filter((e) => e.device_id === dev);
  const seqs = mine.map((e) => e.device_seq).sort((a, b) => a - b);
  seqs.forEach((s, i) => assert.equal(s, i + 1, "本设备的 device_seq 从 1 连续"));
  for (const e of mine) assert.ok(store.state.receipts.has(e.event_id), `本机事件 ${e.event_id} 应有收据`);
  assert.equal(store.state.receipts.size, mine.length, "收据只写给接收的本机事件");
  if (store.state.nextSeq !== null) assert.equal(store.state.nextSeq, seqs.length + 1, "存储里的下一个序号 = 本设备事件数 + 1");
}
