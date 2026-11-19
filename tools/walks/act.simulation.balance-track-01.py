"""双绳拉车：平台消息记录的是同一辆车的真实实验。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import walklib


def play(w):
    w.open(hosted=True)
    w.check("先向平台报到", w.sent()[0]["type"] == "ready")
    w.btn("会加速")
    w.btn("上轨道试试")
    w.shot("1-pull", first=True)
    left = w.doc.locator("#left")
    if w.touch:
        left.scroll_into_view_if_needed()
        b = left.bounding_box()
        w.touch_drag([(b["x"] + b["width"] / 3, b["y"] + b["height"] / 2),
                      (b["x"] + 2*b["width"] / 3, b["y"] + b["height"] / 2)])
    else:
        left.press("ArrowRight")
    w.check("左力计从 2 牛调到 4 牛", left.input_value() == "4", left.input_value())

    def run():
        before = len(w.sent("state"))
        w.btn("松开车闸")
        w.page.wait_for_function("before => {const states=window.__got.filter(m=>m.type==='state'); "
                                 "return states.length>before && states.at(-1).payload.seconds===2;}", arg=before)
        return w.sent("state")[-1]["payload"]

    still = run()
    w.check("4 牛对 4 牛，静车仍停在原点",
            (still["netForce"], still["velocity"], still["position"]) == (0, 0, 0), still)
    w.check("还需观察运动的车", "去第2站" not in w.buttons())
    w.doc.locator("#launch").press("End")
    coast = run()
    w.check("同样的两根绳，原已向右的车每秒仍走两米",
            (coast["netForce"], coast["velocity"], coast["position"]) == (0, 2, 4), coast)
    w.btn("去第 2 站")
    w.btn("先慢下来")
    w.btn("上轨道试试")
    w.shot("2-turn", first=True)
    w.doc.locator("#right").press("End")
    slow = run()
    w.check("右 6 左 4，左行车先减速", (slow["netForce"], slow["velocity"], slow["position"]) == (2, -1, -3), slow)
    w.doc.locator("#left").press("ArrowLeft")
    stronger = run()
    w.check("改成右 6 左 2，合力向右 4 牛", stronger["netForce"] == 4, stronger)
    w.btn("收好星卡")
    completed = w.sent("complete")
    events = w.sent("event")
    w.check("两个预测两个观察", [e["payload"]["verb"] for e in events] == ["predicted","observed"]*2, events)
    w.check("星卡保存三组自己选的记录", len(completed) == 1 and completed[0]["payload"]["records"]["pull"]["left"] == 2, completed)
    w.check("真实受力写在星卡上", "右绳 6 牛" in w.doc.locator("#receipt").inner_text())
    w.check("手机没有横向滚动", w.ev("document.documentElement.scrollWidth <= innerWidth"))
    w.shot("3-card")


if __name__ == "__main__":
    walklib.main(play, timeout=75)
