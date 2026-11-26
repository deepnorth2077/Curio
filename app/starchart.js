// Curio · 正式星图（#230）：从原型首页主题形状试玩版（prototype/index.html 的 `?shapes=1`，#176、#184）移植。
// 数据只来自发布包的知识点目录（catalog）、已发布卡（pack.nodes）、掌握度投影和当前年级。
// 这里大多是「数据 → SVG 字符串」的纯函数，node 里能测；读 DOM 尺寸的只有 placeChartLabels、animateOverview 和 nearestCons。
import { Sk } from "./sketch.js";
import { SHAPES } from "./constellation-shapes.js";
import { groupAttempts, attemptRule } from "../kernel/js/mastery.js";

/* ============================================================
   常量（照原型的 THEMES、BAND_NAME、BANDS、themeShapes）
   ============================================================ */
/** 主题：扇区角度（度，逆时针，0 在右边）、名字、颜色变量、初中起的分科名。 */
export const THEMES = Object.freeze({
  num: { g: "math", name: "数与运算", c: "--l1", sec: [100, 140] },
  rel: { g: "math", name: "数量关系", c: "--l2", sec: [140, 180] },
  geo: { g: "math", name: "图形与测量", c: "--l3", sec: [180, 220] },
  stat: { g: "math", name: "统计与概率", c: "--l4", sec: [220, 260] },
  mat: { g: "science", name: "物质", c: "--l5", sec: [40, 80], later: "化学" },
  ene: { g: "science", name: "能量与运动", c: "--l6", sec: [0, 40], later: "物理" },
  life: { g: "science", name: "生命", c: "--l7", sec: [-40, 0], later: "生物" },
  earth: { g: "science", name: "地球与宇宙", c: "--l8", sec: [-80, -40], later: "地理" },
});
export const THEME_ORDER = Object.freeze(["num", "rel", "geo", "stat", "mat", "ene", "life", "earth"]);
/** 每个主题的星座轮廓（constellation-shapes.js 里的名字）。 */
export const THEME_SHAPES = Object.freeze({ num: "stairs", rel: "scale", geo: "kite", stat: "bars", mat: "icecream", ene: "plane", life: "fish", earth: "moon" });
/** 五个学段圈：G1–2、G3–4、G5–6、G7–9、G10–12。 */
export const BAND_NAME = Object.freeze(["一二年级", "三四年级", "五六年级", "初中", "高中"]);
export const GRADE_NAME = Object.freeze({ G1: "一年级", G2: "二年级", G3: "三年级", G4: "四年级", G5: "五年级", G6: "六年级", G7: "初一", G8: "初二", G9: "初三", G10: "高一", G11: "高二", G12: "高三" });
/** 原型原来的五圈半径：三四年级那一圈最宽。 */
export const BASE_BANDS = Object.freeze([[40, 84], [84, 216], [216, 264], [264, 310], [310, 350]].map((b) => Object.freeze(b)));
/** BASE_BANDS 里最宽的那一圈。 */
export const WIDE_BAND = 1;
/** 四种样子的名字（图例、读屏）。 */
export const STATE_WORD = Object.freeze({ lit: "点亮", explored: "探过", untouched: "未探", closed: "未开放" });
/** 图例的顺序。 */
export const STATES = Object.freeze(["lit", "explored", "untouched", "closed"]);

