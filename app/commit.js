// 提交一条事件：串行地「检查 → 写库 → 进日志」（竖切片 1 规格 6.2）。不碰 DOM，只通过传进来的 store 碰存储。
//
// 不变量：内存日志只来自两个地方——启动时重放存储，和已经提交成功的事务。除此之外谁也不改它。

/**
 * @typedef {{
 *   loadAll(): Promise<{identity: {learner_id: string, device_id: string}|null, nextSeq: number|null, inbox: string[]}>,
 *   init(identity: {learner_id: string, device_id: string}): Promise<void>,
 *   putInbox(raw: string): Promise<void>,
 *   commit(raw: string, receipt: object): Promise<void>,
 * }} Store
 * @typedef {ReturnType<typeof import("../kernel/js/log.js").createLog>} Log
 */

/** 本机产生的事件被判为不合格时抛的错（外壳显示「出错了」）。 */
export class QuarantinedError extends Error {
  /** @param {string} reason @param {string} detail */
  constructor(reason, detail) {
    super(`这条事件被隔离了（${reason}）：${detail}`);
    this.name = "QuarantinedError";
    this.reason = reason;
  }
}

/** 存储和内存可能不一致、或者已经冻结时抛的错（外壳提示「请刷新页面」）。 */
export class FrozenError extends Error {
  constructor(message = "已经停止记录，请刷新页面") {
    super(message);
    this.name = "FrozenError";
  }
}

/**
 * 外壳只建一个。
 * @param {Store} store
 * @param {Log} log
 * @param {{nextSeq: number}} opts nextSeq 是外壳 loadAll 读到的值
 */
export function createCommitter(store, log, { nextSeq }) {
  let frozen = false;
  let seq = nextSeq;
  /** @type {Promise<unknown>} */
  let tail = Promise.resolve();
  /** @type {Map<string, Promise<"accepted"|"duplicate">>} 正在排队或处理的原始文字 */
  const inflight = new Map();

  /** @param {string} raw @param {object} receipt @returns {Promise<"accepted"|"duplicate">} */
  async function run(raw, receipt) {
    if (frozen) throw new FrozenError();
    const r = log.check(raw);
    if (r.result === "duplicate") return "duplicate";
    if (r.result === "quarantined") {
      await store.putInbox(raw);
      throw new QuarantinedError(r.reason || "invalid", r.detail || "");
    }
    await store.commit(raw, receipt);
    const g = log.ingest(raw);
    if (g.result !== "accepted") {
      frozen = true;
      throw new FrozenError(`事务已提交，但日志没有接收（${g.result}）。请刷新页面`);
    }
    seq += 1;
    return "accepted";
  }

  return {
    /**
     * 排队提交一条原始文字。同一条原始文字还在排队或处理时，返回同一个 Promise。
     * @param {string} raw
     * @param {object} receipt
     * @returns {Promise<"accepted"|"duplicate">}
     */
    submit(raw, receipt) {
      if (frozen) return Promise.reject(new FrozenError());
      const same = inflight.get(raw);
      if (same) return same;
      const p = tail.then(() => run(raw, receipt));
      tail = p.catch(() => {});
      inflight.set(raw, p);
      const clear = () => { if (inflight.get(raw) === p) inflight.delete(raw); };
      p.then(clear, clear);
      return p;
    },
    /** 外壳失去写锁时调用。之后 submit 一律抛错。 */
    freeze() { frozen = true; },
    get frozen() { return frozen; },
    /** 下一条本机事件该用的 device_seq。 */
    get nextSeq() { return seq; },
  };
}
