// 腾讯云 Web 函数的适配层：只做转换，不含规则（规则全在 src/handler.js）。
//
// 怎么启动：腾讯云 Web 函数启动时执行代码包根目录下的 scf_bootstrap，
// 它用 Node.js 运行这个文件；这里用 Node 内置的 http 监听 0.0.0.0:9000，
// 把每个请求转成标准 Request，交给 handle，再把 Response 写回去。
//
// deps.storage：COS 的 XML API（GET/PUT Object），自己按 COS 请求签名算法签名
//   （q-sign-algorithm=sha1，HMAC-SHA1；文档：腾讯云对象存储「请求签名」，
//   https://cloud.tencent.com/document/product/436/7778）。凭证是云函数运行角色给的临时密钥：
//   环境变量 TENCENTCLOUD_SECRETID、TENCENTCLOUD_SECRETKEY、TENCENTCLOUD_SESSIONTOKEN，
//   令牌放在请求头 x-cos-security-token 里。
// deps.upstream：全局 fetch 调 DeepSeek，15 秒超时就抛错。
// 不引入任何 npm 依赖。需要 Node.js 18 或更新（全局 fetch、Request、Response、AbortSignal.timeout）。

import http from "node:http";
import { createHash, createHmac } from "node:crypto";
import { pathToFileURL } from "node:url";
import { handle } from "../src/handler.js";

export const PORT = 9000;
export const LISTEN_HOST = "0.0.0.0";
export const DEEPSEEK_URL = "https://api.deepseek.com/chat/completions";
export const UPSTREAM_TIMEOUT_MS = 15000;
// 适配层最多读这么多字节的请求体；多一个字节就足够让 handle 判断「超过 4 KiB」。
export const BODY_READ_LIMIT = 4097;
// COS 单次请求最多等这么久。函数执行超时是 20 秒，DeepSeek 占 15 秒，留给存储的不多。
export const COS_TIMEOUT_MS = 4000;
const SKIP_HEADERS = new Set(["host", "connection", "content-length", "transfer-encoding", "keep-alive", "upgrade", "expect"]);

// ---------- COS 请求签名 ----------

// COS 文档的编码规则：UTF-8 后，除字母、数字和 - _ . ~ 以外都要百分号编码（大写十六进制）。
export function cosEncode(s) {
  return encodeURIComponent(String(s)).replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());
}

function sha1Hex(s) {
  return createHash("sha1").update(s, "utf8").digest("hex");
}

function hmacSha1Hex(key, msg) {
  return createHmac("sha1", key).update(msg, "utf8").digest("hex");
}

function pairs(obj) {
  const list = Object.entries(obj || {}).map(([k, v]) => [cosEncode(String(k).toLowerCase()), cosEncode(String(v))]);
  list.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return {
    keyList: list.map(([k]) => k).join(";"),
    str: list.map(([k, v]) => `${k}=${v}`).join("&"),
  };
}

// 按 COS「请求签名」文档逐步算 Authorization。
// method：GET/PUT；path：请求路径（未编码，以 / 开头）；params、headers：要签进去的查询参数和请求头。
// startSec、endSec：签名有效期（Unix 秒）。返回 {authorization, keyTime, signKey, httpString, stringToSign, signature}。
export function cosSign({ secretId, secretKey, method, path, params = {}, headers = {}, startSec, endSec }) {
  const keyTime = `${startSec};${endSec}`;
  const signKey = hmacSha1Hex(secretKey, keyTime);
  const p = pairs(params);
  const h = pairs(headers);
  const httpString = `${method.toLowerCase()}\n${path}\n${p.str}\n${h.str}\n`;
  const stringToSign = `sha1\n${keyTime}\n${sha1Hex(httpString)}\n`;
  const signature = hmacSha1Hex(signKey, stringToSign);
  const authorization = [
    "q-sign-algorithm=sha1",
    `q-ak=${secretId}`,
    `q-sign-time=${keyTime}`,
    `q-key-time=${keyTime}`,
    `q-header-list=${h.keyList}`,
    `q-url-param-list=${p.keyList}`,
    `q-signature=${signature}`,
  ].join("&");
  return { authorization, keyTime, signKey, httpString, stringToSign, signature };
}

