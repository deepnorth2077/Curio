// 腾讯云适配层的测试：COS 签名、存储、DeepSeek 调用、请求和响应的转换。不联网（只用本机回环地址）。
//
// COS 签名的两组向量来自腾讯云对象存储「请求签名」文档（https://cloud.tencent.com/document/product/436/7778）
// 里的上传、下载示例：SecretKey、KeyTime、请求头、SignKey、HttpString 的 SHA1、Signature 和 Authorization 都照抄文档。

import { test } from "node:test";
import assert from "node:assert/strict";
import { Readable, PassThrough } from "node:stream";
import net from "node:net";
import {
  cosSign,
  cosEncode,
  makeCosStorage,
  makeUpstream,
  toRequest,
  writeResponse,
  readBody,
  createServer,
  credsFrom,
  credsDiagnosis,
  makeDeps,
  DEEPSEEK_URL,
  PORT,
  LISTEN_HOST,
  UPSTREAM_TIMEOUT_MS,
} from "../adapters/tencent.js";

// 腾讯云 COS 签名文档里公开的示例密钥（不是真的）。拆开写，免得 GitHub 的密钥扫描误报。
const DOC_ID = "AKID" + "Qjz3ltompVjBni5LitkWHFlFpwkn9U5q";
const DOC_KEY = "BQYIM75p8x0iWVFSIgqEKwFprpRSVHlz";

test("COS 签名：文档的上传示例", () => {
  const r = cosSign({
    secretId: DOC_ID,
    secretKey: DOC_KEY,
    method: "PUT",
    path: "/exampleobject(腾讯云)",
    headers: {
      Date: "Thu, 16 May 2019 06:45:51 GMT",
      Host: "examplebucket-1250000000.cos.ap-beijing.myqcloud.com",
      "Content-Type": "text/plain",
      "Content-Length": "13",
      "Content-MD5": "mQ/fVh815F3k6TAUm8m0eg==",
      "x-cos-acl": "private",
      "x-cos-grant-read": 'uin="100000000011"',
    },
    startSec: 1557989151,
    endSec: 1557996351,
  });
  assert.equal(r.signKey, "eb2519b498b02ac213cb1f3d1a3d27a3b3c9bc5f");
  assert.equal(r.stringToSign, "sha1\n1557989151;1557996351\n8b2751e77f43a0995d6e9eb9477f4b685cca4172\n");
  assert.equal(r.signature, "3b8851a11a569213c17ba8fa7dcf2abec6935172");
  assert.equal(
    r.authorization,
    "q-sign-algorithm=sha1&q-ak=" + DOC_ID + "&q-sign-time=1557989151;1557996351&q-key-time=1557989151;1557996351&q-header-list=content-length;content-md5;content-type;date;host;x-cos-acl;x-cos-grant-read&q-url-param-list=&q-signature=3b8851a11a569213c17ba8fa7dcf2abec6935172"
  );
});

test("COS 签名：文档的下载示例（带查询参数）", () => {
  const r = cosSign({
    secretId: DOC_ID,
    secretKey: DOC_KEY,
    method: "GET",
    path: "/exampleobject(腾讯云)",
    params: { "response-content-type": "application/octet-stream", "response-cache-control": "max-age=600" },
    headers: { Date: "Thu, 16 May 2019 06:55:53 GMT", Host: "examplebucket-1250000000.cos.ap-beijing.myqcloud.com" },
    startSec: 1557989753,
    endSec: 1557996953,
  });
  assert.equal(r.signKey, "937914bf490e9e8c189836aad2052e4feeb35eaf");
  assert.ok(r.stringToSign.includes("54ecfe22f59d3514fdc764b87a32d8133ea611e6"));
  assert.equal(r.signature, "01681b8c9d798a678e43b685a9f1bba0f6c0e012");
  assert.ok(r.authorization.includes("&q-header-list=date;host&q-url-param-list=response-cache-control;response-content-type&"));
});

