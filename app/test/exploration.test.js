import test from "node:test";
import assert from "node:assert/strict";
import { mountExploration, stationCount } from "../exploration.js";

const tick = () => new Promise((resolve) => setImmediate(resolve));
const content = {
  activity_id: "act.simulation.chromosome-pack-01", node_id: "biology.genetics.chromosome-intro",
  activity_kind: "simulation", activity_version: 2, content_release: "test-release",
};

function setup(options = {}, submit) {
  const win = new EventTarget(), frame = new EventTarget();
  const attributes = {}, events = [], statuses = [], messages = [];
  let timeout, serial = 0;
  win.setTimeout = (fn) => { timeout = fn; return 1; };
  win.clearTimeout = () => { timeout = null; };
  win.requestAnimationFrame = (fn) => setTimeout(fn, 0);
  win.cancelAnimationFrame = clearTimeout;
  frame.setAttribute = (key, value) => { attributes[key] = value; };
  frame.style = {};
  frame.contentWindow = { postMessage: (m) => messages.push(m) };
  frame.remove = () => { frame.removed = true; };
  const signals = (type, payload = {}, overrides = {}) => {
    const event = new Event("message");
    Object.assign(event, {origin: "null", source: frame.contentWindow, data: {contract:"activity/1.1", type, payload}, ...overrides});
    win.dispatchEvent(event);
  };
  const session = { identity: {learner_id:"learner", device_id:"device"}, committer: {
    get nextSeq() { return events.length + 1; },
    freeze() { this.frozen = true; },
    async submit(raw) {
      const e = JSON.parse(raw);
      if (submit) await submit(e);
      events.push(e);
    },
  }};
  const handle = mountExploration({
    container: {ownerDocument:{defaultView:win, createElement:()=>frame},append(){}},
    manifest: {id:(options.content ?? content).activity_id, contract:"activity/1.1", type:"simulation",
      version:(options.content ?? content).activity_version,
      targets:[(options.content ?? content).node_id], age_band:"G3-4", emits:["observed","predicted","answered"]},
    html: "<!DOCTYPE html><html><head><title>活动</title></head><body></body></html>",
    session, now:()=>new Date(0).toISOString(), ids:{attempt:()=>"attempt",event:()=>String(++serial)},
    content, onStatus:(s)=>statuses.push(s), ...options,
  });
  const load = () => frame.dispatchEvent(new Event("load"));
  const progress = (station) => signals("event", {verb:"observed", result:{station, item:"station-complete"}});
  async function start() { signals("ready"); load(); await tick(); }
  return {handle, progress, load, start, timeout:()=>timeout?.(), signals, attributes, frame, events, statuses, messages, session};
}

test("current opaque frame, checked envelope, one init after ready and the saved start", async () => {
  const h = setup({doneStations:[1,1,0,5]});
  assert.equal(h.attributes.sandbox, "allow-scripts");
  assert.match(h.frame.srcdoc, /^<!DOCTYPE html><meta http-equiv="Content-Security-Policy"/);
  assert.match(h.frame.srcdoc, /default-src 'none'/);
  h.load();
  h.signals("ready", {}, {source:{}});
  h.signals("ready", {}, {origin:"https://example.invalid"});
  h.signals("ready", {}, {data:{contract:"other", type:"ready", payload:{}}});
  h.signals("ready", {extra:1});
  h.progress(1);
  await tick();
  assert.deepEqual(h.messages, []);
  assert.deepEqual(h.events, []);
  h.signals("ready"); h.signals("ready"); await tick();
  assert.deepEqual(h.messages.map(m=>m.payload.completed_stations), [[1]]);
  assert.equal(h.messages[0].payload.activity_completed, false);
  assert.deepEqual(h.events.map(e=>e.verb), ["attempt.started"]);
  assert.equal(h.frame.inert, false);
  await h.handle.leave();
});

