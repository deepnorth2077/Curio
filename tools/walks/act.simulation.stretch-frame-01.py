"""拉伸相框。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from math import isclose
import re

from constellation import RIGHT, LEFT, UP, DOWN, run


def size(s, width, height):
    state = s.state()
    for target, old, forward, back in ((width, state["w"], RIGHT, LEFT), (height, state["h"], UP, DOWN)):
        s.keys(forward if target >= old else back, abs(target - old))
    s.expect(w=width, h=height, ok=(3 * width == 4 * height))


def first(s):
    size(s, 10, 8)
    s.expect(ratio="5:4")
    size(s, 12, 9)
    size(s, 16, 12)


def second(s):
    for dimensions in ((4, 3), (8, 6), (12, 9), (16, 12), (17, 12)):
        size(s, *dimensions)


def map_to_moon(s):
    s.keys("]")
    s.numbers(map_cm=4, real_km=8)
    s.keys("[")
    s.numbers(real_km=4)
    s.keys(RIGHT)
    s.numbers(map_cm=3, real_km=3)


    s.button("摆月球")
    s.expect(phase="estimate", guess_cm=None)
    s.w.check("放月球前没有标出平均距离", not s.stage.locator('[data-marker="actual"]').count()
              and "actual_cm" not in s.state())
    visible = s.w.doc.locator("body").inner_text()
    s.w.check("先估距的画面没有距离答案", not re.search(r"1[.]2(?:1)?\s*米|120(?:[.]\d+)?\s*厘米", visible), visible)
    reveal = s.buttons.filter(has_text="展开尺子")
    s.w.check("先放月球才可比较", reveal.count() == 1 and reveal.is_disabled())


def third(s):
    map_to_moon(s)
    if s.w.touch:
        s.drag((505, 116), (400, 248))
        s.numbers(guess_cm=80)
    else:
        s.keys(RIGHT, 5)
        s.numbers(guess_cm=20)
    s.expect(phase="estimate")
    s.w.check("摆好后仍可修改估距", not s.stage.locator('[data-marker="actual"]').count())
    s.w.shot("3-my-moon")
    return "展开尺子"


def compare(s, guess):
    # 以屏幕上地球圆的实际直径校准尺，独立核算两个球心的距离。
    s.expect(phase="compare", guess_cm=guess)
    actual = 384400 * 4 / 12742
    s.numbers(actual_cm=actual)
    circles = s.stage.locator("circle[data-marker]").evaluate_all("""els => els.map(el => {
        const r=el.getBoundingClientRect();
        return {name: el.dataset.marker, x:r.x + r.width/2, y:r.y + r.height/2, width:r.width};
    })""")
    earths = [c for c in circles if c["name"] == "earth"]
    s.w.check("两把尺的地球原点、直径一样", len(earths) == 2
              and abs(earths[0]["x"]-earths[1]["x"]) < 0.1
              and abs(earths[0]["width"]-earths[1]["width"]) < 0.1, circles)
    for name, distance in (("guess", guess), ("actual", actual)):
        moon = next(c for c in circles if c["name"] == name)
        earth = min(earths, key=lambda c: abs(moon["y"] - c["y"]))
        on_ruler = (moon["x"] - earth["x"]) * 4 / earth["width"]
        s.w.check(f"{name} 的月球按同一把尺放置、按比例缩小",
                  abs(earth["y"] - moon["y"]) < 0.1 and isclose(on_ruler, distance, abs_tol=0.15)
                  and isclose(moon["width"]/earth["width"], 3474/12742, abs_tol=0.003), circles)
    s.w.shot("3-compare")


def replay(s):
    initial_guess = 80 if s.w.touch else 20
    s.w.check("星卡记住这次摆的位置", str(initial_guess) + " 厘米" in s.stage.text_content())
    s.button(re.compile(r"第\s*3\s*站"))
    map_to_moon(s)
    s.keys(RIGHT, 9)
    s.numbers(guess_cm=36)
    s.button("展开尺子")
    compare(s, 36)
    s.button("回星卡")
    s.w.check("重玩星卡记住新的估距", "36 厘米" in s.stage.text_content())


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 1, 3), on_card=replay)
