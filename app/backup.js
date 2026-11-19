// 竖切片 6a：恢复密钥、备份文件读写、明文文档、做备份、记录指纹、可读导出
// （docs/specs/backup.md 第 2～4、7～9 节；接口见 docs/specs/backup-api.md）。
// 纯模块：不碰 DOM、存储、当前时间和随机数（都从参数来）；只用 Web Crypto、CompressionStream/DecompressionStream、
// TextEncoder/TextDecoder，Node 22 和 iPad Safari 16.4+ 都能跑。
import { isObject, sameJson } from "../kernel/js/validate.js";

export const FORMAT = "curio-backup/1";
export const MANIFEST = "backup-manifest/1";
export const WRITE_ITERATIONS = 600000;
export const WRITE_CHUNK_SIZE = 1048576;

/** 3.8 的结论代码 → 给家长的话（规格原文）。 */
export const MESSAGES = Object.freeze({
  key_not_digits: "恢复密钥只有数字",
  key_length: "恢复密钥是 6 个数字",
  not_curio: "这不是 Curio 的备份文件",
  update: "这个备份是新版本的 Curio 做的，请先更新 Curio",
  corrupt: "备份文件坏了",
  wrong_key: "恢复密钥不对。请对照纸上的密钥再输一次",
  incomplete: "备份文件坏了，或者不完整。换一个备份文件试试",
  too_big: "备份太大，这台设备放不下",
});

const S = globalThis.crypto.subtle;
const ENC = new TextEncoder();
// 第 4 节：严格 UTF-8；ignoreBOM 让开头的 BOM 留在结果里，好查出来（默认会被悄悄去掉）
const DEC = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
const LINE1 = ENC.encode("CURIO-BACKUP/1\n");
const MAX_HEADER = 4096;
const MAX_PLAIN = 2 ** 30; // 3.3：解压后最多 1 GiB

const ULID = "[0-7][0-9A-HJKMNP-TV-Z]{25}";
const idRe = (p) => new RegExp(`^${p}_${ULID}$`);
const RE = {
  lrn: idRe("lrn"), dev: idRe("dev"), evt: idRe("evt"), imp: idRe("imp"), syn: idRe("syn"),
  ts: /^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{3}Z$/,
  commit: /^[0-9a-f]{7,40}$/, rel: /^rel_[0-9a-f]{64}$/, hex64: /^[0-9a-f]{64}$/,
};
const HEADER_KEYS = ["format", "created_at", "kdf", "iterations", "salt", "key_check", "cipher", "nonce_prefix", "chunk_size", "compression"];
const MANIFEST_KEYS = ["schema", "created_at", "learner_id", "device_id", "app_commit", "counts"];
const COUNT_KEYS = ["inbox", "receipt", "import", "archive", "release"];
const RECEIPT_KEYS = ["event_id", "recorded_at", "source", "batch_id", "clock_skew_ms"];
const IMPORT_KEYS = ["schema", "batch_id", "imported_at", "source", "partial", "file_created_at", "file_device_id", "file_salt",
  "accepted", "duplicate", "not_yet_known", "quarantined_new", "quarantined_skipped", "archived", "releases"];
const EXPORT_NOTE = "每行一条学习事件，格式见 Curio 仓库 docs/specs/events.md。最后一行是前面所有行的 SHA-256。";

/** 读不下去：code 是 3.8 的结论代码。 */
class Fail {
  /** @param {string} code */
  constructor(code) { this.code = code; }
}
/** 写的程序出错（3.7：单独的代理项、非整数），做备份时停下。 */
class WriteError extends Error {}

/** 跑 fn，把 Fail 换成 {ok:false, error}。别的错照常抛（那是程序的错，不是文件的错）。 */
async function attempt(fn) {
  try { return await fn(); } catch (e) { if (e instanceof Fail) return { ok: false, error: e.code }; throw e; }
}

/* ---------------------------------------------------------------- 小工具 */

