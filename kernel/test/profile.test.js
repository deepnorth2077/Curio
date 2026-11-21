// #224 PR 1（docs/specs/profile.md 第 2、3 节）：年级怎么算、舰长资料的投影 profile/1。
// 验收测试的作者写，实现者不改（受保护路径）。期望值全是规格第 2 节的手算例子和第 3 节的规则，写成字面值。
// 跑法：node --test kernel/test/profile.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { schoolYear, grade, projectProfile } from "../js/profile.js";
import { SLICE_VERBS } from "../js/validate.js";

const T = (iso) => Date.parse(iso);

// ---------------------------------------------------------------- schoolYear / grade（第 2 节）
// 按 UTC+8 取年月：加 8 小时以后的 UTC 年月，月 ≥ 9 取当年，否则取前一年。

test("SLICE_VERBS 认 profile.set", () => {
  assert.ok(SLICE_VERBS.includes("profile.set"));
});

test("schoolYear：9 月 1 日（北京时间）起换学年", () => {
  assert.equal(schoolYear(T("2026-08-31T15:59:59.000Z")), 2025, "北京时间 8 月 31 日 23:59:59");
  assert.equal(schoolYear(T("2026-08-31T16:00:00.000Z")), 2026, "北京时间 9 月 1 日 00:00:00");
  assert.equal(schoolYear(T("2026-11-21T04:00:00.000Z")), 2026, "11 月");
  assert.equal(schoolYear(T("2026-12-31T15:59:59.000Z")), 2026, "北京时间 12 月 31 日 23:59:59");
  assert.equal(schoolYear(T("2026-12-31T16:00:00.000Z")), 2026, "北京时间 2027 年 1 月 1 日：月 < 9，取前一年 2026");
  assert.equal(schoolYear(T("2027-02-01T00:00:00.000Z")), 2026, "2 月仍是 2026 学年");
  assert.equal(schoolYear(T("2027-08-31T15:59:59.000Z")), 2026, "北京时间 2027-08-31 23:59:59");
  assert.equal(schoolYear(T("2027-08-31T16:00:00.000Z")), 2027, "北京时间 2027-09-01 00:00:00");
});

test("grade（entry_year = 2024）：规格第 2 节的例子", () => {
  assert.equal(grade(2024, T("2026-08-31T15:59:59.000Z")), 2, "UTC 15:59:59 仍是 2 年级");
  assert.equal(grade(2024, T("2026-08-31T16:00:00.000Z")), 3, "UTC 16:00:00（北京 9 月 1 日 00:00）是 3 年级");
  assert.equal(grade(2024, T("2026-11-21T04:00:00.000Z")), 3, "2026-11-21 是 3 年级");
  assert.equal(grade(2024, T("2027-08-31T00:00:00.000Z")), 3, "2027-08-31 是 3 年级");
  assert.equal(grade(2024, T("2027-09-01T00:00:00.000Z")), 4, "2027-09-01 是 4 年级");
});

test("grade：越界不截断，原样返回（−8 是还没上小学，17 是已经毕业）", () => {
  assert.equal(grade(2035, T("2026-11-21T04:00:00.000Z")), -8);
  assert.equal(grade(2010, T("2026-11-21T04:00:00.000Z")), 17);
});

test("grade：1 年级和 12 年级的边界", () => {
  assert.equal(grade(2026, T("2026-09-01T00:00:00.000Z")), 1, "入学那年 9 月是 1 年级");
  assert.equal(grade(2026, T("2026-08-31T15:59:59.000Z")), 0, "入学前一天（北京时间 8 月 31 日）是 0：还没上小学");
  assert.equal(grade(2015, T("2026-11-21T04:00:00.000Z")), 12);
  assert.equal(grade(2014, T("2026-11-21T04:00:00.000Z")), 13);
});

test("schoolYear、grade 不读运行机器的时区", () => {
  const before = process.env.TZ;
  try {
    for (const tz of ["UTC", "America/Los_Angeles", "Asia/Tokyo", "Pacific/Kiritimati"]) {
      process.env.TZ = tz;
      assert.equal(grade(2024, T("2026-08-31T15:59:59.000Z")), 2, tz);
      assert.equal(grade(2024, T("2026-08-31T16:00:00.000Z")), 3, tz);
    }
  } finally {
    if (before === undefined) delete process.env.TZ; else process.env.TZ = before;
  }
});

// ---------------------------------------------------------------- projectProfile（第 3 节）
const LRN = "lrn_01JC00000000000000000000K1";
const CG = { type: "caregiver", id: "cg_01JC00000000000000000000G1" };
const dev = (n) => `dev_01JC0000000000000000000D${n}`;
let counter = 0;
/** 一条 profile.set。id 是 evt 的末位标签；默认设备 D1、序号自增。 */
function ps(id, rev, at, extra = {}, tb = { math: "renjiao" }, year = 2024) {
  counter += 1;
  const { device = 1, seq = counter, import_batch } = extra;
  const e = {
    schema: "event/2", event_id: `evt_01JC0000000000000000000${id}`, learner_id: LRN, device_id: dev(device), device_seq: seq,
    occurred_at: at, actor: CG, verb: "profile.set", payload: { rev, entry_year: year, textbooks: tb },
  };
  if (import_batch) e.import_batch = import_batch;
  return e;
}
const shown = (e) => ({ ...e.payload, occurred_at: e.occurred_at });
const EMPTY = { algorithm_version: "profile/1", profile: null, conflicts: [] };
const mentions = (c, id) => JSON.stringify(c).includes(id);