const C = 380;
const polar = (th, r) => [C + r * Math.cos(th * Math.PI / 180), C - r * Math.sin(th * Math.PI / 180)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const f1 = (n) => n.toFixed(1);

/* ============================================================
   数据：目录 → 点、星座
   ============================================================ */
/** 年级（"G8" 或 8）→ 学段圈 0～4。 @param {string|number} g */
export function bandOfGrade(g) {
  const n = typeof g === "number" ? g : Number(String(g).replace(/^G/, ""));
  if (n <= 2) return 0;
  if (n <= 4) return 1;
  if (n <= 6) return 2;
  if (n <= 9) return 3;
  return 4;
}

/** 当前年级 → 当前圈；没填资料（null）时 null。 @param {number|null} grade */
export function currentBandOf(grade) {
  return Number.isInteger(grade) && grade >= 1 && grade <= 12 ? bandOfGrade(grade) : null;
}

/**
 * 五圈的半径。有当前圈时，把原来最宽的那一圈的宽度换给当前圈，其余照年级顺序排，最外圈半径不变；没有时就是原来的 BASE_BANDS。
 * @param {number|null} cur
 * @returns {number[][]}
 */
export function overviewBands(cur) {
  if (cur == null) return BASE_BANDS.map((b) => b.slice());
  const widths = BASE_BANDS.map(([a, b]) => b - a);
  [widths[WIDE_BAND], widths[cur]] = [widths[cur], widths[WIDE_BAND]];
  let inner = BASE_BANDS[0][0];
  return widths.map((w) => { const band = [inner, inner + w]; inner += w; return band; });
}

/**
 * 一颗星的样子：已开放的星取掌握度投影（lit / explored / untouched），没开放的是 closed。
 * @param {boolean} open
 * @param {string|undefined} masteryState
 */
export function pointState(open, masteryState) {
  if (!open) return "closed";
  return masteryState === "lit" || masteryState === "explored" ? masteryState : "untouched";
}

/**
 * 星图要用的全部数据。
 * @param {{catalog: any, nodes: any[], mastery?: any, grade: number|null, progress?: Record<string, number>|null}} input
 *   catalog：发布包里的目录（catalog/1）；nodes：已发布卡；mastery：projectMastery 的结果；grade：当前年级或 null；
 *   progress：nodeProgress 的结果（来过的星 → 进度 0～1），星图详情画进度弧用。
 */
export function buildChart({ catalog, nodes, mastery, grade, progress = null }) {
  const cards = new Map((nodes || []).map((n) => [n.id, n]));
  const states = (mastery && mastery.nodes) || {};
  const list = (catalog && Array.isArray(catalog.points)) ? catalog.points : [];
  const points = list.filter((p) => THEMES[p.theme]).map((p, i) => {
    const card = cards.get(p.id);
    const open = !!card;
    return {
      id: p.id, title: p.title, grade: p.grade, theme: p.theme, unit: p.unit || "",
      prereq: (p.prerequisites || []).slice(), band: bandOfGrade(p.grade), open,
      state: pointState(open, states[p.id] && states[p.id].state),
      acts: open && Array.isArray(card.activities) && card.activities.length > 0,
      seed: 11 + i * 7,
      // 图鉴编号（照原型 no: i+1）：目录里的先后
      no: i + 1,
      progress: progress && Object.prototype.hasOwnProperty.call(progress, p.id) ? progress[p.id] : null,
    };
  });
  const byId = new Map(points.map((p) => [p.id, p]));
  /** @type {Map<string, {id: string, theme: string, band: number, points: any[]}>} */
  const consById = new Map();
  for (const p of points) {
    const id = consId(p);
    if (!consById.has(id)) consById.set(id, { id, theme: p.theme, band: p.band, points: [] });
    consById.get(id).points.push(p);
  }
  const links = new Set();
  for (const p of points) for (const q of p.prereq) {
    const a = byId.get(q);
    if (a && consId(a) !== consId(p)) links.add(consId(a) + ">" + consId(p));
  }
  const currentBand = currentBandOf(grade);
  return {
    points, byId, cons: [...consById.values()], consById, links: [...links],
    grade: currentBand == null ? null : grade, currentBand, wideBand: currentBand == null ? WIDE_BAND : currentBand,
    lit: points.filter((p) => p.state === "lit").length,
  };
}
export const consId = (p) => p.theme + "|" + p.band;
/** 星座的名字：初中起科学主题前面加分科名。 */
export const consName = (c) => { const t = THEMES[c.theme]; return (c.band >= 3 && t.later ? t.later + " · " : "") + t.name; };

/**
 * 每颗来过的星走了多少（0～1），照原型「登陆过」那一圈进度弧：
 * 动手探索按做完的站数 ÷ 总站数（整次完成算 1），挑战按掌握度投影里最好的首答成绩；取最大的。
 * 只要有这颗星的事件就算来过（值可以是 0）。只看合格的尝试（attemptRule 为 0）。
 * @param {any[]} events 已接收的事件 @param {any} mastery projectMastery 的结果 @param {(activityId: string) => number} stations 动手探索的站数
 * @returns {Record<string, number>}
 */
export function nodeProgress(events, mastery, stations) {
  /** @type {Record<string, number>} */
  const out = {};
  const bump = (id, v) => { out[id] = Math.max(out[id] ?? 0, Math.min(1, Math.max(0, v))); };
  for (const e of events || []) { const id = e && e.content && e.content.node_id; if (typeof id === "string") bump(id, 0); }
  const observations = new Map();
  for (const evs of groupAttempts(events || []).values()) {
    if (attemptRule(evs)) continue;
    const c = evs[0].content;
    if (!c || c.activity_kind !== "simulation") continue;
    if (evs[evs.length - 1].verb === "attempt.completed") { bump(c.node_id, 1); continue; }
    const total = stations(c.activity_id);
    if (!total) continue;
    // 离开再回来会产生另一条尝试。同一个孩子在这颗星同一活动做过的站只算一次。
    const key = JSON.stringify([evs[0].learner_id, c.node_id, c.activity_id]);
    const done = observations.get(key) ?? new Set();
    observations.set(key, done);
    for (const e of evs) {
      const v = e.payload && e.payload.value;
      if (e.verb === "sim.observed" && e.payload.observable === "station.completed" && Number.isInteger(v) && v >= 1 && v <= total) done.add(v);
    }
    bump(c.node_id, done.size / total);
  }
  const nodes = (mastery && mastery.nodes) || {};
  for (const [id, m] of Object.entries(nodes)) {
    if (m && m.best && m.best.answered > 0) bump(id, m.best.correct / m.best.answered);
  }
  return out;
}

/** 图鉴编号（照原型「图鉴 No.093」的写法）。 @param {number} no */
export const specimenNo = (no) => "No." + String(no).padStart(3, "0");

/**
 * 反向链接（照原型 nextOnes）：目录里把这颗星写进 prerequisites 的星，按目录先后。
 * @param {{points: any[]}} model @param {string} id
 */
export const nextPoints = (model, id) => model.points.filter((x) => x.prereq.includes(id));

/* ============================================================
   星形状态标记（照原型 chartStar；新加 closed）
   ============================================================ */
const STAR_PTS = Array.from({ length: 10 }, (_, i) => {
  const a = -Math.PI / 2 + i * Math.PI / 5, radius = i % 2 ? .49 : 1;
  return [radius * Math.cos(a) * 10, radius * Math.sin(a) * 10];
});
const STAR_OUTLINE = Sk.area(STAR_PTS);
const STAR_HALF = Sk.area([0, 9, 8, 7, 6, 5].map((i) => STAR_PTS[i]));
/** 一颗星形标记，半径 r（以原点为中心）。 @param {string} state @param {number} r */
export function chartStar(state, r) {
  let mark = "";
  // 没开放的星不填色：轮廓的笔画会从星里穿过去，和「未探」（纸色实心）一眼分得开
  if (state !== "closed") mark += `<path d="${STAR_OUTLINE}" class="shape-face"/>`;
  if (state === "explored") mark += `<path d="${STAR_HALF}" class="shape-half"/>`;
  mark += `<path d="${STAR_OUTLINE}" class="shape-outline"/>`;
  if (state === "lit") mark += `<path d="M0 -12v-2.4 M9 -9l1.8 -1.8 M12 0h2.4 M9 9l1.8 1.8 M0 12v2.4 M-9 9l-1.8 1.8 M-12 0h-2.4 M-9 -9l-1.8 -1.8" class="star-rays"/>`;
  return `<g class="shape-mark ${state}" transform="scale(${+(r / 10).toFixed(3)})">${mark}</g>`;
}
/** 图例：四种样子。 */
export function legendHtml() {
  return STATES.map((st) => `<span><svg aria-hidden="true" width="18" height="18" viewBox="-16 -16 32 32">${chartStar(st, 10)}</svg>${STATE_WORD[st]}</span>`).join("");
}
/** 「有活动」的小火花（星图详情和地铁共用）。 */
export const spark = (x, y, arm, seed) => `<path class="k1 spark" d="${Sk.line(x - arm, y + arm, x + arm, y - arm, seed, .1) + Sk.line(x - arm, y - arm, x + arm, y + arm, seed + 1, .1)}"/>`;

/* ============================================================
   主题轮廓（照原型 chartShape、chartShapeFigure）
   ============================================================ */
/** 轮廓的笔画和每颗星的位置（以 ±55 为界的坐标）。 @param {{theme: string, points: any[]}} c */
export function chartShape(c) {
  const shape = SHAPES[THEME_SHAPES[c.theme]];
  const strokes = shape.strokes.map((stroke) => stroke.map((p) => Array.isArray(p) ? p : shape.stars[p]));
  const count = c.points.length, anchors = shape.stars;
  const pts = c.points.slice(0, anchors.length).map((_, i) => anchors[Math.floor(i * anchors.length / Math.min(count, anchors.length))]);
  // 多出来的星放在原来笔画上最空的地方
  if (count > pts.length) {
    const candidates = [];
    for (const stroke of strokes) for (let i = 1; i < stroke.length; i++) {
      const [ax, ay] = stroke[i - 1], [bx, by] = stroke[i];
      const steps = Math.ceil(Math.hypot(bx - ax, by - ay) / 3);
      for (let j = 0; j < steps; j++) candidates.push([ax + (bx - ax) * j / steps, ay + (by - ay) * j / steps]);
    }
    while (pts.length < count) {
      let best = candidates[0], gap = -1;
      for (const point of candidates) {
        const distance = Math.min(...pts.map(([x, y]) => Math.hypot(x - point[0], y - point[1])));
        if (distance > gap) { best = point; gap = distance; }
      }
      pts.push(best);
    }
  }
  return { strokes, pts };
}

function shapeFigure(c, radius) {
  const scale = radius / 55;
  const { strokes, pts } = chartShape(c);
  const point = ([x, y]) => [x * scale, y * scale];
  let fig = strokes.map((stroke, i) => `<path class="shape-stroke" d="${Sk.poly(stroke.map(point), 340 + i * 80, false, .18)}"/>`).join("");
  c.points.forEach((p, i) => {
    const [x, y] = point(pts[i]);
    const others = pts.filter((_, j) => j !== i).map(([px, py]) => Math.hypot(pts[i][0] - px, pts[i][1] - py));
    const nearest = others.length ? Math.min(...others) : 20;
    const r = Math.min(7.2, nearest * .42) * scale;
    let mark = chartStar(p.state, r);
    if (p.acts) { const offset = r * 1.22 + 1, arm = Math.max(1.2, r * .43); mark += spark(-offset, -offset, arm, p.seed); }
    fig += `<g class="shape-point" data-point="${esc(p.id)}" data-state="${p.state}" transform="translate(${f1(x)} ${f1(y)})">${mark}</g>`;
  });
  return fig;
}

/* ============================================================
   总览（照原型 consGeom、renderOverview）
   ============================================================ */
/** 一个星座在总览上的位置、大小、点击半径。 */
export function consGeom(c, bands, model) {
  const t = THEMES[c.theme], [a, b] = bands[c.band], th = (t.sec[0] + t.sec[1]) / 2;
  const cur = c.band === model.wideBand, shape = c.band === model.currentBand;
  const stagger = cur ? (THEME_ORDER.indexOf(c.theme) % 2 ? 18 : -14) : 0;
  const [x, y] = polar(th, (a + b) / 2 + stagger);
  const n = c.points.length;
  const rr = shape ? 39 : cur ? Math.min(44, 14 + n * 2.4) : Math.min(14, 6 + n * 1.5);
  const pts = shape ? null : c.points.map((_, i) => { const ang = i * 2.39996 + c.band, rad = rr * Math.sqrt((i + .6) / n); return [Math.cos(ang) * rad, Math.sin(ang) * rad]; });
  // 点触目标：至少半径 34（手机上 760 宽的图缩到 360 左右，约 32 像素）；重叠时按最近的星座算（nearestCons）
  return { x, y, rr, pts, cur, shape, hit: Math.max(rr + (cur ? 16 : 10), 34) };
}

function clusterFigure(c, geo, ci) {
  let fig = "";
  const idx = Object.fromEntries(c.points.map((p, i) => [p.id, i]));
  c.points.forEach((p, i) => p.prereq.forEach((q) => {
    if (q in idx) { const A = geo.pts[idx[q]], B = geo.pts[i]; fig += `<path class="${geo.cur ? "k1" : "kq"}" d="${Sk.line(A[0], A[1], B[0], B[1], ci * 31 + i, .25)}" opacity="${geo.cur ? .55 : .6}"/>`; }
  }));
  c.points.forEach((p, i) => {
    const [x, y] = geo.pts[i], r = geo.cur ? 4.4 : 2.6;
    fig += `<circle class="dot ${p.state}" data-point="${esc(p.id)}" data-state="${p.state}" cx="${f1(x)}" cy="${f1(y)}" r="${r}"/>`;
    if (p.acts) fig += geo.cur
      ? `<path class="k1 spark" d="${Sk.line(x + 4, y - 4, x + 9, y - 9, p.seed) + Sk.line(x + 5, y - 10, x + 9, y - 4, p.seed + 1)}"/>`
      : `<path class="k1 spark" d="${Sk.line(x + 3, y - 3, x + 7, y - 7, p.seed) + Sk.line(x + 3, y - 7, x + 7, y - 3, p.seed + 1)}"/>`;
  });
  return fig;
}

/** 火箭（和顶栏的标志同一张图），画在星图中心。 */
const SHIP = `<path class="k" d="M50 10C62 26 66 40 64 58C62 70 58 76 50 78C42 76 38 70 36 58C34 40 38 26 50 10Z"/><circle cx="50" cy="40" r="7" class="k1"/><path class="k1" d="M37 58L25 76L39 72M63 58L75 76L61 72"/><path d="M44 80q6 14 12 0z" fill="var(--accent)" opacity=".85"/>`;

/**
 * 总览的 SVG 内容（viewBox 0 0 760 760）。
 * @param {ReturnType<typeof buildChart>} model
 * @returns {{svg: string, geometry: Record<string, ReturnType<typeof consGeom>>, bands: number[][]}}
 */
export function overviewSvg(model) {
  const bands = overviewBands(model.currentBand);
  const cb = model.currentBand;
  let h = "";
  if (cb != null) { const [s, e] = bands[cb]; h += `<circle class="band-now" cx="${C}" cy="${C}" r="${(s + e) / 2}" stroke-width="${e - s}"/>`; }
  bands.forEach(([, b], i) => { h += `<path class="kq ring" d="${Sk.ellipse(C, C, b, b, 200 + i, .6)}" ${i >= 3 ? 'stroke-dasharray="3 6"' : ""}/>`; });
  h += `<path class="kq ring" d="${Sk.ellipse(C, C, 40, 40, 190, .6)}"/>`;
  bands.forEach(([a, b], i) => {
    h += `<text class="${i === cb ? "anno" : "ring-lbl"} grade-caption" x="${C}" y="${C + (a + b) / 2 + 6}" text-anchor="middle">${i === cb ? "你在这一圈" : BAND_NAME[i]}</text>`;
  });
  // 主题之间的分隔线，数学 | 科学 的分界
  THEME_ORDER.forEach((k, i) => { const a0 = THEMES[k].sec[0], p = polar(a0, 44), q = polar(a0, 350); h += `<path class="kq ring" stroke-dasharray="1 7" d="${Sk.line(p[0], p[1], q[0], q[1], 330 + i, .3)}" opacity=".7"/>`; });
  h += `<path class="kq ring" stroke-dasharray="2 6" d="${Sk.line(C, C - 44, C, C - 352, 301, .4)}"/><path class="kq ring" stroke-dasharray="2 6" d="${Sk.line(C, C + 44, C, C + 352, 302, .4)}"/>`;
  h += `<text class="sector-lbl" x="40" y="44">数学</text><text class="sector-lbl" x="720" y="44" text-anchor="end">科学</text>`;
  ["mat", "ene", "life", "earth"].forEach((k) => {
    const t = THEMES[k], th = (t.sec[0] + t.sec[1]) / 2, p = polar(th, 364);
    h += `<text class="ring-lbl subject-caption" x="${f1(p[0])}" y="${f1(p[1] + 5)}" text-anchor="middle" style="fill:var(${t.c})">${t.later}</text>`;
  });
  { const [a, b] = bands[3], p = polar(86, (a + b) / 2); h += `<text class="ring-lbl subject-caption" x="${f1(p[0])}" y="${f1(p[1])}" text-anchor="middle">初中起分科</text>`; }
  h += `<g transform="translate(${C - 22} ${C - 26}) scale(.44)" aria-hidden="true">${SHIP}</g>`;
  /** @type {Record<string, ReturnType<typeof consGeom>>} */
  const G = {};
  for (const c of model.cons) G[c.id] = consGeom(c, bands, model);
  model.links.forEach((l) => { const [a, b] = l.split(">"); h += `<path class="clink kq" data-a="${esc(a)}" data-b="${esc(b)}" stroke-dasharray="2 5" d="" opacity=".8"/>`; });
  model.cons.forEach((c, ci) => {
    const geo = G[c.id], t = THEMES[c.theme];
    const litN = c.points.filter((p) => p.state === "lit").length, openN = c.points.filter((p) => p.open).length;
    const fig = geo.shape ? `<g class="theme-figure">${shapeFigure(c, geo.rr)}</g>` : clusterFigure(c, geo, ci);
    // 一二年级、初中、高中这几圈一般不写名字；有能玩的星的星座例外，免得找不到
    const playable = c.band !== 1 && c.band !== 2 && c.points.some((p) => p.acts);
    const label = !geo.shape && playable
      ? `<text class="cname small" x="0" y="${geo.rr + 15}" text-anchor="middle">${esc(consName(c))}</text>`
      : (geo.shape || c.band === 1 || c.band === 2)
        ? `<text class="cname ${geo.cur ? "" : "small"}" x="0" y="${geo.rr + (geo.cur ? 20 : 15)}" text-anchor="middle">${esc(t.name)}</text>${geo.cur ? `<text class="ccount" x="0" y="${geo.rr + (geo.shape ? 44 : 36)}" text-anchor="middle">${litN}/${c.points.length}</text>` : ""}`
        : "";
    const wash = geo.shape ? `<path d="${Sk.blob(0, 0, geo.rr + 8, geo.rr + 8, ci + 3)}" style="fill:var(${t.c})" opacity=".1"/>` : "";
    h += `<g class="cons" data-id="${esc(c.id)}" data-count="${c.points.length}" tabindex="0" role="button" aria-label="${esc(consName(c))}，${BAND_NAME[c.band]}，${c.points.length} 颗星，开放 ${openN} 颗，点亮 ${litN} 颗" transform="translate(${f1(geo.x)} ${f1(geo.y)})">
      <circle class="hit" r="${geo.hit}"/>${wash}${fig}${label ? `<g class="${geo.shape ? "current-caption" : "other-caption"}">${label}</g>` : ""}</g>`;
  });
  return { svg: h, geometry: G, bands };
}

/**
 * 标签避让（照原型 placeChartLabels）：量出每段字的实际大小，先放五个年级标签，再放星座名字。要在 SVG 已经显示出来以后调用。
 * @param {SVGSVGElement} svg
 * @param {Record<string, {x: number, y: number, rr: number}>} geometry
 */
export function placeChartLabels(svg, geometry) {
  const view = svg.viewBox.baseVal;
  const occupied = [{ x: C - 23, y: C - 27, w: 46, h: 54 }];
  const box = (el, x = 0, y = 0) => { const b = el.getBBox(); return { x: x + b.x, y: y + b.y, w: b.width, h: b.height }; };
  const overlaps = (a, b, pad) => a.x < b.x + b.w + pad && a.x + a.w > b.x - pad && a.y < b.y + b.h + pad && a.y + a.h > b.y - pad;
  for (const group of svg.querySelectorAll(".cons")) {
    const { x, y, rr } = geometry[group.dataset.id], figure = group.querySelector(".theme-figure");
    occupied.push(figure ? box(figure, x, y) : { x: x - rr, y: y - rr, w: rr * 2, h: rr * 2 });
  }
  for (const el of svg.querySelectorAll(".sector-lbl")) occupied.push(box(el));
  const labels = [...svg.querySelectorAll(".grade-caption, .subject-caption"), ...svg.querySelectorAll(".current-caption"), ...svg.querySelectorAll(".other-caption")];
  for (const el of labels) {
    const group = el.closest(".cons"), geo = group ? geometry[group.dataset.id] : null;
    el.removeAttribute("transform");
    const base = box(el, geo?.x, geo?.y);
    const candidates = [];
    if (geo) {
      // 先试这个星座图形的四边；放不下时可以放到自己图形的上面
      const figure = group.querySelector(".theme-figure");
      const rim = figure ? box(figure, geo.x, geo.y) : { x: geo.x - geo.rr, y: geo.y - geo.rr, w: geo.rr * 2, h: geo.rr * 2 };
      const midX = rim.x + rim.w / 2, midY = rim.y + rim.h / 2;
      for (let gap = 8; gap <= 80; gap += 8) for (let slide = -72; slide <= 72; slide += 8) {
        const below = rim.y + rim.h + gap, above = rim.y - gap - base.h, left = rim.x - gap - base.w, right = rim.x + rim.w + gap;
        const append = (x, y, preference) => candidates.push({ dx: x - base.x, dy: y - base.y, distance: Math.abs(slide) + preference + (gap - 8) * 2 });
        append(midX - base.w / 2 + slide, below, 0);
        append(midX - base.w / 2 + slide, above, 8);
        append(left, midY - base.h / 2 + slide, 12);
        append(right, midY - base.h / 2 + slide, 12);
      }
    } else {
      const maxY = el.classList.contains("anno") ? 48 : el.classList.contains("grade-caption") ? 8 : 40;
      for (let dy = -maxY; dy <= maxY; dy += 8) for (let dx = -80; dx <= 80; dx += 8) candidates.push({ dx, dy, distance: Math.hypot(dx * 1.2, dy) });
    }
    candidates.sort((a, b) => a.distance - b.distance);
    let best = null, fewest = Infinity;
    for (const move of candidates) {
      const pos = { ...base, x: base.x + move.dx, y: base.y + move.dy };
      if (pos.x < view.x + 3 || pos.x + pos.w > view.x + view.width - 3 || pos.y < view.y + 3 || pos.y + pos.h > view.y + view.height - 3) continue;
      const hits = occupied.reduce((sum, b) => sum + Number(overlaps(pos, b, 5)), 0);
      if (hits < fewest) { best = { ...move, pos }; fewest = hits; }
      if (hits === 0) break;
    }
    if (best) { el.setAttribute("transform", `translate(${best.dx} ${best.dy})`); occupied.push(best.pos); }
  }
}

/**
 * 星座轻轻浮动、星座之间的连线跟着走（尊重 prefers-reduced-motion）。返回停止的函数。
 * @param {SVGSVGElement} svg @param {Record<string, any>} geometry @param {boolean} reduce
 */
export function animateOverview(svg, geometry, reduce) {
  const cons = [...svg.querySelectorAll(".cons")], clinks = [...svg.querySelectorAll(".clink")];
  const place = (t) => {
    const off = {};
    cons.forEach((el, i) => {
      const geo = geometry[el.dataset.id], k = geo.cur ? 2.2 : 1.2;
      const o = reduce ? [0, 0] : [Math.sin(t / 1900 + i * 1.7) * k, Math.cos(t / 2300 + i * 2.1) * k];
      off[el.dataset.id] = [geo.x + o[0], geo.y + o[1]];
      el.setAttribute("transform", `translate(${f1(off[el.dataset.id][0])} ${f1(off[el.dataset.id][1])})`);
    });
    clinks.forEach((l, i) => {
      const A = off[l.dataset.a], B = off[l.dataset.b], ga = geometry[l.dataset.a], gb = geometry[l.dataset.b];
      if (!A || !B) return;
      const L = Math.hypot(B[0] - A[0], B[1] - A[1]) || 1, ux = (B[0] - A[0]) / L, uy = (B[1] - A[1]) / L;
      l.setAttribute("d", Sk.line(A[0] + ux * (ga.rr + 6), A[1] + uy * (ga.rr + 6), B[0] - ux * (gb.rr + 6), B[1] - uy * (gb.rr + 6), 600 + i, .4));
    });
  };
  place(0);
  if (reduce || typeof requestAnimationFrame !== "function") return () => {};
  let raf = 0, stopped = false;
  const loop = (t) => { if (stopped || !svg.isConnected) return; if (!document.hidden) place(t); raf = requestAnimationFrame(loop); };
  raf = requestAnimationFrame(loop);
  return () => { stopped = true; cancelAnimationFrame(raf); };
}

/**
 * 点在总览上的哪一个星座：在点击半径以内、离中心最近的那个（相邻星座的点击圈有重叠时不会点错）。
 * @param {Record<string, {x: number, y: number, hit: number}>} geometry @param {number} x @param {number} y
 */
export function nearestCons(geometry, x, y) {
  let best = null, bestD = Infinity;
  for (const [id, g] of Object.entries(geometry)) {
    const d = Math.hypot(x - g.x, y - g.y);
    if (d <= g.hit && d < bestD) { best = id; bestD = d; }
  }
  return best;
}

/* ============================================================
   详情视图（照原型 renderConstellation：按单元分行）
   ============================================================ */
/** 单元名：去掉「；」和「（」后面的版本说明。 @param {string} unit */
export const unitName = (unit) => String(unit || "").split(/；|（(?![一二三四五六七八九十0-9]+）)/)[0].trim();

/**
 * 详情视图的排版。measure(text, font) 返回字宽（浏览器里用 canvas 量，测试里可以给一个固定宽度）。
 * @param {{points: any[]}} c @param {number} width @param {(text: string, font: string) => number} measure @param {{hand: string, sans: string}} fonts
 */
export function constellationLayout(c, width, measure, fonts) {
  const units = [];
  for (const p of c.points) {
    const name = unitName(p.unit);
    let unit = units.find((u) => u.name === name);
    if (!unit) { unit = { name, points: [] }; units.push(unit); }
    unit.points.push(p);
  }
  const W = Math.min(860, Math.max(220, width)), colLeft = Math.min(232, Math.max(98, W * .3));
  const columns = Math.min(4, Math.max(1, Math.floor((W - colLeft) / 114))), cell = (W - colLeft) / columns;
  const RH = 100, rows = [], pos = {}, labels = {};
  const lines = (text, w, font) => {
    const out = []; let cur = "";
    for (const ch of text) { if (cur && measure(cur + ch, font) > w) { out.push(cur); cur = ""; } cur += ch; }
    if (cur) out.push(cur);
    return out;
  };
  let H = 14;
  for (const unit of units) {
    for (let start = 0; start < unit.points.length; start += columns) {
      const list = unit.points.slice(start, start + columns);
      const heading = start ? [] : lines(unit.name, colLeft - 22, "16px " + fonts.hand);
      const height = Math.max(RH, heading.length * 22 + 18);
      const y = H + height / 2 - 10;
      rows.push({ heading, y });
      list.forEach((p, i) => {
        pos[p.id] = [colLeft + (i + .5) * cell, y];
        labels[p.id] = lines(p.title.split("：")[0], cell - 12, "14px " + fonts.sans);
      });
      H += height;
    }
  }
  H += 16;
  return { W, H, RH, rows, pos, labels, points: units.flatMap((u) => u.points) };
}

/**
 * 详情视图里一颗星的样子（照原型 renderConstellation）：
 * lit 暖色实心圆加 ✓；landed（探过或有进度）实线圆加进度弧；untouched 淡墨空心圆；closed 更淡的虚线空心圆。
 * @param {any} p buildChart 的点
 */
export function detailState(p) {
  if (!p.open) return "closed";
  if (p.state === "lit") return "lit";
  if (p.state === "explored" || p.progress != null) return "landed";
  return "untouched";
}
/** 详情视图的状态读法。 */
export const DETAIL_WORD = Object.freeze({ lit: "点亮", landed: "探过", untouched: "未探", closed: "未开放" });

/**
 * 一颗星的圆形标记（以原点为中心）。 @param {any} p @param {number} r
 */
export function detailMark(p, r) {
  const st = detailState(p), fill = THEMES[p.theme].g === "math" ? "var(--c-math-2)" : "var(--c-sci-2)";
  if (st === "lit") return `<g class="dmark lit"><path d="${Sk.blob(2, 2, r, r, p.seed)}" style="fill:${fill}"/><path class="k" d="${Sk.ellipse(0, 0, r, r, p.seed + 1)}"/><path class="k1" d="${Sk.line(-4, 0, -1, 4, p.seed + 2) + Sk.line(-1, 4, 5, -4, p.seed + 3)}"/></g>`;
  if (st === "landed") {
    const m = Math.min(.999, Math.max(0, p.progress ?? 0)), R = r + 5;
    const arc = m > 0 ? `<path class="dprog" d="M0 ${-R}A${R} ${R} 0 ${m > .5 ? 1 : 0} 1 ${(R * Math.sin(m * 2 * Math.PI)).toFixed(1)} ${(-R * Math.cos(m * 2 * Math.PI)).toFixed(1)}" fill="none" style="stroke:${fill}" stroke-width="4" stroke-linecap="round"/>` : "";
    return `<g class="dmark landed"><path class="k" d="${Sk.ellipse(0, 0, r, r, p.seed + 1)}"/>${arc}</g>`;
  }
  return `<g class="dmark ${st}"><path class="kq" d="${Sk.ellipse(0, 0, r, r, p.seed + 1)}" ${st === "closed" ? 'stroke-dasharray="3 4"' : ""} style="stroke-width:1.5"/></g>`;
}
/** 有任务的星右上角的小叉（照原型）。 @param {number} r @param {number} seed */
const taskMark = (r, seed) => `<path class="k1 spark" d="${Sk.line(r * .7 + 2, -r * .7 - 2, r * .7 + 8, -r * .7 - 8, seed + 5) + Sk.line(r * .7 + 4, -r * .7 - 9, r * .7 + 9, -r * .7 - 2, seed + 6)}"/>`;

/**
 * 详情视图的 SVG 内容。
 * @param {{theme: string, band: number, points: any[]}} c @param {ReturnType<typeof constellationLayout>} L @param {Set<string>} [busy] 有没做完的挑战的星
 */
export function constellationSvg(c, L, busy = new Set()) {
  const t = THEMES[c.theme], { W, H, RH, pos } = L;
  let h = `<path d="${Sk.blob(W / 2, H / 2, W / 2 - 20, H / 2 - 10, c.band + 7)}" style="fill:var(${t.c})" opacity=".05"/>`;
  for (const { heading, y } of L.rows) {
    if (!heading.length) continue;
    const first = y + 6 - (heading.length - 1) * 11;
    h += `<text class="unit-lbl" x="12" y="${first}">${heading.map((line, i) => `<tspan x="12" dy="${i ? 22 : 0}">${esc(line)}</tspan>`).join("")}</text>`;
  }
  const state = Object.fromEntries(L.points.map((p) => [p.id, p.state]));
  let ei = 0;
  for (const p of L.points) for (const q of p.prereq) {
    if (!pos[q]) continue;
    const [ax, ay] = pos[q], [bx, by] = pos[p.id], lit = state[q] === "lit";
    const cls = lit ? "k1" : "kq", dash = lit ? "" : 'stroke-dasharray="4 5"';
    if (ay === by) { const k = bx < ax ? -1 : 1; h += `<path class="${cls}" ${dash} d="${Sk.line(ax + 20 * k, ay, bx - 22 * k, by, 700 + ei) + Sk.line(bx - 22 * k, by, bx - 29 * k, by - 5, 720 + ei, .3) + Sk.line(bx - 22 * k, by, bx - 29 * k, by + 5, 740 + ei, .3)}"/>`; }
    else { const span = Math.round(Math.abs(by - ay) / RH), bulge = Math.min(62, 22 + span * 12); h += `<path class="${cls}" ${dash} opacity=".7" d="${Sk.curve([[ax + 8, ay + 44], [Math.max(ax, bx) + bulge, (ay + by) / 2], [bx + 10, by - 20]], 760 + ei, .6)}"/>`; }
    ei++;
  }
  for (const p of L.points) {
    const [x, y] = pos[p.id], r = p.acts ? 14 : 12;
    const going = busy.has(p.id);
    const ds = detailState(p);
    const word = DETAIL_WORD[ds] + (ds === "landed" && p.progress ? `，走了 ${Math.round(p.progress * 100)}%` : "") + (p.open ? "" : `，${GRADE_NAME[p.grade] || p.grade}`) + (going ? "，正在挑战" : "");
    h += `<g class="node ${p.open ? "open" : "closed"}" data-id="${esc(p.id)}" data-state="${p.state}" data-mark="${ds}" tabindex="0" role="button" aria-label="${esc(p.title)}，${esc(word)}" transform="translate(${f1(x)} ${f1(y)})"><circle class="hit" r="30"/>
      ${going ? `<path class="sel-ring" d="${Sk.ellipse(0, 0, r + 9, r + 9, p.seed + 9, .8)}"/>` : ""}${detailMark(p, r)}${p.acts ? taskMark(r, p.seed) : ""}
      <text class="lbl${p.open ? "" : " muted-lbl"}" y="${r + 22}" text-anchor="middle">${L.labels[p.id].map((line, i) => `<tspan x="0" dy="${i ? 18 : 0}">${esc(line)}</tspan>`).join("")}</text></g>`;
  }
  return h;
}
