// relay/tools/passphrase.html 的测试：取出页面里的脚本，在 Node 里跑它的 sha256 和两行输出。

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import vm from "node:vm";

const html = readFileSync(new URL("../tools/passphrase.html", import.meta.url), "utf8");
const script = /<script>([\s\S]*?)<\/script>/.exec(html)[1];

function load(withSubtle = true) {
  const g = { TextEncoder, Uint8Array, Uint32Array, Math, Array, Error, console };
  g.crypto = withSubtle ? globalThis.crypto : { getRandomValues: (b) => globalThis.crypto.getRandomValues(b) };
  g.globalThis = g;
  vm.createContext(g);
  vm.runInContext(script, g);
  return g;
}

test("页面不引用任何外部资源", () => {
  assert.ok(!/\b(src|href)\s*=\s*["']?(https?:)?\/\//i.test(html));
  assert.ok(!/fetch\(|XMLHttpRequest|@import/.test(html));
});

test("纯 JS 的 sha256 和 node:crypto 一致（含空串、多块、汉字）", () => {
  const g = load();
  for (const s of ["", "abc", "a".repeat(55), "a".repeat(56), "a".repeat(64), "x".repeat(1000), "口令🌍"]) {
    const want = createHash("sha256").update(s, "utf8").digest("hex");
    assert.equal(g.sha256HexJS(new TextEncoder().encode(s)), want, s.slice(0, 10));
  }
});

test("两行输出：和验收用例里的盐、哈希对得上（有 subtle、没有 subtle 都一样）", async () => {
  for (const withSubtle of [true, false]) {
    const g = load(withSubtle);
    const out = await g.makeLines("correct horse battery staple", "s4lt-7f3a");
    assert.equal(out.salt, "CURIO_SALT=s4lt-7f3a");
    assert.equal(out.hash, "CURIO_PASSPHRASE_HASH=652689b7a191cb878c3cc03d0a47e4402feef74f8b60e91ed6b31eea836c2585");
  }
});

test("盐是 32 位小写十六进制，每次不一样", () => {
  const g = load();
  const a = g.makeSalt(), b = g.makeSalt();
  assert.match(a, /^[0-9a-f]{32}$/);
  assert.notEqual(a, b);
});
