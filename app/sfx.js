// 原生 Web Audio 程序化微音效（docs/specs/kit.md 第 2 节）：无背景音乐、无循环音、无外部音频文件。
// 7 个语义声位：tick（棘轮刻度）、hop（跳步）、snap（清脆咔嗒）、tap（纸面轻点）、right（五度上行）、nudge（温和双轻叩）、lit（点亮泛音和弦）。

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

export { createSfx };
export const Sfx = createSfx();
