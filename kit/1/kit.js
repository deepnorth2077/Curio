const PALETTE_KEYS = new Set([
  "bg", "pane", "hover", "rule", "ink", "text", "muted",
  "accent", "accent-soft", "grip", "grip-soft",
  "sage", "sage-bg", "sky", "apricot", "paper",
  "good", "good-soft", "bad", "bad-soft"
]);
const HEX_COLOR = /^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;

/* curio-sfx begin */
/**
 * 纯工厂函数，便于单测注入假 AudioContext 与假时钟。
 * @param {{AudioCtx?: any, nowMs?: () => number, requireGesture?: boolean, eventTarget?: any}} [opts]
 */
function createSfx(opts = {}) {
  const explicitCtx = "AudioCtx" in opts;
  const AudioCtx = explicitCtx
    ? opts.AudioCtx
    : (typeof globalThis !== "undefined" ? (/** @type {any} */ (globalThis).AudioContext || /** @type {any} */ (globalThis).webkitAudioContext || null) : null);
  const nowMs = opts.nowMs || (() => (typeof performance !== "undefined" ? performance.now() : Date.now()));
  const target = "eventTarget" in opts ? opts.eventTarget : (typeof globalThis !== "undefined" ? globalThis : null);
  let isMuted = false;
  let ctx = null;
  let unlocked = explicitCtx && !opts.requireGesture;
  let lastTick = -1e9;
  let noiseBuf = null;
  let nSeq = 0;
  const sources = new Set();

  function unlock() {
    unlocked = true;
    if (isMuted || !AudioCtx) return;
    try {
      if (!ctx) ctx = new AudioCtx();
      if (ctx && (ctx.state === "suspended" || ctx.state === "interrupted")) {
        const p = ctx.resume();
        if (p && typeof p.catch === "function") p.catch(() => {});
      }
    } catch { /* 音频受限时静默降级 */ }
  }

  if (target && typeof target.addEventListener === "function") {
    // iOS 在触摸结束时才授予激活；继续使用系统默认音频类别，尊重侧边静音开关。
    for (const gesture of ["pointerdown", "touchend", "click", "keydown"]) {
      target.addEventListener(gesture, unlock, true);
    }
  }

  function readyCtx() {
    if (isMuted || !AudioCtx || !unlocked) return null;
    try {
      if (!ctx) ctx = new AudioCtx();
      if (!ctx || ctx.state !== "running") return null;
      return ctx;
    } catch { return null; }
  }

  function getNoise(c) {
    if (noiseBuf) return noiseBuf;
    const len = Math.max(1, Math.floor(c.sampleRate * 0.06));
    const b = c.createBuffer(1, len, c.sampleRate);
    const d = b.getChannelData(0);
    // 固定种子生成短噪声，同采样率下宿主与沙箱得到相同波形。
    let seed = 0x63757269;
    for (let i = 0; i < len; i++) {
      seed ^= seed << 13;
      seed ^= seed >>> 17;
      seed ^= seed << 5;
      const sample = (seed >>> 0) / 0x80000000 - 1;
      d[i] = sample * Math.exp(-i / (len * 0.35));
    }
    noiseBuf = b;
    return b;
  }

  function clean(src, nodes) {
    sources.add(src);
    src.onended = () => {
      sources.delete(src);
      try { src.disconnect(); } catch { /* ignore */ }
      for (const nd of nodes) { try { nd.disconnect(); } catch { /* ignore */ } }
    };
  }

  function tone(c, type, f0, f1, t0, dur, peak) {
    const osc = c.createOscillator(), g = c.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(f0, t0);
    if (f1 !== f0) osc.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t0 + dur);
    g.gain.setValueAtTime(0.0008, t0);
    g.gain.linearRampToValueAtTime(peak, t0 + Math.min(0.008, dur * 0.25));
    g.gain.exponentialRampToValueAtTime(0.0008, t0 + dur);
    osc.connect(g);
    g.connect(c.destination);
    clean(osc, [g]);
    osc.start(t0);
    osc.stop(t0 + dur + 0.004);
  }

  function burst(c, filterType, freq, q, t0, dur, peak) {
    const src = c.createBufferSource(), flt = c.createBiquadFilter(), g = c.createGain();
    src.buffer = getNoise(c);
    flt.type = filterType;
    flt.frequency.setValueAtTime(freq, t0);
    flt.Q.setValueAtTime(q, t0);
    g.gain.setValueAtTime(0.0008, t0);
    g.gain.linearRampToValueAtTime(peak, t0 + 0.002);
    g.gain.exponentialRampToValueAtTime(0.0008, t0 + dur);
    src.connect(flt);
    flt.connect(g);
    g.connect(c.destination);
    clean(src, [flt, g]);
    src.start(t0);
    src.stop(t0 + dur + 0.004);
  }

  return {
    /** @param {boolean} v */
    setMuted(v) {
      isMuted = !!v;
      if (isMuted) {
        // 连尚未开始的琶音一起撤掉。重新开声时只播放新的操作。
        for (const src of sources) {
          src.disconnect();
          src.stop();
        }
        sources.clear();
      }
    },
    muted() { return isMuted; },
    seq() { return nSeq; },
    /** @param {number} [step] */
    tick(step = 0) {
      const now = nowMs();
      if (now - lastTick < 35) return false;
      lastTick = now;
      nSeq++;
      const c = readyCtx();
      if (!c) return false;
      const k = Math.max(-6, Math.min(12, +step || 0));
      burst(c, "bandpass", 1480 * Math.pow(2, k * 0.03), 4.5, c.currentTime, 0.018, 0.042);
      return true;
    },
    /** @param {number} [step] */
    hop(step = 0) {
      nSeq++;
      const c = readyCtx();
      if (!c) return false;
      const k = Math.max(0, Math.min(12, +step || 0));
      const f0 = 330 * Math.pow(2, k / 18);
      tone(c, "triangle", f0, f0 * 1.28, c.currentTime, 0.055, 0.085);
      return true;
    },
    snap() {
      nSeq++;
      const c = readyCtx();
      if (!c) return false;
      const t = c.currentTime;
      burst(c, "highpass", 2200, 1.2, t, 0.016, 0.052);
      tone(c, "sine", 290, 155, t, 0.042, 0.055);
      return true;
    },
    tap() {
      nSeq++;
      const c = readyCtx();
      if (!c) return false;
      tone(c, "sine", 520, 340, c.currentTime, 0.022, 0.045);
      return true;
    },
    right() {
      nSeq++;
      const c = readyCtx();
      if (!c) return false;
      const t = c.currentTime;
      tone(c, "triangle", 523.25, 523.25, t, 0.11, 0.075);
      tone(c, "triangle", 783.99, 783.99, t + 0.065, 0.12, 0.08);
      return true;
    },
    nudge() {
      nSeq++;
      const c = readyCtx();
      if (!c) return false;
      const t = c.currentTime;
      tone(c, "sine", 250, 210, t, 0.04, 0.06);
      tone(c, "sine", 220, 185, t + 0.048, 0.045, 0.055);
      return true;
    },
    lit() {
      nSeq++;
      const c = readyCtx();
      if (!c) return false;
      const t = c.currentTime;
      [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(c, "triangle", f, f, t + i * 0.075, 0.32, 0.055));
      return true;
    },
  };
}
/* curio-sfx end */
const Sfx = createSfx();

