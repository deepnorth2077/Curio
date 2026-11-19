"""同一秒的推车对照。从实际滑尺改变负载与推力，再读回孩子的双车纸带。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import walklib


def play(w):
    w.open(hosted=True)
    w.check("先握手", w.sent()[0]["type"] == "ready")
    w.btn("能，跑得快")
    w.btn("去试车")
    w.shot("compare", first=True)
    mass = w.doc.locator("#mass")
    force = w.doc.locator("#force")

    def run(label, mass_kg, push_n, net_n, a):
        w.btn(label)
        w.wait(1100)
        state = w.sent("state")[-1]["payload"]
        w.check("净力、加速度和一秒的末速度", (state["mass"], state["push"], state["resistance"],
                state["net"], state["acceleration"], state["time"], state["speed"]) ==
                (mass_kg, push_n, 2, net_n, a, 1, a), state)

    run("同时推", 2, 6, 4, 2)
    if w.touch:
        width = mass.bounding_box()["width"]
        mass.tap(position={"x": int(width - 8), "y": 24})
    else:
        mass.press("ArrowRight")
    run("再试", 4, 6, 4, 1)
    mass.press("Home")
    force.press("End")
    run("再试", 2, 10, 8, 4)
    w.btn("配一对纸带")
    w.shot("matching", first=True)
    force.press("End")
    run("同时推", 4, 10, 8, 2)
    w.btn("收好我的纸带")
    w.check("星卡属于刚刚配出的两辆车", "4 千克 · 合力向右 8 牛顿" in w.doc.locator("#dyn").text_content())
    w.shot("my-tapes")
    w.btn("第 2 站")
    w.doc.locator("#referenceForce").press("Home")
    run("同时推", 4, 6, 4, 1)
    w.btn("收好我的纸带")
    w.check("另一种配法做成自己的星卡", "4 千克 · 合力向右 4 牛顿" in w.doc.locator("#dyn").text_content())
    verbs = [m["payload"]["verb"] for m in w.sent("event")]
    w.check("猜测、两次观察和一个成就物", verbs == ["predicted", "observed", "observed"] and
            len(w.sent("complete")) == 1, verbs)
    w.check("手机不横向溢出", w.ev("document.documentElement.scrollWidth <= innerWidth"))


if __name__ == "__main__":
    walklib.main(play)
