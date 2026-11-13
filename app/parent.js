// 家长页（docs/specs/backup.md 第 10 节）：上次备份、记录指纹、恢复密钥（2.3）、做备份（第 7 节）、
// 导出成文字（第 9 节）、从备份恢复（6.3）、上次恢复没做完时的两个按钮。
// 只通过 env 拿外壳的状态（存储、日志、写锁），不在模块顶层碰 DOM，Node 里也能导入。
import { MESSAGES, generateKey, formatKey, parseKey, buildBackup, readBackup, fingerprint, buildExport } from "./backup.js";
import { planRestore, runRestore, abandonRestore } from "./restore.js";

/** 规格原话（2.3、6.1、第 7、10 节）。 */
export const TEXT = Object.freeze({
  askWriter: "请在正在用的那个窗口里做",
  keyDiffer: "和刚才的不一样，请对照纸上再看看",
  keyMismatch: "这台设备用的是另一把恢复密钥，两把都要留着",
  otherLearner: "这个备份是另一个孩子的，这台设备上已经有记录了",
  otherRestore: "上次恢复的是另一个备份，请先用它恢复完，或者点『不恢复了』",
  noSpace: "这台设备的空间不够了",
  selfCheck: "备份没做成，请再试一次",
  keepSafe: "备份文件请存在只有你能打开的地方。",
  noSync: "恢复出来的设备和原来的不会自动同步（以后做了同步才会）。演练完以后，请只在一台设备上继续用。",
  mayClear: "这台设备可能会自动清理记录，请常备份",
  unfinished: "上次恢复没做完",
  cleanHint: "以前在别的设备上用过？请家长从备份恢复",
});
const MISMATCH_FLAG = "curio.keyMismatch";
const RESTORED_NOTE = "curio.restored";
const DAY = 864e5;

/** 6.1：干净 = 收件表、收据、导入记录、archive 都是空的，而且没有 restoring。 @param {any} s */
export const isClean = (s) => !s.restoring && [s.inbox, s.receipts, s.imports, s.archive].every((a) => a.length === 0);

/** 指纹显示成两组：3fa9 c021。 @param {string} fp */
export const formatFingerprint = (fp) => `${fp.slice(0, 4)} ${fp.slice(4, 8)}`;

/**
 * 上次备份的说法（第 10 节）。
 * @param {{at: string}|null} last @param {number} nowMs
 * @returns {{text: string, loud: boolean}}
 */
export function lastBackupText(last, nowMs) {
  if (!last) return { text: "还没有备份", loud: true };
  const days = Math.max(0, Math.floor((nowMs - Date.parse(last.at)) / DAY));
  return { text: days === 0 ? "今天" : `${days} 天前`, loud: days > 30 };
}

/**
 * 入口旁边的小圆点（第 10 节、拍板第 4 条）：超过 30 天没备份。从没备份过时，从最早的一条记录算起。
 * @param {{clean: boolean, lastBackup: {at: string}|null, firstEventAt: string|null}} s @param {number} nowMs
 */
export function needsDot(s, nowMs) {
  if (s.clean) return false;
  const from = s.lastBackup ? s.lastBackup.at : s.firstEventAt;
  return !!from && nowMs - Date.parse(from) > 30 * DAY;
}

