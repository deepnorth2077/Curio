# Curio · 切分机走查脚本。用法：python walk.py <index.html 路径> <截图目录> [只跑哪个：tablet|phone|desk]
# 三种屏幕从头玩到尾，逐站截图；g1.md C.1 第 2 节的验收用例写成断言；收集 console 错误和契约消息。
import sys, json, math, pathlib
from playwright.sync_api import sync_playwright
URL = pathlib.Path(sys.argv[1]).resolve().as_uri(); OUT = pathlib.Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
ONLY = sys.argv[3] if len(sys.argv) > 3 else None
errs, fails = [], []
def check(name, ok, got=None):
    if not ok: fails.append(f"{name}: {got}")
    print(("  ok  " if ok else "  FAIL") + " " + name + ("" if ok else f" -> {got}"))
def run(p, name, vp, scheme, rm, touch):
    b = p.chromium.launch(); ctx = b.new_context(viewport=vp, color_scheme=scheme, reduced_motion=rm, has_touch=touch, device_scale_factor=2)
    page = ctx.new_page()
    page.on("console", lambda m: m.type in ("error", "warning") and errs.append(f"{name}: {m.text}"))
    page.on("pageerror", lambda e: errs.append(f"{name}: {e}"))
    ev = lambda js: page.evaluate(js)
    def shot(n): page.screenshot(path=str(OUT / f"{name}-{n}.png"), full_page=True)
    def btn(text): page.wait_for_timeout(430); page.locator("#actions button", has_text=text).first.click(); page.wait_for_timeout(150)   # 教训 24：等够 0.4 秒
    def pt(x, y): return ev(f"(()=>{{const s=document.getElementById('stage');const p=s.createSVGPoint();p.x={x};p.y={y};const q=p.matrixTransform(s.getScreenCTM());return [q.x,q.y]}})()")
    def readout(): return ev("document.getElementById('readout').innerText.replace(/\\s+/g,' ')")
    def said(): return ev("document.getElementById('say').innerText.replace(/\\s+/g,' ')")
    def sent(kind): return ev(f"(window.__sent||[]).filter(m=>m.type==='{kind}')")
    def grips(): return ev("document.querySelectorAll('#dyn .gfill').length")
    def cue(): return ev("document.getElementById('cue').style.display !== 'none'")
    page.goto(URL); page.wait_for_timeout(400)
    first = ev("window.__sent[0].type"); check("ready 先于别的消息", first == "ready", first)
    # ---------- 第 1 站 ----------
    shot("1a-intro"); btn("然后呢"); btn("是吗"); shot("1b-ask")
    check("提问时没有圆钮", grips() == 0, grips())
    labels = ev("[...document.querySelectorAll('#actions .choice')].map(b=>b.innerText.replace(/\\s+/g,''))"); print("  选项", labels)
    btn("那块大")   # 第一个：1/8 那块大（误区）
    check("猜错用中性气泡", "hmm" in ev("document.getElementById('say').className"), None); shot("1c-wrong")
    btn("动手切"); page.wait_for_timeout(300); shot("1d-act-first")
    check("动手第一屏有 1 个圆钮", grips() == 1, grips())
    if rm == "no-preference":
        check("1.5 秒内不提醒", not cue()); page.wait_for_timeout(1500); check("1.5 秒后提醒", cue()); shot("1e-cue")
    page.locator("#stage").focus()
    def turn_to(n):
        cur = ev("S.n")
        for _ in range(abs(n - cur)): page.keyboard.press("ArrowRight" if n > cur else "ArrowLeft"); page.wait_for_timeout(30)
        page.wait_for_timeout(760)
    # 用手拖一次圆钮：从 1 拖到 3
    gx, gy = pt(*ev("dialGrip()")); tx, ty = pt(*ev("pol(DIAL.x,DIAL.y,dialGripR(),90)"))
    page.mouse.move(gx, gy); page.mouse.down(); page.wait_for_timeout(60)
    for i in range(1, 13):
        a = math.radians(30 + 60 * i / 12); cx, cy = pt(*ev(f"pol(DIAL.x,DIAL.y,dialGripR(),{30 + 60 * i / 12})")); page.mouse.move(cx, cy); page.wait_for_timeout(15)
    shot("1f-dragging"); page.mouse.up(); page.wait_for_timeout(800)
    check("拖圆钮到 3 份", ev("S.n") == 3, ev("S.n")); check("碰过以后不再提醒", not cue())
    check("读数 n=3", readout() == "切成 3 份 · 这一份是这张饼的 1 3", readout())
    check("第一次停住说出分数", "分数" in said() and "三分之一" in said(), said()); shot("1g-n3")
    turn_to(7); st = sent("state")[-1]["payload"]; check("state n=7 deg=51.43", st == {"station": 1, "n": 7, "deg": 51.43}, st)
    check("第二次停住说分子分母", "分母" in said() and "分子" in said() and "分数线" in said(), said()); shot("1h-n7")
    turn_to(11); st = sent("state")[-1]["payload"]; check("state n=11 deg=32.73", st == {"station": 1, "n": 11, "deg": 32.73}, st)
    check("还没切 8，提醒切 8", "8 份" in said(), said())
    turn_to(8); turn_to(7); turn_to(8)
    tray = ev("S.tray.filter(t=>!t.auto).map(t=>t.n).sort((a,b)=>a-b)"); check("托盘同一个 n 只留一块", tray == [3, 7, 8, 11], tray)
    xs = ev("trayLayout().map(t=>[t.n,t.tx,sliceH(t.n,TRAY.r)])"); check("托盘从少到多、一块比一块矮", all(xs[i][0] < xs[i+1][0] and xs[i][1] < xs[i+1][1] and xs[i][2] > xs[i+1][2] for i in range(len(xs)-1)), xs)
    turn_to(12); turn_to(2); shot("1i-ready")
    for n in range(2, 13):
        if name == "desk": turn_to(n); check(f"读数 n={n}", readout() == f"切成 {n} 份 · 这一份是这张饼的 1 {n}", readout())
    turn_to(5); last_n = 5
    btn("看托盘"); page.wait_for_timeout(1700); shot("1j-reveal"); check("揭晓后没有圆钮", grips() == 0, grips())
    check("托盘补满 11 块", ev("S.tray.length") == 11, ev("S.tray.length"))
    btn("所以呢"); shot("1k-reveal2"); btn("去第 2 站")
    # ---------- 第 2 站 ----------
    shot("2a-intro"); btn("然后呢"); shot("2b-ask"); check("提问时没有圆钮", grips() == 0, grips())
    btn("3 块里拿了 1 块"); btn("动手切"); shot("2c-talk"); btn("明白"); page.wait_for_timeout(300); shot("2d-act-first")
    check("第 2 站第一屏 1 个圆钮", grips() == 1, grips())
    def drag_knife(to, steps=14, release=True, mid=None):
        kx, ky = pt(*ev("[cellX(S.knifeP)-KN.off, KN.grip]")); tx, _ = pt(*ev(f"[cellX({to})-KN.off, KN.grip]"))
        if touch and name == "phone":   # 真实触摸事件（教训 25）：用 CDP 触摸
            cdp = ctx.new_cdp_session(page); y0 = ev("scrollY")
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": kx, "y": ky}]})
            for i in range(1, steps + 1): cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": kx + (tx - kx) * i / steps, "y": ky + 30 * math.sin(i)}]}); page.wait_for_timeout(16)
            if mid: page.wait_for_timeout(250); shot(mid)
            if release: cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            check("拖刀时页面不滚", ev("scrollY") == y0, ev("scrollY"))
        else:
            page.mouse.move(kx, ky); page.mouse.down()
            for i in range(1, steps + 1): page.mouse.move(kx + (tx - kx) * i / steps, ky); page.wait_for_timeout(16)
            if mid: page.wait_for_timeout(250); shot(mid)
            if release: page.mouse.up()
        page.wait_for_timeout(250)
    drag_knife(46, mid="2e-dragging")
    check("46 格：不落刀", ev("S.cuts.length") == 0 and ev("S.knife") == 46, [ev("S.cuts"), ev("S.knife")])
    check("46 格：右边沉", ev("S.tilt") > 3 and "右边沉" in said(), [ev("S.tilt"), said()])
    check("46 格读数", readout() == "两份不一样大 · 还不能叫 1 2", readout()); shot("2f-fail")
    drag_knife(52); page.wait_for_timeout(900)
    check("52 格松手吸到 50 并落刀", ev("S.cuts") == [50], ev("S.cuts")); check("落刀后读数", readout() == "2 份一样大 · 每份是它的 1 2", readout())
    st = sent("state")[-1]["payload"]; check("state 第 2 站", st == {"station": 2, "knife": 50, "cuts": [50], "balanced": True}, st); shot("2g-half")
    check("停下来说话时没有圆钮", grips() == 0, grips())
    btn("接着切"); page.wait_for_timeout(200); page.locator("#stage").focus()
    for _ in range(13): page.keyboard.press("ArrowRight")      # 键盘：12 → 25
    page.keyboard.press("Enter"); page.wait_for_timeout(900); check("键盘切第二刀", ev("S.cuts") == [25, 50], ev("S.cuts")); shot("2h-second")
    drag_knife(74); page.wait_for_timeout(900); check("三刀在 25、50、75", ev("S.cuts") == [25, 50, 75], ev("S.cuts"))
    check("三刀后读数", readout() == "4 份一样大 · 每份是它的 1 4", readout()); shot("2i-cut3")
    page.wait_for_timeout(1500); shot("2j-stack"); btn("开场那 3 块呢"); page.wait_for_timeout(900); shot("2k-weigh"); check("开场三块一头沉", abs(ev("S.wtilt")) > 10, ev("S.wtilt"))
    btn("所以呢"); shot("2l-reveal"); btn("还有呢"); btn("去第 3 站")
    # ---------- 第 3 站 ----------
    shot("3a-intro"); btn("然后呢"); shot("3b-ask"); btn("那段"); btn("动手排"); page.wait_for_timeout(200); shot("3c-act-first")
    hb = page.locator("#actions button.hold"); check("按住按钮在", hb.count() == 1, hb.count())
    def hold(ms, mid=None, midshot=None):
        bb = hb.bounding_box(); page.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2); page.mouse.down()
        if mid: page.wait_for_timeout(mid); shot(midshot); page.wait_for_timeout(max(0, ms - mid))
        else: page.wait_for_timeout(ms)
        page.mouse.up(); page.wait_for_timeout(300)
    for i, (n, unit, ms) in enumerate([(10, "分米", 3600), (100, "厘米", 4600), (1000, "毫米", 5600)]):
        if rm == "reduce" or i == 0:
            hold(1200 if i == 0 else 900); c = ev("count3()"); check(f"第 {i+1} 轮松手就停（{c}）", 0 < c < n, c)
            check(f"第 {i+1} 轮半路读数", readout() == f"{c} 个 1 {n} · 排到 {c} {unit}", readout()); page.wait_for_timeout(400); check("松手后计数不走", ev("count3()") == c, ev("count3()"))
            hold(ms, 400, f"3d-round{i+1}-mid")
        else: hold(ms + 300, 2400, f"3d-round{i+1}-mid")
        check(f"第 {i+1} 轮正好停在 {n}", ev("count3()") == n and readout() == f"{n} 个 1 {n} = 1 · 正好 1 米", [ev("count3()"), readout()])
        st = sent("state")[-1]["payload"]; check(f"state 第 3 站 unit={n}", st == {"station": 3, "unit": n, "count": n}, st)
        shot(f"3e-round{i+1}-done"); btn("换更小的" if i < 2 else "看三个放大圈"); page.wait_for_timeout(200)
    shot("3f-wow"); btn("有多薄"); shot("3g-wow2"); btn("看我的星卡"); page.wait_for_timeout(300); shot("4-card")
    # ---------- 星卡和事件 ----------
    pins = ev("document.querySelectorAll('#dyn circle.lead').length"); kinds = ev("kinds().length"); check("钉子数 = 切过的份数", pins - 1 == kinds or pins == kinds, [pins, kinds])   # 第 3 格的放大圈也用了 lead
    check("星卡是最后停的份数", ev("S.lastN") == last_n, ev("S.lastN"))
    evs = [(m["payload"]["verb"], m["payload"]["result"]) for m in sent("event")]
    check("predicted 三次", [e[1]["station"] for e in evs if e[0] == "predicted"] == [1, 2, 3], evs)
    check("predicted 带误区", [e[1]["misconception"] for e in evs if e[0] == "predicted"] == ["bigger-denominator-bigger", "unequal-parts", None], evs)
    check("observed 三次", [e[1]["station"] for e in evs if e[0] == "observed"] == [1, 2, 3], evs)
    check("没有 answered", all(e[0] in ("predicted", "observed") for e in evs), evs); check("complete 一次", len(sent("complete")) == 1, len(sent("complete")))
    btn("再玩一次"); page.wait_for_timeout(300); shot("5-replay"); check("再玩一次回到第 1 站", ev("S.station") == 1 and ev("S.scene") == "s1q")
    btn("然后呢"); btn("是吗"); btn("一样大"); btn("动手切"); check("复位：托盘空、没切", ev("S.tray.length") == 0 and ev("S.n") == 1, None); check("再玩不再发 complete", len(sent("complete")) == 1)
    check("页面没有横向溢出", ev("document.documentElement.scrollWidth <= innerWidth"), ev("document.documentElement.scrollWidth"))
    b.close()
with sync_playwright() as p:
    for cfg in [("tablet", {"width": 820, "height": 1180}, "light", "no-preference", True), ("phone", {"width": 390, "height": 844}, "dark", "no-preference", True), ("desk", {"width": 1280, "height": 900}, "light", "reduce", False)]:
        if ONLY and cfg[0] != ONLY: continue
        print("==", cfg[0]); run(p, *cfg)
print("console:", errs); print("FAILS:", json.dumps(fails, ensure_ascii=False, indent=1))
sys.exit(1 if fails or errs else 0)
