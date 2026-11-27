import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createSfx as shellFactory } from "../sfx.js";

function kitFactory(version) {
  const source = readFileSync(new URL(`../../kit/${version}/kit.js`, import.meta.url), "utf8");
  const factory = source.split("/* curio-sfx begin */")[1].split("/* curio-sfx end */")[0];
  return runInNewContext(factory + "\ncreateSfx", { performance });
}

const factories = [["shell", shellFactory], ["kit/1", kitFactory(1)], ["kit/2", kitFactory(2)]];

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
    createDynamicsCompressor() {
      const n = new FakeNode("compressor");
      for (const key of ["threshold", "ratio", "attack", "release"]) n[key] = new FakeParam();
      this.nodes.push(n);
      return n;
    }
    createOscillator() {
      const n = new FakeNode("osc");
      n.type = "sine";
      n.detune = new FakeParam();
      n.frequency = new FakeParam();
      n.start = (t) => { n.startedAt = t; };
      n.stop = (t) => { n.stoppedAt = t ?? this.currentTime; };
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
      n.stop = (t) => { n.stoppedAt = t ?? this.currentTime; };
      this.nodes.push(n);
      return n;
    }
  }
  return { FakeAudioContext, instances };
}

for (const [name, createSfx] of factories) {
  const v2 = name !== "kit/1";
  const slots = ["tick", "hop", "snap", "tap", "right", "nudge", "lit"];
  if (v2) slots.push("discover");
  const prefix = name + " / ";
  test(prefix + "all semantic sound slots stay within gain/duration bounds and disconnect nodes on ended", () => {
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
    if (v2) assert.equal(sfx.discover(), true);

    assert.equal(instances.length, 1);
    const ctx = instances[0];
    const gains = ctx.nodes.filter((n) => n.kind === "gain" && n.gain.ops.length);
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
      assert.ok(s.stoppedAt - ctx.currentTime <= (v2 ? 0.93 : 0.6), `source duration too long: ${s.stoppedAt - ctx.currentTime}`);
      s.onended();
    }
    const connected = ctx.nodes.filter(n => !n.disconnected);
    assert.deepEqual(connected.map(n => n.kind), v2 ? ["gain", "compressor"] : []);
  });

  test(prefix + "muted: true creates zero AudioContext instances and zero audio nodes", () => {
    const { FakeAudioContext, instances } = makeFakeAudio();
    const sfx = createSfx({ AudioCtx: FakeAudioContext, nowMs: () => 100 });
    sfx.setMuted(true);
    assert.equal(sfx.muted(), true);
    for (const slot of slots) {
      assert.equal(sfx[slot](), false);
      if (v2) assert.equal(sfx.count(slot), 1);
    }
    assert.equal(instances.length, 0);
    assert.equal(sfx.seq(), slots.length);
  });

  test(prefix + "tick throttles repeated calls within 35ms", () => {
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
    assert.equal(sfx.seq(), 2);
    if (v2) assert.equal(sfx.count("tick"), 2);
  });

  test(prefix + "missing AudioContext never throws", () => {
    const noAudio = createSfx({ AudioCtx: null });
    assert.doesNotThrow(() => {
      for (const slot of slots) assert.equal(noAudio[slot](), false);
    });
  });

  for (const gesture of ["pointerdown", "touchend", "keydown", "click"]) {
    test(prefix + "unlocks suspended audio on " + gesture, () => {
      const target = new EventTarget();
      const { FakeAudioContext, instances } = makeFakeAudio("suspended");
      const gated = createSfx({ AudioCtx: FakeAudioContext, requireGesture: true, eventTarget: target, nowMs: () => 50 });
      // 手势前不创建 AudioContext，免得浏览器报控制台自动播放警告
      assert.equal(gated.tap(), false);
      assert.equal(instances.length, 0);

      target.dispatchEvent(new Event(gesture));
      assert.equal(instances.length, 1);
      assert.equal(instances[0].resumed, 1);
      assert.equal(gated.tap(), true);
    });
  }

  test(prefix + "muting cuts both playing and scheduled notes and unmuting cannot revive them", () => {
    const { FakeAudioContext, instances } = makeFakeAudio();
    const sfx = createSfx({ AudioCtx: FakeAudioContext });
    sfx.lit();
    const ctx = instances[0];
    const notes = ctx.nodes.filter((node) => node.kind === "osc");
    assert.equal(notes.length, v2 ? 6 : 4);
    assert.ok(notes.some((node) => node.startedAt > ctx.currentTime));
    sfx.setMuted(true);
    for (const note of notes) {
      assert.equal(note.disconnected, true);
      assert.ok(note.stoppedAt <= ctx.currentTime);
    }
    sfx.setMuted(false);
    assert.equal(sfx.tap(), true);
    for (const note of notes) {
      note.onended();
      assert.equal(note.disconnected, true);
    }
  });
}