const Host = (() => {
  const listeners = new Map(), inFrame = window.parent !== window;
  addEventListener("message", e => {
    const m = e.data;
    if (e.source !== window.parent || !m || m.contract !== "activity/1.2") return;
    for (const handler of listeners.get(m.type) || []) handler(m.payload || {});
  });
  const send = (type, payload) => {
    if (inFrame) parent.postMessage({ contract: "activity/1.2", type, payload: payload || {} }, "*");
    else (window.__sent = window.__sent || []).push({ type, payload: payload || {} });
  };
  if (window.ResizeObserver) new ResizeObserver(() => send("resize", { h: document.documentElement.scrollHeight })).observe(document.body || document.documentElement);
  return {
    inFrame,
    on(type, handler){
      if (!listeners.has(type)) listeners.set(type, new Set());
      const handlers = listeners.get(type);
      handlers.add(handler);
      return () => handlers.delete(handler);
    },
    ready: () => send("ready"),
    event: (verb, result) => send("event", { verb, result }),
    state: o => send("state", o),
    requestHint: () => send("request_hint"),
    noteQuestion: text => send("note_question", { text }),
    complete: r => send("complete", r || {})
  };
})();

let hostThemed = false;
function applyHostTheme(p){
  if (!p || typeof p !== "object") return;
  const root = document.documentElement;
  if (p.scheme === "dark" || p.scheme === "light"){
    hostThemed = true;
    root.classList.toggle("kit-dark", p.scheme === "dark");
    root.style.colorScheme = p.scheme;
  }
  if (p.palette && typeof p.palette === "object"){
    hostThemed = true;
    for (const k of PALETTE_KEYS) root.style.removeProperty("--" + k);
    for (const [k, v] of Object.entries(p.palette)){
      if (PALETTE_KEYS.has(k) && typeof v === "string" && HEX_COLOR.test(v)) root.style.setProperty("--" + k, v);
    }
  }
}
if (!Host.inFrame && typeof matchMedia === "function"){
  const mq = matchMedia("(prefers-color-scheme: dark)");
  const syncSys = () => {
    if (hostThemed) return;
    document.documentElement.classList.toggle("kit-dark", mq.matches);
    document.documentElement.style.colorScheme = mq.matches ? "dark" : "light";
  };
  syncSys();
  if (mq.addEventListener) mq.addEventListener("change", syncSys);
}

