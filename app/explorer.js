// Curio · 知识索引和星球笔记（#233，Luka 2026-11-22）：从原型 prototype/index.html 的 treeHTML、leaf、matchesNode、noteHTML 移植。
// 数据和星图同源：buildChart（starchart.js）给出的现行点、星座和四种状态；旧名来自发布包目录的 catalog.retired。
// 这里全是「数据 → HTML 字符串」的纯函数，node 里能测；点选、展开、抽屉在 app.js。
import { THEMES, THEME_ORDER, BAND_NAME, GRADE_NAME, STATE_WORD, chartStar, consName, consId } from "./starchart.js";
import { LINE_NAME } from "./metro.js";

/** 两个星系（照原型 GALAXY）。 */
export const GALAXY = Object.freeze({ math: "数学", science: "科学" });

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
/** 搜索时不分大小写、不管空格（「20以内」也能找到「20 以内」）。 */
const norm = (s) => String(s ?? "").replace(/\s+/g, "").toLowerCase();

/**
 * 旧名表：现行点 id → 被它接替的旧占位的名字（目录的 retired，replaced_by 连着几层也跟到底）。
 * @param {any} catalog 发布包里的目录（catalog/1）
 * @param {{has: (id: string) => boolean}} live 现行点的 id（buildChart 的 byId）
 * @returns {Map<string, string[]>}
 */
export function aliasIndex(catalog, live) {
  const retired = catalog && Array.isArray(catalog.retired) ? catalog.retired : [];
  const next = new Map(retired.map((r) => [r.id, r.replaced_by]));
  /** @type {Map<string, string[]>} */
  const out = new Map();
  for (const r of retired) {
    if (!r || typeof r.title !== "string") continue;
    let id = r.replaced_by;
    const seen = new Set([r.id]);
    while (next.has(id) && !seen.has(id)) { seen.add(id); id = next.get(id); }
    if (typeof id !== "string" || !live.has(id)) continue;
    if (!out.has(id)) out.set(id, []);
    out.get(id).push(r.title);
  }
  return out;
}

/**
 * 索引的分节：数学、科学两个星系，每个星系下按学段、再按主题排的星座。点亮数和总数都从 buildChart 的点来。
 * @param {ReturnType<typeof import("./starchart.js").buildChart>} model
 */
export function explorerTree(model) {
  return ["math", "science"].map((g) => {
    const pts = model.points.filter((p) => THEMES[p.theme].g === g);
    const cons = model.cons.filter((c) => THEMES[c.theme].g === g)
      .sort((a, b) => a.band - b.band || THEME_ORDER.indexOf(a.theme) - THEME_ORDER.indexOf(b.theme))
      .map((c) => ({ id: c.id, theme: c.theme, band: c.band, name: consName(c), bandName: BAND_NAME[c.band], points: c.points,
        lit: c.points.filter((p) => p.state === "lit").length, total: c.points.length }));
    return { g, name: GALAXY[g], lit: pts.filter((p) => p.state === "lit").length, total: pts.length, cons };
  });
}

/**
 * 搜索（照原型 matchesNode）：名字、单元、主题名、星座名、学段名、星系名，以及旧占位的名字。
 * 搜到旧名时 alias 是那个旧名（叶子旁写「原名：…」）；名字本身就对上时 alias 是 null。
 * @param {ReturnType<typeof import("./starchart.js").buildChart>} model
 * @param {Map<string, string[]>} aliases aliasIndex 的结果
 * @param {string} query
 * @returns {{point: any, alias: string|null}[]}
 */
export function searchPoints(model, aliases, query) {
  const q = norm(query);
  if (!q) return [];
  const has = (t) => typeof t === "string" && norm(t).includes(q);
  const hits = [];
  for (const p of model.points) {
    const old = has(p.title) ? null : (aliases.get(p.id) || []).find(has) || null;
    const t = THEMES[p.theme];
    if (old || has(p.title) || has(p.unit) || has(t.name) || has(consName(p)) || has(BAND_NAME[p.band]) || has(GALAXY[t.g])) {
      hits.push({ point: p, alias: old });
    }
  }
  return hits;
}

/** 叶子前面的小星形：和星图同一套四种样子。 */
export const leafStar = (state) => `<svg class="lstar" aria-hidden="true" width="16" height="16" viewBox="-16 -16 32 32">${chartStar(state, 11)}</svg>`;

/** 火箭标志（和顶栏同一张图）。 */
const SHIP = `<svg class="vlogo" viewBox="0 0 100 100" aria-hidden="true"><path class="k" d="M50 10C62 26 66 40 64 58C62 70 58 76 50 78C42 76 38 70 36 58C34 40 38 26 50 10Z"/><circle cx="50" cy="40" r="7" class="k1"/><path class="k1" d="M37 58L25 76L39 72M63 58L75 76L61 72"/><path d="M44 80q6 14 12 0z" fill="var(--accent)" opacity=".85"/></svg>`;
const CHEVRON = `<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
const LENS = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/></svg>`;

function leafHtml(p, { flat, selected, alias }) {
  const word = STATE_WORD[p.state] + "，" + (GRADE_NAME[p.grade] || p.grade);
  return `<button type="button" class="leaf${flat ? " ind" : ""}" data-node="${esc(p.id)}" data-state="${p.state}" aria-current="${selected === p.id}">${leafStar(p.state)}<span class="lt">${esc(p.title)}${alias ? `<small class="alias">原名：${esc(alias)}</small>` : ""}</span><span class="g" aria-hidden="true">${esc(p.grade)}</span><span class="sr">，${esc(word)}</span></button>`;
}

