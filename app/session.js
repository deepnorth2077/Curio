// 拿到写锁以后的「正在恢复」（竖切片 1 规格 6.3）：读存储 → 没有身份时建身份 → 重放收件表 → 建 committer →
// 给本设备上没结束、也没被判为不一致的尝试各补一条 attempt.abandoned。不碰 DOM，不读发布包。
import { createLog } from "../kernel/js/log.js";
import { projectMastery, groupAttempts } from "../kernel/js/mastery.js";
import { createCommitter } from "./commit.js";

/**
 * @typedef {{learner_id: string, device_id: string}} Identity
 * @typedef {{learner: () => string, device: () => string, event: () => string, attempt?: () => string}} Ids
 */

/**
 * 本机事件的摄入收据 ingest-receipt/1（事件规格 5.3、schemas/ingest-receipt.schema.json）：source 是 local，不带 batch_id、clock_skew_ms。
 * @param {string} event_id
 * @param {string} recorded_at 写入时的本机 UTC 时间
 */
export const localReceipt = (event_id, recorded_at) => ({ event_id, recorded_at, source: "local" });

/** 外壳已经失去写锁时，传给 openSession 的 ids、now 抛这个错。 */
export class LockLostError extends Error {
  constructor() { super("已经失去写锁"); this.name = "LockLostError"; }
}

/**
 * 给 openSession 的依赖包一层：isLost() 为真以后，生成 ID、取时间一律抛 LockLostError。
 * openSession 每写一条（建身份、补写 abandoned）之前都要先生成 ID、取时间，所以失锁以后它不会再发起任何写入
 * （已经交给存储、正在进行的那一个事务除外）。
 * @param {{ids: Ids, now: () => string}} deps
 * @param {() => boolean} isLost
 * @returns {{ids: Ids, now: () => string}}
 */
export function guardDeps({ ids, now }, isLost) {
  const g = (fn) => (...a) => { if (isLost()) throw new LockLostError(); return fn(...a); };
  /** @type {any} */
  const gi = {};
  for (const [k, fn] of Object.entries(ids)) gi[k] = g(fn);
  return { ids: gi, now: g(now) };
}

/**
 * 组装一条本机事件的原始文字。只调用一次 JSON.stringify，重试时用同一条文字。
 * @param {{event_id: string, identity: Identity, device_seq: number, occurred_at: string, actor: {type: string, id: string},
 *          verb: string, attempt_id: string, content: object, payload: object}} f
 * @returns {string}
 */
export function assemble(f) {
  return JSON.stringify({
    schema: "event/2",
    event_id: f.event_id,
    learner_id: f.identity.learner_id,
    device_id: f.identity.device_id,
    device_seq: f.device_seq,
    occurred_at: f.occurred_at,
    actor: f.actor,
    verb: f.verb,
    attempt_id: f.attempt_id,
    content: f.content,
    payload: f.payload,
  });
}

/**
 * 本设备上没有结束事件、也没被判为不一致的尝试，按第一条事件的 device_seq 排好。
 * @param {any[]} events
 * @param {string} device_id
 * @returns {any[][]} 每次尝试的事件（已按 device_seq 排序）
 */
export function unfinishedAttempts(events, device_id) {
  const bad = new Set(projectMastery(events).conflicts.map((c) => c.attempt_id));
  const out = [];
  for (const [att, evs] of groupAttempts(events)) {
    if (bad.has(att)) continue;
    if (evs[0].device_id !== device_id) continue;
    if (evs.some((e) => e.verb === "attempt.completed" || e.verb === "attempt.abandoned")) continue;
    out.push(evs);
  }
  out.sort((a, b) => a[0].device_seq - b[0].device_seq);
  return out;
}

/**
 * 外壳拿到写锁以后调用。全部补写存好以后才 resolve。
 * @param {import("./commit.js").Store} store
 * @param {{ids: Ids, now: () => string}} deps
 * @returns {Promise<{identity: Identity, log: ReturnType<typeof createLog>, committer: ReturnType<typeof createCommitter>, abandoned: string[]}>}
 */
export async function openSession(store, { ids, now }) {
  const data = await store.loadAll();
  let identity = data.identity;
  let nextSeq = data.nextSeq;
  if (!identity) {
    identity = { learner_id: ids.learner(), device_id: ids.device() };
    await store.init(identity);
    nextSeq = 1;
  }
  if (typeof nextSeq !== "number") throw new Error("存储里没有下一个序号");
  const log = createLog();
  for (const raw of data.inbox) log.ingest(raw);
  const committer = createCommitter(store, log, { nextSeq });
  /** @type {string[]} */
  const abandoned = [];
  for (const evs of unfinishedAttempts(log.events(), identity.device_id)) {
    const f = evs[0];
    const event_id = ids.event();
    // 补写的事件从这次尝试的事件里复制 learner_id、device_id、attempt_id 和完整的 content（规格 6.3 第 3 步）
    const raw = assemble({
      event_id,
      identity: { learner_id: f.learner_id, device_id: f.device_id },
      device_seq: committer.nextSeq,
      occurred_at: now(),
      actor: { type: "system", id: "sys:shell" },
      verb: "attempt.abandoned",
      attempt_id: f.attempt_id,
      content: f.content,
      payload: { reason: "left" },
    });
    await committer.submit(raw, localReceipt(event_id, now()));
    abandoned.push(event_id);
  }
  return { identity, log, committer, abandoned };
}