/** 按 Unicode 码点比较（规格第 1 节的排序；不用 localeCompare）。 @param {string} a @param {string} b */
function cmp(a, b) {
  for (let i = 0; ; ) {
    if (i >= a.length || i >= b.length) return Number(i < a.length) - Number(i < b.length);
    const x = /** @type {number} */ (a.codePointAt(i)), y = /** @type {number} */ (b.codePointAt(i));
    if (x !== y) return x - y;
    i += x > 0xffff ? 2 : 1;
  }
}
const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
/** 字段正好是 keys（不看顺序，3.7 读的时候不查顺序）。 */
const exactKeys = (o, keys) => Object.keys(o).length === keys.length && keys.every((k) => has(o, k));
const full = (re, v) => typeof v === "string" && re.test(v);
const nonNegInt = (v) => Number.isInteger(v) && v >= 0;

/** @param {Uint8Array[]} parts */
function concat(parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
}
const sameBytes = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

/** @param {Uint8Array} bytes @returns {Promise<string>} 小写十六进制 */
async function sha256Hex(bytes) {
  const d = new Uint8Array(await S.digest("SHA-256", bytes));
  return Array.from(d, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** 标准 Base64（只用在 16、7 字节这种小东西上）。 */
const b64 = (u) => btoa(String.fromCharCode(...u));
/** 3.1：标准 Base64、带补位、规范写法（解码再编码要和原文相同），解码后正好 n 字节。不对给 null。 */
function b64Exact(s, n) {
  if (typeof s !== "string") return null;
  let bin;
  try { bin = atob(s); } catch { return null; }
  const u = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return u.length === n && b64(u) === s ? u : null;
}

/** 文件名用的本地时间（UTC+8，事件规格第 1 节）：YYYYMMDD-HHMM。 @param {string} utc */
function stamp(utc) {
  const t = new Date(Date.parse(utc) + 8 * 3600e3).toISOString();
  return `${t.slice(0, 4)}${t.slice(5, 7)}${t.slice(8, 10)}-${t.slice(11, 13)}${t.slice(14, 16)}`;
}

/** 一串字节当作只有一段的可读流（不复制）。 @param {Uint8Array[]} parts */
const streamOf = (parts) => new ReadableStream({ start(c) { for (const p of parts) c.enqueue(p); c.close(); } });

/* ---------------------------------------------------------------- 3.7 JSON 行的写法 */

const LONE = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;
/** 3.7 末两条：数只能是整数；字符串里不能有单独的代理项（JSON.stringify 会把它写成 \ud800 而不报错，所以要自己查）。 */
function checkWritable(v) {
  if (typeof v === "string") { if (LONE.test(v)) throw new WriteError("字符串里有单独的代理项"); }
  else if (typeof v === "number") { if (!Number.isSafeInteger(v)) throw new WriteError("这些行里的数只能是整数"); }
  else if (v !== null && typeof v === "object") for (const [k, x] of Object.entries(v)) { checkWritable(k); checkWritable(x); }
}
/** 3.7 的写法就是 JSON.stringify（不加空格、非 ASCII 原样、只转义 " \ 和控制字符）。键的顺序由调用方摆好。 */
function line(v) {
  checkWritable(v);
  return JSON.stringify(v) + "\n";
}
/** 按表格的顺序排键；表外的字段（不该有）排在后面照写，让自检读的时候发现。 */
function ordered(o, keys) {
  const out = {};
  for (const k of keys) if (has(o, k)) out[k] = o[k];
  for (const k of Object.keys(o)) if (!has(out, k)) out[k] = o[k];
  return out;
}

/* ---------------------------------------------------------------- 2. 恢复密钥 */

/** 2.1：x ≥ 4294000000 丢掉重取，否则 x mod 10^6 补零到 6 位；每个 6 位数的机会一样。 @param {() => number} nextU32 */
export function generateKey(nextU32) {
  for (;;) {
    const x = nextU32();
    if (!Number.isInteger(x) || x < 0 || x >= 2 ** 32) throw new RangeError("nextU32 要给 0..2^32-1 的整数");
    if (x < 4294000000) return String(x % 1000000).padStart(6, "0");
  }
}

/** 2.1：显示成两组。 @param {string} digits */
export const formatKey = (digits) => `${digits.slice(0, 3)} ${digits.slice(3)}`;

// 2.2 第 2 步：封闭的表，不用语言自带的「空白」定义
const STRIP = new Set("\t\n\v\f\r  　-‐‑‒–—―−ー");

/** 2.2：NFKC → 去掉封闭表里的字符 → 只许 0～9 → 正好 6 个；按这个顺序，第一处不对就停。 @param {string} input */
export function parseKey(input) {
  let t = "";
  for (const ch of input.normalize("NFKC")) if (!STRIP.has(ch)) t += ch;
  if (!/^[0-9]*$/.test(t)) return { ok: false, error: "key_not_digits" };
  if (t.length !== 6) return { ok: false, error: "key_length" };
  return { ok: true, digits: t };
}

/* ---------------------------------------------------------------- 3. 备份文件 */

/** 3.2：PBKDF2-SHA256 放慢 → HKDF-SHA256（空 salt）派生加密密钥和 key_check。 */
async function derive(digits, salt, iterations) {
  const base = await S.importKey("raw", ENC.encode(digits), "PBKDF2", false, ["deriveBits"]);
  const prk = await S.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations }, base, 256);
  const hk = await S.importKey("raw", prk, "HKDF", false, ["deriveBits"]);
  const hkdf = (info, bits) => S.deriveBits({ name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: ENC.encode(info) }, hk, bits);
  const key = await S.importKey("raw", await hkdf("curio-backup/1 enc", 256), "AES-GCM", false, ["encrypt", "decrypt"]);
  return { key, check: new Uint8Array(await hkdf("curio-backup/1 check", 128)) };
}

