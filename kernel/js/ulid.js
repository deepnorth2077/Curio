// ULID 生成（事件规格第 1 节）：26 个字符，Crockford Base32 大写，前 10 个字符是 48 位毫秒时间，后 16 个是 80 位随机数。
// 同一毫秒（或时钟倒退）时按 ULID 规范单调递增：沿用上一次的时间，随机部分加一。
// 内核不取时间、不取随机数：两者都由外壳作为参数传进来。

const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const MAX_TIME = 2 ** 48 - 1;

/**
 * 编码一个 ULID。
 * @param {number} ms 0～2^48−1 的整数毫秒
 * @param {Uint8Array|number[]} rand 10 个字节（80 位）
 * @returns {string}
 */
export function encodeUlid(ms, rand) {
  if (!Number.isInteger(ms) || ms < 0 || ms > MAX_TIME) throw new RangeError("ULID 时间超出范围");
  if (!rand || rand.length !== 10) throw new RangeError("ULID 随机部分要 10 个字节");
  let t = "";
  let x = ms;
  for (let i = 0; i < 10; i++) { t = ALPHABET[x % 32] + t; x = Math.floor(x / 32); }
  let n = 0n;
  for (const b of rand) n = (n << 8n) | BigInt(b & 0xff);
  let r = "";
  for (let i = 0; i < 16; i++) { r = ALPHABET[Number(n & 31n)] + r; n >>= 5n; }
  return t + r;
}

/**
 * 单调递增的 ULID 生成器。
 * @returns {(ms: number, rand: Uint8Array|number[]) => string}
 */
export function createUlid() {
  let lastMs = -1;
  /** @type {Uint8Array|null} */
  let last = null;
  return (ms, rand) => {
    if (last && ms <= lastMs) {
      const next = Uint8Array.from(last);
      let i = 9;
      while (i >= 0 && next[i] === 0xff) { next[i] = 0; i--; }
      if (i < 0) throw new RangeError("同一毫秒里 ULID 用完了");
      next[i]++;
      last = next;
      return encodeUlid(lastMs, next);
    }
    lastMs = ms;
    last = Uint8Array.from(rand);
    return encodeUlid(ms, last);
  };
}
