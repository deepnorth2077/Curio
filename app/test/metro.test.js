// 实现者补的测试：正式知识地铁的纯函数部分（#233 第 3b 步）。
// 期望值是对着 content/catalog/points.yaml 手数的字面值（102 个现行点；跨主题的前置 11 条），目录一改这里要跟着改。
// 跑法：node --test app/test/metro.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildChart, chartStar, legendHtml, STATE_WORD } from "../starchart.js";
import { lineStations, interchanges, metroLayout, metroSvg, metroScroll, LINE_NAME, LBLW, STATION_R } from "../metro.js";

/** 读目录里的 id、title、grade、theme 和 prerequisites（含多行写法「- id」）。退役点不读。 */
function readCatalog() {
  const text = readFileSync(new URL("../../content/catalog/points.yaml", import.meta.url), "utf8");
  const points = [];
  let cur = null, inList = false, inPoints = false;
  for (const line of text.split("\n")) {
    if (/^points:/.test(line)) { inPoints = true; continue; }
    if (/^retired:/.test(line)) break;
    if (!inPoints) continue;
    const head = line.match(/^- id:\s*(.+)$/);
    if (head) { cur = { id: head[1].trim(), prerequisites: [] }; points.push(cur); inList = false; continue; }
    const kv = line.match(/^  (title|grade|theme|unit|prerequisites):\s*(.*)$/);
    if (kv) {
      inList = kv[1] === "prerequisites";
      if (inList) cur.prerequisites = kv[2].trim() === "[]" ? [] : kv[2].trim().replace(/^\[|\]$/g, "").split(",").map((x) => x.trim()).filter(Boolean);
      else cur[kv[1]] = kv[2].trim().replace(/^["']|["']$/g, "");
      continue;
    }
    const item = line.match(/^  - (.+)$/);
    if (item && inList) cur.prerequisites.push(item[1].trim());
    else if (!/^\s/.test(line)) inList = false;
  }
  return { points };
}
const catalog = readCatalog();
const nodes = [
  { id: "biology.cell.cell-intro", activities: ["act.simulation.cell-zoom-01", "act.quiz.cell-intro-01"] },
  { id: "biology.genetics.dna-intro", activities: ["act.simulation.dna-book-01", "act.quiz.dna-intro-01"] },
  { id: "biology.genetics.chromosome-intro", activities: ["act.simulation.chromosome-pack-01", "act.quiz.chromosome-intro-01", "act.reflection.chromosome-intro-01"] },
];
const count = (s, re) => (s.match(re) || []).length;

test("目录读得对：102 个现行点，前置一共 94 条", () => {
  assert.equal(catalog.points.length, 102);
  assert.equal(catalog.points.reduce((n, p) => n + p.prerequisites.length, 0), 94);
});

test("每条线的站数等于目录里这个主题的点数（手数）", () => {
  const m = buildChart({ catalog, nodes, mastery: null, grade: 3 });
  const lines = lineStations(m);
  const n = Object.fromEntries(Object.entries(lines).map(([k, v]) => [k, v.length]));
  assert.deepEqual(n, { num: 29, rel: 9, geo: 18, stat: 7, mat: 9, ene: 18, life: 8, earth: 4 });
  // 画出来的站也是这么多
  const { map } = metroSvg(m, metroLayout(m));
  for (const [k, want] of Object.entries(n)) assert.equal(count(map, new RegExp(`class="station [a-z]+" data-id="[^"]+" data-line="${k}"`, "g")), want, k);
  assert.equal(count(map, /class="station /g), 102);
  // 每条线一段粗线、一个线名
  assert.equal(count(map, /class="mline"/g), 8);
});

test("一条线上的站按年级从左到右", () => {
  const m = buildChart({ catalog, nodes, mastery: null, grade: null });
  const L = metroLayout(m);
  for (const list of Object.values(L.lines)) {
    for (let i = 1; i < list.length; i++) {
      const a = list[i - 1], b = list[i];
      assert.ok(Number(a.grade.slice(1)) <= Number(b.grade.slice(1)), `${a.id} → ${b.id}`);
      assert.ok(L.pos[a.id][0] < L.pos[b.id][0], `${a.id} 在 ${b.id} 左边`);
      assert.equal(L.pos[a.id][1], L.pos[b.id][1]);
    }
  }
  // 生命线：三四年级 3 站
  assert.equal(L.lines.life.filter((p) => p.grade === "G3" || p.grade === "G4").length, 3);
});

test("换乘站来自 prerequisites：跨主题的前置 11 条、15 个站（手数）", () => {
  const m = buildChart({ catalog, nodes, mastery: null, grade: null });
  const { links, ids } = interchanges(m);
  assert.equal(links.length, 11);
  assert.deepEqual([...ids].sort(), [
    "c.g9.equation", "m.g2.times", "m.g3.mul2", "m.g3.times-concept", "m.g4.laws", "m.g7.rational",
    "math.fraction.as-division", "math.fraction.equivalent", "math.fraction.the-whole", "math.number.same-point",
    "math.operation.multiply-shrinks", "math.percent.change", "math.percent.meaning", "math.ratio.meaning", "math.ratio.sharing",
  ]);
  assert.ok(links.some((l) => l.from === "m.g2.times" && l.to === "m.g3.times-concept"));
  assert.ok(links.some((l) => l.from === "math.ratio.meaning" && l.to === "c.g9.equation"));
  // 同一主题里的前置不是换乘
  assert.ok(!links.some((l) => l.from === "m.g1.count"));
  const { map } = metroSvg(m, metroLayout(m));
  assert.equal(count(map, /class="k1 transfer"/g), 11);
  assert.equal(count(map, /class="inter-ring"/g), 15);
});

test("反例：没有跨主题前置时没有换乘", () => {
  const cat = { points: [
    { id: "a", title: "甲", grade: "G1", theme: "num", prerequisites: [] },
    { id: "b", title: "乙", grade: "G2", theme: "num", prerequisites: ["a"] },
    { id: "c", title: "丙", grade: "G3", theme: "life", prerequisites: ["zzz"] },
  ] };
  const m = buildChart({ catalog: cat, nodes: [], grade: null });
  assert.equal(interchanges(m).links.length, 0);
  assert.equal(count(metroSvg(m, metroLayout(m)).map, /inter-ring/g), 0);
  // 加一条跨主题的前置，就有一个换乘、两个换乘站
  cat.points[2].prerequisites = ["b"];
  const m2 = buildChart({ catalog: cat, nodes: [], grade: null });
  assert.deepEqual(interchanges(m2).links, [{ from: "b", to: "c" }]);
  assert.equal(count(metroSvg(m2, metroLayout(m2)).map, /inter-ring/g), 2);
});

test("站的样子和星图同一套：状态来自 buildChart，画的是同一个 chartStar", () => {
  const mastery = { nodes: { "biology.genetics.dna-intro": { state: "lit" }, "biology.cell.cell-intro": { state: "explored" }, "m.g3.mul2": { state: "lit" } } };
  const m = buildChart({ catalog, nodes, mastery, grade: 3 });
  const { map } = metroSvg(m, metroLayout(m));
  const stateOf = (id) => map.match(new RegExp(`data-id="${id.replace(/\./g, "\\.")}" data-line="[a-z]+" data-state="([a-z]+)"`))[1];
  assert.equal(stateOf("biology.genetics.dna-intro"), "lit");
  assert.equal(stateOf("biology.cell.cell-intro"), "explored");
  assert.equal(stateOf("biology.genetics.chromosome-intro"), "untouched");
  // 没开放的点即使有掌握度记录也是「未开放」（和星图的 pointState 一致）
  assert.equal(stateOf("m.g3.mul2"), "closed");
  for (const p of m.points) assert.equal(stateOf(p.id), p.state, p.id);
  // 每种样子用的就是 chartStar 的那段 SVG
  for (const st of ["lit", "explored", "untouched", "closed"]) assert.ok(map.includes(chartStar(st, STATION_R)), st);
  assert.equal(count(map, /data-state="closed"/g), 99);
  assert.equal(count(map, /class="station open"/g), 3);
  // 读屏念的字和星图图例的字一样
  assert.ok(map.includes(`，${STATE_WORD.lit}`) && map.includes(`，${STATE_WORD.closed}`));
  assert.ok(legendHtml().includes("未开放"));
  // 有活动的站带小火花
  assert.equal(count(map, /class="k1 spark"/g), 3);
});

test("舰长资料：三年级那一段标「你在这里」并加宽；没填资料时不标", () => {
  const m3 = buildChart({ catalog, nodes, mastery: null, grade: 3 });
  const L3 = metroLayout(m3);
  assert.equal(L3.cur, "G3");
  const s3 = metroSvg(m3, L3).map;
  assert.equal(count(s3, /你在这里/g), 1);
  assert.equal(count(s3, /class="zone-now"/g), 1);
  assert.ok(s3.includes(`class="zone-now" x="${L3.zoneX.G3}"`));
  assert.ok(L3.colW.G3 >= 140);
  // 默认横向停在三年级那一段
  assert.equal(metroScroll(L3, 600, 400, null).left, Math.max(0, L3.zoneX.G3 - LBLW - 80));

  const m8 = buildChart({ catalog, nodes, mastery: null, grade: 8 });
  const L8 = metroLayout(m8);
  assert.ok(metroSvg(m8, L8).map.includes(`class="zone-now" x="${L8.zoneX.G8}"`));

  const m0 = buildChart({ catalog, nodes, mastery: null, grade: null });
  const L0 = metroLayout(m0), s0 = metroSvg(m0, L0).map;
  assert.equal(L0.cur, null);
  assert.equal(count(s0, /你在这里/g), 0);
  assert.equal(count(s0, /zone-now/g), 0);
  assert.equal(metroScroll(L0, 600, 400, null).left, 0);
  // 没资料时三年级是普通宽度
  assert.ok(L0.colW.G3 <= L3.colW.G3);
});

test("只看一条线：其他线和站变淡；线名栏八条线都能按", () => {
  const m = buildChart({ catalog, nodes, mastery: null, grade: 3 });
  const L = metroLayout(m);
  const { map, labels } = metroSvg(m, L, { focusLine: "life" });
  assert.equal(count(map, /class="mline" data-line="[a-z]+" opacity="0.25"/g), 7);
  assert.equal(count(map, /class="mline" data-line="life" opacity="1"/g), 1);
  assert.equal(count(map, /data-line="life" data-state="[a-z]+" tabindex="0" role="button" aria-label="[^"]+" transform="[^"]+" opacity="1"/g), 8);
  assert.equal(count(labels, /class="lline"/g), 8);
  assert.equal(count(labels, /aria-pressed="true"/g), 1);
  for (const name of Object.values(LINE_NAME)) assert.ok(labels.includes(name), name);
});

test("选中的站：画选中圈；在视野外时滚到那一站", () => {
  const m = buildChart({ catalog, nodes, mastery: null, grade: 3 });
  const L = metroLayout(m);
  const id = "biology.genetics.chromosome-intro";
  assert.equal(count(metroSvg(m, L, { selected: id }).map, /class="sel-ring"/g), 1);
  assert.equal(count(metroSvg(m, L).map, /class="sel-ring"/g), 0);
  // 高二的点离三年级很远：滚过去
  const far = L.lines.life.find((p) => p.grade === "G11");
  const s = metroScroll(L, 600, 400, far.id);
  assert.ok(s.left > metroScroll(L, 600, 400, null).left);
  assert.ok(L.pos[far.id][0] > s.left + LBLW && L.pos[far.id][0] < s.left + 600);
});
