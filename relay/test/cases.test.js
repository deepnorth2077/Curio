// 跑 cases.json 里 Claude 手算的验收用例。实现者不要改这个文件和 cases.json；
// 觉得用例错了，在交付说明里写出来，由 Claude 判断。
//
// 用例格式（curio-relay-cases/1）：
//   base_env + case.env（值为 null 表示删掉这一项）→ env，全是字符串。
//   case.storage：初始存储，键 → 对象（这里转成 JSON 字符串放进去）。
//   case.steps[]：按顺序发请求。
//     at：这一步的时间（deps.now() 返回它的毫秒数）。
//     origin：请求的 Origin，默认 doc.origin。
//     request.auth："good" 带对的口令；"bad" 带错的；"none" 不带；"raw:<值>" 原样放进 Authorization。
//     request.body：JSON 请求体；raw_body：原样字符串；body_bytes：凑一个正好这么多字节的 JSON 请求体。
//     upstream：这一步 DeepSeek 的回应 {status, json}；{throw: true} 表示超时或连不上（deps.upstream 抛错）。
//     expect.status、expect.json（顶层逐个键比较，键的值整个深比较）、expect.headers（不分大小写）、
//     expect.headers_absent、expect.upstream_calls（这一步调用 DeepSeek 的次数）、
//     expect.upstream_body（发给 DeepSeek 的请求体里这些顶层键深相等）、
//     expect.upstream_messages_contain（messages 拼起来以后包含这些字符串）。
//   case.storage_after：结束时这些键的内容（解析成对象后深相等）。
//   case.storage_absent：结束时这些键不存在。
//   case.never_contain：存储里的任何值、任何 console 输出都不能包含这些字符串（不存原文）。
//
// handle(request, env, deps) 可以是 async。deps.storage.get/put 返回 Promise；deps.upstream 返回 Promise。

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { handle } from "../src/handler.js";

const doc = JSON.parse(readFileSync(new URL("./cases.json", import.meta.url), "utf8"));
const ASK_PREFIX = "https://relay.test";

function makeEnv(overrides = {}) {
  const env = { ...doc.base_env };
  for (const [k, v] of Object.entries(overrides)) {
    if (v === null) delete env[k];
    else env[k] = v;
  }
  return env;
}

function bodyOfBytes(n) {
  const head = '{"age_band":"G3-4","question":"';
  const tail = '"}';
  const pad = n - Buffer.byteLength(head + tail);
  assert.ok(pad > 0, "body_bytes 太小");
  return head + "a".repeat(pad) + tail;
}

function makeRequest(step) {
  const r = step.request;
  const headers = new Headers(r.headers || {});
  headers.set("origin", step.origin || doc.origin);
  if (r.auth === "good") headers.set("authorization", "Bearer " + doc.passphrase);
  else if (r.auth === "bad") headers.set("authorization", "Bearer wrong " + doc.passphrase);
  else if (typeof r.auth === "string" && r.auth.startsWith("raw:")) headers.set("authorization", r.auth.slice(4));
  let body;
  if (r.body !== undefined) body = JSON.stringify(r.body);
  else if (r.raw_body !== undefined) body = r.raw_body;
  else if (r.body_bytes !== undefined) body = bodyOfBytes(r.body_bytes);
  if (body !== undefined) {
    headers.set("content-type", "application/json");
    assert.ok(r.body_bytes === undefined || Buffer.byteLength(body) === r.body_bytes);
  }
  return new Request(ASK_PREFIX + r.path, { method: r.method, headers, body });
}

for (const c of doc.cases) {
  test(c.name, async () => {
    const store = new Map(Object.entries(c.storage || {}).map(([k, v]) => [k, JSON.stringify(v)]));
    let now = 0;
    let pending = null;
    let calls = [];
    const deps = {
      storage: {
        get: async (key) => (store.has(key) ? store.get(key) : null),
        put: async (key, value) => {
          assert.equal(typeof value, "string", `存储 ${key} 的值必须是字符串`);
          store.set(key, value);
        },
      },
      upstream: async (body) => {
        calls.push(body);
        assert.ok(pending, "这一步不应该调用 DeepSeek");
        const u = pending;
        pending = null;
        if (u.throw) throw new Error("timeout");
        return { status: u.status, json: u.json };
      },
      now: () => now,
    };

    const logs = [];
    const orig = {};
    for (const m of ["log", "info", "warn", "error", "debug"]) {
      orig[m] = console[m];
      console[m] = (...a) => logs.push(a.map(String).join(" "));
    }
    try {
      for (const [i, step] of c.steps.entries()) {
        const where = `第 ${i + 1} 步`;
        now = Date.parse(step.at);
        pending = step.upstream || null;
        calls = [];
        const res = await handle(makeRequest(step), makeEnv(c.env), deps);
        const e = step.expect;
        assert.ok(res instanceof Response, `${where}：handle 要返回 Response`);
        assert.equal(res.status, e.status, `${where}：状态码`);
        for (const [h, v] of Object.entries(e.headers || {})) {
          assert.equal(res.headers.get(h), v, `${where}：响应头 ${h}`);
        }
        for (const h of e.headers_absent || []) {
          assert.equal(res.headers.get(h), null, `${where}：不该有响应头 ${h}`);
        }
        if (e.json) {
          const got = await res.json();
          for (const [k, v] of Object.entries(e.json)) {
            if (k === "usage" && typeof v === "object") {
              for (const [uk, uv] of Object.entries(v)) assert.deepEqual(got.usage?.[uk], uv, `${where}：usage.${uk}`);
            } else {
              assert.deepEqual(got[k], v, `${where}：响应里的 ${k}`);
            }
          }
        }
        if (e.upstream_calls !== undefined) assert.equal(calls.length, e.upstream_calls, `${where}：调用 DeepSeek 的次数`);
        if (e.upstream_body) {
          assert.equal(calls.length, 1, `${where}：应该调用一次 DeepSeek`);
          for (const [k, v] of Object.entries(e.upstream_body)) assert.deepEqual(calls[0][k], v, `${where}：发给 DeepSeek 的 ${k}`);
        }
        if (e.upstream_messages_contain) {
          assert.equal(calls.length, 1, `${where}：应该调用一次 DeepSeek`);
          const text = (calls[0].messages || []).map((m) => m.content).join("\n");
          for (const s of e.upstream_messages_contain) assert.ok(text.includes(s), `${where}：发给 DeepSeek 的内容里要有「${s}」`);
        }
        if (step.upstream && e.status === 200) assert.equal(pending, null, `${where}：应该调用 DeepSeek`);
      }
    } finally {
      Object.assign(console, orig);
    }

    for (const [k, v] of Object.entries(c.storage_after || {})) {
      assert.ok(store.has(k), `存储里应该有 ${k}`);
      assert.deepEqual(JSON.parse(store.get(k)), v, `存储 ${k} 的内容`);
    }
    for (const k of c.storage_absent || []) assert.ok(!store.has(k), `存储里不该有 ${k}`);
    for (const s of c.never_contain || []) {
      for (const [k, v] of store) assert.ok(!v.includes(s), `存储 ${k} 里出现了原文「${s}」`);
      for (const l of logs) assert.ok(!l.includes(s), `日志里出现了原文「${s}」`);
    }
  });
}