test("COS 签名：改一个请求头的值，签名就变（反例）", () => {
  const base = { secretId: DOC_ID, secretKey: DOC_KEY, method: "GET", path: "/a", startSec: 1, endSec: 2 };
  const a = cosSign({ ...base, headers: { host: "b-1.cos.ap-guangzhou.myqcloud.com" } });
  const b = cosSign({ ...base, headers: { host: "b-2.cos.ap-guangzhou.myqcloud.com" } });
  assert.notEqual(a.signature, b.signature);
  assert.notEqual(cosSign({ ...base, method: "PUT" }).signature, cosSign(base).signature);
});

test("COS 编码：文档表里的符号都要编码，字母数字和 -_.~ 不编码", () => {
  assert.equal(cosEncode("a-b_c.d~e"), "a-b_c.d~e");
  assert.equal(cosEncode("!'()* /:="), "%21%27%28%29%2A%20%2F%3A%3D");
  assert.equal(cosEncode("腾"), "%E8%85%BE");
});

function fakeFetch(responses) {
  const calls = [];
  const fn = async (url, init) => {
    calls.push({ url, init });
    const r = responses.shift();
    if (r instanceof Error) throw r;
    return new Response(r.body ?? "", { status: r.status });
  };
  fn.calls = calls;
  return fn;
}

const cosOpts = {
  bucket: "curio-test-1250000000",
  region: "ap-guangzhou",
  secretId: "AKIDtest",
  secretKey: "keytest",
  sessionToken: "tokentest",
  nowMs: () => 1794200400000,
};

test("COS 存储：GET 成功返回文字，地址和签名头对", async () => {
  const f = fakeFetch([{ status: 200, body: '{"times":[]}' }]);
  const s = makeCosStorage({ ...cosOpts, fetchImpl: f });
  assert.equal(await s.get("auth/failures.json"), '{"times":[]}');
  const { url, init } = f.calls[0];
  assert.equal(url, "https://curio-test-1250000000.cos.ap-guangzhou.myqcloud.com/auth/failures.json");
  assert.equal(init.method, "GET");
  assert.equal(init.headers["x-cos-security-token"], "tokentest");
  assert.match(init.headers.Authorization, /^q-sign-algorithm=sha1&q-ak=AKIDtest&q-sign-time=1794200340;1794201000&q-key-time=1794200340;1794201000&q-header-list=host&q-url-param-list=&q-signature=[0-9a-f]{40}$/);
  const expected = cosSign({
    secretId: "AKIDtest",
    secretKey: "keytest",
    method: "GET",
    path: "/auth/failures.json",
    headers: { host: "curio-test-1250000000.cos.ap-guangzhou.myqcloud.com" },
    startSec: 1794200340,
    endSec: 1794201000,
  });
  assert.equal(init.headers.Authorization, expected.authorization);
});

test("COS 存储：GET 404 就是 null", async () => {
  const s = makeCosStorage({ ...cosOpts, fetchImpl: fakeFetch([{ status: 404, body: "<Error><Code>NoSuchKey</Code></Error>" }]) });
  assert.equal(await s.get("usage/2026-11.json"), null);
});

test("COS 存储：GET 403（没绑运行角色之类）要抛错，不能当成空", async () => {
  const s = makeCosStorage({ ...cosOpts, fetchImpl: fakeFetch([{ status: 403, body: "AccessDenied" }]) });
  await assert.rejects(() => s.get("usage/2026-11.json"));
});

test("COS 存储：PUT 带上内容；失败抛错", async () => {
  const f = fakeFetch([{ status: 200 }, { status: 500 }]);
  const s = makeCosStorage({ ...cosOpts, fetchImpl: f });
  await s.put("usage/2026-11.json", '{"calls_by_day":{},"cost_ufen":0}');
  assert.equal(f.calls[0].init.method, "PUT");
  assert.equal(f.calls[0].init.body, '{"calls_by_day":{},"cost_ufen":0}');
  await assert.rejects(() => s.put("usage/2026-11.json", "{}"));
});

test("COS 存储：没有临时密钥时抛错，不发请求", async () => {
  const f = fakeFetch([]);
  const s = makeCosStorage({ ...cosOpts, secretId: undefined, secretKey: undefined, fetchImpl: f });
  await assert.rejects(() => s.get("auth/failures.json"));
  assert.equal(f.calls.length, 0);
});

