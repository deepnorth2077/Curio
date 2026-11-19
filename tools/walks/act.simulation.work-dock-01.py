"""纸带机：用真实的把手印出两张工作票，再从星卡读回沿途盖的印。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib


def play(w):
    w.open(hosted=True)
    w.check("先告知宿主可操作", w.sent()[0]["type"] == "ready")
    w.btn("用着劲")
    w.btn("到纸带机")
    w.btn("托稳箱子")
    w.check("托着不移动只记零功", w.sent("state")[-1]["payload"]["work"] == 0)
    w.btn("试试直提")
    slider = w.doc.get_by_role("slider", name="拉货把手")
    slider.press("ArrowRight")
    w.check("直提四分之一米产生三焦耳", w.sent("state")[-1]["payload"]["work"] == 3)
    w.btn("盖一枚中途印")
    slider.press("End")
    w.shot("1-straight")
    w.check("直提票是十二牛一米", w.sent("state")[-1]["payload"] ==
            dict(station=1, force=12, distance=1, work=12))
    w.btn("换长坡")
    if w.touch:
        bounds = slider.bounding_box()
        y = bounds["y"] + bounds["height"] / 2
        w.touch_drag([(bounds["x"] + 8, y), (bounds["x"] + bounds["width"] - 4, y)])
    else:
        slider.press("End")
    w.check("坡面票是三牛四米", w.sent("state")[-1]["payload"] ==
            dict(station=2, force=3, distance=4, work=12))
    w.shot("2-ramp")
    w.btn("收好工作票")
    text = w.doc.locator("#dyn").text_content()
    w.check("工票保留亲手盖的三焦耳印", "0.25 m 时，3 J" in text, text)
    w.check("两站都有观察且领票一次", len(w.sent("complete")) == 1 and
            [m["payload"]["result"]["station"] for m in w.sent("event") if m["payload"]["verb"] == "observed"] == [1, 2])
    w.shot("card")


if __name__ == "__main__":
    walklib.main(play)
