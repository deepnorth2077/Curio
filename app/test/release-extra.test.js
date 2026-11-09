// 实现者补的测试：发布包核对（规格第 2 节）。用 tools/build_release.py 现场构建 slice-1a 夹具，再故意改坏。
import { test, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, cpSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { canonicalJson, cmpCodePoints, loadRelease, ReleaseError } from "../app.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const fileFetch = async (url) => {
  try { const b = readFileSync(fileURLToPath(url)); return { ok: true, json: async () => JSON.parse(b.toString("utf8")), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) }; }
  catch { return { ok: false, status: 404 }; }
};

const temps = [];
const tempDir = (prefix) => { const d = mkdtempSync(join(tmpdir(), prefix)); temps.push(d); return d; };
after(() => { for (const d of temps) rmSync(d, { recursive: true, force: true }); });

let built = null;
function build() {
  if (built) return built;
  const dir = tempDir("curio-rel-");
  const out = join(dir, "release");
  execFileSync("python3", [join(root, "tools", "build_release.py"), "--content", join(root, "tools/tests/fixtures/slice-1a/content"), "--out", out, "--commit", "0".repeat(40)], { cwd: root, stdio: "pipe" });
  built = out;
  return out;
}
const copy = () => { const d = join(tempDir("curio-bad-"), "release"); cpSync(build(), d, { recursive: true }); return d; };
const urlOf = (d) => pathToFileURL(join(d, "release.json"));

test("规范 JSON：递归排序键、按码点、数组保持顺序", () => {
  assert.equal(canonicalJson({ b: [2, { z: "x", a: 1 }], a: "é" }), '{"a":"é","b":[2,{"a":1,"z":"x"}]}');
  assert.ok(cmpCodePoints("\u{1F600}", "～") > 0, "补充平面字符按码点排在 U+FF5E 后面");
  assert.throws(() => canonicalJson({ a: 1.5 }));
  assert.throws(() => canonicalJson({ a: null }));
});

test("构建器生成的发布包核对通过", async () => {
  const p = await loadRelease(urlOf(build()), fileFetch);
  assert.match(p.release.release_id, /^rel_[0-9a-f]{64}$/);
  assert.deepEqual(p.nodes.map((n) => n.id), ["math.number.fraction-intro"]);
  assert.equal(p.activities.get("act.quiz.fraction-intro-01").def.body.items.length, 5);
});

test("改了一份 .yaml.json：broken", async () => {
  const d = copy();
  const f = join(d, "content/activities/act.quiz.fraction-intro-01/activity.yaml.json");
  writeFileSync(f, readFileSync(f, "utf8").replace("分数小挑战", "分数小挑站"));
  await assert.rejects(loadRelease(urlOf(d), fileFetch), (e) => e instanceof ReleaseError && e.kind === "broken");
});

test("改了清单（content_hash 对不上 / release_id 对不上）：broken", async () => {
  const d = copy();
  const m = JSON.parse(readFileSync(join(d, "release.json"), "utf8"));
  m.nodes[0].version = 2;
  writeFileSync(join(d, "release.json"), JSON.stringify(m));
  await assert.rejects(loadRelease(urlOf(d), fileFetch), (e) => e.kind === "broken");
  const d2 = copy();
  const m2 = JSON.parse(readFileSync(join(d2, "release.json"), "utf8"));
  m2.release_id = "rel_" + "0".repeat(64);
  writeFileSync(join(d2, "release.json"), JSON.stringify(m2));
  await assert.rejects(loadRelease(urlOf(d2), fileFetch), (e) => e.kind === "broken");
});

test("engine_min 大于 1：需要更新（不往下读）", async () => {
  const d = copy();
  const m = JSON.parse(readFileSync(join(d, "release.json"), "utf8"));
  m.engine_min = 2;
  writeFileSync(join(d, "release.json"), JSON.stringify(m));
  await assert.rejects(loadRelease(urlOf(d), fileFetch), (e) => e.kind === "update");
});

test("缺文件：broken", async () => {
  await assert.rejects(loadRelease(pathToFileURL("/nonexistent/release.json"), fileFetch), (e) => e.kind === "broken");
});
