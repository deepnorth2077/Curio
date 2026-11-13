// 竖切片 6a 的验收测试：app/restore.js（docs/specs/backup.md 6.1～6.3、2.3，接口见 docs/specs/backup-api.md）。
// 验收测试的作者写，实现者不改（受保护路径）。planRestore 的期望值来自 app/vectors/backup-restore.json
// （tools/backup_ref.py 的 plan_restore 和手算，每条写了 why）；runRestore、abandonRestore 用 fake-backup-store.js 测。
// 跑法：node --test app/test/restore.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { planRestore, runRestore, abandonRestore } from "../restore.js";
import { fingerprint } from "../backup.js";
import { createLog } from "../../kernel/js/log.js";
import { createFakeBackupStore } from "./fake-backup-store.js";

const here = dirname(fileURLToPath(import.meta.url));
const V = JSON.parse(readFileSync(join(here, "..", "vectors", "backup-restore.json"), "utf8"));
const CASES = Object.fromEntries(V.cases.map((c) => [c.name, c]));
const plain = (v) => JSON.parse(JSON.stringify(v));
const never = () => false;

/** 计划和向量比：batches 先核对正好是 items 每 500 项切开，再换成 {count, ownSeqMax} 比。 */
function checkPlan(plan, c) {
  if (!c.expect.ok) {
    assert.deepEqual(plain(plan), c.expect, `${c.name}：${c.why}`);
    return;
  }
  assert.equal(plan.ok, true, `${c.name}：${c.why}；实际 ${JSON.stringify(plan).slice(0, 200)}`);
  const flat = plan.batches.flatMap((b) => b.items);
  assert.deepEqual(plain(flat), plain(plan.items), `${c.name}：batches 接起来就是 items`);
  plan.batches.forEach((b, i) => assert.ok(b.items.length === 500 || i === plan.batches.length - 1, `${c.name}：除最后一批外每批 500 项`));
  const got = plain({ ...plan, batches: plan.batches.map((b) => ({ count: b.items.length, ownSeqMax: b.ownSeqMax })) });
  for (const k of Object.keys(c.expect)) assert.deepEqual(got[k], c.expect[k], `${c.name} 的 ${k}：${c.why}`);
  assert.deepEqual(Object.keys(got).sort(), Object.keys(c.expect).sort(), `${c.name}：返回的字段正好是 backup-api.md 列的`);
}

// ---------------------------------------------------------------- planRestore
for (const c of V.cases) {
  test(`planRestore：${c.name}`, () => {
    const existing = structuredClone(c.existing);
    const backup = structuredClone(c.backup);
    const plan = planRestore(existing, backup, structuredClone(c.opts));
    assert.ok(!(plan instanceof Promise), "planRestore 是同步函数");
    assert.deepEqual(existing, c.existing, "planRestore 不改 existing");
    assert.deepEqual(backup, c.backup, "planRestore 不改 backup");
    checkPlan(plan, c);
  });
}

test("planRestore 是纯函数：同样的输入两次结果相同", () => {
  const c = CASES.clean_device;
  assert.deepEqual(plain(planRestore(structuredClone(c.existing), structuredClone(c.backup), c.opts)),
    plain(planRestore(structuredClone(c.existing), structuredClone(c.backup), c.opts)));
});

// ---------------------------------------------------------------- runRestore + 假存储：和向量的 after 一样
for (const c of V.cases.filter((x) => x.expect.ok)) {
  test(`runRestore 写完：${c.name}，存储等于向量的 after，重放后的日志和指纹对`, async () => {
    const store = createFakeBackupStore(structuredClone(c.existing));
    const plan = planRestore(await store.snapshot(), structuredClone(c.backup), c.opts);
    const r = await runRestore(store, plan, { lockLost: never });
    assert.deepEqual(plain(r), { ok: true });
    assert.deepEqual(store.dump(), c.after, `${c.name}：${c.why}`);
    const log = createLog();
    for (const raw of store.state.inbox) log.ingest(raw);
    assert.deepEqual(log.events().map((e) => e.event_id), c.log_after.accepted);
    assert.equal(log.quarantined().length, c.log_after.quarantined);
    assert.equal(await fingerprint(log.events().map((e) => e.event_id)), c.fingerprint_after);
    const begins = store.log.filter((x) => x.m === "restoreBegin");
    assert.equal(begins.length, 1, "restoreBegin 一次");
    assert.equal(store.log.at(-1).m, "restoreEnd", "最后是 restoreEnd");
    assert.equal(store.calls.restoreBatch ?? 0, c.expect.batches.length, "每批一次 restoreBatch");
  });
}

