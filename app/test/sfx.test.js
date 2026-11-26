import test from "node:test";
import assert from "node:assert/strict";
import { createSfx } from "../sfx.js";

function makeFakeAudio(initialState = "running") {
  const instances = [];
  class FakeParam {
    constructor() { this.ops = []; }
    setValueAtTime(v, t) { this.ops.push(["set", v, t]); }
    linearRampToValueAtTime(v, t) { this.ops.push(["lin", v, t]); }
    exponentialRampToValueAtTime(v, t) { this.ops.push(["exp", v, t]); }
  }
  class FakeNode {
    constructor(kind) { this.kind = kind; this.connected = []; this.disconnected = false; }
    connect(dest) { this.connected.push(dest); return dest; }
    disconnect() { this.disconnected = true; }
  }
  class FakeAudioContext {
    constructor() {
      this.state = initialState;
      this.currentTime = 1.0;
      this.sampleRate = 44100;
      this.destination = { kind: "dest" };
      this.nodes = [];
      this.resumed = 0;
      instances.push(this);
    }
    resume() { this.resumed++; this.state = "running"; return Promise.resolve(); }
    createGain() {
      const n = new FakeNode("gain");
      n.gain = new FakeParam();
      this.nodes.push(n);
      return n;
    }
    createOscillator() {
      const n = new FakeNode("osc");
      n.type = "sine";
      n.frequency = new FakeParam();
      n.start = (t) => { n.startedAt = t; };
      n.stop = (t) => { n.stoppedAt = t; };
      this.nodes.push(n);
      return n;
    }
    createBiquadFilter() {
      const n = new FakeNode("filter");
      n.type = "bandpass";
      n.frequency = new FakeParam();
      n.Q = new FakeParam();
      this.nodes.push(n);
      return n;
    }
    createBuffer(_ch, len, sr) {
      const arr = new Float32Array(len);
      return { length: len, sampleRate: sr, getChannelData: () => arr };
    }
    createBufferSource() {
      const n = new FakeNode("bufsrc");
      n.start = (t) => { n.startedAt = t; };
      n.stop = (t) => { n.stoppedAt = t; };
      this.nodes.push(n);
      return n;
    }
  }
  return { FakeAudioContext, instances };
}

test("all 7 semantic sound slots stay within gain/duration bounds and disconnect nodes on ended", () => {
  const { FakeAudioContext, instances } = makeFakeAudio();
  let clock = 100;
  const sfx = createSfx({ AudioCtx: FakeAudioContext, nowMs: () => clock });

  assert.equal(sfx.tick(2), true);
  clock += 50;
  assert.equal(sfx.hop(3), true);
  assert.equal(sfx.snap(), true);
  assert.equal(sfx.tap(), true);
  assert.equal(sfx.right(), true);
  assert.equal(sfx.nudge(), true);
  assert.equal(sfx.lit(), true);

  assert.equal(instances.length, 1);
  const ctx = instances[0];
  const gains = ctx.nodes.filter((n) => n.kind === "gain");
  assert.ok(gains.length >= 11);

  for (const g of gains) {
    for (const [, val] of g.gain.ops) {
      assert.ok(val <= 0.12, `gain ${val} exceeds 0.12 ceiling`);
      assert.ok(val > 0, `gain ${val} must be positive for exponential ramps`);
    }
  }
  // 第一个声位是 tick，峰值不超过 0.05
  const tickPeak = Math.max(...gains[0].gain.ops.map(([, v]) => v));
  assert.ok(tickPeak <= 0.05, `tick peak ${tickPeak} exceeds 0.05`);

  // 所有声源在 ended 后断开连接回收节点
  const sources = ctx.nodes.filter((n) => n.kind === "osc" || n.kind === "bufsrc");
  assert.ok(sources.length >= 11);
  for (const s of sources) {
    assert.ok(s.stoppedAt - ctx.currentTime <= 0.6, `source duration too long: ${s.stoppedAt - ctx.currentTime}`);
    s.onended();
  }
  for (const n of ctx.nodes) assert.equal(n.disconnected, true, `${n.kind} was not disconnected`);
});

test("muted: true creates zero AudioContext instances and zero audio nodes", () => {
  const { FakeAudioContext, instances } = makeFakeAudio();
  const sfx = createSfx({ AudioCtx: FakeAudioContext, nowMs: () => 100 });
  sfx.setMuted(true);
  assert.equal(sfx.muted(), true);
  for (const fn of [() => sfx.tick(), () => sfx.hop(), () => sfx.snap(), () => sfx.tap(), () => sfx.right(), () => sfx.nudge(), () => sfx.lit()]) {
    assert.equal(fn(), false);
  }
  assert.equal(instances.length, 0);
});

test("tick throttles repeated calls within 35ms", () => {
  const { FakeAudioContext, instances } = makeFakeAudio();
  let clock = 1000;
  const sfx = createSfx({ AudioCtx: FakeAudioContext, nowMs: () => clock });
  assert.equal(sfx.tick(0), true);
  const countAfterFirst = instances[0].nodes.length;
  clock = 1015;
  assert.equal(sfx.tick(1), false);
  clock = 1034;
  assert.equal(sfx.tick(2), false);
  assert.equal(instances[0].nodes.length, countAfterFirst);
  clock = 1035;
  assert.equal(sfx.tick(3), true);
  assert.ok(instances[0].nodes.length > countAfterFirst);
});

test("gesture gate unlocks suspended AudioContext on first pointerdown and missing AudioContext never throws", () => {
  const noAudio = createSfx({ AudioCtx: null });
  assert.doesNotThrow(() => {
    noAudio.tick(); noAudio.hop(); noAudio.snap(); noAudio.tap(); noAudio.right(); noAudio.nudge(); noAudio.lit();
  });

  const target = new EventTarget();
  const { FakeAudioContext, instances } = makeFakeAudio("suspended");
  const gated = createSfx({ AudioCtx: FakeAudioContext, requireGesture: true, eventTarget: target, nowMs: () => 50 });
  // 手势前不创建 AudioContext，免得浏览器报控制台自动播放警告
  assert.equal(gated.tap(), false);
  assert.equal(instances.length, 0);

  target.dispatchEvent(new Event("pointerdown"));
  assert.equal(instances.length, 1);
  assert.equal(instances[0].resumed, 1);
  assert.equal(gated.tap(), true);
});
