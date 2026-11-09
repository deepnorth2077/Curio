// 好奇号 Curio · 竖切片 1a 的外壳（规格第 2 节、6.3）：读发布包 → 拿写锁 → 恢复 → 画星图 → 挑战 → 点亮。
// 读写 IndexedDB、取当前时间、生成 ULID、洗牌都在这里做，结果作为参数交给内核和引擎。
import { createLog } from "../kernel/js/log.js";
import { projectMastery, groupAttempts } from "../kernel/js/mastery.js";
import { createUlid } from "../kernel/js/ulid.js";
import { startQuiz, step } from "../engine/js/quiz.js";
import { openStore } from "./store.js";
import { openSession, localReceipt, assemble, guardDeps, LockLostError } from "./session.js";
import { FrozenError } from "./commit.js";

/** 这个外壳实现的引擎等级（内容规格 3.8）。1a 只实现第 1 级里的选择题挑战。 */
export const ENGINE_LEVEL = 1;
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
    text = canonicalJson({ engine_min: rel.engine_min, contracts: rel.contracts, nodes: rel.nodes, activities: rel.activities, assets: rel.assets });
  } catch (e) { throw new ReleaseError("broken", String(e && e.message)); }
  const h = await sha256Hex(new TextEncoder().encode(text));
  if (h !== rel.content_hash) throw new ReleaseError("broken", "content_hash 对不上");
  if (rel.release_id !== "rel_" + rel.content_hash) throw new ReleaseError("broken", "release_id 对不上");
}

/**
 * 读一份 .yaml.json，核对字节数和 SHA-256 以后才解析。
 * @param {URL} base release.json 的地址
 * @param {{path: string, bytes: number, sha256: string}} j
 * @param {typeof fetch} fetchFn
 */
async function fetchVerifiedJson(base, j, fetchFn) {
  if (!j || typeof j.path !== "string") throw new ReleaseError("broken", "清单条目没有 json");
  const res = await fetchFn(new URL(j.path, base), { cache: "no-cache" });
  if (!res.ok) throw new ReleaseError("broken", `读不到 ${j.path}`);
  const buf = new Uint8Array(await res.arrayBuffer());
  if (buf.byteLength !== j.bytes) throw new ReleaseError("broken", `${j.path} 的字节数对不上`);
  if ((await sha256Hex(buf)) !== j.sha256) throw new ReleaseError("broken", `${j.path} 的哈希对不上`);
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(buf)); }
  catch { throw new ReleaseError("broken", `${j.path} 不是合法的 JSON`); }
}

/**
 * 读发布包并逐个核对。任何一处对不上都抛 ReleaseError。
 * @param {URL} [url]
 * @param {typeof fetch} [fetchFn]
 * @returns {Promise<{release: any, nodes: any[], activities: Map<string, {entry: any, def: any|null}>}>}
 */
