// 显示时才取的六张脸（docs/specs/navigators.md 第 2 节）：核对字节数、SHA-256，按白名单再查一遍，去掉最外层 <svg>。
import { test, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, cpSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { loadRelease, loadNavigatorFaces, ReleaseError, NAVIGATOR_FACES } from "../app.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const temps = [];
after(() => { for (const d of temps) rmSync(d, { recursive: true, force: true }); });
const asked = [];
const fileFetch = async (url) => {
  asked.push(String(url));
  try { const b = readFileSync(fileURLToPath(url)); return { ok: true, arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) }; }
  catch { return { ok: false, status: 404 }; }
};
function build() {
  const dir = mkdtempSync(join(tmpdir(), "curio-faces-")); temps.push(dir);
  const content = join(dir, "content");
  cpSync(join(root, "tools/tests/fixtures/content"), content, { recursive: true });
  cpSync(join(root, "content/navigators"), join(content, "navigators"), { recursive: true });
  const out = join(dir, "release");
  execFileSync("python3", [join(root, "tools/build_release.py"), "--content", content, "--out", out, "--commit", "0".repeat(40)], { cwd: root, stdio: "pipe" });
  return out;
}
const rel = build();
const url = pathToFileURL(join(rel, "release.json"));

test("取到六张脸：只取这一位的六个 SVG，内容是去掉最外层 <svg> 的那一段", async () => {
  const pack = await loadRelease(url, fileFetch);
  asked.length = 0;
  const faces = await loadNavigatorFaces(pack.navigators.get("nav.ring").entry, url, fileFetch);
  assert.deepEqual(Object.keys(faces), NAVIGATOR_FACES);
  assert.deepEqual(asked.map((u) => u.split("/content/")[1]).sort(), NAVIGATOR_FACES.map((f) => `navigators/nav.ring/${f}.svg`).sort());
  const raw = readFileSync(join(root, "content/navigators/nav.ring/clap.svg"), "utf8");
  assert.ok(raw.includes(faces.clap) && !faces.clap.includes("<svg"));
});

test("反例：SVG 改了一个字节（哈希对不上）→ broken", async () => {
  const pack = await loadRelease(url, fileFetch);
  const f = join(rel, "content/navigators/nav.lamp/think.svg");
  const good = readFileSync(f);
  writeFileSync(f, Buffer.from(good.toString("utf8").replace("f-ink", "f-sky")));
  try { await assert.rejects(loadNavigatorFaces(pack.navigators.get("nav.lamp").entry, url, fileFetch), ReleaseError); }
  finally { writeFileSync(f, good); }
});

test("反例：清单哈希对得上，但内容不过白名单（带 <script>）→ broken，外壳不用", async () => {
  const pack = await loadRelease(url, fileFetch);
  const entry = structuredClone(pack.navigators.get("nav.lamp").entry);
  const f = join(rel, "content/navigators/nav.lamp/wrong.svg");
  const good = readFileSync(f);
  const bad = Buffer.from(good.toString("utf8").replace("</svg>", "<script>alert(1)</script></svg>"));
  writeFileSync(f, bad);
  const item = entry.files.find((x) => x.path.endsWith("/wrong.svg"));
  item.bytes = bad.byteLength; item.sha256 = createHash("sha256").update(bad).digest("hex");
  try { await assert.rejects(loadNavigatorFaces(entry, url, fileFetch), /wrong\.svg/); }
  finally { writeFileSync(f, good); }
});
