// handler.js 的补充测试（验收用例之外）：口令比较、日期纯函数、配置自检的日志、花费公式、存储出错。

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  handle,
  passphraseMatches,
  localDay,
  localMonth,
  nextLocalMidnight,
  nextLocalMonthStart,
  readConfig,
  costOf,
} from "../src/handler.js";

const SALT = "s4lt-7f3a";
const HASH = "652689b7a191cb878c3cc03d0a47e4402feef74f8b60e91ed6b31eea836c2585"; // sha256(盐 + "correct horse battery staple")
const ENV = {
  DEEPSEEK_API_KEY: "sk-secret-value-123",
  DEEPSEEK_MODEL: "deepseek-chat",
  CURIO_BUCKET: "curio-test-1250000000",
  CURIO_REGION: "ap-guangzhou",
  CURIO_PASSPHRASE_HASH: HASH,
  CURIO_SALT: SALT,
  CURIO_PRICE_FEN_PER_M: "200,20,800",
};

test("口令：对的通过", () => {
  assert.equal(passphraseMatches("Bearer correct horse battery staple", SALT, HASH), true);
});

test("口令：错的、少一个字、多空格、换盐、不是 Bearer、没有头，都不通过", () => {
  assert.equal(passphraseMatches("Bearer correct horse battery stapl", SALT, HASH), false);
  assert.equal(passphraseMatches("Bearer  correct horse battery staple", SALT, HASH), false);
  assert.equal(passphraseMatches("Bearer correct horse battery staple", "other", HASH), false);
  assert.equal(passphraseMatches("Basic correct horse battery staple", SALT, HASH), false);
  assert.equal(passphraseMatches("Bearer ", SALT, HASH), false);
  assert.equal(passphraseMatches(null, SALT, HASH), false);
});

test("日期：UTC+8 的日期和月份，不看运行环境的时区", () => {
  const t = Date.parse("2026-11-30T15:59:59.999Z");
  assert.equal(localDay(t), "2026-11-30");
  assert.equal(localDay(t + 1), "2026-12-01");
  assert.equal(localMonth(t), "2026-11");
  assert.equal(localMonth(t + 1), "2026-12");
  assert.equal(localMonth(Date.parse("2026-12-31T16:00:00Z")), "2027-01");
  assert.equal(nextLocalMidnight(Date.parse("2026-11-09T13:00:00Z")), Date.parse("2026-11-09T16:00:00Z"));
  assert.equal(nextLocalMonthStart(Date.parse("2026-12-31T15:00:00Z")), Date.parse("2026-12-31T16:00:00Z"));
  assert.equal(nextLocalMonthStart(Date.parse("2026-12-31T16:00:00Z")), Date.parse("2027-01-31T16:00:00Z"));
});

test("日期：换了进程时区结果也一样", () => {
  const old = process.env.TZ;
  try {
    process.env.TZ = "America/Los_Angeles";
    assert.equal(localDay(Date.parse("2026-11-09T16:00:00Z")), "2026-11-10");
  } finally {
    if (old === undefined) delete process.env.TZ;
    else process.env.TZ = old;
  }
});

test("花费：整数公式；缺缓存字段全算未命中；没用量回 null", () => {
  assert.equal(costOf({ prompt_cache_miss_tokens: 1000, prompt_cache_hit_tokens: 500, completion_tokens: 300 }, [200, 20, 800]), 450000);
  assert.equal(costOf({ prompt_tokens: 1000, completion_tokens: 100 }, [200, 20, 800]), 280000);
  assert.equal(costOf(undefined, [1, 1, 1]), null);
});

test("自检：每天次数写成字母也算设置错；空着用默认值", () => {
  assert.ok(readConfig({ ...ENV, CURIO_DAILY_CALLS: "abc" }).problem.includes("CURIO_DAILY_CALLS"));
  assert.equal(readConfig({ ...ENV, CURIO_DAILY_CALLS: "" }).config.dailyCalls, 30);
  assert.equal(readConfig({ ...ENV, CURIO_MONTHLY_FEN: "500" }).config.monthlyFen, 500);
});

test("自检：每天次数、每月上限填 0 或带前导 0 都算设置错", () => {
  for (const v of ["0", "007", "-1", "1.5"]) {
    assert.ok(readConfig({ ...ENV, CURIO_DAILY_CALLS: v }).problem.includes("CURIO_DAILY_CALLS"), v);
    assert.ok(readConfig({ ...ENV, CURIO_MONTHLY_FEN: v }).problem.includes("CURIO_MONTHLY_FEN"), v);
  }
  assert.equal(readConfig({ ...ENV, CURIO_DAILY_CALLS: " 5 " }).config.dailyCalls, 5);
});