test("runRestore：restoreBegin 带上标记；换身份、写密钥只在需要时（2.3、5.2）", async () => {
  for (const name of ["clean_device", "same_learner_clean", "key_confirmed_same", "key_confirmed_other", "key_unconfirmed"]) {
    const c = CASES[name];
    const store = createFakeBackupStore(structuredClone(c.existing));
    const plan = planRestore(await store.snapshot(), structuredClone(c.backup), c.opts);
    await runRestore(store, plan, { lockLost: never });
    const [marker, identity, key] = store.log.find((x) => x.m === "restoreBegin").args;
    assert.deepEqual(marker, c.expect.marker, `${name}：标记`);
    assert.deepEqual(identity, c.expect.changeIdentity ? c.expect.identity : null, `${name}：要换身份时才带身份`);
    assert.deepEqual(key, c.expect.recoveryKey, `${name}：要写密钥时才带密钥`);
  }
});

// ---------------------------------------------------------------- 多批：生成的大备份
const ulid = (tag) => "01JC4Y" + String(tag).padStart(20, "0");
const L = "lrn_" + ulid("A");
const DEV_B = "dev_" + ulid("B");
const DEV_R = "dev_" + ulid("R");
const REL = "rel_" + "a".repeat(64);
const CONTENT = { node_id: "math.number.fraction-intro", activity_id: "act.quiz.fraction-intro-01", activity_kind: "quiz", activity_version: 1, content_release: REL };
const HEADER = CASES.clean_device.backup.header;

/** device 上序号 from..to 的 attempt.started，每条一个尝试。tag 让 ID 不撞。 */
function events(device, tag, from, to, learner = L) {
  const out = [];
  for (let s = from; s <= to; s++) {
    out.push(JSON.stringify({
      schema: "event/2", event_id: `evt_${ulid(`${tag}${s}`)}`, learner_id: learner, device_id: device, device_seq: s,
      occurred_at: "2026-11-12T03:00:00.000Z", actor: { type: "learner", id: learner }, verb: "attempt.started",
      attempt_id: `att_${ulid(`${tag}${s}`)}`, content: CONTENT, payload: { mode: "first" },
    }));
  }
  return out;
}
const localReceipt = (raw) => ({ event_id: JSON.parse(raw).event_id, recorded_at: "2026-11-12T03:00:00.500Z", source: "local" });

function backupOf(device, inbox, receipts = []) {
  const backup = {
    manifest: { schema: "backup-manifest/1", created_at: HEADER.created_at, learner_id: L, device_id: device, app_commit: "275c460",
      counts: { inbox: inbox.length, receipt: receipts.length, import: 0, archive: 0, release: 0 } },
    inbox, receipt: receipts.slice().sort((a, b) => (a.event_id < b.event_id ? -1 : 1)), import: [], archive: [], release: [],
  };
  return { header: HEADER, backup };
}
const cleanDevice = () => ({ identity: { learner_id: "lrn_" + ulid("R1"), device_id: DEV_R }, nextSeq: 1, inbox: [], receipts: [], imports: [], archive: [], releases: [], recoveryKey: null, restoring: null });

// 700 条 B 的事件 + 700 条收据：items 1400 项，分成 500、500、400
const BIG_INBOX = events(DEV_B, "G", 1, 700);
const BIG = backupOf(DEV_B, BIG_INBOX, BIG_INBOX.map(localReceipt));
const OPTS = { batchId: "imp_" + ulid("P1"), now: "2026-11-14T03:00:00.000Z", inputKey: "123456" };

test("分批（5.2、6.3）：每 500 项一批，最后一批是余数；原文和收据在同一项里", async () => {
  const plan = planRestore(cleanDevice(), structuredClone(BIG), OPTS);
  assert.equal(plan.ok, true);
  assert.equal(plan.items.length, 1400);
  assert.deepEqual(plan.batches.map((b) => b.items.length), [500, 500, 400]);
  assert.deepEqual(plan.batches.map((b) => b.ownSeqMax), [0, 0, 0], "没有本机 R 的事件");
  for (const it of plan.items.slice(0, 700)) {
    assert.equal(it.receipt.event_id, JSON.parse(it.inbox).event_id, "收据跟着它的原文");
    assert.deepEqual(plain(it.receipt), { event_id: JSON.parse(it.inbox).event_id, recorded_at: OPTS.now, source: "import", batch_id: OPTS.batchId });
  }
  assert.ok(plan.items.slice(700).every((it) => it.archive && it.archive.kind === "receipt"), "后 700 项是带过来的收据");
  const store = createFakeBackupStore(cleanDevice());
  await runRestore(store, plan, { lockLost: never });
  const sizes = store.log.filter((x) => x.m === "restoreBatch").map((x) => x.args[0].length);
  assert.deepEqual(sizes, [500, 500, 400]);
});