/** 文件头里的 created_at 用这台设备的时间显示。 @param {string} utc */
function localTime(utc) {
  const d = new Date(utc);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const safeStorage = (kind) => { try { return kind === "local" ? globalThis.localStorage : globalThis.sessionStorage; } catch { return null; } };

/* ============================================================
   页面状态
   ============================================================ */
/** @type {any} */
let pv = { screen: "home" };
let token = 0;
/** 正在恢复（写事务进行中）：不让别的按钮插进来 */
let running = false;

/** 进入家长页时调用：回到首页（正在恢复时不打断）。 @param {{restoreOpen?: boolean}} [o] */
export function resetParent(o = {}) {
  if (running) return;
  freeUrl();
  pv = { screen: "home", restoreOpen: !!o.restoreOpen };
}
function freeUrl() { if (pv && pv.url) { try { URL.revokeObjectURL(pv.url); } catch { /* 无所谓 */ } } }

/**
 * @typedef {{
 *   app: any,
 *   main: HTMLElement,
 *   esc: (s: unknown) => string,
 *   now: () => string,
 *   newBatchId: () => string,
 *   holdsLock: () => boolean,
 *   reload: (toParent: boolean) => void,
 * }} Env
 */

/** 画家长页。 @param {Env} env */
export async function renderParent(env) {
  const my = ++token;
  const { app, main, esc } = env;
  if (!app.store) { main.innerHTML = `<section class="parent"><p>这个浏览器不能记录。</p></section>`; return; }
  const head = (title, back = true) => `<div class="p-head">${back ? `<a class="back" href="#" data-p="tochart" aria-label="回到星图"><span aria-hidden="true">←</span><span>星图</span></a>` : ""}<h1>${esc(title)}</h1></div>`;
  const msg = pv.msg ? `<p class="p-msg" role="alert">${esc(pv.msg)}</p>` : "";
  let html = "";

  if (pv.screen === "home") {
    let snap;
    try { snap = await app.store.snapshot(); } catch (e) { console.error(e); if (my === token) main.innerHTML = `<section class="parent">${head("家长")}<p class="p-msg" role="alert">读不出记录。请刷新页面。</p></section>`; return; }
    const events = app.log ? app.log.events() : [];
    const fp = await fingerprint(events.map((e) => e.event_id));
    let persisted = false;
    try { persisted = !!(navigator.storage && typeof navigator.storage.persisted === "function" && await navigator.storage.persisted()); } catch { persisted = false; }
    if (my !== token) return;
    const clean = isClean(snap);
    const last = lastBackupText(snap.lastBackup, Date.now());
    const mismatch = safeStorage("local")?.getItem(MISMATCH_FLAG) === "1";
    let restored = null;
    try { restored = JSON.parse(safeStorage("session")?.getItem(RESTORED_NOTE) || "null"); safeStorage("session")?.removeItem(RESTORED_NOTE); } catch { restored = null; }
    pv.snap = snap;
    const restoreForm = `<form class="p-form" data-p="restoreForm" autocomplete="off">
        <label class="p-label" for="rf">1. 选备份文件（名字像 curio-backup-….curio）</label>
        <input id="rf" name="file" type="file" class="p-file">
        <label class="p-label" for="rk">2. 输入恢复密钥（6 个数字）</label>
        <input id="rk" name="key" class="p-input" type="text" inputmode="numeric" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" maxlength="20" placeholder="例如 482 105">
        <p id="rmsg" class="p-msg" role="alert" hidden></p>
        <div class="btns start"><button class="btn ink big" type="submit">读备份</button></div>
      </form>`;
    html = `${head("家长")}
      ${snap.restoring ? `<div class="card warn-card"><h2>${TEXT.unfinished}</h2><p>可以选同一个备份文件再恢复一次，也可以不恢复了，就用现在这些。</p>
        <div class="btns start"><button class="btn ink big" type="button" data-p="openRestore">再恢复一次</button><button class="btn big" type="button" data-p="abandon">不恢复了，就用现在这些</button></div></div>` : ""}
      ${restored ? `<div class="card good-card" role="status"><h2>恢复好了</h2><p>${esc(restored)}</p><p class="muted small">请和原来那台设备对一对下面的指纹。</p></div>` : ""}
      ${mismatch ? `<div class="card warn-card"><p><b>${TEXT.keyMismatch}</b></p></div>` : ""}
      ${msg}
      <div class="card">
        <p class="p-stat">上次备份：<b class="${last.loud ? "loud" : ""}">${esc(last.text)}</b></p>
        <p class="p-stat">${events.length ? `记录 ${events.length} 条 · 指纹 <b class="mono">${formatFingerprint(fp)}</b>` : "还没有记录"}</p>
        ${persisted ? "" : `<p class="muted small">${TEXT.mayClear}</p>`}
      </div>
      ${clean ? `<div class="card main-card"><h2>从备份恢复</h2><p>以前在别的设备上用过？选那台设备做的备份文件，输入恢复密钥。</p>${restoreForm}</div>
        <div class="card"><div class="btns start"><button class="btn" type="button" data-p="export">导出成文字</button></div></div>`
      : `<div class="card"><h2>备份</h2>
          <div class="btns start"><button class="btn ink big" type="button" data-p="backup">做一份备份</button></div>
          <p class="small">${TEXT.keepSafe}</p>
          <div class="btns start"><button class="btn" type="button" data-p="export">导出成文字</button>${snap.recoveryKey ? `<button class="btn" type="button" data-p="showKey">再看一次恢复密钥</button>` : ""}</div>
        </div>
        <div class="card">${pv.restoreOpen ? `<h2>从备份恢复</h2>${restoreForm}` : `<p>从另一台设备做的备份里，把记录拿回来。</p><div class="btns start"><button class="btn big" type="button" data-p="openRestore">从备份恢复</button></div>`}</div>`}
      <p class="muted small p-note">${TEXT.noSync}</p>`;
  } else if (pv.screen === "key") {
    html = `${head("恢复密钥")}
      <div class="card">
        <p class="keybig mono" aria-label="恢复密钥 ${esc(pv.digits.split("").join(" "))}">${esc(formatKey(pv.digits))}</p>
        <p>${pv.purpose === "new" ? "请把这 6 个数字抄在两张纸上，放在两个地方。" : "这是这台设备的恢复密钥。"}</p>
        <p>换设备、恢复备份时要输入它。纸条丢了，备份就很难打开。</p>
        ${msg}
        <div class="btns start">
          <button class="btn big" type="button" data-p="print">打印</button>
          ${pv.purpose === "new" ? `<button class="btn ink big" type="button" data-p="copied">抄好了</button>` : `<button class="btn ink big" type="button" data-p="home">好了</button>`}
        </div>
      </div>`;
  } else if (pv.screen === "confirm") {
    html = `${head("确认恢复密钥")}
      <div class="card">
        <form class="p-form" data-p="confirmForm" autocomplete="off">
          <label class="p-label" for="ck">看着纸，把 6 个数字输一遍</label>
          <input id="ck" name="key" class="p-input" type="text" inputmode="numeric" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" maxlength="20">
          ${msg}
          <div class="btns start"><button class="btn ink big" type="submit">确定</button><button class="btn big" type="button" data-p="backToKey">回去再看</button></div>
        </form>
      </div>`;
  } else if (pv.screen === "working") {
    html = `${head(pv.title || "请稍等", false)}<div class="card"><p class="p-busy" role="status">${esc(pv.text)}</p></div>`;
  } else if (pv.screen === "backupDone") {
    html = `${head("备份做好了")}
      <div class="card">
        <p>文件：<span class="mono">${esc(pv.fileName)}</span></p>
        <div class="btns start">
          <a class="btn ink big" data-p="download" href="${esc(pv.url)}" download="${esc(pv.fileName)}">下载备份文件</a>
          ${pv.canShare ? `<button class="btn big" type="button" data-p="share">存到文件或网盘</button>` : ""}
        </div>
        <p class="small">${TEXT.keepSafe}</p>
        ${pv.saved ? `<p class="p-ok" role="status">${esc(pv.saved)}</p>` : ""}
        ${msg}
        <p class="p-stat">${pv.count ? `记录 ${pv.count} 条 · 指纹 <b class="mono">${formatFingerprint(pv.fp)}</b>` : "还没有记录"}</p>
        <p class="muted small">请记下指纹。换设备恢复以后，两边的指纹一样，记录就一样。</p>
        <div class="btns start"><button class="btn" type="button" data-p="home">回到家长页</button></div>
      </div>`;
  } else if (pv.screen === "exportDone") {
    html = `${head("导出好了")}
      <div class="card">
        <p>文件：<span class="mono">${esc(pv.fileName)}</span></p>
        <p class="small">这是文字版，谁都能打开看，不加密，也不能用来恢复。</p>
        <div class="btns start"><a class="btn ink big" href="${esc(pv.url)}" download="${esc(pv.fileName)}">下载文字文件</a><button class="btn" type="button" data-p="home">回到家长页</button></div>
      </div>`;
  } else if (pv.screen === "restoreConfirm") {
    const r = pv.plan.report;
    html = `${head("要恢复的备份")}
      <div class="card">
        <p>这个备份是 <b>${esc(localTime(pv.header.created_at))}</b> 做的。</p>
        <ul class="p-list">
          <li>新的记录 <b>${r.accepted}</b> 条</li>
          <li>重复 <b>${r.duplicate}</b> 条</li>
          ${r.not_yet_known ? `<li>这一版还看不懂的 <b>${r.not_yet_known}</b> 条（更新 Curio 以后会算上）</li>` : ""}
          ${r.quarantined_new ? `<li>有问题、先放到一边的 <b>${r.quarantined_new}</b> 条</li>` : ""}
        </ul>
        ${r.ownEarlier ? `<p>备份里有这台设备以前的记录。</p>` : ""}
        ${pv.plan.changeIdentity ? `<p>恢复以后，这台设备上的星星换成备份里的。</p>` : ""}
        ${pv.plan.keyMismatch ? `<p><b>${TEXT.keyMismatch}</b></p>` : ""}
        ${msg}
        <div class="btns start"><button class="btn ink big" type="button" data-p="doRestore">恢复</button><button class="btn big" type="button" data-p="home">先不恢复</button></div>
      </div>`;
  } else if (pv.screen === "restoreResult") {
    const r = pv.plan.report;
    html = pv.result.ok
      ? `${head("恢复好了", false)}<div class="card good-card" role="status"><p>新的记录 <b>${r.accepted}</b> 条，重复 <b>${r.duplicate}</b> 条。</p><p>点「好」，页面会重新打开。</p>
          <div class="btns start"><button class="btn ink big" type="button" data-p="reloadParent">好</button></div></div>`
      : `${head("恢复没做完", false)}<div class="card warn-card" role="alert"><p>${pv.result.error === "lock_lost" ? "这个窗口停止记录了。" : "写到一半出错了。"}已经写进去的不会坏。</p>
          <p>请刷新页面，然后在家长页点「再恢复一次」，或者「不恢复了，就用现在这些」。</p>
          <div class="btns start"><button class="btn ink big" type="button" data-p="reloadParent">刷新</button></div></div>`;
  }
  if (my !== token) return;
  main.innerHTML = `<section class="parent" aria-label="家长页">${html}</section>`;
  bind(env);
  const focus = /** @type {HTMLElement|null} */ (main.querySelector(pv.screen === "confirm" ? "#ck" : "h1"));
  if (focus) { if (focus.tagName === "H1") focus.setAttribute("tabindex", "-1"); focus.focus({ preventScroll: true }); }
  main.scrollTo({ top: 0 });
}

/* ============================================================
   动作
   ============================================================ */
/** @param {Env} env */
function bind(env) {
  const { main } = env;
  const go = (patch) => { pv = { ...pv, msg: null, ...patch }; renderParent(env); };
  const on = (name, fn) => main.querySelectorAll(`[data-p="${name}"]`).forEach((el) => el.addEventListener("click", (e) => { if (running && name !== "reloadParent") return; fn(e); }));
  on("tochart", (e) => { e.preventDefault(); if (running) return; location.hash = ""; });
  on("home", () => { freeUrl(); go({ screen: "home", url: null }); });
  on("openRestore", () => go({ screen: "home", restoreOpen: true }));
  on("abandon", () => abandonUnfinished(env, (m) => go({ msg: m })));
  on("backup", () => startBackup(env, go));
  on("showKey", () => {
    if (!env.holdsLock()) return go({ msg: TEXT.askWriter });
    const rk = pv.snap && pv.snap.recoveryKey;
    if (rk) go({ screen: "key", digits: rk.digits, purpose: rk.confirmed_at == null ? "new" : "again" });
  });
  on("print", () => printKey(pv.digits));
  on("copied", () => go({ screen: "confirm" }));
  on("backToKey", () => go({ screen: "key" }));
  on("export", () => doExport(env, go));
  on("download", () => markSaved(env, go, "已经开始下载。看到文件存好了，备份就做完了。"));
  on("share", () => shareFile(env, go));
  on("doRestore", () => doRestore(env, go));
  on("reloadParent", () => env.reload(true));
  const cf = /** @type {HTMLFormElement|null} */ (main.querySelector('[data-p="confirmForm"]'));
  if (cf) cf.addEventListener("submit", (e) => { e.preventDefault(); confirmKey(env, go, /** @type {HTMLInputElement} */ (cf.elements.namedItem("key")).value); });
  const rf = /** @type {HTMLFormElement|null} */ (main.querySelector('[data-p="restoreForm"]'));
  if (rf) rf.addEventListener("submit", (e) => { e.preventDefault(); if (!running) readForRestore(env, go, rf); });
}

/** 第 7 节、2.3：做一份备份。还没有确认过的密钥时，先生成（先存后显示）、再确认。 */
async function startBackup(env, go) {
  const store = env.app.store;
  let snap;
  try { snap = await store.snapshot(); } catch { return go({ msg: TEXT.selfCheck }); }
  if (isClean(snap)) return go({ msg: null }); // 干净的设备不做备份（按钮本来就不出现）
  const rk = snap.recoveryKey;
  if (rk && rk.confirmed_at != null) return makeBackup(env, go, snap, rk.digits);
  if (!env.holdsLock()) return go({ msg: TEXT.askWriter });
  let digits = rk ? rk.digits : null;
  if (!digits) {
    const fresh = generateKey(() => crypto.getRandomValues(new Uint32Array(1))[0]);
    try { await store.createRecoveryKey(fresh); } catch { /* 已经有了（别处刚生成）：下面读出来用那一把 */ }
    try { digits = (await store.snapshot()).recoveryKey?.digits ?? null; } catch { digits = null; }
    if (!digits) return go({ msg: "没做成，请再试一次" });
  }
  go({ screen: "key", digits, purpose: "new" });
}

async function confirmKey(env, go, input) {
  const k = parseKey(input);
  if (!k.ok) return go({ msg: MESSAGES[k.error] });
  if (k.digits !== pv.digits) return go({ msg: TEXT.keyDiffer });
  if (!env.holdsLock()) return go({ msg: TEXT.askWriter });
  try {
    await env.app.store.confirmRecoveryKey(env.now());
    const snap = await env.app.store.snapshot();
    return makeBackup(env, go, snap, k.digits);
  } catch { return go({ msg: "没存上，请再试一次" }); }
}

async function makeBackup(env, go, snap, digits) {
  go({ screen: "working", title: "正在做备份", text: "正在做备份……大约要几秒，别关页面。" });
  const app = env.app;
  const sc = app.pack && app.pack.release && app.pack.release.source_commit;
  const appCommit = typeof sc === "string" && /^[0-9a-f]{7,40}$/.test(sc) ? sc : "0000000";
  let r;
  try {
    r = await buildBackup(snap, {
      digits, now: env.now(), random: (n) => crypto.getRandomValues(new Uint8Array(n)), appCommit,
      compression: typeof CompressionStream === "function" ? "gzip" : "none",
    });
  } catch (e) { console.error(e); r = { ok: false }; }
  if (!r.ok) return go({ screen: "home", msg: TEXT.selfCheck });
  const ids = (app.log ? app.log.events() : []).map((e) => e.event_id);
  const blob = new Blob([r.bytes], { type: "application/octet-stream" });
  let canShare = false, file = null;
  try {
    file = new File([r.bytes], r.fileName, { type: "application/octet-stream" });
    canShare = typeof navigator.share === "function" && typeof navigator.canShare === "function" && navigator.canShare({ files: [file] });
  } catch { canShare = false; }
  go({ screen: "backupDone", fileName: r.fileName, url: URL.createObjectURL(blob), file, canShare, count: ids.length, fp: await fingerprint(ids), saved: null });
}

/** 下载或分享开始以后写 lastBackup（只在写锁窗口里写）。 */
async function markSaved(env, go, text) {
  if (env.holdsLock()) {
    try { await env.app.store.setLastBackup({ at: env.now(), file_name: pv.fileName }); } catch { /* 下次再记 */ }
  }
  // 不重画链接：点下载的那一下要照常进行
  const box = env.main.querySelector(".p-ok") || document.createElement("p");
  box.className = "p-ok"; box.setAttribute("role", "status"); box.textContent = text;
  if (!box.parentNode) env.main.querySelector(".card .small")?.after(box);
  pv.saved = text;
}

async function shareFile(env, go) {
  try {
    await navigator.share({ files: [pv.file], title: pv.fileName });
    await markSaved(env, go, "已经交给「文件」或网盘。看到文件存好了，备份就做完了。");
  } catch (e) {
    if (e && e.name === "AbortError") return; // 家长取消了
    go({ msg: "没能打开分享，请点「下载备份文件」" });
  }
}

async function doExport(env, go) {
  const app = env.app;
  try {
    const snap = await app.store.snapshot();
    if (!snap.identity) return go({ msg: "还没有记录" });
    const r = await buildExport(app.log ? app.log.raw() : [], { exportedAt: env.now(), learnerId: snap.identity.learner_id });
    freeUrl();
    go({ screen: "exportDone", fileName: r.fileName, url: URL.createObjectURL(new Blob([r.bytes], { type: "application/octet-stream" })) });
  } catch (e) { console.error(e); go({ msg: "没导出来，请再试一次" }); }
}

/** 6.3 第 1、2 步：读文件 → snapshot → planRestore → 查空间。出错只改表单下面那一句，选好的文件不丢。 */
async function readForRestore(env, go, form) {
  const say = (t) => { const m = /** @type {HTMLElement} */ (form.querySelector("#rmsg")); m.textContent = t; m.hidden = !t; };
  const btn = /** @type {HTMLButtonElement} */ (form.querySelector("[type=submit]"));
  const input = /** @type {HTMLInputElement} */ (form.elements.namedItem("file"));
  const keyInput = /** @type {HTMLInputElement} */ (form.elements.namedItem("key")).value;
  const f = input.files && input.files[0];
  if (!f) return say("请先选一个备份文件");
  if (!env.holdsLock()) return say(TEXT.askWriter);
  btn.disabled = true;
  btn.textContent = "正在读……";
  say("");
  try {
    let free = null;
    try {
      const est = navigator.storage && typeof navigator.storage.estimate === "function" ? await navigator.storage.estimate() : null;
      if (est && typeof est.quota === "number" && typeof est.usage === "number") free = Math.max(0, est.quota - est.usage);
    } catch { free = null; }
    const bytes = new Uint8Array(await f.arrayBuffer());
    const r = await readBackup(bytes, keyInput, { maxPlain: free == null ? undefined : Math.min(2 ** 30, free) });
    if (!r.ok) return say(MESSAGES[r.error] || MESSAGES.corrupt);
    const digits = /** @type {string} */ (parseKey(keyInput).digits);
    const snap = await env.app.store.snapshot();
    const plan = planRestore(snap, { header: r.header, backup: r.backup }, { batchId: env.newBatchId(), now: env.now(), inputKey: digits });
    if (!plan.ok) return say(plan.reason === "other_learner" ? TEXT.otherLearner : TEXT.otherRestore);
    if (free != null) {
      const enc = new TextEncoder();
      let need = 0;
      for (const it of plan.items) need += enc.encode(it.inbox ?? (it.release ? it.release.raw : JSON.stringify(it.archive))).length;
      if (free < need * 3) return say(TEXT.noSpace);
    }
    go({ screen: "restoreConfirm", plan, header: r.header });
  } catch (e) {
    console.error(e);
    say(MESSAGES.corrupt);
  } finally {
    if (btn.isConnected) { btn.disabled = false; btn.textContent = "读备份"; }
  }
}

/** 6.3 第 3、4 步：家长点「恢复」以后才冻结 committer、开始写；结束后显示结果，再重新加载。 */
async function doRestore(env, go) {
  const app = env.app;
  if (!env.holdsLock()) return go({ msg: TEXT.askWriter });
  running = true;
  if (app.session) app.session.committer.freeze();
  go({ screen: "working", title: "正在恢复", text: "正在恢复……别关页面。" });
  let result;
  try { result = await runRestore(app.store, pv.plan, { lockLost: () => app.lockLost }); }
  catch (e) { console.error(e); result = { ok: false, error: "store_failed", wrote: 0 }; }
  if (result.ok) {
    const r = pv.plan.report;
    if (pv.plan.keyMismatch) safeStorage("local")?.setItem(MISMATCH_FLAG, "1");
    safeStorage("session")?.setItem(RESTORED_NOTE, JSON.stringify(`新的记录 ${r.accepted} 条，重复 ${r.duplicate} 条。`));
  }
  go({ screen: "restoreResult", result });
  if (location.hash !== "#parent") location.hash = "#parent";
}

/**
 * 6.3「不恢复了，就用现在这些」。外壳的横幅也用它。
 * @param {Env} env @param {(m: string) => void} say
 */
export async function abandonUnfinished(env, say) {
  const app = env.app;
  if (running) return;
  if (!env.holdsLock()) { say(TEXT.askWriter); return; }
  try {
    const snap = await app.store.snapshot();
    if (!snap.restoring) { env.reload(true); return; }
    running = true;
    if (app.session) app.session.committer.freeze();
    const r = await abandonRestore(app.store, snap, { now: env.now() });
    running = false;
    if (!r.ok) { say("没做成，请刷新页面再试一次"); return; }
    env.reload(true);
  } catch (e) { running = false; console.error(e); say("没做成，请刷新页面再试一次"); }
}

/** 打印：只有密钥、日期和一句说明。 @param {string} digits */
function printKey(digits) {
  const sheet = document.getElementById("printSheet");
  if (!sheet) return;
  const d = new Date();
  sheet.innerHTML = `<h1>Curio 恢复密钥</h1><p class="print-key">${formatKey(digits)}</p><p>${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日</p><p>从备份恢复记录时要输入这 6 个数字。请和备份文件分开放好。</p>`;
  window.print();
}
