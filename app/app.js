// Curio · 竖切片 1 的外壳（规格第 2 节、6.3、6.4）：读发布包 → 拿写锁 → 恢复 → 画星图 → 挑战（选择题、数字题、分数题，
// 提示和看答案，都是先存好事件再显示）→ 点亮（带动效，尊重 reduced-motion）。
// 竖切片 6b（docs/specs/backup.md）：存发布包、「上次恢复没做完」、家长页入口（家长页本身在 parent.js）。
// 读写 IndexedDB、取当前时间、生成 ULID、洗牌都在这里做，结果作为参数交给内核和引擎。
import { createLog } from "../kernel/js/log.js";
import { projectMastery, groupAttempts, attemptRule } from "../kernel/js/mastery.js";
import { createUlid } from "../kernel/js/ulid.js";
import { startQuiz, step, DEFAULT_FEEDBACK } from "../engine/js/quiz.js";
import { openStore } from "./store.js";
import { openSession, localReceipt, assemble, guardDeps, LockLostError } from "./session.js";
import { FrozenError } from "./commit.js";
import { mountExploration, supportedExploration, stationCount } from "./exploration.js";
import { Sk } from "./sketch.js";
import { buildChart, overviewSvg, placeChartLabels, animateOverview, nearestCons, constellationLayout, constellationSvg,
  legendHtml, consName, consId, BAND_NAME } from "./starchart.js";
import { metroLayout, metroSvg, metroScroll } from "./metro.js";
import { aliasIndex, treeHtml, searchPoints, noteHtml } from "./explorer.js";
import { renderParent, resetParent, abandonUnfinished, isClean, needsDot, TEXT as PTEXT,
  refreshProfile, currentGradeOf, needsProfileHint, PROFILE_TEXT } from "./parent.js";

/** 这个外壳实现的引擎等级（内容规格 3.8）。挑战的三种答案（选择、数字、分数）都支持；讲解、反思还没做，点开显示「这个还在做」。 */
export const ENGINE_LEVEL = 1;
/** 这个外壳认得的活动契约版本（内容规格 3.8）。清单的 contracts 里有别的版本时，提示「需要更新」。 */
export const KNOWN_CONTRACTS = ["activity/1.1"];
/** 发布包的位置：部署时 release/ 和 app/ 同级（规格第 2、8 节）。 */
const RELEASE_URL = new URL("../release/release.json", import.meta.url);

/* ============================================================
   发布包：规范 JSON、哈希、核对（规格第 2 节；内容规格 6.2、6.3）
   ============================================================ */

/** 按 Unicode 码点比较两个字符串（不用 localeCompare）。 @param {string} a @param {string} b */
export function cmpCodePoints(a, b) {
  const x = [...a], y = [...b];
  const n = Math.min(x.length, y.length);
  for (let i = 0; i < n; i++) {
    const d = /** @type {number} */ (x[i].codePointAt(0)) - /** @type {number} */ (y[i].codePointAt(0));
    if (d) return d;
  }
  return x.length - y.length;
}

/**
 * 规范 JSON：递归地给每一层对象的键按码点排序，数组保持原顺序，不留空白，字符串用 JSON.stringify 写。
 * 清单里只允许字符串和安全整数（内容规格 6.2）；别的值抛错。
 * @param {unknown} v
 * @returns {string}
 */
export function canonicalJson(v) {
  if (typeof v === "string") return JSON.stringify(v);
  if (typeof v === "number") {
    if (!Number.isSafeInteger(v)) throw new TypeError(`清单里只允许安全整数：${v}`);
    return String(v);
  }
  if (Array.isArray(v)) return "[" + v.map(canonicalJson).join(",") + "]";
  if (v !== null && typeof v === "object") {
    return "{" + Object.keys(v).sort(cmpCodePoints).map((k) => JSON.stringify(k) + ":" + canonicalJson(v[k])).join(",") + "}";
  }
  throw new TypeError(`清单里不该有这种值：${String(v)}`);
}

