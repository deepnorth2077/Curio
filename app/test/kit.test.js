import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const kit = readFileSync(new URL("../../kit/1/kit.js", import.meta.url), "utf8");
const darkPalette = {
  bg: "#1E1E1E", pane: "#252525", hover: "#2E2E2E", rule: "#353535",
  ink: "#E4E0D8", text: "#CBC6BC", muted: "#8C887F", accent: "#A797F7",
  "accent-soft": "#2D2943", grip: "#5FC4BE", "grip-soft": "#1F3634",
  sage: "#3C4836", "sage-bg": "#28301F", sky: "#2D3B47", apricot: "#5A4536",
  paper: "#2A2738", good: "#7CC79A", "good-soft": "#203528", bad: "#EF8A72", "bad-soft": "#3A2420",
};

class Element extends EventTarget {
  constructor(tag) {
    super();
    this.tag = tag;
    this.children = [];
    const classes = new Set(), properties = new Map();
    this.classList = {
      contains: (name) => classes.has(name),
      toggle: (name, enable) => enable ? classes.add(name) : classes.delete(name),
    };
    this.style = {
      setProperty: (name, value) => properties.set(name, value),
      removeProperty: (name) => properties.delete(name),
      getPropertyValue: (name) => properties.get(name) ?? "",
    };
  }
  querySelector(tag) { return this.children.find((e) => e.tag === tag) ?? null; }
  append(...elements) { this.children.push(...elements); }
  replaceChildren() { this.children = []; }
  focus() {}
}

function sandbox({ ids = [], standalone = false } = {}) {
  const target = new EventTarget(), root = new Element("html");
  const elements = Object.fromEntries(ids.map(id => [id, new Element("div")]));
  const timers = new Map(), sent = [];
  let clock = 0, timerId = 0;
  const document = {
    documentElement: root, body: new Element("body"),
    getElementById: id => elements[id] ?? null,
    createElement: tag => new Element(tag),
    querySelector: () => null,
  };
  const parent = { postMessage: m => sent.push(m) };
  const context = vm.createContext({
    parent, document, queueMicrotask,
    matchMedia: () => ({ matches: false }),
    performance: { now: () => clock },
    addEventListener: target.addEventListener.bind(target),
    removeEventListener: target.removeEventListener.bind(target),
    setTimeout: (fn, ms) => { timers.set(++timerId, { fn, due: clock + ms }); return timerId; },
    clearTimeout: id => timers.delete(id),
  });
  const run = script => vm.runInContext(script, context);
  run("globalThis.window = globalThis");
  if (standalone) run("globalThis.parent = window");
  run(kit);
  return {
    run, root, elements, sent, target,
    async send(type, payload, contract = "activity/1.2", source = parent) {
      const event = new Event("message");
      Object.assign(event, { source, data: { contract, type, payload } });
      target.dispatchEvent(event);
      await Promise.resolve();
    },
    advance(ms) {
      clock += ms;
      for (const [id, timer] of timers) if (timer.due <= clock) { timers.delete(id); timer.fn(); }
    },
  };
}

test("plain HTML activities share host preferences and keep their own init, theme and mute subscriptions", async () => {
  const s = sandbox();
  s.run(`
    const received = [];
    Host.on("init", p => received.push(p.age_band));
    const offTheme = Host.on("theme", p => received.push(p.scheme));
    Host.on("mute", () => received.push(Sfx.muted()));
    Kit.start(p => received.push("enter:" + p.phase));
  `);
  assert.deepEqual(s.sent.map(m => m.type), ["ready"]);
  await s.send("init", { muted: true }, "activity/1.1");
  await s.send("init", { muted: true }, "activity/1.2", {});
  assert.equal(s.run("received.length"), 0);
  await s.send("init", {
    age_band: "G7-8", phase: "observe", scheme: "dark", palette: darkPalette, muted: true,
    navigator: { faces: { curious: "<circle/>" } }, completed_stations: [1], question_available: false,
  });
  s.advance(600);
  s.target.dispatchEvent(new Event("resize"));
  assert.deepEqual([...s.run("received")], ["G7-8", "enter:observe"]);
  assert.equal(s.root.classList.contains("kit-dark"), true);
  assert.equal(s.root.style.colorScheme, "dark");
  for (const [key, value] of Object.entries(darkPalette)) assert.equal(s.root.style.getPropertyValue("--" + key), value);
  assert.equal(s.run("Sfx.muted()"), true);

  await s.send("theme", { scheme: "light", palette: { accent: "purple", good: "#abc", extra: "#1234" } });
  assert.equal(s.root.classList.contains("kit-dark"), false);
  assert.equal(s.root.style.colorScheme, "light");
  assert.equal(s.root.style.getPropertyValue("--good"), "#abc");
  for (const key of ["accent", "pane", "extra"]) assert.equal(s.root.style.getPropertyValue("--" + key), "");
  s.run("offTheme()");
  await s.send("theme", { scheme: "dark", palette: { accent: "#fff" } });
  assert.equal(s.root.style.getPropertyValue("--accent"), "#fff");
  await s.send("mute", { muted: false });
  await s.send("mute", { muted: true });
  assert.deepEqual([...s.run("received")], ["G7-8", "enter:observe", "light", false, true]);
  s.run("Host.requestHint()");
  assert.equal(s.sent.at(-1).type, "request_hint");
  assert.equal(s.sent.at(-1).contract, "activity/1.2");
});

