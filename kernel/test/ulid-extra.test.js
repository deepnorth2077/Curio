// 实现者补的测试：ULID 格式和单调递增（事件规格第 1 节）。
import { test } from "node:test";
import assert from "node:assert/strict";
import { createUlid, encodeUlid } from "../js/ulid.js";

const RE = /^[0-7][0-9A-HJKMNP-TV-Z]{25}$/;

test("编码：已知值", () => {
  assert.equal(encodeUlid(0, new Uint8Array(10)), "0".repeat(26));
  assert.equal(encodeUlid(2 ** 48 - 1, new Uint8Array(10).fill(255)), "7" + "Z".repeat(25));
  assert.throws(() => encodeUlid(2 ** 48, new Uint8Array(10)));
  assert.throws(() => encodeUlid(1, new Uint8Array(9)));
});

test("同一毫秒、时钟倒退：单调递增，格式合法", () => {
  const next = createUlid();
  const r = new Uint8Array(10).fill(7);
  const a = next(1000, r), b = next(1000, r), c = next(999, new Uint8Array(10)), d = next(1001, r);
  for (const x of [a, b, c, d]) assert.match(x, RE);
  assert.ok(a < b && b < c && c < d, [a, b, c, d].join(" "));
});

test("随机部分进位", () => {
  const next = createUlid();
  const r = new Uint8Array(10); r[9] = 255; r[8] = 255;
  const a = next(5, r), b = next(5, r);
  assert.ok(a < b);
  assert.equal(b.slice(10), encodeUlid(5, Uint8Array.from([0, 0, 0, 0, 0, 0, 0, 1, 0, 0])).slice(10));
});
