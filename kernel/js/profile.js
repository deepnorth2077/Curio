// 舰长资料：学年、年级和当前资料的投影 profile/1（docs/specs/profile.md 第 2、3 节；事件规格 6.1、6.4）。
// 纯函数：不碰 DOM、存储、随机数，不读当前时间，也不读运行机器的时区。时间一律由调用方以时间戳传入。

export const ALGORITHM_VERSION = "profile/1";

/** 家庭时区 UTC+8（事件规格第 1 节「本地日期」第 1 版），单位毫秒。 */
const HOME_OFFSET_MS = 8 * 3600 * 1000;

/**
 * @typedef {{rev: number, entry_year: number, textbooks: Record<string, string>, occurred_at: string}} Profile
 * @typedef {{algorithm_version: string, profile: Profile|null, conflicts: {event_id: string, reason: "same_rev"}[]}} ProfileProjection
 */

const cmpStr = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

/**
 * 学年：按 UTC+8 取年月，9 月起算当年，1～8 月算前一年。
 * @param {number} nowMs 时间戳（毫秒）
 * @returns {number}
 */
export function schoolYear(nowMs) {
  const d = new Date(nowMs + HOME_OFFSET_MS);
  const year = d.getUTCFullYear();
  return d.getUTCMonth() + 1 >= 9 ? year : year - 1;
}

/**
 * 年级：schoolYear − entry_year + 1。越界不截断，原样返回（小于 1 是还没上小学，大于 12 是已经毕业）。
 * @param {number} entry_year 一年级开学那年
 * @param {number} nowMs 时间戳（毫秒）
 * @returns {number}
 */
export function grade(entry_year, nowMs) {
  return schoolYear(nowMs) - entry_year + 1;
}

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
 * 当前舰长资料。rev 最大的生效；rev 相同时排序键最大的生效，其余同 rev 的列进 conflicts。
 * 输入里有 import.voided 时，先去掉被作废批次里的 profile.set；没有时一条也不去掉。
 * @param {any[]} events 已接收的事件（log.events()）
 * @returns {ProfileProjection}
 */
export function projectProfile(events) {
  const voided = new Set();
  for (const e of events) if (e.verb === "import.voided") voided.add(e.payload.batch_id);
  const sets = events.filter((e) => e.verb === "profile.set" && !(typeof e.import_batch === "string" && voided.has(e.import_batch)));
  if (sets.length === 0) return { algorithm_version: ALGORITHM_VERSION, profile: null, conflicts: [] };
  const top = Math.max(...sets.map((e) => e.payload.rev));
  const same = sets.filter((e) => e.payload.rev === top).sort(cmpKey);
  const win = same[same.length - 1];
  const conflicts = same.slice(0, -1).map((e) => ({ event_id: e.event_id, reason: /** @type {const} */ ("same_rev") }));
  conflicts.sort((a, b) => cmpStr(a.event_id, b.event_id));
  const p = win.payload;
  return {
    algorithm_version: ALGORITHM_VERSION,
    profile: { rev: p.rev, entry_year: p.entry_year, textbooks: { ...p.textbooks }, occurred_at: win.occurred_at },
    conflicts,
  };
}
