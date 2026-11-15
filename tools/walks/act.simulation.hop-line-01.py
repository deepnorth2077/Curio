# Curio · 数线跳跳走查。用法：python tools/walks/act.simulation.hop-line-01.py <index.html> <截图目录> [--only tablet|phone|desk]
# 三种屏幕从头玩到尾，逐站截图；g1.md C.2 第 2 节的验收用例写成断言。期望值不能为了通过去改（受保护路径）。
#
# 旗的键盘：起点 1.75，每按一次 0.02，只能走到奇数位（0.99、0.37、0.35……），踩不到 0.36 和 0.78。
# 所以第 1 面旗用键盘走到 0.99 插下（落在验收表「0.92 到 1.08」里），后两面按验收表的原值（0.36、0.78）用拖的。
# 不要写「按键直到等于某个值」的 while 循环：走不到的值会让它永远不停。
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib  # noqa: E402


def play(w):
    name, rm, touch, page = w.name, w.rm, w.touch, w.page
    ev, check, btn, shot, pt = w.ev, w.check, w.btn, w.shot, w.pt
    readout, said, sent, grips, cue = w.readout, w.said, w.sent, w.grips, w.cue

    def hop(n=1):
        for _ in range(n):
            btn("跳一步"); page.wait_for_timeout(520)

    w.open()
    first = ev("window.__sent[0].type"); check("ready 先于别的消息", first == "ready", first)
    # ---------- 第 1 站 ----------
    shot("1a-intro"); btn("然后呢"); shot("1b-ask"); check("提问时没有圆钮", grips() == 0, grips())
    n_fs = ev("document.querySelectorAll('#dyn .fs').length")   # .fs 是 SVG 里的分数标签；「1」记号牌用 .one 和 .fm，不算
    check("提问时 0 和 1 之间是空的：一个分数标签都没有", ev("S.steps") == 0 and n_fs == 0, [ev("S.steps"), n_fs])
    btn("没有，0 后面就是 1"); check("猜错用中性气泡", "hmm" in ev("document.getElementById('say').className")); btn("让火箭跳"); shot("1c-act-first", first=True)
    hop(1); shot("1d-hop1"); hop(2)
    check("跳 3 步读数", readout() == "跳了 3 步 · 3 个 1 4 是 3 4", readout())
    st = sent("state")[-1]["payload"]; check("state 第 1 站", st == {"station": 1, "den": 4, "steps": 3}, st)
    check("3/4 时说名字", "四分之三" in said(), said()); shot("1e-hop3")
    rx = ev("X(pos(S.steps,S.den))"); check("火箭在 0 到 1 的四分之三处", abs(rx - (140 + 260 * .75)) < .01, rx)
    hop(1); check("跳 4 步读数", readout() == "跳了 4 步 · 4 个 1 4 正好是 1", readout()); check("到 1 以后出现步长的托", ev("S.scene") == "s1c", ev("S.scene"))
    page.wait_for_timeout(300); shot("1f-chooser-first"); check("托里还没有选中的", grips() == 0, grips())
    if rm == "no-preference":
        page.wait_for_timeout(1500); check("1.5 秒后提醒托", cue()); shot("1g-cue")
    hop(1); check("彩蛋：跳过 1 标 5/4", readout() == "跳了 5 步 · 5 个 1 4 是 5 4" and "比 1 大" in said(), [readout(), said()]); shot("1h-over1")
    # 点小圆片选 1/5
    cx, cy = pt(*ev("(()=>{const c=chipPos(2);return [c.x,c.y]})()"))
    if touch: page.touchscreen.tap(cx, cy)
    else: page.mouse.click(cx, cy)
    page.wait_for_timeout(300)
    check("选了每步 1/5", ev("S.den") == 5 and ev("S.steps") == 0 and ev("S.trip") == 2, [ev("S.den"), ev("S.steps"), ev("S.trip")])
    check("碰过以后不再提醒", not cue()); check("选中的小圆片填成圆钮色", grips() == 1, grips())
    xs = []
    for _ in range(5):
        hop(1); xs.append(ev("X(pos(S.steps,S.den))"))
    gaps = [round(xs[i + 1] - xs[i], 3) for i in range(4)]
    check("每步 1/5 步子一样宽，5 步落在 1 上", len(set(gaps)) == 1 and abs(xs[-1] - 400) < .01, [gaps, xs[-1]])
    check("第二趟到 1 以后可以走了", ev("S.done2") is True and page.locator("#actions button", has_text="看明白了").count() == 1, ev("S.done2")); shot("1i-ready")
    page.locator("#stage").focus(); page.keyboard.press("ArrowRight"); page.wait_for_timeout(200)
    check("键盘 → 换步长", ev("S.den") == 6, ev("S.den"))
    page.keyboard.press("Enter"); page.wait_for_timeout(600); check("键盘回车跳一步", ev("S.steps") == 1, ev("S.steps"))
    # 走到这里：1/5 跳到了 1，又换成 1/6 只跳了一步。星卡只能画孩子真做到的事（教训 12）：
    # 用最后一种「跳到 1」的步长，也就是 1/5；1/6 没跳完，不能画成「跳了 6 步到 1」
    last_den = 5
    btn("看明白了"); btn("我来说"); shot("1j-say"); btn("3"); btn("还有呢"); shot("1k-reveal"); btn("去第 2 站")
    # ---------- 第 2 站 ----------
    shot("2a-intro"); btn("然后呢"); shot("2b-ask")
    check("提问时没有圆钮、没有「1」记号", grips() == 0 and ev("document.querySelectorAll('#dyn .one').length") == 0, [grips(), ev("document.querySelectorAll('#dyn .one').length")])
    btn("乙"); btn("我来插"); page.wait_for_timeout(300); shot("2c-act-first", first=True); check("第 2 站第一屏 1 个圆钮", grips() == 1, grips())

    def drag_flag(to, mid=None):
        fx, fy = pt(*ev("[X(S.fp), FY + gripR()*.2]")); tx, _ = pt(*ev(f"[X({to}), FY]"))
        before = (lambda: (page.wait_for_timeout(200), shot(mid))) if mid else None
        if touch and name == "phone":   # 真实触摸事件（教训 25）
            path = [(fx, fy)] + [(fx + (tx - fx) * i / 14, fy + 30 * math.sin(i)) for i in range(1, 15)]
            w.touch_drag(path, before_release=before, no_scroll="拖旗时页面不滚")
        else:
            path = [(fx, fy)] + [(fx + (tx - fx) * i / 14, fy) for i in range(1, 15)]
            w.mouse_drag(path, before_release=before)
        page.wait_for_timeout(250)
    # 第 1 面旗（1/2）：键盘从 1.75 走到 0.99（38 步），回车插下。验收表：插在 0.92 到 1.08 之间 → 差得远
    page.locator("#stage").focus()
    for _ in range(38): page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(500)
    check("键盘移旗：1.75 往左 38 步到 0.99", abs(ev("S.fv") - 0.99) < 1e-6, ev("S.fv"))
    page.keyboard.press("Enter"); page.wait_for_timeout(300)
    f = ev("S.planted[0]"); check("1/2 插在 1 附近：差得远", f["grade"] == "far" and 0.92 <= f["drop"] <= 1.08, f)
    check("专门说那里是 1", "那里是 1" in said() and "正中间" in said(), said())
    page.wait_for_timeout(900); shot("2e-far")
    check("旗滑到 0.5，原地留影子", abs(ev("S.planted[0].px") - .5) < .01 and ev("document.querySelectorAll('#dyn .kf').length") >= 1, ev("S.planted[0].px"))
    check("说话时没有圆钮", grips() == 0, grips()); btn("下一面旗")
    # 第 2 面旗（1/4）：拖到 0.36 → 差一点
    page.wait_for_timeout(300)
    drag_flag(0.36, "2d-dragging")
    st = sent("state")[-1]["payload"]
    check("1/4 插在 0.36：差一点", st == {"station": 2, "flag": "1/4", "drop": 0.36, "target": 0.25, "grade": "near"}, st); page.wait_for_timeout(800); shot("2f-near")
    btn("下一面旗"); page.wait_for_timeout(300)
    # 第 3 面旗（3/4）：拖到 0.78 → 正中，滑到 0.75
    drag_flag(0.78); page.wait_for_timeout(900)
    f = ev("S.planted[2]"); check("3/4 插在 0.78：正中，滑到 0.75", f["grade"] == "hit" and f["drop"] == 0.78 and abs(f["px"] - .75) < .005, f)
    shot("2g-three"); n_q = ev("document.querySelectorAll('#dyn g[aria-label=\"四分之二\"]').length")
    check("三面旗后 2/4 的标签在 1/2 的旗下面", n_q == 1, n_q)
    # 容差边界（g1.md C.2 验收表）：压在边界上的值，两边要判得一样。直接调页面里的评级函数，不用再插旗
    got = ev("[grade(0.54, .5), grade(0.46, .5), grade(0.55, .5), grade(0.45, .5), grade(0.62, .5), grade(0.38, .5), grade(0.63, .5), grade(0.37, .5)]")
    check("容差边界：0.54/0.46 正中，0.55/0.45/0.62/0.38 差一点，0.63/0.37 差得远", got == ["hit", "hit", "near", "near", "near", "near", "far", "far"], got)
    bad = ev("""(() => { const bad = [], r2 = v => Math.round(v * 100) / 100;
      for (const t of [0.25, 0.5, 0.75]) for (let k = -20; k <= 20; k++) { const drop = r2(t + k / 100); if (drop < 0 || drop > 2) continue;
        const di = Math.abs(Math.round(drop * 100) - Math.round(t * 100)), want = di <= 4 ? "hit" : di <= 12 ? "near" : "far", g = grade(drop, t);
        if (g !== want) bad.push([t, drop, g, want]); }
      return bad; })()""")
    check("容差边界：0.25、0.5、0.75 各 ±0.20 内每个插法的评级和整数比较一致", bad == [], bad[:5])
    btn("看一看"); shot("2h-reveal"); btn("还有呢"); check("埋了伏笔", "同一个地方" in said(), said()); btn("去第 3 站")
    # ---------- 第 3 站 ----------
    shot("3a-intro"); btn("然后呢"); shot("3b-ask"); btn("100 个"); btn("动手拧"); page.wait_for_timeout(300); shot("3c-act-first", first=True)
    check("第 3 站第一屏 1 个圆钮", grips() == 1, grips())
    page.locator("#stage").focus()
    for n in [2, 3, 4, 5, 6, 8, 10, 12, 20, 50, 100, 1000]:
        w.step(f"拧到 {n}")
        page.keyboard.press("ArrowRight"); page.wait_for_timeout(760 if n in (2, 4, 50, 100, 1000) or name == "desk" else 120)
        if n in (2, 4, 50, 100, 1000) or name == "desk":
            check(f"读数 n={n}", readout() == f"平均分成 {n} 段 · 0 和 1 之间多出 {n - 1} 个数", readout())
            if n in (4, 50, 100, 1000): shot(f"3d-n{n}")
        if n == 20: check("还没到 100 不能走", page.locator("#actions button", has_text="看一看").count() == 0)
    st = sent("state")[-1]["payload"]; check("state 第 3 站", st == {"station": 3, "den": 1000, "between": 999}, st)
    gx, gy = pt(*ev("dialGrip()"))
    path = [(gx, gy)] + [tuple(pt(*ev(f"pol(DIAL.x,DIAL.y,dialGripR(),{360 - 30 * i / 8})"))) for i in range(1, 9)]
    w.mouse_drag(path, step_ms=15); page.wait_for_timeout(800); check("拖圆钮退到 100", ev("gearN()") == 100, ev("gearN()"))
    btn("看一看"); page.wait_for_timeout(400); shot("3e-wow"); check("揭晓后没有圆钮", grips() == 0, grips()); btn("再密呢"); shot("3f-wow2"); btn("看我的星卡"); page.wait_for_timeout(300); shot("4-card")
    got = [ev("S.lastDen"), ev("S.planted.length"), ev("S.best")]
    check("星卡：最后一种跳到 1 的步长（1/5，不是只跳了一步的 1/6）、三面旗、拧到的最密一档", got == [last_den, 3, 1000], got)
    card = ev("[...document.querySelectorAll('#dyn text')].map(t=>t.textContent).join('')")
    check("星卡第一层写的是 5 步到 1", "跳了 5 步到 1" in card, card[:120])
    evs = [(m["payload"]["verb"], m["payload"]["result"]) for m in sent("event")]
    check("predicted 三次带误区", [(e[1]["station"], e[1]["misconception"]) for e in evs if e[0] == "predicted"] == [(1, "no-numbers-between"), (2, "whole-line-as-one"), (3, "count-ticks-not-steps")], evs)
    check("observed 三次", [e[1]["station"] for e in evs if e[0] == "observed"] == [1, 2, 3], evs)
    check("没有 answered", all(e[0] in ("predicted", "observed") for e in evs), evs); check("complete 一次", len(sent("complete")) == 1, len(sent("complete")))
    btn("再玩一次"); page.wait_for_timeout(300)
    check("再玩一次回到第 1 站", ev("S.station") == 1 and ev("S.steps") == 0 and ev("S.scene") == "s1", [ev("S.station"), ev("S.steps"), ev("S.scene")]); shot("5-replay")
    check("页面没有横向溢出", ev("document.documentElement.scrollWidth <= innerWidth"), ev("document.documentElement.scrollWidth"))


if __name__ == "__main__":
    walklib.main(play)
