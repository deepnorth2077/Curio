// 实现者补的测试：舰长资料 PR 2「会写的界面」（docs/specs/profile.md 第 1、4、5 节，#224）。
// 期望值都是手算的字面值：学年按 UTC+8，9 月 1 日起升一级。
// 跑法：node --test app/test/profile-parent.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createLog } from "../../kernel/js/log.js";
import { openSession, assembleCaregiver, caregiverId } from "../session.js";
import {
  saveProfile, profilePayload, profileSentence, savedDateText, schoolYearText, currentGradeOf, defaultGrade,
  needsProfileHint, refreshProfile, isClean,
} from "../parent.js";
import { currentGrade } from "../app.js";
import { writeManifestDoc } from "../backup.js";
import { createFakeBackupStore as createBase } from "./fake-backup-store.js";
import { fixtures } from "./fake-store.js";

/**
 * 假存储（受保护，不改）外面加上 app/store.js 的两个 caregiver 方法，语义照 store.js：
 * ensureCaregiver 一个事务里「有就保留、没有才写」，返回存着的那个；snapshot() 不带它。
 */
function createFakeBackupStore(snap) {
  const store = createBase(snap);
  let cg = null;
  let queue = Promise.resolve();
  const RE = /^cg_[0-7][0-9A-HJKMNP-TV-Z]{25}$/;
  store.state.caregiver = null;
  store.calls.ensureCaregiver = 0;
  store.getCaregiver = async () => (cg ? { ...cg } : null);
  store.ensureCaregiver = (v) => {
    store.calls.ensureCaregiver++;
    const p = queue.then(async () => {
      await new Promise((r) => setTimeout(r, 0));
      if (typeof v?.id !== "string" || !RE.test(v.id)) throw new Error("假存储：caregiver 的 id 格式不对");
      if (!cg) { cg = { id: v.id }; store.state.caregiver = { ...cg }; }
      return { ...cg };
    });
    queue = p.catch(() => {});
    return p;
  };
  return store;
}

const CG = (n) => "cg_01JC" + String(n).padStart(22, "0");
/** 北京时间 2026-11-21 10:00（UTC 02:00）。 */
const NOV21 = Date.UTC(2026, 10, 21, 2, 0, 0);

/** 开好会话的假设备，外加 saveProfile 要的 env。 */
async function device({ mode = "writable", lock = true } = {}) {
  const store = createFakeBackupStore();
  const fx = fixtures();
  let c = 0;
  const ids = { ...fx.ids, caregiver: () => CG(++c) };
  const s = await openSession(store, { ids, now: fx.now });
  const app = { mode, session: s, log: s.log, store, profile: null, clean: true };
  refreshProfile(app);
  const env = { app, holdsLock: () => lock, ids, now: fx.now, nowMs: () => NOV21 };
  return { store, fx, s, app, env, made: () => c };
}

test("caregiver ID 只生成一次：第二次读到存着的那个", async () => {
  const store = createFakeBackupStore();
  let n = 0;
  const newId = () => CG(++n);
  assert.equal(await caregiverId(store, newId), "cg_01JC0000000000000000000001");
  assert.equal(await caregiverId(store, newId), "cg_01JC0000000000000000000001");
  assert.equal(n, 1, "只生成了一个");
  assert.equal(store.calls.ensureCaregiver, 1, "只写了一次");
  // store.js 的真实现由无头浏览器走查核对（meta 里只有一条 caregiver）
  // 两个事务同时来：先存的留下，后来的拿到先存的
  const store2 = createFakeBackupStore();
  const [a, b] = await Promise.all([store2.ensureCaregiver({ id: CG(7) }), store2.ensureCaregiver({ id: CG(8) })]);
  assert.deepEqual([a.id, b.id], ["cg_01JC0000000000000000000007", "cg_01JC0000000000000000000007"]);
  await assert.rejects(store2.ensureCaregiver({ id: "cg_bad" }), /格式不对/);
});

test("caregiver ID 不进备份：snapshot 不带它，备份文档里也没有", async () => {
  const store = createFakeBackupStore({ identity: { learner_id: "lrn_01JC0000000000000000000001", device_id: "dev_01JC0000000000000000000002" }, nextSeq: 1 });
  await store.ensureCaregiver({ id: CG(5) });
  const snap = await store.snapshot();
  assert.equal("caregiver" in snap, false, "snapshot 不带 caregiver");
  assert.equal(isClean(snap), true, "只存了 caregiver 的设备仍然干净（还能恢复）");
  // 就算快照里混进了 caregiver，备份也只从固定的几部分组装
  const doc = new TextDecoder().decode(await writeManifestDoc({ ...snap, caregiver: { id: CG(5) } }, { createdAt: "2026-11-21T02:00:00.000Z", appCommit: "0000000" }));
  assert.equal(doc.includes("cg_01JC0000000000000000000005"), false);
  assert.equal(doc.includes("caregiver"), false);
});

