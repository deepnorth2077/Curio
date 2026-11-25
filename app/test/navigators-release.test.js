// #242 PR 1（docs/specs/navigators.md 第 2 节）：外壳读带 navigators 的发布包，只核对、不显示。
// 验收测试的作者写，实现者不改（受保护路径）。办法照 release-extra.test.js：用 tools/build_release.py 现场构建，再故意改坏。
// 约定的接口：loadRelease 的结果里多一个 navigators，每位对应 navigator.yaml.json 解析出来的定义（def）；
// 容器可以是 Map<id, {entry, def}>（和 activities 同款）或数组，下面的 defsOf 两种都收。
// 跑法：node --test app/test/navigators-release.test.js
import { test, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, cpSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { loadRelease, ReleaseError, ENGINE_LEVEL } from "../app.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const fixtures = join(root, "tools/tests/fixtures");
const temps = [];
const tempDir = (prefix) => { const d = mkdtempSync(join(tmpdir(), prefix)); temps.push(d); return d; };
after(() => { for (const d of temps) rmSync(d, { recursive: true, force: true }); });

const asked = [];
const fileFetch = async (url) => {
  asked.push(String(url));
  try { const b = readFileSync(fileURLToPath(url)); return { ok: true, json: async () => JSON.parse(b.toString("utf8")), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) }; }
  catch { return { ok: false, status: 404 }; }
};
const urlOf = (d) => pathToFileURL(join(d, "release.json"));
const defsOf = (r) => {
  const list = r.navigators instanceof Map ? [...r.navigators.values()] : (r.navigators ?? []);
  return list.map((x) => x.def ?? x);
};

function buildWith(navigators) {
  const dir = tempDir("curio-nav-");
  const content = join(dir, "content");
  cpSync(join(fixtures, "content"), content, { recursive: true });
  if (navigators) cpSync(join(fixtures, "navigators"), join(content, "navigators"), { recursive: true });
  const out = join(dir, "release");
  execFileSync("python3", [join(root, "tools/build_release.py"), "--content", content, "--out", out, "--commit", "0".repeat(40)], { cwd: root, stdio: "pipe" });
  return out;
}
let withNav = null;
const goodRelease = () => (withNav ||= buildWith(true));
const copy = () => { const d = join(tempDir("curio-nav-bad-"), "release"); cpSync(goodRelease(), d, { recursive: true }); return d; };
const readManifest = (d) => JSON.parse(readFileSync(join(d, "release.json"), "utf8"));

test("外壳的引擎等级是 2", () => {
  assert.equal(ENGINE_LEVEL, 2);
});

test("带 navigators 的发布包能核对通过，engine_min 是 2 也不报「需要更新」，结果里有两位的定义", async () => {
  const dir = goodRelease();
  assert.equal(readManifest(dir).engine_min, 2);
  assert.deepEqual(readManifest(dir).navigators.map((n) => n.id), ["nav.lamp", "nav.ring"]);
  const r = await loadRelease(urlOf(dir), fileFetch);
  assert.match(r.release.release_id, /^rel_[0-9a-f]{64}$/);
  const defs = defsOf(r);
  assert.deepEqual(defs.map((d) => d.id).sort(), ["nav.lamp", "nav.ring"]);
  const lamp = defs.find((d) => d.id === "nav.lamp");
  assert.equal(lamp.schema, "navigator/1");
  assert.equal(lamp.title, "小灯");
  assert.equal(lamp.intro, "我头顶有一盏小灯，想到什么它就亮。");
  assert.deepEqual(lamp.unlock, { start: true });
  assert.equal(lamp.review, "approved");
  assert.equal(defs.find((d) => d.id === "nav.ring").title, "小环");
  assert.deepEqual(r.nodes.map((n) => n.id), ["math.number.fraction-intro"], "知识点照常读出来");
});

test("读包只取每位的 navigator.yaml.json，不预取 SVG（选中那位的 SVG 要显示时才取）", async () => {
  asked.length = 0;
  await loadRelease(urlOf(goodRelease()), fileFetch);
  assert.ok(asked.some((u) => u.endsWith("/content/navigators/nav.lamp/navigator.yaml.json")));
  assert.ok(asked.some((u) => u.endsWith("/content/navigators/nav.ring/navigator.yaml.json")));
  assert.deepEqual(asked.filter((u) => u.endsWith(".svg")), [], "没有取任何 SVG");
});

test("改了领航员 yaml.json 的一个字节：broken", async () => {
  for (const nid of ["nav.lamp", "nav.ring"]) {
    const d = copy();
    const f = join(d, `content/navigators/${nid}/navigator.yaml.json`);
    const text = readFileSync(f, "utf8");
    writeFileSync(f, text.replace("小", "晓"));
    await assert.rejects(loadRelease(urlOf(d), fileFetch), (e) => e instanceof ReleaseError && e.kind === "broken", nid);
  }
});

test("领航员的 yaml.json 文件不见了：broken", async () => {
  const d = copy();
  rmSync(join(d, "content/navigators/nav.ring/navigator.yaml.json"));
  await assert.rejects(loadRelease(urlOf(d), fileFetch), (e) => e.kind === "broken");
});

test("清单里的 navigators 被改动或删掉：content_hash 对不上，broken（领航员计入哈希）", async () => {
  const d1 = copy();
  const m1 = readManifest(d1);
  m1.navigators[0].version = 2;
  writeFileSync(join(d1, "release.json"), JSON.stringify(m1));
  await assert.rejects(loadRelease(urlOf(d1), fileFetch), (e) => e.kind === "broken");
  const d2 = copy();
  const m2 = readManifest(d2);
  delete m2.navigators;
  writeFileSync(join(d2, "release.json"), JSON.stringify(m2));
  await assert.rejects(loadRelease(urlOf(d2), fileFetch), (e) => e.kind === "broken");
  const d3 = copy();
  const m3 = readManifest(d3);
  m3.navigators.reverse();
  writeFileSync(join(d3, "release.json"), JSON.stringify(m3));
  await assert.rejects(loadRelease(urlOf(d3), fileFetch), (e) => e.kind === "broken", "顺序也在哈希里");
});

test("engine_min 3：需要更新（不往下读）", async () => {
  const d = copy();
  const m = readManifest(d);
  m.engine_min = 3;
  writeFileSync(join(d, "release.json"), JSON.stringify(m));
  await assert.rejects(loadRelease(urlOf(d), fileFetch), (e) => e.kind === "update");
});

test("没有领航员的旧发布包照常能读：engine_min 1，结果里没有领航员", async () => {
  const dir = buildWith(false);
  assert.equal(readManifest(dir).engine_min, 1);
  assert.ok(!("navigators" in readManifest(dir)));
  const r = await loadRelease(urlOf(dir), fileFetch);
  assert.deepEqual(defsOf(r), []);
});