/** 3.2：随机数 = nonce_prefix（7）+ 块序号（4，大端）+ 末块标记（1）。 */
function nonce(prefix, i, last) {
  const n = new Uint8Array(12);
  n.set(prefix);
  new DataView(n.buffer).setUint32(7, i);
  n[11] = last ? 1 : 0;
  return n;
}

/** 3.1：文件头那一行，字段按表的顺序，3.7 的写法（不含结尾的 \n）。 */
const headerText = (h) => JSON.stringify(Object.fromEntries(HEADER_KEYS.map((k) => [k, h[k]])));

/** 3.3 写：恰好一个 gzip 成员，FLG = 0，MTIME = 0。 @param {Uint8Array} doc @param {string} compression */
async function compress(doc, compression) {
  if (compression === "none") return doc;
  if (compression !== "gzip") throw new TypeError(`compression 只能是 gzip 或 none：${compression}`);
  const gz = new Uint8Array(await new Response(streamOf([doc]).pipeThrough(new CompressionStream("gzip"))).arrayBuffer());
  // 浏览器写的 MTIME 不一定是 0，它不在 CRC 里，直接清零；FLG 不是 0 就带了文件名之类，没法这样修
  if (gz[3] !== 0) throw new Error("CompressionStream 写的 gzip 头 FLG 不是 0");
  gz.fill(0, 4, 8);
  return gz;
}

/** 3.1～3.2：把按 compression 处理好的字节流切块加密，组成文件。 */
async function seal(stream, { createdAt, salt, noncePrefix, iterations, chunkSize, compression }, keys) {
  if (stream.length === 0) throw new Error("明文流不能是空的");
  const head = ENC.encode(headerText({
    format: FORMAT, created_at: createdAt, kdf: "pbkdf2-sha256+hkdf-sha256", iterations, salt: b64(salt), key_check: b64(keys.check),
    cipher: "aes-256-gcm", nonce_prefix: b64(noncePrefix), chunk_size: chunkSize, compression,
  }));
  const aad = concat([LINE1, head]); // 3.2：AAD 是前两行，不含第二行的 \n
  const out = [aad, ENC.encode("\n")];
  const count = Math.ceil(stream.length / chunkSize);
  for (let i = 0; i < count; i++) {
    const iv = nonce(noncePrefix, i, i === count - 1);
    const c = await S.encrypt({ name: "AES-GCM", iv, additionalData: aad }, keys.key, stream.subarray(i * chunkSize, (i + 1) * chunkSize));
    out.push(new Uint8Array(c));
  }
  return concat(out);
}

/** 3.8 第 2、3 步：第一行是 CURIO-BACKUP/ 加不带前导零的正整数加 \n，数字要是 1。返回第二行开始的位置。 */
function firstLine(f) {
  if (f.length < 15 || !LINE1.subarray(0, 13).every((b, i) => f[i] === b)) throw new Fail("not_curio");
  let i = 13;
  while (i < f.length && f[i] >= 0x30 && f[i] <= 0x39) i++;
  if (i === 13 || f[13] === 0x30 || i >= f.length || f[i] !== 0x0a) throw new Fail("not_curio");
  if (i !== 14 || f[13] !== 0x31) throw new Fail("update"); // 按数字串比，很长的数也只是「不是 1」
  return i + 1;
}

