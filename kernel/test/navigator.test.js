// #242 PR 1（docs/specs/navigators.md 第 3 节）：选了谁，投影 navigator/1。
// 验收测试的作者写，实现者不改（受保护路径）。期望值全是规格第 3 节的规则，写成字面值。
// 跑法：node --test kernel/test/navigator.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { projectNavigator } from "../js/navigator.js";
import { SLICE_VERBS } from "../js/validate.js";

const LRN = "lrn_01JC00000000000000000000K1";
const LEARNER = { type: "learner", id: LRN };
const dev = (n) => `dev_01JC0000000000000000000D${n}`;
let counter = 0;
/** 一条 navigator.chosen。id 是 evt 的末位标签；默认设备 D1、序号自增。 */
function nc(id, rev, navigatorId, at, extra = {}) {
  counter += 1;
  const { device = 1, seq = counter, import_batch } = extra;
  const e = {
    schema: "event/2", event_id: `evt_01JC0000000000000000000${id}`, learner_id: LRN, device_id: dev(device), device_seq: seq,
    occurred_at: at, actor: LEARNER, verb: "navigator.chosen", payload: { rev, navigator_id: navigatorId },
  };
  if (import_batch) e.import_batch = import_batch;
  return e;
}
const EMPTY = { algorithm_version: "navigator/1", navigator_id: null, rev: 0, conflicts: [] };
const eid = (id) => `evt_01JC0000000000000000000${id}`;
const AT = "2026-11-22T03:00:00.000Z";

test("SLICE_VERBS 认 navigator.chosen", () => {
  assert.ok(SLICE_VERBS.includes("navigator.chosen"));
});

test("空输入：navigator_id 为 null，rev 为 0（还没选过；第一次保存取 rev + 1 = 1），conflicts 为空", () => {
  assert.deepEqual(projectNavigator([]), EMPTY);
});

test("只有别的动词：和空输入一样", () => {
  const other = { schema: "event/2", event_id: "evt_01JC0000000000000000000Q01", learner_id: LRN, device_id: dev(1), device_seq: 1,
    occurred_at: AT, actor: LEARNER, verb: "attempt.started", attempt_id: "att_01JC00000000000000000000A1", payload: { mode: "first" } };
  const profile = { schema: "event/2", event_id: "evt_01JC0000000000000000000Q02", learner_id: LRN, device_id: dev(1), device_seq: 2,
    occurred_at: AT, actor: { type: "caregiver", id: "cg_01JC00000000000000000000G1" }, verb: "profile.set",
    payload: { rev: 9, entry_year: 2024, textbooks: {} } };
  assert.deepEqual(projectNavigator([other, profile]), EMPTY);
});

test("一条：输出恰好是 {algorithm_version, navigator_id, rev, conflicts}，没有别的字段", () => {
  const r = projectNavigator([nc("N01", 1, "nav.lamp", AT)]);
  assert.deepEqual(r, { algorithm_version: "navigator/1", navigator_id: "nav.lamp", rev: 1, conflicts: [] });
  assert.deepEqual(Object.keys(r).sort(), ["algorithm_version", "conflicts", "navigator_id", "rev"]);
});

test("不校验 navigator_id 在不在发布包里：nav.gone 照样是生效的那位", () => {
  assert.equal(projectNavigator([nc("N01", 1, "nav.gone", AT)]).navigator_id, "nav.gone");
});

test("rev 优先于时钟：rev 2 的 occurred_at 更早，仍然胜出；低 rev 不进 conflicts", () => {
  const old = nc("N01", 1, "nav.lamp", "2026-11-22T03:00:00.000Z");
  const newer = nc("N02", 2, "nav.ring", "2026-11-20T03:00:00.000Z");
  for (const input of [[old, newer], [newer, old]]) {
    assert.deepEqual(projectNavigator(input), { algorithm_version: "navigator/1", navigator_id: "nav.ring", rev: 2, conflicts: [] });
  }
});

