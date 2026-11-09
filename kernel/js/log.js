// 内存里的事件日志：摄入、去重、冲突、隔离区（竖切片 1 规格第 3 节；事件规格 5.1、5.2）。
// 纯内存，不碰 DOM、存储、时间和随机数。外壳启动时把存下来的原始文字按到达顺序重新 ingest，就恢复出同样的日志。
import { allNumbersOk, checkEnvelope, checkVerb, isObject, sameJson, utf8Bytes } from "./validate.js";

/** 原始文字的 UTF-8 字节上限（事件规格第 2 节「大小」）。 */
export const MAX_RAW_BYTES = 16384;

/**
 * @typedef {{result: "accepted"|"duplicate"|"quarantined", reason?: "invalid"|"conflict", detail?: string}} IngestResult
 * @typedef {{raw: string, reason: "invalid"|"conflict", detail: string}} Quarantined
 */

/** 深冻结，免得调用方改了日志里的事件。 @template T @param {T} v @returns {T} */
function deepFreeze(v) {
  if (v !== null && typeof v === "object") {
    for (const x of Object.values(v)) deepFreeze(x);
    Object.freeze(v);
  }
  return v;
}

const invalid = (detail) => ({ result: /** @type {const} */ ("quarantined"), reason: /** @type {const} */ ("invalid"), detail });
const conflict = (detail) => ({ result: /** @type {const} */ ("quarantined"), reason: /** @type {const} */ ("conflict"), detail });

/**
 * 新建一个空的内存日志。
 */
export function createLog() {
  /** @type {object[]} */ const events = [];
  /** @type {string[]} */ const raws = [];
  /** @type {Quarantined[]} */ const quarantine = [];
  /** @type {Map<string, object>} event_id → 已接收的事件 */ const byId = new Map();
  /** @type {Map<string, string>} device_id + device_seq → event_id */ const bySeq = new Map();
  const seqKey = (e) => `${e.device_id}\u0000${e.device_seq}`;

  /**
   * 判断，不改日志。返回判断结果和解析出的事件（接收时）。
   * @param {string} raw
   * @returns {{r: IngestResult, event?: any}}
   */
  function judge(raw) {
    if (typeof raw !== "string") return { r: invalid("原始文字不是字符串") };
    if (utf8Bytes(raw) > MAX_RAW_BYTES) return { r: invalid(`超过 ${MAX_RAW_BYTES} 字节`) };
    let e;
    try { e = JSON.parse(raw); } catch { return { r: invalid("不是合法的 JSON") }; }
    if (!isObject(e)) return { r: invalid("顶层不是对象") };
    if (!allNumbersOk(e)) return { r: invalid("有数不满足数值规则") };
    const env = checkEnvelope(e);
    if (env) return { r: invalid(env) };
    const vb = checkVerb(e);
    if (vb) return { r: invalid(vb) };
    const old = byId.get(e.event_id);
    if (old) return sameJson(old, e) ? { r: { result: "duplicate" } } : { r: conflict("event_id 已经有了，内容不同") };
    if (bySeq.has(seqKey(e))) return { r: conflict("(device_id, device_seq) 已被另一条事件占用") };
    return { r: { result: "accepted" }, event: e };
  }

  return {
    /** 判断结果，不改日志。 @param {string} raw @returns {IngestResult} */
    check(raw) {
      return { ...judge(raw).r };
    },
    /** 和 check 同样的结果，并按结果改日志。 @param {string} raw @returns {IngestResult} */
    ingest(raw) {
      const { r, event } = judge(raw);
      if (r.result === "accepted") {
        deepFreeze(event);
        events.push(event);
        raws.push(raw);
        byId.set(event.event_id, event);
        bySeq.set(seqKey(event), event.event_id);
      } else if (r.result === "quarantined") {
        quarantine.push(Object.freeze({ raw, reason: /** @type {"invalid"|"conflict"} */ (r.reason), detail: r.detail || "" }));
      }
      return { ...r };
    },
    /** 已接收的事件（解析后的对象，已冻结），按接收顺序。 */
    events() { return events.slice(); },
    /** 已接收事件的原始文字，按接收顺序。 */
    raw() { return raws.slice(); },
    /** 隔离区：[{raw, reason, detail}]，按到达顺序。 */
    quarantined() { return quarantine.map((q) => ({ ...q })); },
  };
}