test("assembleCaregiver：范围「无」，不带 attempt_id、content，能被 createLog().ingest 接收", () => {
  const raw = assembleCaregiver({
    event_id: "evt_01JC0000000000000000000009",
    identity: { learner_id: "lrn_01JC0000000000000000000001", device_id: "dev_01JC0000000000000000000002" },
    device_seq: 1,
    occurred_at: "2026-11-21T02:00:00.000Z",
    caregiver_id: "cg_01JC0000000000000000000003",
    verb: "profile.set",
    payload: { rev: 1, entry_year: 2024, textbooks: { math: "renjiao", science: "jiaoke" } },
  });
  assert.equal(raw, '{"schema":"event/2","event_id":"evt_01JC0000000000000000000009","learner_id":"lrn_01JC0000000000000000000001",'
    + '"device_id":"dev_01JC0000000000000000000002","device_seq":1,"occurred_at":"2026-11-21T02:00:00.000Z",'
    + '"actor":{"type":"caregiver","id":"cg_01JC0000000000000000000003"},"verb":"profile.set",'
    + '"payload":{"rev":1,"entry_year":2024,"textbooks":{"math":"renjiao","science":"jiaoke"}}}');
  const log = createLog();
  assert.equal(log.ingest(raw).result, "accepted");
  assert.equal(log.events().length, 1);
});

test("保存两次：rev 1 → 2，entry_year 按学年换算，app.profile 跟着更新，写进存储", async () => {
  const { store, app, env, made } = await device();
  assert.equal(app.profile.profile, null);
  const r1 = await saveProfile(env, { grade: 3, textbooks: { math: "renjiao", science: "jiaoke" } });
  assert.equal(r1.ok, true);
  assert.deepEqual(app.profile.profile.rev, 1);
  assert.equal(app.profile.profile.entry_year, 2024, "2026 学年读 3 年级 → 2024 年入学");
  assert.deepEqual(app.profile.profile.textbooks, { math: "renjiao", science: "jiaoke" });
  assert.equal(app.clean, false);
  const e1 = JSON.parse(r1.raw);
  assert.deepEqual(e1.actor, { type: "caregiver", id: "cg_01JC0000000000000000000001" });
  assert.equal("attempt_id" in e1, false);
  assert.equal("content" in e1, false);
  assert.equal(e1.device_seq, 1);
  assert.deepEqual(e1.payload, { rev: 1, entry_year: 2024, textbooks: { math: "renjiao", science: "jiaoke" } });

  const r2 = await saveProfile(env, { grade: 4, textbooks: { math: "renjiao", science: "jiaoke" } });
  assert.equal(r2.ok, true);
  const e2 = JSON.parse(r2.raw);
  assert.deepEqual(e2.payload, { rev: 2, entry_year: 2023, textbooks: { math: "renjiao", science: "jiaoke" } });
  assert.equal(e2.device_seq, 2);
  assert.equal(e2.actor.id, "cg_01JC0000000000000000000001", "第二次用同一个家长 ID");
  assert.equal(made(), 1);
  assert.equal(app.profile.profile.rev, 2);
  assert.equal(currentGradeOf(app.profile.profile, NOV21), 4);
  assert.equal(profileSentence(app.profile.profile, NOV21), "这个学年读 4 年级，数学人教版，科学教科版");

  // 存储里：两条原文、两张收据、nextSeq = 3；isClean 为假
  assert.equal(store.state.inbox.length, 2);
  assert.equal(store.state.receipts.size, 2);
  assert.equal(store.state.nextSeq, 3);
  assert.equal(isClean(await store.snapshot()), false);

  // 刷新：重新打开会话，不补写任何东西，资料还在
  const fx2 = fixtures();
  const s2 = await openSession(store, { ids: { ...fx2.ids, caregiver: () => CG(99) }, now: fx2.now });
  assert.deepEqual(s2.abandoned, []);
  const app2 = { log: s2.log };
  refreshProfile(app2);
  assert.equal(app2.profile.profile.rev, 2);
  assert.equal(app2.profile.profile.entry_year, 2023);
});

