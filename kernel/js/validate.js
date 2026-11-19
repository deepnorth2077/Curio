// 事件信封和 payload 的校验（竖切片 1 规格第 3 节；事件规格第 2 节；schemas/event.schema.json）。
// 纯函数：不碰 DOM、存储、时间和随机数。字符串长度一律按 Unicode 码点数。

/** 本切片认的 6 个动词（answer.revealed 是 CURIO-013 加的）。 */
export const SLICE_VERBS = Object.freeze([
  "attempt.started",
  "item.answered",
  "hint.used",
  "answer.revealed",
  "attempt.completed",
  "attempt.abandoned",
]);

/** schemas/event.schema.json 里 verb 的全部取值（信封校验用；本切片只认其中 6 个）。 */
const SCHEMA_VERBS = new Set([
  "attempt.started", "attempt.completed", "attempt.abandoned",
  "poe.predicted", "poe.explained", "sim.adjusted", "sim.observed",
  "item.answered", "hint.used", "answer.revealed", "reflection.written",
  "question.asked", "question.answered",
  "repair.opened", "repair.linked", "repair.practiced", "repair.resolved",
  "plan.created", "plan.task_done", "plan.task_undone",
  "reward.goal_set", "reward.redeem_requested", "reward.spent", "reward.adjusted", "reward.revoked",
  "import.voided", "attachment.erased", "text.erased",
]);

const ULID = "[0-7][0-9A-HJKMNP-TV-Z]{25}";
const RE = {
  evt: new RegExp(`^evt_${ULID}$`),
  lrn: new RegExp(`^lrn_${ULID}$`),
  cg: new RegExp(`^cg_${ULID}$`),
  dev: new RegExp(`^dev_${ULID}$`),
  att: new RegExp(`^att_${ULID}$`),
  imp: new RegExp(`^imp_${ULID}$`),
  sys: /^sys:[a-z0-9-]+$/,
  rel: /^rel_[0-9a-f]{64}$/,
  node: /^[a-z]+(\.[a-z0-9-]+)+$/,
  act: /^act\.[a-z]+\.[a-z0-9-]+$/,
  grader: /^[a-z][a-z0-9-]*\/[1-9][0-9]*$/,
  ts: /^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{3}Z$/,
};

const MAX_SAFE = 9007199254740991;

/**
 * 一个数的最短十进制表示（String(x)）小数点后有几位，按指数换算。
 * @param {number} x 有限数
 * @returns {number}
 */
