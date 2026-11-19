// IndexedDB 存取（竖切片 1 规格 6.2；版本 2 见 docs/specs/backup.md 5.1、5.2）。
//
// 对象仓库：
//   inbox     主键是自增的到达序号，值是原始文字。不以 event_id 或 (device_id, device_seq) 为唯一键：
//             冲突的副本和解析不了的原文也要能存下来。事件的唯一约束由日志负责。
//   receipts  收据，主键 event_id。隔离的原文没有收据。
//   meta      "identity" → {learner_id, device_id}；"nextSeq" → 下一条本机事件的 device_seq；
//             版本 2 加："recoveryKey" → {digits, confirmed_at}；"lastBackup" → {at, file_name}；"restoring" → 恢复标记。
//   imports   版本 2 加。本机的导入记录（import-record/1），主键 batch_id。
//   archive   版本 2 加。恢复时从备份带过来的收据和导入记录 {kind, v}，自增主键，只追加。
//   releases  版本 2 加。用过的发布包 {release_id, raw}，主键 release_id。
// 每个方法只用一个事务，只在事务 complete 以后 resolve；abort、error 时 reject。写事务都要求 durability: "strict"。
// 方法的语义和 app/test/fake-backup-store.js 一样。

export const DB_NAME = "curio";
export const DB_VERSION = 2;
const INBOX = "inbox";
const RECEIPTS = "receipts";
const META = "meta";
const IMPORTS = "imports";
const ARCHIVE = "archive";
const RELEASES = "releases";
const SAME_FILE = ["file_created_at", "file_device_id", "file_salt", "file_learner_id"];

/**
 * 升级（规格 5.1）：只加东西，不改旧仓库。按 oldVersion 分支：0 → 建全部仓库；1 → 只建版本 2 新加的三个。
 * 单独导出，好在 Node 里用一个记下调用的假 db 测分支（app/test/store-upgrade.test.js）。
 * @param {{createObjectStore: (name: string, opts?: IDBObjectStoreParameters) => unknown}} db
 * @param {number} oldVersion
 */
export function upgrade(db, oldVersion) {
  if (oldVersion < 1) {
    db.createObjectStore(INBOX, { autoIncrement: true });
    db.createObjectStore(RECEIPTS, { keyPath: "event_id" });
    db.createObjectStore(META);
  }
  if (oldVersion < 2) {
    db.createObjectStore(IMPORTS, { keyPath: "batch_id" });
    db.createObjectStore(ARCHIVE, { autoIncrement: true });
    db.createObjectStore(RELEASES, { keyPath: "release_id" });
  }
}

/**
 * 打开数据库。
 * @param {string} name
 * @param {IDBFactory|undefined} idb
 * @param {() => void} onVersionChange 别的页面要升级数据库时调用（这时连接已经关了）
 * @returns {Promise<IDBDatabase>}
 */
function openDb(name, idb, onVersionChange) {
  return new Promise((resolve, reject) => {
    if (!idb) { reject(new Error("这个浏览器没有 IndexedDB")); return; }
    let req;
    try { req = idb.open(name, DB_VERSION); } catch (e) { reject(e); return; }
    req.onupgradeneeded = (ev) => { upgrade(req.result, ev.oldVersion || 0); };
    req.onsuccess = () => {
      const db = req.result;
      // 别的页面要升级：让路，并按「失去写锁」处理（冻结、只读、提示刷新）
      db.onversionchange = () => { db.close(); try { onVersionChange(); } catch { /* 外壳的事 */ } };
      resolve(db);
    };
    req.onerror = () => reject(req.error || new Error("打不开数据库"));
    req.onblocked = () => reject(new Error("数据库被另一个页面占着"));
  });
}

/**
 * 跑一个事务：body 里发请求，返回 complete 后的结果。body 可以调用 abort(reason) 中止事务。
 * @template T
 * @param {IDBDatabase} db
 * @param {string[]} stores
 * @param {IDBTransactionMode} mode
 * @param {(tx: IDBTransaction, abort: (why: string) => void, set: (v: T) => void) => void} body
 * @returns {Promise<T>}
 */
