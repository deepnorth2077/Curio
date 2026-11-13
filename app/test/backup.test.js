// 竖切片 6a 的验收测试：app/backup.js（docs/specs/backup.md，接口见 docs/specs/backup-api.md）。
// 验收测试的作者写，实现者不改（受保护路径）。期望值全部来自 app/vectors/backup-*.json，
// 那些向量由 tools/backup_ref.py（Python 参考实现）和手算得出，每条都写了 why。
// 跑法：node --test app/test/backup.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as M from "../backup.js";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const vec = (name) => JSON.parse(readFileSync(join(root, "app", "vectors", name), "utf8"));
const fromHex = (h) => Uint8Array.from(Buffer.from(h, "hex"));
const toHex = (u) => Buffer.from(u).toString("hex");
/** 结果里的 Uint8Array 换成十六进制、去掉 undefined，再比。 */
const plain = (v) => JSON.parse(JSON.stringify(v, (k, x) => (x instanceof Uint8Array ? toHex(x) : x)));

/** 向量里的坏文件变换（和 tools/tests/test_backup_ref.py 的 apply_ops 一样）。 */
export function applyOps(file, ops) {
  let f = Array.from(file);
  for (const op of ops) {
    if (op.op === "truncate") f = f.slice(0, op.len);
    else if (op.op === "xor") f[op.at] ^= op.mask;
    else if (op.op === "append") f = f.concat(Array.from(fromHex(op.hex)));
    else if (op.op === "swap") {
      const x = f.slice(op.a, op.a + op.len);
      const y = f.slice(op.b, op.b + op.len);
      f.splice(op.a, op.len, ...y);
      f.splice(op.b, op.len, ...x);
    } else if (op.op === "replace") f.splice(op.start, op.end - op.start, ...fromHex(op.hex));
    else throw new Error(`向量有错：不认识的变换 ${op.op}`);
  }
  return Uint8Array.from(f);
}

const KEYV = vec("backup-key.json");
const FILEV = vec("backup-file.json");
const MANV = vec("backup-manifest.json");
const EXPV = vec("backup-export.json");
const FILES = Object.fromEntries(Object.entries(FILEV.files).map(([k, f]) => [k, fromHex(f.hex)]));
const src = (c) => (c.from ? FILES[c.from] : new Uint8Array(0));
const zeros = (n) => new Uint8Array(n);

// ---------------------------------------------------------------- 常量
test("常量和给家长的话（backup-api.md，规格 3.8 的原文）", () => {
  assert.equal(M.FORMAT, "curio-backup/1");
  assert.equal(M.MANIFEST, "backup-manifest/1");
  assert.equal(M.WRITE_ITERATIONS, 600000);
  assert.equal(M.WRITE_CHUNK_SIZE, 1048576);
  assert.deepEqual({ ...M.MESSAGES }, {
    key_not_digits: "恢复密钥只有数字",
    key_length: "恢复密钥是 6 个数字",
    not_curio: "这不是 Curio 的备份文件",
    update: "这个备份是新版本的 Curio 做的，请先更新 Curio",
    corrupt: "备份文件坏了",
    wrong_key: "恢复密钥不对。请对照纸上的密钥再输一次",
    incomplete: "备份文件坏了，或者不完整。换一个备份文件试试",
    too_big: "备份太大，这台设备放不下",
  });
});

// ---------------------------------------------------------------- 2. 恢复密钥
test("generateKey（2.1）：丢掉重取、补零，不多取随机数", () => {
  for (const g of KEYV.generate) {
    let i = 0;
    const got = M.generateKey(() => {
      if (i >= g.u32.length) throw new Error("多取了随机数");
      return g.u32[i++];
    });
    assert.equal(got, g.expect, g.why);
    assert.equal(i, g.u32.length, `${g.why}：应正好取 ${g.u32.length} 个随机数`);
  }
});

test("formatKey（2.1）", () => {
  for (const f of KEYV.format) assert.equal(M.formatKey(f.digits), f.expect, f.why);
});

test("parseKey（2.2）：规整的每一步和提示的先后", () => {
  for (const p of KEYV.parse) assert.deepEqual(plain(M.parseKey(p.input)), p.expect, `${JSON.stringify(p.input)}：${p.why}`);
});

// ---------------------------------------------------------------- 3. 文件
test("encodeBackup（3.1～3.2）：none 模式逐字节等于向量", async () => {
  for (const c of FILEV.encode) {
    const p = c.params;
    const got = await M.encodeBackup(fromHex(c.doc_hex), {
      digits: p.digits, createdAt: p.createdAt, salt: fromHex(p.salt_hex), noncePrefix: fromHex(p.noncePrefix_hex),
      iterations: p.iterations, chunkSize: p.chunkSize, compression: p.compression,
    });
    assert.ok(got instanceof Uint8Array, "返回 Uint8Array");
    assert.equal(toHex(got), FILEV.files[c.file].hex, `${c.file}：${c.why}`);
  }
});

