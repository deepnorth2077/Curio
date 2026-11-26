// 试玩页和原型内容播放器都随产物内联这份代码，单文件离线打开也能用。
function createPreviewPreferences(fallbackPalettes = {}) {
  const root = document.documentElement;
  const dark = matchMedia("(prefers-color-scheme: dark)");
  const listeners = new Set();
  function read(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  }
  let theme = read("curio.theme"), muted = read("curio.muted") === "1";
  function scheme() {
    return theme === "light" || theme === "dark" ? theme : dark.matches ? "dark" : "light";
  }
  function apply() {
    if (theme === "light" || theme === "dark") root.dataset.theme = theme;
    else delete root.dataset.theme;
    for (const listener of listeners) listener();
  }
  dark.addEventListener("change", apply);
  addEventListener("storage", e => {
    if (e.key !== null && e.key !== "curio.theme" && e.key !== "curio.muted") return;
    theme = read("curio.theme");
    muted = read("curio.muted") === "1";
    apply();
  });
  function set(key, value) {
    try { localStorage.setItem(key, value); } catch { /* 独立打开时只在本页生效 */ }
    apply();
  }
  apply();
  return {
    scheme,
    muted: () => muted,
    toggleTheme() { theme = scheme() === "dark" ? "light" : "dark"; set("curio.theme", theme); },
    toggleMute() { muted = !muted; set("curio.muted", muted ? "1" : "0"); },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    themePayload() {
      const mode = scheme();
      // 冻结的原型没有同步色位段，由构建器提供相同的两张平台色表。
      const palette = {...fallbackPalettes[mode]};
      const style = getComputedStyle(root);
      const keys = style.getPropertyValue("--curio-palette-keys").trim().split(/\s+/).filter(Boolean);
      for (const key of keys) {
        const value = style.getPropertyValue("--" + key).trim();
        if (/^#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(value)) palette[key] = value;
      }
      return {scheme: mode, palette};
    },
    // 调用方在收到 ready 后订阅，离开活动时退订。
    connect(post) {
      let lastScheme = scheme(), lastMuted = muted;
      return this.subscribe(() => {
        if (lastScheme !== scheme()) { lastScheme = scheme(); post("theme", this.themePayload()); }
        if (lastMuted !== muted) { lastMuted = muted; post("mute", {muted}); }
      });
    },
  };
}
