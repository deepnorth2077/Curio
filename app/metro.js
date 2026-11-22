// Curio · 正式知识地铁（#233 第 3b 步）：从原型 prototype/index.html 的 renderMetro / metroLayout 移植。
// 数据和星图同源：buildChart（starchart.js）给出的现行点、已开放判定和四种状态；站的样子和图例也用星图的 chartStar。
// 这里全是「数据 → SVG 字符串」的纯函数，node 里能测；滚动、点选在 app.js。
import { Sk } from "./sketch.js";
import { THEMES, THEME_ORDER, GRADE_NAME, STATE_WORD, chartStar, spark } from "./starchart.js";

/** 每条线的名字（照原型 THEMES[k].line）。 */
export const LINE_NAME = Object.freeze({ num: "数与运算线", rel: "数量关系线", geo: "图形与测量线", stat: "统计与概率线", mat: "物质线", ene: "能量线", life: "生命线", earth: "地球线" });
const GALAXY = Object.freeze({ math: "数学", science: "科学" });
export const GRADES = Object.freeze(["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"]);
/** 左边固定的线名栏宽度。 */
export const LBLW = 150;
/** 站的星形半径。 */
export const STATION_R = 8;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const f1 = (n) => n.toFixed(1);

/**
 * 每条线上的站，按年级、再按目录里的先后排。
 * @param {{points: any[]}} model buildChart 的结果
 * @returns {Record<string, any[]>}
 */
export function lineStations(model) {
  /** @type {Record<string, any[]>} */
  const out = Object.fromEntries(THEME_ORDER.map((k) => [k, []]));
  for (const g of GRADES) for (const p of model.points) if (p.grade === g && out[p.theme]) out[p.theme].push(p);
  return out;
}

/**
 * 换乘：前置点和后续点不在同一条线上（只看目录里的 prerequisites）。
 * @param {{points: any[], byId: Map<string, any>}} model
 * @returns {{links: {from: string, to: string}[], ids: Set<string>}}
 */
export function interchanges(model) {
  const links = [], ids = new Set();
  for (const p of model.points) for (const q of p.prereq) {
    const a = model.byId.get(q);
    if (!a || a.theme === p.theme) continue;
    links.push({ from: a.id, to: p.id });
    ids.add(a.id); ids.add(p.id);
  }
  return { links, ids };
}

/**
 * 排版（照原型 metroLayout）：横向是年级，一个年级一段；纵向是八条线。当前年级那一段加宽。
 * @param {ReturnType<typeof import("./starchart.js").buildChart>} model
 */
export function metroLayout(model) {
  const cur = model.grade == null ? null : "G" + model.grade;
  const lines = lineStations(model);
  /** @type {Record<string, Record<string, any[]>>} */
  const by = {};
  for (const k of THEME_ORDER) { by[k] = {}; for (const g of GRADES) by[k][g] = lines[k].filter((p) => p.grade === g); }
  /** @type {Record<string, number>} */ const colW = {};
  /** @type {Record<string, number>} */ const zoneX = {};
  let x = LBLW;
  for (const g of GRADES) {
    const mx = Math.max(...THEME_ORDER.map((k) => by[k][g].length));
    colW[g] = Math.max(g === cur ? 140 : 104, mx * 60 + 36);
    zoneX[g] = x; x += colW[g];
  }
  /** @type {Record<string, number>} */ const rowY = {};
  let y = 156;
  THEME_ORDER.forEach((k, i) => {
    // 站名是两行（「：」前后各一行），每条线多留 24
    if (i) y += 80 + (i === 4 ? 34 : 0) + (lines[k].length ? 24 : 0);
    rowY[k] = y;
  });
  const W = x + 60, H = rowY[THEME_ORDER[THEME_ORDER.length - 1]] + 90;
  /** @type {Record<string, [number, number]>} */ const pos = {};
  for (const k of THEME_ORDER) for (const g of GRADES) {
    const list = by[k][g];
    list.forEach((p, i) => { pos[p.id] = [zoneX[g] + 18 + (i + .5) * (colW[g] - 36) / list.length, rowY[k]]; });
  }
  return { cur, lines, colW, zoneX, rowY, W, H, pos };
}

/** 站名：有「：」时拆成两行（照原型）。 */
function stationLabel(title) {
  const split = title.indexOf("：");
  return split < 0 ? esc(title) : `<tspan x="0" y="-14">${esc(title.slice(0, split + 1))}</tspan><tspan x="0" y="0">${esc(title.slice(split + 1))}</tspan>`;
}

/**
 * 线路图的 SVG 内容。返回两段：map 是会跟着滚动的图，labels 是左边固定的线名栏（滚动时由 app.js 平移）。
 * @param {ReturnType<typeof import("./starchart.js").buildChart>} model
 * @param {ReturnType<typeof metroLayout>} L
 * @param {{focusLine?: string|null, selected?: string|null}} [opts]
 */