test("standalone starts immediately; iframe falls back after 300 ms and accepts late init once", async () => {
  const plain = sandbox({ standalone: true });
  plain.run("let entered = 0; Kit.start(() => entered++)");
  assert.equal(plain.run("entered"), 1);
  const s = sandbox();
  s.run("let entered = 0; Kit.start(() => entered++)");
  s.advance(299);
  assert.equal(s.run("entered"), 0);
  s.advance(1);
  assert.equal(s.run("entered"), 1);
  await s.send("init", { muted: true, scheme: "dark" });
  assert.equal(s.run("entered"), 1);
  assert.equal(s.run("Sfx.muted()"), true);
  assert.equal(s.root.style.colorScheme, "dark");
});

const stationIds = ["actions", "hint", "readout", "say", "cue", "qarea"];
test("station activities can offer a continuation or retain replay-only behavior", async () => {
  for (const resume of [false, true]) {
    const s = sandbox({ ids: stationIds });
    s.run(`
      let continued, replayed;
      STATIONS = 3;
      REPLAY[1] = () => { replayed = 1; };
      Kit.start(() => {}, { stations: ${resume ? "{ resume: n => { continued = n; } }" : "{}"} });
    `);
    await s.send("init", { completed_stations: [1, 3], question_available: false });
    const buttons = s.elements.actions.children;
    assert.equal(s.elements.qarea.hidden, true);
    assert.deepEqual(buttons.map(b => b.innerHTML), (resume
      ? ["继续第 2 站", "重玩第 1 站", "从头玩"]
      : ["重玩第 1 站", "从头玩"]).map(label => `<span>${label}</span>`));
    s.advance(500);
    buttons[0].dispatchEvent(new Event("click"));
    if (resume) {
      assert.equal(s.run("continued"), 2);
      s.run('nextOr("下一站", () => {})');
      assert.equal(s.elements.actions.children[0].innerHTML, "<span>下一站</span>");
    } else {
      assert.equal(s.run("replayed"), 1);
      s.run('nextOr("下一站", () => {})');
      assert.equal(s.elements.actions.children[0].innerHTML, "<span>回到选站</span>");
    }
  }
});

test("both fraction renderers produce readable Chinese labels for zero and large integers", () => {
  const s = sandbox();
  for (const [a, b, label] of [[0, 4, "四分之零"], [3, 10, "十分之三"], [999, 1000, "千分之九百九十九"], [110, 105, "一百零五分之一百一十"], [1, 12000, "12000分之一"]]) {
    for (const expression of [`F(${a},${b})`, `fracS(0,0,${a},${b},"fs",7)`]) {
      assert.ok(s.run(expression).includes(`aria-label="${label}"`));
    }
  }
});

test("prediction choices play exactly one right or nudge sound", () => {
  const s = sandbox({ ids: stationIds });
  s.run(`
    const heard = [];
    for (const key of ["right", "nudge", "tap"]) {
      const sound = Sfx[key];
      Sfx[key] = () => { heard.push(key); return sound(); };
    }
    ask("有几块？", [{label:"一",correct:true,feedback:"对了"}, {label:"二",feedback:"再看看"}], () => {});
  `);
  s.advance(500);
  for (const button of s.elements.actions.children) button.dispatchEvent(new Event("click"));
  assert.deepEqual([...s.run("heard")], ["right", "nudge"]);
});
