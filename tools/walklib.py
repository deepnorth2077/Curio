"""动手探索模块走查的公共部分（#140 第 4 条）。走查脚本放在 tools/walks/<活动 id>.py，写法见 act.simulation.fair-cut-01.py。

一个走查脚本只写一个函数 play(w)，从头玩到尾，最后调用 walklib.main(play)。
用法：python tools/walks/<活动 id>.py <index.html> <截图目录> [--only tablet|phone|desk]

w 能做的事：
- check(名字, 是否通过, 实际值)：记一条断言；
- btn(文字)：等 0.43 秒再点 #actions 里的按钮（教训 24）；3 秒内找不到就报错，写明卡在哪一步、现在有哪些按钮；
- pt(x, y)：SVG 坐标换成屏幕坐标；readout()、said()、sent(类型)、grips()、cue()：读画面和发给平台的消息；
- mouse_drag(点列)、touch_drag(点列)：鼠标拖、真实触摸拖（CDP，顺带断言页面不滚，教训 25）；
- shot(名字, first=True)：截图；标了 first 的是「进入动手、手不碰的第一屏」，最后拼成一张灰度图（圆钮规格 G8）。

每种屏幕有总超时，超时算失败并写出最后一步。有失败或 console 有错误时退出码是 1。
"""
import argparse
import base64
import json
import os
import pathlib
import sys
import threading
import time

from playwright.sync_api import sync_playwright

# 三种屏幕：名字、视口、明暗、减少动效、触摸
CONFIGS = [
    ("tablet", {"width": 820, "height": 1180}, "light", "no-preference", True),
    ("phone", {"width": 390, "height": 844}, "dark", "no-preference", True),
    ("desk", {"width": 1280, "height": 900}, "light", "reduce", False),
]
TIMEOUT = 240      # 每种屏幕最多跑多少秒
BTN_WAIT = 2.5     # 0.43 秒的等待之后，再等按钮出现多久（加起来不到 3 秒）
HOST = "http://walk.curio/"   # 放进沙箱 iframe 打开时用的假地址（不联网，由 route 直接回文件）