test("DeepSeek：带密钥、发 JSON、回 {status, json}", async () => {
  const f = fakeFetch([{ status: 200, body: '{"choices":[]}' }]);
  const up = makeUpstream({ apiKey: "sk-x", fetchImpl: f });
  const out = await up({ model: "m", messages: [] });
  assert.deepEqual(out, { status: 200, json: { choices: [] } });
  assert.equal(f.calls[0].url, DEEPSEEK_URL);
  assert.equal(f.calls[0].init.headers.Authorization, "Bearer sk-x");
  assert.deepEqual(JSON.parse(f.calls[0].init.body), { model: "m", messages: [] });
  assert.ok(f.calls[0].init.signal instanceof AbortSignal);
});

test("DeepSeek：回的不是 JSON 时 json 为 null；连不上就抛错", async () => {
  const up = makeUpstream({ apiKey: "sk-x", fetchImpl: fakeFetch([{ status: 502, body: "<html>" }, new Error("ECONNRESET")]) });
  assert.deepEqual(await up({}), { status: 502, json: null });
  await assert.rejects(() => up({}));
});

test("DeepSeek：超过超时就抛错", async () => {
  const slow = (url, init) =>
    new Promise((resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(init.signal.reason));
    });
  const up = makeUpstream({ apiKey: "sk-x", fetchImpl: slow, timeoutMs: 20 });
  // AbortSignal.timeout 的计时器不挡住进程退出，这里另放一个计时器让测试等到它。
  const keep = setTimeout(() => {}, 1000);
  try {
    await assert.rejects(() => up({}), (e) => e.name === "TimeoutError");
  } finally {
    clearTimeout(keep);
  }
});

test("转换：http 请求 → 标准 Request", async () => {
  const req = toRequest(
    { method: "post", url: "/v1/capabilities/tutor.ask?x=1", headers: { host: "abc.example", origin: "https://o.example", authorization: "Bearer p", "content-length": "2", connection: "keep-alive" } },
    Buffer.from("{}")
  );
  assert.equal(req.method, "POST");
  assert.equal(req.url, "https://abc.example/v1/capabilities/tutor.ask?x=1");
  assert.equal(req.headers.get("origin"), "https://o.example");
  assert.equal(req.headers.get("authorization"), "Bearer p");
  assert.equal(req.headers.get("connection"), null);
  assert.equal(await req.text(), "{}");
  const get = toRequest({ method: "GET", url: "/v1/ping", headers: { host: "abc.example" } }, Buffer.from("ignored"));
  assert.equal(await get.text(), "");
});

test("读请求体：最多读 4097 字节", async () => {
  const big = Readable.from([Buffer.alloc(3000, 97), Buffer.alloc(3000, 98)]);
  assert.equal((await readBody(big)).length, 4097);
  const small = Readable.from([Buffer.from("abc")]);
  assert.equal((await readBody(small)).toString(), "abc");
});

test("转换：标准 Response → http 响应", async () => {
  const written = {};
  const fakeRes = {
    writeHead(status, headers) {
      written.status = status;
      written.headers = headers;
    },
    end(buf) {
      written.body = buf.toString();
    },
  };
  await writeResponse(fakeRes, new Response('{"a":1}', { status: 429, headers: { "Retry-After": "10", Vary: "Origin" } }));
  assert.equal(written.status, 429);
  assert.equal(written.headers["retry-after"], "10");
  assert.equal(written.headers["vary"], "Origin");
  assert.equal(written.headers["content-length"], "7");
  assert.equal(written.body, '{"a":1}');
});

test("整条链路：本机起服务，ping 和 OPTIONS 走得通", async () => {
  const env = {
    DEEPSEEK_API_KEY: "sk-test",
    DEEPSEEK_MODEL: "m",
    CURIO_BUCKET: "b-1250000000",
    CURIO_REGION: "ap-guangzhou",
    CURIO_PASSPHRASE_HASH: "0".repeat(64),
    CURIO_SALT: "s",
    CURIO_PRICE_FEN_PER_M: "200,4,800",
  };
  const server = createServer(env);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const ping = await fetch(base + "/v1/ping", { headers: { origin: "https://deepnorth2077.github.io" } });
    assert.equal(ping.status, 200);
    assert.equal(ping.headers.get("access-control-allow-origin"), "https://deepnorth2077.github.io");
    assert.deepEqual(await ping.json(), { service: "curio-relay", version: 1 });
    const pre = await fetch(base + "/v1/usage", { method: "OPTIONS", headers: { origin: "https://deepnorth2077.github.io" } });
    assert.equal(pre.status, 204);
    assert.equal(pre.headers.get("access-control-allow-headers"), "authorization, content-type");
    const big = await fetch(base + "/v1/capabilities/tutor.ask", { method: "POST", body: "x".repeat(10000) });
    assert.equal(big.status, 413);
  } finally {
    await new Promise((r) => server.close(r));
  }
});

