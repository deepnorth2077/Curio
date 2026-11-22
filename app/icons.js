// 手绘小插图（100×100）：从 prototype/index.html 的 ICONS、icon() 照搬（原型冻结，不改它）。
// 星球笔记的信号卡、任务、图鉴提示用。取法照原型：卡有专属插图的用专属的，其余用主题的默认插图。
import { Sk } from "./sketch.js";

const P = (d, c) => `<path class="${c || "k"}" d="${d}"/>`;
const wedge = (cx, cy, r, a0, a1) => { const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0), x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1); return `M${cx} ${cy}L${x0.toFixed(1)} ${y0.toFixed(1)}A${r} ${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}Z`; };

/** @type {Record<string, (s: number) => string>} */
export const ICONS = {
  cake: (s) => P(Sk.blob(54, 56, 34, 34, s), "f") + `<path class="f2" d="${wedge(52, 52, 33, -Math.PI / 2, Math.PI / 6)}"/>` + P(Sk.ellipse(52, 52, 34, 34, s + 1)) + P(Sk.line(52, 52, 52, 18, s + 2) + Sk.line(52, 52, 81, 69, s + 3) + Sk.line(52, 52, 23, 69, s + 4)) + P(Sk.curve([[66, 24], [72, 14], [76, 12]], s + 5), "k1"),
  clock: (s) => P(Sk.blob(53, 57, 32, 32, s), "f") + P(Sk.ellipse(50, 54, 32, 32, s + 1)) + P(Sk.line(50, 54, 50, 33, s + 2) + Sk.line(50, 54, 64, 61, s + 3)) + P(Sk.line(50, 24, 50, 29, s + 4) + Sk.line(80, 54, 75, 54, s + 5) + Sk.line(50, 84, 50, 79, s + 6) + Sk.line(20, 54, 25, 54, s + 7), "k1") + P(Sk.ellipse(30, 22, 8, 6, s + 8) + Sk.ellipse(70, 22, 8, 6, s + 9), "k1"),
  perimeter: (s) => `<path class="f" d="${Sk.area([[22, 34], [80, 32], [82, 72], [24, 74]])}"/>` + P(Sk.rect(20, 30, 58, 40, s)) + [0, 1, 2, 3, 4, 5].map((i) => `<circle class="f2" cx="${24 + i * 10}" cy="22" r="2.4"/>`).join("") + P(Sk.curve([[82, 22], [88, 30], [88, 40]], s + 3), "k1") + P(Sk.line(84, 38, 88, 42, s + 4) + Sk.line(92, 37, 88, 42, s + 5), "k1"),
  candy: (s) => [20, 50, 80].map((x, i) => P(Sk.blob(x + 2, 74, 15, 5, s + i), "f") + P(Sk.ellipse(x, 72, 15, 5, s + i + 10), "k1")).join("") + [[16, 58], [24, 58], [20, 50], [46, 58], [54, 58], [50, 50], [76, 58], [84, 58], [80, 50]].map((q, i) => `<circle class="f2" cx="${q[0]}" cy="${q[1]}" r="4"/>` + P(Sk.ellipse(q[0], q[1], 4, 4, s + 20 + i), "k1")).join("") + P(Sk.curve([[38, 24], [50, 16], [62, 24]], s + 40), "k1") + P(Sk.line(58, 20, 62, 24, s + 41) + Sk.line(62, 24, 57, 26, s + 42), "k1"),
  bars: (s) => `<path class="f2" d="${Sk.area([[16, 26], [40, 26], [40, 42], [16, 42]])}"/><path class="f2" d="${Sk.area([[16, 58], [56, 58], [56, 74], [16, 74]])}"/>` + P(Sk.rect(16, 26, 64, 16, s) + Sk.rect(16, 58, 64, 16, s + 5)) + [1, 2, 3, 4, 5, 6, 7].map((i) => P(Sk.line(16 + i * 8, 26, 16 + i * 8, 42, s + 10 + i) + Sk.line(16 + i * 8, 58, 16 + i * 8, 74, s + 20 + i), "k1")).join(""),
  cup: (s) => `<path class="f" d="${Sk.area([[8, 56], [92, 54], [92, 90], [8, 90]])}"/>` + P(Sk.curve([[8, 56], [22, 52], [36, 57], [50, 53], [64, 57], [78, 53], [92, 56]], s), "k1") + `<path class="fp" d="${Sk.area([[34, 24], [66, 24], [62, 70], [38, 70]])}"/>` + P(Sk.poly([[38, 70], [34, 24], [66, 24], [62, 70]], s + 2, false)) + P(Sk.curve([[40, 64], [50, 61], [60, 64]], s + 4), "k1") + `<circle class="f2" cx="50" cy="40" r="5"/>`,
  ice: (s) => `<path class="f" d="${Sk.area([[12, 52], [40, 50], [42, 78], [14, 80]])}"/>` + P(Sk.rect(12, 50, 28, 28, s)) + P(Sk.line(18, 56, 26, 56, s + 1), "k1") + `<path class="f2" d="${Sk.area([[52, 80], [60, 62], [68, 80]])}"/>` + P(Sk.curve([[60, 58], [52, 74], [56, 82], [64, 82], [68, 74], [60, 58]], s + 2)) + P(Sk.curve([[80, 80], [76, 70], [84, 62], [80, 52]], s + 3) + Sk.curve([[90, 78], [86, 68], [94, 60], [90, 50]], s + 4), "k1"),
  torch: (s) => `<path class="f" d="${Sk.area([[44, 40], [94, 22], [94, 78], [44, 60]])}"/>` + P(Sk.rect(8, 42, 24, 16, s)) + P(Sk.poly([[32, 40], [44, 36], [44, 64], [32, 60]], s + 1, true)) + P(Sk.line(46, 40, 94, 24, s + 2) + Sk.line(46, 60, 94, 76, s + 3), "k1") + `<circle class="f2" cx="20" cy="50" r="3"/>`,
  pinhole: (s) => `<path class="f" d="${Sk.area([[50, 48], [84, 30], [84, 70]])}"/><path class="f" d="${Sk.area([[16, 30], [50, 48], [50, 52], [16, 70]])}"/>` + P(Sk.line(16, 40, 16, 72, s) + Sk.line(50, 20, 50, 46, s + 1) + Sk.line(50, 54, 50, 80, s + 2) + Sk.line(84, 20, 84, 80, s + 3)) + P(Sk.line(16, 34, 84, 66, s + 4) + Sk.line(16, 72, 84, 32, s + 5), "k1") + `<path class="f2" d="M16 26c4 4 4 8 0 10c-4-2-4-6 0-10z"/>` + P(Sk.line(84, 40, 84, 62, s + 6) + Sk.line(80, 58, 84, 64, s + 7) + Sk.line(88, 58, 84, 64, s + 8), "k"),
  // 主题的默认插图
  blocks: (s) => `<path class="f" d="${Sk.area([[18, 54], [44, 54], [44, 80], [18, 80]])}"/><path class="f2" d="${Sk.area([[46, 54], [72, 54], [72, 80], [46, 80]])}"/><path class="f" d="${Sk.area([[32, 26], [58, 26], [58, 52], [32, 52]])}"/>` + P(Sk.rect(16, 52, 28, 28, s) + Sk.rect(44, 52, 28, 28, s + 4) + Sk.rect(30, 24, 28, 28, s + 8)) + P(Sk.curve([[78, 30], [86, 22], [90, 30]], s + 12), "k1"),
  scale: (s) => P(Sk.blob(22, 60, 12, 5, s), "f") + P(Sk.blob(78, 54, 12, 5, s + 1), "f") + P(Sk.line(50, 22, 50, 84, s + 2) + Sk.line(34, 84, 66, 84, s + 3) + Sk.line(18, 36, 82, 28, s + 4)) + P(Sk.line(18, 36, 10, 58, s + 5) + Sk.line(18, 36, 28, 58, s + 6) + Sk.line(82, 28, 72, 52, s + 7) + Sk.line(82, 28, 90, 52, s + 8) + Sk.curve([[8, 58], [18, 66], [30, 58]], s + 9) + Sk.curve([[70, 52], [80, 60], [92, 52]], s + 10), "k1") + `<circle class="fa" cx="50" cy="20" r="3"/>`,
  ruler: (s) => `<path class="f" d="${Sk.area([[12, 64], [72, 24], [86, 44], [26, 84]])}"/>` + P(Sk.poly([[12, 64], [72, 24], [86, 44], [26, 84]], s, true)) + [0, 1, 2, 3, 4, 5, 6].map((i) => { const t = i / 7, x = 16 + t * 56, y = 62 - t * 37, L = i % 2 ? 7 : 12; return P(Sk.line(x, y, x + L * .55, y + L * .83, s + 10 + i), "k1"); }).join(""),
  sprout: (s) => `<path class="f" d="${Sk.area([[8, 74], [92, 72], [92, 92], [8, 92]])}"/>` + P(Sk.curve([[8, 74], [30, 70], [60, 74], [92, 71]], s), "k1") + P(Sk.curve([[50, 74], [48, 58], [50, 42], [54, 30]], s + 1)) + P(Sk.blob(36, 46, 14, 7, s + 2), "f2") + P(Sk.ellipse(36, 46, 14, 7, s + 3), "k1") + P(Sk.blob(66, 36, 14, 7, s + 4), "f2") + P(Sk.ellipse(66, 36, 14, 7, s + 5), "k1"),
  sun: (s) => P(Sk.blob(52, 52, 18, 18, s), "f2") + P(Sk.ellipse(50, 50, 18, 18, s + 1)) + [0, 1, 2, 3, 4, 5, 6, 7].map((i) => { const a = i / 8 * Math.PI * 2; return P(Sk.line(50 + Math.cos(a) * 26, 50 + Math.sin(a) * 26, 50 + Math.cos(a) * 38, 50 + Math.sin(a) * 38, s + 3 + i), "k1"); }).join(""),
};