test("identical sample rates produce the same noise in independent shell and kit contexts", () => {
  function tickNoise(factory) {
    const { FakeAudioContext, instances } = makeFakeAudio();
    factory({ AudioCtx: FakeAudioContext }).tick(2);
    const source = instances[0].nodes.find((node) => node.kind === "bufsrc");
    return source.buffer.getChannelData(0);
  }
  const samples = tickNoise(shellFactory);
  assert.ok(samples.some((value) => value > 0.1) && samples.some((value) => value < -0.1));
  for (const [, factory] of factories) assert.deepEqual(tickNoise(factory), samples);
});

for (const [name, createSfx] of factories.filter(([name]) => name !== "kit/1")) {
  test(name + " / selected iPad sound parameters use one shared gain and compressor", () => {
    const { FakeAudioContext, instances } = makeFakeAudio();
    const sfx = createSfx({ AudioCtx: FakeAudioContext });
    const hopFreq = 330 * 2 ** (3 / 18);
    // [wave, start Hz, end Hz, start offset, envelope duration, peak]
    const voices = {
      tick: [],
      hop: [["triangle", hopFreq, hopFreq * 1.28, 0, .055, .085]],
      snap: [["sine", 620, 420, 0, .045, .055], ["sine", 1240, 1240, 0, .045, .055 * .18]],
      tap: [["sine", 880, 660, 0, .020, .045]],
      right: [["triangle", 523.25, 523.25, 0, .11, .075], ["triangle", 783.99, 783.99, .065, .12, .08]],
      nudge: [
        ["sine", 440, 370, 0, .04, .06], ["sine", 880, 740, 0, .04, .06 * .35],
        ["sine", 392, 330, .048, .045, .055], ["sine", 784, 660, .048, .045, .055 * .35],
      ],
      discover: [["triangle", 659.25, 659.25, 0, .09, .075 * .7]],
      lit: [
        ["triangle", 523.25, 523.25, 0, .32, .055], ["triangle", 659.25, 659.25, .075, .32, .055],
        ["triangle", 783.99, 783.99, .15, .32, .055], ["triangle", 1046.5, 1046.5, .225, .7, .055],
        ["sine", 1567.98, 1567.98, .225, .7, .055 * .25],
      ],
    };
    const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} ≠ ${expected}`);
    let offset = 0;
    for (const [slot, expected] of Object.entries(voices)) {
      assert.equal(sfx.count(slot), 0);
      assert.equal(sfx[slot](3), true);
      assert.equal(sfx.count(slot), 1);
      const ctx = instances[0], nodes = ctx.nodes.slice(offset);
      offset = ctx.nodes.length;
      const oscillators = nodes.filter(n => n.kind === "osc" && n.frequency.ops.length);
      assert.equal(oscillators.length, expected.length, slot);
      for (const [i, [wave, start, end, delay, duration, peak]] of expected.entries()) {
        const osc = oscillators[i], envelope = osc.connected[0].gain.ops;
        assert.equal(osc.type, wave);
        close(osc.frequency.ops[0][1], start);
        close(osc.frequency.ops.at(-1)[1], end);
        close(osc.startedAt, ctx.currentTime + delay);
        close(envelope.at(-1)[2], osc.startedAt + duration);
        close(envelope[1][1], peak);
      }
      if (slot === "lit") {
        const lfo = nodes.find(n => n.kind === "osc" && n.frequency.value === 5.5);
        const depth = lfo.connected[0];
        assert.equal(depth.gain.value, 6);
        assert.equal(depth.connected[0], oscillators[3].detune);
        assert.equal(lfo.startedAt, oscillators[3].startedAt);
        assert.equal(lfo.stoppedAt, oscillators[3].stoppedAt);
      }
      const noise = nodes.filter(n => n.kind === "bufsrc");
      assert.equal(noise.length, slot === "tick" || slot === "snap" ? 1 : 0);
      if (noise.length) {
        const filter = noise[0].connected[0], tick = slot === "tick";
        assert.equal(filter.type, tick ? "bandpass" : "highpass");
        close(filter.frequency.ops[0][1], tick ? 1480 * 2 ** (3 * .03) : 2200);
        close(filter.Q.ops[0][1], tick ? 4.5 : 1.2);
        close(filter.connected[0].gain.ops[1][1], tick ? .042 : .052);
        close(noise[0].stoppedAt - noise[0].startedAt, (tick ? .018 : .016) + .004);
      }
    }
    const ctx = instances[0];
    assert.equal(sfx.seq(), Object.keys(voices).length);
    const compressors = ctx.nodes.filter(n => n.kind === "compressor");
    assert.equal(compressors.length, 1);
    const compressor = compressors[0];
    assert.deepEqual(["threshold", "ratio", "attack", "release"].map(k => compressor[k].value), [-18, 4, .003, .12]);
    assert.deepEqual(compressor.connected, [ctx.destination]);
    const inputs = ctx.nodes.filter(n => n.connected.includes(compressor));
    assert.equal(inputs.length, 1);
    const master = inputs[0];
    assert.equal(master.gain.value, 3);
    for (const node of ctx.nodes.filter(n => n.kind === "gain" && n.gain.ops.length)) {
      assert.deepEqual(node.connected, [master]);
    }
  });
}