test("rev 递增 1、2、3：只有 3 生效，conflicts 为空；再换回第一位也是新的一条（rev 4）", () => {
  const e = [nc("N01", 1, "nav.lamp", "2026-11-01T03:00:00.000Z"), nc("N02", 2, "nav.ring", "2026-11-02T03:00:00.000Z"),
    nc("N03", 3, "nav.lamp", "2026-11-03T03:00:00.000Z")];
  assert.deepEqual(projectNavigator(e), { algorithm_version: "navigator/1", navigator_id: "nav.lamp", rev: 3, conflicts: [] });
  e.push(nc("N04", 4, "nav.ring", "2026-11-04T03:00:00.000Z"));
  assert.equal(projectNavigator(e).navigator_id, "nav.ring");
  assert.equal(projectNavigator(e).rev, 4);
});

test("同 rev：occurred_at 较晚的生效，落选的进 conflicts {event_id, reason: 'same_rev'}", () => {
  const early = nc("N01", 2, "nav.lamp", "2026-11-22T03:00:00.000Z", { device: 1 });
  const late = nc("N02", 2, "nav.ring", "2026-11-22T03:00:05.000Z", { device: 2 });
  for (const input of [[early, late], [late, early]]) {
    assert.deepEqual(projectNavigator(input), {
      algorithm_version: "navigator/1", navigator_id: "nav.ring", rev: 2, conflicts: [{ event_id: eid("N01"), reason: "same_rev" }],
    });
  }
});

test("同 rev、同 occurred_at：device_id 大的生效，不看 device_seq", () => {
  const d1 = nc("N01", 2, "nav.lamp", AT, { device: 1, seq: 9 });
  const d2 = nc("N02", 2, "nav.ring", AT, { device: 2, seq: 1 });
  for (const input of [[d1, d2], [d2, d1]]) {
    const r = projectNavigator(input);
    assert.equal(r.navigator_id, "nav.ring");
    assert.deepEqual(r.conflicts, [{ event_id: eid("N01"), reason: "same_rev" }]);
  }
});

test("同 rev、同 occurred_at、同设备：device_seq 按整数比（10 > 3）；再相同看 event_id", () => {
  const s3 = nc("N01", 2, "nav.lamp", AT, { seq: 3 });
  const s10 = nc("N02", 2, "nav.ring", AT, { seq: 10 });
  assert.equal(projectNavigator([s3, s10]).navigator_id, "nav.ring", "不是字符串比：\"10\" < \"3\"");
  assert.equal(projectNavigator([s10, s3]).navigator_id, "nav.ring");
  const a = nc("NAA", 2, "nav.lamp", AT, { seq: 5 });
  const b = nc("NBB", 2, "nav.ring", AT, { seq: 5 });
  assert.equal(projectNavigator([a, b]).navigator_id, "nav.ring", "event_id 大的生效");
  assert.equal(projectNavigator([b, a]).navigator_id, "nav.ring");
});

test("同 rev 同一位也算平手：落选的照样进 conflicts", () => {
  const a = nc("N01", 2, "nav.lamp", "2026-11-22T03:00:00.000Z", { device: 1 });
  const b = nc("N02", 2, "nav.lamp", "2026-11-22T03:00:09.000Z", { device: 2 });
  const r = projectNavigator([a, b]);
  assert.equal(r.navigator_id, "nav.lamp");
  assert.deepEqual(r.conflicts, [{ event_id: eid("N01"), reason: "same_rev" }]);
});

test("三条同 rev 加一条低 rev：落选的两条按 event_id 升序进 conflicts，低 rev 和生效的不进", () => {
  const low = nc("N01", 1, "nav.lamp", "2026-11-30T03:00:00.000Z");
  const a = nc("N09", 2, "nav.lamp", "2026-11-22T03:00:01.000Z", { device: 1 });
  const b = nc("N03", 2, "nav.ring", "2026-11-22T03:00:02.000Z", { device: 2 });
  const c = nc("N05", 2, "nav.gone", "2026-11-22T03:00:03.000Z", { device: 3 });
  const want = { algorithm_version: "navigator/1", navigator_id: "nav.gone", rev: 2,
    conflicts: [{ event_id: eid("N03"), reason: "same_rev" }, { event_id: eid("N09"), reason: "same_rev" }] };
  for (const input of [[c, low, a, b], [a, b, c, low], [low, b, a, c]]) assert.deepEqual(projectNavigator(input), want);
});