/** @param {ArrayBuffer|Uint8Array} bytes @returns {Promise<string>} 小写十六进制 */
export async function sha256Hex(bytes) {
  const d = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export class ReleaseError extends Error {
  /** @param {"broken"|"update"} kind @param {string} message */
  constructor(kind, message) { super(message); this.name = "ReleaseError"; this.kind = kind; }
}

/**
 * 核对清单本身：content_hash 等于规范 JSON 的 SHA-256，release_id 等于 rel_ + content_hash。
 * @param {any} rel
 */
export async function verifyManifest(rel) {
  if (!rel || typeof rel !== "object" || rel.schema !== "release/1") throw new ReleaseError("broken", "不是 release/1 清单");
  if (!Number.isSafeInteger(rel.engine_min)) throw new ReleaseError("broken", "engine_min 不是整数");
  if (rel.engine_min > ENGINE_LEVEL) throw new ReleaseError("update", `需要 ${rel.engine_min} 级引擎`);
  let text;
  try {
    const fields = { engine_min: rel.engine_min, contracts: rel.contracts, nodes: rel.nodes, activities: rel.activities, assets: rel.assets };
    if ("catalog" in rel) fields.catalog = rel.catalog;
    text = canonicalJson(fields);
  } catch (e) { throw new ReleaseError("broken", String(e && e.message)); }
  const h = await sha256Hex(new TextEncoder().encode(text));
  if (h !== rel.content_hash) throw new ReleaseError("broken", "content_hash 对不上");
  if (rel.release_id !== "rel_" + rel.content_hash) throw new ReleaseError("broken", "release_id 对不上");
  if (!Array.isArray(rel.contracts) || !rel.contracts.every((c) => typeof c === "string")) throw new ReleaseError("broken", "contracts 不是字符串列表");
  const unknown = rel.contracts.filter((c) => !KNOWN_CONTRACTS.includes(c));
  if (unknown.length) throw new ReleaseError("update", `不认得的契约：${unknown.join("、")}`);
}

/**
 * 读发布清单中列出的文件；HTML 和 JSON 都先逐字节核对，再解码。
 * @param {URL} base release.json 的地址
 * @param {{path: string, bytes: number, sha256: string}} j
 * @param {typeof fetch} fetchFn
 */
async function fetchVerifiedText(base, j, fetchFn) {
  if (!j || typeof j.path !== "string") throw new ReleaseError("broken", "清单里缺少文件路径");
  const res = await fetchFn(new URL(j.path, base), { cache: "no-cache" });
  if (!res.ok) throw new ReleaseError("broken", `读不到 ${j.path}`);
  const buf = new Uint8Array(await res.arrayBuffer());
  if (buf.byteLength !== j.bytes) throw new ReleaseError("broken", `${j.path} 的字节数对不上`);
  if ((await sha256Hex(buf)) !== j.sha256) throw new ReleaseError("broken", `${j.path} 的哈希对不上`);
  try { return new TextDecoder("utf-8", { fatal: true }).decode(buf); }
  catch { throw new ReleaseError("broken", `${j.path} 不是 UTF-8 文件`); }
}

async function fetchVerifiedJson(base, j, fetchFn) {
  const text = await fetchVerifiedText(base, j, fetchFn);
  try { return JSON.parse(text); }
  catch { throw new ReleaseError("broken", `${j.path} 不是合法的 JSON`); }
}

/**
 * 读发布包并逐个核对。任何一处对不上都抛 ReleaseError。
 * @param {URL} [url]
 * @param {typeof fetch} [fetchFn]
 * @returns {Promise<{release: any, raw: string, nodes: any[], catalog?: any, activities: Map<string, {entry: any, def: any|null, module?: {manifest:any, html:string}}>}>}
 */
export async function loadRelease(url = RELEASE_URL, fetchFn = fetch) {
  let rel, raw;
  try {
    const res = await fetchFn(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(String(res.status));
    // 留着原文：拿着写锁时原样存进 releases（backup.md 5.1）
    raw = new TextDecoder("utf-8", { fatal: true }).decode(await res.arrayBuffer());
    rel = JSON.parse(raw);
  } catch { throw new ReleaseError("broken", "读不到 release.json"); }
  await verifyManifest(rel);
  const nodes = [];
  for (const n of rel.nodes) {
    const def = await fetchVerifiedJson(url, n.json, fetchFn);
    if (!def || def.id !== n.id) throw new ReleaseError("broken", `知识点 ${n.id} 对不上`);
    nodes.push(def);
  }
  /** @type {Map<string, {entry: any, def: any|null, module?: {manifest:any, html:string}}>} */
  const activities = new Map();
  for (const a of rel.activities) {
    if (supportedExploration(a.id)) {
      const dir = "content/activities/" + a.id + "/";
      const manifestFile = a.files.find((f) => f.path === dir + "manifest.yaml");
      const htmlFile = a.files.find((f) => f.path === dir + "index.html");
      if (a.kind !== "simulation" || !manifestFile || manifestFile.json?.path !== manifestFile.path + ".json" || !htmlFile) {
        throw new ReleaseError("broken", `探索 ${a.id} 的文件不完整`);
      }
      const [manifest, html] = await Promise.all([
        fetchVerifiedJson(url, manifestFile.json, fetchFn), fetchVerifiedText(url, htmlFile, fetchFn)
      ]);
      const targets = nodes.filter((n) => n.activities?.includes(a.id));
      if (manifest?.id !== a.id || manifest.version !== a.version || manifest.type !== a.kind ||
          manifest.contract !== "activity/1.1" || manifest.entry !== "index.html" || manifest.pedagogy !== "explain" ||
          !Array.isArray(manifest.emits) || !Array.isArray(manifest.targets) ||
          !targets.length || !targets.every((n) => manifest.targets.includes(n.id))) {
        throw new ReleaseError("broken", `探索 ${a.id} 和发布清单或所属星对不上`);
      }
      activities.set(a.id, { entry: a, def: null, module: { manifest, html } });
      continue;
    }
    let def = null;
    for (const f of a.files) {
      if (!f.json) continue;
      const v = await fetchVerifiedJson(url, f.json, fetchFn);
      if (/\/activity\.yaml$/.test(f.path)) def = v;
    }
    if (def && def.id !== a.id) throw new ReleaseError("broken", `活动 ${a.id} 对不上`);
    activities.set(a.id, { entry: a, def });
  }
  const result = { release: rel, raw, nodes, activities };
  if ("catalog" in rel) {
    const entry = rel.catalog;
    if (entry?.path !== "content/catalog/points.yaml" || entry.json?.path !== entry.path + ".json") {
      throw new ReleaseError("broken", "知识点目录的文件不完整");
    }
    result.catalog = await fetchVerifiedJson(url, entry.json, fetchFn);
  }
  return result;
}


/* ============================================================
   小工具
   ============================================================ */
const $ = (sel) => /** @type {HTMLElement} */ (document.querySelector(sel));
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
/** 文字里的 1/4 排成上下结构（内容规格 3.7）。 */
const rich = (s) => esc(s).replace(/(\d+)\/(\d+)/g, (_m, a, b) => `<span class="frac" role="img" aria-label="${b}分之${a}"><span>${a}</span><span>${b}</span></span>`);
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

const ulid = createUlid();
const rand10 = () => crypto.getRandomValues(new Uint8Array(10));
const ids = {
  learner: () => "lrn_" + ulid(Date.now(), rand10()),
  device: () => "dev_" + ulid(Date.now(), rand10()),
  event: () => "evt_" + ulid(Date.now(), rand10()),
  attempt: () => "att_" + ulid(Date.now(), rand10()),
  caregiver: () => "cg_" + ulid(Date.now(), rand10()),
};
const now = () => new Date().toISOString();
/** 洗牌（活动的 shuffle 为真时）。 */
function shuffled(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const r = crypto.getRandomValues(new Uint32Array(1))[0];
    const j = r % (i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/* ============================================================
   手绘图：星星和配图
   ============================================================ */
function starPoints(cx, cy, R, r, rot = -Math.PI / 2) {
  const pts = [];
  for (let i = 0; i < 10; i++) { const a = rot + i * Math.PI / 5, rr = i % 2 ? r : R; pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]); }
  return pts;
}
/** 一颗星的 SVG。state：untouched / explored / lit。 */
function starSvg(state, seed, size) {
  const pts = starPoints(50, 52, 38, 16);
  let body = "";
  if (state === "lit") {
    body += `<path class="star-fill" d="${Sk.area(starPoints(52, 55, 38, 16))}"/>`;
    body += `<path class="k" d="${Sk.poly(pts, seed, true, .8)}"/>`;
    for (let i = 0; i < 8; i++) {
      const a = i / 8 * Math.PI * 2 + .2;
      body += `<path class="k1 ray" d="${Sk.line(50 + Math.cos(a) * 44, 52 + Math.sin(a) * 44, 50 + Math.cos(a) * 49, 52 + Math.sin(a) * 49, seed + 20 + i, .4)}"/>`;
    }
  } else if (state === "explored") {
    body += `<path class="star-half" d="${Sk.area([0, 9, 8, 7, 6, 5].map((i) => pts[i]))}" opacity=".7"/>`;
    body += `<path class="k" d="${Sk.poly(pts, seed, true, .8)}"/>`;
  } else {
    body += `<path class="fp" d="${Sk.area(pts)}"/>`;
    body += `<path class="kq" stroke-dasharray="3 4" d="${Sk.poly(pts, seed, true, .8)}"/>`;
  }
  return `<svg viewBox="0 0 100 100" width="${size}" height="${size}" aria-hidden="true">${body}</svg>`;
}
const wedge = (cx, cy, r, a0, a1) => {
  const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0), x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
  return `M${cx} ${cy}L${x0.toFixed(1)} ${y0.toFixed(1)}A${r} ${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}Z`;
};
/** 题目配图（内容规格 3.6）。画不了的返回占位。 */
function figureSvg(fig, seed = 7) {
  if (!fig || typeof fig !== "object") return "";
  let inner = "", vb = "0 0 200 120", label = "配图";
  if (fig.type === "pie") {
    const n = fig.parts, k = fig.shaded, cx = 100, cy = 60, r = 48;
    for (let i = 0; i < k; i++) inner += `<path class="fig-shade" d="${wedge(cx, cy, r, -Math.PI / 2 + i / n * 2 * Math.PI, -Math.PI / 2 + (i + 1) / n * 2 * Math.PI)}"/>`;
    inner += `<path class="k" d="${Sk.ellipse(cx, cy, r, r, seed, .5)}"/>`;
    for (let i = 0; i < n; i++) { const a = -Math.PI / 2 + i / n * 2 * Math.PI; inner += `<path class="k1" d="${Sk.line(cx, cy, cx + Math.cos(a) * r, cy + Math.sin(a) * r, seed + 3 + i, .4)}"/>`; }
    label = `一个圆，分成 ${n} 份，涂色 ${k} 份`; // 只描述形状：「平均」「不一样大」可能就是题目要问的
  } else if (fig.type === "rect" || fig.type === "rect-unequal") {
    const widths = fig.type === "rect" ? Array(fig.parts).fill(1) : fig.widths;
    const shaded = fig.type === "rect" ? [...Array(fig.shaded).keys()] : fig.shaded;
    const vertical = fig.type === "rect" && fig.direction === "v";
    const X = 20, Y = 20, W = 160, H = 80, sum = widths.reduce((a, b) => a + b, 0);
    let at = 0;
    widths.forEach((w, i) => {
      const a = at / sum, b = (at + w) / sum; at += w;
      const box = vertical ? [X, Y + a * H, W, (b - a) * H] : [X + a * W, Y, (b - a) * W, H];
      if (shaded.includes(i)) inner += `<path class="fig-shade" d="${Sk.area([[box[0], box[1]], [box[0] + box[2], box[1]], [box[0] + box[2], box[1] + box[3]], [box[0], box[1] + box[3]]])}"/>`;
      if (i > 0) inner += `<path class="k1" d="${vertical ? Sk.line(X, box[1], X + W, box[1], seed + 10 + i, .4) : Sk.line(box[0], Y, box[0], Y + H, seed + 10 + i, .4)}"/>`;
    });
    inner += `<path class="k" d="${Sk.rect(X, Y, W, H, seed, .5)}"/>`;
    label = `一个长方形，分成 ${widths.length} 份，涂色 ${shaded.length} 份`;
  } else if (fig.type === "number-line") {
    const from = Number(fig.from), to = Number(fig.to), stp = Number(fig.step) || 1;
    const x = (v) => 20 + (v - from) / ((to - from) || 1) * 160;
    vb = "0 0 200 70";
    inner += `<path class="k" d="${Sk.line(14, 34, 196, 34, seed, .4)}"/><path class="k1" d="${Sk.line(196, 34, 190, 30, seed + 1, .3) + Sk.line(196, 34, 190, 38, seed + 2, .3)}"/>`;   // 箭头在最后一个刻度（x=180）右边，不挨着
    const n = Math.min(60, Math.round((to - from) / stp));
    for (let i = 0; i <= n; i++) inner += `<path class="k1" d="${Sk.line(x(from + i * stp), 29, x(from + i * stp), 39, seed + 5 + i, .3)}"/>`;
    for (const m of fig.marks || []) inner += `<text x="${x(Number(m.at)).toFixed(1)}" y="58" text-anchor="middle" class="fig-txt">${esc(m.label ?? m.at)}</text>`;
    label = "一条数轴";
  } else {
    return `<p class="fig-missing">（这张图还没准备好）</p>`;
  }
  return `<svg class="fig" viewBox="${vb}" role="img" aria-label="${esc(label)}">${inner}</svg>`;
}

/* ============================================================
   外壳状态
   ============================================================ */
const app = {
  /** @type {"loading"|"readonly"|"recovering"|"writable"|"unfinished"|"stopped"} */ mode: "loading",
  /** @type {null|"busy"|"nolock"|"lost"|"nostore"} */ why: null,
  /** @type {Awaited<ReturnType<typeof loadRelease>>|null} */ pack: null,
  /** @type {Awaited<ReturnType<typeof openStore>>|null} */ store: null,
  /** @type {Awaited<ReturnType<typeof openSession>>|null} */ session: null,
  /** @type {ReturnType<typeof createLog>|null} */ log: null,
  hasIdentity: false,
  /** 失去过写锁（失锁以后这个页面不再写任何东西，要刷新） */ lockLost: false,
  /** 「再试一次」正在进行 */ relocking: false,
  /** @type {any} */ mastery: null,
  /** 正在做的挑战 */ quiz: /** @type {null|{q: any, def: any, node: any, content: any, attempt_id: string, startedMs: number, cur: null|{id: number, raw: string, receipt: object}, busy: boolean, error: any, solved: string|null, wrongBy: Record<string, string[]>, litBefore: boolean}} */ (null),
  /** 星球笔记打开着的那颗星（#233）：星图、地铁、索引里同步高亮；null 是没打开 */ note: /** @type {string|null} */ (null),
  /** 星图正在看的星座（详情视图），null 是总览 */ chartZoom: /** @type {string|null} */ (null),
  /** 首页是星图还是知识地铁（#233）：URL 的 #metro 记住它；从星、站进去的活动退出来回到这里 */ home: /** @type {"chart"|"metro"} */ ("chart"),
  /** 地铁上只看哪一条线（点左边的线名），null 是全部 */ metroLine: /** @type {string|null} */ (null),
  exploration: /** @type {null|{host: ReturnType<typeof mountExploration>|null, leaving: Promise<boolean>|null, failed:boolean}} */ (null),
  view: /** @type {"chart"|"quiz"|"exploration"|"parent"} */ ("chart"),
  notice: /** @type {string|null} */ (null),
  /** 打开时读到的：干净的设备（backup.md 6.1）、上次备份、最早一条记录的时间（家长入口的小圆点） */
  clean: false,
  /** @type {{at: string, file_name: string}|null} */ lastBackup: null,
  /** @type {string|null} */ firstEventAt: null,
  /** 舰长资料的投影 profile/1（docs/specs/profile.md 第 3、5 节）：启动时和每次摄入以后重算。还没有日志时是 null。 */
  /** @type {ReturnType<typeof import("../kernel/js/profile.js").projectProfile>|null} */ profile: null,
  /** 当前年级 1～12，或 null（没填、还没上小学、已经毕业）。第 2 步画星图时用。 @param {number} [nowMs] */
  currentGrade: (nowMs = Date.now()) => currentGrade(nowMs),
};

/**
 * 当前年级（docs/specs/profile.md 第 5 节）：app.profile 里没有资料，或者算出的年级不在 1～12 时是 null。
 * @param {number} nowMs 时间戳（毫秒）
 * @returns {number|null}
 */
export function currentGrade(nowMs) {
  return currentGradeOf(app.profile ? app.profile.profile : null, nowMs);
}

/** 拿着写锁、可以写存储（「上次恢复没做完」时也拿着锁，只是不能开始挑战）。 */
const holdsLock = () => (app.mode === "writable" || app.mode === "unfinished") && !app.lockLost;

/** 给家长页的外壳接口。 */
const parentEnv = () => ({
  app, main: $("#main"), esc, now, holdsLock,
  ids: guardDeps({ ids, now }, () => app.lockLost).ids,
  newBatchId: () => "imp_" + ulid(Date.now(), rand10()),
  reload: (toParent) => { if (toParent) location.hash = "#parent"; location.reload(); },
});

/** 按当前的 view 重画。 */
function renderCurrent() {
  if (app.view === "quiz" && app.quiz) renderQuiz();
  else if (app.view === "exploration" && app.exploration) return; // 保留已装入的实物和当前手势。
  else if (app.view === "parent") { syncNav(); renderExplorer(); renderParent(parentEnv()); }
  else renderChart();
}

function recompute() {
  app.mastery = app.log ? projectMastery(app.log.events()) : null;
  if (app.log) refreshProfile(app); else app.profile = null;
}
const nodeState = (id) => (app.mastery && app.mastery.nodes[id] ? app.mastery.nodes[id].state : "untouched");

/* ============================================================
   横幅（只读、需要刷新、出错）
   ============================================================ */
function renderBanner() {
  const b = $("#banner");
  let html = "";
  if (app.mode === "readonly") {
    if (app.why === "busy") html = `<p><b>另一个窗口正在用。</b>这里只能看。关掉那个窗口以后，点「再试一次」。</p><button class="btn" data-act="relock" type="button">再试一次</button>`;
    else if (app.why === "nolock") html = `<p><b>这个浏览器不能记录。</b>这里只能看，换一个新一点的浏览器试试。</p>`;
    else if (app.why === "nostore") html = `<p><b>这个浏览器不能记录。</b>可能开着无痕模式，请家长看一看。</p>`;
    else if (app.why === "lost") html = `<p><b>请刷新页面。</b>刚才离开了一会儿，刷新以后接着玩，星星不会变。</p><button class="btn ink" data-act="reload" type="button">刷新</button>`;
  } else if (app.mode === "unfinished") {
    // backup.md 6.3：上次恢复没做完，不进「可以写」
    html = `<p><b>${PTEXT.unfinished}。</b>请家长选一个：</p><span class="banner-btns"><button class="btn ink" data-act="reRestore" type="button">再恢复一次</button><button class="btn" data-act="abandon" type="button">不恢复了，就用现在这些</button></span><p id="bannerMsg" class="small" role="alert" hidden></p>`;
  }
  b.innerHTML = html;
  b.hidden = !html;
  const r = b.querySelector('[data-act="relock"]');
  if (r) r.addEventListener("click", relock);
  const l = b.querySelector('[data-act="reload"]');
  if (l) l.addEventListener("click", () => location.reload());
  const rr = b.querySelector('[data-act="reRestore"]');
  if (rr) rr.addEventListener("click", () => {
    resetParent({ restoreOpen: true });
    app.view = "parent"; // 先设好：hashchange 看到已经在家长页，就不再把表单收起来
    if (location.hash === "#parent") renderCurrent(); else location.hash = "#parent";
  });
  const ab = b.querySelector('[data-act="abandon"]');
  if (ab) ab.addEventListener("click", () => abandonUnfinished(parentEnv(), (m) => { const e = document.getElementById("bannerMsg"); if (e) { e.textContent = m; e.hidden = false; } }));
}

/** 整页的提示（内容包坏了、需要更新、出错）。 */
function renderStop(title, text) {
  app.mode = "stopped";
  $("#banner").hidden = true;
  $("#main").innerHTML = `<section class="stop"><div class="stop-art">${starSvg("untouched", 5, 120)}</div><h1>${esc(title)}</h1>${text ? `<p>${esc(text)}</p>` : ""}</section>`;
}

/* ============================================================
   星图（#230）：画法在 starchart.js，这里只接数据和点选
   ============================================================ */
/** 星图的数据：目录 + 已发布卡 + 掌握度投影 + 当前年级。 */
function chartModel() {
  return buildChart({ catalog: app.pack ? app.pack.catalog : null, nodes: app.pack ? app.pack.nodes : [], mastery: app.mastery, grade: app.currentGrade(Date.now()) });
}
let stopFloat = () => {};
let chartWidth = 0;

function renderChart() {
  app.view = "chart";
  stopFloat();
  syncNav();
  const main = $("#main");
  renderExplorer();
  if (app.mode === "readonly" && !app.hasIdentity) { main.innerHTML = ""; renderNote(); return; }
  const model = chartModel();
  // 笔记先放好：宽屏上它占右边一栏，星图要按剩下的宽度排
  renderNote(model);
  if (app.home === "metro") { renderMetro(main, model); return; }
  const c = app.chartZoom ? model.consById.get(app.chartZoom) : null;
  if (c) renderConstellation(main, model, c);
  else { app.chartZoom = null; renderOverview(main, model); }
}

/** URL 的 hash → 首页是哪一个（#metro 是地铁，其余是星图）。 @param {string} hash */
export const homeOfHash = (hash) => (hash === "#metro" ? "metro" : "chart");
/** 返回按钮上的字。 */
const homeName = () => (app.home === "metro" ? "地铁" : "星图");
/**
 * 导航上标出当前页（星图、地铁，或家长页的锁）；家长入口的两个提醒挂在锁上：
 * 30 天没备份是一个小圆点，「还没填舰长资料」在工具条上是锁旁的小字（手机上是小圆点），读屏读出原话（profile.md 第 4 节：和备份提醒放在同一处）。
 */
function syncNav() {
  const cur = app.view === "parent" ? "parent" : app.home;
  for (const a of document.querySelectorAll(".ribbon [data-view], .bottomnav [data-view]")) {
    a.setAttribute("aria-current", /** @type {HTMLElement} */ (a).dataset.view === cur ? "page" : "false");
  }
  const show = !!(app.store && app.hasIdentity);
  const old = show && needsDot({ clean: app.clean, lastBackup: app.lastBackup, firstEventAt: app.firstEventAt }, Date.now());
  const noProfile = show && !!app.profile && needsProfileHint({ clean: showCleanHint(), profile: app.profile.profile });
  const words = ["家长", ...(old ? ["很久没备份了"] : []), ...(noProfile ? [PROFILE_TEXT.missing] : [])].join("，");
  for (const a of /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll('[data-view="parent"]'))) {
    a.hidden = !show;
    a.setAttribute("aria-label", words);
    if (a.classList.contains("ibtn")) a.title = words;
    const dot = /** @type {HTMLElement|null} */ (a.querySelector(".ndot"));
    const hint = /** @type {HTMLElement|null} */ (a.querySelector(".lock-hint"));
    if (hint) { hint.textContent = PROFILE_TEXT.missing; hint.hidden = !noProfile; }
    if (dot) dot.hidden = !(old || (noProfile && !hint));
  }
}