function run(db, stores, mode, body) {
  return new Promise((resolve, reject) => {
    let tx;
    // 写事务要求落盘以后才 complete（durability: "strict"）；不认这个选项的浏览器会忽略它
    try { tx = mode === "readwrite" ? db.transaction(stores, mode, { durability: "strict" }) : db.transaction(stores, mode); } catch (e) { reject(e); return; }
    /** @type {any} */ let value;
    /** @type {string|null} */ let why = null;
    let settled = false;
    const fail = (err) => { if (!settled) { settled = true; reject(err); } };
    tx.oncomplete = () => { if (!settled) { settled = true; resolve(value); } };
    tx.onabort = () => fail(new Error(why || (tx.error && tx.error.message) || "事务中止"));
    tx.onerror = () => { /* error 之后一定会有 abort；在 abort 里统一 reject */ };
    const abort = (w) => { why = w; try { tx.abort(); } catch { /* 已经结束 */ } };
    try { body(tx, abort, (v) => { value = v; }); } catch (e) { abort(String(e && e.message || e)); }
  });
}

/** 读一个请求的结果，读到以后调用 fn。 @param {IDBRequest} req @param {(v: any) => void} fn */
const got = (req, fn) => { req.onsuccess = () => fn(req.result); };
const copy = (v) => (v == null ? null : structuredClone(v));

/**
 * 打开存储，返回规格 6.2 和 backup.md 5.2 的 store 接口。
 * @param {{name?: string, indexedDB?: IDBFactory, onVersionChange?: () => void}} [opts]
 */
