// 实现者补的测试：first / retry 按孩子算（docs/specs/backup.md 第 11 节），和家长页的几个纯函数（第 8、10 节）。
import { test } from "node:test";
import assert from "node:assert/strict";
import { createLog } from "../../kernel/js/log.js";
import { nodeProgress } from "../starchart.js";
import { stationCount } from "../exploration.js";
import { completedBefore, explorationProgress } from "../app.js";
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

const LIFE = { ...CONTENT_V1, node_id: "biology.cell.cell-intro", activity_kind: "simulation",
  activity_id: "act.simulation.cell-zoom-01", activity_version: 2 };

test("旧探索只有整次完成记录：同一个孩子在另一台设备也可以重玩全部四站；别的孩子没有进度", () => {
  const history = events(attempt({device:DEV_B, content:LIFE, seq:1}));
  assert.deepEqual(explorationProgress(history, LRN, LIFE.activity_id),
    {doneStations:[1, 2, 3, 4], activityCompleted:true});
  assert.deepEqual(explorationProgress(history, OTHER, LIFE.activity_id),
    {doneStations:[], activityCompleted:false});
  assert.deepEqual(explorationProgress(history, LRN, "act.simulation.dna-book-01"),
    {doneStations:[], activityCompleted:false});
});

// docs/specs/navigators.md 第 6 节：进度按活动 id 重建，不按 activity_version 过滤
test("模块版本加 1 以后，旧版本做过的站在新版本里仍算；整次完成过的仍算拿过星卡", () => {
  const MATH = { ...LIFE, node_id: "math.fraction.unit-fraction", activity_id: "act.simulation.fair-cut-01", activity_version: 1 };
  const [start, end] = attempt({content:MATH, seq:1, ends:"abandoned"});
  const observed = (value, seq) => JSON.stringify({...JSON.parse(start), verb:"sim.observed", event_id:"evt_" + body(++n), device_seq:seq,
    payload:{observable:"station.completed", value}});
  const v1 = events(start, observed(1, 2), observed(2, 3), JSON.stringify({...JSON.parse(end), device_seq:4}));
  // 外壳现在装的是第 2 版：调用方不再传版本，第 1 版的两站照样回来
  assert.deepEqual(explorationProgress(v1, LRN, MATH.activity_id), {doneStations:[1, 2], activityCompleted:false});
  const done = events(attempt({content:{...MATH, activity_version: 1}, seq:1}));
  assert.deepEqual(explorationProgress(done, LRN, MATH.activity_id), {doneStations:[1, 2, 3], activityCompleted:true});
  // 新旧两版混在一起：取并集
  const v2start = attempt({content:{...MATH, activity_version: 2}, seq:10, ends:"abandoned"});
  const v2obs = JSON.stringify({...JSON.parse(v2start[0]), verb:"sim.observed", event_id:"evt_" + body(++n), device_seq:11, payload:{observable:"station.completed", value:3}});
  const mixed = events(start, observed(1, 2), JSON.stringify({...JSON.parse(end), device_seq:4}), v2start[0], v2obs, JSON.stringify({...JSON.parse(v2start[1]), device_seq:12}));
  assert.deepEqual(explorationProgress(mixed, LRN, MATH.activity_id), {doneStations:[1, 3], activityCompleted:false});
});

test("站号超出当前模块站数的不算（旧版本站多、新版本站少时也一样）", () => {
  const MATH = { ...LIFE, node_id: "math.fraction.unit-fraction", activity_id: "act.simulation.fair-cut-01", activity_version: 1 };
  const [start, end] = attempt({content:MATH, seq:1, ends:"abandoned"});
  const observed = (value, seq) => JSON.stringify({...JSON.parse(start), verb:"sim.observed", event_id:"evt_" + body(++n), device_seq:seq,
    payload:{observable:"station.completed", value}});
  const history = events(start, observed(2, 2), observed(4, 3), observed(9, 4), JSON.stringify({...JSON.parse(end), device_seq:5}));
  assert.deepEqual(explorationProgress(history, LRN, MATH.activity_id), {doneStations:[2], activityCompleted:false});
});

