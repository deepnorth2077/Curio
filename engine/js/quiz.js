// 挑战的纯状态机（竖切片 1 规格 6.1）。输入动作，输出界面状态和要写的事件意图。不碰 DOM、存储、时间和随机数。
// 状态是普通的 JSON 对象；step 不改旧状态，忽略的动作原样返回同一个对象。
import { grade, checkAnswerNumbers } from "./grade.js";

/**
 * @typedef {"starting"|"answering"|"finishing"|"done"} Phase
 * @typedef {{id: number, verb: string, payload: Record<string, unknown>}} Pending
 * @typedef {{item_id: string, correct: boolean, text: string}} Feedback
 * @typedef {{id: string, stem: string, figure: any, choices: {id: string, text: string}[]}} ItemView
 * @typedef {{
 *   phase: Phase,
 *   item_id: string|null,
 *   item: ItemView|null,
 *   index: number,
 *   total: number,
 *   wrong_choices: string[],
 *   waiting: boolean,
 *   failed: boolean,
 *   feedback: Feedback|null,
 *   result: {first_try_correct: number, total: number}|null,
 * }} View
 * @typedef {{
 *   phase: Phase, pending: Pending|null, view: View,
 *   s: {items: Record<string, any>, order: string[], pos: number, tries: Record<string, number>,
 *       first: Record<string, boolean>, wrong: Record<string, string[]>, nextId: number,
 *       inflight: {item_id: string, correct: boolean, response: string, text: string}|null,
 *       failed: boolean, feedback: Feedback|null}
 * }} Quiz
 */

/** 内容里没写反馈时的默认的话。 */
export const DEFAULT_FEEDBACK = Object.freeze({ correct: "答对了！", wrong: "再想想，换一个试试。" });

const clone = (x) => JSON.parse(JSON.stringify(x));

/**
 * 开始一次挑战。
 * @param {any} activity 活动文件（activity-def/1，kind 是 quiz）
 * @param {string[]} order 活动全部 item_id 的一个排列
 * @param {"first"|"retry"} mode
 * @returns {Quiz}
 */
export function startQuiz(activity, order, mode) {
  if (!activity || activity.kind !== "quiz") throw new TypeError("不是挑战活动");
  if (mode !== "first" && mode !== "retry") throw new TypeError("mode 只能是 first 或 retry");
  const list = activity.body && activity.body.items;
  if (!Array.isArray(list) || list.length === 0) throw new TypeError("挑战里没有题目");
  /** @type {Record<string, any>} */
  const items = {};
  for (const it of list) {
    if (!it || typeof it.id !== "string") throw new TypeError("题目没有 id");
    if (Object.prototype.hasOwnProperty.call(items, it.id)) throw new TypeError(`题目 id 重复：${it.id}`);
    const a = it.answer;
    if (!a || typeof a !== "object") throw new TypeError(`${it.id} 没有答案`);
    checkAnswerNumbers(a);
    if (a.type !== "choice") throw new TypeError(`1a 只支持选择题：${it.id} 是 ${a.type}`);
    const cs = a.choices;
    if (!Array.isArray(cs) || cs.length < 2) throw new TypeError(`${it.id} 的选项不够`);
    if (new Set(cs.map((c) => c.id)).size !== cs.length) throw new TypeError(`${it.id} 的选项 id 重复`);
    if (cs.filter((c) => c.correct === true).length !== 1) throw new TypeError(`${it.id} 要恰好一个正确选项`);
    items[it.id] = clone(it);
  }
  if (!Array.isArray(order) || order.length !== list.length || new Set(order).size !== order.length ||
      !order.every((id) => typeof id === "string" && Object.prototype.hasOwnProperty.call(items, id))) {
    throw new RangeError("order 不是活动全部题目的一个排列");
  }
  const s = {
    items, order: order.slice(), pos: 0, tries: {}, first: {}, wrong: {}, nextId: 2,
    inflight: null, failed: false, feedback: null,
  };
  const pending = { id: 1, verb: "attempt.started", payload: { mode } };
  return build("starting", pending, s);
}

