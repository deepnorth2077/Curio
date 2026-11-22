// 写 navigator.chosen（docs/specs/navigators.md 第 3 节，PR 2）：范围无的 learner 事件，rev = 当前生效 rev + 1，
// 走 committer 的同一套摄入校验；投影出写下的那一位。
import { test } from "node:test";
import assert from "node:assert/strict";
import { openSession, assembleLearner, submitNavigatorChoice } from "../session.js";
import { projectNavigator } from "../../kernel/js/navigator.js";
import { createFakeStore, fixtures, rebuild } from "./fake-store.js";

test("组装：没有 attempt_id、content，actor 是孩子本人", () => {
  const e = JSON.parse(assembleLearner({ event_id: "evt_x", identity: { learner_id: "lrn_a", device_id: "dev_b" }, device_seq: 7,
    occurred_at: "2026-11-22T00:00:00.000Z", verb: "navigator.chosen", payload: { rev: 1, navigator_id: "nav.ring" } }));
  assert.deepEqual(Object.keys(e).sort(), ["actor", "device_id", "device_seq", "event_id", "learner_id", "occurred_at", "payload", "schema", "verb"]);
  assert.deepEqual(e.actor, { type: "learner", id: "lrn_a" });
  assert.equal(e.device_seq, 7);
});

test("第一次 rev 是 1，再换一次是 2；摄入接收，投影是后选的那位，重启以后还是它", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  const a = await submitNavigatorChoice(s, fx, "nav.ring");
  assert.equal(a.result, "accepted");
  assert.deepEqual(JSON.parse(a.raw).payload, { rev: 1, navigator_id: "nav.ring" });
  const b = await submitNavigatorChoice(s, fx, "nav.lamp");
  assert.deepEqual(JSON.parse(b.raw).payload, { rev: 2, navigator_id: "nav.lamp" });
  assert.equal(projectNavigator(s.log.events()).navigator_id, "nav.lamp");
  assert.equal(projectNavigator(rebuild(store).events()).navigator_id, "nav.lamp");
  assert.equal(s.log.quarantined().length, 0);
});

test("反例：navigator_id 格式不对时摄入不接收，投影不变", async () => {
  const store = createFakeStore();
  const fx = fixtures();
  const s = await openSession(store, fx);
  await submitNavigatorChoice(s, fx, "nav.ring");
  await assert.rejects(submitNavigatorChoice(s, fx, "Nav.Bad"));
  assert.equal(projectNavigator(s.log.events()).navigator_id, "nav.ring");
});
