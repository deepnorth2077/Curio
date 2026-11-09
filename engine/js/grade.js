// 判分（竖切片 1 规格第 5 节；内容规格 3.3）。纯函数，不改传进来的 answer。
import { numberOk } from "../../kernel/js/validate.js";

/** @typedef {{correct: boolean, misconception: string|null}} Grade */

/** 规整时去掉的 7 种空白：U+0009、U+000A、U+000B、U+000C、U+000D、U+0020、U+3000。 */
const WS = new Set(["\t", "\n", "\u000b", "\f", "\r", " ", "　"]);

/**
 * 规整作答：去掉首尾的 7 种空白；全角数字、全角斜杠、全角小数点换成半角。
 * @param {string} s
 * @returns {string}
 */
export function normalize(s) {
  const cs = [...String(s)];
  let i = 0, j = cs.length;
  while (i < j && WS.has(cs[i])) i++;
  while (j > i && WS.has(cs[j - 1])) j--;
  return cs.slice(i, j).map((c) => {
    const cp = /** @type {number} */ (c.codePointAt(0));
    if (cp >= 0xff10 && cp <= 0xff19) return String.fromCharCode(cp - 0xff10 + 0x30);
    if (c === "／") return "/";
    if (c === "．") return ".";
    return c;
  }).join("");
}

const RESP_NUMBER = /^(-?)([0-9]{1,9})(?:\.([0-9]{1,6}))?$/;
const RESP_SLASH = /^([0-9]{1,6}) *\/ *([0-9]{1,6})$/;
const RESP_FENZHI = /^([0-9]{1,6}) *分之 *([0-9]{1,6})$/;
const MICRO = 6;

/**
 * 活动里的数换成「百万分之一」为单位的整数（BigInt）：按它的最短十进制表示、带指数解析。
 * 不满足数值规则（小数超过 6 位、绝对值不小于 10^9）时抛错。
 * @param {unknown} x
 * @returns {bigint}
 */
export function microOf(x) {
  if (typeof x !== "number" || !numberOk(x) || Math.abs(x) >= 1e9) throw new RangeError(`活动里的数不在范围内：${String(x)}`);
  const m = /^(-?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/.exec(String(x));
  if (!m) throw new RangeError(`认不出这个数：${String(x)}`);
  const frac = m[3] || "";
  const k = (m[4] ? Number(m[4]) : 0) - frac.length + MICRO;
  let v = BigInt(m[2] + frac);
  if (k >= 0) v *= 10n ** BigInt(k);
  else {
    const d = 10n ** BigInt(-k);
    if (v % d !== 0n) throw new RangeError(`小数超过 6 位：${String(x)}`);
    v /= d;
  }
  return m[1] ? -v : v;
}

/** @param {string} s 已匹配 RESP_NUMBER @returns {bigint|null} */
function microOfResponse(s) {
  const m = RESP_NUMBER.exec(s);
  if (!m) return null;
  const v = BigInt(m[2]) * 10n ** BigInt(MICRO) + BigInt((m[3] || "").padEnd(MICRO, "0"));
  return m[1] ? -v : v;
}

const abs = (v) => (v < 0n ? -v : v);

/**
 * 分数作答 a/b 或 b分之a → [a, b]；认不出时 null。
 * @param {string} s
 * @returns {[bigint, bigint]|null}
 */
function parseFraction(s) {
  let m = RESP_SLASH.exec(s);
  if (m) return [BigInt(m[1]), BigInt(m[2])];
  m = RESP_FENZHI.exec(s);
  if (m) return [BigInt(m[2]), BigInt(m[1])];
  return null;
}

/** @param {unknown} n @returns {bigint} */
function intOf(n) {
  if (typeof n !== "number" || !Number.isSafeInteger(n)) throw new RangeError(`分数里要整数：${String(n)}`);
  return BigInt(n);
}

const wrong = (misconception = null) => ({ correct: false, misconception });

/**
 * 判分。
 * @param {any} answer 活动文件里的 answer 对象
 * @param {string} response 孩子的作答
 * @returns {Grade}
 */
export function grade(answer, response) {
  const r = normalize(typeof response === "string" ? response : "");
  if (!answer || typeof answer !== "object") throw new TypeError("answer 不是对象");
  if (answer.type === "choice") {
    const c = (answer.choices || []).find((x) => x.id === r);
    if (!c) return wrong();
    if (c.correct === true) return { correct: true, misconception: null };
    return wrong(typeof c.misconception === "string" ? c.misconception : null);
  }
  if (answer.type === "number") {
    const V = microOf(answer.value);
    const T = answer.tolerance === undefined ? 0n : microOf(answer.tolerance);
    const cws = (answer.common_wrong || []).map((w) => [microOf(w.value), w]);
    const X = microOfResponse(r);
    if (X === null) return wrong();
    if (abs(X - V) <= T) return { correct: true, misconception: null };
    for (const [W, w] of cws) if (abs(X - W) <= T) return wrong(typeof w.misconception === "string" ? w.misconception : null);
    return wrong();
  }
  if (answer.type === "fraction") {
    const eq = answer.accept_equivalent === true;
    const N = intOf(answer.numerator), D = intOf(answer.denominator);
    const cws = (answer.common_wrong || []).map((w) => [intOf(w.numerator), intOf(w.denominator), w]);
    const f = parseFraction(r);
    if (!f) return wrong();
    const [a, b] = f;
    if (b === 0n) return wrong();
    const same = (n, d) => (eq ? a * d === n * b : a === n && b === d);
    if (same(N, D)) return { correct: true, misconception: null };
    for (const [n, d, w] of cws) if (same(n, d)) return wrong(typeof w.misconception === "string" ? w.misconception : null);
    return wrong();
  }
  throw new TypeError(`不认识的答案类型：${String(answer.type)}`);
}

/**
 * 检查一个答案里的数都在范围内（startQuiz 用）。不满足时抛错。
 * @param {any} answer
 */
export function checkAnswerNumbers(answer) {
  if (answer.type === "number") {
    microOf(answer.value);
    if (answer.tolerance !== undefined && microOf(answer.tolerance) < 0n) throw new RangeError("tolerance 不能是负数");
    for (const w of answer.common_wrong || []) microOf(w.value);
  } else if (answer.type === "fraction") {
    intOf(answer.numerator);
    if (intOf(answer.denominator) === 0n) throw new RangeError("分母不能是 0");
    for (const w of answer.common_wrong || []) { intOf(w.numerator); intOf(w.denominator); }
  }
}