/** 3.8 第 4 步：值对、写法对（按表的顺序重写，逐字节相同）。 @param {Uint8Array} raw */
function parseHeader(raw) {
  let h;
  try { h = JSON.parse(DEC.decode(raw)); } catch { throw new Fail("corrupt"); }
  if (!isObject(h)) throw new Fail("corrupt");
  const it = h.iterations, cs = h.chunk_size;
  const salt = b64Exact(h.salt, 16), check = b64Exact(h.key_check, 16), prefix = b64Exact(h.nonce_prefix, 7);
  const valuesOk = h.format === FORMAT && h.kdf === "pbkdf2-sha256+hkdf-sha256" && h.cipher === "aes-256-gcm"
    && full(RE.ts, h.created_at) && Number.isInteger(it) && it >= 100000 && it <= 10000000
    && salt && check && prefix
    && Number.isInteger(cs) && cs >= 64 && cs <= 16777216 && (cs & (cs - 1)) === 0
    && (h.compression === "gzip" || h.compression === "none");
  // 写法对：挡住重复的键、多余的空格、别的转义、600000.0 这类写法
  if (!valuesOk || !sameBytes(ENC.encode(headerText(h)), raw)) throw new Fail("corrupt");
  return { h, salt: /** @type {Uint8Array} */ (salt), check: /** @type {Uint8Array} */ (check), prefix: /** @type {Uint8Array} */ (prefix) };
}

/**
 * 3.3 读：一个或多个首尾相接的成员，最后一个之后不能再有字节（DecompressionStream 本来就这样）。
 * 边解边数：超过 maxPlain 以后不再留着解出来的字节，只把流解完，好让第 7 步（坏了）排在第 8 步（太大）前面。
 */
async function gunzip(parts, maxPlain) {
  const reader = streamOf(parts).pipeThrough(new DecompressionStream("gzip")).getReader();
  const out = [];
  let n = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      n += value.length;
      if (n <= maxPlain) out.push(value);
      else out.length = 0;
    }
  } catch { throw new Fail("incomplete"); }
  if (n > maxPlain) throw new Fail("too_big");
  return concat(out);
}

/** 3.8 第 9 步：严格 UTF-8，不以 BOM 开头。 @param {Uint8Array} doc */
function utf8(doc) {
  let t;
  try { t = DEC.decode(doc); } catch { throw new Fail("corrupt"); }
  if (t.charCodeAt(0) === 0xfeff) throw new Fail("corrupt");
  return t;
}

/** 3.8 第 2～9 步。keys 是做备份时刚派生的（第 7 节自检可以复用，不再算 PBKDF2；key_check 照样比）。 */
async function open(file, digits, maxPlain, keys) {
  const start = firstLine(file);
  const nl = file.subarray(start, start + MAX_HEADER + 1).indexOf(0x0a); // 第 4097 个字节还不是 \n 就是坏了
  if (nl < 0) throw new Fail("corrupt");
  const headerLine = file.subarray(start, start + nl);
  const { h, salt, check, prefix } = parseHeader(headerLine);
  const k = keys ?? await derive(digits, salt, h.iterations);
  if (!sameBytes(k.check, check)) throw new Fail("wrong_key"); // 第 5 步：先比 key_check，不去解密文
  const aad = file.subarray(0, start + nl);
  const body = file.subarray(start + nl + 1);
  const whole = h.chunk_size + 16;
  if (body.length === 0) throw new Fail("incomplete");
  // 第 6 步：解开全部块以后才往下。读满一整块后面没有字节了，它就是末块
  const parts = [];
  for (let pos = 0, i = 0; pos < body.length; i++) {
    const last = body.length - pos <= whole;
    const n = last ? body.length - pos : whole;
    if (n < 17) throw new Fail("incomplete");
    try {
      parts.push(new Uint8Array(await S.decrypt({ name: "AES-GCM", iv: nonce(prefix, i, last), additionalData: aad }, k.key, body.subarray(pos, pos + n))));
    } catch { throw new Fail("incomplete"); }
    pos += n;
  }
  const doc = h.compression === "gzip" ? await gunzip(parts, maxPlain) : concat(parts); // 第 7 步
  if (doc.length > maxPlain) throw new Fail("too_big"); // 第 8 步
  utf8(doc); // 第 9 步
  return { ok: true, header: h, headerLine: headerLine.slice(), doc };
}