test("每个事务之前检查一次写锁（6.3 第 3 步）", async () => {
  const plan = planRestore(cleanDevice(), structuredClone(BIG), OPTS);
  const store = createFakeBackupStore(cleanDevice());
  const order = [];
  const origLog = store.log;
  const lockLost = () => { order.push(`check@${origLog.length}`); return false; };
  await runRestore(store, plan, { lockLost });
  // 每个写方法调用之前，最近一次检查时已写入的调用数正好是它之前的调用数
  const writes = store.log.map((x) => x.m);
  assert.deepEqual(writes, ["restoreBegin", "restoreBatch", "restoreBatch", "restoreBatch", "restoreEnd"]);
  for (let i = 0; i < writes.length; i++) assert.ok(order.includes(`check@${i}`), `第 ${i + 1} 个事务（${writes[i]}）之前查过写锁`);
});

test("写到第 2 批失败，再恢复一次：沿用同一个 batch_id，最后的存储和一次写完一样，restoring 被删掉（规格测试表）", async () => {
  // 一次写完
  const once = createFakeBackupStore(cleanDevice());
  const p1 = planRestore(await once.snapshot(), structuredClone(BIG), OPTS);
  assert.deepEqual(plain(await runRestore(once, p1, { lockLost: never })), { ok: true });
  // 第 2 批失败
  const s = createFakeBackupStore(cleanDevice());
  const pa = planRestore(await s.snapshot(), structuredClone(BIG), OPTS);
  s.failOn.restoreBatch = 2;
  const ra = await runRestore(s, pa, { lockLost: never });
  assert.deepEqual(plain(ra), { ok: false, error: "store_failed", wrote: 1 });
  assert.ok(s.state.restoring, "失败以后标记还在");
  assert.equal(s.state.restoring.batch_id, OPTS.batchId);
  assert.equal(s.state.inbox.length, 500, "第 1 批写进去了");
  assert.equal(s.state.receipts.size, 500, "原文和收据成对");
  assert.deepEqual(s.state.identity, { learner_id: L, device_id: DEV_R }, "身份在 restoreBegin 时已经换了");
  assert.deepEqual(s.state.recoveryKey, { digits: "123456", confirmed_at: OPTS.now }, "密钥在 restoreBegin 时已经写了（2.3）");
  assert.equal(s.calls.restoreEnd ?? 0, 0);
  // 重新打开，再恢复一次：参数里给另一个 batchId，也要用标记里的
  const pb = planRestore(await s.snapshot(), structuredClone(BIG), { ...OPTS, batchId: "imp_" + ulid("P9") });
  assert.equal(pb.ok, true);
  assert.equal(pb.batchId, OPTS.batchId, "沿用标记里的 batch_id");
  assert.equal(pb.record.batch_id, OPTS.batchId);
  assert.deepEqual([pb.record.accepted, pb.record.duplicate, pb.record.archived], [200, 500, 700], "已经写进去的 500 条算重复，剩下的补上");
  assert.deepEqual(plain(await runRestore(s, pb, { lockLost: never })), { ok: true });
  assert.equal(s.state.restoring, null, "标记删掉了");
  const a = once.dump();
  const b = s.dump();
  // 导入记录的计数按规格 6.3 记的是第二次的（重复 500），其余字段相同；存储的其余部分完全相同
  const COUNTS = ["accepted", "duplicate", "not_yet_known", "quarantined_new", "quarantined_skipped", "archived", "releases"];
  const strip = (d) => ({ ...d, imports: d.imports.map((r) => Object.fromEntries(Object.entries(r).filter(([k]) => !COUNTS.includes(k)))) });
  assert.deepEqual(strip(b), strip(a));
  assert.equal(b.imports.length, 1, "只有一条导入记录");
});