test("only ordered, declared station markers persist; completion drains before concurrent leave", async () => {
  const h = setup();
  await h.start();
  h.signals("complete");
  h.signals("event", {verb:"predicted",result:{station:1,item:"station-complete"}});
  h.signals("event", {verb:"unexpected",result:{station:1,item:"station-complete"}});
  h.signals("event", {verb:"observed",result:{station:1,item:"read-all"}});
  h.signals("event", {verb:"observed",result:{station:1,item:"station-complete",extra:1}});
  h.signals("event", {verb:"observed",result:{station:"1",item:"station-complete"}});
  h.progress(5); h.progress(2); h.progress(1); h.progress(1);
  for (let i=0;i<100;i++) { h.signals("state",{station:1,length_m:i}); h.signals("resize",{h:600+i}); }
  h.progress(2); h.progress(3); h.progress(4);
  h.signals("complete", {extra:1}); h.signals("complete"); h.signals("complete");
  await Promise.all([h.handle.leave(), h.handle.leave()]);
  h.signals("ready"); h.progress(1); await tick();
  assert.deepEqual(h.events.map(e=>e.verb), ["attempt.started", ...Array(4).fill("sim.observed"), "attempt.completed"]);
  assert.deepEqual(h.events.slice(1,5).map(e=>e.payload), [1,2,3,4].map(value=>({observable:"station.completed",value})));
  assert.deepEqual(h.events.map(e=>e.device_seq), [1,2,3,4,5,6]);
  assert.ok(h.frame.removed);
});

test("saved stations allow finishing a former visit; completed activities replay without writes", async () => {
  const h = setup({doneStations:[1,2,3,4]}); await h.start(); h.signals("complete"); await tick(); await h.handle.leave();
  assert.deepEqual(h.events.map(e=>e.verb), ["attempt.started","attempt.completed"]);
  const replay = setup({doneStations:[1,2,3,4],activityCompleted:true}); await replay.start();
  assert.equal(replay.messages[0].payload.activity_completed,true);
  replay.progress(1); replay.signals("complete"); await replay.handle.leave();
  assert.deepEqual(replay.events,[]);
});

test("a three-station exploration completes after its own last station and refuses a fourth", async () => {
  const math = {...content, activity_id:"act.simulation.fair-cut-01", node_id:"math.fraction.unit-fraction", activity_version:1};
  assert.equal(stationCount(math.activity_id), 3);
  assert.equal(stationCount("act.simulation.chocolate-split-01"), 0);
  const h = setup({content:math});
  await h.start();
  h.progress(1); h.progress(2); h.progress(4);
  h.signals("complete"); await tick();
  assert.deepEqual(h.events.map(e=>e.verb), ["attempt.started","sim.observed","sim.observed"]);
  h.progress(3); h.signals("complete"); await tick(); await h.handle.leave();
  assert.deepEqual(h.events.map(e=>e.verb), ["attempt.started", ...Array(3).fill("sim.observed"), "attempt.completed"]);
  assert.deepEqual(h.events.slice(1,4).map(e=>e.payload.value), [1,2,3]);
  const again = setup({content:math, doneStations:[1,2,3,4]}); await again.start();
  assert.deepEqual(again.messages[0].payload.completed_stations, [1,2,3]);
});

test("an incomplete visit, timeout, and second navigation terminate once", async () => {
  const h = setup(); await h.start(); h.progress(1); await h.handle.leave();
  assert.equal(h.events.at(-1).payload.reason, "left");
  const slow = setup(); slow.timeout(); await tick(); slow.load(); slow.signals("ready"); await tick();
  assert.deepEqual(slow.statuses, ["loading","timeout"]);
  assert.deepEqual(slow.events, []);
  const nav = setup(); await nav.start(); nav.progress(1); nav.load(); nav.progress(2); await nav.handle.leave();
  assert.deepEqual(nav.statuses,["loading","active","navigation"]);
  assert.equal(nav.events.at(-1).payload.reason,"error");
  assert.equal(nav.events.length,3);
});

test("stop on failed checkpoint without issuing later writes, or after loss of writer ownership", async () => {
  const jobs = [];
  const h = setup({}, async e => { jobs.push(e.verb); if(e.verb==="sim.observed") throw Error("storage"); });
  await h.start(); h.progress(1); h.progress(2); await assert.rejects(h.handle.leave(), /storage/);
  assert.equal(h.session.committer.frozen,true);
  assert.deepEqual(jobs, ["attempt.started","sim.observed"]);
  assert.deepEqual(h.statuses, ["loading","active","failed"]);
  assert.ok(h.frame.removed);
  const locked = setup(); await locked.start(); locked.progress(1); locked.handle.destroy(); await locked.handle.leave();
  assert.deepEqual(locked.events.map(e=>e.verb), ["attempt.started"]);
});

test("resize before the first ready is bounded, coalesced and does not block completion", async () => {
  const h = setup();
  h.signals("resize", {h:480}); h.signals("resize", {h:650});
  assert.equal(h.frame.style.height, undefined);
  await h.start();
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal(h.frame.style.height,"650px");
  h.signals("resize", {h:1e6});
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal(h.frame.style.height,"2400px");
  await h.handle.leave();
});