// 存储：get(key) → 字符串或 null（404），put(key, 字符串)。别的失败一律抛错，由 handle 回 500 并写日志。
// fetchImpl、nowMs 可以换掉，方便不联网测试。
export function makeCosStorage({ bucket, region, secretId, secretKey, sessionToken, fetchImpl = globalThis.fetch, nowMs = () => Date.now(), timeoutMs = COS_TIMEOUT_MS }) {
  const host = `${bucket}.cos.${region}.myqcloud.com`;
  async function send(method, key, body) {
    if (!secretId || !secretKey) throw new Error("没有临时密钥（函数没有绑定运行角色）");
    const path = "/" + key;
    const start = Math.floor(nowMs() / 1000) - 60;
    const { authorization } = cosSign({ secretId, secretKey, method, path, headers: { host }, startSec: start, endSec: start + 660 });
    const headers = { Authorization: authorization };
    if (sessionToken) headers["x-cos-security-token"] = sessionToken;
    if (body !== undefined) headers["Content-Type"] = "application/json; charset=utf-8";
    const url = `https://${host}/` + key.split("/").map(encodeURIComponent).join("/");
    try {
      return await fetchImpl(url, { method, headers, body, signal: AbortSignal.timeout(timeoutMs) });
    } catch (e) {
      // 原因不含秘密，handle 会把它写进日志
      throw new Error(e && e.name === "TimeoutError" ? `COS ${method} 超时（${timeoutMs / 1000} 秒）` : `COS ${method} 连不上`);
    }
  }
  return {
    async get(key) {
      const res = await send("GET", key);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`COS GET ${res.status}`);
      return await res.text();
    },
    async put(key, value) {
      const res = await send("PUT", key, value);
      if (!res.ok) throw new Error(`COS PUT ${res.status}`);
    },
  };
}

// ---------- DeepSeek ----------

export function makeUpstream({ apiKey, fetchImpl = globalThis.fetch, timeoutMs = UPSTREAM_TIMEOUT_MS }) {
  return async function upstream(body) {
    const res = await fetchImpl(DEEPSEEK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
    let json = null;
    try {
      json = JSON.parse(await res.text());
    } catch (e) {
      json = null;
    }
    return { status: res.status, json };
  };
}

// ---------- http ↔ Request / Response ----------

// 读请求体，最多读 limit 个字节（多出的丢掉；handle 看到超过 4096 就回 413）。
export function readBody(req, limit = BODY_READ_LIMIT) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    let ended = false;
    req.on("data", (c) => {
      if (size >= limit) return;
      const take = c.subarray(0, limit - size);
      chunks.push(take);
      size += take.length;
    });
    req.on("end", () => {
      ended = true;
      resolve(Buffer.concat(chunks));
    });
    req.on("error", reject);
    // 客户端中途断开：不再等，交给调用方丢掉这个请求。
    req.on("aborted", () => reject(new Error("客户端断开了")));
    req.on("close", () => {
      if (!ended) reject(new Error("客户端断开了"));
    });
  });
}

export function toRequest({ method, url, headers }, body) {
  const h = new Headers();
  for (const [k, v] of Object.entries(headers || {})) {
    if (v === undefined || SKIP_HEADERS.has(k.toLowerCase())) continue;
    h.set(k, Array.isArray(v) ? v.join(", ") : String(v));
  }
  const host = (headers && headers.host) || "localhost";
  const m = (method || "GET").toUpperCase();
  const init = { method: m, headers: h };
  if (m !== "GET" && m !== "HEAD" && body && body.length) init.body = body;
  return new Request(`https://${host}${url || "/"}`, init);
}

export async function writeResponse(res, response) {
  const headers = {};
  response.headers.forEach((v, k) => {
    headers[k] = v;
  });
  const buf = Buffer.from(await response.arrayBuffer());
  if (buf.length) headers["content-length"] = String(buf.length);
  res.writeHead(response.status, headers);
  res.end(buf);
}

export function makeDeps(env = process.env, fetchImpl = globalThis.fetch) {
  return {
    storage: makeCosStorage({
      fetchImpl,
      bucket: env.CURIO_BUCKET,
      region: env.CURIO_REGION,
      secretId: env.TENCENTCLOUD_SECRETID,
      secretKey: env.TENCENTCLOUD_SECRETKEY,
      sessionToken: env.TENCENTCLOUD_SESSIONTOKEN,
    }),
    // 密钥粘贴时常带上换行或空格，放进请求头会出错，这里去掉首尾空白
    upstream: makeUpstream({ apiKey: String(env.DEEPSEEK_API_KEY || "").trim(), fetchImpl }),
    now: () => Date.now(),
  };
}

export function createServer(env = process.env) {
  return http.createServer(async (req, res) => {
    let body;
    try {
      body = await readBody(req);
    } catch (e) {
      // 客户端已经走了，没有人收响应，什么也不做
      console.error("[curio-relay] 请求没收完，客户端断开了");
      res.destroy();
      return;
    }
    try {
      // 临时密钥会轮换，每个请求重新读环境变量。
      const response = await handle(toRequest(req, body), env, makeDeps(env));
      await writeResponse(res, response);
    } catch (e) {
      console.error("[curio-relay] 适配层出错：" + (e && e.name ? e.name : "Error"));
      if (!res.headersSent) res.writeHead(500, { "content-type": "application/json; charset=utf-8", vary: "Origin" });
      res.end('{"error":"misconfigured"}');
    }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  createServer().listen(PORT, LISTEN_HOST, () => console.log(`[curio-relay] 在 ${LISTEN_HOST}:${PORT} 上等请求`));
}