export function metroSvg(model, L, opts = {}) {
  const { W, H, rowY, pos, zoneX, colW, cur, lines } = L;
  const focus = opts.focusLine || null, selected = opts.selected || null;
  const inter = interchanges(model);
  let h = "";
  // 年级段：当前年级那一段铺淡色，写「你在这里」
  GRADES.forEach((g, i) => {
    const x = zoneX[g], w = colW[g], here = g === cur;
    if (here) h += `<rect class="zone-now" x="${x}" y="70" width="${w}" height="${H - 80}" rx="14"/>`;
    h += `<text class="zone-lbl${here ? " here" : ""}" x="${x + w / 2}" y="44" text-anchor="middle">${here ? "你在这里" : GRADE_NAME[g]}</text>`;
    const big = g === "G7" || g === "G10";
    if (i > 0) h += `<path class="kq${big ? " zone-cut" : ""}" stroke-dasharray="${big ? "6 4" : "1 6"}" d="${Sk.line(x, 58, x, H - 10, 900 + i, .3)}"/>`;
  });
  h += `<text class="zone-sub" x="${zoneX.G1 + 4}" y="62">小学</text><text class="zone-sub" x="${zoneX.G7 + 6}" y="62">初中 · 理科分科</text><text class="zone-sub" x="${zoneX.G10 + 6}" y="62">高中</text>`;
  // 线
  THEME_ORDER.forEach((k, li) => {
    const t = THEMES[k], y = rowY[k], st = lines[k];
    const pts = [[LBLW + 6, y], ...st.map((p) => pos[p.id])], last = pts[pts.length - 1];
    let d = "";
    for (let i = 0; i < pts.length - 1; i++) d += Sk.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], 1000 + li * 50 + i, .35);
    const dim = focus && focus !== k;
    h += `<g class="mline" data-line="${k}" opacity="${dim ? .25 : 1}"><path d="${d}" fill="none" style="stroke:var(${t.c})" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="${Sk.line(last[0], y, W - 20, y, 1400 + li, .3)}" fill="none" style="stroke:var(${t.c})" stroke-width="2.5" stroke-dasharray="2 7" stroke-linecap="round"/>
      ${t.later ? `<text class="hand" x="${zoneX.G7 + 8}" y="${y - 16}" font-size="15" style="fill:var(${t.c})">→ ${t.later}</text>` : ""}</g>`;
  });
  // 换乘：跨线的前置关系
  inter.links.forEach(({ from, to }, j) => {
    const [ax, ay] = pos[from], [bx, by] = pos[to];
    h += `<path class="k1 transfer" data-from="${esc(from)}" data-to="${esc(to)}" d="${Sk.curve([[ax, ay], [ax + (bx - ax) * .5, ay + (by - ay) * .15], [bx - (bx - ax) * .15, by - (by - ay) * .4], [bx, by]], 1600 + j, .5)}" stroke-dasharray="1 5" style="stroke-width:2" opacity=".75"/>`;
  });
  // 站
  for (const k of THEME_ORDER) for (const p of lines[k]) {
    const [x, y] = pos[p.id], dim = focus && focus !== p.theme, isInter = inter.ids.has(p.id), r = STATION_R;
    const word = `${GRADE_NAME[p.grade] || p.grade}，${STATE_WORD[p.state]}${isInter ? "，换乘站" : ""}`;
    h += `<g class="station ${p.open ? "open" : "closed"}" data-id="${esc(p.id)}" data-line="${p.theme}" data-state="${p.state}" tabindex="0" role="button" aria-label="${esc(p.title)}，${esc(word)}" transform="translate(${f1(x)} ${y})" opacity="${dim ? .3 : 1}"><circle class="hit" r="20"/>
      ${p.id === selected ? `<circle class="sel-ring" r="15"/>` : ""}${isInter ? `<rect class="inter-ring" x="-13" y="-11" width="26" height="22" rx="11"/>` : `<circle class="station-gap" r="${r + 2.5}"/>`}${chartStar(p.state, r)}${p.acts ? spark(r * .95 + 3, -r * .95 - 3, 3, p.seed + 5) : ""}
      <text class="slbl${p.open ? "" : " dim"}" transform="translate(6 -16) rotate(-36)">${stationLabel(p.title)}</text></g>`;
  }
  // 左边固定的线名栏
  let lbl = `<rect x="0" y="0" width="${LBLW}" height="${H}" style="fill:var(--pane)"/><path class="kq" d="M${LBLW} 0V${H}"/>`;
  for (const k of THEME_ORDER) {
    const t = THEMES[k], y = rowY[k], on = focus === k;
    lbl += `<g class="lline" data-line="${k}" tabindex="0" role="button" aria-pressed="${on}" aria-label="${LINE_NAME[k]}，${lines[k].length} 站${on ? "，只看这条线" : ""}"><rect class="hit" x="6" y="${y - 22}" width="${LBLW - 12}" height="48" rx="8"/><rect x="14" y="${y - 4}" width="18" height="8" rx="4" style="fill:var(${t.c})"/><text class="line-lbl" x="40" y="${y + 5}">${LINE_NAME[k]}</text><text class="zone-sub" x="40" y="${y + 20}">${GALAXY[t.g]}${t.later ? " → " + t.later : ""}</text></g>`;
  }
  lbl += `<text class="zone-sub" x="14" y="${rowY.num - 34}">数学</text><text class="zone-sub" x="14" y="${rowY.mat - 34}">科学</text>`;
  return { map: h, labels: lbl, interchanges: inter };
}

/**
 * 打开时横向停在哪：默认停在当前年级那一段（没有资料时从头开始）；选中的站在视野外时停到那一站（照原型）。
 * @param {ReturnType<typeof metroLayout>} L @param {number} viewW 滚动框的宽 @param {number} viewH @param {string|null} selected
 */
export function metroScroll(L, viewW, viewH, selected) {
  const home = L.cur ? Math.max(0, L.zoneX[L.cur] - LBLW - 80) : 0;
  const sp = selected ? L.pos[selected] : null;
  const left = sp && (sp[0] < home + LBLW + 20 || sp[0] > home + viewW - 40) ? Math.max(0, sp[0] - LBLW - (viewW - LBLW) / 2) : home;
  const top = sp ? Math.max(0, sp[1] - viewH / 2) : 0;
  return { left, top };
}
