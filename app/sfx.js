// 原生 Web Audio 程序化微音效（docs/specs/kit.md 第 2 节）：无背景音乐、无循环音、无外部音频文件。
// 此处的 createSfx 由 tools/kit.py 从最新零件库同步。

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
  const counts = new Map();
  let master = null;
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

  function readyCtx(name) {
    // 记录操作所请求的声位，即使静音也让按钮和走查得到相同的反馈语义。
    nSeq++;
    counts.set(name, (counts.get(name) || 0) + 1);
    if (isMuted || !AudioCtx || !unlocked) return null;
    try {
      if (!ctx) ctx = new AudioCtx();
      if (!ctx || ctx.state !== "running") return null;
      if (!master) {
        const gain = ctx.createGain(), compressor = ctx.createDynamicsCompressor();
        gain.gain.value = 3;
        compressor.threshold.value = -18;
        compressor.ratio.value = 4;
        compressor.attack.value = 0.003;
        compressor.release.value = 0.12;
        gain.connect(compressor);
        compressor.connect(ctx.destination);
        master = gain;
      }
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

  function tone(c, type, f0, f1, t0, dur, peak, vibrato = false) {
    const osc = c.createOscillator(), g = c.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(f0, t0);
    if (f1 !== f0) osc.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t0 + dur);
    g.gain.setValueAtTime(0.0008, t0);
    g.gain.linearRampToValueAtTime(peak, t0 + Math.min(0.008, dur * 0.25));
    g.gain.exponentialRampToValueAtTime(0.0008, t0 + dur);
    if (vibrato) {
      const lfo = c.createOscillator(), depth = c.createGain();
      lfo.frequency.value = 5.5;
      depth.gain.value = 6;
      lfo.connect(depth);
      depth.connect(osc.detune);
      clean(lfo, [depth]);
      lfo.start(t0);
      lfo.stop(t0 + dur + 0.004);
    }
    osc.connect(g);
    g.connect(master);
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
    g.connect(master);
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
    count(name) { return counts.get(name) || 0; },
    /** @param {number} [step] */
    tick(step = 0) {
      const now = nowMs();
      if (now - lastTick < 35) return false;
      lastTick = now;
      const c = readyCtx("tick");
      if (!c) return false;
      const k = Math.max(-6, Math.min(12, +step || 0));
      burst(c, "bandpass", 1480 * Math.pow(2, k * 0.03), 4.5, c.currentTime, 0.018, 0.042);
      return true;
    },
    /** @param {number} [step] */
    hop(step = 0) {
      const c = readyCtx("hop");
      if (!c) return false;
      const k = Math.max(0, Math.min(12, +step || 0));
      const f0 = 330 * Math.pow(2, k / 18);
      tone(c, "triangle", f0, f0 * 1.28, c.currentTime, 0.055, 0.085);
      return true;
    },
    snap() {
      const c = readyCtx("snap");
      if (!c) return false;
      const t = c.currentTime;
      burst(c, "highpass", 2200, 1.2, t, 0.016, 0.052);
      tone(c, "sine", 620, 420, t, 0.045, 0.055);
      tone(c, "sine", 1240, 1240, t, 0.045, 0.055 * 0.18);
      return true;
    },
    tap() {
      const c = readyCtx("tap");
      if (!c) return false;
      tone(c, "sine", 880, 660, c.currentTime, 0.020, 0.045);
      return true;
    },
    right() {
      const c = readyCtx("right");
      if (!c) return false;
      const t = c.currentTime;
      tone(c, "triangle", 523.25, 523.25, t, 0.11, 0.075);
      tone(c, "triangle", 783.99, 783.99, t + 0.065, 0.12, 0.08);
      return true;
    },
    nudge() {
      const c = readyCtx("nudge");
      if (!c) return false;
      const t = c.currentTime;
      for (const [from, to, delay, duration, peak] of [[440, 370, 0, 0.04, 0.06], [392, 330, 0.048, 0.045, 0.055]]) {
        tone(c, "sine", from, to, t + delay, duration, peak);
        tone(c, "sine", from * 2, to * 2, t + delay, duration, peak * 0.35);
      }
      return true;
    },
    discover() {
      const c = readyCtx("discover");
      if (!c) return false;
      tone(c, "triangle", 659.25, 659.25, c.currentTime, 0.09, 0.075 * 0.7);
      return true;
    },
    lit() {
      const c = readyCtx("lit");
      if (!c) return false;
      const t = c.currentTime;
      [523.25, 659.25, 783.99].forEach((f, i) => tone(c, "triangle", f, f, t + i * 0.075, 0.32, 0.055));
      const tail = t + 3 * 0.075;
      tone(c, "triangle", 1046.5, 1046.5, tail, 0.7, 0.055, true);
      tone(c, "sine", 1567.98, 1567.98, tail, 0.7, 0.055 * 0.25);
      return true;
    },
  };
}
/* curio-sfx end */

export { createSfx };
export const Sfx = createSfx();
