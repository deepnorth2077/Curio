// 竖切片 6a：恢复计划和写进存储（docs/specs/backup.md 6.1～6.3、2.3；接口见 docs/specs/backup-api.md）。
// planRestore 是纯函数：不碰存储、时间和随机数；runRestore、abandonRestore 只通过传进来的 store（规格 5.2）写。
import { createLog } from "../kernel/js/log.js";
import { SLICE_VERBS, isObject } from "../kernel/js/validate.js";

/** 5.2：restoreBatch 一次最多 500 项。 */
const BATCH = 500;
const COUNTS = ["accepted", "duplicate", "not_yet_known", "quarantined_new", "quarantined_skipped", "archived", "releases"];
/** 6.1 第 4 行：这四样都相同才是「同一个文件」。 */
const SAME_FILE = ["file_created_at", "file_device_id", "file_salt", "file_learner_id"];

/** 按码点比较（规范 JSON 的键排序；不用 localeCompare）。 @param {string} a @param {string} b */
function cmp(a, b) {
  for (let i = 0; ; ) {
    if (i >= a.length || i >= b.length) return Number(i < a.length) - Number(i < b.length);
    const x = /** @type {number} */ (a.codePointAt(i)), y = /** @type {number} */ (b.codePointAt(i));
    if (x !== y) return x - y;
    i += x > 0xffff ? 2 : 1;
  }
}

/** 3.7 末尾的规范 JSON：键按码点排序，整数值写成整数（JS 读 5.0 本来就得到 5）。 */
function canonical(v) {
  if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
  if (isObject(v)) return "{" + Object.keys(v).sort(cmp).map((k) => JSON.stringify(k) + ":" + canonical(v[k])).join(",") + "}";
  return JSON.stringify(v);
}
/** 6.2 第 4 步的比较键。 */
const compareKey = (kind, v) => kind + "\n" + canonical(v);

/** 5.3 import-record/1，字段按表的顺序。 */
function importRecord(marker, at, partial, counts) {
  return {
    schema: "import-record/1", batch_id: marker.batch_id, imported_at: at, source: "backup", partial,
    file_created_at: marker.file_created_at, file_device_id: marker.file_device_id, file_salt: marker.file_salt, ...counts,
  };
}

/**
 * 6.2 第 3 步「这一版还不认识的」：自己解析原文判断，不靠 log.check 的 detail。调用前已知日志判它 invalid。
 * @param {string} raw
 */
function notYetKnown(raw) {
  let e;
  try { e = JSON.parse(raw); } catch { return false; }
  if (!isObject(e) || typeof e.schema !== "string" || !e.schema.startsWith("event/")) return false;
  return e.schema !== "event/2" || (typeof e.verb === "string" && !SLICE_VERBS.includes(e.verb));
}

/**
 * 6.1、6.2：能不能恢复到这台设备，能的话要写什么。
 * @param {any} existing store.snapshot() 的结果
 * @param {{header: any, backup: any}} file readBackup 的 {header, backup}
 * @param {{batchId: string, now: string, inputKey: string}} opts inputKey 是这次输入并通过 key_check 的 6 位数字
 */
