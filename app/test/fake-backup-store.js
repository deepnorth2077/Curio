// 设备存储版本 2 的内存假存储（docs/specs/backup.md 5.2）。验收测试的作者写，实现者不改（受保护路径）。
//
// 照规格 5.2 的接口模拟 IndexedDB 的事务语义：每个写方法要么整个生效，要么什么都不写，然后 reject。
// 这里的检查（批次不超过 500 项、原文和收据成对、restoreBegin 核对同一个文件……）是假存储自己的；
// 真的 app/store.js 靠 6b 的浏览器冒烟测试。
//
// 安排故障：store.failOn.restoreBatch = 2  表示从现在起第 2 次 restoreBatch 在提交前中止（什么都不写，reject）。
//          其他写方法同理（restoreBegin、restoreEnd、restoreAbandon、commit……）。数到以后自动清掉。
// store.log 按顺序记下每次写方法的调用：{m: 方法名, args}，测试用它核对调用顺序和参数。
// store.dump() 给出比较用的全部状态：收据按 event_id、导入记录按 batch_id、发布包按 release_id 排序，收件表和 archive 保持顺序
// （形状和 tools/tests/test_backup_ref.py 的 dump_store 一样，backup-restore.json 的 after 就是它）。

const clone = (v) => (v === undefined ? undefined : structuredClone(v));
const tick = () => new Promise((r) => setTimeout(r, 0));
const byKey = (k) => (a, b) => (a[k] < b[k] ? -1 : a[k] > b[k] ? 1 : 0);
const SAME_FILE = ["file_created_at", "file_device_id", "file_salt", "file_learner_id"];

/**
 * @param {object} [snap] 初始状态，store.snapshot() 的形状（缺的部分当成空的）
 */
