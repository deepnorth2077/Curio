# Curio · 动手探索模块的走查脚本样例（染色体模块）。复制后改 URL 和流程：平板、手机、电脑三种宽度，浅色深色，reduced-motion，逐站截图到一个目录，收集 console 错误。
import sys
from playwright.sync_api import sync_playwright
URL = "file:///home/claude/wt-genetics.chromosome-intro/content/activities/act.simulation.chromosome-pack-01/index.html"
errs = []
def btn(page, text):
    page.wait_for_timeout(420); page.locator("#actions button", has_text=text).first.click(); page.wait_for_timeout(120)
def shot(page, name): page.screenshot(path=f"/home/claude/sim-shots/{name}.png", full_page=True)
def svgpt(page, x, y):
    return page.evaluate(f"(()=>{{const s=document.getElementById('stage');const p=s.createSVGPoint();p.x={x};p.y={y};const q=p.matrixTransform(s.getScreenCTM());return [q.x,q.y]}})()")
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, vp, scheme, rm in [("tablet", {"width":820,"height":1180}, "light", "no-preference"), ("phone", {"width":390,"height":844}, "dark", "no-preference"), ("desk", {"width":1280,"height":900}, "light", "reduce")]:
        ctx = b.new_context(viewport=vp, color_scheme=scheme, reduced_motion=rm, has_touch=(name!="desk"))
        page = ctx.new_page()
        page.on("console", lambda m, n=name: m.type in ("error","warning") and errs.append(f"{n}: {m.text}"))
        page.on("pageerror", lambda e, n=name: errs.append(f"{n}: {e}"))
        page.goto(URL); page.wait_for_timeout(400); shot(page, f"{name}-1-intro")
        btn(page, "然后呢"); shot(page, f"{name}-1-ask")
        btn(page, "揉成一团"); shot(page, f"{name}-1-wrong")
        btn(page, "那该怎么收"); btn(page, "开始绕")
        # 用鼠标拖把手转两圈
        cx, cy = svgpt(page, 135, 250); r = 60*(cx/135 if False else 1)
        import math
        k = page.evaluate("document.getElementById('stage').getScreenCTM().a")
        page.mouse.move(cx, cy - 66*k); page.mouse.down()
        for i in range(1, 80):
            a = -math.pi/2 + i*0.16
            page.mouse.move(cx + math.cos(a)*66*k, cy + math.sin(a)*66*k)
        page.mouse.up(); page.wait_for_timeout(500); shot(page, f"{name}-1-mid")
        print(name, "p1 after drag", page.evaluate("S.t1"))
        # 按住「转」按钮
        hb = page.locator("#actions button", has_text="转").first
        bb = hb.bounding_box(); page.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); page.mouse.down(); page.wait_for_timeout(7000); page.mouse.up()
        page.wait_for_timeout(600); shot(page, f"{name}-1-done")
        print(name, "mode", page.evaluate("S.mode"), page.evaluate("S.t1"))
        btn(page, "继续"); btn(page, "去第 2 站"); shot(page, f"{name}-2-intro")
        btn(page, "怎么办")
        kx, ky = page.evaluate("fiberPts(S.p2)[KNOB_I]"); sx, sy = svgpt(page, kx, ky); ex, ey = svgpt(page, kx-340, ky)
        page.mouse.move(sx, sy); page.mouse.down()
        for i in range(1, 30): page.mouse.move(sx + (ex-sx)*i/58, sy); 
        page.wait_for_timeout(500); shot(page, f"{name}-2-mid")
        for i in range(30, 59): page.mouse.move(sx + (ex-sx)*i/58, sy)
        page.mouse.up(); page.wait_for_timeout(900); shot(page, f"{name}-2-done")
        btn(page, "继续"); btn(page, "继续"); shot(page, f"{name}-2-wow"); btn(page, "继续"); btn(page, "去第 3 站")
        btn(page, "继续"); btn(page, "那怎么办")
        hb = page.locator("#actions button", has_text="卷紧").first
        bb = hb.bounding_box(); page.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); page.mouse.down(); page.wait_for_timeout(2000)
        shot(page, f"{name}-3-mid"); page.wait_for_timeout(4200); page.mouse.up(); page.wait_for_timeout(600)
        shot(page, f"{name}-3-rods")
        btn(page, "继续"); btn(page, "继续"); btn(page, "23 根"); btn(page, "数一数"); page.wait_for_timeout(3500); shot(page, f"{name}-3-count")
        btn(page, "继续"); btn(page, "继续"); btn(page, "去配对台"); page.wait_for_timeout(300); shot(page, f"{name}-3-pair0")
        # 点 1 号的两根；再点一对错的
        def tap_rod(idx):
            x, y = page.evaluate(f"[RODS[{idx}].x, RODS[{idx}].y]"); sx, sy = svgpt(page, x, y)
            if name == "desk": page.mouse.click(sx, sy)
            else: page.touchscreen.tap(sx, sy)
            page.wait_for_timeout(150)
        ids = page.evaluate("RODS.map(r=>r.id)")
        i1 = [i for i, v in enumerate(ids) if v == "1"]; i2 = [i for i, v in enumerate(ids) if v == "2"]; i7 = [i for i, v in enumerate(ids) if v == "7"]; ix = ids.index("X")
        iy = ids.index("Y"); tap_rod(ix); tap_rod(iy); page.wait_for_timeout(300); shot(page, f"{name}-3-xyfirst")
        print(name, "xy-first pairs", page.evaluate("S.pairs"), page.evaluate("S.mode"))
        tap_rod(i1[0]); shot(page, f"{name}-3-sel"); tap_rod(i1[1]); page.wait_for_timeout(600); shot(page, f"{name}-3-pair1")
        tap_rod(i7[0]); tap_rod(ix); page.wait_for_timeout(200); shot(page, f"{name}-3-wrong")
        tap_rod(i2[0]); tap_rod(i2[1]); tap_rod(i7[0]); tap_rod(i7[1]); page.wait_for_timeout(400)
        print(name, "pairs", page.evaluate("S.pairs"))
        btn(page, "帮忙"); page.wait_for_timeout(4500); shot(page, f"{name}-3-auto")
        tap_rod(ix); tap_rod(iy); page.wait_for_timeout(1500); shot(page, f"{name}-3-allpaired")
        btn(page, "第 23 对"); shot(page, f"{name}-4-intro"); btn(page, "继续"); btn(page, "继续"); btn(page, "妈妈"); shot(page, f"{name}-4-reveal")
        btn(page, "女孩"); shot(page, f"{name}-4-girl"); btn(page, "继续"); btn(page, "星卡"); page.wait_for_timeout(300); shot(page, f"{name}-5-end")
        btn(page, "继续"); btn(page, "为什么"); btn(page, "再玩一次"); print(name, "replay", page.evaluate("[S.station, S.round]"))
        ctx.close()
    b.close()
print("ERRORS:", errs)
