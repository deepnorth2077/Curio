// 判分向量的执行器（竖切片 1 规格第 5、7 节）。Claude 写，实现者不改（受保护路径）。
// 补充要求：grade 不改传进来的 answer（引擎模块是纯函数，规格第 1 节）。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { grade } from "../js/grade.js";

const here = dirname(fileURLToPath(import.meta.url));
const v = JSON.parse(readFileSync(join(here, "..", "vectors", "grading.json"), "utf8"));

for (const [i, c] of v.cases.entries()) {
  test(`判分 ${i + 1}：${c.answer} ← ${JSON.stringify(c.response)}（${c.why}）`, () => {
    const answer = structuredClone(v.answers[c.answer]);
    assert.ok(answer, `向量有错：没有 answer「${c.answer}」`);
    const before = structuredClone(answer);
    assert.deepEqual(grade(answer, c.response), c.expect);
    assert.deepEqual(answer, before, "grade 不能改传进来的 answer");
  });
}
