// 实现者补的测试：设备存储 1 → 2 的升级分支（docs/specs/backup.md 5.1，原则 7）。
// Node 里没有 IndexedDB，这里用一个记下 createObjectStore 调用的假 db 测 upgrade() 的分支；
// 真实 IndexedDB 上的升级（旧记录一字不变、三个新仓库是空的）在整合时用浏览器跑，结果写进 PR。
import { test } from "node:test";
import assert from "node:assert/strict";
import { upgrade, DB_VERSION } from "../store.js";

function fakeDb(existing = []) {
  const stores = new Map(existing.map((n) => [n, "旧的"]));
  const made = [];
  return {
    stores, made,
    createObjectStore(name, opts) {
      if (stores.has(name)) throw new Error(`ConstraintError：${name} 已经有了`);
      stores.set(name, opts ?? {});
      made.push([name, opts ?? {}]);
    },
  };
}

test("版本号是 2", () => { assert.equal(DB_VERSION, 2); });

test("从 0 升级：建全部六个仓库，主键照规格 5.1", () => {
  const db = fakeDb();
  upgrade(db, 0);
  assert.deepEqual(db.made, [
    ["inbox", { autoIncrement: true }],
    ["receipts", { keyPath: "event_id" }],
    ["meta", {}],
    ["imports", { keyPath: "batch_id" }],
    ["archive", { autoIncrement: true }],
    ["releases", { keyPath: "release_id" }],
  ]);
});

test("从 1 升级：只建新加的三个，旧仓库不碰", () => {
  const db = fakeDb(["inbox", "receipts", "meta"]);
  upgrade(db, 1);
  assert.deepEqual(db.made.map((m) => m[0]), ["imports", "archive", "releases"]);
  for (const n of ["inbox", "receipts", "meta"]) assert.equal(db.stores.get(n), "旧的", `${n} 没被重建`);
});

test("反例：从 1 升级时如果去重建旧仓库会报错（假 db 能发现「改旧仓库」）", () => {
  const db = fakeDb(["inbox", "receipts", "meta"]);
  assert.throws(() => upgrade(db, 0), /ConstraintError/);
});

test("已经是 2：什么都不建", () => {
  const db = fakeDb(["inbox", "receipts", "meta", "imports", "archive", "releases"]);
  upgrade(db, 2);
  assert.deepEqual(db.made, []);
});
