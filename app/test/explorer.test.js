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

/* ---- #233 恢复原型画面：反向链接、图鉴编号、进度弧、笔记里的插图和各节 ---- */
import { nextPoints, specimenNo, nodeProgress, detailState, detailMark } from "../starchart.js";
import { AGE_BAND } from "../explorer.js";
import { iconOf, icon } from "../icons.js";

test("反向链接：目录里以「谁的几分之几」为前置的四颗星，按目录先后", () => {
  assert.deepEqual(nextPoints(model, "math.fraction.the-whole").map((x) => x.title), ["分数和除法", "分数乘分数", "按比分配", "百分数：都换成 100 份"]);
  assert.deepEqual(nextPoints(model, "m.g3.mul1-oral").map((x) => x.id), ["m.g3.mul1-written"]);
  assert.deepEqual(nextPoints(model, "恐龙蛋"), []);
});

test("图鉴编号：目录里的第几个，补齐三位", () => {
  assert.equal(model.byId.get("m.g1.count").no, 1);
  assert.equal(model.byId.get("math.decimal.tenths").no, 76);
  assert.equal(model.byId.get("math.fraction.the-whole").no, 84);
  assert.equal(specimenNo(84), "No.084");
  assert.equal(specimenNo(1), "No.001");
  assert.equal(specimenNo(102), "No.102");
});

test("进度：探索按做完的站数，挑战按最好的首答，来过但没做完是 0", () => {
  const ev = (attempt, seq, verb, payload = {}, extra = {}) => ({
    attempt_id: attempt, device_seq: seq, device_id: "d", learner_id: "L", actor: { type: "learner", id: "L" }, event_id: attempt + seq, verb, payload,
    content: { node_id: extra.node || "math.fraction.the-whole", activity_id: extra.act || "act.simulation.whose-half-01", activity_kind: extra.kind || "simulation", activity_version: 1 },
  });
  const events = [
    ev("a1", 1, "attempt.started"),
    ev("a1", 2, "sim.observed", { observable: "station.completed", value: 1 }),
    ev("a1", 3, "sim.observed", { observable: "station.completed", value: 1 }),
    ev("a2", 1, "attempt.started", {}, { node: "math.decimal.tenths", act: "act.simulation.hundred-grid-01" }),
  ];
  const stations = (id) => (id.startsWith("act.simulation.") ? 3 : 0);
  const pr = nodeProgress(events, { nodes: { "m.g3.add3": { state: "explored", best: { correct: 3, answered: 4 } } } }, stations);
  assert.equal(pr["math.fraction.the-whole"], 1 / 3);
  assert.equal(pr["math.decimal.tenths"], 0);
  assert.equal(pr["m.g3.add3"], .75);
  assert.equal("m.g1.count" in pr, false);
  // 整次完成算 1
  const done = nodeProgress([...events, ev("a1", 4, "attempt.completed")], null, stations);
  assert.equal(done["math.fraction.the-whole"], 1);
});

test("详情里的星：点亮实心加 ✓、有进度画弧、未探空心、未开放虚线", () => {
  const m = buildChart({ catalog, nodes: [...nodes, { id: "math.fraction.the-whole", activities: ["act.z"] }, { id: "m.g3.add3", activities: [] }], mastery, grade: 3, progress: { "math.fraction.the-whole": 1 / 3 } });
  const lit = m.byId.get("math.decimal.tenths"), half = m.byId.get("math.fraction.the-whole"), ex = m.byId.get("math.fraction.unit-fraction");
  const un = m.byId.get("m.g3.add3"), cl = m.byId.get("m.g1.count");
  assert.deepEqual([lit, half, ex, un, cl].map(detailState), ["lit", "landed", "landed", "untouched", "closed"]);
  assert.match(detailMark(lit, 14), /class="dmark lit"/);
  assert.match(detailMark(half, 14), /class="dprog"/);
  assert.doesNotMatch(detailMark(ex, 14), /class="dprog"/); // 探过、没有进度数字时只有实线圆
  assert.doesNotMatch(detailMark(un, 12), /stroke-dasharray/);
  assert.match(detailMark(cl, 12), /stroke-dasharray="3 4"/);
});

test("笔记：线路可点、信号卡和任务带插图、图鉴提示、不同年龄看到的样子、反向链接", () => {
  const p = model.byId.get("math.decimal.tenths");
  const card = { driving_question: "一块饼切成十份？", lenses: [{ band: "G3-4", approach: "百格板涂色" }, { band: "G5-6", approach: "小数点移动" }] };
  const html = noteHtml(p, { card, model, tasks: [{ id: "act.x", title: "百格板", meta: "动手探索 · 3 站", go: "开始" }], canStart: true, animate: true });
  assert.match(html, /<a class="wikilink" href="#metro" data-line="num"><span class="lsw"[^>]*><\/span>数与运算线<\/a>/);
  assert.match(html, /class="signal-card"[\s\S]*<svg viewBox="0 0 100 100" width="100" height="100" class="drawin"/);
  assert.match(html, /class="taskrow"><svg viewBox="0 0 100 100" width="48"/);
  assert.match(html, /图鉴 No\.076/);
  assert.match(html, /class="minispec">/); // 已点亮：不是灰的
  assert.match(html, /已收集/);
  assert.match(html, /不同年龄看到的样子/);
  assert.match(html, /<div class="on"><span class="b">G3-4<\/span>/);
  assert.match(html, /<div class=""><span class="b">G5-6<\/span>/);
  assert.equal(AGE_BAND[model.currentBand], "G3-4");
  assert.match(html, /反向链接/);
  assert.match(html, /点亮这里之后可以去：<\/p><div class="links"><a class="wikilink" href="#" data-goto="math\.decimal\.compare-add">/);
  assert.doesNotMatch(html, /学习|信号站/);
  // 没点亮：图鉴提示是灰的，写「点亮之后」
  const ex = noteHtml(model.byId.get("math.fraction.unit-fraction"), { card: {}, model, tasks: [], canStart: true });
  assert.match(ex, /class="minispec locked"/);
  assert.match(ex, /点亮之后，这张标本卡会收进图鉴/);
  assert.doesNotMatch(ex, /不同年龄看到的样子/);
  assert.match(ex, /小数是什么/); // 反向链接里有它
  // 插图取法：主题默认，原型有专属插图的点用专属的
  assert.equal(iconOf(p), "blocks");
  assert.equal(iconOf({ id: "math.geometry.perimeter", theme: "geo" }), "perimeter");
  assert.equal(iconOf({ id: "x", theme: "life" }), "sprout");
  assert.match(icon("sprout", "science", 40, 3), /--icon-fill:var\(--c-sci\)/);
});

test("笔记：未开放的星没有卡，不显示「不同年龄看到的样子」，反向链接照目录算", () => {
  const html = noteHtml(model.byId.get("m.g3.mul1-oral"), { model, tasks: [], canStart: true });
  assert.match(html, /还没开放/);
  assert.doesNotMatch(html, /不同年龄看到的样子|图鉴/);
  assert.match(html, /反向链接[\s\S]*data-goto="m\.g3\.mul1-written">笔算乘法<\/a>/);
  const leaf = noteHtml(model.byId.get("m.g3.mul1-written"), { model, tasks: [], canStart: true });
  // 笔算乘法后面是两位数乘两位数
  assert.match(leaf, /两位数乘两位数/);
});
