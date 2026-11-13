// 实现者补的测试（竖切片 6a）：验收测试和向量没单独覆盖、JS 里容易写错的几处。
// 跑法：node --test app/test/backup-extra.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as M from "../backup.js";

const here = dirname(fileURLToPath(import.meta.url));
const FILEV = JSON.parse(readFileSync(join(here, "..", "vectors", "backup-file.json"), "utf8"));
const fixture = FILEV.build.find((c) => c.name === "fixture_none_midnight");
const opts = { digits: "123456", now: fixture.now, random: (n) => new Uint8Array(n), appCommit: fixture.appCommit, iterations: 100000, chunkSize: 64 };

test("排序按码点，不按 UTF-16 码元：U+FF5E 排在 U+1F600 前面（第 8 节；期望值用 Python sorted 算）", async () => {
  // UTF-16 码元比较会把 😀（D83D…）排到 ～（FF5E）前面，得到别的指纹
  assert.equal(await M.fingerprint(["\u{1F600}", "～", "a"]), "50a85efe");
});

test("单独的低位代理项、非整数的数：做备份停下（3.7 末两条）", async () => {
  for (const bad of [
    (s) => { s.inbox[0] += "\uDC00"; },
    (s) => { s.receipts[0] = { ...s.receipts[0], recorded_at: "x\uD83D" }; },
    (s) => { s.receipts.push({ event_id: "evt_01JC4Y00000000000000000B99", recorded_at: "2026-11-12T01:00:00.000Z", source: "sync", batch_id: "syn_01JC4Y000000000000000000S1", clock_skew_ms: 1.5 }); },
  ]) {
    const s = structuredClone(fixture.snapshot);
    bad(s);
    assert.deepEqual(await M.buildBackup(s, { ...opts, compression: "none" }), { ok: false, error: "self_check" });
  }
  // 成对的代理项（emoji）没问题
  const s = structuredClone(fixture.snapshot);
  s.inbox[0] = s.inbox[0].replace("attempt.started", "attempt.started😀");
  assert.equal((await M.buildBackup(s, { ...opts, compression: "none" })).ok, true);
});

test("快照里有读的时候不认的字段：自检发现，不交出文件（第 7 节）", async () => {
  const s = structuredClone(fixture.snapshot);
  s.receipts[0] = { ...s.receipts[0], extra: 1 };
  assert.deepEqual(await M.buildBackup(s, { ...opts, compression: "gzip" }), { ok: false, error: "self_check" });
});

test("gzip 解压超过上限：too_big，远小于实际大小的上限也一样（3.3 边解边数）", async () => {
  const doc = new TextEncoder().encode("a".repeat(300000));
  const file = await M.encodeBackup(doc, { digits: "123456", createdAt: fixture.now, salt: new Uint8Array(16), noncePrefix: new Uint8Array(7),
    iterations: 100000, chunkSize: 1024, compression: "gzip" });
  assert.deepEqual(await M.decodeBackup(file, "123456", { maxPlain: 1000 }), { ok: false, error: "too_big" });
  assert.deepEqual(await M.decodeBackup(file, "123456", { maxPlain: 299999 }), { ok: false, error: "too_big" });
  const r = await M.decodeBackup(file, "123456", { maxPlain: 300000 });
  assert.equal(r.ok, true);
  assert.equal(r.doc.length, 300000);
});

test("parseKey：NFKC 后不在封闭表里的字符（U+2028、U+200B）不去掉，报「只有数字」；U+2003 经 NFKC 变成空格（2.2）", () => {
  assert.deepEqual(M.parseKey("482 105"), { ok: false, error: "key_not_digits" });
  assert.deepEqual(M.parseKey("482​105"), { ok: false, error: "key_not_digits" });
  assert.deepEqual(M.parseKey("482 105"), { ok: true, digits: "482105" });
  assert.deepEqual(M.parseKey("482 105"), { ok: true, digits: "482105" });
});