export async function loadRelease(url = RELEASE_URL, fetchFn = fetch) {
  let rel;
  try {
    const res = await fetchFn(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(String(res.status));
    rel = await res.json();
  } catch { throw new ReleaseError("broken", "读不到 release.json"); }
  await verifyManifest(rel);
  // TODO：以后按内容规格 3.8 检查 contracts（宿主不支持其中任何一个契约时不切换发布，提示「需要更新」）。1a 不承载自定义实验，先不处理。
  const nodes = [];
  for (const n of rel.nodes) {
    const def = await fetchVerifiedJson(url, n.json, fetchFn);
    if (!def || def.id !== n.id) throw new ReleaseError("broken", `知识点 ${n.id} 对不上`);
    nodes.push(def);
  }
  /** @type {Map<string, {entry: any, def: any|null}>} */
  const activities = new Map();
  for (const a of rel.activities) {
    let def = null;
    for (const f of a.files) {
      if (!f.json) continue;
      const v = await fetchVerifiedJson(url, f.json, fetchFn);
      if (/\/activity\.yaml$/.test(f.path)) def = v;
    }
    if (def && def.id !== a.id) throw new ReleaseError("broken", `活动 ${a.id} 对不上`);
    activities.set(a.id, { entry: a, def });
  }
  return { release: rel, nodes, activities };
}

/* ============================================================
   手绘线稿（从 prototype/index.html 的 sketchLib 拷来，确定性、带种子）
   ============================================================ */
function sketchLib() {
  const R = (seed) => { let s = ((seed | 0) * 2654435761) >>> 0 || 7; return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; };
  const f = (n) => Math.round(n * 10) / 10;
  function cr(p, closed) {
    const n = p.length; let d = `M${f(p[0][0])} ${f(p[0][1])}`;
    for (let i = 0; i < (closed ? n : n - 1); i++) {
      const p1 = p[i], p2 = p[(i + 1) % n]; const p0 = (!closed && i === 0) ? p1 : p[(i - 1 + n) % n]; const p3 = (!closed && i + 2 >= n) ? p2 : p[(i + 2) % n];
      d += `C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
    }
    return d;
  }
  function line(x1, y1, x2, y2, seed, j) {
    const r = R(seed); j = j == null ? 1 : j; const L = Math.hypot(x2 - x1, y2 - y1) || 1; const a = Math.min(1.8, .5 + L * .008) * j; const o = () => (r() - .5) * 2 * a;
    const nx = -(y2 - y1) / L, ny = (x2 - x1) / L, bow = (r() - .5) * Math.min(L * .035, 6) * j;
    return `M${f(x1 + o())} ${f(y1 + o())}Q${f((x1 + x2) / 2 + nx * bow)} ${f((y1 + y2) / 2 + ny * bow)} ${f(x2 + o())} ${f(y2 + o())}`;
  }
  function ellipse(cx, cy, rx, ry, seed, j) {
    const r = R(seed); j = j == null ? 1 : j; const N = 12, a0 = r() * Math.PI * 2, turn = 1.05 + r() * .06, p = [];
    for (let i = 0; i <= N; i++) { const t = a0 + i / N * Math.PI * 2 * turn, k = 1 + (r() - .5) * .07 * j; p.push([cx + Math.cos(t) * rx * k, cy + Math.sin(t) * ry * k]); }
    return cr(p, false);
  }
  function blob(cx, cy, rx, ry, seed) { const r = R(seed), N = 9, p = []; for (let i = 0; i < N; i++) { const t = i / N * Math.PI * 2, k = 1 + (r() - .5) * .1; p.push([cx + Math.cos(t) * rx * k, cy + Math.sin(t) * ry * k]); } return cr(p, true) + "Z"; }
  function rect(x, y, w, h, seed, j) { return line(x, y, x + w, y, seed, j) + line(x + w, y, x + w, y + h, seed + 1, j) + line(x + w, y + h, x, y + h, seed + 2, j) + line(x, y + h, x, y, seed + 3, j); }
  function poly(pts, seed, closed, j) { let d = ""; const n = pts.length; for (let i = 0; i < (closed ? n : n - 1); i++) { const a = pts[i], b = pts[(i + 1) % n]; d += line(a[0], a[1], b[0], b[1], seed + i * 3, j); } return d; }
  function area(pts) { return "M" + pts.map((q) => f(q[0]) + " " + f(q[1])).join("L") + "Z"; }
  return { line, ellipse, blob, rect, poly, area, R };
}
const Sk = sketchLib();

/* ============================================================
   小工具
   ============================================================ */
const $ = (sel) => /** @type {HTMLElement} */ (document.querySelector(sel));
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
/** 文字里的 1/4 排成上下结构（内容规格 3.7）。 */
const rich = (s) => esc(s).replace(/(\d+)\/(\d+)/g, (_m, a, b) => `<span class="frac" aria-label="${b}分之${a}"><span>${a}</span><span>${b}</span></span>`);
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

const ulid = createUlid();
const rand10 = () => crypto.getRandomValues(new Uint8Array(10));
const ids = {
  learner: () => "lrn_" + ulid(Date.now(), rand10()),
  device: () => "dev_" + ulid(Date.now(), rand10()),
  event: () => "evt_" + ulid(Date.now(), rand10()),
  attempt: () => "att_" + ulid(Date.now(), rand10()),
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
      body += `<path class="k1" d="${Sk.line(50 + Math.cos(a) * 44, 52 + Math.sin(a) * 44, 50 + Math.cos(a) * 49, 52 + Math.sin(a) * 49, seed + 20 + i, .4)}"/>`;
    }
  } else if (state === "explored") {
    body += `<path class="star-half" d="${Sk.area(starPoints(50, 52, 38, 16).filter((p) => p[0] <= 50.5).concat([[50, 90], [50, 14]]))}" opacity=".7"/>`;
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
    label = `一个圆平均分成 ${n} 份，涂色 ${k} 份`;
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
    label = fig.type === "rect" ? `一个长方形平均分成 ${fig.parts} 份，涂色 ${fig.shaded} 份` : `一个长方形分成大小不一样的 ${widths.length} 份`;
  } else if (fig.type === "number-line") {
    const from = Number(fig.from), to = Number(fig.to), stp = Number(fig.step) || 1;
    const x = (v) => 20 + (v - from) / ((to - from) || 1) * 160;
    vb = "0 0 200 70";
    inner += `<path class="k" d="${Sk.line(14, 34, 188, 34, seed, .4)}"/><path class="k1" d="${Sk.line(188, 34, 181, 30, seed + 1, .3) + Sk.line(188, 34, 181, 38, seed + 2, .3)}"/>`;
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
const STATE_WORD = { untouched: "还没点亮", explored: "探索过", lit: "已点亮" };
const app = {
  /** @type {"loading"|"readonly"|"recovering"|"writable"|"stopped"} */ mode: "loading",
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
  view: /** @type {"chart"|"quiz"} */ ("chart"),
  notice: /** @type {string|null} */ (null),
};

function recompute() {
  app.mastery = app.log ? projectMastery(app.log.events()) : null;
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
  }
  b.innerHTML = html;
  b.hidden = !html;
  const r = b.querySelector('[data-act="relock"]');
  if (r) r.addEventListener("click", relock);
  const l = b.querySelector('[data-act="reload"]');
  if (l) l.addEventListener("click", () => location.reload());
}

/** 整页的提示（内容包坏了、需要更新、出错）。 */
function renderStop(title, text) {
  app.mode = "stopped";
  $("#banner").hidden = true;
  $("#main").innerHTML = `<section class="stop"><div class="stop-art">${starSvg("untouched", 5, 120)}</div><h1>${esc(title)}</h1>${text ? `<p>${esc(text)}</p>` : ""}</section>`;
}

/* ============================================================
   星图
   ============================================================ */
function skySvg() {
  const r = Sk.R(42);
  let dots = "";
  for (let i = 0; i < 46; i++) {
    const x = r() * 1000, y = r() * 600, s = .8 + r() * 1.6;
    dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${s.toFixed(1)}" class="sky-dot"/>`;
  }
  let lines = "";
  for (let i = 0; i < 5; i++) {
    const y = 80 + i * 110 + r() * 20;
    lines += `<path class="kq sky-line" d="${Sk.line(-20, y, 1020, y + (r() - .5) * 60, 300 + i, 1)}"/>`;
  }
  return `<svg class="sky" viewBox="0 0 1000 600" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${lines}${dots}</svg>`;
}

function renderChart() {
  app.view = "chart";
  const main = $("#main");
  if (app.mode === "readonly" && !app.hasIdentity) { main.innerHTML = ""; return; }
  const nodes = app.pack ? app.pack.nodes : [];
  const lit = nodes.filter((n) => nodeState(n.id) === "lit").length;
  const stars = nodes.map((n, i) => {
    const st = nodeState(n.id);
    const going = app.quiz && app.quiz.node.id === n.id && pendingQuiz(app.quiz);
    return `<li><button class="star" type="button" data-node="${esc(n.id)}" data-state="${st}" aria-label="${esc(n.title)}，${STATE_WORD[st]}${going ? "，正在挑战" : ""}">
      ${starSvg(st, 11 + i * 7, 132)}
      <span class="star-name">${esc(n.title)}</span>
      <span class="pill ${st === "lit" ? "lit" : ""}">${going ? (app.quiz.q.phase === "done" ? "看结果" : "接着做") : STATE_WORD[st]}</span>
    </button></li>`;
  }).join("");
  main.innerHTML = `<section class="chart" aria-labelledby="chartTitle">
    ${skySvg()}
    <div class="chart-head"><h1 id="chartTitle">星图</h1><p class="sub">点亮了 ${lit} 颗，一共 ${nodes.length} 颗</p></div>
    <ul class="stars">${stars}</ul>
    <p class="chart-tip muted">${app.mode === "writable" ? "点一颗星，开始挑战。" : app.mode === "recovering" ? "正在准备……" : ""}</p>
    <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
  </section>`;
  main.querySelectorAll("[data-node]").forEach((b) => b.addEventListener("click", () => openNode(/** @type {HTMLElement} */ (b).dataset.node || "")));
}

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
   开始挑战（规格 6.3「开始一次挑战」）
   ============================================================ */
function openNode(nodeId) {
  if (app.mode !== "writable" || !app.session) {
    toast(app.mode === "recovering" ? "正在准备，等一下再点。" : app.why === "lost" ? "请刷新页面。" : "这里只能看，不能开始挑战。");
    return;
  }
  if (app.quiz && app.quiz.node.id === nodeId && pendingQuiz(app.quiz)) { app.view = "quiz"; renderQuiz(); return; }
  const node = /** @type {any} */ (app.pack).nodes.find((n) => n.id === nodeId);
  const acts = (node.activities || []).map((id) => /** @type {any} */ (app.pack).activities.get(id)).filter(Boolean);
  const quizzes = acts.filter((a) => a.entry.kind === "quiz" && a.def);
  if (!quizzes.length) { toast("这个还在做。"); return; }
  startChallenge(node, quizzes[0].def);
}

/** 这次挑战还没做完，或者做完了但孩子还没看到结果（最后一道存好前回了星图）。 */
const pendingQuiz = (z) => z.q.phase !== "done" || !z.resultSeen;

/** 这台设备上这个活动有没有合法完成过。 */
function completedBefore(activityId) {
  const s = /** @type {any} */ (app.session);
  const bad = new Set(projectMastery(s.log.events()).conflicts.map((c) => c.attempt_id));
  for (const [att, evs] of groupAttempts(s.log.events())) {
    if (bad.has(att)) continue;
    const f = evs[0];
    if (f.device_id === s.identity.device_id && f.content.activity_id === activityId && evs[evs.length - 1].verb === "attempt.completed") return true;
  }
  return false;
}

function startChallenge(node, def) {
  const ids0 = (def.body && Array.isArray(def.body.items) ? def.body.items : []).map((it) => it && it.id);
  const order = def.body && def.body.shuffle ? shuffled(ids0) : ids0;
  const mode = completedBefore(def.id) ? "retry" : "first";
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
      if (!pl.correct) z.wrongBy[pl.item_id] = [...(z.wrongBy[pl.item_id] || []), pl.response];
      else z.solved = pl.item_id;
    }
    z.q = step(z.q, { type: "saved", id: cur.id });
    if (z.q.phase === "done") { recompute(); }
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
  else if (z.q.phase === "done") renderChart(); // 存好时孩子已经回到星图：重画，星星换样子
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

function itemHtml(item, opts) {
  const { wrong = [], right = null, disabled = false } = opts;
  const choices = item.answer ? item.answer.choices : item.choices;
  return `<div class="q">
    ${item.figure ? `<div class="figbox">${figureSvg(item.figure, 9)}</div>` : ""}
    <p class="stem">${rich(item.stem)}</p>
    <div class="choices" role="group" aria-label="选一个">
      ${choices.map((c) => {
        const isWrong = wrong.includes(c.id), isRight = right === c.id;
        return `<button type="button" class="choice ${isWrong ? "wrong" : ""} ${isRight ? "right" : ""}" data-choice="${esc(c.id)}" ${disabled || isWrong || right ? "disabled" : ""}>${rich(c.text)}${isWrong ? '<span class="sr">，选过了，不对</span>' : ""}</button>`;
      }).join("")}
    </div>
  </div>`;
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
    // 刚答对的题：先看反馈，再点「下一题」
    const right = solvedItem.answer.choices.find((c) => c.correct === true).id;
    const fb = v.feedback && v.feedback.item_id === z.solved ? v.feedback.text : "";
    const last = z.q.phase !== "answering";
    body = itemHtml(solvedItem, { wrong: z.wrongBy[z.solved] || [], right, disabled: true }) +
      `<div class="bub good" role="status">${starMini()}<p>${rich(fb)}</p></div>
       <div class="btns"><button class="btn ink big" type="button" data-act="next" ${last && z.q.phase !== "done" ? "disabled" : ""}>${last ? "看看结果" : "下一题"}</button></div>`;
  } else if (z.q.phase === "answering" && v.item) {
    const fb = v.feedback && v.feedback.item_id === v.item_id && !v.feedback.correct ? v.feedback : null;
    body = itemHtml(v.item, { wrong: v.wrong_choices, disabled: v.waiting || app.mode !== "writable" }) +
      (fb ? `<div class="bub bad" role="status" tabindex="-1"><p>${rich(fb.text)}</p><p class="muted small">再选一个试试。</p></div>` : "");
  } else if (z.q.phase === "done") {
    body = resultHtml(z);
  } else {
    body = `<div class="q"><p class="stem">马上就好……</p></div>`;
  }
  main.innerHTML = `<section class="quiz" aria-labelledby="quizTitle">
    <div class="quiz-head">
      <button class="back" type="button" data-act="back" aria-label="回到星图">${backIcon()}<span>星图</span></button>
      <div><h1 id="quizTitle">${esc(z.def.title)}</h1><p class="sub">${esc(z.node.title)}</p></div>
    </div>
    ${z.q.phase !== "done" ? progressHtml(z) : ""}
    ${body}
    ${statusHtml(z)}
  </section>`;
  main.querySelectorAll("[data-choice]").forEach((b) => b.addEventListener("click", () => answer(/** @type {HTMLElement} */ (b).dataset.choice || "")));
  main.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => {
    const act = /** @type {HTMLElement} */ (b).dataset.act;
    if (act === "back") { renderChart(); }
    else if (act === "retry") retry();
    else if (act === "reload") location.reload();
    else if (act === "next") { z.solved = null; renderQuiz(); }
    else if (act === "again") { const node = z.node, def = z.def; app.quiz = null; startChallenge(node, def); }
  }));
  focusQuiz(z);
}