test("中途退出沿用保存的站；不一致的完成记录不会解锁其余站", () => {
  const [start, end] = attempt({content:LIFE, seq:1, ends:"abandoned"});
  const observation = {...JSON.parse(start), verb:"sim.observed", event_id:"evt_" + body(++n), device_seq:2,
    payload:{observable:"station.completed", value:1}};
  const history = events(start, JSON.stringify(observation), JSON.stringify({...JSON.parse(end), device_seq:3}),
    attempt({content:LIFE, seq:4, actor:{type:"learner", id:OTHER}}));
  assert.deepEqual(explorationProgress(history, LRN, LIFE.activity_id),
    {doneStations:[1], activityCompleted:false});
});

test("三站的数学探索：整次完成给出三站，站号超过三的记录不算", () => {
  const MATH = { ...LIFE, node_id: "math.fraction.unit-fraction", activity_id: "act.simulation.fair-cut-01", activity_version: 1 };
  assert.deepEqual(explorationProgress(events(attempt({content:MATH, seq:1})), LRN, MATH.activity_id),
    {doneStations:[1, 2, 3], activityCompleted:true});
  const [start, end] = attempt({content:MATH, seq:1, ends:"abandoned"});
  const observed = (value, seq) => JSON.stringify({...JSON.parse(start), verb:"sim.observed", event_id:"evt_" + body(++n), device_seq:seq,
    payload:{observable:"station.completed", value}});
  const history = events(start, observed(1, 2), observed(4, 3), JSON.stringify({...JSON.parse(end), device_seq:4}));
  assert.deepEqual(explorationProgress(history, LRN, MATH.activity_id), {doneStations:[1], activityCompleted:false});
});

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

test("resume and chart project old station observations against the selected verified release", () => {
  const id = "act.simulation.five-stations";
  const sim = { ...LIFE, activity_id: id };
  const [start, end] = attempt({ content: sim, seq: 1, ends: "abandoned" });
  const observed = JSON.stringify({ ...JSON.parse(start), verb: "sim.observed", event_id: "evt_" + body(++n),
    device_seq: 2, payload: { observable: "station.completed", value: 5 } });
  const history = events(start, observed, JSON.stringify({ ...JSON.parse(end), device_seq: 3 }));
  const five = { id, contract: "activity/1.2", kit: 1, type: "simulation", pedagogy: "explain", emits: ["observed"], station_count: 5 };
  const [returnStart, returnEnd] = attempt({ content: sim, seq: 4, ends: "abandoned" });
  const again = JSON.stringify({ ...JSON.parse(returnStart), verb: "sim.observed", event_id: "evt_" + body(++n),
    device_seq: 5, payload: { observable: "station.completed", value: 4 } });
  const visits = [...history, ...events(returnStart, again, JSON.stringify({ ...JSON.parse(returnEnd), device_seq: 6 }))];
  assert.deepEqual(explorationProgress(visits, LRN, id, five).doneStations, [4, 5]);
  assert.equal(nodeProgress(visits, null, (key) => stationCount(key, five))[sim.node_id], 2 / 5);
  const four = { ...five, station_count: 4 };
  assert.deepEqual(explorationProgress(history, LRN, id, five), { doneStations: [5], activityCompleted: false });
  assert.equal(nodeProgress(history, null, (key) => stationCount(key, five))[sim.node_id], 1 / 5);
  assert.deepEqual(explorationProgress(history, LRN, id, four), { doneStations: [], activityCompleted: false });
  assert.equal(nodeProgress(history, null, (key) => stationCount(key, four))[sim.node_id], 0);
  assert.deepEqual(explorationProgress(events(attempt({ content: sim, seq: 1 })), LRN, id, five),
    { doneStations: [1, 2, 3, 4, 5], activityCompleted: true });
});