test("空输入：profile 为 null，conflicts 为空", () => {
  assert.deepEqual(projectProfile([]), EMPTY);
});

test("只有别的动词：profile 为 null", () => {
  const other = { schema: "event/2", event_id: "evt_01JC0000000000000000000Q01", learner_id: LRN, device_id: dev(1), device_seq: 1,
    occurred_at: "2026-11-21T03:00:00.000Z", actor: { type: "learner", id: LRN }, verb: "attempt.started",
    attempt_id: "att_01JC00000000000000000000A1", payload: { mode: "first" } };
  assert.deepEqual(projectProfile([other]), EMPTY);
});

test("一条：生效的是它的 payload 加上 occurred_at，没有别的字段", () => {
  const a = ps("P01", 1, "2026-11-21T03:00:00.000Z", {}, { math: "renjiao", science: "jiaoke" });
  assert.deepEqual(projectProfile([a]), {
    algorithm_version: "profile/1",
    profile: { rev: 1, entry_year: 2024, textbooks: { math: "renjiao", science: "jiaoke" }, occurred_at: "2026-11-21T03:00:00.000Z" },
    conflicts: [],
  });
});

test("textbooks 是 {} 也照样生效", () => {
  const a = ps("P01", 1, "2026-11-21T03:00:00.000Z", {}, {});
  assert.deepEqual(projectProfile([a]).profile, { rev: 1, entry_year: 2024, textbooks: {}, occurred_at: "2026-11-21T03:00:00.000Z" });
});

test("rev 优先于时钟：rev 2 的 occurred_at 更早，仍然胜出", () => {
  const old = ps("P01", 1, "2026-11-21T03:00:00.000Z", {}, { math: "renjiao" }, 2024);
  const newer = ps("P02", 2, "2026-11-20T03:00:00.000Z", {}, {}, 2023);
  const r = projectProfile([old, newer]);
  assert.deepEqual(r.profile, { rev: 2, entry_year: 2023, textbooks: {}, occurred_at: "2026-11-20T03:00:00.000Z" });
  assert.deepEqual(r.conflicts, [], "被盖过的低 rev 是正常的历史，不进 conflicts");
});

test("rev 递增 1、2、3：只有 3 生效，conflicts 为空", () => {
  const r = projectProfile([
    ps("P01", 1, "2026-11-01T03:00:00.000Z", {}, {}, 2022),
    ps("P02", 2, "2026-11-02T03:00:00.000Z", {}, {}, 2023),
    ps("P03", 3, "2026-11-03T03:00:00.000Z", {}, {}, 2024),
  ]);
  assert.equal(r.profile.rev, 3);
  assert.equal(r.profile.entry_year, 2024);
  assert.deepEqual(r.conflicts, []);
});

test("同 rev：排序键最大的生效，另一条进 conflicts", () => {
  const early = ps("P01", 2, "2026-11-21T03:00:00.000Z", { device: 1 }, {}, 2023);
  const late = ps("P02", 2, "2026-11-21T03:00:05.000Z", { device: 2 }, {}, 2024);
  for (const input of [[early, late], [late, early]]) {
    const r = projectProfile(input);
    assert.deepEqual(r.profile, shown(late), "occurred_at 较晚的生效");
    assert.equal(r.conflicts.length, 1);
    assert.ok(mentions(r.conflicts[0], "P01"), "落选的 P01 在 conflicts 里");
    assert.ok(!mentions(r.conflicts[0], "P02"), "生效的 P02 不在 conflicts 里");
  }
});

test("同 rev、同 occurred_at：device_id 大的生效", () => {
  const at = "2026-11-21T03:00:00.000Z";
  const d1 = ps("P01", 2, at, { device: 1, seq: 9 }, {}, 2023);
  const d2 = ps("P02", 2, at, { device: 2, seq: 1 }, {}, 2024);
  for (const input of [[d1, d2], [d2, d1]]) {
    const r = projectProfile(input);
    assert.equal(r.profile.entry_year, 2024, "D2 > D1，不看 device_seq");
    assert.equal(r.conflicts.length, 1);
    assert.ok(mentions(r.conflicts[0], "P01"));
  }
});

test("同 rev、同 occurred_at、同设备：device_seq 大的生效；再相同看 event_id", () => {
  const at = "2026-11-21T03:00:00.000Z";
  const s3 = ps("P01", 2, at, { seq: 3 }, {}, 2023);
  const s10 = ps("P02", 2, at, { seq: 10 }, {}, 2024);
  assert.equal(projectProfile([s3, s10]).profile.entry_year, 2024, "device_seq 按整数比：10 > 3（不是字符串比）");
  assert.equal(projectProfile([s10, s3]).profile.entry_year, 2024);
  const a = ps("PAA", 2, at, { seq: 5 }, {}, 2023);
  const b = ps("PBB", 2, at, { seq: 5 }, {}, 2024);
  assert.equal(projectProfile([a, b]).profile.entry_year, 2024, "event_id 大的生效");
  assert.equal(projectProfile([b, a]).profile.entry_year, 2024);
});