/** 底部：干净设备的提示、小字。总览和详情视图共用（家长入口在导航的锁上）。 */
function chartFoot() {
  return `${showCleanHint() ? `<p class="clean-hint"><a href="#parent">${esc(PTEXT.cleanHint)}</a></p>` : ""}
    <div class="chart-foot">
      <p class="chart-note muted">记录存在这台设备上，记得在「家长」里备份</p>
    </div>
    <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>`;
}

function renderOverview(main, model) {
  const tip = app.mode === "recovering" ? "正在准备……" : "从里到外是年级。点一个星座，飞进去看看。";
  main.innerHTML = `<section class="chart" aria-labelledby="chartTitle">
    <div class="vhead"><div><h1 id="chartTitle">星图</h1><p class="sub">${tip}</p></div>
      <div class="legend" aria-hidden="true">${legendHtml()}<span class="mono">${model.lit}/${model.points.length}</span></div></div>
    <p class="sr">点亮了 ${model.lit} 颗，一共 ${model.points.length} 颗。</p>
    <div class="graph shape-overview" id="graph">
      <svg id="gsvg" viewBox="0 0 760 760" role="group" aria-label="星图：从里到外是年级圈，一圈分成八个主题"></svg>
    </div>
    ${model.currentBand == null ? `<p class="grade-hint">在「家长」里填年级，你那一圈会变大</p>` : ""}
    ${chartFoot()}
  </section>`;
  const g = /** @type {HTMLElement} */ (main.querySelector("#graph"));
  const svg = /** @type {SVGSVGElement} */ (/** @type {unknown} */ (main.querySelector("#gsvg")));
  chartWidth = g.clientWidth;
  g.classList.toggle("narrow", g.clientWidth < 620);
  const { svg: inner, geometry } = overviewSvg(model);
  svg.innerHTML = inner;
  placeChartLabels(svg, geometry);
  if (document.fonts && document.fonts.status === "loading") document.fonts.ready.then(() => { if (svg.isConnected) placeChartLabels(svg, geometry); });
  const cons = [...svg.querySelectorAll(".cons")], clinks = [...svg.querySelectorAll(".clink")];
  const neighbors = (id) => { const s = new Set([id]); clinks.forEach((l) => { if (l.dataset.a === id) s.add(l.dataset.b); if (l.dataset.b === id) s.add(l.dataset.a); }); return s; };
  const focus = (id) => {
    g.classList.toggle("focusing", !!id);
    if (!id) return;
    const nb = neighbors(id);
    cons.forEach((el) => el.classList.toggle("nb", nb.has(el.dataset.id)));
    clinks.forEach((l) => l.classList.toggle("nb", l.dataset.a === id || l.dataset.b === id));
  };
  for (const el of cons) {
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); zoomTo(el.dataset.id, el); } });
    el.addEventListener("pointerenter", () => focus(el.dataset.id));
    el.addEventListener("pointerleave", () => focus(null));
    el.addEventListener("focus", () => focus(el.dataset.id));
    el.addEventListener("blur", () => focus(null));
  }
  // 点在哪个星座上：点击圈有重叠时取最近的
  svg.addEventListener("click", (e) => {
    const m = svg.getScreenCTM();
    if (!m) return;
    const pt = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    const id = nearestCons(geometry, pt.x, pt.y);
    if (id) zoomTo(id, svg.querySelector(`.cons[data-id="${CSS.escape(id)}"]`));
  });
  stopFloat = animateOverview(svg, geometry, reducedMotion());
}

function zoomTo(id, el) {
  const svg = /** @type {SVGSVGElement|null} */ (/** @type {unknown} */ (document.getElementById("gsvg")));
  const go = () => { app.chartZoom = id; renderChart(); $("#consTitle")?.focus({ preventScroll: true }); };
  if (reducedMotion() || !svg || !el || !svg.animate) { go(); return; }
  stopFloat();
  const r = el.getBoundingClientRect(), s = svg.getBoundingClientRect();
  svg.style.transformOrigin = `${r.left + r.width / 2 - s.left}px ${r.top + r.height / 2 - s.top}px`;
  svg.animate([{ transform: "scale(1)", opacity: 1 }, { transform: "scale(2.4)", opacity: 0 }], { duration: 320, easing: "ease-in" }).onfinish = () => {
    go();
    const ns = document.getElementById("gsvg");
    if (ns && ns.animate) ns.animate([{ transform: "scale(.92)", opacity: 0 }, { transform: "scale(1)", opacity: 1 }], { duration: 260, easing: "ease-out" });
  };
}

function zoomOut() {
  const from = app.chartZoom;
  const go = () => {
    app.chartZoom = null;
    renderChart();
    const back = from && document.querySelector(`#gsvg .cons[data-id="${CSS.escape(from)}"]`);
    if (back) /** @type {HTMLElement} */ (back).focus({ preventScroll: true });
    const ns = document.getElementById("gsvg");
    if (ns && ns.animate && !reducedMotion()) ns.animate([{ transform: "scale(1.25)", opacity: 0 }, { transform: "scale(1)", opacity: 1 }], { duration: 300, easing: "ease-out" });
  };
  const svg = document.getElementById("gsvg");
  if (svg && svg.animate && !reducedMotion()) svg.animate([{ opacity: 1, transform: "scale(1)" }, { opacity: 0, transform: "scale(.85)" }], { duration: 200 }).onfinish = go;
  else go();
}

/* ============================================================
   知识地铁（#233）：画法在 metro.js，数据和星图同一份（chartModel）
   ============================================================ */
