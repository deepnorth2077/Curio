# 附：竖切片 6a 的模块接口（`docs/specs/backup.md` 的实现约定）

验收测试和实现都照这份写。改接口要先改这份，再改测试。

全部是浏览器原生 ES 模块，JSDoc 类型，不引入依赖；只用 `globalThis.crypto.subtle`、`CompressionStream`/`DecompressionStream`、`TextEncoder`/`TextDecoder`（Node 22 都有）。不碰 DOM、IndexedDB、当前时间、随机数——时间和随机数都由参数传入。字节一律是 `Uint8Array`。

## `app/backup.js`

```js
export const FORMAT = "curio-backup/1";
export const MANIFEST = "backup-manifest/1";
export const WRITE_ITERATIONS = 600000;
export const WRITE_CHUNK_SIZE = 1048576;

// 3.8 的结论代码 → 给家长的话（规格原文）
export const MESSAGES = {
  key_not_digits: "恢复密钥只有数字",
  key_length: "恢复密钥是 6 个数字",
  not_curio: "这不是 Curio 的备份文件",
  update: "这个备份是新版本的 Curio 做的，请先更新 Curio",
  corrupt: "备份文件坏了",
  wrong_key: "恢复密钥不对。请对照纸上的密钥再输一次",
  incomplete: "备份文件坏了，或者不完整。换一个备份文件试试",
  too_big: "备份太大，这台设备放不下",
};

// 2.1 生成：nextU32() 每次给一个 0..2^32-1 的整数
export function generateKey(nextU32) /* → "000007" */;
// 显示：两组，中间一个空格
export function formatKey(digits) /* "482105" → "482 105" */;
// 2.2 规整
export function parseKey(input) /* → {ok:true, digits:"482105"} | {ok:false, error:"key_not_digits"|"key_length"} */;

// 3.1～3.3：明文文档字节 ↔ 文件字节
export async function encodeBackup(doc, {digits, createdAt, salt /*16B*/, noncePrefix /*7B*/, iterations = WRITE_ITERATIONS, chunkSize = WRITE_CHUNK_SIZE, compression /*"gzip"|"none"*/})
  /* → Uint8Array 文件字节 */;
// 3.8 第 2～9 步。maxPlain：解压后大小上限（字节），默认 1 GiB
export async function decodeBackup(file, digits, {maxPlain} = {})
  /* → {ok:true, header /*解析出的文件头对象*/, headerLine /*第二行原始字节，不含 \n*/, doc /*明文 Uint8Array*/}
     | {ok:false, error:"not_curio"|"update"|"corrupt"|"wrong_key"|"incomplete"|"too_big"} */;

// 第 4 节。snapshot 见下；返回明文文档字节
export function writeManifestDoc(snapshot, {createdAt, appCommit}) /* → Uint8Array */;
// 第 4 节的读和全部检查（3.8 第 9～11 步）。header 是 decodeBackup 给的文件头（核对 created_at）
export function readManifestDoc(doc, header)
  /* → {ok:true, manifest, inbox:[raw], receipt:[obj], import:[obj], archive:[{kind, v}], release:[raw]}
     | {ok:false, error:"corrupt"|"update"} */;

// 第 7 节：做备份并自检。random(n) 给 n 个随机字节；now 是 UTC 时间字符串
export async function buildBackup(snapshot, {digits, now, random, appCommit, compression, iterations, chunkSize})
  /* → {ok:true, bytes, fileName /* curio-backup-YYYYMMDD-HHMM.curio，本地时间 UTC+8 */} | {ok:false, error:"self_check"} */;
// 3.8 第 1～11 步合起来：输入框原文 → 结果
export async function readBackup(file, keyInput, {maxPlain} = {})
  /* → {ok:true, header, backup: {manifest, inbox, receipt, import, archive, release}} | {ok:false, error} */;

// 第 8 节：被接收事件的 event_id 列表 → 8 位小写十六进制
export async function fingerprint(eventIds) /* → "3fa9c021" */;
// 第 9 节：被接收事件的原始文字（任意顺序）→ 导出文件字节
export async function buildExport(acceptedRaws, {exportedAt, learnerId}) /* → {bytes, fileName} */;
```

`snapshot`（规格 5.2 `store.snapshot()` 的形状）：

```js
{
  identity: {learner_id, device_id} | null,
  nextSeq: number | null,
  inbox: [raw, …],                // 到达顺序
  receipts: [receipt, …],          // 任意顺序；写清单时按 event_id 码点排序
  imports: [importRecord, …],      // 任意顺序；写清单时按 batch_id 码点排序
  archive: [{kind: "receipt"|"import", v}, …], // 存入顺序
  releases: [{release_id, raw}, …], // 任意顺序；写清单时按 release_id 码点排序
  recoveryKey: {digits, confirmed_at} | null,
  restoring: marker | null,
}
```

## `app/restore.js`

```js
// 6.1、6.2。existing 是 snapshot；backup 是 readBackup 的 {header, backup}；batchId 形如 imp_<ULID>；now 是 UTC 时间字符串
// inputKey 是这次输入并通过 key_check 的 6 位数字（用来按 2.3 决定 restoreBegin 写不写密钥）
export function planRestore(existing, {header, backup}, {batchId, now, inputKey})
  /* → {ok:false, reason:"other_learner"|"other_restore"}
     | {ok:true,
        batchId,                    // 有 restoring 时是标记里的
        marker: {batch_id, started_at, file_created_at, file_device_id, file_salt, file_learner_id},
        identity,                   // 恢复后的身份；需要换时和原来的不同
        changeIdentity: boolean,
        recoveryKey: {digits, confirmed_at} | null,   // 要写进本机的；null 表示不写
        keyMismatch: boolean,       // 2.3 第三种：本机已有确认过的、不一样的
        items: [ {inbox: raw, receipt?, own_seq?} | {archive: {kind, v}} | {release: {release_id, raw}} ],
                                    // own_seq：这条被接收、而且 device_id 是本机时，它的 device_seq
        batches: [ {items, ownSeqMax} ],   // items 每 500 项切一批；ownSeqMax 见规格 5.2（没有就是 0）
        nextSeq,
        record,                     // import-record/1，计数是全部的；partial:false
        report: {accepted, duplicate, not_yet_known, quarantined_new, quarantined_skipped, archived, releases,
                 fingerprint /* 恢复后，8 位十六进制 */, ownEarlier /* 备份里有本机以前的记录 */, noReceipt /* 被接收事件里一条收据都没有的条数 */}
       } */;
// 注意：planRestore 是同步函数，fingerprint 需要 SHA-256，所以 report.fingerprint 由 runRestore 算好再填，planRestore 里给 null。

// 6.3：store 有规格 5.2 的方法；deps.lockLost() 返回 true 时停
export async function runRestore(store, plan, {lockLost})
  /* → {ok:true} | {ok:false, error:"lock_lost"|"store_failed", wrote: number /* 已完成的 restoreBatch 次数 */} */;
// 6.3「不恢复了」
export async function abandonRestore(store, existing, {now})  // 用标记里的 batch_id 写 partial:true 的导入记录，计数全为 0
  /* → {ok:true} | {ok:false, error:"store_failed"} */;
```

`planRestore` 内部用 `kernel/js/log.js` 的 `createLog()` 摄入（和外壳启动重放同一套），用 `kernel/js/validate.js` 的 `SLICE_VERBS` 判断 `not_yet_known`。