let navFaces = null, navNow = "curious";
function navFace(k){
  navNow = k;
  const avatar = document.querySelector(".ava");
  if (avatar && typeof navFaces?.[k] === "string") avatar.innerHTML = navFaces[k];
}

const sentPred = new Set(), sentObs = new Set();
let completed = false;
function observedOnce(station){ if (sentObs.has(station)) return; sentObs.add(station); Host.event("observed", { station, item: "station-complete" }); }
let lastState = "";
function sendState(o){ const s = JSON.stringify(o); if (s === lastState) return; lastState = s; Host.state(o); }

function sketchLib(){
  const R=(seed)=>{ let s=((seed|0)*2654435761)>>>0||7; return ()=>{ s^=s<<13; s>>>=0; s^=s>>>17; s^=s<<5; s>>>=0; return s/4294967296; }; };
  const f=n=>Math.round(n*10)/10;
  function cr(p,closed){ const n=p.length; let d=`M${f(p[0][0])} ${f(p[0][1])}`;
    for(let i=0;i<(closed?n:n-1);i++){ const p1=p[i],p2=p[(i+1)%n]; const p0=(!closed&&i===0)?p1:p[(i-1+n)%n]; const p3=(!closed&&i+2>=n)?p2:p[(i+2)%n];
      d+=`C${f(p1[0]+(p2[0]-p0[0])/6)} ${f(p1[1]+(p2[1]-p0[1])/6)} ${f(p2[0]-(p3[0]-p1[0])/6)} ${f(p2[1]-(p3[1]-p1[1])/6)} ${f(p2[0])} ${f(p2[1])}`; }
    return d; }
  function line(x1,y1,x2,y2,seed,j){ const r=R(seed); j=j==null?1:j; const L=Math.hypot(x2-x1,y2-y1)||1; const a=Math.min(1.8,.5+L*.008)*j; const o=()=>(r()-.5)*2*a;
    const nx=-(y2-y1)/L, ny=(x2-x1)/L, bow=(r()-.5)*Math.min(L*.035,6)*j;
    return `M${f(x1+o())} ${f(y1+o())}Q${f((x1+x2)/2+nx*bow)} ${f((y1+y2)/2+ny*bow)} ${f(x2+o())} ${f(y2+o())}`; }
  function ellipse(cx,cy,rx,ry,seed,j){ const r=R(seed); j=j==null?1:j; const N=12, a0=r()*Math.PI*2, turn=1.05+r()*.06, p=[];
    for(let i=0;i<=N;i++){ const t=a0+i/N*Math.PI*2*turn, k=1+(r()-.5)*.07*j; p.push([cx+Math.cos(t)*rx*k, cy+Math.sin(t)*ry*k]); }
    return cr(p,false); }
  function curve(pts,seed,j){ const r=R(seed); j=j==null?1:j; return cr(pts.map(q=>[q[0]+(r()-.5)*2*j,q[1]+(r()-.5)*2*j]),false); }
  return {line,ellipse,curve,cr,R,f};
}
const Sk = sketchLib();
const P = (d, cls, extra) => `<path class="${cls || "k"}" d="${d}"${extra ? " " + extra : ""}/>`;
const T = (x, y, s, cls, extra) => `<text x="${x}" y="${y}" class="${cls || "t"}"${extra ? " " + extra : ""}>${s}</text>`;
const TC = (x, y, s, cls, extra) => T(x, y, s, cls, 'text-anchor="middle"' + (extra ? " " + extra : ""));
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const r1 = n => Math.round(n * 10) / 10;
const box = (x, y, w, h, seed, j) => Sk.line(x, y, x + w, y, seed, j) + Sk.line(x + w, y, x + w, y + h, seed + 1, j) + Sk.line(x + w, y + h, x, y + h, seed + 2, j) + Sk.line(x, y + h, x, y, seed + 3, j);
const pol = (cx, cy, r, deg) => { const a = deg * Math.PI / 180; return [cx + r * Math.sin(a), cy - r * Math.cos(a)]; };
function sectorD(cx, cy, r, a0, a1){
  if (a1 - a0 >= 359.9) return `M${r1(cx - r)} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0Z`;
  const p0 = pol(cx, cy, r, a0), p1 = pol(cx, cy, r, a1);
  return `M${r1(cx)} ${r1(cy)}L${r1(p0[0])} ${r1(p0[1])}A${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${r1(p1[0])} ${r1(p1[1])}Z`;
}
function arcD(cx, cy, r, a0, a1, seed){
  const rnd = Sk.R(seed), N = Math.max(2, Math.ceil((a1 - a0) / 14)), pts = [];
  for (let i = 0; i <= N; i++) pts.push(pol(cx, cy, r * (1 + (rnd() - .5) * .012), a0 + (a1 - a0) * i / N));
  return Sk.cr(pts, false);
}