function renderMetro(main, model) {
  const tip = app.mode === "recovering" ? "正在准备……" : "每条线是一个大概念，从一年级开到高中。换乘站是两条线相遇的地方。";
  main.innerHTML = `<section class="chart metro" aria-labelledby="metroTitle">
    <div class="vhead"><div><h1 id="metroTitle" tabindex="-1">知识地铁</h1><p class="sub">${tip}</p></div>
      <div class="legend" aria-hidden="true">${legendHtml()}<span class="mono">${model.lit}/${model.points.length}</span></div></div>
    <p class="sr">点亮了 ${model.lit} 站，一共 ${model.points.length} 站。</p>
    ${model.currentBand == null ? `<p class="grade-hint">在「家长」里填年级，地铁会标出你在哪一段</p>` : ""}
    <div class="mscroll" id="mscroll"></div>
    ${chartFoot()}
  </section>`;
  const L = metroLayout(model);
  const sel = app.note && model.byId.has(app.note) ? app.note : null;
  const { map, labels } = metroSvg(model, L, { focusLine: app.metroLine, selected: sel });
  const sc = /** @type {HTMLElement} */ (main.querySelector("#mscroll"));
  sc.innerHTML = `<svg width="${L.W}" height="${L.H}" viewBox="0 0 ${L.W} ${L.H}" role="group" aria-label="知识地铁线路图">${map}<g id="mlabels">${labels}</g></svg>`;
  const ml = sc.querySelector("#mlabels");
  const pin = () => ml.setAttribute("transform", `translate(${sc.scrollLeft} 0)`);
  sc.addEventListener("scroll", pin, { passive: true });
  const { left, top } = metroScroll(L, sc.clientWidth, sc.clientHeight, sel);
  sc.scrollLeft = left; sc.scrollTop = top;
  pin();
  for (const el of sc.querySelectorAll(".station")) {
    const open = () => openPoint(model, /** @type {HTMLElement} */ (el).dataset.id || "", /** @type {HTMLElement} */ (el));
    el.addEventListener("click", open);
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    // 键盘移到被左边线名栏挡住的站时，把它滚出来
    el.addEventListener("focus", () => {
      const p = L.pos[/** @type {HTMLElement} */ (el).dataset.id || ""];
      if (p && p[0] - 24 < sc.scrollLeft + 150) sc.scrollLeft = Math.max(0, p[0] - 150 - 60);
    });
  }
  for (const el of sc.querySelectorAll(".lline")) {
    const toggle = () => {
      const k = /** @type {HTMLElement} */ (el).dataset.line || null;
      app.metroLine = app.metroLine === k ? null : k;
      const keepL = sc.scrollLeft, keepT = sc.scrollTop;
      renderChart();
      const ns = /** @type {HTMLElement|null} */ (document.getElementById("mscroll"));
      if (ns) { ns.scrollLeft = keepL; ns.scrollTop = keepT; /** @type {HTMLElement|null} */ (ns.querySelector(`.lline[data-line="${k}"]`))?.focus({ preventScroll: true }); }
    };
    el.addEventListener("click", toggle);
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
  }
}

let measureCtx = null;
function renderConstellation(main, model, c) {
  const litN = c.points.filter((p) => p.state === "lit").length, openN = c.points.filter((p) => p.open).length;
  main.innerHTML = `<section class="chart detail" aria-labelledby="consTitle">
    <div class="vhead"><div>
      <div class="crumb"><button type="button" class="back" data-zout>${backIcon()} 星图</button><span>/</span><span>${BAND_NAME[c.band]}</span></div>
      <h1 id="consTitle" tabindex="-1">${esc(consName(c))}座</h1>
      <p class="sub">${c.points.length} 颗星 · 开放 ${openN} 颗 · 点亮 ${litN} 颗</p></div>
      <div class="legend" aria-hidden="true">${legendHtml()}</div></div>
    <div class="graph scroll" id="graph"><svg id="gsvg" role="group" aria-label="${esc(consName(c))}座的星"></svg></div>
    ${chartFoot()}
  </section>`;
  const wrap = /** @type {HTMLElement} */ (main.querySelector("#graph"));
  chartWidth = wrap.clientWidth;
  if (!measureCtx) measureCtx = document.createElement("canvas").getContext("2d");
  const css = getComputedStyle(wrap);
  const fonts = { hand: css.getPropertyValue("--f-hand") || "sans-serif", sans: css.getPropertyValue("--f-sans") || "sans-serif" };
  const measure = (text, font) => { measureCtx.font = font; return measureCtx.measureText(text).width; };
  const L = constellationLayout(c, wrap.clientWidth, measure, fonts);
  const busy = new Set(app.quiz && pendingQuiz(app.quiz) ? [app.quiz.node.id] : []);
  const svg = main.querySelector("#gsvg");
  svg.setAttribute("viewBox", `0 0 ${L.W} ${L.H}`);
  svg.setAttribute("width", String(L.W));
  svg.innerHTML = constellationSvg(c, L, busy);
  // 笔记打开着的那颗星：画一个选中圈（照原型 select）
  const pick = app.note ? model.byId.get(app.note) : null;
  const pickEl = pick && svg.querySelector(`.node[data-id="${CSS.escape(pick.id)}"]`);
  if (pickEl && !busy.has(pick.id)) { const r = pick.acts ? 14 : 12; pickEl.insertAdjacentHTML("afterbegin", `<path class="sel-ring" d="${Sk.ellipse(0, 0, r + 9, r + 9, pick.seed + 9, .8)}"/>`); }
  main.querySelector("[data-zout]").addEventListener("click", zoomOut);
  for (const el of svg.querySelectorAll(".node")) {
    const open = () => openPoint(model, /** @type {HTMLElement} */ (el).dataset.id || "", /** @type {HTMLElement} */ (el));
    el.addEventListener("click", open);
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  }
}

/** 点了星图详情里的一颗星、地铁站：打开这颗星的笔记（照原型 select）。 */
function openPoint(_model, id, el) { selectPoint(id, { from: el, reveal: false }); }

/* ============================================================
   星球笔记（#233，照原型 select、noteHTML、bindNote、closeNote）：只在星图和地铁页
   ============================================================ */
/** 笔记收起时焦点回到哪里（点开笔记的那颗星、那个站或索引里的叶子）。 */
let noteFrom = /** @type {string|null} */ (null);
const X_ICON = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>`;

/** 一个元素 → 重画以后还能找回它的选择器。 @param {Element|null} el */
function focusKey(el) {
  if (!el || !(el instanceof Element)) return null;
  const d = /** @type {HTMLElement} */ (el).dataset || {};
  if (el.closest("#drawer")) return '.bottomnav [data-act="drawer"]';
  if (d.node) return `#explorer [data-node="${CSS.escape(d.node)}"]`;
  if (el.classList.contains("node") && d.id) return `#gsvg .node[data-id="${CSS.escape(d.id)}"]`;
  if (el.classList.contains("station") && d.id) return `#mscroll .station[data-id="${CSS.escape(d.id)}"]`;
  if (d.goto) return null;
  return el.id ? "#" + CSS.escape(el.id) : null;
}

/**
 * 选中一颗星，打开它的笔记。reveal：从索引、笔记里的链接来的，星图飞进这颗星的星座、地铁滚到这一站；
 * 从星图、地铁上点的，画面不动，只换选中圈。
 * @param {string} id @param {{from?: Element|null, reveal?: boolean}} [o]
 */
function selectPoint(id, { from = null, reveal = false } = {}) {
  const model = chartModel();
  const p = model.byId.get(id);
  if (!p) return;
  app.note = id;
  tree.sel = id;
  tree.open[consId(p)] = true;
  const key = focusKey(from);
  if (key) noteFrom = key;
  if (reveal && app.home === "chart") app.chartZoom = consId(p);
  redrawChart(!reveal);
  /** @type {HTMLElement|null} */ (document.getElementById("noteTitle"))?.focus({ preventScroll: true });
}

/** 收起笔记（× 或 Esc），焦点回到点开它的地方。 */
function closeNote() {
  if (!app.note) return;
  app.note = null;
  tree.sel = null;
  redrawChart(true);
  const back = noteFrom && /** @type {HTMLElement|null} */ (document.querySelector(noteFrom));
  noteFrom = null;
  if (back) back.focus({ preventScroll: true });
}

/** 重画星图或地铁；keep 为真时留住滚动位置（笔记开合会改变宽度，详情视图要按新宽度重新排）。 @param {boolean} keep */
function redrawChart(keep) {
  const main = $("#main");
  const sc = document.getElementById("mscroll"), gr = document.getElementById("graph");
  const saved = { top: main.scrollTop, sl: sc ? sc.scrollLeft : 0, st: sc ? sc.scrollTop : 0, gt: gr ? gr.scrollTop : 0, metro: !!sc };
  renderChart();
  if (!keep) return;
  main.scrollTop = saved.top;
  const ns = document.getElementById("mscroll");
  if (ns && saved.metro) { ns.scrollLeft = saved.sl; ns.scrollTop = saved.st; ns.dispatchEvent(new Event("scroll")); }
}

/** 这颗星能进的活动（动手探索、挑战）。 @param {any} node */
function activityChoices(node) {
  return nodeActivities(node).filter((a) => a.module || (a.entry.kind === "quiz" && a.def));
}

/** 现在不能开始活动时的一句话。 */
function whyCantStart() {
  return app.mode === "recovering" ? "正在准备，等一下再点。" : app.mode === "unfinished" ? "请家长先看一看上面的提示。" : app.why === "lost" ? "请刷新页面。" : "这里只能看，不能开始挑战。";
}

/** 画笔记（星图、地铁页）。 @param {ReturnType<typeof chartModel>} [model] */
function renderNote(model) {
  const pane = $("#notepane"), shell = $(".app");
  const p = model && app.note ? model.byId.get(app.note) : null;
  if (!p) { if (app.note && model) app.note = null; shell.classList.remove("note-open"); pane.innerHTML = ""; return; }
  const card = app.pack.nodes.find((n) => n.id === p.id) || null;
  const choices = card ? activityChoices(card) : [];
  const tasks = choices.map((a) => {
    const def = a.module?.manifest || a.def;
    const isQuiz = a.entry.kind === "quiz";
    const resume = isQuiz && app.quiz?.def.id === def.id && pendingQuiz(app.quiz);
    return { id: a.entry.id, title: def.title, meta: `${isQuiz ? "挑战" : "动手探索"} · ${isQuiz ? `${def.body.items.length} 道题` : `${stationCount(def.id)} 站`}`, go: resume ? "接着做" : "开始" };
  });
  const canStart = app.mode === "writable" && !!app.session;
  const top = pane.dataset.for === p.id ? pane.scrollTop : 0;
  pane.innerHTML = `<div class="grab" aria-hidden="true"></div><button class="close note-x" type="button" aria-label="收起笔记" title="收起">${X_ICON}</button>` +
    noteHtml(p, { card, model, tasks, canStart, why: whyCantStart() });
  pane.dataset.for = p.id;
  pane.scrollTop = top;
  shell.classList.add("note-open");
  pane.querySelector(".note-x").addEventListener("click", closeNote);
  for (const b of pane.querySelectorAll("[data-start]")) {
    b.addEventListener("click", () => {
      if (app.mode !== "writable" || !app.session || !card) return;
      const a = choices.find((x) => x.entry.id === /** @type {HTMLElement} */ (b).dataset.start);
      if (!a) return;
      if (a.module) { if (canSwitchActivity()) openExploration(card, a.module); }
      else openQuiz(card, a.def);
    });
  }
  for (const l of pane.querySelectorAll("[data-goto]")) {
    l.addEventListener("click", (e) => { e.preventDefault(); selectPoint(/** @type {HTMLElement} */ (l).dataset.goto || "", { reveal: true }); });
  }
}