test("写到第 2 批失败，点「不恢复了」：一条 partial 的导入记录，标记没了，本机有这把密钥，能照常写（规格测试表）", async () => {
  const s = createFakeBackupStore(cleanDevice());
  const p = planRestore(await s.snapshot(), structuredClone(BIG), OPTS);
  s.failOn.restoreBatch = 2;
  await runRestore(s, p, { lockLost: never });
  const existing = await s.snapshot();
  const now = "2026-11-14T05:00:00.000Z";
  assert.deepEqual(plain(await abandonRestore(s, existing, { now })), { ok: true });
  assert.equal(s.state.restoring, null);
  const recs = [...s.state.imports.values()];
  assert.deepEqual(recs, [{
    schema: "import-record/1", batch_id: OPTS.batchId, imported_at: now, source: "backup", partial: true,
    file_created_at: HEADER.created_at, file_device_id: DEV_B, file_salt: HEADER.salt,
    accepted: 0, duplicate: 0, not_yet_known: 0, quarantined_new: 0, quarantined_skipped: 0, archived: 0, releases: 0,
  }], "backup-api.md：用标记里的 batch_id 写 partial:true 的导入记录，计数全为 0；字段按 5.3");
  assert.deepEqual(Object.keys(recs[0]), ["schema", "batch_id", "imported_at", "source", "partial", "file_created_at", "file_device_id",
    "file_salt", "accepted", "duplicate", "not_yet_known", "quarantined_new", "quarantined_skipped", "archived", "releases"], "字段顺序按 5.3");
  assert.deepEqual(s.state.recoveryKey, { digits: "123456", confirmed_at: OPTS.now }, "放弃以后本机也有这把（2.3）");
  assert.equal(s.state.inbox.length, 500, "写进去的留着");
  const raw = events(DEV_R, "W", s.state.nextSeq, s.state.nextSeq)[0];
  await s.commit(raw, localReceipt(raw));
  assert.equal(s.state.inbox.at(-1), raw, "放弃以后照常写");
});

test("abandonRestore：存储失败时 store_failed", async () => {
  const s = createFakeBackupStore(cleanDevice());
  const p = planRestore(await s.snapshot(), structuredClone(BIG), OPTS);
  s.failOn.restoreBatch = 1;
  await runRestore(s, p, { lockLost: never });
  s.failOn.restoreAbandon = 1;
  assert.deepEqual(plain(await abandonRestore(s, await s.snapshot(), { now: OPTS.now })), { ok: false, error: "store_failed" });
  assert.ok(s.state.restoring, "没放弃成，标记还在");
});

test("写到一半失去写锁：不再写下一批，标记留着（规格测试表）", async () => {
  const s = createFakeBackupStore(cleanDevice());
  const p = planRestore(await s.snapshot(), structuredClone(BIG), OPTS);
  const r = await runRestore(s, p, { lockLost: () => (s.calls.restoreBatch ?? 0) >= 1 });
  assert.deepEqual(plain(r), { ok: false, error: "lock_lost", wrote: 1 });
  assert.equal(s.calls.restoreBatch, 1);
  assert.equal(s.calls.restoreEnd ?? 0, 0);
  assert.ok(s.state.restoring);
});

test("一开始就没有写锁：什么都不写", async () => {
  const s = createFakeBackupStore(cleanDevice());
  const before = s.dump();
  const p = planRestore(await s.snapshot(), structuredClone(BIG), OPTS);
  assert.deepEqual(plain(await runRestore(s, p, { lockLost: () => true })), { ok: false, error: "lock_lost", wrote: 0 });
  assert.deepEqual(s.dump(), before);
  assert.equal(s.log.length, 0);
});

test("最后一步之前失去写锁：批次都写了，restoreEnd 不写，标记留着", async () => {
  const s = createFakeBackupStore(cleanDevice());
  const p = planRestore(await s.snapshot(), structuredClone(BIG), OPTS);
  const r = await runRestore(s, p, { lockLost: () => (s.calls.restoreBatch ?? 0) >= 3 });
  assert.deepEqual(plain(r), { ok: false, error: "lock_lost", wrote: 3 });
  assert.ok(s.state.restoring);
});

test("restoreBegin 失败：store_failed，存储一点没动", async () => {
  const s = createFakeBackupStore(cleanDevice());
  const before = s.dump();
  const p = planRestore(await s.snapshot(), structuredClone(BIG), OPTS);
  s.failOn.restoreBegin = 1;
  assert.deepEqual(plain(await runRestore(s, p, { lockLost: never })), { ok: false, error: "store_failed", wrote: 0 });
  assert.deepEqual(s.dump(), before);
});

test("restoreEnd 失败：store_failed，wrote 是全部批数，标记留着", async () => {
  const s = createFakeBackupStore(cleanDevice());
  const p = planRestore(await s.snapshot(), structuredClone(BIG), OPTS);
  s.failOn.restoreEnd = 1;
  assert.deepEqual(plain(await runRestore(s, p, { lockLost: never })), { ok: false, error: "store_failed", wrote: 3 });
  assert.ok(s.state.restoring);
});

