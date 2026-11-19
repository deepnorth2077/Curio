"""同一坡底和同一比较线，核对三栏能量及最后的手作账本。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib


def play(w):
    w.open(hosted=True)
    w.btn("去了滑块")
    w.btn("打开能量格")

    def balance(label, expected):
        state = w.sent("state")[-1]["payload"]
        values = tuple(state[key] for key in ("potential", "kinetic", "thermal"))
        w.check(label, values == expected and sum(values) == 12, values)

    balance("坡顶十二焦耳", (12, 0, 0))
    w.btn("松开滑块")
    balance("半坡势能换成动能", (8, 4, 0))
    wheel = w.doc.get_by_role("slider", name="停格手轮")
    wheel.press("ArrowRight")
    balance("手轮移到靠下的刻线", (4, 8, 0))
    wheel.press("ArrowLeft")
    w.btn("留这格作书签")
    w.btn("滑到下一道刻线")
    w.btn("滑到下一道刻线")
    balance("坡底滑块的动能", (0, 12, 0))
    w.btn("试试水平轨")
    w.btn("滑过光滑段")
    balance("光滑比较线", (0, 12, 0))
    w.btn("铺甲号毛毡")
    w.btn("松手，滑到比较线")
    balance("同一位置，多出来的内能", (0, 8, 4))
    w.shot("2-crossing")
    w.btn("再滑一段")
    w.btn("再滑一段")
    balance("完全停稳", (0, 0, 12))
    w.btn("收好能量账")
    w.check("手选的半坡书签", "重力势能 8 J、动能 4 J" in w.said(), w.said())
    w.check("两站观察、一次领账", [m["payload"]["verb"] for m in w.sent("event")] ==
            ["predicted", "observed", "observed"] and len(w.sent("complete")) == 1)
    w.shot("card")


if __name__ == "__main__":
    walklib.main(play)