/* ============================================================
   知识索引（#233，照原型 treeHTML、bindTree、renderExplorer、openTree）
   ============================================================ */
const EX_KEY = "curio.explorer";
const tree = {
  query: "",
  /** 星座 id → 展开没有；没记的按「是不是舰长当前学段」 */ open: /** @type {Record<string, boolean>} */ ({}),
  sel: /** @type {string|null} */ (null),
  /** @type {Map<string, string[]>|null} */ aliases: null,
  collapsed: false,
};
/** 收起状态记在 localStorage；读写失败就默认展开。 */
function readCollapsed() { try { return localStorage.getItem(EX_KEY) === "closed"; } catch { return false; } }
function writeCollapsed(v) { try { localStorage.setItem(EX_KEY, v ? "closed" : "open"); } catch { /* 记不住就算了 */ } }

const isOpenIn = (model) => (c) => (c.id in tree.open ? tree.open[c.id] : c.band === model.currentBand);

function renderExplorer() {
  const roots = /** @type {HTMLElement[]} */ ([document.getElementById("explorer"), document.getElementById("drawer")].filter(Boolean));
  const ready = !!(app.pack && app.pack.catalog) && !(app.mode === "readonly" && !app.hasIdentity) && app.mode !== "stopped";
  const model = ready ? chartModel() : null;
  if (model && !tree.aliases) tree.aliases = aliasIndex(app.pack.catalog, model.byId);
  for (const root of roots) {
    if (!model) { root.innerHTML = ""; continue; }
    // 重画以后焦点、光标、滚动位置都留在原处
    const ae = /** @type {HTMLElement|null} */ (document.activeElement);
    let key = null, pos = null;
    if (ae && root.contains(ae)) {
      if (ae.matches("[data-treeq]")) { key = "[data-treeq]"; pos = /** @type {HTMLInputElement} */ (ae).selectionStart; }
      else if (ae.dataset.cons) key = `[data-cons="${CSS.escape(ae.dataset.cons)}"]`;
      else if (ae.dataset.node) key = `[data-node="${CSS.escape(ae.dataset.node)}"]`;
    }
    const top = root.scrollTop;
    root.innerHTML = treeHtml(model, { query: tree.query, isOpen: isOpenIn(model), selected: tree.sel, aliases: /** @type {Map<string, string[]>} */ (tree.aliases) });
    root.scrollTop = top;
    bindTree(root, model);
    const el = key && /** @type {HTMLElement|null} */ (root.querySelector(key));
    if (el) { el.focus({ preventScroll: true }); if (pos != null) /** @type {HTMLInputElement} */ (el).setSelectionRange(pos, pos); }
  }
}

let liveTimer = 0;
function bindTree(root, model) {
  for (const b of root.querySelectorAll("[data-cons]")) {
    b.addEventListener("click", () => {
      const id = /** @type {HTMLElement} */ (b).dataset.cons || "", c = model.consById.get(id);
      tree.open[id] = !(c && isOpenIn(model)(c));
      renderExplorer();
    });
  }
  for (const b of root.querySelectorAll("[data-node]")) b.addEventListener("click", () => openLeaf(/** @type {HTMLElement} */ (b).dataset.node || "", /** @type {HTMLElement} */ (b)));
  const qi = /** @type {HTMLInputElement|null} */ (root.querySelector("[data-treeq]"));
  if (qi) qi.addEventListener("input", () => {
    tree.query = qi.value;
    renderExplorer();
    clearTimeout(liveTimer);
    liveTimer = setTimeout(() => {
      const q = tree.query.trim();
      $("#live").textContent = q ? `找到 ${searchPoints(chartModel(), /** @type {any} */ (tree.aliases), q).length} 颗星球` : "";
    }, 400);
  });
}

/** 点了索引里的一颗星：不在星图或地铁时先回去，再打开它的笔记。 */
function openLeaf(id, el) {
  const inDrawer = !!el.closest("#drawer");
  if (inDrawer) closeDrawer(false);
  if (app.view === "quiz" || app.view === "exploration" || app.mode === "stopped") return;
  if (app.view === "parent") {
    app.view = "chart"; // 先设好：hashchange 看到已经不在家长页，不再重画
    location.hash = app.home === "metro" ? "#metro" : "#chart";
  }
  selectPoint(id, { from: el, reveal: true });
}

/** 桌面：收起、展开左边的知识索引。 @param {boolean} collapsed */
function setCollapsed(collapsed) {
  tree.collapsed = collapsed;
  writeCollapsed(collapsed);
  applyCollapsed();
  if (app.view === "chart") redrawChart(true); // 星图可用的宽度变了
}
function applyCollapsed() {
  $(".app").classList.toggle("ex-closed", tree.collapsed);
  const b = document.querySelector('.ribbon [data-act="tree"]');
  if (!b) return;
  const words = tree.collapsed ? "展开知识索引" : "收起知识索引";
  b.setAttribute("aria-expanded", String(!tree.collapsed));
  b.setAttribute("aria-label", words);
  b.setAttribute("title", words);
}

/** 手机：知识索引从左边滑出（照原型 openTree），带遮罩；Esc、点遮罩关上，焦点回到底部的「索引」。 */
function openDrawer() {
  if (document.getElementById("drawer")) return;
  const btn = document.querySelector('.bottomnav [data-act="drawer"]');
  const sc = document.createElement("div");
  sc.className = "drawer-scrim";
  sc.id = "drawerScrim";
  sc.addEventListener("click", () => closeDrawer(true));
  const d = document.createElement("aside");
  d.className = "drawer";
  d.id = "drawer";
  d.tabIndex = -1;
  d.setAttribute("role", "dialog");
  d.setAttribute("aria-modal", "true");
  d.setAttribute("aria-label", "知识索引");
  d.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeDrawer(true); return; }
    if (e.key !== "Tab") return;
    const f = /** @type {HTMLElement[]} */ ([...d.querySelectorAll("button, input, a[href]")]);
    if (!f.length) return;
    if (e.shiftKey && (document.activeElement === f[0] || document.activeElement === d)) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
  });
  document.body.append(sc, d);
  /** @type {any} */ ($(".app")).inert = true;
  btn?.setAttribute("aria-expanded", "true");
  renderExplorer();
  d.focus({ preventScroll: true });
}
/** @param {boolean} restore 焦点回到「索引」按钮 */
function closeDrawer(restore) {
  const d = document.getElementById("drawer");
  if (!d) return;
  d.remove();
  document.getElementById("drawerScrim")?.remove();
  /** @type {any} */ ($(".app")).inert = false;
  const btn = /** @type {HTMLElement|null} */ (document.querySelector('.bottomnav [data-act="drawer"]'));
  btn?.setAttribute("aria-expanded", "false");
  if (restore) btn?.focus({ preventScroll: true });
}

// 宽度变了（转屏、改窗口）：重画星图，排版和标签避让跟着变
let resizeTimer = 0;
if (typeof window !== "undefined") window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const g = document.getElementById("graph");
    if (app.view === "chart" && app.home === "chart" && g && Math.abs(g.clientWidth - chartWidth) > 24) {
      redrawChart(true);
    }
  }, 180);
});

/** 干净的设备（打开时读到的，而且之后没有新记录）：首页提示可以从备份恢复。 */
const showCleanHint = () => app.clean && !!app.log && app.log.raw().length === 0 && app.log.quarantined().length === 0;

let toastTimer = 0;
function toast(text) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

/* ============================================================
   开始挑战（规格 6.3「开始一次挑战」）：从笔记的「任务」进来
   ============================================================ */
function nodeActivities(node) {
  return (node.activities || []).map((id) => app.pack.activities.get(id)).filter(Boolean);
}

function openQuiz(node, def) {
  if (app.mode !== "writable" || !app.session) return;
  if (app.quiz?.def.id === def.id && pendingQuiz(app.quiz)) {
    app.view = "quiz";
    renderQuiz();
  } else if (canSwitchActivity()) {
    startChallenge(node, def);
  }
}

// 旧挑战可能刚好退回星图、最后一笔还在写。它的重试必须继续使用同一条原始事件。
function canSwitchActivity() {
  if (!app.quiz?.q.pending) return true;
  $("#live").textContent = "请先存好上次的挑战。";
  if (app.quiz.q.view.failed) {
    app.view = "quiz";
    renderQuiz();
  } else {
    toast("正在保存上次的挑战，稍等一下再点。");
  }
  return false;
}

/** 合格尝试里已保存的站包括中途退出前完成的站。通关只认单独的结束事件。 */
export function explorationProgress(events, learnerId, activityId, version) {
  const stations = new Set(), count = stationCount(activityId);
  for (const attempt of groupAttempts(events).values()) {
    const first = attempt[0];
    const content = first.content;
    if (first.learner_id !== learnerId || content?.activity_id !== activityId ||
        content.activity_kind !== "simulation" || content.activity_version !== version || attemptRule(attempt)) continue;
    if (attempt[attempt.length - 1].verb === "attempt.completed") {
      // 较早的记录只有整次完成。各站当时必须依次走完，重进时应能任选一站。
      return { doneStations: Array.from({ length: count }, (_, i) => i + 1), activityCompleted: true };
    }
    for (const e of attempt) {
      const value = e.payload.value;
      if (e.verb === "sim.observed" && e.payload.observable === "station.completed" &&
          Number.isInteger(value) && value >= 1 && value <= count) stations.add(value);
    }
  }
  return { doneStations: [...stations].sort((a,b) => a-b), activityCompleted: false };
}

function openExploration(node, module) {
  if (app.exploration || app.mode !== "writable" || !app.session) return;
  const { manifest, html } = module;
  const session = app.session;
  const history = explorationProgress(session.log.events(), session.identity.learner_id, manifest.id, manifest.version);
  const run = { host: null, leaving: null, failed:false };
  app.exploration = run;
  app.view = "exploration";
  $("#main").innerHTML = `<section class="exploration" aria-labelledby="exploreTitle">
    <header class="quiz-head"><button type="button" class="back" data-act="leave" aria-label="退出探索，回到${homeName()}">${backIcon()} ${homeName()}</button>
    <div><h1 id="exploreTitle" tabindex="-1">${esc(manifest.title)}</h1><p class="sub">${esc(node.title)}</p></div></header>
    <div class="explore-status"><p role="status">正在打开……</p><button type="button" class="btn" data-act="refresh" hidden>刷新</button></div><div class="workbench"></div></section>`;
  const back = $("#main [data-act=leave]");
  const panel = $("#main .explore-status");
  const status = panel.querySelector('[role="status"]');
  const refresh = panel.querySelector('[data-act="refresh"]');
  refresh.addEventListener("click", () => location.reload());
  back.addEventListener("click", async () => {
    if (await closeExploration(run) && app.view === "exploration") renderChart();
  });
  $("#exploreTitle").focus({ preventScroll: true });
  try {
    run.host = mountExploration({
      container: $("#main .workbench"), manifest, html, session, ids, now,
      content: Object.freeze({ node_id: node.id, activity_id: manifest.id, activity_kind: "simulation",
        activity_version: manifest.version, content_release: app.pack.release.release_id }),
      mode: history.activityCompleted ? "retry" : "first", ...history,
      onStatus(state) {
        if (app.exploration !== run) return;
        if (state === "completed") recompute();
        const words = {loading:"正在打开……", active:"", completed:"", failed:"记录没存好。请刷新页面，再回到这颗星。",
          timeout:"实物没有打开。回到星图，再试一次。", navigation:"探索中断了。请回到星图再试。"};
        status.textContent = words[state] || "";
        panel.hidden = !status.textContent;
        if (state === "failed") {
          run.failed = true;
          back.disabled = true;
          refresh.hidden = false;
        }
      }
    });
  } catch (e) {
    console.error(e);
    panel.hidden = false;
    status.textContent = "这个探索暂时打不开，请回到星图。";
  }
}