test("decodeBackup（3.8 第 2～9 步）：好文件、各种坏文件、给出的结论代码", async () => {
  for (const c of FILEV.decode) {
    const file = applyOps(src(c), c.ops);
    const opts = c.maxPlain !== undefined ? { maxPlain: c.maxPlain } : {};
    const r = await M.decodeBackup(file, c.digits, opts);
    if (c.expect.ok) {
      assert.equal(r.ok, true, `${c.name}：${c.why}；实际 ${JSON.stringify(plain(r))}`);
      assert.ok(r.doc instanceof Uint8Array && r.headerLine instanceof Uint8Array, `${c.name}：doc、headerLine 是 Uint8Array`);
      assert.equal(toHex(r.doc), c.expect.doc_hex, `${c.name}：明文`);
      assert.equal(toHex(r.headerLine), c.expect.headerLine_hex, `${c.name}：文件头那一行`);
      assert.deepEqual(plain(r.header), c.expect.header, `${c.name}：文件头对象`);
    } else {
      assert.deepEqual(plain(r), c.expect, `${c.name}：${c.why}`);
    }
  }
});

test("readBackup（3.8 第 1～11 步）", async () => {
  for (const c of FILEV.read) {
    const r = await M.readBackup(applyOps(src(c), c.ops), c.keyInput);
    assert.deepEqual(plain(r), c.expect, `${c.name}：${c.why}`);
  }
  const r = await M.readBackup(FILES.min, "123456", { maxPlain: 350 });
  assert.deepEqual(plain(r), { ok: false, error: "too_big" }, "readBackup 把 maxPlain 交给第 8 步");
});

test("readBackup 不改传进来的文件字节", async () => {
  const f = FILES.fixture_none.slice();
  await M.readBackup(f, "123456");
  assert.equal(toHex(f), FILEV.files.fixture_none.hex);
});

// ---------------------------------------------------------------- 4. 明文文档
// backup-api.md 把 writeManifestDoc、readManifestDoc 写成同步函数，但它们要算 end 行的 SHA-256，而 Web Crypto 的 digest 只有异步的。
// 测试对两者都 await：同步实现（自带 SHA-256）和异步实现都能过。接口最后怎么定，见交付说明。
test("writeManifestDoc（第 4 节、3.7）：逐字节", async () => {
  for (const c of MANV.write) {
    const got = await M.writeManifestDoc(c.snapshot, { createdAt: c.createdAt, appCommit: c.appCommit });
    assert.ok(got instanceof Uint8Array, "返回 Uint8Array");
    assert.equal(toHex(got), c.expect_hex, `${c.name}：${c.why}`);
  }
});

test("readManifestDoc（第 4 节；3.8 第 9～11 步）：每条规则的正反例", async () => {
  for (const c of MANV.read) {
    const r = await M.readManifestDoc(fromHex(c.doc_hex), MANV.header);
    assert.deepEqual(plain(r), c.expect, `${c.name}：${c.why}`);
  }
});

// ---------------------------------------------------------------- 7. 做备份
test("buildBackup（第 7 节）：none 逐字节、文件名按 UTC+8、默认参数、gzip 能读回、单独的代理项停下", async () => {
  for (const c of FILEV.build) {
    const opts = { digits: FILEV.key, now: c.now, random: zeros, appCommit: c.appCommit, compression: c.compression };
    if (c.iterations !== undefined) opts.iterations = c.iterations;
    if (c.chunkSize !== undefined) opts.chunkSize = c.chunkSize;
    const r = await M.buildBackup(structuredClone(c.snapshot), opts);
    if (!c.expect.ok) {
      // 注意：JSON.stringify 遇到单独的代理项不会出错，而是写成 \ud800 这样的转义（ES2019），所以要另外查（3.7 末条）
      assert.deepEqual({ ok: r.ok, error: r.error }, c.expect, `${c.name}：${c.why}`);
      continue;
    }
    assert.equal(r.ok, true, `${c.name}：${JSON.stringify(plain(r)).slice(0, 300)}`);
    assert.equal(r.fileName, c.expect.fileName, `${c.name}：文件名`);
    if (c.expect.hex) assert.equal(toHex(r.bytes), c.expect.hex, `${c.name}：${c.why}`);
    const d = await M.decodeBackup(r.bytes, FILEV.key);
    assert.equal(d.ok, true);
    assert.equal(toHex(d.doc), c.expect.doc_hex, `${c.name}：读回来的明文`);
    assert.equal(d.header.compression, c.compression);
    for (const [k, v] of Object.entries(c.expect.header ?? {})) assert.equal(d.header[k], v, `${c.name}：文件头 ${k}`);
  }
});

test("buildBackup 用传进来的随机数做 salt 和 nonce_prefix", async () => {
  const c = FILEV.build[0];
  const r = await M.buildBackup(structuredClone(c.snapshot), { digits: "123456", now: c.now, random: (n) => new Uint8Array(n).fill(0xab),
    appCommit: c.appCommit, compression: "none", iterations: 600000, chunkSize: 64 });
  const d = await M.decodeBackup(r.bytes, "123456");
  assert.equal(d.header.salt, Buffer.alloc(16, 0xab).toString("base64"));
  assert.equal(d.header.nonce_prefix, Buffer.alloc(7, 0xab).toString("base64"));
});

