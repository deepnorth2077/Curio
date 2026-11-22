// One verified release entry, one opaque iframe, one ordered stream of local writes.
import { assemble, localReceipt } from "./session.js";

const CONTRACT = "activity/1.1";
// Explorations this shell hosts, with each module's station count (slice-5a; zero-to-one in #233).
// The count bounds station numbers and decides when the whole exploration is done.
const stationCounts = new Map([
  ["act.simulation.cell-zoom-01", 4],
  ["act.simulation.chromosome-pack-01", 4],
  ["act.simulation.dna-book-01", 4],
  // 「0 和 1 之间」19 颗（#233）
  ["act.simulation.cross-cut-01", 3],
  ["act.simulation.fair-cut-01", 3],
  ["act.simulation.grow-shrink-01", 3],
  ["act.simulation.hop-line-01", 3],
  ["act.simulation.hundred-grid-01", 3],
  ["act.simulation.match-cuts-01", 3],
  ["act.simulation.measuring-cup-01", 3],
  ["act.simulation.mix-drink-01", 3],
  ["act.simulation.place-slots-01", 3],
  ["act.simulation.pour-cups-01", 3],
  ["act.simulation.ratio-chute-01", 3],
  ["act.simulation.recut-01", 3],
  ["act.simulation.share-table-01", 3],
  ["act.simulation.slide-rule-01", 3],
  ["act.simulation.stretch-bar-01", 3],
  ["act.simulation.stretch-frame-01", 3],
  ["act.simulation.three-rulers-01", 3],
  ["act.simulation.whose-half-01", 3],
  ["act.simulation.zoom-line-01", 3],
  // 「乘法的秘密」掰巧克力（#54）
  ["act.simulation.chocolate-split-01", 3],
]);
export const supportedExploration = (id) => stationCounts.has(id);
export const stationCount = (id) => stationCounts.get(id) ?? 0;

const policy = [
  "default-src 'none'", "script-src 'unsafe-inline'", "style-src 'unsafe-inline'",
  "img-src data:", "base-uri 'none'", "form-action 'none'", "connect-src 'none'",
].join("; ");

function isolatedDocument(html) {
  if (typeof html !== "string" || !/^<!doctype html>/i.test(html)) throw new Error("活动入口格式有误");
  // srcdoc inherits its parent's base URL. Put restrictions before any source markup.
  return html.replace(/^<!doctype html>/i, (doctype) =>
    doctype + '<meta http-equiv="Content-Security-Policy" content="' + policy + '">');
}

function record(value) {
  return value !== null && typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype;
}
function exact(value, keys) {
  return record(value) && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}
function stationNumber(n, count) {
  return Number.isInteger(n) && n >= 1 && n <= count;
}