// 在离开宿主前等它提交最后的观察和退出，防止下一次活动争用同一个 device_seq。
function closeExploration(run = app.exploration) {
  if (!run) return Promise.resolve(true);
  if (run.failed) return Promise.resolve(false);
  if (run.leaving) return run.leaving;
  const back = $("#main [data-act=leave]");
  if (back) back.disabled = true;
  run.leaving = (async () => {
    try {
      await run.host?.leave();
      if (app.exploration !== run) return false;
      run.host?.destroy();
      app.exploration = null;
      recompute();
      return true;
    } catch (e) {
      console.error(e);
      if (app.exploration === run) {
        run.failed = true;
        const panel = $("#main .explore-status");
        if (panel) {
          panel.hidden = false;
          panel.querySelector('[role="status"]').textContent = "记录没存好。请刷新页面，再回到这颗星。";
          panel.querySelector('[data-act="refresh"]').hidden = false;
        }
      }
      return false;
    }
  })();
  return run.leaving;
}

/** 这次挑战还没做完，或者做完了但孩子还没看到结果（最后一道存好前回了星图）。 */
const pendingQuiz = (z) => z.q.phase !== "done" || !z.resultSeen;

/**
 * 这个孩子在任何设备上有没有一次合法、已完成的这个活动的尝试（backup.md 第 11 节；slice-1 6.3「开始一次挑战」）。
 * 被判不一致的、被放弃的不算。
 * @param {any[]} events 日志里被接收的事件
 * @param {string} learnerId
 * @param {string} activityId
 */
export function completedBefore(events, learnerId, activityId) {
  const bad = new Set(projectMastery(events).conflicts.map((c) => c.attempt_id));
  for (const [att, evs] of groupAttempts(events)) {
    if (bad.has(att)) continue;
    const f = evs[0];
    if (f.learner_id === learnerId && f.content && f.content.activity_id === activityId && evs[evs.length - 1].verb === "attempt.completed") return true;
  }
  return false;
}

function startChallenge(node, def) {
  const ids0 = (def.body && Array.isArray(def.body.items) ? def.body.items : []).map((it) => it && it.id);
  const order = def.body && def.body.shuffle ? shuffled(ids0) : ids0;
  const s0 = /** @type {any} */ (app.session);
  const mode = completedBefore(s0.log.events(), s0.identity.learner_id, def.id) ? "retry" : "first";
  let q;
  try { q = startQuiz(def, order, mode); }
  catch { toast("这个挑战暂时不能玩。"); return; }
  const rel = /** @type {any} */ (app.pack).release;
  app.quiz = {
    q, def, node,
    // 冻结这次挑战的 content：这次尝试的每条事件都用它
    content: Object.freeze({ node_id: node.id, activity_id: def.id, activity_kind: "quiz", activity_version: def.version, content_release: rel.release_id }),
    attempt_id: ids.attempt(),
    startedMs: 0,
    cur: null, busy: false, error: null, solved: null, wrongBy: {}, resultSeen: false, lastKey: "",
    answered: {}, lastResponse: {}, draft: {}, lit: false, focusHint: false,
    litBefore: nodeState(node.id) === "lit",
  };
  app.view = "quiz";
  renderQuiz();
  pump();
}

/** 把当前意图组装成原始文字（只组装一次，重试用同一条）。 */
function assembleCurrent() {
  const z = /** @type {any} */ (app.quiz), s = /** @type {any} */ (app.session), p = z.q.pending;
  if (z.cur && z.cur.id === p.id) return z.cur;
  const event_id = ids.event();
  const occurred_at = now();
  if (p.verb === "attempt.started") z.startedMs = Date.now();
  const payload = p.verb === "attempt.completed" ? { duration_ms: Math.max(0, Math.round(Date.now() - z.startedMs)) } : p.payload;
  const raw = assemble({
    event_id,
    identity: s.identity,
    device_seq: s.committer.nextSeq,
    occurred_at,
    actor: { type: "learner", id: s.identity.learner_id },
    verb: p.verb,
    attempt_id: z.attempt_id,
    content: z.content,
    payload,
  });
  z.cur = { id: p.id, raw, receipt: localReceipt(event_id, now()), verb: p.verb, payload };
  return z.cur;
}

/** 提交当前意图，按结果给状态机发 saved 或 failed。 */
async function pump() {
  const z = app.quiz;
  if (!z || !z.q.pending || z.busy || !app.session) return;
  const cur = assembleCurrent();
  z.busy = true;
  renderQuiz();
  try {
    await app.session.committer.submit(cur.raw, cur.receipt);
    if (app.quiz !== z) return;
    z.error = null;
    if (cur.verb === "item.answered") {
      const pl = /** @type {any} */ (cur.payload);
      z.answered[pl.item_id] = true;
      z.lastResponse[pl.item_id] = pl.response;
      if (!pl.correct) z.wrongBy[pl.item_id] = [...(z.wrongBy[pl.item_id] || []), pl.response];
      else z.solved = pl.item_id;
    } else if (cur.verb === "hint.used") {
      z.focusHint = true;
    } else if (cur.verb === "answer.revealed") {
      // 存好了才显示答案（CURIO-013）：这道题记为「看过答案」，画面换成答案和「下一题」
      z.solved = /** @type {any} */ (cur.payload).item_id;
    }
    z.q = step(z.q, { type: "saved", id: cur.id });
    // 读屏器：答错的反馈、新提示用常驻的 aria-live 区域读出来（焦点会回到输入框）
    const v2 = z.q.view;
    if (cur.verb === "hint.used" && v2.hints.length) z.announce = `提示 ${v2.hints.length}：${v2.hints[v2.hints.length - 1]}`;
    else if (cur.verb === "item.answered" && v2.feedback && !v2.feedback.correct && v2.feedback.item_id === v2.item_id) z.announce = v2.feedback.text;
    if (z.q.phase === "done") {
      recompute();
      // 星星这一次才从暗变亮：结果页放一次点亮动效（尊重 reduced-motion，见 resultHtml）
      z.lit = !z.litBefore && nodeState(z.node.id) === "lit";
    }
  } catch (e) {
    if (app.quiz !== z) return;
    z.error = e;
    z.q = step(z.q, { type: "failed", id: cur.id });
    if (e instanceof FrozenError && app.mode === "writable") { app.mode = "readonly"; app.why = "lost"; renderBanner(); }
  } finally {
    z.busy = false;
  }
  if (app.quiz !== z) return;
  if (app.view === "quiz") renderQuiz();
  else if (z.q.phase === "done" && app.view === "chart") renderChart(); // 存好时孩子已经回到星图：重画，星星换样子
  if (z.q.pending && !z.q.view.failed) pump();
}

function answer(response) {
  const z = app.quiz;
  if (!z || app.mode !== "writable") return;
  const before = z.q;
  z.q = step(z.q, { type: "answer", response });
  if (z.q === before) return;
  z.solved = null;
  pump();
}

/** 要个提示（6.4）：状态机接受了才写 hint.used，存好以后提示才显示。 */
function askHint() {
  const z = app.quiz;
  if (!z || app.mode !== "writable") return;
  const before = z.q;
  z.q = step(z.q, { type: "hint" });
  if (z.q === before) return;
  pump();
}

/** 看答案（6.4，CURIO-013）：状态机接受了才写 answer.revealed，存好以后答案才显示；是最后一题时接着写完成。 */
function revealAnswer() {
  const z = app.quiz;
  if (!z || app.mode !== "writable") return;
  const before = z.q;
  z.q = step(z.q, { type: "reveal" });
  if (z.q === before) return;
  pump();
}

/** 数字框、分数框交上来的作答；框是空的时不提交。 */
function submitTyped(form) {
  const z = app.quiz;
  if (!z) return;
  const t = z.q.view.answer_type;
  const val = (name) => /** @type {HTMLInputElement} */ (form.elements.namedItem(name)).value;
  let response;
  if (t === "number") {
    if (!val("n").trim()) return;
    response = val("n");
  } else if (t === "fraction") {
    const a = val("a").trim(), b = val("b").trim();
    if (!a || !b) return;
    response = `${a}/${b}`;
  } else return;
  answer(response);
}

function retry() {
  const z = app.quiz;
  if (!z || z.busy) return;
  z.q = step(z.q, { type: "retry" });
  pump();
}

/* ============================================================
   挑战界面
   ============================================================ */
function progressHtml(z) {
  const v = z.q.view, solvedN = z.q.phase === "answering" ? v.index : v.total;
  return `<div class="prog" role="img" aria-label="第 ${Math.min(v.index + 1, v.total)} 题，一共 ${v.total} 题">${Array.from({ length: v.total }, (_, i) => `<i class="${i < solvedN ? "on" : ""}"></i>`).join("")}<span>${Math.min(v.index + 1, v.total)} / ${v.total}</span></div>`;
}

/** 一道题：配图、题干、作答区（选项，或数字框，或上下两个分数框）。 */
function itemHtml(item, opts) {
  const { wrong = [], right = null, disabled = false, busy = false, draft = {}, shown = null, itemId = "" } = opts;
  // 等待存储时输入框只读（不是 disabled），焦点和平板输入法不丢；选项按钮照旧变灰
  const off = disabled || busy;
  const inAttr = disabled ? "disabled" : busy ? "readonly" : "";
  const a = item.answer;
  // 作答时选项取自状态机的 view.choices（不带答案）；已有结果时才用活动数据标出正确选项
  const choices = opts.choices || (a.type === "choice" ? a.choices.map((c) => ({ id: c.id, text: c.text })) : []);
  let area = "";
  if (a.type === "choice") {
    area = `<div class="choices" role="group" aria-label="选一个">
      ${choices.map((c) => {
        const isWrong = wrong.includes(c.id), isRight = right === c.id;
        return `<button type="button" class="choice ${isWrong ? "wrong" : ""} ${isRight ? "right" : ""}" data-choice="${esc(c.id)}" ${off || isWrong || right ? "disabled" : ""}>${rich(c.text)}${isWrong ? '<span class="sr">，选过了，不对</span>' : ""}</button>`;
      }).join("")}
    </div>`;
  } else if (shown !== null) {
    // 这道题已经有结果：只读地显示答案
    area = `<div class="ansrow done"><span class="ansval ${shown.ok ? "right" : ""}">${rich(shown.text)}</span></div>`;
  } else if (a.type === "number") {
    area = `<form class="ansrow" data-form data-item="${esc(itemId)}" autocomplete="off">
      <label class="sr" for="ans-n">写一个数</label>
      <input id="ans-n" name="n" class="numbox" type="text" inputmode="decimal" enterkeyhint="done" maxlength="16" value="${esc(draft.n || "")}" ${inAttr}>
      ${typeof a.unit === "string" && a.unit ? `<span class="unit">${esc(a.unit)}</span>` : ""}
      <button class="btn ink big" type="submit" ${off ? "disabled" : ""}>确定</button>
    </form>`;
  } else if (a.type === "fraction") {
    area = `<form class="ansrow" data-form data-item="${esc(itemId)}" autocomplete="off">
      <div class="fracbox" role="group" aria-label="写一个分数">
        <label class="sr" for="ans-a">分子（横线上面）</label>
        <input id="ans-a" name="a" class="numbox" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="6" value="${esc(draft.a || "")}" ${inAttr}>
        <span class="fracline" aria-hidden="true"></span>
        <label class="sr" for="ans-b">分母（横线下面）</label>
        <input id="ans-b" name="b" class="numbox" type="text" inputmode="numeric" pattern="[0-9]*" enterkeyhint="done" maxlength="6" value="${esc(draft.b || "")}" ${inAttr}>
      </div>
      <button class="btn ink big" type="submit" ${off ? "disabled" : ""}>确定</button>
    </form>`;
  }
  return `<div class="q">
    ${item.figure ? `<div class="figbox">${figureSvg(item.figure, 9)}</div>` : ""}
    <p class="stem">${rich(item.stem)}</p>
    ${area}
  </div>`;
}