/**
 * 整个索引的 HTML（照原型 treeHTML）：标志、搜索框，然后是分节和星座分组，或者搜索结果。
 * @param {ReturnType<typeof import("./starchart.js").buildChart>} model
 * @param {{query?: string, isOpen: (c: {id: string, band: number}) => boolean, selected?: string|null, aliases: Map<string, string[]>}} o
 */
export function treeHtml(model, o) {
  const q = (o.query || "").trim();
  let body = "";
  if (q) {
    const hits = searchPoints(model, o.aliases, q);
    body = `<div class="sec">找到 ${hits.length} 颗星球</div>` + hits.map((h) => leafHtml(h.point, { flat: true, selected: o.selected, alias: h.alias })).join("");
  } else {
    for (const s of explorerTree(model)) {
      body += `<div class="sec">${s.name}星系 · <span class="mono">${s.lit}/${s.total}</span></div>`;
      for (const c of s.cons) {
        const open = o.isOpen(c);
        body += `<button type="button" class="grp" data-cons="${esc(c.id)}" aria-expanded="${open}">${CHEVRON}<span class="sw" style="background:var(${THEMES[c.theme].c})"></span><span class="gn">${esc(c.name)}<span class="gb"> · ${c.bandName}</span></span><span class="c"><span class="sr">点亮 </span>${c.lit}/${c.total}</span></button>`;
        if (open) body += c.points.map((p) => leafHtml(p, { flat: false, selected: o.selected, alias: null })).join("");
      }
    }
  }
  const who = Number.isInteger(model.grade) ? `舰长 · ${GRADE_NAME["G" + model.grade]}` : "舰长";
  return `<div class="vault">${SHIP}<div><b>Curio</b><small>${esc(who)}</small></div></div>
    <div class="xsearch">${LENS}<input type="search" placeholder="搜索知识点" value="${esc(o.query || "")}" aria-label="搜索知识点" enterkeyhint="search" autocomplete="off" data-treeq></div>
    <div class="tree">${body}</div>`;
}

/* ============================================================
   星球笔记（照原型 noteHTML；错题、提问、图鉴这些还没接入正式外壳的部分不搬）
   ============================================================ */
/**
 * 一颗星的笔记。
 * @param {any} p buildChart 里的点
 * @param {{card?: any, model: any, tasks: {id: string, title: string, meta: string, go: string}[], canStart: boolean, why?: string}} o
 *   card：已发布的卡（开放的星才有）；tasks：这颗星的入口（动手探索、挑战）；canStart：现在能不能进入；why：不能进入时的一句话
 */
export function noteHtml(p, o) {
  const t = THEMES[p.theme];
  const lit = p.state === "lit";
  const prereq = p.prereq.map((id) => o.model.byId.get(id)).filter(Boolean);
  const dq = o.card && typeof o.card.driving_question === "string" ? o.card.driving_question : "";
  const props = `<dl class="props">
      <dt>状态</dt><dd><span class="pill ${lit ? "lit" : ""}">${STATE_WORD[p.state]}</span></dd>
      <dt>年级</dt><dd>${esc(GRADE_NAME[p.grade] || p.grade)}</dd>
      ${p.unit ? `<dt>单元</dt><dd>${esc(p.unit)}</dd>` : ""}
      <dt>线路</dt><dd><span class="lsw" style="background:var(${t.c})"></span>${esc(LINE_NAME[p.theme])}</dd>
      ${prereq.length ? `<dt>先去</dt><dd class="links">${prereq.map((x) => `<a class="wikilink" href="#" data-goto="${esc(x.id)}">${esc(x.title)}</a>`).join("")}</dd>` : ""}
    </dl>`;
  const head = `<div class="crumbs"><span>${GALAXY[t.g]}</span><span>${esc(consName(p))}座</span><span>${esc(GRADE_NAME[p.grade] || p.grade)}</span></div>
    <h1 id="noteTitle" tabindex="-1">${esc(p.title)}</h1>`;
  if (!p.open) {
    return `<div class="note">${head}${props}
      <div class="callout closed-call">${leafStar("closed")}<div><b>还没开放</b><p class="muted small">这颗星的探索还在造。</p></div></div></div>`;
  }
  const bg = t.g === "math" ? "var(--c-math-bg)" : "var(--c-sci-bg)";
  return `<div class="note">${head}${props}
    ${dq ? `<div class="signal-card" style="background:${bg}"><div class="eyebrow">来自这颗星球的信号</div><p class="dq">${esc(dq)}</p></div>` : ""}
    <h2>任务</h2>
    <div class="tasklist">${o.tasks.length ? o.tasks.map((a) => `<div class="taskrow"><div><b>${esc(a.title)}</b><small>${esc(a.meta)}</small></div><button type="button" class="btn ink" data-start="${esc(a.id)}"${o.canStart ? "" : " disabled"}>${esc(a.go)}</button></div>`).join("")
      : `<p class="muted small">这个还在做。</p>`}</div>
    ${!o.canStart && o.why ? `<p class="muted small">${esc(o.why)}</p>` : ""}
  </div>`;
}

export { consId };
