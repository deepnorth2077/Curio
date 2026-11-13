// 实现者补的测试：first / retry 按孩子算（docs/specs/backup.md 第 11 节），和家长页的几个纯函数（第 8、10 节）。
import { test } from "node:test";
import assert from "node:assert/strict";
import { createLog } from "../../kernel/js/log.js";
import { completedBefore } from "../app.js";
import { isClean, lastBackupText, needsDot, formatFingerprint } from "../parent.js";
import { CONTENT_V1 } from "./fake-store.js";

const body = (n) => "01JC" + String(n).padStart(22, "0");
const LRN = "lrn_" + body(1), OTHER = "lrn_" + body(2);
const DEV_A = "dev_" + body(3), DEV_B = "dev_" + body(4);
let n = 100;

/** 一次尝试的事件。ends：completed / abandoned / none。 */
function attempt({ learner = LRN, device = DEV_A, seq, ends = "completed", content = CONTENT_V1, actor }) {
  const att = "att_" + body(++n);
  const ev = (verb, s, payload, a) => JSON.stringify({
    schema: "event/2", event_id: "evt_" + body(++n), learner_id: learner, device_id: device, device_seq: s,
    occurred_at: "2026-11-13T10:00:00.000Z", actor: a ?? { type: "learner", id: learner }, verb, attempt_id: att, content, payload,
  });
  const out = [ev("attempt.started", seq, { mode: "first" }, actor)];
  if (ends === "completed") out.push(ev("attempt.completed", seq + 1, { duration_ms: 5 }));
  if (ends === "abandoned") out.push(ev("attempt.abandoned", seq + 1, { reason: "left" }, { type: "system", id: "sys:shell" }));
  return out;
}
const events = (...raws) => { const log = createLog(); for (const r of raws.flat()) log.ingest(r); return log.events(); };
const ACT = CONTENT_V1.activity_id;

test("另一台设备上完成过（同一个孩子）→ retry", () => {
  assert.equal(completedBefore(events(attempt({ device: DEV_B, seq: 1 })), LRN, ACT), true);
});
test("这台设备上完成过 → retry", () => {
  assert.equal(completedBefore(events(attempt({ seq: 1 })), LRN, ACT), true);
});
test("反例：从没做过 → first", () => {
  assert.equal(completedBefore(events(), LRN, ACT), false);
});
test("反例：只有被放弃的、没结束的 → first", () => {
  assert.equal(completedBefore(events(attempt({ seq: 1, ends: "abandoned" }), attempt({ seq: 3, ends: "none" })), LRN, ACT), false);
});
test("反例：完成的是别的活动 → first", () => {
  assert.equal(completedBefore(events(attempt({ seq: 1, content: { ...CONTENT_V1, activity_id: "act.quiz.other-01" } })), LRN, ACT), false);
});
test("反例：完成的是别的孩子 → first", () => {
  assert.equal(completedBefore(events(attempt({ learner: OTHER, seq: 1 })), LRN, ACT), false);
});
test("反例：被判不一致的尝试（started 的 actor 不是孩子本人，规则 2）不算 → first", () => {
  const evs = events(attempt({ seq: 1, actor: { type: "learner", id: OTHER } }));
  assert.equal(evs.length, 2, "两条都被接收（不一致是掌握度投影判的，不是隔离）");
  assert.equal(completedBefore(evs, LRN, ACT), false);
});

const empty = { inbox: [], receipts: [], imports: [], archive: [], restoring: null };
test("干净：四个仓库都空、没有 restoring；任何一样不空或有标记就不干净", () => {
  assert.equal(isClean(empty), true);
  assert.equal(isClean({ ...empty, inbox: ["x"] }), false);
  assert.equal(isClean({ ...empty, archive: [{ kind: "receipt", v: {} }] }), false);
  assert.equal(isClean({ ...empty, imports: [{}] }), false);
  assert.equal(isClean({ ...empty, restoring: { batch_id: "imp_x" } }), false);
});

test("上次备份的说法；超过 30 天醒目", () => {
  const now = Date.parse("2026-11-14T12:00:00.000Z");
  assert.deepEqual(lastBackupText(null, now), { text: "还没有备份", loud: true });
  assert.deepEqual(lastBackupText({ at: "2026-11-14T08:00:00.000Z" }, now), { text: "今天", loud: false });
  assert.deepEqual(lastBackupText({ at: "2026-11-11T12:00:00.000Z" }, now), { text: "3 天前", loud: false });
  assert.deepEqual(lastBackupText({ at: "2026-10-13T11:00:00.000Z" }, now), { text: "32 天前", loud: true });
});

test("入口的小圆点：超过 30 天没备份才有；干净的设备没有", () => {
  const now = Date.parse("2026-11-14T12:00:00.000Z");
  assert.equal(needsDot({ clean: false, lastBackup: { at: "2026-11-01T00:00:00.000Z" }, firstEventAt: "2026-01-01T00:00:00.000Z" }, now), false);
  assert.equal(needsDot({ clean: false, lastBackup: { at: "2026-10-01T00:00:00.000Z" }, firstEventAt: null }, now), true);
  assert.equal(needsDot({ clean: false, lastBackup: null, firstEventAt: "2026-11-10T00:00:00.000Z" }, now), false);
  assert.equal(needsDot({ clean: false, lastBackup: null, firstEventAt: "2026-10-01T00:00:00.000Z" }, now), true);
  assert.equal(needsDot({ clean: true, lastBackup: null, firstEventAt: null }, now), false);
});

test("指纹两组显示", () => { assert.equal(formatFingerprint("3fa9c021"), "3fa9 c021"); });