/** 按内部状态算出 view。 @returns {Quiz} */
function build(phase, pending, s) {
  const total = s.order.length;
  const id = phase === "answering" ? s.order[s.pos] : null;
  const it = id ? s.items[id] : null;
  /** @type {View} */
  const view = {
    phase,
    item_id: id,
    item: it ? {
      id: it.id, stem: it.stem, figure: it.figure === undefined ? null : it.figure,
      choices: it.answer.choices.map((c) => ({ id: c.id, text: c.text })),
    } : null,
    index: Math.min(s.pos, total),
    total,
    wrong_choices: id ? (s.wrong[id] || []).slice() : [],
    waiting: pending !== null,
    failed: pending !== null && s.failed,
    feedback: s.feedback,
    result: phase === "done" ? {
      first_try_correct: s.order.filter((k) => s.first[k] === true).length,
      total,
    } : null,
  };
  return { phase, pending, view, s };
}

/** 这次作答的反馈文字。 */
function feedbackText(item, response, correct) {
  const fb = item.feedback || {};
  if (correct) return typeof fb.correct === "string" ? fb.correct : DEFAULT_FEEDBACK.correct;
  const c = item.answer.choices.find((x) => x.id === response);
  if (c && typeof c.feedback === "string") return c.feedback;
  return typeof fb.wrong === "string" ? fb.wrong : DEFAULT_FEEDBACK.wrong;
}

/**
 * 推进状态机。纯函数，返回新状态；忽略的动作原样返回 q。
 * @param {Quiz} q
 * @param {{type: "answer", response: string}|{type: "saved", id: number}|{type: "failed", id: number}|{type: "retry"}} action
 * @returns {Quiz}
 */
export function step(q, action) {
  if (!action || typeof action !== "object") return q;
  switch (action.type) {
    case "answer": {
      if (q.phase !== "answering" || q.pending) return q;
      const response = action.response;
      if (typeof response !== "string" || [...response].length > 32) return q;
      const id = q.s.order[q.s.pos];
      const item = q.s.items[id];
      const g = grade(item.answer, response);
      const payload = { item_id: id, response, correct: g.correct, try: (q.s.tries[id] || 0) + 1, hints_used: 0 };
      if (g.misconception !== null) payload.misconception = g.misconception;
      const s = { ...q.s, nextId: q.s.nextId + 1, failed: false,
        inflight: { item_id: id, correct: g.correct, response, text: feedbackText(item, response, g.correct) } };
      return build("answering", { id: q.s.nextId, verb: "item.answered", payload }, s);
    }
    case "saved": {
      if (!q.pending || action.id !== q.pending.id) return q;
      if (q.phase === "starting") return build("answering", null, { ...q.s, failed: false });
      if (q.phase === "finishing") return build("done", null, { ...q.s, failed: false });
      if (q.phase !== "answering" || !q.s.inflight) return q;
      const f = q.s.inflight;
      const s = {
        ...q.s,
        tries: { ...q.s.tries, [f.item_id]: (q.s.tries[f.item_id] || 0) + 1 },
        first: Object.prototype.hasOwnProperty.call(q.s.first, f.item_id) ? q.s.first : { ...q.s.first, [f.item_id]: f.correct },
        wrong: f.correct ? q.s.wrong : { ...q.s.wrong, [f.item_id]: [...(q.s.wrong[f.item_id] || []), f.response] },
        feedback: { item_id: f.item_id, correct: f.correct, text: f.text },
        inflight: null,
        failed: false,
      };
      if (!f.correct) return build("answering", null, s);
      s.pos = q.s.pos + 1;
      if (s.pos < s.order.length) return build("answering", null, s);
      // 最后一题的正确作答存好了。只有每道题都有已存好的作答时才完成。
      if (!s.order.every((k) => (s.tries[k] || 0) >= 1)) return build("answering", null, { ...s, pos: q.s.pos });
      const pending = { id: s.nextId, verb: "attempt.completed", payload: {} };
      return build("finishing", pending, { ...s, nextId: s.nextId + 1 });
    }
    case "failed": {
      if (!q.pending || action.id !== q.pending.id) return q;
      if (q.s.failed) return q;
      return build(q.phase, q.pending, { ...q.s, failed: true });
    }
    case "retry":
      return q;
  }
  return q;
}