export function decimalPlaces(x) {
  const m = /^-?(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/.exec(String(x));
  if (!m) return Infinity;
  const frac = m[2] ? m[2].length : 0;
  const exp = m[3] ? Number(m[3]) : 0;
  return Math.max(0, frac - exp);
}

/**
 * 数值规则（事件规格第 2 节）：整数值绝对值不超过 2^53−1；非整数绝对值小于 10^9，最短十进制表示不超过 6 位小数。
 * @param {unknown} x
 * @returns {boolean}
 */
export function numberOk(x) {
  if (typeof x !== "number" || !Number.isFinite(x)) return false;
  if (Number.isInteger(x)) return Math.abs(x) <= MAX_SAFE;
  return Math.abs(x) < 1e9 && decimalPlaces(x) <= 6;
}

/**
 * 递归检查一个 JSON 值里的每一个数。
 * @param {unknown} v
 * @returns {boolean}
 */
export function allNumbersOk(v) {
  if (typeof v === "number") return numberOk(v);
  if (Array.isArray(v)) return v.every(allNumbersOk);
  if (v !== null && typeof v === "object") return Object.values(v).every(allNumbersOk);
  return true;
}

/** @param {unknown} v @returns {v is Record<string, unknown>} */
export const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const isInt = (v) => typeof v === "number" && Number.isInteger(v);
const isStr = (v) => typeof v === "string";
/** 按码点数的字符串长度。 @param {string} s */
export const codePoints = (s) => [...s].length;

/**
 * 只许出现这些键，必须有 required 里的键。
 * @param {Record<string, unknown>} o @param {string[]} allowed @param {string[]} required
 * @returns {string|null} 不合格时的说明
 */
function keys(o, allowed, required, where) {
  for (const k of required) if (!has(o, k)) return `${where}缺少 ${k}`;
  for (const k of Object.keys(o)) if (!allowed.includes(k)) return `${where}多了 ${k}`;
  return null;
}

const ENVELOPE_REQUIRED = ["schema", "event_id", "learner_id", "device_id", "device_seq", "occurred_at", "actor", "verb", "payload"];
const ENVELOPE_ALLOWED = [...ENVELOPE_REQUIRED, "attempt_id", "content", "import_batch"];
const CONTENT_KEYS = ["node_id", "activity_id", "activity_kind", "activity_version", "content_release"];
const KINDS = ["explain", "quiz", "reflection", "experiment", "simulation"];

/**
 * 信封校验（schemas/event.schema.json 的信封部分）。
 * @param {Record<string, unknown>} e
 * @returns {string|null}
 */
export function checkEnvelope(e) {
  const k = keys(e, ENVELOPE_ALLOWED, ENVELOPE_REQUIRED, "信封");
  if (k) return k;
  if (e.schema !== "event/2") return "schema 不是 event/2";
  if (!isStr(e.event_id) || !RE.evt.test(e.event_id)) return "event_id 格式不对";
  if (!isStr(e.learner_id) || !RE.lrn.test(e.learner_id)) return "learner_id 格式不对";
  if (!isStr(e.device_id) || !RE.dev.test(e.device_id)) return "device_id 格式不对";
  if (!isInt(e.device_seq) || e.device_seq < 1) return "device_seq 要是不小于 1 的整数";
  if (!isStr(e.occurred_at) || !RE.ts.test(e.occurred_at)) return "occurred_at 格式不对";
  const a = e.actor;
  if (!isObject(a)) return "actor 不是对象";
  const ka = keys(a, ["type", "id"], ["type", "id"], "actor ");
  if (ka) return ka;
  if (!isStr(a.id)) return "actor.id 不是字符串";
  if (a.type === "learner") { if (!RE.lrn.test(a.id)) return "actor.id 格式不对"; }
  else if (a.type === "caregiver") { if (!RE.cg.test(a.id)) return "actor.id 格式不对"; }
  else if (a.type === "system") { if (!RE.sys.test(a.id)) return "actor.id 格式不对"; }
  else return "actor.type 不认识";
  if (!isStr(e.verb) || !SCHEMA_VERBS.has(e.verb)) return "verb 不认识";
  if (has(e, "attempt_id") && (!isStr(e.attempt_id) || !RE.att.test(e.attempt_id))) return "attempt_id 格式不对";
  if (has(e, "content")) {
    const c = e.content;
    if (!isObject(c)) return "content 不是对象";
    const kc = keys(c, CONTENT_KEYS, CONTENT_KEYS, "content ");
    if (kc) return kc;
    if (!isStr(c.node_id) || !RE.node.test(c.node_id)) return "content.node_id 格式不对";
    if (!isStr(c.activity_id) || !RE.act.test(c.activity_id)) return "content.activity_id 格式不对";
    if (!KINDS.includes(/** @type {string} */ (c.activity_kind))) return "content.activity_kind 不认识";
    if (!isInt(c.activity_version) || c.activity_version < 1) return "content.activity_version 要是正整数";
    if (!isStr(c.content_release) || !RE.rel.test(c.content_release)) return "content.content_release 格式不对";
  }
  if (has(e, "import_batch") && (!isStr(e.import_batch) || !RE.imp.test(e.import_batch))) return "import_batch 格式不对";
  if (!isObject(e.payload)) return "payload 不是对象";
  return null;
}

/**
 * 本切片 6 个动词各自的规则（第 3 节的表）。调用前信封已经合格。
 * @param {Record<string, any>} e
 * @returns {string|null}
 */
export function checkVerb(e) {
  if (!SLICE_VERBS.includes(e.verb)) return "这一版不认这个动词";
  if (!has(e, "attempt_id")) return `${e.verb} 必须带 attempt_id`;
  if (!has(e, "content")) return `${e.verb} 必须带 content`;
  const t = e.actor.type;
  if (e.verb === "attempt.abandoned") { if (t !== "learner" && t !== "system") return "attempt.abandoned 的 actor 只能是 learner 或 system"; }
  else if (t !== "learner") return `${e.verb} 的 actor 只能是 learner`;
  const p = e.payload;
  switch (e.verb) {
    case "attempt.started": {
      const k = keys(p, ["mode", "grader"], ["mode"], "payload ");
      if (k) return k;
      if (!["first", "retry", "review"].includes(p.mode)) return "mode 不认识";
      if (has(p, "grader") && (!isStr(p.grader) || codePoints(p.grader) > 32 || !RE.grader.test(p.grader))) return "grader 格式不对";
      return null;
    }
    case "attempt.completed": {
      const k = keys(p, ["duration_ms"], ["duration_ms"], "payload ");
      if (k) return k;
      if (!isInt(p.duration_ms) || p.duration_ms < 0) return "duration_ms 要是非负整数";
      return null;
    }
    case "attempt.abandoned": {
      const k = keys(p, ["reason"], ["reason"], "payload ");
      if (k) return k;
      if (!["left", "timeout", "error"].includes(p.reason)) return "reason 不认识";
      return null;
    }
    case "item.answered": {
      const req = ["item_id", "response", "correct", "try", "hints_used"];
      const k = keys(p, [...req, "misconception"], req, "payload ");
      if (k) return k;
      if (!isStr(p.item_id)) return "item_id 不是字符串";
      if (!isStr(p.response)) return "response 不是字符串";
      if (codePoints(p.response) > 32) return "response 超过 32 个字符";
      if (typeof p.correct !== "boolean") return "correct 只能是 true 或 false";
      if (!isInt(p.try) || p.try < 1) return "try 要是不小于 1 的整数";
      if (!isInt(p.hints_used) || p.hints_used < 0) return "hints_used 要是非负整数";
      if (has(p, "misconception") && !isStr(p.misconception)) return "misconception 不是字符串";
      return null;
    }
    case "hint.used": {
      const k = keys(p, ["item_id", "level"], ["level"], "payload ");
      if (k) return k;
      if (has(p, "item_id") && !isStr(p.item_id)) return "item_id 不是字符串";
      if (!isInt(p.level) || p.level < 1 || p.level > 3) return "level 只能是 1～3";
      return null;
    }
    case "answer.revealed": {
      const k = keys(p, ["item_id"], ["item_id"], "payload ");
      if (k) return k;
      if (!isStr(p.item_id)) return "item_id 不是字符串";
      return null;
    }
  }
  return "这一版不认这个动词";
}

/**
 * 两个 JSON 值语义相同（事件规格 5.2）：类型必须相同，对象不看键的顺序，数字按数值比。
 * @param {unknown} a @param {unknown} b
 * @returns {boolean}
 */
export function sameJson(a, b) {
  if (a === null || b === null) return a === b;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((x, i) => sameJson(x, b[i]));
  }
  if (typeof a !== typeof b) return false;
  if (typeof a === "object") {
    const ka = Object.keys(/** @type {object} */ (a));
    const kb = Object.keys(/** @type {object} */ (b));
    if (ka.length !== kb.length) return false;
    return ka.every((k) => has(b, k) && sameJson(a[k], b[k]));
  }
  return a === b;
}

/**
 * 字符串按 UTF-8 编码的字节数（孤立的代理项按 U+FFFD 算 3 字节，和 TextEncoder 一致）。
 * @param {string} s
 * @returns {number}
 */
export function utf8Bytes(s) {
  let n = 0;
  for (const ch of s) {
    const cp = /** @type {number} */ (ch.codePointAt(0));
    n += cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4;
  }
  return n;
}
