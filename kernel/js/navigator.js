// 选了谁：领航员选择的投影 navigator/1（docs/specs/navigators.md 第 3 节；事件规格 6.1、6.4）。
// 纯函数：不碰 DOM、存储、时间和随机数。规则照 profile/1（kernel/js/profile.js）。

export const ALGORITHM_VERSION = "navigator/1";

/**
 * @typedef {{algorithm_version: string, navigator_id: string|null, rev: number, conflicts: {event_id: string, reason: "same_rev"}[]}} NavigatorProjection
 */

const cmpStr = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

/**
 * 排序键 (occurred_at, device_id, device_seq, event_id) 的比较；device_seq 按整数比。
 * @param {any} a @param {any} b
 * @returns {number}
 */
function cmpKey(a, b) {
  return cmpStr(a.occurred_at, b.occurred_at) || cmpStr(a.device_id, b.device_id) ||
    a.device_seq - b.device_seq || cmpStr(a.event_id, b.event_id);
}

/**
 * 当前选的领航员。rev 最大的生效；rev 相同时排序键最大的生效，其余同 rev 的列进 conflicts（按 event_id 升序）。
 * 输入里有 import.voided 时，先去掉被作废批次里的 navigator.chosen；没有时一条也不去掉。
 * 不校验 navigator_id 在不在发布包里（退回规则由调用方按发布包处理）。
 * 还没选过时 navigator_id 为 null、rev 为 0，所以下一次保存的 rev 总是「当前 rev + 1」。
 * @param {any[]} events 已接收的事件（log.events()）
 * @returns {NavigatorProjection}
 */
export function projectNavigator(events) {
  const voided = new Set();
  for (const e of events) if (e.verb === "import.voided") voided.add(e.payload.batch_id);
  const chosen = events.filter((e) => e.verb === "navigator.chosen" && !(typeof e.import_batch === "string" && voided.has(e.import_batch)));
  if (chosen.length === 0) return { algorithm_version: ALGORITHM_VERSION, navigator_id: null, rev: 0, conflicts: [] };
  const top = Math.max(...chosen.map((e) => e.payload.rev));
  const same = chosen.filter((e) => e.payload.rev === top).sort(cmpKey);
  const win = same[same.length - 1];
  const conflicts = same.slice(0, -1).map((e) => ({ event_id: e.event_id, reason: /** @type {const} */ ("same_rev") }));
  conflicts.sort((a, b) => cmpStr(a.event_id, b.event_id));
  return { algorithm_version: ALGORITHM_VERSION, navigator_id: win.payload.navigator_id, rev: top, conflicts };
}