test("年龄段：五档都接受，别的不接受", async () => {
  for (const [band, status] of [["G1-2", 200], ["G3-4", 200], ["G5-6", 200], ["G7-9", 200], ["G10-12", 200], ["G13", 400], ["g3-4", 400]]) {
    const deps = memDeps(new Map(), async () => ({ status: 200, json: { choices: [{ message: { content: "回答" } }], usage: { completion_tokens: 1 } } }));
    const req = new Request("https://r.test/v1/capabilities/tutor.ask", {
      method: "POST",
      headers: { authorization: "Bearer correct horse battery staple", "content-type": "application/json" },
      body: JSON.stringify({ question: "为什么？", age_band: band }),
    });
    assert.equal((await handle(req, ENV, deps)).status, status, band);
  }
});

function capture(fn) {
  const logs = [];
  const orig = console.error;
  console.error = (...a) => logs.push(a.map(String).join(" "));
  return Promise.resolve(fn()).finally(() => (console.error = orig)).then((r) => [r, logs]);
}

const memDeps = (store = new Map(), upstream = async () => { throw new Error("不该调用"); }) => ({
  storage: { get: async (k) => (store.has(k) ? store.get(k) : null), put: async (k, v) => void store.set(k, v) },
  upstream,
  now: () => Date.parse("2026-11-09T05:00:00Z"),
});

test("自检的日志：说清哪一项和第几步，不出现密钥、哈希、盐", async () => {
  const env = { ...ENV, CURIO_PASSPHRASE_HASH: HASH.toUpperCase(), CURIO_BUCKET: "" };
  const [res, logs] = await capture(() => handle(new Request("https://r.test/v1/ping"), env, memDeps()));
  assert.equal(res.status, 500);
  const text = logs.join("\n");
  assert.match(text, /CURIO_PASSPHRASE_HASH/);
  assert.match(text, /CURIO_BUCKET/);
  assert.match(text, /第 \d+ 步/);
  for (const secret of [ENV.DEEPSEEK_API_KEY, HASH, HASH.toUpperCase(), SALT]) assert.ok(!text.includes(secret), "日志里出现了秘密");
});

test("存储读不出来：500 misconfigured，日志指向运行角色", async () => {
  const deps = memDeps();
  deps.storage.get = async () => {
    throw new Error("COS GET 403");
  };
  const req = new Request("https://r.test/v1/usage", { headers: { authorization: "Bearer correct horse battery staple" } });
  const [res, logs] = await capture(() => handle(req, ENV, deps));
  assert.equal(res.status, 500);
  assert.deepEqual(await res.json(), { error: "misconfigured" });
  assert.match(logs.join("\n"), /运行角色/);
});

test("成功后存储写不进去：回答照样给页面，日志说一句", async () => {
  const deps = memDeps(new Map(), async () => ({
    status: 200,
    json: { choices: [{ message: { content: "回答" } }], usage: { prompt_tokens: 1, completion_tokens: 1 } },
  }));
  deps.storage.put = async () => {
    throw new Error("COS PUT 403");
  };
  const req = new Request("https://r.test/v1/capabilities/tutor.ask", {
    method: "POST",
    headers: { authorization: "Bearer correct horse battery staple", "content-type": "application/json" },
    body: JSON.stringify({ question: "为什么？", age_band: "G3-4" }),
  });
  const [res, logs] = await capture(() => handle(req, ENV, deps));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).answer, "回答");
  assert.ok(logs.some((l) => l.includes("没记上")));
});

test("声明的 Content-Length 超过 4 KiB 直接 413", async () => {
  const req = new Request("https://r.test/v1/capabilities/tutor.ask", {
    method: "POST",
    headers: { "content-length": "999999" },
    body: "{}",
  });
  const res = await handle(req, ENV, memDeps());
  assert.equal(res.status, 413);
});

test("名单里的来源能读到 Retry-After（Expose-Headers）；名单外的没有", async () => {
  const store = new Map([["usage/2026-11.json", JSON.stringify({ calls_by_day: { "2026-11-09": 30 }, cost_ufen: 0 })]]);
  const mk = (origin) =>
    new Request("https://r.test/v1/capabilities/tutor.ask", {
      method: "POST",
      headers: { origin, authorization: "Bearer correct horse battery staple", "content-type": "application/json" },
      body: JSON.stringify({ question: "为什么？", age_band: "G3-4" }),
    });
  const a = await handle(mk("https://deepnorth2077.github.io"), ENV, memDeps(store));
  assert.equal(a.status, 429);
  assert.equal(a.headers.get("access-control-expose-headers"), "Retry-After");
  const b = await handle(mk("https://evil.example"), ENV, memDeps(store));
  assert.equal(b.headers.get("access-control-expose-headers"), null);
});