test("三条同 rev 加一条低 rev：落选的两条进 conflicts，低 rev 不进", () => {
  const low = ps("P01", 1, "2026-11-30T03:00:00.000Z", {}, {}, 2020);
  const a = ps("P02", 2, "2026-11-21T03:00:01.000Z", { device: 1 }, {}, 2021);
  const b = ps("P03", 2, "2026-11-21T03:00:02.000Z", { device: 2 }, {}, 2022);
  const c = ps("P04", 2, "2026-11-21T03:00:03.000Z", { device: 3 }, {}, 2023);
  const r = projectProfile([c, low, a, b]);
  assert.equal(r.profile.entry_year, 2023);
  assert.equal(r.conflicts.length, 2);
  const text = JSON.stringify(r.conflicts);
  assert.ok(text.includes("P02") && text.includes("P03"));
  assert.ok(!text.includes("P01") && !text.includes("P04"));
});

test("输入顺序打乱，结果完全相同", () => {
  const evs = [
    ps("P01", 1, "2026-11-01T03:00:00.000Z", {}, {}, 2022),
    ps("P02", 2, "2026-11-02T03:00:00.000Z", { device: 1 }, { math: "renjiao" }, 2023),
    ps("P03", 3, "2026-11-01T01:00:00.000Z", { device: 1 }, { science: "jiaoke" }, 2024),
    ps("P04", 3, "2026-11-01T01:00:00.000Z", { device: 2 }, { math: "renjiao", science: "jiaoke" }, 2025),
    ps("P05", 3, "2026-10-01T01:00:00.000Z", { device: 3 }, {}, 2026),
  ];
  const expected = {
    algorithm_version: "profile/1",
    profile: { rev: 3, entry_year: 2025, textbooks: { math: "renjiao", science: "jiaoke" }, occurred_at: "2026-11-01T01:00:00.000Z" },
  };
  let state = 12345;
  const rnd = () => ((state = (Math.imul(state, 1103515245) + 12345) >>> 0) / 4294967296);
  const orders = [evs, [...evs].reverse()];
  for (let k = 0; k < 20; k++) {
    const a = [...evs];
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    orders.push(a);
  }
  for (const input of orders) {
    const r = projectProfile(input);
    assert.equal(r.algorithm_version, expected.algorithm_version);
    assert.deepEqual(r.profile, expected.profile);
    assert.equal(r.conflicts.length, 2, "rev 3 里落选的 P03、P05");
    const text = JSON.stringify(r.conflicts);
    assert.ok(text.includes("P03") && text.includes("P05"));
    assert.ok(!text.includes("P01") && !text.includes("P02") && !text.includes("P04"));
  }
});

test("被 import.voided 作废的批次里的 profile.set 不算（第 3 节：输入照 6.1）", () => {
  // 约定：projectProfile 收「已接收的事件」，自己按 6.1 第 2 条去掉被输入里的 import.voided 作废的 import_batch；
  // 输入里没有 import.voided 时等于什么都不去掉（已经过滤过的输入也能直接用）。
  const BATCH = "imp_01JC00000000000000000000B1";
  const real = ps("P01", 2, "2026-11-10T03:00:00.000Z", {}, { math: "renjiao" }, 2024);
  const imported = ps("P02", 5, "2026-11-11T03:00:00.000Z", { import_batch: BATCH }, {}, 2020);
  const voided = {
    schema: "event/2", event_id: "evt_01JC0000000000000000000V01", learner_id: LRN, device_id: dev(1), device_seq: 99,
    occurred_at: "2026-11-12T03:00:00.000Z", actor: CG, verb: "import.voided", payload: { batch_id: BATCH, reason: "bad_data" },
  };
  assert.equal(projectProfile([real, imported]).profile.rev, 5, "没作废时 rev 5 生效");
  const r = projectProfile([real, imported, voided]);
  assert.deepEqual(r.profile, shown(real), "作废以后 rev 2 生效");
  assert.deepEqual(r.conflicts, []);
  assert.deepEqual(projectProfile([voided, imported, real]), r, "顺序无关");
  assert.deepEqual(projectProfile([imported, voided]), EMPTY, "只剩被作废的：没有资料");
  const sameRev = ps("P03", 2, "2026-11-20T03:00:00.000Z", { import_batch: BATCH }, {}, 2019);
  assert.deepEqual(projectProfile([real, sameRev, voided]).conflicts, [], "被作废批次里的同 rev 事件不进 conflicts");
});

test("不改传进来的数组和事件", () => {
  const evs = [ps("P01", 2, "2026-11-02T03:00:00.000Z"), ps("P02", 1, "2026-11-03T03:00:00.000Z")];
  const copy = structuredClone(evs);
  projectProfile(evs);
  assert.deepEqual(evs, copy);
});
