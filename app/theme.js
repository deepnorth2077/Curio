// 平台 20 个通用色位与明暗/静音本机界面偏好（docs/specs/kit.md 1.3、2.1）。
// 不写学习事件、不进备份文件。

export const PALETTE_KEYS = Object.freeze([
  "bg", "pane", "hover", "rule", "ink", "text", "muted",
  "accent", "accent-soft", "grip", "grip-soft",
  "sage", "sage-bg", "sky", "apricot", "paper",
  "good", "good-soft", "bad", "bad-soft",
]);

export const HEX_COLOR = /^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;

export const LIGHT_PALETTE = Object.freeze({
  bg: "#F5F4EE", pane: "#FBFAF6", hover: "#E7E4D9", rule: "#E0DCD0",
  ink: "#1F1E1C", text: "#3B3833", muted: "#7A766D",
  accent: "#C2603F", "accent-soft": "#F3E0D6",
  grip: "#2A7F7C", "grip-soft": "#D3E8E5",
  sage: "#CCD6C0", "sage-bg": "#DCE3D2", sky: "#CFDCE6", apricot: "#ECCDB6", paper: "#EFE4D6",
  good: "#3B7A56", "good-soft": "#DCEBDF", bad: "#B4432E", "bad-soft": "#F5DFD8",
});

export const DARK_PALETTE = Object.freeze({
  bg: "#1E1E1E", pane: "#252525", hover: "#2E2E2E", rule: "#353535",
  ink: "#E4E0D8", text: "#CBC6BC", muted: "#8C887F",
  accent: "#A797F7", "accent-soft": "#2D2943",
  grip: "#5FC4BE", "grip-soft": "#1F3634",
  sage: "#3C4836", "sage-bg": "#28301F", sky: "#2D3B47", apricot: "#5A4536", paper: "#2A2738",
  good: "#7CC79A", "good-soft": "#203528", bad: "#EF8A72", "bad-soft": "#3A2420",
});

/**
 * 宿主自检 20 键十六进制颜色表（kit.md 1.3）。
 * @param {unknown} p
 * @returns {p is Record<string, string>}
 */
export function validPalette(p) {
  if (!p || typeof p !== "object" || Object.getPrototypeOf(p) !== Object.prototype) return false;
  return PALETTE_KEYS.every((key) => Object.hasOwn(p, key)) &&
    Object.values(p).every((value) => typeof value === "string" && HEX_COLOR.test(value));
}

/**
 * 读取当前外壳生效的 20 个十六进制平台色位；非浏览器环境或变量未就绪时回退到同模式基准表。
 * @param {"light"|"dark"} scheme
 * @param {Document|null} [doc]
 * @returns {Record<string, string>}
 */
export function resolvePalette(scheme, doc = typeof document !== "undefined" ? document : null) {
  const fallback = scheme === "dark" ? DARK_PALETTE : LIGHT_PALETTE;
  const style = doc?.defaultView?.getComputedStyle && doc.documentElement
    ? doc.defaultView.getComputedStyle(doc.documentElement)
    : null;
  const out = { ...fallback };
  if (!style) return out;
  const declared = style.getPropertyValue("--curio-palette-keys").trim();
  const keys = new Set([...PALETTE_KEYS, ...(declared ? declared.split(/\s+/) : [])]);
  for (const key of keys) {
    const value = style.getPropertyValue("--" + key).trim();
    if (HEX_COLOR.test(value)) out[key] = value;
  }
  return out;
}