test("被拒绝的恢复不碰存储：别的孩子（6.1）", async () => {
  for (const name of ["other_learner_with_records", "restoring_other_child", "restoring_other_file_salt"]) {
    const c = CASES[name];
    const s = createFakeBackupStore(structuredClone(c.existing));
    const before = s.dump();
    const p = planRestore(await s.snapshot(), structuredClone(c.backup), c.opts);
    assert.equal(p.ok, false, name);
    assert.deepEqual(s.dump(), before, `${name}：存储不变`);
    assert.equal(s.log.length, 0);
  }
});

test("备份里有本机 1～4、本机 nextSeq 3，写完第一批断掉，重新打开：存储里的 nextSeq 已经是 5，补写的放弃用序号 5 不冲突（规格测试表）", async () => {
  const own = CASES.own_seq_rollback;
  const b14 = own.backup.backup.inbox;            // 设备 B 的 1～4（同一个尝试 T1，没结束）
  const filler = events("dev_" + ulid("E"), "F", 1, 600);
  const backup = { header: own.backup.header, backup: { ...structuredClone(own.backup.backup), inbox: [...b14, ...filler],
    manifest: { ...own.backup.backup.manifest, counts: { ...own.backup.backup.manifest.counts, inbox: 604 } } } };
  const s = createFakeBackupStore(structuredClone(own.existing));
  const plan = planRestore(await s.snapshot(), structuredClone(backup), OPTS);
  assert.equal(plan.ok, true);
  assert.equal(plan.nextSeq, 5);
  assert.equal(plan.report.ownEarlier, true);
  assert.deepEqual(plan.batches.map((b) => [b.items.length, b.ownSeqMax]), [[500, 4], [104, 0]], "B3、B4 在第一批，ownSeqMax 4；第二批 600-498 条 + 2 条带过来的收据");
  assert.deepEqual(plan.items.slice(0, 2).map((i) => i.own_seq), [3, 4]);
  assert.ok(plan.items.slice(2).every((i) => i.own_seq === undefined), "别的设备的事件不标 own_seq");
  s.failOn.restoreBatch = 2;
  const r = await runRestore(s, plan, { lockLost: never });
  assert.deepEqual(plain(r), { ok: false, error: "store_failed", wrote: 1 });
  const batchCalls = s.log.filter((x) => x.m === "restoreBatch");
  assert.equal(batchCalls[0].args[1], 4, "restoreBatch 收到这一批的 ownSeqMax");
  assert.equal(s.state.nextSeq, 5, "第一批写完，nextSeq 已经推进到 5（5.2）");
  // 重新打开：补写本机没结束的尝试 T1 的放弃，用序号 5
  const log = createLog();
  for (const raw of s.state.inbox) log.ingest(raw);
  const t1 = JSON.parse(b14[0]);
  const abandoned = JSON.stringify({ ...t1, event_id: "evt_" + ulid("AB5"), device_seq: s.state.nextSeq, occurred_at: "2026-11-14T06:00:00.000Z",
    verb: "attempt.abandoned", payload: { reason: "left" } });
  assert.equal(log.check(abandoned).result, "accepted", "序号 5 不撞号");
  await s.commit(abandoned, { event_id: JSON.parse(abandoned).event_id, recorded_at: "2026-11-14T06:00:00.000Z", source: "local" });
  assert.equal(s.state.nextSeq, 6);
});

test("同一个文件恢复两次：第二次 items 空，只多一条导入记录（6.2 末段）", async () => {
  const c = CASES.clean_device;
  const s = createFakeBackupStore(structuredClone(c.existing));
  await runRestore(s, planRestore(await s.snapshot(), structuredClone(c.backup), c.opts), { lockLost: never });
  const first = s.dump();
  const p2 = planRestore(await s.snapshot(), structuredClone(c.backup), { ...c.opts, batchId: "imp_" + ulid("P2"), now: "2026-11-14T04:00:00.000Z" });
  assert.deepEqual(p2.items, []);
  assert.deepEqual(p2.batches, []);
  assert.equal(p2.nextSeq, first.nextSeq);
  await runRestore(s, p2, { lockLost: never });
  const second = s.dump();
  assert.deepEqual({ ...second, imports: [] }, { ...first, imports: [] }, "除了导入记录什么都没变");
  assert.equal(second.imports.length, first.imports.length + 1);
  assert.equal(s.log.filter((x) => x.m === "restoreBatch").length, 1, "第二次一批都不写");
});