/**
 * 3.1～3.3：明文文档字节 → 文件字节。
 * @param {Uint8Array} doc
 * @param {{digits: string, createdAt: string, salt: Uint8Array, noncePrefix: Uint8Array, iterations?: number, chunkSize?: number, compression: "gzip"|"none"}} p
 */
export async function encodeBackup(doc, { digits, iterations = WRITE_ITERATIONS, chunkSize = WRITE_CHUNK_SIZE, ...p }) {
  const keys = await derive(digits, p.salt, iterations);
  return seal(await compress(doc, p.compression), { ...p, iterations, chunkSize }, keys);
}

/**
 * 3.8 第 2～9 步。
 * @param {Uint8Array} file @param {string} digits 规整好的 6 位数字
 * @param {{maxPlain?: number}} [opts] 解压后大小上限，默认 1 GiB
 */
export async function decodeBackup(file, digits, { maxPlain = MAX_PLAIN } = {}) {
  return attempt(() => open(file, digits, maxPlain));
}

/* ---------------------------------------------------------------- 4. 明文文档 */

/** snapshot 里要写进清单的五部分，按第 1 节的顺序摆好（写和自检共用）。 */
function sections(s) {
  const by = (k) => (a, b) => cmp(a[k], b[k]);
  return {
    inbox: s.inbox,
    receipt: [...s.receipts].sort(by("event_id")),
    import: [...s.imports].sort(by("batch_id")),
    archive: s.archive.map((a) => ({ kind: a.kind, v: a.v })),
    release: [...s.releases].sort(by("release_id")).map((r) => r.raw),
  };
}

/**
 * 第 4 节：snapshot（store.snapshot() 的形状）→ 明文文档字节。遇到 3.7 写不了的值抛 WriteError。
 * @param {any} snapshot @param {{createdAt: string, appCommit: string}} opts
 */
export async function writeManifestDoc(snapshot, { createdAt, appCommit }) {
  const p = sections(snapshot);
  const counts = Object.fromEntries(COUNT_KEYS.map((k) => [k, p[k].length]));
  const { learner_id, device_id } = snapshot.identity;
  const rows = [line({ schema: MANIFEST, created_at: createdAt, learner_id, device_id, app_commit: appCommit, counts })];
  for (const raw of p.inbox) rows.push(line({ t: "inbox", raw }));
  for (const v of p.receipt) rows.push(line({ t: "receipt", v: ordered(v, RECEIPT_KEYS) }));
  for (const v of p.import) rows.push(line({ t: "import", v: ordered(v, IMPORT_KEYS) }));
  for (const a of p.archive) rows.push(line({ t: "archive", v: { kind: a.kind, v: ordered(a.v, a.kind === "receipt" ? RECEIPT_KEYS : IMPORT_KEYS) } }));
  for (const raw of p.release) rows.push(line({ t: "release", raw }));
  const body = ENC.encode(rows.join(""));
  const lines = 1 + COUNT_KEYS.reduce((n, k) => n + counts[k], 0);
  return concat([body, ENC.encode(line({ t: "end", lines, sha256: await sha256Hex(body) }))]);
}

/** schemas/ingest-receipt.schema.json：batch_id、clock_skew_ms 出不出现由 source 决定。 */
function receiptOk(v) {
  if (!isObject(v) || !Object.keys(v).every((k) => RECEIPT_KEYS.includes(k))) return false;
  if (!full(RE.evt, v.event_id) || !full(RE.ts, v.recorded_at)) return false;
  const skew = has(v, "clock_skew_ms");
  if (skew && !Number.isInteger(v.clock_skew_ms)) return false;
  if (v.source === "local") return !has(v, "batch_id") && !skew;
  if (v.source === "sync") return full(RE.syn, v.batch_id) && skew;
  if (v.source === "import") return full(RE.imp, v.batch_id) && !skew;
  return false;
}