/** 已存好的提示，按顺序。 */
function hintsHtml(hints) {
  if (!hints.length) return "";
  return `<ol class="hints" aria-label="提示">${hints.map((h, i) => `<li class="bub hint" tabindex="-1"><span class="tag">提示 ${i + 1}</span><p>${rich(h)}</p></li>`).join("")}</ol>`;
}

function statusHtml(z) {
  const v = z.q.view;
  if (v.failed) {
    const frozen = z.error instanceof FrozenError;
    if (frozen) return `<div class="save bad" role="alert"><p><b>没存上。</b>请刷新页面。</p><button class="btn ink" type="button" data-act="reload">刷新</button></div>`;
    if (z.error && z.error.name === "QuarantinedError") return `<div class="save bad" role="alert"><p><b>出错了。</b>请家长看一看。</p></div>`;
    return `<div class="save bad" role="alert"><p><b>没存上。</b>再点一次就好。</p><button class="btn ink" type="button" data-act="retry" ${z.busy ? "disabled" : ""}>再试</button></div>`;
  }
  if (v.waiting) return `<p class="save muted" aria-live="polite">正在记下……</p>`;
  return "";
}

function renderQuiz() {
  const z = app.quiz;
  if (!z || app.view !== "quiz") return;
  const main = $("#main");
  const v = z.q.view;
  let body = "";
  const solvedItem = z.solved ? z.def.body.items.find((it) => it.id === z.solved) : null;
  if (z.q.phase === "starting") {
    body = `<div class="q"><p class="stem">准备好了吗？</p></div>`;
  } else if (solvedItem && (z.q.phase !== "answering" || v.item_id !== z.solved)) {
    // 刚有结果的题（答对存好，或 answer.revealed 存好）：先看反馈，再点「下一题」
    const fbo = v.feedback && v.feedback.item_id === z.solved ? v.feedback : null;
    const revealed = !!(fbo && fbo.revealed);
    const a = solvedItem.answer;
    const right = a.type === "choice" ? a.choices.find((c) => c.correct === true).id : null;
    const shown = a.type === "choice" ? null : revealed ? { ok: true, text: fbo.answer_text } : { ok: true, text: z.lastResponse[z.solved] + (a.unit ? " " + a.unit : "") };
    const last = z.q.phase !== "answering";
    const bubble = revealed
      ? `<div class="bub reveal" role="status"><p><b>答案是 ${rich(fbo.answer_text)}</b></p><p>${rich(fbo.text)}</p></div>`
      : `<div class="bub good" role="status">${starMini()}<p>${rich(fbo ? fbo.text : "")}</p></div>`;
    body = itemHtml(solvedItem, { wrong: z.wrongBy[z.solved] || [], right, disabled: true, shown }) + bubble +
      `<div class="btns"><button class="btn ink big" type="button" data-act="next" ${last && z.q.phase !== "done" ? "disabled" : ""}>${last ? "看看结果" : "下一题"}</button></div>`;
  } else if (z.q.phase === "answering" && v.item) {
    const item = z.def.body.items.find((it) => it.id === v.item_id);
    const fb = v.feedback && v.feedback.item_id === v.item_id && !v.feedback.correct ? v.feedback : null;
    const off = v.waiting || app.mode !== "writable";
    // 默认的话已经说了「再试一次」时，下面不再加小字
    const again = fb && fb.text === DEFAULT_FEEDBACK.wrong ? "" : v.answer_type === "choice" ? "再选一个试试。" : "改一改，再试试。";
    // 有过一次已存好的作答以后，才出现「要个提示」「看答案」（等存储时先变灰，不跳来跳去）
    const hintMax = Math.min(Array.isArray(item.hints) ? item.hints.length : 0, 3);
    const tools = z.answered[v.item_id]
      ? `<div class="btns tools">
          ${hintMax > 0 ? `<button class="btn big" type="button" data-act="hint" ${v.can_hint ? "" : "disabled"}>${hintIcon()}${v.hints.length >= hintMax ? "提示用完了" : "要个提示"}</button>` : ""}
          <button class="btn big" type="button" data-act="reveal" ${v.can_reveal ? "" : "disabled"}>看答案</button>
        </div>` : "";
    const after = (fb ? `<div class="bub bad" tabindex="-1"><p>${rich(fb.text)}</p>${again ? `<p class="muted small">${again}</p>` : ""}</div>` : "") +
      hintsHtml(v.hints) + tools;
    // 数字题、分数题：同一道题里只换输入框周围的部分，不重建输入框，焦点和平板上的输入法都不丢
    const formNow = /** @type {HTMLFormElement|null} */ (main.querySelector("[data-form]"));
    if (formNow && v.answer_type !== "choice" && formNow.dataset.item === v.item_id && !z.solved) {
      patchTyped(z, formNow, after);
      return;
    }
    body = itemHtml(item, { wrong: v.wrong_choices, disabled: app.mode !== "writable", busy: off, draft: z.draft[v.item_id] || {}, choices: v.choices || undefined, itemId: v.item_id }) +
      `<div class="after">${after}</div>`;
  } else if (z.q.phase === "done") {
    body = resultHtml(z);
  } else {
    body = `<div class="q"><p class="stem">马上就好……</p></div>`;
  }
  main.innerHTML = `<section class="quiz" aria-labelledby="quizTitle">
    <div class="quiz-head">
      <button class="back" type="button" data-act="back" aria-label="回到${homeName()}">${backIcon()}<span>${homeName()}</span></button>
      <div><h1 id="quizTitle">${esc(z.def.title)}</h1><p class="sub">${esc(z.node.title)}</p></div>
    </div>
    ${z.q.phase !== "done" ? progressHtml(z) : ""}
    ${body}
    <div class="statusbox">${statusHtml(z)}</div>
  </section>`;
  main.querySelectorAll("[data-choice]").forEach((b) => b.addEventListener("click", () => answer(/** @type {HTMLElement} */ (b).dataset.choice || "")));
  const form = /** @type {HTMLFormElement|null} */ (main.querySelector("[data-form]"));
  if (form) {
    const id = z.q.view.item_id || "";
    const sync = () => {
      const d = {};
      for (const el of /** @type {any} */ (form.elements)) if (el.name) d[el.name] = el.value;
      z.draft[id] = d;
      const empty = [...form.querySelectorAll("input")].some((el) => !/** @type {HTMLInputElement} */ (el).value.trim());
      /** @type {HTMLButtonElement} */ (form.querySelector("[type=submit]")).disabled = empty || z.q.view.waiting || app.mode !== "writable";
    };
    form.addEventListener("input", sync);
    form.addEventListener("submit", (e) => { e.preventDefault(); submitTyped(form); });
    // 分子写好按回车，跳到分母
    const top = form.querySelector("[name=a]");
    if (top) top.addEventListener("keydown", (e) => { if (/** @type {KeyboardEvent} */ (e).key === "Enter") { e.preventDefault(); /** @type {HTMLElement} */ (form.querySelector("[name=b]")).focus(); } });
    sync();
  }
  bindActs(z, main);
  focusQuiz(z);
}

/** 只更新输入框周围：进度、反馈、提示、按钮、保存状态；输入框本身只改可不可写。 */
function patchTyped(z, form, after) {
  const main = /** @type {HTMLElement} */ (document.querySelector("#main"));
  const v = z.q.view;
  const busy = v.waiting || app.mode !== "writable";
  form.querySelectorAll("input").forEach((el) => { /** @type {HTMLInputElement} */ (el).readOnly = busy; });
  const prog = main.querySelector(".prog");
  if (prog) prog.outerHTML = progressHtml(z);
  const a = /** @type {HTMLElement} */ (main.querySelector(".after"));
  a.innerHTML = after;
  const st = /** @type {HTMLElement} */ (main.querySelector(".statusbox"));
  st.innerHTML = statusHtml(z);
  form.dispatchEvent(new Event("input")); // 重新算「确定」能不能点
  bindActs(z, a);
  bindActs(z, st);
  focusQuiz(z);
}

/** 给 root 里的 data-act 按钮绑事件。 */
function bindActs(z, root) {
  root.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => {
    const act = /** @type {HTMLElement} */ (b).dataset.act;
    if (act === "back") { app.view = "chart"; renderChart(); }
    else if (act === "retry") retry();
    else if (act === "reload") location.reload();
    else if (act === "next") { z.solved = null; renderQuiz(); }
    else if (act === "hint") askHint();
    else if (act === "reveal") revealAnswer();
    else if (act === "again") { const node = z.node, def = z.def; app.quiz = null; startChallenge(node, def); }
  }));
}

/**
 * 重画以后放焦点：没存上 → 「再试」；刚答对 → 「下一题／看看结果」；答错 → 反馈区；结果 → 结果标题；新题 → 第一个可用选项。
 * 正在等待存储时不动焦点。换了一道题时滚回顶部。
 */
function focusQuiz(z) {
  const main = /** @type {HTMLElement} */ (document.querySelector("#main"));
  const v = z.q.view;
  const hint = z.focusHint;
  z.focusHint = false;
  const typedQ = v.answer_type === "number" || v.answer_type === "fraction";
  const wrongNow = !!(v.feedback && v.feedback.item_id === v.item_id && !v.feedback.correct);
  if (z.announce) {
    const live = document.getElementById("live");
    const text = z.announce;
    z.announce = null;
    if (live) { live.textContent = ""; setTimeout(() => { live.textContent = text; }, 50); }
  }
  const sel = v.failed ? "[data-act='retry'], [data-act='reload']"
    : z.q.phase === "done" && !z.solved ? ".result h2"
    : z.solved ? "[data-act='next']:not([disabled])"
    : v.waiting ? null
    : typedQ && (hint || wrongNow) ? "#ans-n, #ans-a"
    : hint ? ".hints li:last-child"
    : wrongNow ? ".bub.bad"
    : ".choice:not([disabled]), .numbox:not([disabled])";
  const key = `${z.q.phase}|${z.solved || v.item_id}`;
  if (key !== z.lastKey) { main.scrollTo({ top: 0, behavior: reducedMotion() ? "auto" : "smooth" }); z.lastKey = key; }
  if (!sel) return;
  const f = /** @type {HTMLElement|null} */ (main.querySelector(sel));
  if (f) {
    f.focus({ preventScroll: true });
    // 回到输入框时选中里面的数，孩子直接改；平板上输入法不收起
    if (f instanceof HTMLInputElement) f.select();
  }
}

