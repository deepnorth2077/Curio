// 领航员（docs/specs/navigators.md 第 1、4 节）：显示谁、脸的 SVG 按白名单再查一遍、去掉最外层 <svg>。
// 纯函数，不碰 DOM、不联网；外壳和 node 测试共用。SVG 的规则和 tools/ci_checks.py 的 check_navigator_svg 一一对应，
// 两边用同一份向量 app/vectors/navigator-svg.json 测。

/** 每位领航员的六张脸。 */
export const NAVIGATOR_FACES = Object.freeze(["curious", "waiting", "surprised", "clap", "think", "wrong"]);

const SVG_NS = "http://www.w3.org/2000/svg";
const XLINK_NS = "http://www.w3.org/1999/xlink";
const XML_NS = "http://www.w3.org/XML/1998/namespace";
const DRAWABLE = new Set(["path", "circle", "ellipse", "rect", "line", "polyline", "polygon"]);
const ELEMENTS = new Set([...DRAWABLE, "svg", "g"]);
// 内容规格 3.6 的属性白名单，去掉 id、href、xlink:href、clip-path、渐变和文字用的属性（同 ci_checks.NAVIGATOR_ATTRIBUTES）
const ATTRIBUTES = new Set([
  "x", "y", "width", "height", "d", "points", "cx", "cy", "r", "rx", "ry", "x1", "y1", "x2", "y2",
  "transform", "viewBox", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
  "stroke-dasharray", "opacity", "fill-opacity", "stroke-opacity", "class", "xmlns", "aria-label", "role",
]);
const CLASSES = new Set(["k", "k1", "f-ink", "f-pane", "f-sky", "f-sage", "f-apricot", "f-paper", "f-muted", "f-accent"]);
export const NAVIGATOR_MAX_DRAWABLE = 16;
export const NAVIGATOR_MAX_BYTES = 3072;

const NAME = /^[A-Za-z_][A-Za-z0-9._-]*(?::[A-Za-z_][A-Za-z0-9._-]*)?/;
const ENTITY = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" };

class ParseError extends Error {}

/** 解开属性值里的实体（只认五个预定义的和数字的）；别的实体是解析错误。 @param {string} v */
function unescape(v) {
  if (v.includes("<")) throw new ParseError("属性值里不能有 <");
  return v.replace(/&([^;]*);?/g, (m, body) => {
    if (!m.endsWith(";")) throw new ParseError("实体没有结束");
    if (body in ENTITY) return ENTITY[body];
    const n = /^#x([0-9a-fA-F]+)$/.exec(body) ? parseInt(body.slice(2), 16) : /^#([0-9]+)$/.exec(body) ? parseInt(body.slice(1), 10) : NaN;
    if (!Number.isFinite(n) || n < 1 || n > 0x10ffff) throw new ParseError("不认识的实体");
    return String.fromCodePoint(n);
  });
}

/**
 * 很小的 XML 解析：只够读领航员的脸。注释、CDATA、DOCTYPE、处理指令（第一行的 XML 声明除外）都算解析不了。
 * 返回根元素：{ns, local, prefixed, attrs: [{name, ns, local, value}], children, text, tail, start, innerStart, innerEnd}。
 * @param {string} s
 */