/** 5.3 import-record/1（schemas/import-record.schema.json）。 */
function importOk(v) {
  return isObject(v) && exactKeys(v, IMPORT_KEYS) && v.schema === "import-record/1" && full(RE.imp, v.batch_id)
    && full(RE.ts, v.imported_at) && v.source === "backup" && typeof v.partial === "boolean" && full(RE.ts, v.file_created_at)
    && full(RE.dev, v.file_device_id) && b64Exact(v.file_salt, 16) !== null && IMPORT_KEYS.slice(8).every((k) => nonNegInt(v[k]));
}

const RECORD_OK = {
  receipt: receiptOk,
  import: importOk,
  archive: (v) => isObject(v) && exactKeys(v, ["kind", "v"]) && (v.kind === "receipt" ? receiptOk(v.v) : v.kind === "import" && importOk(v.v)),
};

/** 发布包原文 → release_id（要等于 "rel_" + content_hash）；不合格给 null。 @param {string} raw */
function releaseId(raw) {
  let r;
  try { r = JSON.parse(raw); } catch { return null; }
  if (!isObject(r) || !full(RE.rel, r.release_id) || typeof r.content_hash !== "string" || r.release_id !== "rel_" + r.content_hash) return null;
  return r.release_id;
}

const parseOr = (s) => { try { return JSON.parse(s); } catch { return undefined; } };

/** 第 4 节的读和全部检查（3.8 第 9～11 步）。 */
async function readDoc(doc, header) {
  const text = utf8(doc);
  // 第 10 步：第一行解析得出对象而 schema 不认识 →「请先更新」；解析不出来就看不出版本，归第 11 步「坏了」
  const nl = text.indexOf("\n");
  const head = parseOr(nl < 0 ? text : text.slice(0, nl));
  if (isObject(head) && head.schema !== MANIFEST) throw new Fail("update");
  // 第 11 步
  const bad = () => { throw new Fail("corrupt"); };
  if (!text.endsWith("\n")) bad();
  const objs = text.slice(0, -1).split("\n").map((r) => { const o = parseOr(r); return isObject(o) ? o : bad(); }); // 空行解析不出来
  const m = objs[0], c = m.counts;
  if (!exactKeys(m, MANIFEST_KEYS) || m.schema !== MANIFEST || m.created_at !== header.created_at) bad();
  if (!full(RE.lrn, m.learner_id) || !full(RE.dev, m.device_id) || !full(RE.commit, m.app_commit)) bad();
  if (!isObject(c) || !exactKeys(c, COUNT_KEYS) || !COUNT_KEYS.every((k) => nonNegInt(c[k]))) bad();
  const end = objs.at(-1);
  if (objs.length < 2 || end.t !== "end" || !exactKeys(end, ["t", "lines", "sha256"])) bad();
  /** @type {Record<string, any[]>} */
  const part = { inbox: [], receipt: [], import: [], archive: [], release: [] };
  let rank = -1;
  for (const o of objs.slice(1, -1)) {
    const r = COUNT_KEYS.indexOf(o.t); // end 出现在中间也在这里挡掉
    if (r < 0 || r < rank) bad();
    rank = r;
    if (o.t === "inbox" || o.t === "release") {
      if (!exactKeys(o, ["t", "raw"]) || typeof o.raw !== "string") bad();
      part[o.t].push(o.raw);
    } else {
      if (!exactKeys(o, ["t", "v"]) || !RECORD_OK[o.t](o.v)) bad();
      part[o.t].push(o.v);
    }
  }
  if (!COUNT_KEYS.every((k) => part[k].length === c[k])) bad();
  const ids = part.release.map(releaseId);
  if (ids.some((id, i) => id === null || (i > 0 && cmp(ids[i - 1], id) >= 0))) bad(); // 按 release_id 排好、不重复
  if (!Number.isInteger(end.lines) || end.lines !== 1 + COUNT_KEYS.reduce((n, k) => n + c[k], 0)) bad();
  // sha256 按解压后的原始字节算，不先解码再编码
  const body = doc.subarray(0, doc.lastIndexOf(0x0a, doc.length - 2) + 1);
  if (!full(RE.hex64, end.sha256) || end.sha256 !== await sha256Hex(body)) bad();
  return { ok: true, manifest: m, ...part };
}