HARNESS = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{margin:0;height:100%}iframe{border:0;width:100%;height:100%;display:block}</style></head>
<body><iframe id="m" sandbox="allow-scripts" src="module/index.html"></iframe><script>
window.__got = [];
addEventListener("message", e => { const m = e.data; if (m && m.contract === "activity/1.1") window.__got.push({ type: m.type, payload: m.payload || {} }); });
</script></body></html>"""


class WalkError(Exception):
    pass


class Walker:
    def __init__(self, p, cfg, path, out, timeout):
        self.name, self.vp, self.scheme, self.rm, self.touch = cfg
        self.path, self.out, self.timeout = pathlib.Path(path).resolve(), out, timeout
        self.deadline = time.monotonic() + timeout
        self.last, self.firsts, self.fails, self.errs, self.oks = "打开页面", [], [], [], 0
        self.browser = p.chromium.launch()
        self.ctx = self.browser.new_context(viewport=self.vp, color_scheme=self.scheme, reduced_motion=self.rm, has_touch=self.touch, device_scale_factor=2)
        self.page = self.ctx.new_page()
        self.page.on("console", lambda m: m.type in ("error", "warning") and self.errs.append(f"{self.name}: {m.text}"))
        self.page.on("pageerror", lambda e: self.errs.append(f"{self.name}: {e}"))
        self.doc, self.hosted, self._cdp = self.page, False, None

    # ---------- 打开 ----------
    def open(self, hosted=False, wait=400):
        """hosted=False：单独打开，消息记在 window.__sent；hosted=True：像平台一样放进沙箱 iframe，消息由外层页面收。"""
        self.step("打开页面")
        if hosted:
            folder = self.path.parent

            def serve(route):
                rel = route.request.url[len(HOST):].split("?")[0]
                if rel == "":
                    return route.fulfill(body=HARNESS, content_type="text/html; charset=utf-8")
                f = folder / rel[len("module/"):] if rel.startswith("module/") else None
                if f and f.is_file():
                    return route.fulfill(path=str(f))
                return route.fulfill(status=404, body="")
            self.page.route(HOST + "**", serve)
            self.page.goto(HOST)
            self.doc, self.hosted = self.page.wait_for_selector("#m").content_frame(), True
        else:
            self.page.goto(self.path.as_uri())
        self.page.wait_for_timeout(wait)

    # ---------- 基本 ----------
    def step(self, what):
        self.last = what
        if time.monotonic() > self.deadline:
            raise WalkError(f"超时（{self.timeout} 秒），最后一步：{what}")

    def ev(self, js):
        return self.doc.evaluate(js)

    def wait(self, ms):
        self.page.wait_for_timeout(ms)

    def check(self, name, ok, got=None):
        self.step(f"断言「{name}」")
        if ok:
            self.oks += 1
        else:
            self.fails.append(f"{self.name}: {name}: {got}")
        print(("  ok  " if ok else "  FAIL") + " " + name + ("" if ok else f" -> {got}"), flush=True)

    def shot(self, n, first=False):
        self.step(f"截图 {n}")
        f = self.out / f"{self.name}-{n}.png"
        self.page.screenshot(path=str(f), full_page=True)
        if first:
            self.firsts.append(f)

    def buttons(self):
        return self.ev("[...document.querySelectorAll('#actions button')].map(b=>b.innerText.replace(/\\s+/g,''))")

    def btn(self, text):
        self.step(f"点「{text}」")
        self.wait(430)
        try:
            self.doc.locator("#actions button", has_text=text).first.click(timeout=BTN_WAIT * 1000)
        except Exception:
            raise WalkError(f"卡在这一步：点「{text}」。找不到这个按钮，现在的按钮：{self.buttons()}") from None
        self.wait(150)

    # ---------- 读画面 ----------
    def pt(self, x, y):
        return self.ev(f"(()=>{{const s=document.getElementById('stage');const p=s.createSVGPoint();p.x={x};p.y={y};const q=p.matrixTransform(s.getScreenCTM());return [q.x,q.y]}})()")

    def readout(self):
        return self.ev("document.getElementById('readout').innerText.replace(/\\s+/g,' ')")

    def said(self):
        return self.ev("document.getElementById('say').innerText.replace(/\\s+/g,' ')")

    def sent(self, kind=None):
        msgs = self.page.evaluate("window.__got") if self.hosted else self.ev("window.__sent||[]")
        return [m for m in msgs if kind is None or m["type"] == kind]

    def grips(self):
        return self.ev("document.querySelectorAll('#dyn .gfill').length")

    def cue(self):
        return self.ev("document.getElementById('cue').style.display !== 'none'")

    # ---------- 拖动 ----------
    def mouse_drag(self, pts, down_wait=0, step_ms=16, before_release=None, release=True):
        self.step("鼠标拖动")
        m = self.page.mouse
        m.move(*pts[0]); m.down()
        if down_wait:
            self.wait(down_wait)
        for x, y in pts[1:]:
            m.move(x, y); self.wait(step_ms)
        if before_release:
            before_release()
        if release:
            m.up()

    def touch_drag(self, pts, step_ms=16, before_release=None, release=True, no_scroll="拖动时页面不滚"):
        """真实触摸事件（教训 25）。拖完断言页面没有跟着滚。"""
        self.step("触摸拖动")
        cdp = self._cdp = self._cdp or self.ctx.new_cdp_session(self.page)
        y0 = self.page.evaluate("scrollY")
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": pts[0][0], "y": pts[0][1]}]})
        for x, y in pts[1:]:
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]}); self.wait(step_ms)
        if before_release:
            before_release()
        if release:
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        y1 = self.page.evaluate("scrollY")
        self.check(no_scroll, y1 == y0, y1)

    def close(self):
        try:
            self.browser.close()
        except Exception:
            pass


def montage(p, files, dest):
    """第一屏灰度拼图：每张缩到 410 宽、4 列。"""
    if not files:
        return
    cells = "".join(f'<figure><img src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}"><figcaption>{f.stem}</figcaption></figure>' for f in files)
    html = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{margin:8px;background:#fff;font:13px sans-serif}"
            "main{display:grid;grid-template-columns:repeat(4,410px);gap:8px;align-items:start}figure{margin:0}"
            "img{width:410px;display:block;filter:grayscale(1)}</style></head><body><main>" + cells + "</main></body></html>")
    b = p.chromium.launch()
    try:
        page = b.new_page(viewport={"width": 4 * 410 + 40, "height": 400})
        page.set_content(html); page.wait_for_timeout(200)
        page.screenshot(path=str(dest), full_page=True)
    finally:
        b.close()


def walk(play, path, out, only=None, timeout=TIMEOUT):
    """三种屏幕各跑一次 play(w)。返回 (失败列表, console 错误列表, ok 条数)。"""
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    fails, errs, oks, firsts = [], [], 0, []
    with sync_playwright() as p:
        for cfg in CONFIGS:
            if only and cfg[0] != only:
                continue
            print("==", cfg[0], flush=True)
            w = Walker(p, cfg, path, out, timeout)
            # 万一卡死在页面里（脚本里的死循环之类），宽限 20 秒后直接退出
            dog = threading.Timer(timeout + 20, lambda: (print(f"  FAIL {w.name} 超时，最后一步：{w.last}", flush=True), os._exit(1)))
            dog.daemon = True; dog.start()
            try:
                play(w)
            except Exception as exc:   # 一种屏幕出错不影响下一种
                msg = str(exc) if isinstance(exc, WalkError) else f"出错，最后一步：{w.last}：{type(exc).__name__}: {exc}"
                print(f"  FAIL {msg}", flush=True)
                w.fails.append(f"{w.name}: {msg}")
            finally:
                dog.cancel(); w.close()
            fails += w.fails; errs += w.errs; oks += w.oks; firsts += w.firsts
        montage(p, firsts, out / "first-screens.png")
    return fails, errs, oks


def main(play, timeout=TIMEOUT):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("html"); ap.add_argument("out")
    ap.add_argument("--only", choices=[c[0] for c in CONFIGS])
    a = ap.parse_args()
    t0 = time.monotonic()
    fails, errs, oks = walk(play, a.html, a.out, a.only, timeout)
    print(f"ok {oks} 条，FAIL {len(fails)} 条，用时 {time.monotonic() - t0:.0f} 秒")
    print("console:", errs)
    print("FAILS:", json.dumps(fails, ensure_ascii=False, indent=1))
    sys.exit(1 if fails or errs else 0)