const narrow = () => document.body.classList.contains("narrow");
const CN1 = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"];
function cnNum(value){
  const n = Number(value);
  if (n === 100) return "百";
  if (n === 1000) return "千";
  if (!Number.isInteger(n) || n < 0 || n > 999) return String(value);
  if (n <= 10) return CN1[n];
  const hundreds = Math.floor(n / 100), tens = Math.floor(n / 10) % 10, ones = n % 10;
  let text = hundreds ? CN1[hundreds] + "百" : "";
  if (tens) text += (tens === 1 && !hundreds ? "" : CN1[tens]) + "十";
  else if (hundreds && ones) text += "零";
  return text + (ones ? CN1[ones] : "");
}
const cnFrac = (a, b) => `${cnNum(b)}分之${cnNum(a)}`;
const F = (a, b) => `<span class="frac" role="img" aria-label="${cnFrac(a, b)}"><span aria-hidden="true">${a}</span><span aria-hidden="true">${b}</span></span>`;
const FSZ = { fs: [16, 20], fm: [22, 26], fb: [34, 38] };
function fracS(x, y, a, b, cls, seed){
  const sz = FSZ[cls][narrow() ? 1 : 0], w = Math.max(String(a).length, String(b).length) * sz * .62 + sz * .5;
  return `<g role="img" aria-label="${cnFrac(a, b)}">` + TC(x, r1(y - sz * .3), a, cls) + P(Sk.line(x - w / 2, y, x + w / 2, y, seed || 7, .45), "fl") + TC(x, r1(y + sz * .98), b, cls) + `</g>`;
}
function oneMark(x, y, w, h, seed, o){
  const tx = x + 4, ty = o && o.below ? y + h - 15 : y - 15;
  return P(box(x, y, w, h, seed, .8), "one") +
    `<g transform="rotate(-5 ${tx + 14} ${ty + 14})"><rect x="${tx}" y="${ty}" width="28" height="30" rx="4" class="papr"/>` + P(box(tx, ty, 28, 30, seed + 9, .4), "k1") + TC(tx + 14, ty + 22, "1", "fm") + `</g>`;
}