test("存储出错的日志带上适配层给的原因", async () => {
  const deps = memDeps();
  deps.storage.get = async () => {
    throw new Error("COS GET 403");
  };
  const req = new Request("https://r.test/v1/usage", { headers: { authorization: "Bearer correct horse battery staple" } });
  const [res, logs] = await capture(() => handle(req, ENV, deps));
  assert.equal(res.status, 500);
  assert.match(logs.join("\n"), /COS GET 403/);
});

for (const [name, key, raw] of [
  ["用量文件不是 JSON", "usage/2026-11.json", "{oops"],
  ["用量文件 cost_ufen 是小数", "usage/2026-11.json", JSON.stringify({ calls_by_day: {}, cost_ufen: 1.5 })],
  ["用量文件某天的次数是负数", "usage/2026-11.json", JSON.stringify({ calls_by_day: { "2026-11-09": -1 }, cost_ufen: 0 })],
  ["用量文件没有 calls_by_day", "usage/2026-11.json", JSON.stringify({ cost_ufen: 0 })],
  ["失败记录 times 里有字符串", "auth/failures.json", JSON.stringify({ times: ["1"] })],
  ["失败记录不是对象", "auth/failures.json", "[]"],
]) {
  test(`存储内容坏了：${name} → 500，日志里有文件名和删掉它`, async () => {
    const req = new Request("https://r.test/v1/usage", { headers: { authorization: "Bearer correct horse battery staple" } });
    const [res, logs] = await capture(() => handle(req, ENV, memDeps(new Map([[key, raw]]))));
    assert.equal(res.status, 500);
    assert.deepEqual(await res.json(), { error: "misconfigured" });
    const text = logs.join("\n");
    assert.ok(text.includes(key), "日志里要有文件名");
    assert.match(text, /删掉/);
  });
}

test("DeepSeek 非 2xx 带用量，但记账写不进去：仍是 502，不是 500", async () => {
  for (const [status, code] of [[402, "no_balance"], [500, "upstream"]]) {
    const deps = memDeps(new Map(), async () => ({ status, json: { usage: { prompt_tokens: 10, completion_tokens: 0 } } }));
    deps.storage.put = async () => {
      throw new Error("COS PUT 403");
    };
    const req = new Request("https://r.test/v1/capabilities/tutor.ask", {
      method: "POST",
      headers: { authorization: "Bearer correct horse battery staple", "content-type": "application/json" },
      body: JSON.stringify({ question: "为什么？", age_band: "G3-4" }),
    });
    const [res, logs] = await capture(() => handle(req, ENV, deps));
    assert.equal(res.status, 502);
    assert.deepEqual(await res.json(), { error: code });
    assert.ok(logs.some((l) => l.includes("没记上")));
  }
});

test("记账前再读一次：调用 DeepSeek 期间别的请求写进去的数不会被覆盖", async () => {
  const store = new Map([["usage/2026-11.json", JSON.stringify({ calls_by_day: { "2026-11-09": 1 }, cost_ufen: 100 })]]);
  const deps = memDeps(store, async () => {
    // DeepSeek 回答期间，另一个请求把用量改成了 2 次、200
    store.set("usage/2026-11.json", JSON.stringify({ calls_by_day: { "2026-11-09": 2 }, cost_ufen: 200 }));
    return { status: 200, json: { choices: [{ message: { content: "答" } }], usage: { prompt_tokens: 1, completion_tokens: 0 } } };
  });
  const req = new Request("https://r.test/v1/capabilities/tutor.ask", {
    method: "POST",
    headers: { authorization: "Bearer correct horse battery staple", "content-type": "application/json" },
    body: JSON.stringify({ question: "为什么？", age_band: "G3-4" }),
  });
  const res = await handle(req, ENV, deps);
  assert.equal(res.status, 200);
  assert.deepEqual(JSON.parse(store.get("usage/2026-11.json")), { calls_by_day: { "2026-11-09": 3 }, cost_ufen: 400 });
  assert.equal((await res.json()).usage.calls_today, 3);
});

test("失败记录里比现在还晚的时间也算（规格没有排除它）", async () => {
  const now = Date.parse("2026-11-09T05:00:00Z");
  const times = Array.from({ length: 10 }, (_, i) => now + 1000 + i);
  const req = new Request("https://r.test/v1/usage", { headers: { authorization: "Bearer correct horse battery staple" } });
  const res = await handle(req, ENV, memDeps(new Map([["auth/failures.json", JSON.stringify({ times })]])));
  assert.equal(res.status, 429);
});