function parseXml(s) {
  let i = 0;
  const ws = () => { while (i < s.length && /\s/.test(s[i])) i++; };
  if (s.startsWith("<?xml")) { const e = s.indexOf("?>"); if (e < 0) throw new ParseError("XML 声明没有结束"); i = e + 2; }
  ws();
  /** @type {any} */ let root = null;
  /** @type {any[]} */ const stack = [];
  /** @type {Array<Record<string,string>>} */ const scopes = [{ xml: XML_NS }];
  const lookup = (prefix) => { for (let k = scopes.length - 1; k >= 0; k--) if (prefix in scopes[k]) return scopes[k][prefix]; return undefined; };
  let lastClosed = null;
  while (i < s.length) {
    if (s[i] !== "<") {
      const e = s.indexOf("<", i), chunk = s.slice(i, e < 0 ? s.length : e);
      const text = unescapeText(chunk);
      if (stack.length) {
        const top = stack[stack.length - 1];
        if (lastClosed && lastClosed.parent === top) lastClosed.tail += text; else top.text += text;
      } else if (text.trim()) throw new ParseError("根元素外面有文字");
      i = e < 0 ? s.length : e;
      continue;
    }
    if (s.startsWith("</", i)) {
      i += 2;
      const m = NAME.exec(s.slice(i));
      if (!m) throw new ParseError("结束标签不对");
      const top = stack.pop();
      if (!top || top.qname !== m[0]) throw new ParseError("结束标签和开始标签对不上");
      top.innerEnd = i - 2;
      i += m[0].length; ws();
      if (s[i] !== ">") throw new ParseError("结束标签不对");
      i++;
      scopes.pop();
      lastClosed = top;
      continue;
    }
    if (s.startsWith("<!", i) || s.startsWith("<?", i)) throw new ParseError("不能有注释、CDATA、DOCTYPE 或处理指令");
    if (root && !stack.length) throw new ParseError("只能有一个根元素");
    const start = i;
    i++;
    const m = NAME.exec(s.slice(i));
    if (!m) throw new ParseError("开始标签不对");
    i += m[0].length;
    /** @type {Array<{name: string, value: string}>} */ const raw = [];
    let selfClose = false;
    for (;;) {
      const before = i; ws();
      if (s[i] === "/" && s[i + 1] === ">") { i += 2; selfClose = true; break; }
      if (s[i] === ">") { i++; break; }
      if (i === before) throw new ParseError("属性之间要有空白");
      const a = NAME.exec(s.slice(i));
      if (!a) throw new ParseError("属性名不对");
      i += a[0].length; ws();
      if (s[i] !== "=") throw new ParseError("属性没有值");
      i++; ws();
      const q = s[i];
      if (q !== '"' && q !== "'") throw new ParseError("属性值要加引号");
      const e = s.indexOf(q, i + 1);
      if (e < 0) throw new ParseError("属性值没有结束");
      if (raw.some((r) => r.name === a[0])) throw new ParseError("属性重复");
      raw.push({ name: a[0], value: unescape(s.slice(i + 1, e)) });
      i = e + 1;
    }
    /** @type {Record<string,string>} */ const scope = {};
    for (const r of raw) {
      if (r.name === "xmlns") scope[""] = r.value;
      else if (r.name.startsWith("xmlns:")) scope[r.name.slice(6)] = r.value;
    }
    scopes.push(scope);
    const [prefix, local] = m[0].includes(":") ? m[0].split(":") : ["", m[0]];
    const ns = lookup(prefix);
    if (prefix && ns === undefined) throw new ParseError("没有声明的前缀");
    const attrs = [];
    for (const r of raw) {
      if (r.name === "xmlns" || r.name.startsWith("xmlns:")) continue; // 命名空间声明不算属性（和 Python 的 ElementTree 一样）
      if (r.name.includes(":")) {
        const [p, l] = r.name.split(":");
        const ans = lookup(p);
        if (ans === undefined) throw new ParseError("没有声明的前缀");
        attrs.push({ name: r.name, ns: ans, local: l, value: r.value });
      } else attrs.push({ name: r.name, ns: "", local: r.name, value: r.value });
    }
    const el = { qname: m[0], ns: ns || "", local, prefixed: !!prefix, attrs, children: [], text: "", tail: "", parent: stack[stack.length - 1] || null, start, innerStart: i, innerEnd: i };
    if (el.parent) el.parent.children.push(el); else root = el;
    lastClosed = null;
    if (selfClose) { scopes.pop(); lastClosed = el; } else stack.push(el);
  }
  if (stack.length || !root) throw new ParseError("文件没有结束");
  return root;
}

/** 元素中间的文字：只解开实体，不许出现 & 之外的标记。 @param {string} chunk */
function unescapeText(chunk) {
  if (chunk.includes(">") && /\]\]>/.test(chunk)) throw new ParseError("文字里不能有 ]]>");
  return unescape(chunk);
}

/**
 * 一张领航员表情 SVG 的严格检查（规格第 1 节「每个 SVG」），和 tools/ci_checks.py 的 check_navigator_svg 同一套规则。
 * @param {Uint8Array} bytes 原始字节
 * @returns {string[]} 错误文字；空数组是通过
 */
