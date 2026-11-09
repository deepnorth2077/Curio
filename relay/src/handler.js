// Curio AI 中转服务的全部规则（docs/specs/relay.md 第 2～4 节）。
// handle(request, env, deps) → Response。不绑平台：平台适配层把请求转成标准 Request，
// 把 deps（storage、upstream、now）传进来。这里不读时钟、不联网、不打印问题和回答。

import { createHash, timingSafeEqual } from "node:crypto";
import { buildMessages, MAX_TOKENS } from "./navigator.js";

const DEFAULT_ORIGINS = "https://deepnorth2077.github.io";
const DEFAULT_DAILY_CALLS = 30;
const DEFAULT_MONTHLY_FEN = 2000;
const MAX_BODY_BYTES = 4096;
const LOCK_WINDOW_MS = 1800 * 1000;
const LOCK_THRESHOLD = 10;
const MAX_FAILURES_KEPT = 10;
const UFEN_PER_FEN = 1000000;
const LOCAL_OFFSET_MS = 8 * 3600 * 1000; // UTC+8
const AGE_BANDS = new Set(["G1-2", "G3-4", "G5-6", "G7-9", "G10-12"]);
const FAILURES_KEY = "auth/failures.json";

const ROUTES = {
  "/v1/ping": "GET",
  "/v1/capabilities/tutor.ask": "POST",
  "/v1/usage": "GET",
};

// ---------- 日期：纯函数，UTC 字段加 8 小时 ----------

function pad(n) {
  return String(n).padStart(2, "0");
}

export function localParts(ms) {
  const d = new Date(ms + LOCAL_OFFSET_MS);
  return { y: d.getUTCFullYear(), m: d.getUTCMonth(), d: d.getUTCDate() };
}

export function localDay(ms) {
  const p = localParts(ms);
  return `${p.y}-${pad(p.m + 1)}-${pad(p.d)}`;
}

export function localMonth(ms) {
  const p = localParts(ms);
  return `${p.y}-${pad(p.m + 1)}`;
}

// 本地第二天 0 点（毫秒时间戳）
export function nextLocalMidnight(ms) {
  const p = localParts(ms);
  return Date.UTC(p.y, p.m, p.d + 1) - LOCAL_OFFSET_MS;
}

// 本地下个月 1 日 0 点（毫秒时间戳）
export function nextLocalMonthStart(ms) {
  const p = localParts(ms);
  return Date.UTC(p.y, p.m + 1, 1) - LOCAL_OFFSET_MS;
}

function secondsUntil(target, now) {
  return Math.max(1, Math.ceil((target - now) / 1000));
}

// ---------- 配置和启动时自检 ----------

const NON_NEG_INT = /^\d+$/;
// 每天次数、每月上限：正整数，最多 9 位（填 0 等于永远不能问，日志里却看不出原因）
const POS_INT = /^[1-9]\d{0,8}$/;

function blank(v) {
  return v === undefined || v === null || String(v).trim() === "";
}