export function createFakeBackupStore(snap = {}) {
  const state = {
    identity: clone(snap.identity ?? null),
    nextSeq: snap.nextSeq ?? null,
    inbox: clone(snap.inbox ?? []),
    receipts: new Map((snap.receipts ?? []).map((r) => [r.event_id, clone(r)])),
    imports: new Map((snap.imports ?? []).map((r) => [r.batch_id, clone(r)])),
    archive: clone(snap.archive ?? []),
    releases: new Map((snap.releases ?? []).map((r) => [r.release_id, r.raw])),
    recoveryKey: clone(snap.recoveryKey ?? null),
    lastBackup: clone(snap.lastBackup ?? null),
    restoring: clone(snap.restoring ?? null),
  };
  const calls = {};
  const log = [];

  /** 一个事务：先数调用、看要不要中止，再在副本上改，最后整个换上。 */
  async function tx(name, args, body) {
    calls[name] = (calls[name] ?? 0) + 1;
    log.push({ m: name, args: clone(args) });
    await tick();
    const n = store.failOn[name];
    if (n !== undefined) {
      if (n <= 1) {
        delete store.failOn[name];
        throw new Error(`假存储：${name} 事务中止（安排的故障）`);
      }
      store.failOn[name] = n - 1;
    }
    const draft = {
      ...state,
      identity: clone(state.identity),
      inbox: [...state.inbox],
      receipts: new Map(state.receipts),
      imports: new Map(state.imports),
      archive: [...state.archive],
      releases: new Map(state.releases),
      recoveryKey: clone(state.recoveryKey),
      lastBackup: clone(state.lastBackup),
      restoring: clone(state.restoring),
    };
    const out = body(draft);
    Object.assign(state, draft);
    return out;
  }

  const store = {
    state,
    calls,
    log,
    /** @type {Record<string, number>} */
    failOn: {},

    // ---- slice-1 6.2 的方法（不变；loadAll 额外返回 restoring）
    async loadAll() {
      calls.loadAll = (calls.loadAll ?? 0) + 1;
      await tick();
      return { identity: clone(state.identity), nextSeq: state.nextSeq, inbox: [...state.inbox], restoring: clone(state.restoring) };
    },
    init(identity) {
      return tx("init", [identity], (d) => {
        if (d.identity) throw new Error("假存储：已经有身份，事务中止");
        d.identity = { learner_id: identity.learner_id, device_id: identity.device_id };
        d.nextSeq = 1;
      });
    },
    putInbox(raw) {
      return tx("putInbox", [raw], (d) => { d.inbox.push(raw); });
    },
    commit(raw, receipt) {
      return tx("commit", [raw, receipt], (d) => {
        const ev = JSON.parse(raw);
        if (d.nextSeq !== ev.device_seq) throw new Error(`假存储：下一个序号是 ${d.nextSeq}，不是 ${ev.device_seq}，事务中止`);
        d.inbox.push(raw);
        d.receipts.set(ev.event_id, clone(receipt));
        d.nextSeq = ev.device_seq + 1;
      });
    },
    close() {},

    // ---- 5.2 新加的方法
    async snapshot() {
      calls.snapshot = (calls.snapshot ?? 0) + 1;
      await tick();
      return {
        identity: clone(state.identity),
        nextSeq: state.nextSeq,
        inbox: [...state.inbox],
        receipts: [...state.receipts.values()].map(clone),
        imports: [...state.imports.values()].map(clone),
        archive: clone(state.archive),
        releases: [...state.releases].map(([release_id, raw]) => ({ release_id, raw })),
        recoveryKey: clone(state.recoveryKey),
        restoring: clone(state.restoring),
      };
    },
    putRelease(raw, release_id) {
      return tx("putRelease", [raw, release_id], (d) => { if (!d.releases.has(release_id)) d.releases.set(release_id, raw); });
    },
    createRecoveryKey(digits) {
      return tx("createRecoveryKey", [digits], (d) => {
        if (d.recoveryKey) throw new Error("假存储：已经有恢复密钥，事务中止");
        d.recoveryKey = { digits, confirmed_at: null };
      });
    },
    confirmRecoveryKey(at) {
      return tx("confirmRecoveryKey", [at], (d) => {
        if (!d.recoveryKey) throw new Error("假存储：没有恢复密钥，事务中止");
        d.recoveryKey = { ...d.recoveryKey, confirmed_at: at };
      });
    },
    setLastBackup(v) {
      return tx("setLastBackup", [v], (d) => { d.lastBackup = clone(v); });
    },
    restoreBegin(marker, identity, recoveryKey) {
      return tx("restoreBegin", [marker, identity ?? null, recoveryKey ?? null], (d) => {
        if (d.restoring) {
          for (const k of SAME_FILE) {
            if (d.restoring[k] !== marker[k]) throw new Error(`假存储：已经在恢复另一个文件（${k} 不同），事务中止`);
          }
          return; // 不重写
        }
        for (const k of ["batch_id", "started_at", ...SAME_FILE]) {
          if (typeof marker?.[k] !== "string") throw new Error(`假存储：标记缺 ${k}`);
        }
        d.restoring = clone(marker);
        if (identity) d.identity = { learner_id: identity.learner_id, device_id: identity.device_id };
        if (recoveryKey) d.recoveryKey = { digits: recoveryKey.digits, confirmed_at: recoveryKey.confirmed_at };
      });
    },
    restoreBatch(items, ownSeqMax) {
      return tx("restoreBatch", [items, ownSeqMax], (d) => {
        if (!d.restoring) throw new Error("假存储：没有 restoring 标记就写恢复批次");
        if (!Array.isArray(items) || items.length > 500) throw new Error("假存储：一批最多 500 项");
        if (!Number.isInteger(ownSeqMax) || ownSeqMax < 0) throw new Error("假存储：ownSeqMax 要是非负整数");
        for (const it of items) {
          const kinds = ["inbox", "archive", "release"].filter((k) => it[k] !== undefined);
          if (kinds.length !== 1) throw new Error("假存储：每项正好是 inbox、archive、release 之一");
          if (it.inbox !== undefined) {
            if (typeof it.inbox !== "string") throw new Error("假存储：inbox 是原文字符串");
            d.inbox.push(it.inbox);
            if (it.receipt !== undefined) {
              const id = JSON.parse(it.inbox).event_id;
              if (it.receipt.event_id !== id) throw new Error("假存储：收据和原文不是同一条事件");
              d.receipts.set(id, clone(it.receipt));
            }
          } else if (it.archive !== undefined) {
            if (!["receipt", "import"].includes(it.archive.kind)) throw new Error("假存储：archive 的 kind 不对");
            d.archive.push({ kind: it.archive.kind, v: clone(it.archive.v) });
          } else {
            const { release_id, raw } = it.release;
            if (typeof release_id !== "string" || typeof raw !== "string") throw new Error("假存储：release 是 {release_id, raw}");
            if (!d.releases.has(release_id)) d.releases.set(release_id, raw);
          }
        }
        d.nextSeq = Math.max(d.nextSeq ?? 1, ownSeqMax + 1);
      });
    },
    restoreEnd(record) {
      return tx("restoreEnd", [record], (d) => {
        if (!d.restoring) throw new Error("假存储：没有 restoring 标记");
        d.imports.set(record.batch_id, clone(record));
        d.restoring = null;
      });
    },
    restoreAbandon(record) {
      return tx("restoreAbandon", [record], (d) => {
        if (!d.restoring) throw new Error("假存储：没有 restoring 标记");
        if (record.partial !== true) throw new Error("假存储：放弃时写 partial: true 的导入记录");
        d.imports.set(record.batch_id, clone(record));
        d.restoring = null;
      });
    },

    /** 比较用的全部状态（见文件头）。 */
    dump() {
      return structuredClone({
        identity: state.identity,
        nextSeq: state.nextSeq,
        inbox: state.inbox,
        receipts: [...state.receipts.values()].sort(byKey("event_id")),
        imports: [...state.imports.values()].sort(byKey("batch_id")),
        archive: state.archive,
        releases: [...state.releases].map(([release_id, raw]) => ({ release_id, raw })).sort(byKey("release_id")),
        recoveryKey: state.recoveryKey,
        restoring: state.restoring,
      });
    },
  };
  return store;
}