/**
 * 第 4 节的读（3.8 第 9～11 步）。header 是 decodeBackup 给的文件头（核对 created_at）。
 * @param {Uint8Array} doc @param {{created_at: string}} header
 */
export async function readManifestDoc(doc, header) {
  return attempt(() => readDoc(doc, header));
}

/* ---------------------------------------------------------------- 3.8 第 1～11 步合起来、第 7 节做备份 */

/**
 * 输入框原文 → 结果。
 * @param {Uint8Array} file @param {string} keyInput @param {{maxPlain?: number}} [opts]
 */
export async function readBackup(file, keyInput, { maxPlain } = {}) {
  const k = parseKey(keyInput);
  if (!k.ok) return k;
  const d = await decodeBackup(file, /** @type {string} */ (k.digits), { maxPlain });
  if (!d.ok) return d;
  const { ok, ...backup } = await readManifestDoc(d.doc, d.header);
  return ok ? { ok, header: d.header, backup } : { ok, ...backup };
}

/**
 * 第 7 节：做备份，并马上在内存里从头读一遍，读出的每一部分和快照相同才算做成。
 * random(n) 给 n 个随机字节（先 salt 后 nonce_prefix）；now 是 UTC 时间字符串。
 * @param {any} snapshot
 * @param {{digits: string, now: string, random: (n: number) => Uint8Array, appCommit: string, compression: "gzip"|"none", iterations?: number, chunkSize?: number}} o
 */
export async function buildBackup(snapshot, { digits, now, random, appCommit, compression, iterations = WRITE_ITERATIONS, chunkSize = WRITE_CHUNK_SIZE }) {
  const fail = { ok: false, error: "self_check" };
  let doc;
  try { doc = await writeManifestDoc(snapshot, { createdAt: now, appCommit }); } catch (e) { if (e instanceof WriteError) return fail; throw e; }
  const salt = random(16), noncePrefix = random(7);
  const keys = await derive(digits, salt, iterations);
  const bytes = await seal(await compress(doc, compression), { createdAt: now, salt, noncePrefix, iterations, chunkSize, compression }, keys);
  // 自检只用 1 GiB 这一条上限（3.3）
  const d = await attempt(() => open(bytes, digits, MAX_PLAIN, keys));
  if (!d.ok || !sameBytes(d.doc, doc)) return fail;
  const r = await readManifestDoc(d.doc, d.header);
  if (!r.ok) return fail;
  const { ok, manifest, ...parts } = r;
  if (!sameJson(parts, sections(snapshot))) return fail;
  return { ok: true, bytes, fileName: `curio-backup-${stamp(now)}.curio` };
}

/* ---------------------------------------------------------------- 8、9 */

/** 第 8 节：event_id 按码点排序、各加 \n，SHA-256 的前 8 个十六进制字符。 @param {string[]} eventIds */
export async function fingerprint(eventIds) {
  const text = [...eventIds].sort(cmp).map((id) => id + "\n").join("");
  return (await sha256Hex(ENC.encode(text))).slice(0, 8);
}

/**
 * 第 9 节：被接收事件的原始文字（任意顺序）→ curio-export/1。按事件规格 6.2 的排序键排；原文里的 \r、\n 换成空格，其余原样。
 * @param {string[]} acceptedRaws @param {{exportedAt: string, learnerId: string}} opts
 */
export async function buildExport(acceptedRaws, { exportedAt, learnerId }) {
  const rows = acceptedRaws.map((raw) => ({ raw, e: JSON.parse(raw) }));
  rows.sort(({ e: a }, { e: b }) => cmp(a.occurred_at, b.occurred_at) || cmp(a.device_id, b.device_id)
    || a.device_seq - b.device_seq || cmp(a.event_id, b.event_id));
  const head = line({ format: "curio-export/1", exported_at: exportedAt, learner_id: learnerId, events: rows.length, note: EXPORT_NOTE });
  const body = ENC.encode(head + rows.map((r) => r.raw.replace(/[\r\n]/g, " ") + "\n").join(""));
  return { bytes: concat([body, ENC.encode(line({ sha256: await sha256Hex(body) }))]), fileName: `curio-export-${stamp(exportedAt)}.jsonl` };
}
