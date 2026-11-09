// 黄金向量的执行器（竖切片 1 规格第 7 节）。Claude 写，实现者不改（受保护路径）。
// 跑法：node --test kernel/test/*.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createLog } from "../js/log.js";
import { projectMastery } from "../js/mastery.js";
import { numberOk } from "../js/validate.js";

const here = dirname(fileURLToPath(import.meta.url));
const vdir = join(here, "..", "vectors");
const files = readdirSync(vdir).filter((f) => f.endsWith(".json") && f !== "numbers.json").sort();

/** 一项输入的原始文字（规格第 7 节：event 浅合并；raw 原样；pad_to_bytes 末尾补空格）。 */
export function rawOf(base, item) {
  let raw = item.raw !== undefined ? item.raw : JSON.stringify(Object.assign({}, base, item.event));
  if (item.pad_to_bytes !== undefined) {
    const n = Buffer.byteLength(raw, "utf8");
    if (n > item.pad_to_bytes) throw new Error(`向量有错：原文已有 ${n} 字节，超过 pad_to_bytes`);
    raw += " ".repeat(item.pad_to_bytes - n);
  }
  return raw;
}

const resultOf = (r) => (r.result === "quarantined" ? `quarantined:${r.reason}` : r.result);
const snap = (log) => structuredClone({ events: log.events(), raw: log.raw(), quarantined: log.quarantined() });

/** 固定种子的伪随机数（mulberry32），保证乱序测试每次一样。 */
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

for (const f of files) {
  const v = JSON.parse(readFileSync(join(vdir, f), "utf8"));
  const raws = v.inputs.map((it) => rawOf(v.base, it));

  test(`${v.name}：按顺序摄入`, () => {
    const log = createLog();
    v.inputs.forEach((it, i) => {
      const before = snap(log);
      const c1 = log.check(raws[i]);
      const c2 = log.check(raws[i]);
      assert.deepEqual(snap(log), before, `第 ${i + 1} 项：check 改了日志`);
      assert.equal(resultOf(c1), it.expect, `第 ${i + 1} 项 check：${it.why || ""}`);
      assert.equal(resultOf(c2), it.expect, `第 ${i + 1} 项第二次 check`);
      const g = log.ingest(raws[i]);
      assert.equal(resultOf(g), resultOf(c1), `第 ${i + 1} 项：ingest 和 check 的结果不同`);
      const after = snap(log);
      if (g.result === "accepted") {
        assert.equal(after.events.length, before.events.length + 1, `第 ${i + 1} 项：接收后 events 应多一条`);
        assert.equal(after.raw.length, before.raw.length + 1);
        assert.equal(after.raw.at(-1), raws[i]);
        assert.equal(after.quarantined.length, before.quarantined.length);
      } else if (g.result === "duplicate") {
        assert.deepEqual(after, before, `第 ${i + 1} 项：重复的不该进任何地方`);
      } else {
        assert.equal(after.events.length, before.events.length);
        assert.equal(after.raw.length, before.raw.length);
        assert.equal(after.quarantined.length, before.quarantined.length + 1, `第 ${i + 1} 项：隔离的应进隔离区`);
        const q = after.quarantined.at(-1);
        assert.equal(q.raw, raws[i]);
        assert.equal(q.reason, g.reason);
      }
      if (it.mastery_after) assert.deepEqual(projectMastery(log.events()), it.mastery_after, `第 ${i + 1} 项之后的投影`);
    });
    const acceptedRaw = v.inputs.map((it, i) => (it.expect === "accepted" ? raws[i] : null)).filter((x) => x !== null);
    assert.deepEqual(log.raw(), acceptedRaw, "raw() 应正好是标成 accepted 的原文，按顺序");
    assert.deepEqual(projectMastery(log.events()), v.mastery);
  });

  if (v.order_free) {
    test(`${v.name}：乱序、重复 20 次，投影不变`, () => {
      for (let round = 0; round < 20; round++) {
        const r = rng(1000 + round);
        const seq = [];
        raws.forEach((raw) => {
          const times = 1 + Math.floor(r() * 3);
          for (let k = 0; k < times; k++) seq.push(raw);
        });
        for (let i = seq.length - 1; i > 0; i--) {
          const j = Math.floor(r() * (i + 1));
          [seq[i], seq[j]] = [seq[j], seq[i]];
        }
        const log = createLog();
        for (const raw of seq) {
          const g = log.ingest(raw);
          assert.notEqual(g.result, "quarantined", `第 ${round + 1} 轮：乱序时不该有隔离：${raw.slice(0, 80)}`);
        }
        assert.deepEqual(projectMastery(log.events()), v.mastery, `第 ${round + 1} 轮的投影`);
      }
    });
  }
}

test("数值规则（numbers.json）", () => {
  const v = JSON.parse(readFileSync(join(vdir, "numbers.json"), "utf8"));
  for (const c of v.cases) assert.equal(numberOk(JSON.parse(c.json)), c.expect, `${c.json}：${c.why}`);
});
