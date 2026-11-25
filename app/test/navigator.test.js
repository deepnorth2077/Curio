// 领航员的纯函数（docs/specs/navigators.md 第 1、4 节）：SVG 白名单（和 Python 同一份向量）、去掉最外层 <svg>、显示谁。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { checkNavigatorSvg, innerSvg, shownNavigator, NAVIGATOR_FACES } from "../navigator.js";

const enc = (s) => new TextEncoder().encode(s);
const V = JSON.parse(readFileSync(new URL("../vectors/navigator-svg.json", import.meta.url), "utf8"));

test("SVG 检查：每条向量的结果和期望一致（Python 的 check_navigator_svg 用同一份）", () => {
  assert.ok(V.checks.filter((c) => c.ok).length >= 5 && V.checks.filter((c) => !c.ok).length >= 30);
  for (const c of V.checks) {
    const errors = checkNavigatorSvg(enc(c.svg));
    assert.equal(errors.length === 0, c.ok, `${c.name}：${errors.join("；") || "通过"}`);
  }
});

test("SVG 检查：不是 UTF-8 的字节不通过", () => {
  assert.ok(checkNavigatorSvg(new Uint8Array([0x3c, 0xff, 0xfe])).length > 0);
});

test("去掉最外层 <svg>：向量", () => {
  for (const c of V.inner) assert.equal(innerSvg(c.svg), c.inner, c.name);
});

test("去掉最外层 <svg>：根带前缀时不肯做（去掉以后前缀没有声明）", () => {
  const s = V.checks.find((c) => c.name === "带前缀的根（命名空间对）").svg;
  assert.throws(() => innerSvg(s));
});

test("仓库里两位领航员的十二张脸都通过检查，去掉根以后不再有 <svg>", () => {
  const root = new URL("../../content/navigators/", import.meta.url);
  const dirs = readdirSync(root).sort();
  assert.deepEqual(dirs, ["nav.lamp", "nav.ring"]);
  for (const d of dirs) for (const f of NAVIGATOR_FACES) {
    const bytes = readFileSync(new URL(`${d}/${f}.svg`, root));
    assert.deepEqual(checkNavigatorSvg(new Uint8Array(bytes)), [], `${d}/${f}`);
    const inner = innerSvg(bytes.toString("utf8"));
    assert.ok(inner.length > 100 && !/<\/?svg/.test(inner), `${d}/${f}`);
  }
});

// 规格第 4 节的用例 1～5（期望值手算）
const both = new Map([["nav.ring", {}], ["nav.lamp", {}]]);
test("显示谁 1：还没选 → 排第一的 nav.lamp", () => { assert.equal(shownNavigator(null, both), "nav.lamp"); });
test("显示谁 2：选了 nav.ring → nav.ring", () => { assert.equal(shownNavigator("nav.ring", both), "nav.ring"); });
test("显示谁 3：选的 nav.gone 不在发布包里 → nav.lamp", () => { assert.equal(shownNavigator("nav.gone", both), "nav.lamp"); });
test("显示谁 4：选了 nav.ring，发布包里只有 lamp → nav.lamp", () => { assert.equal(shownNavigator("nav.ring", new Map([["nav.lamp", {}]])), "nav.lamp"); });
test("显示谁 5：发布包里没有领航员 → null", () => {
  assert.equal(shownNavigator("nav.ring", new Map()), null);
  assert.equal(shownNavigator(null, []), null);
});