// 返回 {config} 或 {problem: 给日志的人话}。日志里不出现密钥、哈希、盐的值。
export function readConfig(env) {
  const e = env || {};
  const problems = [];
  if (blank(e.DEEPSEEK_API_KEY)) problems.push("DEEPSEEK_API_KEY 没填（部署手册第 3 步建密钥，第 8 步填进环境变量）");
  if (blank(e.DEEPSEEK_MODEL)) problems.push("DEEPSEEK_MODEL 没填（部署手册第 8 步）");
  if (blank(e.CURIO_BUCKET)) problems.push("CURIO_BUCKET 没填（部署手册第 5 步建桶，第 8 步填桶名）");
  if (blank(e.CURIO_REGION)) problems.push("CURIO_REGION 没填（部署手册第 5 步记下地域，第 8 步填进去）");
  if (typeof e.CURIO_PASSPHRASE_HASH !== "string" || !/^[0-9a-f]{64}$/.test(e.CURIO_PASSPHRASE_HASH)) {
    problems.push("CURIO_PASSPHRASE_HASH 不是 64 位小写十六进制（用部署手册第 4 步的小网页重新生成，整行复制，第 8 步粘贴）");
  }
  if (blank(e.CURIO_SALT)) problems.push("CURIO_SALT 没填（部署手册第 4 步的小网页生成，第 8 步粘贴）");

  let prices = null;
  const parts = typeof e.CURIO_PRICE_FEN_PER_M === "string" ? e.CURIO_PRICE_FEN_PER_M.split(",").map((s) => s.trim()) : [];
  if (parts.length === 3 && parts.every((s) => NON_NEG_INT.test(s))) prices = parts.map((s) => Number(s));
  else problems.push("CURIO_PRICE_FEN_PER_M 要写三个非负整数、用逗号分开，例如 200,4,800（部署手册第 8 步）");

  const intOrDefault = (name, def) => {
    const v = e[name];
    if (blank(v)) return def;
    const s = String(v).trim();
    if (!POS_INT.test(s)) {
      problems.push(`${name} 要写一个正整数（不能是 0），或者删掉这一项用默认值（部署手册第 8 步）`);
      return def;
    }
    return Number(s);
  };
  const dailyCalls = intOrDefault("CURIO_DAILY_CALLS", DEFAULT_DAILY_CALLS);
  const monthlyFen = intOrDefault("CURIO_MONTHLY_FEN", DEFAULT_MONTHLY_FEN);

  const originsRaw = blank(e.CURIO_ALLOWED_ORIGINS) ? DEFAULT_ORIGINS : String(e.CURIO_ALLOWED_ORIGINS);
  const origins = originsRaw.split(",").map((s) => s.trim()).filter(Boolean);

  if (problems.length) return { problem: problems.join("；") };
  return {
    config: {
      apiKey: e.DEEPSEEK_API_KEY,
      model: String(e.DEEPSEEK_MODEL).trim(),
      hash: e.CURIO_PASSPHRASE_HASH,
      salt: e.CURIO_SALT,
      prices,
      dailyCalls,
      monthlyFen,
      origins,
    },
  };
}

