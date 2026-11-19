// 真实备份、解密、恢复事务、日志重放和只读导出的闭环。只用内存存储代替 IndexedDB。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildBackup, readBackup, buildExport } from "../backup.js";
import { planRestore, runRestore } from "../restore.js";
import { createFakeBackupStore } from "./fake-backup-store.js";
import { createLog } from "../../kernel/js/log.js";
import { projectMastery } from "../../kernel/js/mastery.js";

const vector = JSON.parse(readFileSync(new URL("../../kernel/vectors/ingest-sim-observed.json", import.meta.url)));
const events = vector.inputs.filter(row => row.expect === "accepted")
  .map(row => ({ ...vector.base, ...row.event }));
const now = "2026-11-19T08:00:00.000Z";
const key = "123456";

for (const legacy of [true, false]) {
  test(legacy ? "旧事件无站点观察也可恢复，不补造站点记录" : "观察的原文穿过加密备份、恢复、重放和导出", async () => {
    const originals = legacy
      ? events.filter(e => e.verb !== "sim.observed").map(e => ({ ...e, content: { ...e.content, activity_version: 1 } }))
      : events;
    const raws = originals.map(e => JSON.stringify(e));
    const { learner_id, device_id } = vector.base;
    const source = createFakeBackupStore({
      identity: { learner_id, device_id }, inbox: raws, nextSeq: originals.at(-1).device_seq + 1,
    });
    const file = await buildBackup(await source.snapshot(), {
      now, digits: key, appCommit: "a123bcd", compression: "gzip", iterations: 100000,
      random: n => crypto.getRandomValues(new Uint8Array(n)),
    });
    assert.equal(file.ok, true);
    const decoded = await readBackup(file.bytes, key);
    assert.equal(decoded.ok, true);
    assert.deepEqual(decoded.backup.inbox, raws);
    const target = createFakeBackupStore({
      identity: { learner_id, device_id: "dev_00000000000000000000000002" }, nextSeq: 1,
    });
    const opts = { now, batchId: "imp_00000000000000000000000001", inputKey: key };
    const plan = planRestore(await target.snapshot(), decoded, opts);
    assert.equal(plan.ok, true);
    assert.deepEqual(await runRestore(target, plan, { lockLost: () => false }), { ok: true });
    const restored = await target.snapshot();
    assert.deepEqual(restored.inbox, raws);
    assert.equal(restored.imports[0].accepted, raws.length);
    assert.equal(restored.imports[0].not_yet_known, 0);
    assert.equal(restored.imports[0].quarantined_new, 0);
    assert.equal(restored.receipts.length, raws.length);
    const log = createLog();
    for (const raw of restored.inbox) assert.equal(log.ingest(raw).result, "accepted");
    assert.deepEqual(projectMastery(log.events()), vector.mastery);
    const exported = await buildExport(log.raw(), { exportedAt: now, learnerId: learner_id });
    const lines = new TextDecoder().decode(exported.bytes).trimEnd().split("\n");
    assert.equal(JSON.parse(lines[0]).events, raws.length);
    assert.deepEqual(lines.slice(1, -1), raws);
    const again = planRestore(restored, decoded, { ...opts, batchId: "imp_00000000000000000000000002" });
    assert.equal(again.record.accepted, 0);
    assert.equal(again.record.duplicate, raws.length);
  });
}