/** Mount only after the release loader verifies the manifest and HTML bytes. */
export function mountExploration({
  container, manifest, html, session, ids, now, content, mode = "first",
  doneStations = [], activityCompleted = false, onStatus = () => {},
}) {
  if (!supportedExploration(manifest.id) || manifest.contract !== CONTRACT ||
      manifest.type !== "simulation" || manifest.id !== content.activity_id ||
      manifest.version !== content.activity_version || content.activity_kind !== "simulation" ||
      !manifest.targets.includes(content.node_id) || !Array.isArray(manifest.emits) ||
      !manifest.emits.includes("observed")) throw new Error("活动清单和入口不符");
  const srcdoc = isolatedDocument(html);
  const doc = container.ownerDocument;
  const win = doc.defaultView;
  const frame = doc.createElement("iframe");
  frame.setAttribute("sandbox", "allow-scripts");
  frame.setAttribute("referrerpolicy", "no-referrer");
  frame.title = manifest.title;
  frame.srcdoc = srcdoc;
  frame.inert = true;
  frame.style.visibility = "hidden";

  const count = stationCount(manifest.id);
  const previous = [...new Set(doneStations.filter((n) => stationNumber(n, count)))].sort((a,b) => a-b);
  const stations = new Set(previous);
  const attempt = activityCompleted ? null : ids.attempt();
  let phase = "loading", ready = false, loaded = false, accepting = true;
  let started = false, ended = false, aborted = false, startedAt, failure;
  let queue = Promise.resolve();
  let timer, animation, pendingHeight;

  // Both the event ID and device_seq are assigned at the front of this queue.
  async function write(verb, payload) {
    const event_id = ids.event(), occurred_at = now(), identity = session.identity;
    const raw = assemble({
      event_id, occurred_at, device_seq: session.committer.nextSeq, identity,
      actor: { type: "learner", id: identity.learner_id }, verb, attempt_id: attempt, content, payload,
    });
    try {
      await session.committer.submit(raw, localReceipt(event_id, now()));
    } catch (error) {
      // Do not let another activity claim a sequence after an uncertain transaction.
      session.committer.freeze();
      throw error;
    }
  }
  function detach() {
    accepting = false;
    win.clearTimeout(timer);
    if (animation !== undefined) win.cancelAnimationFrame(animation);
    win.removeEventListener("message", receive);
    frame.removeEventListener("load", load);
    frame.remove();
  }
  function enqueue(job) {
    queue = queue.then(() => { if (!aborted) return job(); }).catch((error) => {
      // The storage transaction may already have committed. Recovery replays the journal.
      if (aborted) return; // lock-loss teardown has already replaced this screen
      failure = error instanceof Error ? error : new Error("探索中断了");
      aborted = true;
      detach();
      onStatus("failed");
    });
    return queue;
  }
  function stop(status, reason) {
    if (!accepting) return queue;
    detach();
    // A pending start or checkpoint was accepted before leaving. Drain it first.
    return enqueue(async () => {
      if (started && !ended) {
        await write("attempt.abandoned", { reason });
        ended = true;
      }
      if (!aborted && status) onStatus(status);
    });
  }
  function activate() {
    if (!loaded || !ready || phase !== "loading") return;
    phase = "starting";
    win.clearTimeout(timer);
    enqueue(async () => {
      if (attempt) {
        startedAt = Date.now();
        await write("attempt.started", { mode });
        started = true;
      }
      if (!accepting) return;
      phase = "active";
      frame.contentWindow.postMessage({
        contract: CONTRACT, type: "init", payload: {
          age_band: manifest.age_band, lang: "zh-CN", phase: "observe",
          completed_stations: previous, activity_completed: activityCompleted, question_available: false,
        },
      }, "*"); // sandboxed srcdoc has an opaque origin.
      frame.inert = false;
      frame.style.visibility = "";
      if (pendingHeight !== undefined) resize(pendingHeight);
      onStatus("active");
    });
  }
  function load() {
    if (loaded) { stop("navigation", "error"); return; }
    loaded = true;
    activate();
  }
  function resize(height) {
    if (!Number.isFinite(height) || height <= 0) return;
    pendingHeight = Math.min(2400, Math.max(240, Math.ceil(height)));
    if ((phase !== "active" && phase !== "completed") || animation !== undefined) return;
    animation = win.requestAnimationFrame(() => {
      animation = undefined;
      if (accepting) frame.style.height = pendingHeight + "px";
    });
  }
  function receive(event) {
    if (!accepting || event.source !== frame.contentWindow || event.origin !== "null" || event.ports?.length) return;
    const m = event.data;
    if (!exact(m, ["contract", "type", "payload"]) || m.contract !== CONTRACT) return;
    const p = m.payload;
    if (m.type === "ready" && phase === "loading" && exact(p, [])) {
      ready = true;
      activate();
      return;
    }
    if (m.type === "resize" && exact(p, ["h"])) { resize(p.h); return; }
    // No handler for state, transient lesson observations, private text, AI, or grading.
    if (phase !== "active" || !attempt) return;
    if (m.type === "event" && exact(p, ["verb", "result"]) && p.verb === "observed" && manifest.emits.includes(p.verb)) {
      const result = p.result;
      if (!exact(result, ["station", "item"]) || result.item !== "station-complete" ||
          !stationNumber(result.station, count) || stations.has(result.station)) return;
      for (let n = 1; n < result.station; n++) if (!stations.has(n)) return;
      const value = result.station;
      stations.add(value);
      enqueue(() => write("sim.observed", { observable: "station.completed", value }));
    } else if (m.type === "complete" && exact(p, []) && stations.size === count) {
      phase = "finishing"; // Reserve the terminal event synchronously, including against a simultaneous leave.
      const duration_ms = Math.max(0, Date.now() - startedAt);
      enqueue(async () => {
        await write("attempt.completed", { duration_ms });
        ended = true;
        phase = "completed";
        if (accepting) {
          if (pendingHeight !== undefined) resize(pendingHeight);
          onStatus("completed");
        }
      });
    }
  }

  win.addEventListener("message", receive);
  frame.addEventListener("load", load);
  timer = win.setTimeout(() => stop("timeout", "timeout"), 3000);
  onStatus("loading");
  container.append(frame);
  return {
    async leave() {
      await stop(null, "left");
      if (failure) throw failure;
    },
    // On loss of writer ownership, queued and future writes must stop immediately.
    destroy() { aborted = true; detach(); },
  };
}