const $ = id => document.getElementById(id);
const svg = $("stage"), gDyn = $("dyn"), cueEl = $("cue");
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const vbW = () => svg.viewBox.baseVal.width || 800;
const pxScale = () => vbW() / (svg.clientWidth || 800);
const gripR = () => Math.max(17, 15 * pxScale());
const hitR = () => Math.max(30, 26 * pxScale());
function chevron(px, py, dx, dy, s){ const nx = -dy, ny = dx; return `M${r1(px - dx * s + nx * s)} ${r1(py - dy * s + ny * s)}L${r1(px + dx * s * .7)} ${r1(py + dy * s * .7)}L${r1(px - dx * s - nx * s)} ${r1(py - dy * s - ny * s)}`; }
function grip(x, y, dir, o){
  o = o || {}; const g = gripR(), on = !!o.on, k = on ? 1.12 : 1, r = g * k, [dx, dy] = dir, nx = -dy, ny = dx;
  let s = `<circle cx="${r1(x)}" cy="${r1(y)}" r="${r1(r)}" class="gfill"/>` + P(Sk.ellipse(x, y, r, r, o.seed || 71, .5), "gring" + (on ? " on" : ""));
  for (const i of [-1, 0, 1]){ const ox = dx * i * r * .36, oy = dy * i * r * .36, L = r * (i ? .36 : .5); s += P(`M${r1(x + ox - nx * L)} ${r1(y + oy - ny * L)}L${r1(x + ox + nx * L)} ${r1(y + oy + ny * L)}`, "gridge"); }
  const gap = g + 11;
  if (o.arc){ const [cx, cy] = o.arc, R = Math.hypot(x - cx, y - cy), a0 = Math.atan2(x - cx, cy - y) * 180 / Math.PI, da = gap / R * 180 / Math.PI;
    for (const sg of [-1, 1]){ const [px, py] = pol(cx, cy, R, a0 + sg * da), a = (a0 + sg * da) * Math.PI / 180; s += P(chevron(px, py, sg * Math.cos(a), sg * Math.sin(a), 6), "garrow"); } }
  else for (const sg of [-1, 1]) s += P(chevron(x + dx * sg * gap, y + dy * sg * gap, dx * sg, dy * sg, 6), "garrow");
  if (o.kbd) s += `<circle cx="${r1(x)}" cy="${r1(y)}" r="${r1(r + 6)}" class="gkbd"/>`;
  return s;
}
function lineStrip(lx, ly, lw, fracs, seed){
  let s = P(Sk.line(lx - 10, ly, lx + lw + 14, ly, seed, .5)) + P(`M${lx} ${ly - 12}v24M${lx + lw} ${ly - 12}v24`) + TC(lx, ly + 38, "0", "lbm") + TC(lx + lw, ly + 38, "1", "lbm"), lastLab = 1e9;
  for (const [a, b] of fracs.slice().sort((p, q) => q[0] / q[1] - p[0] / p[1])){
    const x = r1(lx + lw * a / b);
    s += P(`M${x} ${ly}v-15`, "k1") + `<circle cx="${x}" cy="${ly - 18}" r="5.5" class="lead"/>` + P(Sk.ellipse(x, ly - 18, 5.5, 5.5, seed + a * 13 + b, .3), "k1");
    if (lastLab - x >= (narrow() ? 44 : 36)){ s += fracS(x, ly - 50, a, b, "fs", seed + b); lastLab = x; }
  }
  return s;
}
const RIDGES = `<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 3v12M9 3v12M14 3v12"/></svg>`;

let STATIONS = 3;
const S = { station: 1, mode: "talk", scene: "s1", hold: false, press: false, kbd: false, dirty: true };
let gen = 0;
const later = (ms, f) => { const g = gen; setTimeout(() => { if (g === gen) f(); }, reduced ? Math.min(ms, 60) : ms); };

