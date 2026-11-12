// 掌握度投影 mastery/1（竖切片 1 规格第 4 节；事件规格 6.2～6.4）。
// 纯函数：输出只取决于事件集合，和到达顺序无关。不读时间、随机数、收据、发布包。
import { sameJson } from "./validate.js";

export const ALGORITHM_VERSION = "mastery/1";

/**
 * @typedef {{correct: number, answered: number}} Score
 * @typedef {{state: "untouched"|"explored"|"lit", best: Score|null}} NodeMastery
 * @typedef {{algorithm_version: string, nodes: Record<string, NodeMastery>, conflicts: {attempt_id: string, rule: number}[]}} Mastery
 */

const END = new Set(["attempt.completed", "attempt.abandoned"]);
const cmpStr = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

/**
 * 一次尝试的事件按 device_seq 排好以后，返回不满足的规则里编号最小的那条；都满足时返回 0。
 * @param {any[]} evs 已按 device_seq 排序
 * @returns {number}
 */
export function attemptRule(evs) {
  const f = evs[0];
  // 1. 同一台设备、同一个孩子
  if (!evs.every((e) => e.device_id === f.device_id && e.learner_id === f.learner_id)) return 1;
  // 2. actor 是这条事件的孩子本人；只有 attempt.abandoned 允许 system
  for (const e of evs) {
    const ok = (e.actor.type === "learner" && e.actor.id === e.learner_id) ||
      (e.verb === "attempt.abandoned" && e.actor.type === "system");
    if (!ok) return 2;
  }
  // 3. content 语义相同
  if (!evs.every((e) => sameJson(e.content, f.content))) return 3;
  // 4. 第一条是唯一的 started；结束事件最多一条，有的话是最后一条
  if (f.verb !== "attempt.started") return 4;
  if (evs.filter((e) => e.verb === "attempt.started").length !== 1) return 4;
  const ends = evs.map((e, i) => (END.has(e.verb) ? i : -1)).filter((i) => i >= 0);
  if (ends.length > 1) return 4;
  if (ends.length === 1 && ends[0] !== evs.length - 1) return 4;
  // 5. 同一 item_id 的 try 恰好是 1、2、3……
  /** @type {Map<string, number>} */
  const tries = new Map();
  for (const e of evs) {
    if (e.verb !== "item.answered") continue;
    const id = e.payload.item_id;
    const want = (tries.get(id) || 0) + 1;
    if (e.payload.try !== want) return 5;
    tries.set(id, want);
  }
  // 6. answer.revealed：之前已有同题 item.answered；同一 item_id 最多一条；之后不再有同题 item.answered（CURIO-013）
  /** @type {Set<string>} */
  const answered = new Set();
  /** @type {Set<string>} */
  const revealed = new Set();
  for (const e of evs) {
    const id = e.payload.item_id;
    if (e.verb === "item.answered") {
      if (revealed.has(id)) return 6;
      answered.add(id);
    } else if (e.verb === "answer.revealed") {
      if (!answered.has(id) || revealed.has(id)) return 6;
      revealed.add(id);
    }
  }
  return 0;
}

/**
 * 把事件按 attempt_id 分组，每组按 device_seq 排序（相同时按 device_id、event_id，保证确定）。
 * @param {any[]} events
 * @returns {Map<string, any[]>}
 */
export function groupAttempts(events) {
  /** @type {Map<string, any[]>} */
  const g = new Map();
  for (const e of events) {
    if (typeof e.attempt_id !== "string") continue;
    if (!g.has(e.attempt_id)) g.set(e.attempt_id, []);
    /** @type {any[]} */ (g.get(e.attempt_id)).push(e);
  }
  for (const evs of g.values()) {
    evs.sort((a, b) => a.device_seq - b.device_seq || cmpStr(a.device_id, b.device_id) || cmpStr(a.event_id, b.event_id));
  }
  return g;
}

/**
 * 一次尝试的首答成绩。
 * @param {any[]} evs
 * @returns {Score}
 */
export function firstTryScore(evs) {
  const items = new Set();
  let correct = 0;
  for (const e of evs) {
    if (e.verb !== "item.answered") continue;
    items.add(e.payload.item_id);
    if (e.payload.try === 1 && e.payload.correct === true) correct++;
  }
  return { correct, answered: items.size };
}

/**
 * 掌握度投影。
 * @param {any[]} events 已接收的事件（log.events()）
 * @returns {Mastery}
 */
export function projectMastery(events) {
  /** @type {Record<string, {best: Score|null, completed: boolean}>} */
  const acc = {};
  for (const e of events) {
    const id = e.content && e.content.node_id;
    if (typeof id === "string" && !Object.prototype.hasOwnProperty.call(acc, id)) acc[id] = { best: null, completed: false };
  }
  const conflicts = [];
  for (const [attempt_id, evs] of groupAttempts(events)) {
    const rule = attemptRule(evs);
    if (rule) { conflicts.push({ attempt_id, rule }); continue; }
    if (evs[evs.length - 1].verb !== "attempt.completed") continue;
    const node = acc[evs[0].content.node_id];
    node.completed = true;
    if (evs[0].content.activity_kind !== "quiz") continue;
    const s = firstTryScore(evs);
    if (s.answered === 0) continue;
    const b = node.best;
    if (!b) { node.best = s; continue; }
    const l = s.correct * b.answered, r = b.correct * s.answered;
    if (l > r || (l === r && s.answered > b.answered)) node.best = s;
  }
  /** @type {Record<string, NodeMastery>} */
  const nodes = {};
  for (const id of Object.keys(acc).sort(cmpStr)) {
    const { best, completed } = acc[id];
    const lit = best !== null && best.correct * 5 >= best.answered * 4;
    nodes[id] = { state: lit ? "lit" : completed ? "explored" : "untouched", best: best ? { ...best } : null };
  }
  conflicts.sort((a, b) => cmpStr(a.attempt_id, b.attempt_id));
  return { algorithm_version: ALGORITHM_VERSION, nodes, conflicts };
}