test("COS 存储：超过 4 秒就放弃，原因里写着超时", async () => {
  const slow = (url, init) =>
    new Promise((resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(init.signal.reason));
    });
  const s = makeCosStorage({ ...cosOpts, fetchImpl: slow, timeoutMs: 20 });
  const keep = setTimeout(() => {}, 1000);
  try {
    await assert.rejects(() => s.get("usage/2026-11.json"), /COS GET 超时/);
  } finally {
    clearTimeout(keep);
  }
});

test("COS 存储：默认超时是 4 秒", async () => {
  let seen;
  const f = async (url, init) => {
    seen = init.signal;
    return new Response("", { status: 404 });
  };
  const { COS_TIMEOUT_MS } = await import("../adapters/tencent.js");
  assert.equal(COS_TIMEOUT_MS, 4000);
  await makeCosStorage({ ...cosOpts, fetchImpl: f }).get("x");
  assert.ok(seen instanceof AbortSignal);
});

test("读请求体：客户端中途断开就 reject", async () => {
  const req = new PassThrough();
  const p = readBody(req);
  req.write("{\"question\":");
  req.emit("aborted");
  req.emit("close");
  await assert.rejects(p, /断开/);
  const req2 = new PassThrough();
  const p2 = readBody(req2);
  req2.write("abc");
  req2.emit("close");
  await assert.rejects(p2, /断开/);
});

test("整条链路：客户端发了一半就断开，服务不崩，还能接着处理下一个请求", async () => {
  const env = {
    DEEPSEEK_API_KEY: "sk-test",
    DEEPSEEK_MODEL: "m",
    CURIO_BUCKET: "b-1250000000",
    CURIO_REGION: "ap-guangzhou",
    CURIO_PASSPHRASE_HASH: "0".repeat(64),
    CURIO_SALT: "s",
    CURIO_PRICE_FEN_PER_M: "200,4,800",
  };
  const server = createServer(env);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const port = server.address().port;
  const origErr = console.error;
  const logs = [];
  console.error = (...a) => logs.push(a.join(" "));
  try {
    await new Promise((resolve) => {
      const sock = net.connect(port, "127.0.0.1", () => {
        sock.write("POST /v1/capabilities/tutor.ask HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{\"question\":");
        setTimeout(() => {
          sock.destroy();
          resolve();
        }, 30);
      });
    });
    await new Promise((r) => setTimeout(r, 50));
    const ping = await fetch(`http://127.0.0.1:${port}/v1/ping`);
    assert.equal(ping.status, 200);
    assert.ok(logs.some((l) => l.includes("断开")));
  } finally {
    console.error = origErr;
    await new Promise((r) => server.close(r));
  }
});

test("Web 函数的固定值：端口 9000、监听 0.0.0.0、DeepSeek 超时 15 秒", () => {
  assert.equal(PORT, 9000);
  assert.equal(LISTEN_HOST, "0.0.0.0");
  assert.equal(UPSTREAM_TIMEOUT_MS, 15000);
});

test("makeDeps：临时密钥的 token 放进 x-cos-security-token；DeepSeek 密钥去掉首尾空白", async () => {
  const calls = [];
  const f = async (url, init) => {
    calls.push({ url, init });
    return new Response(url.includes("deepseek") ? '{"choices":[]}' : '{"times":[]}', { status: 200 });
  };
  const deps = makeDeps({
    CURIO_BUCKET: "curio-test-1250000000",
    CURIO_REGION: "ap-guangzhou",
    TENCENTCLOUD_SECRETID: "AKIDtest",
    TENCENTCLOUD_SECRETKEY: "keytest",
    TENCENTCLOUD_SESSIONTOKEN: "token-from-env",
    DEEPSEEK_API_KEY: "  sk-abc\n",
  }, f);
  await deps.storage.get("auth/failures.json");
  const h = new Headers(calls[0].init.headers);
  assert.equal(h.get("x-cos-security-token"), "token-from-env");
  await deps.upstream({ model: "m", messages: [] });
  assert.equal(new Headers(calls[1].init.headers).get("authorization"), "Bearer sk-abc");
});