// ---------------------------------------------------------------- 8、9
test("fingerprint（第 8 节）", async () => {
  for (const c of EXPV.fingerprint) assert.equal(await M.fingerprint(c.ids), c.expect, c.why);
});

test("buildExport（第 9 节）：逐字节、按排序键、换行换成空格", async () => {
  for (const c of EXPV.export) {
    const r = await M.buildExport(c.raws, { exportedAt: c.exportedAt, learnerId: c.learnerId });
    assert.equal(toHex(r.bytes), c.expect.hex, c.why);
    assert.equal(r.fileName, c.expect.fileName);
  }
});

// ---------------------------------------------------------------- 样例文件（3.5）
const FIX = join(root, "tests", "fixtures", "backup");
const fixtureBackup = FILEV.read.find((c) => c.name === "ok_fixture_none").expect.backup;
const expectedDoc = readFileSync(join(FIX, "expected-doc.jsonl"));

for (const name of ["v1-none.curio", "v1-gzip.curio"]) {
  test(`样例文件 ${name}（Python 写的）：JS 能读，内容和 expected-doc.jsonl 一样`, async () => {
    const file = new Uint8Array(readFileSync(join(FIX, name)));
    const d = await M.decodeBackup(file, "123456");
    assert.equal(d.ok, true, JSON.stringify(plain(d)));
    assert.equal(toHex(d.doc), expectedDoc.toString("hex"));
    const r = await M.readBackup(file, "１２３ ４５６");
    assert.equal(r.ok, true);
    assert.deepEqual(plain(r.backup), fixtureBackup);
    assert.deepEqual(plain(await M.readBackup(file, "123457")), { ok: false, error: "wrong_key" });
  });
}

// ---------------------------------------------------------------- 浏览器写的 gzip，Python 读（3.3、测试接缝）
function findPython() {
  for (const py of ["python3", "python"]) {
    const p = spawnSync(py, ["-c", "import cryptography, sys; print(sys.version_info[0])"], { encoding: "utf8" });
    if (p.status === 0 && p.stdout.trim() === "3") return py;
  }
  return null;
}

test("JS 的 buildBackup 写 gzip 文件，Python 参考实现读得出同样的明文；gzip 是一个成员、FLG=0、MTIME=0", async (t) => {
  const py = findPython();
  if (!py) {
    if (process.env.CI) assert.fail("CI 里应当有装了 cryptography 的 Python（tools/requirements.txt）");
    t.skip("没有装了 cryptography 的 Python，跳过");
    return;
  }
  const c = FILEV.build.find((x) => x.name === "fixture_gzip");
  const r = await M.buildBackup(structuredClone(c.snapshot), { digits: "123456", now: c.now, random: (n) => new Uint8Array(n).fill(7),
    appCommit: c.appCommit, compression: "gzip", iterations: 600000, chunkSize: 64 });
  assert.equal(r.ok, true);
  const dir = mkdtempSync(join(tmpdir(), "curio-6a-"));
  try {
    const f = join(dir, r.fileName);
    writeFileSync(f, r.bytes);
    const p = spawnSync(py, [join(root, "tools", "backup_ref.py"), "decode", f, "123456"]);
    assert.equal(p.status, 0, `Python 读 JS 写的文件失败：${p.stderr}`);
    assert.equal(p.stdout.toString("hex"), c.expect.doc_hex, "Python 解出的明文和向量一样");
    const check = [
      "import sys, json, zlib, base64",
      `sys.path.insert(0, ${JSON.stringify(join(root, "tools"))})`,
      "import backup_ref as B",
      "f = open(sys.argv[1], 'rb').read()",
      "s = f.index(b'\\n') + 1; e = f.index(b'\\n', s); h = json.loads(f[s:e])",
      "k, _ = B.derive('123456', base64.b64decode(h['salt']), h['iterations'])",
      "body = f[e + 1:]; n = h['chunk_size'] + 16; parts = [body[i:i + n] for i in range(0, len(body), n)]",
      "stream = b''.join(B.AESGCM(k).decrypt(B.nonce(base64.b64decode(h['nonce_prefix']), i, i == len(parts) - 1), c, f[:e]) for i, c in enumerate(parts))",
      "assert stream[:4] == b'\\x1f\\x8b\\x08\\x00', 'FLG 不是 0'",
      "assert stream[4:8] == b'\\x00\\x00\\x00\\x00', 'MTIME 不是 0'",
      "d = zlib.decompressobj(16 + zlib.MAX_WBITS); d.decompress(stream); d.flush()",
      "assert d.eof and d.unused_data == b'', '不是正好一个 gzip 成员'",
      "print('ok')",
    ].join("\n");
    const q = spawnSync(py, ["-c", check, f], { encoding: "utf8" });
    assert.equal(q.stdout.trim(), "ok", q.stderr);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