/** 每个主题的默认插图（照原型 THEMES[k].icon）。 */
export const THEME_ICON = Object.freeze({ num: "blocks", rel: "scale", geo: "ruler", stat: "bars", mat: "ice", ene: "torch", life: "sprout", earth: "sun" });
/** 原型里有专属插图的点（照原型 DETAIL[id].icon；只取插图名，其余内容来自发布包）。 */
export const POINT_ICON = Object.freeze({
  "math.number.division-meaning": "candy",
  "math.measure.time-units": "clock",
  "math.geometry.perimeter": "perimeter",
  "science.matter.air-space": "cup",
  "science.matter.water-states": "ice",
  "science.light.straight-line": "torch",
  "science.light.pinhole": "pinhole",
});
/** 一颗星用哪张插图（照原型 n.icon = DETAIL 的 icon || 主题的 icon）。 @param {{id: string, theme: string}} p */
export const iconOf = (p) => POINT_ICON[p.id] || THEME_ICON[p.theme] || "blocks";

/**
 * 一张插图（照原型 icon()）：数学用暖色、科学用绿色。
 * @param {string} name @param {"math"|"science"|string} galaxy @param {number} size @param {number} [seed] @param {string} [cls]
 */
export function icon(name, galaxy, size, seed, cls) {
  const fill = galaxy === "math" ? "var(--c-math)" : galaxy === "science" ? "var(--c-sci)" : "var(--c-sky)";
  const fill2 = galaxy === "math" ? "var(--c-math-2)" : "var(--c-sci-2)";
  const draw = ICONS[name] || ICONS.blocks;
  return `<svg viewBox="0 0 100 100" width="${size}" height="${size}" class="${cls || ""}" style="--icon-fill:${fill};--icon-fill-2:${fill2}" aria-hidden="true">${draw(seed || 3)}</svg>`;
}