test("临时密钥：Web 函数从 X-Scf-* 请求头拿，没有再用环境变量", () => {
  const env = { TENCENTCLOUD_SECRETID: "env-id", TENCENTCLOUD_SECRETKEY: "env-key", TENCENTCLOUD_SESSIONTOKEN: "env-token" };
  assert.deepEqual(credsFrom({ "x-scf-secret-id": "h-id", "x-scf-secret-key": "h-key", "x-scf-session-token": "h-token" }, env),
    { secretId: "h-id", secretKey: "h-key", sessionToken: "h-token" });
  assert.deepEqual(credsFrom({}, env), { secretId: "env-id", secretKey: "env-key", sessionToken: "env-token" });
  assert.equal(credsFrom({}, {}).secretId, undefined);
});

test("x-scf-* 请求头不交给 handle", () => {
  const r = toRequest({ method: "GET", url: "/v1/ping", headers: { host: "h", "x-scf-secret-key": "k", "X-Scf-Session-Token": "t", origin: "o" } });
  assert.equal(r.headers.get("x-scf-secret-key"), null);
  assert.equal(r.headers.get("x-scf-session-token"), null);
  assert.equal(r.headers.get("origin"), "o");
});

test("整条链路：环境变量里没有临时密钥，请求头里有，照样能读写 COS", async () => {
  const env = {
    DEEPSEEK_API_KEY: "sk-test",
    DEEPSEEK_MODEL: "m",
    CURIO_BUCKET: "b-1250000000",
    CURIO_REGION: "ap-guangzhou",
    CURIO_PASSPHRASE_HASH: "a7745af11e674ef4d55476be509fb4710fa9b08d58dc83ebef0af62440a4ad2a", // sha256("s" + "pw pw")
    CURIO_SALT: "s",
    CURIO_PRICE_FEN_PER_M: "200,4,800",
  };
  const cos = [];
  const f = async (url, init) => {
    if (url.includes("deepseek")) {
      return new Response(JSON.stringify({ choices: [{ message: { content: "回答" } }], usage: { completion_tokens: 1 } }), { status: 200 });
    }
    cos.push({ url, headers: new Headers(init.headers), method: init.method });
    return new Response("", { status: init.method === "GET" ? 404 : 200 });
  };
  const server = createServer(env, f);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const res = await fetch(base + "/v1/capabilities/tutor.ask", {
      method: "POST",
      headers: {
        authorization: "Bearer pw pw",
        "content-type": "application/json",
        "x-scf-secret-id": "AKIDweb",
        "x-scf-secret-key": "webkey",
        "x-scf-session-token": "webtoken",
      },
      body: JSON.stringify({ question: "为什么？", age_band: "G3-4" }),
    });
    assert.equal(res.status, 200);
    assert.ok(cos.length >= 2);
    for (const c of cos) {
      assert.equal(c.headers.get("x-cos-security-token"), "webtoken");
      assert.ok(c.headers.get("authorization").includes("q-ak=AKIDweb&"));
    }
  } finally {
    await new Promise((r) => server.close(r));
  }
});

test("找不到临时密钥时的诊断：只列名字，不写值", () => {
  const d = credsDiagnosis({ "x-scf-request-id": "r1", "x-scf-appid": "125", authorization: "Bearer secret" }, { TENCENTCLOUD_SECRETID: "id-value" });
  assert.ok(d.includes("x-scf-appid, x-scf-request-id"));
  assert.ok(d.includes("TENCENTCLOUD_SECRETID：有"));
  assert.ok(d.includes("TENCENTCLOUD_SECRETKEY：没有"));
  for (const v of ["r1", "125", "secret", "id-value"]) assert.ok(!d.includes(v), v);
  assert.ok(credsDiagnosis({}, {}).includes("一个都没有"));
});