function head(n, title){ $("station").textContent = n ? `第 ${n} 站 · 共 ${STATIONS} 站` : "星卡"; $("title").textContent = title; }
function hint(s){ $("hint").textContent = s || ""; }
function readout(html){ if ($("readout").innerHTML !== (html || "")) $("readout").innerHTML = html || ""; }
function say(html, tone){ const b = $("say"); b.innerHTML = html; b.className = "bubble" + (tone ? " " + tone : ""); navFace(tone === "good" ? "clap" : tone === "bad" || tone === "hmm" ? "think" : "curious"); }
let fingerDown = false;
let keysDown = 0;
function mountStationControls(){
  addEventListener("pointerdown", () => { fingerDown = true; }, true);
  for (const ev of ["pointerup", "pointercancel"]) addEventListener(ev, () => { fingerDown = false; }, true);
  addEventListener("keydown", e => { if (!e.repeat) keysDown++; }, true);
  addEventListener("keyup", () => { keysDown = Math.max(0, keysDown - 1); }, true);
  addEventListener("blur", () => { fingerDown = false; keysDown = 0; S.hold = false; });
  if (svg) addEventListener("resize", fitView);
  mountQuestion();
}
function actions(list){
  const boxEl = $("actions"); boxEl.replaceChildren();
  S.dirty = true;
  const guard = fingerDown, born = performance.now();
  let keyGuard = keysDown > 0;
  if (keyGuard){ const off = () => { if (keysDown === 0){ setTimeout(() => { keyGuard = false; }, 0); removeEventListener("keyup", off, true); } }; addEventListener("keyup", off, true); }
  for (const a of list || []){
    const b = document.createElement("button");
    b.type = "button"; b.className = "btn " + (a.cls || ""); b.innerHTML = (a.hold ? RIDGES : "") + `<span>${a.label}</span>`;
    if (a.hold){
      const on = v => { S.hold = v; b.classList.toggle("on", v); if (v) touched(); };
      b.addEventListener("pointerdown", e => { e.preventDefault(); b.setPointerCapture && b.setPointerCapture(e.pointerId); on(true); });
      for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) b.addEventListener(ev, () => on(false));
      b.addEventListener("keydown", e => { if (e.key === " " || e.key === "Enter"){ e.preventDefault(); if (a.step) a.step(); else on(true); } });
      b.addEventListener("keyup", e => { if (e.key === " " || e.key === "Enter"){ e.preventDefault(); on(false); } });
      b.addEventListener("blur", () => on(false));
      b.addEventListener("contextmenu", e => e.preventDefault());
    } else {
      b.addEventListener("click", e => {
        if (performance.now() - born < 400 || (keyGuard && e.detail === 0)) return;
        const s0 = Sfx.seq();
        a.go(e);
        if (Sfx.seq() === s0) Sfx.tap();
      });
      if (guard){ b.disabled = true; const en = () => { setTimeout(() => { b.disabled = false; }, 120); removeEventListener("pointerup", en, true); }; addEventListener("pointerup", en, true); }
    }
    boxEl.append(b);
  }
  const first = boxEl.querySelector("button");
  if (first && !/^act/.test(S.mode)) first.focus({ preventScroll: true });
  return boxEl;
}
function ask(question, options, onAnswer){
  say(question); navFace("waiting");
  actions(options.map((o, i) => ({ label: o.label, cls: "choice", go: () => {
    if (!sentPred.has(S.station)){ sentPred.add(S.station); Host.event("predicted", { station: S.station, choice: i, correct: !!o.correct, misconception: o.mis || null }); }
    S.guess = S.guess || {}; S.guess[S.station] = o;
    say(o.feedback, o.correct ? "good" : "hmm");
    if (o.correct) Sfx.right(); else Sfx.nudge();
    onAnswer(o);
  }})));
}
function next(label, go, cls){ actions([{ label, go, cls }]); }
let replay = 0;
const REPLAY = {};
function nextOr(label, go, cls){ if (replay && picking) next("回到选站", pickStation); else if (replay) next("回星卡", enterEnd); else next(label, go, cls); }
function replayAt(k){ replay = k; gen++; S.station = k; hint(""); readout(""); disarmCue(); REPLAY[k](); }
function restart(){ replay = 0; picking = false; sentPred.clear(); sentObs.clear(); S.guess = {}; lastState = ""; enter1(); }
function endActions(){
  replay = 0; picking = false;
  actions([{ label: "从头玩", go: restart, cls: "ghost tight" }].concat(Array.from({ length: STATIONS }, (_, i) => ({ label: `第 ${i + 1} 站`, go: () => replayAt(i + 1), cls: "tight" }))));
}
let doneStations = 0, picking = false, stationOptions = null;
function resumeFrom(p){
  if (!stationOptions || picking || doneStations || !p) return;
  const saved = new Set(Array.isArray(p.completed_stations) ? p.completed_stations : []);
  const all = p.activity_completed === true;
  while (doneStations < STATIONS && (all || saved.has(doneStations + 1))) doneStations++;
  if (doneStations) pickStation();
}
function pickStation(){
  picking = true; replay = 0; gen++; S.mode = "talk"; hint(""); readout(""); disarmCue();
  const list = [];
  const nextStation = doneStations + 1;
  const canContinue = nextStation <= STATIONS && typeof stationOptions.resume === "function";
  if (canContinue) list.push({ label: `继续第 ${nextStation} 站`, go: () => {
    picking = false;
    S.station = nextStation;
    stationOptions.resume(nextStation);
  } });
  for (let k = 1; k <= doneStations; k++) list.push({ label: `重玩第 ${k} 站`, go: () => replayAt(k), cls: "tight" });
  list.push({ label: "从头玩", go: restart, cls: "ghost tight" });
  if (canContinue) say(`上次做完了 ${doneStations} 站。接着玩，还是重玩一站？`);
  else say(doneStations < STATIONS ? `上次做完了 ${doneStations} 站。重玩一站，还是从头玩？` : "这几站你都做完了。想重玩哪一站？");
  actions(list);
}