export function checkNavigatorSvg(bytes) {
  const errors = [];
  if (bytes.byteLength > NAVIGATOR_MAX_BYTES) errors.push(`领航员的 SVG 不能超过 ${NAVIGATOR_MAX_BYTES} 字节，现在是 ${bytes.byteLength}`);
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes); }
  catch { return [...errors, "领航员的 SVG 不是 UTF-8"]; }
  if (text.includes("<!--")) errors.push("领航员的 SVG 不能有注释");
  if (text.toUpperCase().includes("<![CDATA[")) errors.push("领航员的 SVG 不能有 CDATA");
  if (/<!\s*(?:DOCTYPE|ENTITY)\b/i.test(text)) errors.push("领航员的 SVG 不能有 DOCTYPE 或实体");
  for (const m of text.matchAll(/<\?([A-Za-z0-9_-]+)[\s\S]*?\?>/g)) {
    if (!(m[1].toLowerCase() === "xml" && m.index === 0)) errors.push("领航员的 SVG 只允许第一行的 XML 声明，不允许其他处理指令");
  }
  let root;
  try { root = parseXml(text); }
  catch (e) { return [...errors, `领航员的 SVG 不是合法的 XML：${e instanceof Error ? e.message : e}`]; }
  if (root.ns !== SVG_NS || root.local !== "svg") errors.push("领航员的 SVG 最外层必须是 SVG 命名空间的 <svg>");
  const vb = root.attrs.find((a) => a.ns === "" && a.local === "viewBox");
  if (!vb || vb.value !== "0 0 48 48") errors.push(`领航员的 SVG 的 viewBox 必须是 0 0 48 48，现在是 ${vb ? JSON.stringify(vb.value) : "没有"}`);
  let drawable = 0, accent = 0;
  const walk = (el) => {
    const tag = el.local;
    if (!ELEMENTS.has(tag) || (tag === "svg" && el !== root)) errors.push(`领航员的 SVG 不能用元素 ${tag}` + (tag === "svg" ? "（不能嵌套 <svg>）" : ""));
    if (DRAWABLE.has(tag)) drawable++;
    if (el.text.trim() || (el !== root && el.tail.trim())) errors.push("领航员的 SVG 里不能有文字");
    for (const a of el.attrs) {
      const name = a.ns === XLINK_NS && a.local === "href" ? "xlink:href" : a.local;
      if (!ATTRIBUTES.has(name)) errors.push(`领航员的 SVG 不能用属性 ${name}`);
      if ((name === "fill" || name === "stroke") && a.value !== "none") errors.push(`领航员的 SVG 颜色只能用 class，${name} 只许写 none，现在是 ${JSON.stringify(a.value)}`);
      if (/url\s*\(/i.test(a.value)) errors.push("领航员的 SVG 不能用 url(…)");
    }
    const cls = el.attrs.find((a) => a.ns === "" && a.local === "class");
    if (cls) {
      const names = cls.value.split(/\s+/).filter(Boolean);
      if (tag === "g" || tag === "svg") errors.push(`领航员的 SVG 颜色类不能写在 <${tag}> 上`);
      for (const n of names) if (!CLASSES.has(n)) errors.push(`领航员的 SVG 不认识颜色类 ${n}`);
      if (names.includes("f-accent")) accent++;
    }
    for (const c of el.children) walk(c);
  };
  walk(root);
  if (drawable > NAVIGATOR_MAX_DRAWABLE) errors.push(`领航员的 SVG 能画出东西的元素不能超过 ${NAVIGATOR_MAX_DRAWABLE} 个，现在是 ${drawable}`);
  if (accent > 1) errors.push(`领航员的 SVG 每张最多一个元素用 f-accent，现在是 ${accent}`);
  return errors;
}

/**
 * 去掉最外层 <svg>，只留里面的内容（规格第 1、6 节）：外壳放进自己的 <svg>，宿主发给模块。只用这一个函数做。
 * 只收已经通过 checkNavigatorSvg 的文字；根带前缀或里面有带前缀的元素时抛错（去掉根以后前缀就没有声明了）。
 * @param {string} text
 * @returns {string}
 */
export function innerSvg(text) {
  const root = parseXml(text);
  if (root.prefixed || root.local !== "svg" || root.ns !== SVG_NS) throw new Error("最外层不是 <svg>");
  const anyPrefixed = (el) => el.children.some((c) => c.prefixed || c.attrs.some((a) => a.name.includes(":")) || anyPrefixed(c));
  if (anyPrefixed(root)) throw new Error("里面的元素不能带前缀");
  return text.slice(root.innerStart, root.innerEnd).trim();
}

/**
 * 显示的是谁（规格第 4 节）：「已认识」是发布包里的领航员（第一版都是 start），按 id 码点排序。
 * 选的那位在「已认识」里就用它；否则（还没选，或选的那位不在发布包里）用排第一的那位，不写事件。
 * 发布包里一位都没有时是 null（外壳和模块用自带的脸）。
 * @param {string|null|undefined} chosenId 投影 projectNavigator 给出的 navigator_id
 * @param {Map<string, any>|Iterable<string>} navigators 发布包里的领航员（loadRelease 的 navigators，或 id 列表）
 * @returns {string|null}
 */
export function shownNavigator(chosenId, navigators) {
  const ids = [...(navigators instanceof Map ? navigators.keys() : navigators)].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  if (!ids.length) return null;
  return typeof chosenId === "string" && ids.includes(chosenId) ? chosenId : ids[0];
}