export function planRestore(existing, { header, backup }, { batchId, now, inputKey }) {
  const man = backup.manifest;
  const me = existing.identity.device_id;
  const file = { file_created_at: header.created_at, file_device_id: man.device_id, file_salt: header.salt, file_learner_id: man.learner_id };

  // 1. 6.1：先看 restoring，再看干净不干净
  let marker, identity = { ...existing.identity };
  if (existing.restoring) {
    if (SAME_FILE.some((k) => existing.restoring[k] !== file[k])) return { ok: false, reason: "other_restore" };
    marker = { ...existing.restoring }; // 沿用标记里的 batch_id，身份在第一次 restoreBegin 时已经换了
  } else {
    marker = { batch_id: batchId, started_at: now, ...file };
    const clean = [existing.inbox, existing.receipts, existing.imports, existing.archive].every((a) => a.length === 0);
    if (clean) identity = { learner_id: man.learner_id, device_id: me }; // device_id 不变（6.1 末段）
    else if (man.learner_id !== identity.learner_id) return { ok: false, reason: "other_learner" };
  }

  // 2.3：本机没有确认过的密钥就换成输入的这把；有确认过的就不动，不一样时提示
  const rk = existing.recoveryKey;
  const confirmed = Boolean(rk && rk.confirmed_at != null);
  const recoveryKey = confirmed ? null : { digits: inputKey, confirmed_at: now };
  const keyMismatch = confirmed && rk.digits !== inputKey;

  // 2. 本机的日志，和外壳启动时一样
  const log = createLog();
  for (const raw of existing.inbox) log.ingest(raw);
  const seenRaw = new Set(existing.inbox);
  const n = Object.fromEntries(COUNTS.map((k) => [k, 0]));
  const items = [], acceptedIds = [];

  // 3. 备份的收件表，按到达顺序。见过的原文只可能是重复或再进隔离区，只判断不摄入
  for (const raw of backup.inbox) {
    const seen = seenRaw.has(raw);
    const r = seen ? log.check(raw) : log.ingest(raw);
    seenRaw.add(raw);
    if (r.result === "accepted") {
      const e = JSON.parse(raw);
      const item = { inbox: raw, receipt: { event_id: e.event_id, recorded_at: now, source: "import", batch_id: marker.batch_id } };
      if (e.device_id === me) item.own_seq = e.device_seq;
      items.push(item);
      acceptedIds.push(e.event_id);
      n.accepted++;
    } else if (r.result === "duplicate") n.duplicate++;
    else if (seen) n.quarantined_skipped++;
    else {
      items.push({ inbox: raw });
      n[r.reason === "invalid" && notYetKnown(raw) ? "not_yet_known" : "quarantined_new"]++;
    }
  }

  // 4. 带过来的收据和导入记录：比较键已经有的跳过
  const keys = new Set([
    ...existing.receipts.map((v) => compareKey("receipt", v)),
    ...existing.imports.map((v) => compareKey("import", v)),
    ...existing.archive.map((a) => compareKey(a.kind, a.v)),
  ]);
  const carried = [...backup.receipt.map((v) => ({ kind: "receipt", v })), ...backup.import.map((v) => ({ kind: "import", v })), ...backup.archive];
  for (const { kind, v } of carried) {
    const k = compareKey(kind, v);
    if (keys.has(k)) continue;
    keys.add(k);
    items.push({ archive: { kind, v } });
    n.archived++;
  }

  // 5. 发布包：本机没有这个 release_id 的才放
  const have = new Set(existing.releases.map((r) => r.release_id));
  for (const raw of backup.release) {
    const release_id = JSON.parse(raw).release_id;
    if (have.has(release_id)) continue;
    have.add(release_id);
    items.push({ release: { release_id, raw } });
    n.releases++;
  }

  // 6. nextSeq 不落后于本机被接收事件的最大序号（网页存储被回滚过时，备份里会有本机以前的事件）
  const before = existing.nextSeq ?? 1;
  let nextSeq = before;
  for (const e of log.events()) if (e.device_id === me) nextSeq = Math.max(nextSeq, e.device_seq + 1);

  // 7. 报告：被接收的事件里一条原来的收据都没有的条数（只是提示）
  const receipted = new Set([...backup.receipt, ...existing.receipts].map((r) => r.event_id));
  for (const a of [...backup.archive, ...existing.archive]) if (a.kind === "receipt") receipted.add(a.v.event_id);

  const batches = [];
  for (let s = 0; s < items.length; s += BATCH) {
    const part = items.slice(s, s + BATCH);
    batches.push({ items: part, ownSeqMax: Math.max(0, ...part.map((i) => i.own_seq ?? 0)) });
  }
  return {
    ok: true, batchId: marker.batch_id, marker, identity, changeIdentity: identity.learner_id !== existing.identity.learner_id,
    recoveryKey, keyMismatch, items, batches, nextSeq,
    record: importRecord(marker, now, false, n),
    report: { ...n, fingerprint: null, ownEarlier: nextSeq > before, noReceipt: acceptedIds.filter((id) => !receipted.has(id)).length },
  };
}

const LOCK_LOST = Symbol("lock_lost");

/**
 * 6.3 第 3 步：restoreBegin → 每批一次 restoreBatch → restoreEnd。每个事务之前查一次写锁，失锁就停，留着标记。
 * @param {any} store 有规格 5.2 的方法
 * @param {any} plan planRestore 的 ok 结果
 * @param {{lockLost: () => boolean}} deps
 */
export async function runRestore(store, plan, { lockLost }) {
  let wrote = 0;
  const tx = async (fn) => { if (lockLost()) throw LOCK_LOST; await fn(); };
  try {
    await tx(() => store.restoreBegin(plan.marker, plan.changeIdentity ? plan.identity : null, plan.recoveryKey));
    for (const b of plan.batches) {
      await tx(() => store.restoreBatch(b.items, b.ownSeqMax));
      wrote++;
    }
    await tx(() => store.restoreEnd(plan.record));
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e === LOCK_LOST ? "lock_lost" : "store_failed", wrote };
  }
}

/**
 * 6.3「不恢复了，就用现在这些」：用标记里的 batch_id 写一条 partial: true、计数全为 0 的导入记录，删掉标记。
 * @param {any} store @param {any} existing store.snapshot() 的结果 @param {{now: string}} opts
 */
export async function abandonRestore(store, existing, { now }) {
  if (!existing.restoring) return { ok: false, error: "store_failed" };
  const zeros = Object.fromEntries(COUNTS.map((k) => [k, 0]));
  try {
    await store.restoreAbandon(importRecord(existing.restoring, now, true, zeros));
    return { ok: true };
  } catch {
    return { ok: false, error: "store_failed" };
  }
}