/**
 * 重画以后放焦点：没存上 → 「再试」；刚答对 → 「下一题／看看结果」；答错 → 反馈区；结果 → 结果标题；新题 → 第一个可用选项。
 * 正在等待存储时不动焦点。换了一道题时滚回顶部。
 */
function focusQuiz(z) {
  const main = /** @type {HTMLElement} */ (document.querySelector("#main"));
  const v = z.q.view;
  const sel = v.failed ? "[data-act='retry'], [data-act='reload']"
    : z.q.phase === "done" && !z.solved ? ".result h2"
    : z.solved ? "[data-act='next']:not([disabled])"
    : v.waiting ? null
    : v.feedback && v.feedback.item_id === v.item_id && !v.feedback.correct ? ".bub.bad"
    : ".choice:not([disabled])";
  const key = `${z.q.phase}|${z.solved || v.item_id}`;
  if (key !== z.lastKey) { main.scrollTo({ top: 0, behavior: reducedMotion() ? "auto" : "smooth" }); z.lastKey = key; }
  if (!sel) return;
  const f = /** @type {HTMLElement|null} */ (main.querySelector(sel));
  if (f) f.focus({ preventScroll: true });
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
  return `<div class="result">
    <div class="result-star" data-state="${st}">${starSvg(st, 11, 150)}</div>
    <h2 tabindex="-1">第一次就答对了 ${r.first_try_correct} 道，一共 ${r.total} 道</h2>
    <p>${esc(line)}</p>
    <div class="btns center"><button class="btn big" type="button" data-act="again">再来一遍</button><button class="btn ink big" type="button" data-act="back">回到星图</button></div>
  </div>`;
}

