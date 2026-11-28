# Curio · 货舱里的杠杆（v4，交付 A：开场 + 第 1 站 + 临时结尾）走查。
# 用法：python tools/walks/act.simulation.lever-dock-01.py <index.html> <截图目录> [--only tablet|phone|desk]
# 期望值来自 tools/tests/fixtures/expected/lever-dock.json，由任务说明 v5 手算；不读模块代码，不能为了通过去改。
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import walklib  # noqa: E402

EXP = json.loads((TOOLS / "tests/fixtures/expected/lever-dock.json").read_text(encoding="utf-8"))
INTRO, S1 = EXP["intro"], EXP["station1"]
HOLES = {h["k"]: h for h in S1["holes"]}


def ns(s):
    return re.sub(r"\s+", "", s or "")


def play(w):
    page, ev, check, btn, shot = w.page, w.ev, w.check, w.btn, w.shot

    def box(part):
        return ev("(()=>{const e=document.querySelector('[data-part=%s]');if(!e)return null;const r=e.getBoundingClientRect();"
                  "return {x:r.x,y:r.y,w:r.width,h:r.height,b:r.bottom}})()" % part)

    def text(sel):   # innerText；SVG 元素没有 innerText 时退到 textContent
        return ns(ev("(()=>{const e=document.querySelector(%s);return e?(e.innerText??e.textContent):''})()" % json.dumps(sel)))

    def state():
        return w.sent("state")[-1]["payload"]

    def events(verb):
        return [m["payload"]["result"] for m in w.sent("event") if m["payload"]["verb"] == verb]

    def can_finish():
        return ev("[...document.querySelectorAll('#actions button')].some(b=>/就这样/.test(b.innerText)&&!b.disabled)")

    def same(a, b, tol=1):
        return all(abs(a[k] - b[k]) <= tol for k in ("x", "y", "w", "h"))

    cur = {"k": 1}

    def goto(k):   # 键盘一次一格：← 往外（格数加一），→ 往里。次数是算好的，不用 while
        n = k - cur["k"]
        for _ in range(abs(n)):
            page.keyboard.press("ArrowLeft" if n > 0 else "ArrowRight")
            page.wait_for_timeout(120)
        cur["k"] = k
        page.wait_for_timeout(1800 if k >= 7 else 900)

    def to_choices():   # 开场可能有几句要点「下一句」；最多点 4 次，直到出现三个选项
        for _ in range(4):
            if ev("document.querySelectorAll('#actions .choice').length") > 0:
                return
            first = ev("(document.querySelector('#actions button')||{innerText:''}).innerText.replace(/\\s+/g,'')")
            if not first:
                return
            btn(first)

    def to_end():   # 揭晓之后到临时结尾：最多点 4 次，直到出现「再玩一次」
        for _ in range(4):
            if "再玩一次" in w.buttons():
                return
            first = ev("(document.querySelector('#actions button')||{innerText:''}).innerText.replace(/\\s+/g,'')")
            if not first:
                return
            btn(first)

    def ending_dx():   # 结尾小图里铁环相对支点的水平偏移；取页面里最后一枚铁环和最后一个支点
        return ev("(()=>{const rs=[...document.querySelectorAll('[data-part=ring]')],ps=[...document.querySelectorAll('[data-part=pivot]')];"
                  "if(!rs.length||!ps.length)return null;const r=rs[rs.length-1].getBoundingClientRect(),p=ps[ps.length-1].getBoundingClientRect();"
                  "return r.x+r.width/2-(p.x+p.width/2)})()")

    w.open()
    check("ready 先于别的消息", w.sent()[0]["type"] == "ready", w.sent()[:1])

    # ---------- 开场 ----------
    shot("1-intro")
    check("开场没有木杆", box("beam") is None or box("beam")["w"] == 0, box("beam"))
    check("开场秤秤屏幕是 6", text("[data-part=robot-screen]") == str(INTRO["screen_at_open"]), text("[data-part=robot-screen]"))
    to_choices(); shot("2-ask")
    labels = ev("[...document.querySelectorAll('#actions .choice')].map(b=>b.innerText.replace(/\\s+/g,''))")
    check("三个选项的文字和顺序", labels == [ns(o["text"]) for o in INTRO["options"]], labels)
    check("提问时还没有铁环", ev("document.querySelectorAll('[data-part=ring]').length") == 0 or box("ring") is None or box("ring")["w"] == 0, None)
    btn(INTRO["options"][0]["text"])   # 第 1 个：heavy-wins（错）
    pred = events("predicted")
    check("predicted 一次，开场 station 1", len(pred) == 1 and pred[0].get("station") == 1, pred)
    check("heavy-wins：correct false、误区 id", pred and pred[0].get("correct") is False and pred[0].get("misconception") == "heavy-wins", pred)
    check("猜错用中性气泡", "hmm" in ev("document.getElementById('say').className"), ev("document.getElementById('say').className"))
    check("heavy-wins 反馈原句", INTRO["say_wrong_heavy_wins"] in ns(ev("document.getElementById('say').innerText")), ev("document.getElementById('say').innerText"))
    page.wait_for_timeout(1200)

    # ---------- 第 1 站：动手 ----------
    shot("3-act-first", first=True)
    check("#station 写第 1 站", text("#station") == S1["station_label"], text("#station"))
    check("左下提示是一句话目标", S1["hint"] in text("#hint"), text("#hint"))
    check("开场状态：铁环在第 1 格、屏幕 5", text("[data-part=robot-screen]") == "5", text("[data-part=robot-screen]"))
    check("读数「铁环：第 1 格」，还没有乘法", text("#readout") == "铁环：第1格", text("#readout"))
    check("第 1 站没有「就这样」", not can_finish(), w.buttons())
    page.locator("#stage").focus()
    beam0, crate0, robot0 = box("beam"), box("crate"), box("robot")
    check("木杆、箱子、秤秤都在画面上", all(b and b["w"] > 0 for b in (beam0, crate0, robot0)), [beam0, crate0, robot0])
    robot_top0 = robot0["y"]

    # 铁环依次第 1～6 格
    for k in range(1, 7):
        if k > 1:
            goto(k)
        e, st = HOLES[k], state()
        check(f"第 {k} 格：秤秤屏幕 {e['screen']}", text("[data-part=robot-screen]") == str(e["screen"]), text("[data-part=robot-screen]"))
        check(f"第 {k} 格：state hole/screen/lifted/robot_out", (st.get("station"), st.get("hole"), st.get("screen"), st.get("lifted"), st.get("robot_out")) == (1, k, e["screen"], False, False), st)
        check(f"第 {k} 格：杆保持水平、箱子秤秤不动", same(box("beam"), beam0) and same(box("crate"), crate0) and same(box("robot"), robot0), [box("beam"), beam0])
        check(f"第 {k} 格：读数「铁环：第 {k} 格」", text("#readout") == f"铁环：第{k}格", text("#readout"))
        check(f"第 {k} 格：还不能按「就这样」", not can_finish(), w.buttons())
        if k == 2:
            said = ns(ev("document.getElementById('say').innerText"))
            check("第一次松手说出「杠杆」「支点」", "杠杆" in said and "支点" in said, said)
        if k == 3:
            said = ns(ev("document.getElementById('say').innerText"))
            check("屏幕 3：往外一格少压 1 牛", "少压秤秤1牛" in said, said)
        if k == 6:
            said = ns(ev("document.getElementById('say').innerText"))
            check("第 6 格：秤秤说「一点都不压了」，箱子仍挨着", "一点都不压了" in said and "出不去" in said, said)
            shot("4-hole6")
            gap6 = robot_top0 - box("crate")["b"]
            check("第 6 格箱底还挨着秤秤（空隙小于 12）", gap6 < S1["min_gap_px"], gap6)

    # 第 7 格：翘起
    goto(7)
    e, st, gap = HOLES[7], state(), robot_top0 - box("crate")["b"]
    print(f"  第 7 格箱底和秤秤原顶边的空隙：{gap:.1f} CSS px（{w.name}）")
    check("第 7 格：屏幕 0", text("[data-part=robot-screen]") == "0", text("[data-part=robot-screen]"))
    check("第 7 格：state lifted、robot_out", (st.get("hole"), st.get("screen"), st.get("lifted"), st.get("robot_out")) == (7, 0, True, True), st)
    check(f"第 7 格：箱底和秤秤原顶边空隙 ≥ {S1['min_gap_px']} CSS px", gap >= S1["min_gap_px"], gap)
    check("第 7 格：杆转动了（和水平时不同）", not same(box("beam"), beam0, 1.5), [box("beam"), beam0])
    rb = box("robot")
    check("第 7 格：秤秤开出来了（位置变了）", abs(rb["x"] - robot0["x"]) > 10 or abs(rb["y"] - robot0["y"]) > 10, [rb, robot0])
    said = ns(ev("document.getElementById('say').innerText"))
    check("第 7 格：领航员说「箱子没变轻」", "箱子没变轻" in said, said)
    check("第 7 格可按「就这样」", can_finish(), w.buttons())
    shot("5-wow")

    # 退回第 5 格
    goto(5)
    st = state()
    check("退回第 5 格：robot_out 仍是 true、lifted false", (st.get("hole"), st.get("robot_out"), st.get("lifted")) == (5, True, False), st)
    check("退回第 5 格：屏幕显示 0（秤秤身上没东西）", text("[data-part=robot-screen]") == "0", text("[data-part=robot-screen]"))
    check("退回第 5 格：箱子比开场更低（落到地板）", box("crate")["b"] > crate0["b"] + 4, [box("crate")["b"], crate0["b"]])
    check("退回第 5 格：「就这样」不可用", not can_finish(), w.buttons())
    shot("6-back5")

    # 第 8 格，按「就这样」
    goto(8)
    st = state()
    gap8 = robot_top0 - box("crate")["b"]
    check("第 8 格：state lifted、robot_out", (st.get("hole"), st.get("lifted"), st.get("robot_out")) == (8, True, True), st)
    check(f"第 8 格：空隙 ≥ {S1['min_gap_px']} CSS px", gap8 >= S1["min_gap_px"], gap8)
    check("第 8 格可按「就这样」", can_finish(), w.buttons())
    check("按之前读数里没有乘法", "×" not in text("#readout"), text("#readout"))
    btn("就这样")
    obs = events("observed")
    check("observed 一次，station 1", len(obs) == 1 and obs[0].get("station") == 1, obs)
    check("揭晓说「第 6 格刚好打平」", S1["reveal_say"] in ns(ev("document.getElementById('say').innerText")), ev("document.getElementById('say').innerText"))
    check("揭晓后读数出现乘法", "×" in text("#readout"), text("#readout"))
    shot("7-reveal")
    to_end(); page.wait_for_timeout(500)
    shot("8-end")
    body = ns(ev("document.body.innerText"))
    check("临时结尾：#station 写「星卡」", text("#station") == S1["end_station"], text("#station"))
    check("临时结尾：标题「第 1 站完成」", S1["end_title"] in body, body[:200])
    check("临时结尾：「1 枚铁环，第 8 格，翘起 6 牛」", S1["end_caption"]["8"] in body, body[:300])
    check("临时结尾有「再玩一次」", "再玩一次" in w.buttons(), w.buttons())
    check("complete 一次，payload 空", [m["payload"] for m in w.sent("complete")] == [{}], w.sent("complete"))
    dx8 = ending_dx()
    check("结尾小图里有铁环和支点", dx8 is not None, dx8)

    # ---------- 再玩一次：停在第 7 格 ----------
    btn("再玩一次"); to_choices()
    check("再玩一次回到开场（三个选项）", ev("document.querySelectorAll('#actions .choice').length") == 3, w.buttons())
    btn(INTRO["options"][1]["text"])   # 第 2 个：正确答案
    check("猜对用的不是 hmm 气泡", "hmm" not in ev("document.getElementById('say').className"), ev("document.getElementById('say').className"))
    check("猜对反馈原句", INTRO["say_right"] in ns(ev("document.getElementById('say').innerText")), ev("document.getElementById('say').innerText"))
    page.wait_for_timeout(1200)
    st = state()
    check("再玩一次后全部复位", (st.get("hole"), st.get("lifted"), st.get("robot_out")) == (1, False, False), st)
    check("再玩一次后屏幕回到 5", text("[data-part=robot-screen]") == "5", text("[data-part=robot-screen]"))
    check("再玩一次后「就这样」不可用", not can_finish(), w.buttons())
    page.locator("#stage").focus(); cur["k"] = 1
    goto(7)
    check("第二遍第 7 格可按「就这样」", can_finish(), w.buttons())
    btn("就这样")
    check("第二遍读数「1 × 7 = 7 · 比 6 多 · 翘起」", text("#readout") == S1["reveal_readout_k7"], text("#readout"))
    to_end(); page.wait_for_timeout(500)
    shot("9-end-again")
    body = ns(ev("document.body.innerText"))
    check("第二遍结尾：「1 枚铁环，第 7 格，翘起 6 牛」", S1["end_caption"]["7"] in body, body[:300])
    dx7 = ending_dx()
    check("结尾小图里的铁环位置和第 8 格那次不同（第 7 格在里侧）", dx8 is not None and dx7 is not None and dx8 < dx7 - 2, [dx8, dx7])
    check("再玩一次以后 complete 仍只一次", len(w.sent("complete")) == 1, len(w.sent("complete")))
    check("predicted、observed 各只记第一次", len(events("predicted")) == 1 and len(events("observed")) == 1, [events("predicted"), events("observed")])
    check("页面没有横向溢出", ev("document.documentElement.scrollWidth <= innerWidth"), ev("document.documentElement.scrollWidth"))


if __name__ == "__main__":
    walklib.main(play)