test("输入顺序打乱，结果完全相同", () => {
  const evs = [
    nc("N01", 1, "nav.lamp", "2026-11-01T03:00:00.000Z"),
    nc("N02", 2, "nav.ring", "2026-11-02T03:00:00.000Z", { device: 1 }),
    nc("N03", 3, "nav.lamp", "2026-11-01T01:00:00.000Z", { device: 1 }),
    nc("N04", 3, "nav.ring", "2026-11-01T01:00:00.000Z", { device: 2 }),
    nc("N05", 3, "nav.gone", "2026-10-01T01:00:00.000Z", { device: 3 }),
  ];
  const want = { algorithm_version: "navigator/1", navigator_id: "nav.ring", rev: 3,
    conflicts: [{ event_id: eid("N03"), reason: "same_rev" }, { event_id: eid("N05"), reason: "same_rev" }] };
  let state = 4242;
  const rnd = () => ((state = (Math.imul(state, 1103515245) + 12345) >>> 0) / 4294967296);
  const orders = [evs, [...evs].reverse()];
  for (let k = 0; k < 20; k++) {
    const a = [...evs];
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    orders.push(a);
  }
  for (const input of orders) assert.deepEqual(projectNavigator(input), want);
});

test("被 import.voided 作废的批次里的 navigator.chosen 不算（照 6.1；集合里没有 import.voided 时一条也不去掉）", () => {
  const BATCH = "imp_01JC00000000000000000000B1";
  const real = nc("N01", 2, "nav.lamp", "2026-11-10T03:00:00.000Z");
  const imported = nc("N02", 5, "nav.ring", "2026-11-11T03:00:00.000Z", { import_batch: BATCH });
  const voided = { schema: "event/2", event_id: "evt_01JC0000000000000000000V01", learner_id: LRN, device_id: dev(1), device_seq: 99,
    occurred_at: "2026-11-12T03:00:00.000Z", actor: { type: "caregiver", id: "cg_01JC00000000000000000000G1" },
    verb: "import.voided", payload: { batch_id: BATCH, reason: "bad_data" } };
  assert.equal(projectNavigator([real, imported]).navigator_id, "nav.ring", "没作废时 rev 5 生效");
  const r = projectNavigator([real, imported, voided]);
  assert.deepEqual(r, { algorithm_version: "navigator/1", navigator_id: "nav.lamp", rev: 2, conflicts: [] });
  assert.deepEqual(projectNavigator([voided, imported, real]), r, "顺序无关");
  assert.deepEqual(projectNavigator([imported, voided]), EMPTY, "只剩被作废的：没有选择");
  const sameRev = nc("N03", 2, "nav.gone", "2026-11-20T03:00:00.000Z", { import_batch: BATCH });
  assert.deepEqual(projectNavigator([real, sameRev, voided]).conflicts, [], "被作废批次里的同 rev 事件不进 conflicts");
});

test("不改传进来的数组和事件", () => {
  const evs = [nc("N01", 2, "nav.lamp", "2026-11-02T03:00:00.000Z"), nc("N02", 1, "nav.ring", "2026-11-03T03:00:00.000Z"),
    nc("N03", 2, "nav.ring", "2026-11-02T03:00:00.000Z", { device: 2 })];
  const copy = structuredClone(evs);
  const r = projectNavigator(evs);
  assert.deepEqual(evs, copy);
  r.conflicts.push("x");
  assert.deepEqual(projectNavigator(evs).conflicts.length, 1, "返回值和输入不共享可变状态");
});
