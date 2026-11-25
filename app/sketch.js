// 手绘线稿：从 prototype/index.html 的 sketchLib 拷来（原型冻结，不改它），确定性、带种子。
// 外壳（app.js）和星图（starchart.js）共用这一份。
export function sketchLib() {
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
  function curve(pts, seed, j) { const r = R(seed); j = j == null ? 1 : j; return cr(pts.map((q) => [q[0] + (r() - .5) * 2 * j, q[1] + (r() - .5) * 2 * j]), false); }
  function area(pts) { return "M" + pts.map((q) => f(q[0]) + " " + f(q[1])).join("L") + "Z"; }
  return { line, ellipse, blob, rect, poly, curve, area, R };
}
/** 共用的一份。 */
export const Sk = sketchLib();