export async function openStore(opts = {}) {
  const db = await openDb(opts.name || DB_NAME, opts.indexedDB || globalThis.indexedDB, opts.onVersionChange || (() => {}));
  return {
    /**
     * 在一个只读事务里读出身份、下一个序号、收件表（按到达序号）、恢复标记。
     * @returns {Promise<{identity: {learner_id: string, device_id: string}|null, nextSeq: number|null, inbox: string[], restoring: any}>}
     */
    loadAll() {
      return run(db, [INBOX, META], "readonly", (tx, _abort, set) => {
        const out = { identity: null, nextSeq: null, inbox: [], restoring: null };
        const m = tx.objectStore(META);
        got(m.get("identity"), (v) => { out.identity = v ? { learner_id: v.learner_id, device_id: v.device_id } : null; });
        got(m.get("nextSeq"), (v) => { out.nextSeq = typeof v === "number" ? v : null; });
        got(m.get("restoring"), (v) => { out.restoring = copy(v); });
        got(tx.objectStore(INBOX).getAll(), (v) => { out.inbox = v; });
        set(out);
      });
    },
    /**
     * 只在没有身份时，在一个事务里写身份和 nextSeq = 1；已经有身份就中止。
     * @param {{learner_id: string, device_id: string}} identity
     */
    init(identity) {
      return run(db, [META], "readwrite", (tx, abort) => {
        const m = tx.objectStore(META);
        got(m.get("identity"), (v) => {
          if (v) { abort("已经有身份"); return; }
          m.put({ learner_id: identity.learner_id, device_id: identity.device_id }, "identity");
          m.put(1, "nextSeq");
        });
      });
    },
    /** 只往收件表追加一条。 @param {string} raw */
    putInbox(raw) {
      return run(db, [INBOX], "readwrite", (tx) => { tx.objectStore(INBOX).add(raw); });
    },
    /**
     * 一个事务里写收件表、收据，并把下一个序号从 device_seq 推进到 device_seq + 1。
     * 事务里先读出当前值，不等于 device_seq 就中止。
     * @param {string} raw
     * @param {{event_id: string}} receipt
     */
    commit(raw, receipt) {
      let seq;
      try { seq = JSON.parse(raw).device_seq; } catch { return Promise.reject(new Error("原始文字不是 JSON")); }
      return run(db, [INBOX, RECEIPTS, META], "readwrite", (tx, abort) => {
        const m = tx.objectStore(META);
        got(m.get("nextSeq"), (v) => {
          if (v !== seq) { abort(`存储里的下一个序号是 ${v}，不是 ${seq}`); return; }
          tx.objectStore(INBOX).add(raw);
          tx.objectStore(RECEIPTS).add(receipt);
          m.put(seq + 1, "nextSeq");
        });
      });
    },

    /* ---------------- 版本 2（backup.md 5.2） ---------------- */

    /**
     * 一个只读事务里读出全部仓库。另外带上 lastBackup（家长页用；不进备份）。
     * @returns {Promise<any>}
     */
    snapshot() {
      return run(db, [INBOX, RECEIPTS, META, IMPORTS, ARCHIVE, RELEASES], "readonly", (tx, _abort, set) => {
        const out = { identity: null, nextSeq: null, inbox: [], receipts: [], imports: [], archive: [], releases: [], recoveryKey: null, restoring: null, lastBackup: null };
        const m = tx.objectStore(META);
        got(m.get("identity"), (v) => { out.identity = v ? { learner_id: v.learner_id, device_id: v.device_id } : null; });
        got(m.get("nextSeq"), (v) => { out.nextSeq = typeof v === "number" ? v : null; });
        got(m.get("recoveryKey"), (v) => { out.recoveryKey = v ? { digits: v.digits, confirmed_at: v.confirmed_at ?? null } : null; });
        got(m.get("restoring"), (v) => { out.restoring = copy(v); });
        got(m.get("lastBackup"), (v) => { out.lastBackup = copy(v); });
        got(tx.objectStore(INBOX).getAll(), (v) => { out.inbox = v; });
        got(tx.objectStore(RECEIPTS).getAll(), (v) => { out.receipts = v; });
        got(tx.objectStore(IMPORTS).getAll(), (v) => { out.imports = v; });
        got(tx.objectStore(ARCHIVE).getAll(), (v) => { out.archive = v.map((a) => ({ kind: a.kind, v: a.v })); });
        got(tx.objectStore(RELEASES).getAll(), (v) => { out.releases = v.map((r) => ({ release_id: r.release_id, raw: r.raw })); });
        set(out);
      });
    },
    /** 没有这个 release_id 才写；有了就保留先存的那份。 @param {string} raw @param {string} release_id */
    putRelease(raw, release_id) {
      return run(db, [RELEASES], "readwrite", (tx) => {
        const s = tx.objectStore(RELEASES);
        got(s.getKey(release_id), (k) => { if (k === undefined) s.add({ release_id, raw }); });
      });
    },
    /** 写 {digits, confirmed_at: null}；已经有密钥就中止。 @param {string} digits */
    createRecoveryKey(digits) {
      return run(db, [META], "readwrite", (tx, abort) => {
        const m = tx.objectStore(META);
        got(m.get("recoveryKey"), (v) => {
          if (v) { abort("已经有恢复密钥"); return; }
          m.put({ digits, confirmed_at: null }, "recoveryKey");
        });
      });
    },
    /** 写 confirmed_at；没有密钥就中止。 @param {string} at */
    confirmRecoveryKey(at) {
      return run(db, [META], "readwrite", (tx, abort) => {
        const m = tx.objectStore(META);
        got(m.get("recoveryKey"), (v) => {
          if (!v) { abort("没有恢复密钥"); return; }
          m.put({ digits: v.digits, confirmed_at: at }, "recoveryKey");
        });
      });
    },
    /** @param {{at: string, file_name: string}} v */
    setLastBackup(v) {
      return run(db, [META], "readwrite", (tx) => { tx.objectStore(META).put({ at: v.at, file_name: v.file_name }, "lastBackup"); });
    },
    /**
     * 没有 restoring 时：写标记，需要时一起写身份、恢复密钥。已经有 restoring 时：不重写，只核对是不是同一个文件，不是就中止。
     * @param {any} marker @param {{learner_id: string, device_id: string}|null} [identity] @param {{digits: string, confirmed_at: string}|null} [recoveryKey]
     */
    restoreBegin(marker, identity, recoveryKey) {
      return run(db, [META], "readwrite", (tx, abort) => {
        const m = tx.objectStore(META);
        got(m.get("restoring"), (cur) => {
          if (cur) {
            for (const k of SAME_FILE) if (cur[k] !== marker[k]) { abort(`已经在恢复另一个文件（${k} 不同）`); return; }
            return; // 不重写
          }
          for (const k of ["batch_id", "started_at", ...SAME_FILE]) {
            if (typeof marker?.[k] !== "string") { abort(`标记缺 ${k}`); return; }
          }
          m.put(structuredClone(marker), "restoring");
          if (identity) m.put({ learner_id: identity.learner_id, device_id: identity.device_id }, "identity");
          if (recoveryKey) m.put({ digits: recoveryKey.digits, confirmed_at: recoveryKey.confirmed_at }, "recoveryKey");
        });
      });
    },
    /**
     * 一批恢复项（最多 500 项），一个事务：原文和它的收据一起写；nextSeq 推进到 max(当前值, ownSeqMax + 1)。
     * @param {any[]} items @param {number} ownSeqMax
     */
    restoreBatch(items, ownSeqMax) {
      if (!Array.isArray(items) || items.length > 500) return Promise.reject(new Error("一批最多 500 项"));
      if (!Number.isInteger(ownSeqMax) || ownSeqMax < 0) return Promise.reject(new Error("ownSeqMax 要是非负整数"));
      return run(db, [INBOX, RECEIPTS, META, ARCHIVE, RELEASES], "readwrite", (tx, abort) => {
        const m = tx.objectStore(META);
        got(m.get("restoring"), (cur) => {
          if (!cur) { abort("没有 restoring 标记就写恢复批次"); return; }
          const inbox = tx.objectStore(INBOX), rc = tx.objectStore(RECEIPTS), ar = tx.objectStore(ARCHIVE), rel = tx.objectStore(RELEASES);
          for (const it of items) {
            const kinds = ["inbox", "archive", "release"].filter((k) => it[k] !== undefined);
            if (kinds.length !== 1) { abort("每项正好是 inbox、archive、release 之一"); return; }
            if (it.inbox !== undefined) {
              if (typeof it.inbox !== "string") { abort("inbox 是原文字符串"); return; }
              inbox.add(it.inbox);
              if (it.receipt !== undefined) {
                let id;
                try { id = JSON.parse(it.inbox).event_id; } catch { id = undefined; }
                if (it.receipt.event_id !== id) { abort("收据和原文不是同一条事件"); return; }
                rc.put(structuredClone(it.receipt));
              }
            } else if (it.archive !== undefined) {
              if (!["receipt", "import"].includes(it.archive.kind)) { abort("archive 的 kind 不对"); return; }
              ar.add({ kind: it.archive.kind, v: structuredClone(it.archive.v) });
            } else {
              const { release_id, raw } = it.release;
              if (typeof release_id !== "string" || typeof raw !== "string") { abort("release 是 {release_id, raw}"); return; }
              got(rel.getKey(release_id), (k) => { if (k === undefined) rel.add({ release_id, raw }); });
            }
          }
          got(m.get("nextSeq"), (n) => { m.put(Math.max(typeof n === "number" ? n : 1, ownSeqMax + 1), "nextSeq"); });
        });
      });
    },
    /** 写导入记录，删掉 restoring。 @param {any} record */
    restoreEnd(record) {
      return run(db, [META, IMPORTS], "readwrite", (tx, abort) => {
        const m = tx.objectStore(META);
        got(m.get("restoring"), (cur) => {
          if (!cur) { abort("没有 restoring 标记"); return; }
          tx.objectStore(IMPORTS).put(structuredClone(record));
          m.delete("restoring");
        });
      });
    },
    /** 写 partial: true 的导入记录，删掉 restoring。 @param {any} record */
    restoreAbandon(record) {
      return run(db, [META, IMPORTS], "readwrite", (tx, abort) => {
        const m = tx.objectStore(META);
        got(m.get("restoring"), (cur) => {
          if (!cur) { abort("没有 restoring 标记"); return; }
          if (record.partial !== true) { abort("放弃时写 partial: true 的导入记录"); return; }
          tx.objectStore(IMPORTS).put(structuredClone(record));
          m.delete("restoring");
        });
      });
    },
    /** 关闭数据库连接。 */
    close() { db.close(); },
  };
}
