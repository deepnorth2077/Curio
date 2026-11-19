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

    w.btn("会更省力")
    w.btn("试推短坡")
    w.shot("short", first=True)
    w.btn("把货交给站台")
    w.check("货箱未到不能领取记录", "还没到" in w.said())
    drag(190, -110)
    expect(station=1, length=2, height=1, distance=2, force=6, work=12)
    w.btn("把货交给站台")
    w.btn("抽出长坡板")
    w.shot("long", first=True)
    w.btn("固定坡脚")
    w.check("实际选到长板才能出发", "再把坡脚" in w.said())
    press("ArrowLeft", 2)
    w.btn("固定坡脚")
    press("ArrowRight", 8)
    expect(station=2, length=4, height=1, distance=4, force=3, work=12)
    w.btn("把货交给站台")
    w.btn("我来选块板")
    w.shot("choose", first=True)
    w.btn("固定坡脚")
    press("ArrowRight", 8)
    expect(station=3, length=3, height=1, distance=3, force=4, work=12)
    w.btn("把货交给站台")
    w.btn("收下坡板记录")
    card = w.doc.locator("#dyn").inner_text()
    w.check("星卡保留自己选的坡板", "我选的坡" in card and "3 m · 4 N" in card, card)

    expected_stations = list(range(1, 3 + 1))
    events = [m["payload"] for m in w.sent("event")]
    observed = [e["result"]["station"] for e in events if e["verb"] == "observed"]
    w.check("每站各记录一次观察", observed == expected_stations, observed)
    w.check("预测仅记一次", sum(e["verb"] == "predicted" for e in events) == 1)
    w.check("星卡收好仅完成一次", len(w.sent("complete")) == 1)
    w.shot("card")


if __name__ == "__main__":
    walklib.main(play)
