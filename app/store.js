// IndexedDB 存取（竖切片 1 规格 6.2）：收件表（收到的原始文字）、收据、设备信息、下一个序号。
//
// 三个对象仓库：
//   inbox     主键是自增的到达序号，值是原始文字。不以 event_id 或 (device_id, device_seq) 为唯一键：
//             冲突的副本和解析不了的原文也要能存下来。事件的唯一约束由日志负责。
//   receipts  收据，主键 event_id。隔离的原文没有收据。
//   meta      "identity" → {learner_id, device_id}；"nextSeq" → 下一条本机事件的 device_seq。
// 每个方法只用一个事务，只在事务 complete 以后 resolve；abort、error 时 reject。

export const DB_NAME = "curio";
export const DB_VERSION = 1;
const INBOX = "inbox";
const RECEIPTS = "receipts";
const META = "meta";

/**
 * 打开数据库。
 * @param {string} [name]
 * @param {IDBFactory} [idb]
 * @returns {Promise<IDBDatabase>}
 */
function openDb(name = DB_NAME, idb = globalThis.indexedDB) {
  return new Promise((resolve, reject) => {
    if (!idb) { reject(new Error("这个浏览器没有 IndexedDB")); return; }
    let req;
    try { req = idb.open(name, DB_VERSION); } catch (e) { reject(e); return; }
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(INBOX)) db.createObjectStore(INBOX, { autoIncrement: true });
      if (!db.objectStoreNames.contains(RECEIPTS)) db.createObjectStore(RECEIPTS, { keyPath: "event_id" });
      if (!db.objectStoreNames.contains(META)) db.createObjectStore(META);
    };
    req.onsuccess = () => {
      const db = req.result;
      // 以后升级数据库版本时，旧页面让路
      db.onversionchange = () => db.close();
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

/**
 * 打开存储，返回规格 6.2 的 store 接口。
 * @param {{name?: string, indexedDB?: IDBFactory}} [opts]
 */
export async function openStore(opts = {}) {
  const db = await openDb(opts.name, opts.indexedDB);
  return {
    /**
     * 在一个只读事务里读出身份、下一个序号、收件表（按到达序号）。
     * @returns {Promise<{identity: {learner_id: string, device_id: string}|null, nextSeq: number|null, inbox: string[]}>}
     */
    loadAll() {
      return run(db, [INBOX, META], "readonly", (tx, _abort, set) => {
        const out = { identity: null, nextSeq: null, inbox: [] };
        const m = tx.objectStore(META);
        const a = m.get("identity");
        a.onsuccess = () => { out.identity = a.result ? { learner_id: a.result.learner_id, device_id: a.result.device_id } : null; };
        const b = m.get("nextSeq");
        b.onsuccess = () => { out.nextSeq = typeof b.result === "number" ? b.result : null; };
        const c = tx.objectStore(INBOX).getAll();
        c.onsuccess = () => { out.inbox = c.result; };
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
        const g = m.get("identity");
        g.onsuccess = () => {
          if (g.result) { abort("已经有身份"); return; }
          m.put({ learner_id: identity.learner_id, device_id: identity.device_id }, "identity");
          m.put(1, "nextSeq");
        };
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
        const g = m.get("nextSeq");
        g.onsuccess = () => {
          if (g.result !== seq) { abort(`存储里的下一个序号是 ${g.result}，不是 ${seq}`); return; }
          tx.objectStore(INBOX).add(raw);
          tx.objectStore(RECEIPTS).add(receipt);
          m.put(seq + 1, "nextSeq");
        };
      });
    },
    /** 关闭数据库连接。 */
    close() { db.close(); },
  };
}
