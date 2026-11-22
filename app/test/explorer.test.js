// 实现者补的测试：知识索引和星球笔记的纯函数（#233，Luka 2026-11-22）。
// 期望值是对着 content/catalog/points.yaml 手数的字面值（102 个现行点，数学 63、科学 39，28 个星座；退役 9 条），目录一改这里要跟着改。
// 跑法：node --test app/test/explorer.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildChart } from "../starchart.js";
import { aliasIndex, explorerTree, searchPoints, treeHtml, noteHtml, GALAXY } from "../explorer.js";

/** 读目录：points 和 retired 两段（只读这里用到的字段，含多行写法的前置）。 */
function readCatalog() {
  const text = readFileSync(new URL("../../content/catalog/points.yaml", import.meta.url), "utf8");
  const out = { points: [], retired: [] };
  let list = null, cur = null, inPre = false;
  for (const line of text.split("\n")) {
    if (/^points:/.test(line)) { list = out.points; continue; }
    if (/^retired:/.test(line)) { list = out.retired; continue; }
    if (!list) continue;
    const head = line.match(/^- id:\s*(.+)$/);
    if (head) { cur = { id: head[1].trim(), prerequisites: [] }; list.push(cur); inPre = false; continue; }
    const kv = line.match(/^  (title|grade|theme|unit|replaced_by|prerequisites):\s*(.*)$/);
    if (kv) {
      inPre = kv[1] === "prerequisites";
      if (inPre) cur.prerequisites = kv[2].trim() === "[]" ? [] : [];
      else cur[kv[1]] = kv[2].trim().replace(/^["']|["']$/g, "");
      continue;
    }
    const item = line.match(/^  - (.+)$/);
    if (item && inPre) cur.prerequisites.push(item[1].trim());
  }
  return out;
}
const catalog = readCatalog();
/** 已开放的星：一颗点亮、一颗探过，其余没开放。 */
const nodes = [{ id: "math.decimal.tenths", activities: ["act.x"] }, { id: "math.fraction.unit-fraction", activities: ["act.y"] }];
const mastery = { nodes: { "math.decimal.tenths": { state: "lit" }, "math.fraction.unit-fraction": { state: "explored" } } };
const model = buildChart({ catalog, nodes, mastery, grade: 3 });
const aliases = aliasIndex(catalog, model.byId);

test("目录读对了：102 个现行点、9 条退役", () => {
  assert.equal(catalog.points.length, 102);
  assert.equal(catalog.retired.length, 9);
});

test("分节：数学 63 颗、科学 39 颗，点亮数从掌握度来", () => {
  const [math, sci] = explorerTree(model);
  assert.deepEqual([math.name, math.total, math.lit], ["数学", 63, 1]);
  assert.deepEqual([sci.name, sci.total, sci.lit], ["科学", 39, 0]);
  assert.equal(math.cons.length + sci.cons.length, 28);
});

test("分组：每个星座的点数等于目录里的数（手数）", () => {
  // 主题|学段圈（0 一二年级、1 三四年级、2 五六年级、3 初中、4 高中）→ 点数
  const want = {
    "num|0": 5, "geo|0": 4, "stat|0": 1,
    "num|1": 15, "rel|1": 3, "geo|1": 13, "stat|1": 3,
    "num|2": 8, "rel|2": 3, "geo|2": 1, "stat|2": 3,
    "num|3": 1, "rel|3": 2, "rel|4": 1,
    "mat|1": 5, "ene|1": 2, "life|1": 3, "earth|1": 2,
    "mat|2": 1, "ene|2": 6, "earth|2": 1,
    "mat|3": 2, "ene|3": 7, "life|3": 4, "earth|3": 1,
    "mat|4": 1, "ene|4": 3, "life|4": 1,
  };
  const got = {};
  for (const s of explorerTree(model)) for (const c of s.cons) got[c.id] = c.total;
  assert.deepEqual(got, want);
});

test("分组的顺序：先按学段，同一学段按主题顺序", () => {
  const [math] = explorerTree(model);
  assert.deepEqual(math.cons.slice(0, 5).map((c) => c.id), ["num|0", "geo|0", "stat|0", "num|1", "rel|1"]);
  assert.equal(math.cons.find((c) => c.id === "num|1").lit, 1);
});

test("旧名表：退役点指向接替它的新星", () => {
  assert.deepEqual(aliases.get("math.decimal.tenths"), ["小数的初步认识", "小数的意义"]);
  assert.deepEqual(aliases.get("math.fraction.the-whole"), ["分数的简单应用", "分数的意义"]);
  assert.equal(aliases.has("m.g3.decimal"), false);
  // 接替的星不在现行目录里：不收
  assert.equal(aliasIndex(catalog, { has: () => false }).size, 0);
  // 接替链：a → b（也退役）→ 现行的 c
  const chain = aliasIndex({ retired: [{ id: "a", title: "甲", replaced_by: "b" }, { id: "b", title: "乙", replaced_by: "c" }] }, new Set(["c"]));
  assert.deepEqual(chain.get("c"), ["甲", "乙"]);
});

test("搜索：名称命中", () => {
  const hits = searchPoints(model, aliases, "小数是什么");
  assert.deepEqual(hits.map((h) => [h.point.id, h.alias]), [["math.decimal.tenths", null]]);
  // 不管空格：「20以内」也找得到「20 以内加减法」
  assert.ok(searchPoints(model, aliases, "20以内").some((h) => h.point.id === "m.g1.add20"));
});

test("搜索：旧名命中，指向接替的新星，并带上原名", () => {
  const hits = searchPoints(model, aliases, "小数的初步认识");
  const tenths = hits.find((h) => h.point.id === "math.decimal.tenths");
  assert.ok(tenths);
  assert.equal(tenths.point.title, "小数是什么");
  assert.equal(tenths.alias, "小数的初步认识");
  const old = searchPoints(model, aliases, "分数的初步认识").find((h) => h.point.id === "math.fraction.unit-fraction");
  assert.equal(old.alias, "分数的初步认识");
});

test("搜索：没命中返回空，空白查询也返回空", () => {
  assert.deepEqual(searchPoints(model, aliases, "恐龙蛋"), []);
  assert.deepEqual(searchPoints(model, aliases, "   "), []);
});

test("搜索：主题名、学段名也能找", () => {
  assert.equal(searchPoints(model, aliases, "统计与概率").length, 7);
  assert.equal(searchPoints(model, aliases, "高中").length, 6);
});

test("索引 HTML：当前学段的星座默认展开，叶子带四种样子和年级", () => {
  const html = treeHtml(model, { query: "", isOpen: (c) => c.band === model.currentBand, selected: "math.decimal.tenths", aliases });
  assert.match(html, /数学星系 · <span class="mono">1\/63<\/span>/);
  assert.match(html, /科学星系 · <span class="mono">0\/39<\/span>/);
  assert.match(html, /data-cons="num\|1" aria-expanded="true"/);
  assert.match(html, /data-cons="num\|0" aria-expanded="false"/);
  // 三四年级 8 个星座全展开：叶子数 = 15+3+13+3+5+2+3+2
  assert.equal((html.match(/class="leaf"/g) || []).length, 46);
  assert.match(html, /data-node="math\.decimal\.tenths" data-state="lit" aria-current="true"/);
  assert.match(html, /data-node="math\.fraction\.unit-fraction" data-state="explored" aria-current="false"/);
  assert.match(html, /shape-mark closed/);
  assert.match(html, /舰长 · 三年级/);
  assert.doesNotMatch(html, /学习/);
});

test("索引 HTML：搜索结果写「找到 N 颗星球」，旧名旁写原名", () => {
  const html = treeHtml(model, { query: "小数的初步认识", isOpen: () => false, selected: null, aliases });
  const n = searchPoints(model, aliases, "小数的初步认识").length;
  assert.match(html, new RegExp(`找到 ${n} 颗星球`));
  assert.match(html, /<small class="alias">原名：小数的初步认识<\/small>/);
  assert.match(treeHtml(model, { query: "恐龙蛋", isOpen: () => false, selected: null, aliases }), /找到 0 颗星球/);
});

test("笔记：已开放的星有任务入口；未开放的只写「还没开放」", () => {
  const p = model.byId.get("math.decimal.tenths");
  const open = noteHtml(p, { card: { driving_question: "一块饼切成十份？" }, model, tasks: [{ id: "act.x", title: "百格板", meta: "动手探索 · 3 站", go: "开始" }], canStart: true });
  assert.match(open, /<h1 id="noteTitle" tabindex="-1">小数是什么<\/h1>/);
  assert.match(open, /一块饼切成十份？/);
  assert.match(open, /data-start="act\.x">开始<\/button>/);
  assert.match(open, /点亮/);
  const off = noteHtml(p, { card: null, model, tasks: [{ id: "act.x", title: "百格板", meta: "", go: "开始" }], canStart: false, why: "这里只能看，不能开始挑战。" });
  assert.match(off, /data-start="act\.x" disabled/);
  assert.match(off, /这里只能看/);
  const closed = noteHtml(model.byId.get("m.g1.count"), { model, tasks: [], canStart: true });
  assert.match(closed, /还没开放/);
  assert.match(closed, /未开放/);
  assert.doesNotMatch(closed, /data-start/);
  assert.equal(GALAXY.math, "数学");
});
