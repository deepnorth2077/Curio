import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../../preview/preferences.js", import.meta.url), "utf8");

function preview(saved = {}) {
  const events = new EventTarget(), media = new EventTarget(), values = new Map(Object.entries(saved));
  const root = {dataset:{}}, css = new Map();
  media.matches = false;
  const context = vm.createContext({
    document:{documentElement:root}, matchMedia:() => media,
    localStorage:{getItem:k => values.get(k), setItem:(k,v) => values.set(k,v)},
    getComputedStyle:() => ({getPropertyValue:key => css.get(key) ?? ""}),
    addEventListener:events.addEventListener.bind(events),
  });
  const prefs = vm.runInContext(source + "\ncreatePreviewPreferences({dark:{accent:'#abc'}})", context);
  return {prefs, media, css, values, root, storage(key) {
    events.dispatchEvent(Object.assign(new Event("storage"), {key}));
  }};
}

test("试玩读取设备偏好与扩展色位；未登记的外壳色不发给模块", () => {
  const {prefs, css, root} = preview({"curio.theme":"dark", "curio.muted":"1"});
  css.set("--curio-palette-keys", "accent ocean invalid");
  css.set("--ocean", "#123456"); css.set("--invalid", "invalid"); css.set("--private", "#abc");
  assert.equal(root.dataset.theme, "dark");
  assert.equal(prefs.muted(), true);
  assert.deepEqual(JSON.parse(JSON.stringify(prefs.themePayload())), {
    scheme:"dark", palette:{accent:"#abc", ocean:"#123456"},
  });
});

test("同页切换、系统变化和其他标签的偏好即时下发，离开活动即取消", () => {
  const {prefs, values, root, media, storage} = preview();
  const messages = [];
  const leave = prefs.connect((type,payload) => messages.push([type,payload.scheme ?? payload.muted]));
  media.matches = true; media.dispatchEvent(new Event("change"));
  prefs.toggleTheme(); prefs.toggleMute();
  assert.equal(values.get("curio.theme"), "light");
  assert.equal(values.get("curio.muted"), "1");
  values.delete("curio.theme"); values.delete("curio.muted"); storage(null);
  assert.equal(root.dataset.theme, undefined);
  leave();
  prefs.toggleMute();
  assert.deepEqual(messages, [["theme","dark"], ["theme","light"], ["mute",true], ["theme","dark"], ["mute",false]]);
});
