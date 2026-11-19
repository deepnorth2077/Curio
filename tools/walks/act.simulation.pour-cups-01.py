"""倒水。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, run


def first(s):
    for cup, cups in (("2", 3), ("1", 6), ("1/2", 12)):
        if cups != 3:
            s.keys(RIGHT)
        s.held_until("cups", cups)
        s.expect(cup=cup)


def second(s):
    for parts, cups in ((24, 8), (18, 9)):
        if cups != 8:
            s.button("换一种杯子")
        s.keys("Enter")
        s.held_until("cups", cups)
        s.numbers(parts=parts)


def third(s):
    s.keys("Space", 6)
    s.expect(scene="ribbon", count=6)
    s.button("换成半张饼")
    s.keys("Space", 3)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 3, 1))