test("只读、「上次恢复没做完」时不能保存，什么都不写", async () => {
  for (const opt of [{ lock: false }, { mode: "unfinished" }, { mode: "readonly" }]) {
    const { store, env } = await device(opt);
    const r = await saveProfile(env, { grade: 3, textbooks: { math: "renjiao", science: "jiaoke" } });
    assert.deepEqual(r, { ok: false, error: "readonly" }, JSON.stringify(opt));
    assert.equal(store.state.inbox.length, 0);
    assert.equal(store.state.caregiver, null, "也不生成家长 ID");
  }
});

test("committer 冻结（失去写锁）以后不能保存", async () => {
  const { store, s, env } = await device();
  s.committer.freeze();
  const r = await saveProfile(env, { grade: 3, textbooks: { math: "renjiao", science: "jiaoke" } });
  assert.equal(r.ok, false);
  assert.equal(store.state.inbox.length, 0);
});

test("currentGrade：9 月 1 日（北京时间）的边界、越界返回 null", () => {
  const p = (entry_year) => ({ rev: 1, entry_year, textbooks: {}, occurred_at: "2026-11-21T02:00:00.000Z" });
  assert.equal(currentGradeOf(p(2024), Date.parse("2026-08-31T15:59:59Z")), 2);
  assert.equal(currentGradeOf(p(2024), Date.parse("2026-08-31T16:00:00Z")), 3);
  assert.equal(currentGradeOf(p(2024), NOV21), 3);
  assert.equal(currentGradeOf(p(2035), NOV21), null, "得 −8：还没上小学");
  assert.equal(currentGradeOf(p(2010), NOV21), null, "得 17：已经毕业");
  assert.equal(currentGradeOf(p(2026), NOV21), 1);
  assert.equal(currentGradeOf(p(2015), NOV21), 12);
  assert.equal(currentGradeOf(p(2014), NOV21), null, "得 13");
  assert.equal(currentGradeOf(null, NOV21), null);
  assert.equal(currentGrade(NOV21), null, "外壳还没有日志时 app.profile 是 null");
});

test("家长页的字：学年、确认句、保存日期、默认年级、提醒", () => {
  assert.equal(schoolYearText(NOV21), "这个学年：2026 年 9 月～2027 年 8 月");
  assert.equal(schoolYearText(Date.parse("2027-08-15T02:00:00Z")), "这个学年：2026 年 9 月～2027 年 8 月", "8 月仍是正要结束的学年");
  assert.equal(schoolYearText(Date.parse("2027-08-31T16:00:00Z")), "这个学年：2027 年 9 月～2028 年 8 月");
  const tb = { math: "renjiao", science: "jiaoke" };
  assert.equal(profileSentence({ entry_year: 2024, textbooks: tb }, NOV21), "这个学年读 3 年级，数学人教版，科学教科版");
  assert.equal(profileSentence({ entry_year: 2035, textbooks: tb }, NOV21), "还没上小学，数学人教版，科学教科版");
  assert.equal(profileSentence({ entry_year: 2010, textbooks: tb }, NOV21), "已经毕业，数学人教版，科学教科版");
  assert.equal(profileSentence({ entry_year: 2024, textbooks: {} }, NOV21), "这个学年读 3 年级");
  assert.equal(savedDateText("2026-11-21T02:00:00.000Z"), "11 月 21 日保存");
  assert.equal(savedDateText("2026-11-20T16:30:00.000Z"), "11 月 21 日保存", "UTC 20 日 16:30 是北京时间 21 日");
  assert.equal(savedDateText("2026-11-20T15:59:59.000Z"), "11 月 20 日保存");
  assert.equal(defaultGrade(null, NOV21), 3);
  assert.equal(defaultGrade({ entry_year: 2023 }, NOV21), 4);
  assert.equal(defaultGrade({ entry_year: 2035 }, NOV21), 1);
  assert.equal(defaultGrade({ entry_year: 2010 }, NOV21), 12);
  assert.deepEqual(profilePayload(null, 3, NOV21, tb), { rev: 1, entry_year: 2024, textbooks: tb });
  assert.deepEqual(profilePayload({ rev: 4 }, 12, NOV21, tb), { rev: 5, entry_year: 2015, textbooks: tb });
  assert.throws(() => profilePayload(null, 13, NOV21, tb));
  assert.throws(() => profilePayload(null, 0, NOV21, tb));
  assert.equal(needsProfileHint({ clean: true, profile: null }), false, "干净设备上不提醒");
  assert.equal(needsProfileHint({ clean: false, profile: null }), true);
  assert.equal(needsProfileHint({ clean: false, profile: { rev: 1 } }), false);
});
