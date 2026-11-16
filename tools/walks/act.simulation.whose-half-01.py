# Curio · 谁的一半走查。用法：python tools/walks/act.simulation.whose-half-01.py <index.html> <截图目录> [--only tablet|phone|desk]
# 三种屏幕从头玩到尾，逐站截图；03-the-whole.md 第 2 节的验收用例写成断言。期望值不能为了通过去改（受保护路径）。
#
# 只用 /home/claude/seams-whose-half.md 列出的全局变量、函数、按钮文字、class。
# 第 1 站：键盘 ← → 每次 8 厘米，16 走 3 次到 40（停 700 毫秒，过了 600 毫秒的判停）；再拖拉手到 64。
# 第 2 站：点糖袋 3 下（点之间 450 毫秒）；点亮 3 盘（一盘点、两盘 ↑ 键）；→ 换 6 盘，空格 + 回车发完。
# 第 3 站：按住「再摆一份」。按下 300 毫秒内摆第一份，之后每 700 毫秒一份：
#   1/3 要再摆 2 份，约 1000 毫秒；1/10 要再摆 9 份，约 5900 毫秒；1/2 要再摆 1 份。下面的时长都留了余量。
# 不要写「按键直到等于某个值」的 while 循环：走不到的值会让它永远不停。次数都是固定的。
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib  # noqa: E402

READ_L = "领航员：20 厘米的 1 2 是 10 厘米 · 舰长：{L} 厘米的 1 4 是 {p} 厘米"