function resultHtml(z) {
  z.resultSeen = true;
  const r = z.q.view.result;
  const st = nodeState(z.node.id);
  const need = Math.ceil(r.total * 4 / 5);
  let line;
  if (st === "lit" && !z.litBefore) line = "星星亮起来了！";
  else if (st === "lit") line = "星星还亮着。";
  else line = `第一次就答对 ${need} 道，星星就会亮。再来一遍试试？`;
  // 点亮动效只放一次；reduced-motion 时不加这个类，CSS 里也只在 no-preference 下才有动画
  const play = z.lit && !reducedMotion();
  z.lit = false;
  return `<div class="result">
    <div class="result-star ${play ? "lighting" : ""}" data-state="${st}">${starSvg(st, 11, 150)}</div>
    <h2 tabindex="-1">第一次就答对了 ${r.first_try_correct} 道，一共 ${r.total} 道</h2>
    <p>${esc(line)}</p>
    <div class="btns center"><button class="btn big" type="button" data-act="again">再来一遍</button><button class="btn ink big" type="button" data-act="back">回到${homeName()}</button></div>
  </div>`;
}

const starMini = () => `<svg class="mini" viewBox="0 0 100 100" aria-hidden="true"><path class="star-fill" d="${Sk.area(starPoints(52, 55, 38, 16))}"/><path class="k" d="${Sk.poly(starPoints(50, 52, 38, 16), 3, true, .6)}"/></svg>`;
const hintIcon = () => `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path class="k1" d="${Sk.ellipse(12, 10, 6, 6, 8, .4) + Sk.line(9.5, 17, 14.5, 17, 9, .2) + Sk.line(10, 20, 14, 20, 10, .2)}"/></svg>`;
const backIcon = () => `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path class="k" d="${Sk.line(19, 12, 5, 12, 2, .3) + Sk.line(5, 12, 11, 6, 3, .3) + Sk.line(5, 12, 11, 18, 4, .3)}"/></svg>`;

/* ============================================================
   写锁（规格 6.3）
   ============================================================ */
/**
 * 请求写锁，不抢、不 steal。返回 "got"（拿到了，一直持有）、"busy"（另一个窗口占着）、"nolock"（浏览器不支持或出错）。
 * @returns {Promise<"got"|"busy"|"nolock">}
 */
function requestLock() {
  const locks = navigator.locks;
  if (!locks || typeof locks.request !== "function") return Promise.resolve("nolock");
  return new Promise((resolve) => {
    let got = false;
    let p;
    try {
      p = locks.request("curio-writer", { ifAvailable: true }, (lock) => {
        if (!lock) { resolve("busy"); return undefined; }
        got = true;
        resolve("got");
        return new Promise(() => {}); // 一直不结束：锁一直持有
      });
    } catch { resolve("nolock"); return; }
    // 拿到锁以后，request 的 Promise 结束或出错，就是锁被收回了
    p.then(() => { if (got) lostLock(); }, () => { if (got) lostLock(); else resolve("nolock"); });
  });
}

function lostLock() {
  app.lockLost = true; // 先记下：恢复途中（还没有 session）也靠它停止写入
  if (app.session) app.session.committer.freeze();
  if (app.exploration) {
    const run = app.exploration;
    app.exploration = null;
    run.host?.destroy();
    app.view = location.hash === "#parent" ? "parent" : "chart";
  }
  if (app.mode === "stopped") return;
  app.mode = "readonly";
  app.why = "lost";
  renderBanner();
  renderCurrent();
}

/** 打开时读一次：干净不干净、上次备份、最早的记录（家长入口用）。只读事务。 */
async function readDeviceFacts() {
  if (!app.store) return null;
  const snap = await app.store.snapshot();
  app.clean = isClean(snap);
  app.lastBackup = snap.lastBackup || null;
  let first = null;
  for (const e of app.log ? app.log.events() : []) if (first === null || e.occurred_at < first) first = e.occurred_at;
  app.firstEventAt = first;
  return snap;
}

/** 只读窗口：照样 loadAll 并重放（只读事务，不写任何东西）。 */
async function enterReadonly(why) {
  app.mode = "readonly";
  app.why = why;
  if (app.store) {
    try {
      const d = await app.store.loadAll();
      app.hasIdentity = !!d.identity;
      const log = createLog();
      for (const raw of d.inbox) log.ingest(raw);
      app.log = log;
      await readDeviceFacts();
    } catch { app.hasIdentity = false; }
  }
  recompute();
  renderBanner();
  renderCurrent();
}

/** 拿到锁以后：正在恢复 → 可以写。 */
async function recover() {
  app.mode = "recovering";
  app.why = null;
  renderBanner();
  renderCurrent();
  let s;
  try {
    // 失锁以后，openSession 再要 ID 或时间就抛错，于是不再建身份、不再补写（规格 6.3「失去写锁」）
    s = await openSession(/** @type {any} */ (app.store), guardDeps({ ids, now }, () => app.lockLost));
  } catch (e) {
    if (app.lockLost || e instanceof LockLostError) { await enterReadonly("lost"); return; } // 只读地重放，星星照样画对
    console.error(e);
    renderStop("出错了", "请刷新页面。还不行的话，请家长看一看。");
    return;
  }
  if (app.lockLost) { s.committer.freeze(); await enterReadonly("lost"); return; } // 恢复刚结束时锁被收回
  app.session = s;
  app.log = app.session.log;
  app.hasIdentity = true;
  recompute();
  let snap;
  try { snap = await readDeviceFacts(); }
  catch (e) { console.error(e); s.committer.freeze(); renderStop("出错了", "请刷新页面。还不行的话，请家长看一看。"); return; }
  if (app.lockLost) { s.committer.freeze(); await enterReadonly("lost"); return; }
  // backup.md 5.1：拿着写锁时，把核对过的发布包存进 releases（没有才存；失败不要紧，下次再存）
  const rel = app.pack && app.pack.release;
  if (rel && !snap.releases.some((r) => r.release_id === rel.release_id)) {
    try { await /** @type {any} */ (app.store).putRelease(/** @type {any} */ (app.pack).raw, rel.release_id); } catch (e) { console.warn("发布包没存上，下次再存", e); }
  }
  if (app.lockLost) { s.committer.freeze(); await enterReadonly("lost"); return; }
  // backup.md 6.3：上次恢复没做完时，不进「可以写」
  app.mode = snap.restoring ? "unfinished" : "writable";
  renderBanner();
  renderCurrent();
}

async function relock() {
  if (app.relocking || app.lockLost) return;
  app.relocking = true;
  try {
    const r = await requestLock();
    if (r === "got") await recover();
    else await enterReadonly(r);
  } finally {
    app.relocking = false;
  }
}

/* ============================================================
   启动
   ============================================================ */
async function boot() {
  window.addEventListener("pageshow", (e) => { if (e.persisted) lostLock(); });
  // 家长页用 #parent，浏览器的「返回」也能回到星图
  app.view = location.hash === "#parent" ? "parent" : "chart";
  app.home = homeOfHash(location.hash);
  tree.collapsed = readCollapsed();
  applyCollapsed();
  syncNav();
  // 导航上的按钮：收起、展开知识索引，搜索，手机上打开索引抽屉
  document.addEventListener("click", (e) => {
    const b = /** @type {HTMLElement|null} */ (/** @type {HTMLElement} */ (e.target).closest?.("[data-act]"));
    if (!b || !b.closest(".ribbon, .bottomnav")) return;
    const act = b.dataset.act;
    if (act === "tree") setCollapsed(!tree.collapsed);
    else if (act === "search") {
      if (tree.collapsed) setCollapsed(false);
      /** @type {HTMLElement|null} */ (document.querySelector("#explorer [data-treeq]"))?.focus();
    } else if (act === "drawer") openDrawer();
  });
  // Esc 收起笔记（抽屉、对话框自己先接住 Esc）
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || !app.note || app.view !== "chart" || document.getElementById("drawer")) return;
    closeNote();
  });
  // 转到桌面宽度时，抽屉不再需要
  const wide = matchMedia("(min-width: 760px)");
  const onWide = () => { if (wide.matches) closeDrawer(false); };
  if (wide.addEventListener) wide.addEventListener("change", onWide); else wide.addListener(onWide);
  window.addEventListener("hashchange", async () => {
    closeDrawer(false);
    if (app.exploration && location.hash === "#parent") {
      if (!await closeExploration()) return;
      if (location.hash !== "#parent") { renderChart(); return; }
    }
    if (location.hash === "#parent") { if (app.view !== "parent") resetParent(); app.view = "parent"; }
    else {
      // 星图 / 地铁切换（#233）：在挑战、动手探索里只记下来，退出时回到这里
      const home = homeOfHash(location.hash), changed = home !== app.home;
      app.home = home;
      syncNav();
      if (app.view === "parent") app.view = "chart";
      else if (changed && app.view === "chart") { /* 换到另一个首页，笔记照旧开着 */ }
      else return;
    }
    if (app.mode !== "loading" && app.mode !== "stopped") renderCurrent();
  });
  if (!globalThis.crypto || !crypto.subtle || typeof crypto.getRandomValues !== "function") {
    // crypto.subtle 只在安全的网址（https 或 localhost）下有；没有它核对不了内容包，不能误报「内容包不完整」
    renderStop("请用 https 或 localhost 打开", "这样才能核对内容包。请家长换一个网址打开。");
    return;
  }
  // 请浏览器别自动清掉这台设备上的记录；没有这个功能或被拒绝时照常往下走
  try { if (navigator.storage && typeof navigator.storage.persist === "function") navigator.storage.persist().catch(() => {}); } catch { /* 照常往下走 */ }
  try {
    app.pack = await loadRelease();
  } catch (e) {
    if (e instanceof ReleaseError && e.kind === "update") renderStop("需要更新", "请家长更新 Curio，再打开。");
    else { console.error(e); renderStop("内容包不完整，请家长重新部署", ""); }
    return;
  }
  try {
    // 别的页面要升级数据库时，按失去写锁处理（backup.md 5.1）
    app.store = await openStore({ onVersionChange: () => lostLock() });
  } catch (e) {
    console.error(e);
    app.store = null;
    // 设备上的数据库比这一版新（演示页回退到旧提交时）：停在错误页，不建身份，数据不丢
    if (e && /** @type {any} */ (e).name === "VersionError") { renderStop("需要更新", "这台设备上的记录是新一点的 Curio 存的。请家长更新 Curio，再打开。记录不会丢。"); return; }
    await enterReadonly("nostore");
    return;
  }
  const r = await requestLock();
  if (r === "got") await recover();
  else await enterReadonly(r);
}

if (typeof document !== "undefined" && document.getElementById("main")) boot();
