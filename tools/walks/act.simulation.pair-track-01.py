"""两车同时互推；既核对车上两支箭头，也核对同一秒的速度变化与落签。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import walklib


def play(w):
    w.open(hosted=True)
    w.check("先握手", w.sent()[0]["type"] == "ready")
    w.btn("两个力抵消")
    w.btn("装好推杆")
    w.shot("piston", first=True)
    w.btn("让两车互推")
    w.wait(1100)
    before = w.sent("state")[-1]["payload"]
    w.check("同质量、同一秒向相反方向运动", (before["time"], before["speed_a"], before["speed_b"]) ==
            (1, -2, 2), before)
    mass = w.doc.locator("#rightMass")
    if w.touch:
        width = mass.bounding_box()["width"]
        mass.tap(position={"x": int(width - 8), "y": 24})
    else:
        mass.press("ArrowRight")
    w.btn("再推一次")
    w.wait(1100)
    after = w.sent("state")[-1]["payload"]
    w.check("甲二千克向左、乙四千克向右；力相等，加速度不同",
            tuple(after[k] for k in ("mass_a", "mass_b", "force_a", "force_b",
                                     "acceleration_a", "acceleration_b", "speed_a", "speed_b", "time")) ==
            (2, 4, -4, 4, -2, 1, -2, 1, 1), after)
    arrows = w.ev("[...document.querySelectorAll('.force-arrow')].map(a => [a.closest('[data-car]').dataset.car, Number(a.dataset.length)])")
    w.check("两支箭头各在受力的车上，方向相反并等长",
            arrows[0][0] == "甲" and arrows[1][0] == "乙" and arrows[0][1] < 0 and arrows[0][1] == -arrows[1][1], arrows)
    w.btn("去贴力签")
    w.shot("labels", first=True)
    left = w.doc.get_by_role("button", name="贴到甲车")
    right = w.doc.get_by_role("button", name="贴到乙车")
    left.click()
    w.check("贴到错误对象需再试", "哪辆车挨了推" in w.said())
    if w.touch:
        right.tap()
        left.tap()
    else:
        right.press("Enter")
        left.press("Enter")
    w.btn("收好我的互推印章")
    w.check("个人星卡保留实际选择", "甲 2 千克，乙 4 千克" in w.readout(), w.readout())
    w.shot("my-stamps")
    verbs = [m["payload"]["verb"] for m in w.sent("event")]
    w.check("测量和贴签各观察一次", verbs == ["predicted", "observed", "observed"] and
            len(w.sent("complete")) == 1, verbs)
    w.check("手机不横向溢出", w.ev("document.documentElement.scrollWidth <= innerWidth"))


if __name__ == "__main__":
    walklib.main(play)
