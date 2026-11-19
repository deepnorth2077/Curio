"""验收实物操作、同一次测量的读数，以及亲手做出的星卡。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib


def play(w):
    w.open(hosted=True)
    stage = w.doc.locator("#stage")

    def press(key, times=1):
        stage.focus()
        for _ in range(times):
            stage.press(key)
        w.wait(80)

    def drag(dx, dy):
        grip = w.doc.locator("#dyn .gfill")
        x, y = (float(grip.get_attribute(attr)) for attr in ("cx", "cy"))
        points = [w.pt(x + dx * i / 8, y + dy * i / 8) for i in range(9)]
        (w.touch_drag if w.touch else w.mouse_drag)(points)
        w.wait(100)

    def expect(**expected):
        actual = w.sent("state")[-1]["payload"]
        w.check(str(expected), all(actual.get(k) == v for k, v in expected.items()), actual)

    w.btn("重箱总会压下去")
    w.btn("松开横杆")
    w.shot("lever", first=True)
    w.btn("核对平衡")
    w.check("动手前不能过站", not w.sent("complete") and "低" in w.said())
    drag(-64, 0)
    expect(station=1, leftArm=3, rightArm=1, leftMoment=6, rightMoment=6)
    press("ArrowRight")
    expect(leftArm=2, leftMoment=4, rightMoment=6)
    press("ArrowLeft")
    w.btn("核对平衡")
    w.btn("换个支点")
    w.shot("pivot", first=True)
    press("ArrowLeft", 2)
    w.btn("锁住支点")
    press("ArrowLeft", 8)
    expect(station=2, leftArm=9, rightArm=3, leftMoment=18, rightMoment=18)
    w.btn("核对平衡")
    w.btn("收下平衡记录")
    w.check("星卡保留自选的新支点", "9 格" in w.doc.locator("#dyn").inner_text())

    expected_stations = list(range(1, 2 + 1))
    events = [m["payload"] for m in w.sent("event")]
    observed = [e["result"]["station"] for e in events if e["verb"] == "observed"]
    w.check("每站各记录一次观察", observed == expected_stations, observed)
    w.check("预测仅记一次", sum(e["verb"] == "predicted" for e in events) == 1)
    w.check("星卡收好仅完成一次", len(w.sent("complete")) == 1)
    w.shot("card")


if __name__ == "__main__":
    walklib.main(play)