function mountQuestion(){
  const area = $("qarea");
  if (!area) return;
  const open = document.createElement("button");
  open.type = "button"; open.className = "btn ghost small"; open.textContent = "我有个问题";
  open.style.marginTop = "12px";
  open.addEventListener("click", () => {
    if (area.querySelector("textarea")) return;
    Sfx.tap();
    const ta = document.createElement("textarea"); ta.maxLength = 120; ta.placeholder = "想问领航员什么？";
    const send = document.createElement("button"); send.type = "button"; send.className = "btn small"; send.textContent = "发给领航员";
    const bx = document.createElement("div"); bx.className = "qbox"; bx.append(ta, send);
    send.addEventListener("click", () => { const q = ta.value.trim(); if (!q) return; Sfx.tap(); Host.noteQuestion(q); bx.remove(); say("好问题，我记下来了。等会儿一起找答案。"); });
    area.append(bx); ta.focus();
  });
  area.append(open);
}

let cuePos = null, cueTimer = 0;
function armCue(pos){ disarmCue(); const g = gen; cueTimer = setTimeout(() => { if (g === gen && /^act/.test(S.mode)){ cuePos = pos; S.dirty = true; } }, 1500); }
function disarmCue(){ clearTimeout(cueTimer); cuePos = null; cueEl.style.display = "none"; }
function touched(){ if (cuePos || cueTimer) disarmCue(); cueTimer = 0; }
function placeCue(){ if (!cuePos) return; const [x, y, r] = cuePos(); cueEl.setAttribute("cx", r1(x)); cueEl.setAttribute("cy", r1(y)); cueEl.setAttribute("r", r1((r || gripR()) + 2)); cueEl.style.display = ""; }
function cueAt(x, y, r){ disarmCue(); cueEl.setAttribute("cx", r1(x)); cueEl.setAttribute("cy", r1(y)); cueEl.setAttribute("r", r1(r)); cueEl.style.display = ""; }
function hideCue(){ disarmCue(); }

let VIEW = {};
function fitView(){
  const nar = (svg.clientWidth || 800) < 600, cfg = VIEW[S.scene];
  S.narrow = nar;
  document.body.classList.toggle("narrow", nar);
  const b = !cfg ? [0, 0, 800, 610] : cfg.length === 4 ? (nar ? cfg : [0, 0, 800, 610]) : (nar ? [100, cfg[0], 600, cfg[1]] : [0, cfg[0], 800, cfg[1]]);
  const v = b.join(" ");
  if (svg.getAttribute("viewBox") !== v){ svg.setAttribute("viewBox", v); S.dirty = true; return true; }
  return false;
}
function scene(name){ S.scene = name; fitView(); S.dirty = true; }

Host.on("theme", p => { applyHostTheme(p); S.dirty = true; });
Host.on("mute", p => { if (p && typeof p.muted === "boolean") Sfx.setMuted(p.muted); });

const Kit = (() => {
  let enterFn = null, booted = false, timer = 0, pendingInit = null;
  function boot(){
    if (booted || !enterFn) return;
    booted = true;
    clearTimeout(timer);
    enterFn(pendingInit || {});
  }
  Host.on("init", p => {
    applyHostTheme(p);
    if (p && typeof p.muted === "boolean") Sfx.setMuted(p.muted);
    if (p && p.navigator && p.navigator.faces && typeof p.navigator.faces.curious === "string"){
      navFaces = p.navigator.faces;
      navFace(navNow);
    }
    if (p && p.question_available === false && $("qarea")) $("qarea").hidden = true;
    pendingInit = p;
    // 先让活动自己的 init 订阅读到年级、阶段等字段，再进入首屏。
    queueMicrotask(() => { boot(); if (booted) resumeFrom(p); });
  });
  return {
    start(fn, { stations = null } = {}){
      if (enterFn) return;
      stationOptions = stations;
      if (stationOptions) mountStationControls();
      enterFn = fn;
      Host.ready();
      if (!Host.inFrame) boot();
      else if (!booted){
        if (pendingInit){ boot(); resumeFrom(pendingInit); }
        else timer = setTimeout(boot, 300);
      }
    }
  };
})();