def play(w):
    name, rm, touch, page = w.name, w.rm, w.touch, w.page
    ev, check, btn, shot, pt = w.ev, w.check, w.btn, w.shot, w.pt
    readout, said, sent, grips, cue = w.readout, w.said, w.sent, w.grips, w.cue

    def cnt(sel):
        return ev(f"document.querySelectorAll('{sel}').length")

    def at(expr):
        """接缝函数返回 [x, y] 或 {x, y}（SVG 坐标）都行，换成屏幕坐标。"""
        return pt(*ev(f"(()=>{{const v={expr};return Array.isArray(v)?v:[v.x,v.y]}})()"))

    def tap(x, y):
        if touch:
            page.touchscreen.tap(x, y)
        else:
            page.mouse.click(x, y)

    def focus():
        page.locator("#stage").focus()

    def neutral(label):
        check(label, "hmm" in ev("document.getElementById('say').className"), ev("document.getElementById('say').className"))

    def hold_btn(ms, mid=None, midshot=None):
        """用鼠标按住「再摆一份」ms 毫秒再松手（平板手机也用鼠标按住）。"""
        w.step(f"按住按钮 {ms} 毫秒")
        bb = page.locator("#actions button.hold").bounding_box()
        page.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2); page.mouse.down()
        if mid:
            page.wait_for_timeout(mid); shot(midshot); page.wait_for_timeout(max(0, ms - mid))
        else:
            page.wait_for_timeout(ms)
        page.mouse.up(); page.wait_for_timeout(300)

    def hold_key(ms):
        w.step(f"按住空格 {ms} 毫秒")
        focus(); page.keyboard.down("Space"); page.wait_for_timeout(ms); page.keyboard.up("Space"); page.wait_for_timeout(300)

    def keys(key, n, gap=100):
        for _ in range(n):
            page.keyboard.press(key); page.wait_for_timeout(gap)

    def drag_handle(to_cm, mid=None):
        hx, hy_svg = ev("handleXY()")
        fx, fy = pt(hx, hy_svg); tx, _ = pt(ev(f"lenX({to_cm})"), hy_svg)
        before = (lambda: (page.wait_for_timeout(200), shot(mid))) if mid else None
        if touch and name == "phone":   # 真实触摸事件（教训 25）
            path = [(fx, fy)] + [(fx + (tx - fx) * i / 14, fy + 30 * math.sin(i)) for i in range(1, 15)]
            w.touch_drag(path, before_release=before, no_scroll="拖拉手时页面不滚")
        else:
            path = [(fx, fy)] + [(fx + (tx - fx) * i / 14, fy) for i in range(1, 15)]
            w.mouse_drag(path, before_release=before)
        page.wait_for_timeout(300)

    w.open()
    first = ev("window.__sent[0].type"); check("ready 先于别的消息", first == "ready", first)
    # ---------- 第 1 站 · 拉 ----------
    shot("1a-intro"); btn("然后呢"); shot("1b-ask")
    check("第 1 站提问时没有圆钮", grips() == 0, grips())
    check("第 1 站提问时不画蛋糕卷（不泄露答案）", cnt("#dyn .roll") == 0, cnt("#dyn .roll"))
    btn("领航员"); neutral("第 1 站猜错用中性气泡"); btn("揭开餐罩"); page.wait_for_timeout(300); shot("1c-act-first", first=True)
    check("第 1 站第一屏 1 个圆钮（拉手）", grips() == 1, grips())
    check("第 1 站一开始 L=16", ev("S.station") == 1 and ev("S.L") == 16, [ev("S.station"), ev("S.L")])
    check("第 1 站读数 L=16", readout() == READ_L.format(L=16, p=4), readout())
    check("「1」记号在（第 1 站）", cnt("#dyn .one") >= 1, cnt("#dyn .one"))
    # 验收用例：键盘 16 -> 40，停 700 毫秒
    focus(); keys("ArrowRight", 3); page.wait_for_timeout(700)
    check("键盘 → 3 次：L=40，停在 40", ev("S.L") == 40 and ev("S.stop40") is True, [ev("S.L"), ev("S.stop40")])
    check("L=40 读数两边都是 10 厘米", readout() == READ_L.format(L=40, p=10), readout())
    st = sent("state")[-1]["payload"]; check("state L=40", st == {"station": 1, "whole": 40, "part": 10, "other": 10}, st)
    check("停在 40 说「一样多了」", "一样多了" in said(), said()); shot("1d-L40")
    check("只停过 40 时还没有「看明白了」", "看明白了" not in w.buttons(), w.buttons())
    n_state = len(sent("state"))
    # 验收用例：拖拉手到 64
    drag_handle(64, mid="1e-dragging")
    check("拖到 64：L=64，停在 ≥48 过", ev("S.L") == 64 and ev("S.stop48") is True, [ev("S.L"), ev("S.stop48")])
    check("L=64 读数：舰长那块 16 厘米", readout() == READ_L.format(L=64, p=16), readout())
    st = sent("state")[-1]["payload"]; check("state L=64", st == {"station": 1, "whole": 64, "part": 16, "other": 10}, st)
    check("拖完松手只多发一次 state", len(sent("state")) == n_state + 1, [n_state, len(sent("state"))])
    check("停在 ≥48 说「比我的还长」", "比我的还长" in said(), said()); shot("1f-L64")
    check("两个都停过以后出「看明白了」", "看明白了" in w.buttons(), w.buttons())
    btn("看明白了"); t1 = [said()]; shot("1g-say"); btn("我来说"); t1.append(said()); btn("大"); t1.append(said()); btn("还有呢"); t1.append(said()); shot("1h-reveal")
    joined = "".join(t1)
    check("第 1 站揭晓出现「整体」", "整体" in joined, t1)
    check("第 1 站揭晓有「同一条蛋糕卷上」那句", "同一条蛋糕卷" in joined, t1)
    btn("去第 2 站")
    # ---------- 第 2 站 · 发 ----------
    shot("2a-intro"); btn("然后呢"); shot("2b-ask")
    check("第 2 站提问时没有圆钮", grips() == 0, grips())
    check("第 2 站提问时不画糖（不泄露答案）", cnt("#dyn .candy") == 0, cnt("#dyn .candy"))
    btn("1 颗"); neutral("第 2 站猜错用中性气泡"); btn("发糖"); page.wait_for_timeout(300); shot("2c-act-first", first=True)
    check("第 2 站第一屏 1 个圆钮（糖袋）", grips() == 1, grips())
    check("第 2 站一开始 4 个盘子", ev("S.station") == 2 and ev("S.plates") == 4 and ev("S.dealt") == 0, [ev("S.plates"), ev("S.dealt")])
    check("「1」记号在（第 2 站）", cnt("#dyn .one") >= 1, cnt("#dyn .one"))
    for i in range(3):
        w.step(f"点糖袋第 {i + 1} 下"); page.wait_for_timeout(450); tap(*at("bagXY()")); page.wait_for_timeout(450)
        check(f"点 {i + 1} 下：发了 {i + 1} 轮", ev("S.dealt") == i + 1, ev("S.dealt"))
        if i == 1:
            tap(*at("plateXY(0)")); page.wait_for_timeout(300)
            check("没发完点盘子不亮", ev("S.lit") == 0, ev("S.lit"))
    page.wait_for_timeout(300)
    check("4 盘发完读数", readout() == "12 颗平均分成 4 份 · 每份 3 颗 · 一袋的 1 4 是 3 颗", readout())
    st = sent("state")[-1]["payload"]; check("state 4 盘发完", st == {"station": 2, "plates": 4, "each": 3, "taken": 0}, st); shot("2d-dealt")
    tap(*at("plateXY(0)")); page.wait_for_timeout(300)
    check("点盘子亮 1 盘读数", ev("S.lit") == 1 and readout() == "1 盘是一袋的 1 4 · 3 颗", [ev("S.lit"), readout()])
    focus(); page.keyboard.press("ArrowRight"); page.wait_for_timeout(300)
    check("点亮过 3 盘以前不能换盘子数", ev("S.plates") == 4 and ev("S.dealt") == 3, [ev("S.plates"), ev("S.dealt")])
    page.keyboard.press("ArrowUp"); page.wait_for_timeout(300)
    check("↑ 再亮 1 盘：2 盘读数", ev("S.lit") == 2 and readout() == "2 盘是一袋的 2 4 · 6 颗", [ev("S.lit"), readout()])
    page.keyboard.press("ArrowUp"); page.wait_for_timeout(300)
    check("点亮 3 盘读数", readout() == "3 盘是一袋的 3 4 · 9 颗", readout())
    check("点亮过正好 3 盘", ev("S.lit") == 3 and ev("S.lit3") is True, [ev("S.lit"), ev("S.lit3")])
    st = sent("state")[-1]["payload"]; check("state 点亮 3 盘", st == {"station": 2, "plates": 4, "each": 3, "taken": 3}, st); shot("2e-lit3")
    check("还没换盘子数发完时没有「看明白了」", "看明白了" not in w.buttons(), w.buttons())
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(400)
    check("→ 换成 6 盘：糖回袋、点亮归零", ev("S.plates") == 6 and ev("S.dealt") == 0 and ev("S.lit") == 0, [ev("S.plates"), ev("S.dealt"), ev("S.lit")])
    page.keyboard.press("Space"); page.wait_for_timeout(450); page.keyboard.press("Enter"); page.wait_for_timeout(700)   # 键盘发 2 轮
    check("6 盘发完：发了 2 轮", ev("S.dealt") == 2, ev("S.dealt"))
    check("6 盘发完读数", readout() == "12 颗平均分成 6 份 · 每份 2 颗 · 一袋的 1 6 是 2 颗", readout())
    st = sent("state")[-1]["payload"]; check("state 6 盘发完", st == {"station": 2, "plates": 6, "each": 2, "taken": 0}, st)
    check("换了盘子数又发完过", ev("S.redealt") is True, ev("S.redealt")); shot("2f-six")
    check("三件事做完出「看明白了」", "看明白了" in w.buttons(), w.buttons())
    btn("看明白了"); shot("2g-reveal"); btn("去第 3 站")
    # ---------- 第 3 站 · 找回来 ----------
    shot("3a-intro"); btn("然后呢"); shot("3b-ask")
    check("第 3 站提问时没有圆钮", grips() == 0, grips())
    check("第 3 站提问时不画袋子（不泄露答案）", cnt("#dyn .bag") == 0, cnt("#dyn .bag"))
    check("第 3 站提问时只有 5 颗糖", cnt("#dyn .candy") == 5, cnt("#dyn .candy"))
    btn("8 颗"); neutral("第 3 站猜错用中性气泡"); btn("摆一摆"); page.wait_for_timeout(300); shot("3c-act-first", first=True)
    # 圆钮规格 G5：圆钮只装在这一刻能动的东西上。1/3 摆满以前分母不能换，所以第一屏没有分母托，手放在按住按钮上
    check("第 3 站第一屏没有圆钮，手放在按住按钮上（G5）", grips() == 0 and cnt("#actions button.hold") == 1, [grips(), cnt("#actions button.hold")])
    check("第 3 站一开始 1/3、1 份", ev("S.station") == 3 and ev("S.den") == 3 and ev("S.copies") == 1, [ev("S.den"), ev("S.copies")])
    check("按住按钮在", cnt("#actions button.hold") == 1, cnt("#actions button.hold"))
    check("「1」记号在（第 3 站）", cnt("#dyn .one") >= 1, cnt("#dyn .one"))
    # 松手就停：按住 500 毫秒只摆 1 份（第 2 份），松手后不再走
    hold_btn(500)
    check("按住 500 毫秒松手：2 份", ev("S.copies") == 2 and readout() == "2 份 · 10 颗", [ev("S.copies"), readout()]); shot("3d-partial")
    page.wait_for_timeout(800); check("松手后份数不走", ev("S.copies") == 2, ev("S.copies"))
    focus(); page.keyboard.press("ArrowRight"); page.wait_for_timeout(300)
    check("1/3 没摆满不能换分母", ev("S.den") == 3 and ev("S.copies") == 2, [ev("S.den"), ev("S.copies")])
    hold_btn(1500)
    check("1/3 摆满：3 份", ev("S.copies") == 3 and 3 in ev("S.full"), [ev("S.copies"), ev("S.full")])
    check("1/3 摆满读数", readout() == "5 颗是一袋的 1 3 · 一整袋 15 颗", readout())
    st = sent("state")[-1]["payload"]; check("state 1/3 摆满", st == {"station": 3, "part": 5, "den": 3, "copies": 3, "whole": 15}, st); shot("3e-full3")
    check("只摆满 1/3 还没有「看明白了」", "看明白了" not in w.buttons(), w.buttons())
    check("1/3 摆满后出现分母托，选中的小圆片是圆钮", grips() == 1, grips())
    # 点小圆片换成 1/10，摆满：10 份 50 颗
    tap(*at("chipXY(10)")); page.wait_for_timeout(400)
    check("点小圆片选 1/10，份数回到 1", ev("S.den") == 10 and ev("S.copies") == 1, [ev("S.den"), ev("S.copies")])
    check("选中的小圆片是圆钮", grips() == 1, grips()); shot("3f-den10-first")
    hold_btn(6800, 3000, "3g-den10-mid")
    check("1/10 摆满：10 份", ev("S.copies") == 10 and 10 in ev("S.full"), [ev("S.copies"), ev("S.full")])
    check("1/10 摆满读数：50 颗", readout() == "5 颗是一袋的 1 10 · 一整袋 50 颗", readout())
    st = sent("state")[-1]["payload"]; check("state 1/10 摆满", st == {"station": 3, "part": 5, "den": 10, "copies": 10, "whole": 50}, st); shot("3h-full10")
    # ← 4 次从 10 走到 2（10 -> 5 -> 4 -> 3 -> 2），键盘按住空格摆满 1/2
    focus(); keys("ArrowLeft", 4, 150); page.wait_for_timeout(300)
    check("键盘 ← 4 次：换成 1/2，份数回到 1", ev("S.den") == 2 and ev("S.copies") == 1, [ev("S.den"), ev("S.copies")])
    hold_key(1500)
    check("键盘按住空格摆满 1/2", ev("S.copies") == 2 and 2 in ev("S.full"), [ev("S.copies"), ev("S.full")])
    check("1/2 摆满读数", readout() == "5 颗是一袋的 1 2 · 一整袋 10 颗", readout())
    st = sent("state")[-1]["payload"]; check("state 1/2 摆满", st == {"station": 3, "part": 5, "den": 2, "copies": 2, "whole": 10}, st); shot("3i-full2")
    check("三种分母摆满过", sorted(set(ev("S.full"))) == [2, 3, 10], ev("S.full"))
    check("三种分母摆满后出「看明白了」", "看明白了" in w.buttons(), w.buttons())
    btn("看明白了"); btn("还有呢"); page.wait_for_timeout(400); shot("3j-wow")
    check("到「哇」", ev("S.mode") == "wow", ev("S.mode"))
    check("蓝鲸读数（事实核对 R4：「大约」）", readout() == "蓝鲸大约 30 米 · 它的 1 10 是 3 米 · 两个舰长大约 260 厘米", readout())
    check("蓝鲸说 3 米", "3 米" in said(), said())
    btn("看我的星卡"); page.wait_for_timeout(300); shot("4-card")
    # ---------- 星卡和事件 ----------
    card = ev("S.card")
    check("星卡是孩子最后做到的：L=64、6 盘、1/2", card is not None and card.get("L") == 64 and card.get("plates") == 6 and card.get("den") == 2, card)
    text = ev("[...document.querySelectorAll('#dyn text')].map(t=>t.textContent).join('')").replace(" ", "")
    check("星卡数线条上挂「1 = 64 厘米」", "1=64厘米" in text, text[:160])
    evs = [(m["payload"]["verb"], m["payload"]["result"]) for m in sent("event")]
    check("predicted 三次带误区", [(e[1]["station"], e[1]["misconception"]) for e in evs if e[0] == "predicted"] == [(1, "ignore-the-whole"), (2, "numerator-as-count"), (3, "add-instead-of-copy")], evs)
    check("observed 三次", [e[1]["station"] for e in evs if e[0] == "observed"] == [1, 2, 3], evs)
    check("没有 answered", all(e[0] in ("predicted", "observed") for e in evs), evs); check("complete 一次", len(sent("complete")) == 1, len(sent("complete")))

    # ---------- 选站重玩（#154）：跳过开场和猜测，直接动手；揭晓完「回星卡」；事件每站只记第一次 ----------
    def events():
        evs = [(m["payload"]["verb"], m["payload"]["result"]["station"]) for m in sent("event")]
        return [e for e in evs if e[0] == "predicted"], [e for e in evs if e[0] == "observed"]
    before = events()
    check("星卡上能选站重玩", w.buttons() == ["从头玩", "第1站", "第2站", "第3站"], w.buttons())
    # 重玩第 3 站：1/3、1/4、1/5 各摆满，星卡的分母换成 1/5
    btn("第 3 站"); page.wait_for_timeout(400); shot("5a-replay3-first")
    check("重玩第 3 站：不问猜测题，直接动手", ev("S.station") == 3 and ev("S.mode") == "act3" and cnt("#actions .choice") == 0, [ev("S.station"), ev("S.mode")])
    check("重玩第 3 站：这一站复位（1/3、1 份）", ev("S.den") == 3 and ev("S.copies") == 1, [ev("S.den"), ev("S.copies")])
    check("重玩第 3 站：第一屏没有圆钮（分母托收起，G5）", grips() == 0, grips())
    hold_btn(1600); check("重玩第 3 站：1/3 摆满", ev("S.copies") == 3, ev("S.copies"))
    focus(); keys("ArrowRight", 1, 300); hold_btn(2500); check("重玩第 3 站：1/4 摆满", ev("S.den") == 4 and ev("S.copies") == 4, [ev("S.den"), ev("S.copies")])
    focus(); keys("ArrowRight", 1, 300); hold_btn(3300); check("重玩第 3 站：1/5 摆满", ev("S.den") == 5 and ev("S.copies") == 5, [ev("S.den"), ev("S.copies")])
    btn("看明白了"); btn("还有呢")
    check("重玩一站揭晓完是「回星卡」", w.buttons() == ["回星卡"], w.buttons())
    btn("回星卡"); page.wait_for_timeout(300); check("回到星卡", ev("S.mode") == "end", ev("S.mode"))
    check("星卡换成这次摆满的 1/5，别的不变", ev("S.card.den") == 5 and ev("S.card.L") == 64 and ev("S.card.plates") == 6, ev("S.card"))
    # 重玩第 1 站：从头复位，停在 40 和 48
    btn("第 1 站"); page.wait_for_timeout(400); shot("5b-replay1-first")
    check("重玩第 1 站：不问猜测题，直接动手，这一站复位", ev("S.station") == 1 and ev("S.mode") == "act1" and ev("S.L") == 16 and not ev("S.stop40") and not ev("S.stop48") and cnt("#actions .choice") == 0, [ev("S.mode"), ev("S.L"), ev("S.stop40"), ev("S.stop48")])
    check("重玩第 1 站：第一屏 1 个圆钮", grips() == 1, grips())
    focus(); keys("ArrowRight", 3); page.wait_for_timeout(700); keys("ArrowRight", 1); page.wait_for_timeout(700)
    check("重玩第 1 站：键盘走到 40 再到 48", ev("S.L") == 48 and ev("S.stop40") is True and ev("S.stop48") is True, [ev("S.L"), ev("S.stop40"), ev("S.stop48")])
    btn("看明白了"); btn("我来说"); btn("大"); btn("还有呢")
    check("重玩一站揭晓完是「回星卡」（第 1 站）", w.buttons() == ["回星卡"], w.buttons())
    btn("回星卡"); page.wait_for_timeout(300); shot("5c-card-again")
    text = ev("[...document.querySelectorAll('#dyn text')].map(t=>t.textContent).join('')").replace(" ", "")
    check("星卡换成这次停的 L=48", ev("S.card.L") == 48 and "1=48厘米" in text, [ev("S.card"), text[:120]])
    check("重玩一站不多记猜测和完成", events() == before, [before, events()]); check("重玩一站不再发 complete", len(sent("complete")) == 1, len(sent("complete")))
    btn("从头玩"); page.wait_for_timeout(300)
    check("从头玩回到第 1 站，复位", ev("S.station") == 1 and ev("S.mode") == "intro1" and ev("S.L") == 16, [ev("S.station"), ev("S.mode"), ev("S.L")]); shot("5-replay")
    check("页面没有横向溢出", ev("document.documentElement.scrollWidth <= innerWidth"), ev("document.documentElement.scrollWidth"))


if __name__ == "__main__":
    walklib.main(play)