function allowedOrigins(env) {
  const raw = env && !blank(env.CURIO_ALLOWED_ORIGINS) ? String(env.CURIO_ALLOWED_ORIGINS) : DEFAULT_ORIGINS;
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

// ---------- 响应 ----------

function corsHeaders(request, env) {
  const h = new Headers({ Vary: "Origin" });
  const origin = request.headers.get("origin");
  if (origin && allowedOrigins(env).includes(origin)) {
    h.set("Access-Control-Allow-Origin", origin);
    // 不加这一行，浏览器里的页面读不到 Retry-After，就没法显示「还要等多久」。
    h.set("Access-Control-Expose-Headers", "Retry-After");
  }
  return h;
}

function json(request, env, status, body, extra = {}) {
  const h = corsHeaders(request, env);
  h.set("Content-Type", "application/json; charset=utf-8");
  for (const [k, v] of Object.entries(extra)) h.set(k, String(v));
  return new Response(JSON.stringify(body), { status, headers: h });
}

function err(request, env, status, code, extra) {
  return json(request, env, status, { error: code }, extra);
}

// ---------- 口令 ----------

function sha256Hex(s) {
  return createHash("sha256").update(s, "utf8").digest("hex");
}

// 定长比较：两边都是 64 位十六进制（自检保证了配置那一边）。
export function passphraseMatches(header, salt, expectedHash) {
  if (typeof header !== "string") return false;
  const m = /^bearer (.+)$/is.exec(header);
  if (!m) return false;
  const enc = new TextEncoder();
  const got = enc.encode(sha256Hex(salt + m[1]));
  const want = enc.encode(expectedHash);
  if (got.length !== want.length) return false;
  return timingSafeEqual(got, want);
}

// ---------- 存储 ----------

// 存储出错。reason 是适配层给的原因（例如「COS GET 403」「没有临时密钥」），不含秘密；
// badFile 表示读到了，但内容坏了。
class StorageError extends Error {
  constructor(message, badFile = null) {
    super(message);
    this.badFile = badFile;
  }
}

function reasonOf(e) {
  const m = e && typeof e.message === "string" && e.message ? e.message : e && e.name ? e.name : "未知原因";
  return m.slice(0, 200);
}

function badFile(key, what) {
  return new StorageError(`${key} 的内容坏了（${what}）。到 COS 控制台打开这个桶，删掉 ${key} 这个文件，中转服务会重新建一个`, key);
}

async function readJson(storage, key) {
  let raw;
  try {
    raw = await storage.get(key);
  } catch (e) {
    throw new StorageError(`读 ${key} 失败：${reasonOf(e)}`);
  }
  if (raw === null || raw === undefined) return null;
  try {
    return JSON.parse(raw);
  } catch (e) {
    throw badFile(key, "不是合法的 JSON");
  }
}

async function writeJson(storage, key, value) {
  try {
    await storage.put(key, JSON.stringify(value));
  } catch (e) {
    throw new StorageError(`写 ${key} 失败：${reasonOf(e)}`);
  }
}

const isNonNegInt = (v) => Number.isSafeInteger(v) && v >= 0;
const isPlainObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

// 失败记录：{times: [数字…]}。格式不对就抛 badFile。返回窗口里的、从早到晚排好的记录。
async function readFailures(storage, now) {
  const obj = await readJson(storage, FAILURES_KEY);
  if (obj === null) return { times: [], hadRecords: false };
  if (!isPlainObject(obj) || !Array.isArray(obj.times) || !obj.times.every((t) => typeof t === "number" && Number.isFinite(t))) {
    throw badFile(FAILURES_KEY, "times 要是一串数字");
  }
  const times = obj.times.filter((t) => now - t < LOCK_WINDOW_MS).sort((a, b) => a - b);
  return { times, hadRecords: obj.times.length > 0 };
}

// 用量：{calls_by_day: {日期: 非负整数}, cost_ufen: 非负整数}。没有文件就是空的；格式不对就抛 badFile。
async function readUsage(storage, key) {
  const obj = await readJson(storage, key);
  if (obj === null) return { calls_by_day: {}, cost_ufen: 0 };
  if (!isPlainObject(obj) || !isPlainObject(obj.calls_by_day) || !Object.values(obj.calls_by_day).every(isNonNegInt)) {
    throw badFile(key, "calls_by_day 的每个值要是非负整数");
  }
  if (!isNonNegInt(obj.cost_ufen)) throw badFile(key, "cost_ufen 要是非负整数");
  return { calls_by_day: { ...obj.calls_by_day }, cost_ufen: obj.cost_ufen };
}

function storageLog(e) {
  if (e.badFile) return `[curio-relay] 存储出错：${e.message}`;
  return `[curio-relay] 存储出错：${e.message}。最常见的原因是函数没有绑定能读写这个桶的运行角色：检查部署手册第 6 步（角色和策略）和第 9 步（绑定角色），再看第 8 步里的桶名和地域`;
}

// ---------- 请求校验 ----------

function codePoints(s) {
  return Array.from(s).length;
}

function validateAsk(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return null;
  if (typeof body.question !== "string") return null;
  const question = body.question.trim();
  const n = codePoints(question);
  if (n < 1 || n > 200) return null;
  if (typeof body.age_band !== "string" || !AGE_BANDS.has(body.age_band)) return null;
  let context;
  if (body.context !== undefined) {
    const c = body.context;
    if (c === null || typeof c !== "object" || Array.isArray(c)) return null;
    context = {};
    for (const k of ["node_title", "activity_title"]) {
      if (c[k] === undefined) continue;
      if (typeof c[k] !== "string" || codePoints(c[k]) > 40) return null;
      if (c[k].trim()) context[k] = c[k].trim();
    }
  }
  return { question, age_band: body.age_band, context };
}

// ---------- 花费 ----------

function nonNegInt(v) {
  return Number.isInteger(v) && v >= 0 ? v : 0;
}

// 返回百万分之一分的整数；DeepSeek 没回用量时返回 null。
export function costOf(usage, prices) {
  if (!usage || typeof usage !== "object") return null;
  const hasSplit = usage.prompt_cache_miss_tokens !== undefined || usage.prompt_cache_hit_tokens !== undefined;
  const miss = hasSplit ? nonNegInt(usage.prompt_cache_miss_tokens) : nonNegInt(usage.prompt_tokens);
  const hit = hasSplit ? nonNegInt(usage.prompt_cache_hit_tokens) : 0;
  const out = nonNegInt(usage.completion_tokens);
  return miss * prices[0] + hit * prices[1] + out * prices[2];
}

function fenOf(ufen) {
  return Math.ceil(ufen / UFEN_PER_FEN);
}

// ---------- 主流程 ----------

export async function handle(request, env, deps) {
  const url = new URL(request.url);
  const method = request.method.toUpperCase();

  // 1. OPTIONS 预检
  if (method === "OPTIONS") {
    const h = corsHeaders(request, env);
    if (h.has("Access-Control-Allow-Origin")) {
      h.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
      h.set("Access-Control-Allow-Headers", "authorization, content-type");
      h.set("Access-Control-Max-Age", "600");
    }
    return new Response(null, { status: 204, headers: h });
  }

  // 2. 路由
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const want = ROUTES[path];
  if (!want) return err(request, env, 404, "not_found");
  if (method !== want) return err(request, env, 405, "method_not_allowed");

  // 3. 启动时自检
  const { config, problem } = readConfig(env);
  if (!config) {
    console.error(`[curio-relay] 中转服务的设置填错了：${problem}`);
    return err(request, env, 500, "misconfigured");
  }

  // 4. 请求体大小
  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) return err(request, env, 413, "too_large");
  let bodyText = "";
  if (method === "POST") {
    const buf = new Uint8Array(await request.arrayBuffer());
    if (buf.byteLength > MAX_BODY_BYTES) return err(request, env, 413, "too_large");
    bodyText = new TextDecoder("utf-8").decode(buf);
  }

  if (path === "/v1/ping") return json(request, env, 200, { service: "curio-relay", version: 1 });

  try {
    if (path === "/v1/usage") return await usageRoute(request, env, deps, config);
    return await askRoute(request, env, deps, config, bodyText);
  } catch (e) {
    if (e instanceof StorageError) {
      console.error(storageLog(e));
      return err(request, env, 500, "misconfigured");
    }
    console.error("[curio-relay] 意外错误：" + (e && e.name ? e.name : "Error"));
    return err(request, env, 500, "misconfigured");
  }
}

