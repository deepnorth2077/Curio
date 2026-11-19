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

    def wheel_turn():
        return w.doc.locator("#wheelSpokes").evaluate(
            "(g) => g.transform.baseVal.getItem(0).angle"
        )

    w.btn("要看绳子怎样托住箱子")
    w.btn("拉起第一箱")
    w.shot("fixed", first=True)
    w.btn("对齐刻线")
    w.check("没拉绳不能交货", "还要" in w.said())
    drag(0, 67)
    expect(station=1, strands=1, rope=1, height=1, force=8, work=8)
    w.check("定滑轮右边沿着手拉方向向下转", wheel_turn() > 0)
    w.btn("对齐刻线")
    w.btn("把轮子挂到箱上")
    w.shot("moving", first=True)
    press("ArrowUp", 4)
    expect(station=2, strands=2, rope=1, height=.5, force=4, work=4)
    w.check("动滑轮左边绕固定绳段滚动", wheel_turn() < 0)
    w.btn("补收一段绳")
    press("ArrowUp", 2)
    w.btn("在绳上留印")
    press("ArrowUp", 2)
    expect(strands=2, rope=2, height=1, force=4, work=8)
    w.btn("对齐刻线")
    w.btn("收下吊运单")
    card = w.doc.locator("#dyn").text_content()
    w.check("星卡记录自己的绳印", "1.5 m" in card and "0.75 m" in card, card)

    expected_stations = list(range(1, 2 + 1))
    events = [m["payload"] for m in w.sent("event")]
    observed = [e["result"]["station"] for e in events if e["verb"] == "observed"]
    w.check("每站各记录一次观察", observed == expected_stations, observed)
    w.check("预测仅记一次", sum(e["verb"] == "predicted" for e in events) == 1)
    w.check("星卡收好仅完成一次", len(w.sent("complete")) == 1)
    w.shot("card")


if __name__ == "__main__":
    walklib.main(play)
