// 实现者补的测试：正式星图的纯函数部分（#230）。
// 期望值是从当前 content/catalog/points.yaml 数出来的字面值（102 个现行点、9 个退役点），目录一改这里要跟着改。
// 跑法：node --test app/test/starchart.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  bandOfGrade, currentBandOf, overviewBands, pointState, buildChart, overviewSvg, chartStar, legendHtml,
  chartShape, constellationLayout, constellationSvg, nearestCons, unitName, consGeom, BASE_BANDS, THEME_ORDER,
} from "../starchart.js";

/** 只读 id、grade、theme、unit、prerequisites 这几行（目录的写法是固定的，见 docs/specs/catalog.md 第 2 节）。 */
function readCatalog() {
  const text = readFileSync(new URL("../../content/catalog/points.yaml", import.meta.url), "utf8");
  const out = { points: [], retired: [] };
  let list = null, cur = null;
  for (const line of text.split("\n")) {
    if (/^points:/.test(line)) { list = out.points; continue; }
    if (/^retired:/.test(line)) { list = out.retired; continue; }
    if (!list) continue;
    const m = line.match(/^\s*(-\s+)?(id|title|grade|theme|unit|prerequisites):\s*(.*)$/);
    if (!m) continue;
    if (m[1]) { cur = { prerequisites: [] }; list.push(cur); }
    let v = m[3].trim();
    if (m[2] === "prerequisites") v = v.replace(/^\[|\]$/g, "").split(",").map((s) => s.trim()).filter(Boolean);
    else v = v.replace(/^["']|["']$/g, "");
    cur[m[2]] = v;
  }
  return out;
}
const catalog = readCatalog();
/** 发布包里的 3 张已发布卡（content/nodes/life/ 下 status: published 的三张）。 */
const nodes = [
  { id: "biology.cell.cell-intro", activities: ["act.simulation.cell-zoom-01", "act.quiz.cell-intro-01"] },
  { id: "biology.genetics.dna-intro", activities: ["act.simulation.dna-book-01", "act.quiz.dna-intro-01"] },
  { id: "biology.genetics.chromosome-intro", activities: ["act.simulation.chromosome-pack-01", "act.quiz.chromosome-intro-01", "act.reflection.chromosome-intro-01"] },
];
const count = (s, re) => (s.match(re) || []).length;

test("目录读得对：102 个现行点、9 个退役点", () => {
  assert.equal(catalog.points.length, 102);
  assert.equal(catalog.retired.length, 9);
});

test("年级 → 学段圈：G1–2、G3–4、G5–6、G7–9、G10–12", () => {
  assert.deepEqual(["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"].map(bandOfGrade), [0, 0, 1, 1, 2, 2, 3, 3, 3, 4, 4, 4]);
  assert.equal(bandOfGrade(8), 3);
});

test("点按学段、主题分组：手数的字面值", () => {
  const m = buildChart({ catalog, nodes, mastery: null, grade: 3 });
  assert.equal(m.points.length, 102);
  const n = (theme, band) => (m.consById.get(theme + "|" + band) || { points: [] }).points.length;
  // 每一圈的点数
  assert.deepEqual([0, 1, 2, 3, 4].map((b) => m.points.filter((p) => p.band === b).length), [10, 46, 23, 17, 6]);
  // 主题 × 学段
  assert.deepEqual([0, 1, 2, 3, 4].map((b) => n("num", b)), [5, 15, 8, 1, 0]);
  assert.deepEqual([0, 1, 2, 3, 4].map((b) => n("geo", b)), [4, 13, 1, 0, 0]);
  assert.deepEqual([0, 1, 2, 3, 4].map((b) => n("ene", b)), [0, 2, 6, 7, 3]);
  assert.deepEqual([0, 1, 2, 3, 4].map((b) => n("life", b)), [0, 3, 0, 4, 1]);
  assert.equal(m.cons.length, 28);
  // 一二年级那一圈只有三个主题有点
  assert.deepEqual(m.cons.filter((c) => c.band === 0).map((c) => c.theme).sort(), ["geo", "num", "stat"]);
  // 退役点不画
  assert.equal(m.byId.has("math.number.fraction-intro"), false);
  assert.equal(m.byId.has("m.g6.ratio"), false);
  for (const r of catalog.retired) assert.equal(m.byId.has(r.id), false, r.id);
});

test("已开放：只有 3 张已发布卡的点", () => {
  const m = buildChart({ catalog, nodes, mastery: null, grade: null });
  assert.deepEqual(m.points.filter((p) => p.open).map((p) => p.id).sort(), ["biology.cell.cell-intro", "biology.genetics.chromosome-intro", "biology.genetics.dna-intro"]);
  assert.equal(m.points.filter((p) => !p.open).length, 99);
  // 「有活动」的小火花只给已开放的星
  assert.deepEqual(m.points.filter((p) => p.acts).map((p) => p.id).sort(), ["biology.cell.cell-intro", "biology.genetics.chromosome-intro", "biology.genetics.dna-intro"]);
  // 没有发布包的卡时都是未开放
  assert.equal(buildChart({ catalog, nodes: [], grade: null }).points.filter((p) => p.open).length, 0);
});

test("四种状态映射", () => {
  assert.equal(pointState(true, "lit"), "lit");
  assert.equal(pointState(true, "explored"), "explored");
  assert.equal(pointState(true, "untouched"), "untouched");
  assert.equal(pointState(true, undefined), "untouched");
  assert.equal(pointState(false, "lit"), "closed");
  assert.equal(pointState(false, undefined), "closed");
  const mastery = { nodes: {
    "biology.genetics.dna-intro": { state: "lit" },
    "biology.cell.cell-intro": { state: "explored" },
    "m.g1.count": { state: "lit" }, // 没开放的点即使有记录也画成未开放
  } };
  const m = buildChart({ catalog, nodes, mastery, grade: 8 });
  const st = (id) => m.byId.get(id).state;
  assert.equal(st("biology.genetics.dna-intro"), "lit");
  assert.equal(st("biology.cell.cell-intro"), "explored");
  assert.equal(st("biology.genetics.chromosome-intro"), "untouched");
  assert.equal(st("m.g1.count"), "closed");
  assert.equal(m.lit, 1);
});

test("星形标记：四种样子各不相同", () => {
  const lit = chartStar("lit", 10), ex = chartStar("explored", 10), un = chartStar("untouched", 10), cl = chartStar("closed", 10);
  assert.match(lit, /star-rays/); assert.match(lit, /shape-face/);
  assert.match(ex, /shape-half/); assert.doesNotMatch(ex, /star-rays/);
  assert.match(un, /shape-face/); assert.doesNotMatch(un, /shape-half|star-rays/);
  assert.doesNotMatch(cl, /shape-face|shape-half|star-rays/); // 未开放：只有轮廓，不填色
  assert.match(cl, /class="shape-mark closed"/);
  const lg = legendHtml();
  for (const w of ["点亮", "探过", "未探", "未开放"]) assert.ok(lg.includes(w), w);
});

test("当前圈：1 年级是第 0 圈，7 年级是第 3 圈，没填资料不换圈", () => {
  assert.equal(currentBandOf(1), 0);
  assert.equal(currentBandOf(7), 3);
  assert.equal(currentBandOf(null), null);
  const widest = (bands) => { const w = bands.map(([a, b]) => b - a); return w.indexOf(Math.max(...w)); };
  assert.deepEqual(overviewBands(null), BASE_BANDS.map((b) => b.slice()));
  assert.equal(widest(overviewBands(null)), 1);
  assert.deepEqual(overviewBands(0), [[40, 172], [172, 216], [216, 264], [264, 310], [310, 350]]);
  assert.deepEqual(overviewBands(3), [[40, 84], [84, 130], [130, 178], [178, 310], [310, 350]]);
  assert.equal(widest(overviewBands(3)), 3);
  for (const g of [1, 3, 7, 12]) assert.equal(overviewBands(currentBandOf(g))[4][1], 350, "最外圈半径不变");
  assert.equal(buildChart({ catalog, nodes, grade: 1 }).currentBand, 0);
  assert.equal(buildChart({ catalog, nodes, grade: 7 }).currentBand, 3);
  const none = buildChart({ catalog, nodes, grade: null });
  assert.equal(none.currentBand, null);
  assert.equal(none.wideBand, 1);
});

test("总览：当前圈画主题轮廓，一个点一颗星", () => {
  const g3 = overviewSvg(buildChart({ catalog, nodes, grade: 3 })).svg;
  assert.equal(count(g3, /class="theme-figure"/g), 8);
  assert.equal(count(g3, /class="shape-point"/g), 46);
  assert.equal(count(g3, /data-point="/g), 102);
  assert.ok(g3.includes("你在这一圈"));
  const g1 = overviewSvg(buildChart({ catalog, nodes, grade: 1 })).svg;
  assert.equal(count(g1, /class="theme-figure"/g), 3);
  assert.equal(count(g1, /class="shape-point"/g), 10);
  const g7 = overviewSvg(buildChart({ catalog, nodes, grade: 7 })).svg;
  assert.equal(count(g7, /class="shape-point"/g), 17);
  // 没填资料：不画轮廓、不突出任何一圈
  const none = overviewSvg(buildChart({ catalog, nodes, grade: null })).svg;
  assert.equal(count(none, /class="theme-figure"/g), 0);
  assert.equal(count(none, /band-now/g), 0);
  assert.ok(!none.includes("你在这一圈"));
  assert.equal(count(none, /data-point="/g), 102);
});

test("主题轮廓：点比锚点多时也一点一个位置", () => {
  const m = buildChart({ catalog, nodes, grade: 3 });
  const num = m.consById.get("num|1"); // 15 个点，阶梯只有 13 个锚点
  const { pts } = chartShape(num);
  assert.equal(pts.length, 15);
  assert.equal(new Set(pts.map((p) => p.join(","))).size, 15);
});

test("点触目标：总览上每个星座的点击半径不小于 34；重叠时取最近的", () => {
  const m = buildChart({ catalog, nodes, grade: 3 });
  const { geometry } = overviewSvg(m);
  for (const g of Object.values(geometry)) assert.ok(g.hit >= 34);
  const life = geometry["life|3"];
  assert.equal(nearestCons(geometry, life.x, life.y), "life|3");
  assert.equal(nearestCons(geometry, 0, 0), null);
  assert.equal(consGeom(m.consById.get("life|1"), overviewBands(1), m).rr, 39);
  assert.deepEqual(THEME_ORDER.length, 8);
});

test("详情视图：按单元分行，染色体和 DNA 同一行", () => {
  const m = buildChart({ catalog, nodes, grade: 8 });
  const life = m.consById.get("life|3");
  assert.equal(unitName("生物 · 绿色植物"), "生物 · 绿色植物");
  assert.equal(unitName("三上 · 万以内加减法（一）"), "三上 · 万以内加减法（一）");
  assert.equal(unitName("一上；人教版（2024）"), "一上");
  const L = constellationLayout(life, 1000, (text) => text.length * 14, { hand: "x", sans: "x" });
  assert.equal(L.points.length, 4);
  assert.equal(L.rows.filter((r) => r.heading.length).length, 3);
  assert.equal(L.pos["biology.genetics.dna-intro"][1], L.pos["biology.genetics.chromosome-intro"][1]);
  const svg = constellationSvg(life, L, new Set(["biology.genetics.chromosome-intro"]));
  assert.equal(count(svg, /class="node open"/g), 3);
  assert.equal(count(svg, /class="node closed"/g), 1);
  assert.ok(svg.includes("正在挑战"));
  assert.equal(count(svg, /tabindex="0"/g), 4);
});