// 第 2、3 步：锁定和口令。通过返回 null，否则返回要回给页面的 Response。
async function checkAuth(request, env, deps, config, now) {
  const { times, hadRecords } = await readFailures(deps.storage, now);
  if (times.length >= LOCK_THRESHOLD) {
    const unlockAt = times[times.length - LOCK_THRESHOLD] + LOCK_WINDOW_MS;
    return err(request, env, 429, "locked", { "Retry-After": secondsUntil(unlockAt, now), "Cache-Control": "no-store" });
  }
  const ok = passphraseMatches(request.headers.get("authorization"), config.salt, config.hash);
  if (!ok) {
    times.push(now);
    await writeJson(deps.storage, FAILURES_KEY, { times: times.slice(-MAX_FAILURES_KEPT) });
    return err(request, env, 401, "bad_passphrase", { "Cache-Control": "no-store" });
  }
  if (hadRecords) await writeJson(deps.storage, FAILURES_KEY, { times: [] });
  return null;
}

async function usageRoute(request, env, deps, config) {
  const now = deps.now();
  const denied = await checkAuth(request, env, deps, config, now);
  if (denied) return denied;
  const month = localMonth(now);
  const usage = await readUsage(deps.storage, `usage/${month}.json`);
  return json(
    request,
    env,
    200,
    {
      month,
      calls_by_day: usage.calls_by_day,
      fen_month: fenOf(usage.cost_ufen),
      daily_calls: config.dailyCalls,
      monthly_fen: config.monthlyFen,
    },
    { "Cache-Control": "no-store" }
  );
}