const starMini = () => `<svg class="mini" viewBox="0 0 100 100" aria-hidden="true"><path class="star-fill" d="${Sk.area(starPoints(52, 55, 38, 16))}"/><path class="k" d="${Sk.poly(starPoints(50, 52, 38, 16), 3, true, .6)}"/></svg>`;
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
  if (app.mode === "stopped") return;
  app.mode = "readonly";
  app.why = "lost";
  renderBanner();
  if (app.view === "quiz") renderQuiz(); else renderChart();
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
    } catch { app.hasIdentity = false; }
  }
  recompute();
  renderBanner();
  renderChart();
}

/** 拿到锁以后：正在恢复 → 可以写。 */
async function recover() {
  app.mode = "recovering";
  app.why = null;
  renderBanner();
  renderChart();
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
  app.mode = "writable";
  renderBanner();
  renderChart();
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
  if (!globalThis.crypto || !crypto.subtle || typeof crypto.getRandomValues !== "function") {
    // crypto.subtle 只在安全的网址（https 或 localhost）下有；没有它核对不了内容包，不能误报「内容包不完整」
    renderStop("请用 https 或 localhost 打开", "这样才能核对内容包。请家长换一个网址打开。");
    return;
  }
  try {
    app.pack = await loadRelease();
  } catch (e) {
    if (e instanceof ReleaseError && e.kind === "update") renderStop("需要更新", "请家长更新好奇号，再打开。");
    else { console.error(e); renderStop("内容包不完整，请家长重新部署", ""); }
    return;
  }
  try {
    app.store = await openStore();
  } catch (e) {
    console.error(e);
    app.store = null;
    await enterReadonly("nostore");
    return;
  }
  const r = await requestLock();
  if (r === "got") await recover();
  else await enterReadonly(r);
}

if (typeof document !== "undefined" && document.getElementById("main")) boot();
