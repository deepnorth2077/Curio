# Curio · 掰巧克力走查。用法：python tools/walks/act.simulation.chocolate-split-01.py <index.html> <截图目录> [--only tablet|phone|desk]
# 三种屏幕从头玩到尾，覆盖三站核心交互（拉开包装纸与拖缝、拼不齐与拼成整块、拨盘魔术机）及星卡选站重玩。
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib  # noqa: E402


def play(w):
    name, touch, page = w.name, w.touch, w.page
    ev, check, btn, shot, pt = w.ev, w.check, w.btn, w.shot, w.pt
    readout, said, sent = w.readout, w.said, w.sent

    w.open()
    first = ev("window.__sent[0].type")
    check("ready 先于别的消息", first == "ready", first)
    if name == "phone":
        check("独立深色模式自动挂上 .kit-dark", ev("document.documentElement.classList.contains('kit-dark')"), True)

    # ---------- 第 1 站：掰开 ----------
    shot("1a-intro")
    check("开场错账 19 块", readout() == "3×5 + 4 = 19 块", readout())
    btn("继续")
    btn("帮你找找")
    shot("1b-ask")
    btn("4 块")
    check("猜错用温和气泡", "hmm" in ev("document.getElementById('say').className"))
    btn("拉开包装纸")
    page.wait_for_timeout(200)
    shot("1c-wrap-first", first=True)
    check("包装纸还遮着时，缝上没有圆钮", w.grips() == 0, w.grips())

    # 同一格内的两次移动隔开 35ms，避免音效自身的节流掩盖重复发声。
    x, y = pt(*ev("[400, wrapTop(0)]"))
    _, next_y = pt(*ev("[400, wrapTop(1 / 8)]"))
    seq = ev("Sfx.seq()")
    w.mouse_drag([(x, y), (x + 3, y + 2), (x - 3, y + 1)], step_ms=70, release=False)
    check("包装纸在同一格内来回拖不响", ev("Sfx.seq()") == seq, ev("Sfx.seq()") - seq)
    page.mouse.move(x, next_y)
    check("包装纸拖过一格只响一次", ev("Sfx.seq()") == seq + 1, ev("Sfx.seq()") - seq)
    page.mouse.up()

    # 键盘拉到底，揭晓漏掉的 16 块
    page.locator("#stage").focus()
    for _ in range(4):
        page.keyboard.press("ArrowDown")
    page.wait_for_timeout(450)
    check("包装纸拉到底转入拖缝", ev("S.wrapDone") is True and ev("S.phase1") == "seam", [ev("S.wrapDone"), ev("S.phase1")])
    check("缝可以拖动时出现一个青绿圆钮", w.grips() == 1, w.grips())
    check("读数纠正为 35 块", readout() == "3×5 = 15 · 4×5 = 20 · 一共 35 块", readout())
    shot("1d-unwrapped")

    # 拖那条缝从 3 到 2，再用键盘试 3 和 4（共 3 条缝）
    sx, sy = pt(*ev("[seamX(S.kp), L1.knobY]"))
    tx, _ = pt(*ev("[seamX(2), L1.knobY]"))
    path = [(sx, sy)] + [(sx + (tx - sx) * i / 10, sy) for i in range(1, 11)]
    if touch and name == "phone":
        w.touch_drag(path, no_scroll="拖缝时页面不滚")
    else:
        w.mouse_drag(path)
    page.wait_for_timeout(300)
    check("拖到第 2 条缝也是 35 块", ev("S.ks") == 2 and readout() == "2×5 = 10 · 5×5 = 25 · 一共 35 块", [ev("S.ks"), readout()])
    shot("1e-seam2")

    page.locator("#stage").focus()
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(200)
    check("第 2 个停点说出乘法分配律", "乘法分配律" in said(), said())
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(300)
    check("试够 3 条缝进揭晓", ev("S.scene") == "s1r", ev("S.scene"))
    shot("1f-reveal")
    btn("还有呢")
    btn("去第 2 站")

    # ---------- 第 2 站：拼起来 ----------
    shot("2a-ask")
    btn("能，就是 (3+4)×5")
    btn("拼拼看")
    page.wait_for_timeout(200)
    shot("2b-act-first", first=True)

    # 先把 4×6（C）拖到拼台槽位：多出一排
    cx, cy = pt(*ev("(()=>{const r=pieceRect('C');return [r.x+40,r.y+40]})()"))
    gx, gy = pt(*ev("[L2.slot.x+40, L2.slot.y+40]"))
    path2 = [(cx, cy)] + [(cx + (gx - cx) * i / 12, cy + (gy - cy) * i / 12) for i in range(1, 13)]
    if touch and name == "phone":
        w.touch_drag(path2, no_scroll="拖巧克力块时页面不滚")
    else:
        w.mouse_drag(path2)
    page.wait_for_timeout(450)
    check("4×6 拼不齐，多出 4 块", ev("S.triedC") is True and "多出 4 块" in readout(), [ev("S.triedC"), readout()])
    shot("2c-mismatch")

    # 等 C 滑回原处、放出 4×5（B），再拼好
    page.wait_for_timeout(2700)
    check("放出 4×5 那块 B", ev("S.pc.B.shown") is True, ev("S.pc.B.shown"))
    page.locator("#stage").focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(1500)
    check("4×5 拼成整块进入揭晓", ev("S.merged") is True and ev("S.mode") == "talk", [ev("S.merged"), ev("S.mode")])
    shot("2d-merged")
    btn("还有呢")
    btn("去第 3 站")

    # ---------- 第 3 站：乘 101 的魔术机 ----------
    shot("3a-ask")
    btn("3701")
    btn("打开魔术机")
    page.wait_for_timeout(200)
    shot("3b-act-first", first=True)
    check("开机读数 37×101 = 3737", readout() == "37×100 = 3700 · 37×1 = 37 · 一共 3737", readout())

    page.locator("#stage").focus()
    page.keyboard.press("ArrowUp")
    page.wait_for_timeout(950)
    check("拨到 47 记录新数", 47 in ev("S.tried") and "4747" in readout(), [ev("S.tried"), readout()])
    shot("3c-n47")

    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(950)
    check("试够 3 个两位数进入揭晓", ev("S.scene") == "s3r", ev("S.scene"))
    shot("3d-reveal")
    btn("还有呢")
    check("三位数反例 12423", "12423" in said(), said())
    btn("看我的星卡")
    page.wait_for_timeout(300)
    shot("4-card")

    # ---------- 事件与选站重玩 ----------
    evs = [(m["payload"]["verb"], m["payload"]["result"]) for m in sent("event")]
    check("predicted 三次带误区", [(e[1]["station"], e[1]["misconception"]) for e in evs if e[0] == "predicted"] ==
          [(1, "multiply-one-part"), (2, "merge-unlike"), (3, "multiply-one-part")], evs)
    check("observed 三次", [e[1]["station"] for e in evs if e[0] == "observed"] == [1, 2, 3], evs)
    check("complete 一次", len(sent("complete")) == 1, len(sent("complete")))
    check("星卡上能选站重玩", w.buttons() == ["从头玩", "第1站", "第2站", "第3站"], w.buttons())

    before = len(evs)
    btn("第 3 站")
    page.wait_for_timeout(300)
    check("重玩第 3 站跳过猜测直接进魔术机", ev("S.station") == 3 and ev("S.mode") == "act3", [ev("S.station"), ev("S.mode")])
    page.locator("#stage").focus()
    page.keyboard.press("ArrowUp")
    page.wait_for_timeout(950)
    page.keyboard.press("ArrowUp")
    page.wait_for_timeout(950)
    btn("还有呢")
    check("重玩揭晓后显示回星卡", w.buttons() == ["回星卡"], w.buttons())
    btn("回星卡")
    page.wait_for_timeout(250)
    check("重玩不重复记事件和 complete", len(sent("event")) == before and len(sent("complete")) == 1, [len(sent("event")), len(sent("complete"))])
    check("页面没有横向溢出", ev("document.documentElement.scrollWidth <= innerWidth"), ev("document.documentElement.scrollWidth"))


if __name__ == "__main__":
    walklib.main(play)