async function askRoute(request, env, deps, config, bodyText) {
  // 第 1 步：格式
  let body;
  try {
    body = JSON.parse(bodyText);
  } catch (e) {
    return err(request, env, 400, "bad_request", { "Cache-Control": "no-store" });
  }
  const ask = validateAsk(body);
  if (!ask) return err(request, env, 400, "bad_request", { "Cache-Control": "no-store" });

  // 第 2、3 步：锁定、口令
  const now = deps.now();
  const denied = await checkAuth(request, env, deps, config, now);
  if (denied) return denied;

  // 第 4、5 步：今天的次数、本月花费
  const day = localDay(now);
  const usageKey = `usage/${localMonth(now)}.json`;
  const usage = await readUsage(deps.storage, usageKey);
  const callsToday = usage.calls_by_day[day] || 0;
  if (callsToday >= config.dailyCalls) {
    return err(request, env, 429, "daily_cap", { "Retry-After": secondsUntil(nextLocalMidnight(now), now), "Cache-Control": "no-store" });
  }
  if (usage.cost_ufen >= config.monthlyFen * UFEN_PER_FEN) {
    return err(request, env, 429, "monthly_cap", { "Retry-After": secondsUntil(nextLocalMonthStart(now), now), "Cache-Control": "no-store" });
  }

  // 第 6 步：调用 DeepSeek
  const upstreamBody = {
    model: config.model,
    messages: buildMessages(ask),
    max_tokens: MAX_TOKENS,
    thinking: { type: "disabled" },
    stream: false,
  };
  let res;
  try {
    res = await deps.upstream(upstreamBody);
  } catch (e) {
    console.error("[curio-relay] DeepSeek 超时或连不上");
    return err(request, env, 502, "upstream", { "Cache-Control": "no-store" });
  }
  const status = res && typeof res.status === "number" ? res.status : 0;
  const rjson = res && res.json && typeof res.json === "object" ? res.json : null;
  const cost = costOf(rjson && rjson.usage, config.prices);
  const content = rjson && Array.isArray(rjson.choices) && rjson.choices[0] && rjson.choices[0].message ? rjson.choices[0].message.content : undefined;
  const ok = status >= 200 && status < 300 && typeof content === "string" && content !== "";

  // 记账：调用 DeepSeek 之后、写回之前再读一次用量再加，缩小并发时丢计数的窗口。
  // 这里出错只写日志：钱已经花了，回答（或 502）照样交给页面。
  let after = null;
  const record = async (addCall) => {
    if (cost === null && !addCall) return;
    try {
      const fresh = await readUsage(deps.storage, usageKey);
      if (addCall) fresh.calls_by_day[day] = (fresh.calls_by_day[day] || 0) + 1;
      fresh.cost_ufen += cost || 0;
      await writeJson(deps.storage, usageKey, fresh);
      after = fresh;
    } catch (e) {
      console.error((e instanceof StorageError ? storageLog(e) : "[curio-relay] 记账出错：" + reasonOf(e)) + "。这次的用量没记上");
    }
  };

  if (!ok) {
    await record(false);
    if (status === 402) {
      console.error("[curio-relay] DeepSeek 说余额不足（402），请给 DeepSeek 充值");
      return err(request, env, 502, "no_balance", { "Cache-Control": "no-store" });
    }
    console.error(`[curio-relay] DeepSeek 出错，状态 ${status || "无"}`);
    return err(request, env, 502, "upstream", { "Cache-Control": "no-store" });
  }

  // 第 7 步：成功
  await record(true);
  if (!after) {
    // 没记上：按读到的旧数加上这一次给页面看
    after = { calls_by_day: { ...usage.calls_by_day, [day]: callsToday + 1 }, cost_ufen: usage.cost_ufen + (cost || 0) };
  }
  return json(
    request,
    env,
    200,
    {
      answer: content,
      usage: {
        calls_today: after.calls_by_day[day],
        daily_calls: config.dailyCalls,
        fen_month: fenOf(after.cost_ufen),
        monthly_fen: config.monthlyFen,
      },
    },
    { "Cache-Control": "no-store" }
  );
}
