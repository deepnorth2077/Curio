"""百格电量条。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import LEFT, RIGHT, UP, run


def first(s):
    s.keys(RIGHT, 4)
    s.keys(UP, 3)
    s.numbers(cells_a=100, lit_a=85, cells_b=100, lit_b=84)


def second(s):
    if s.w.touch:
        # 电量条的底线是 y=312，每格占 2.3 个绘图单位。
        s.drag((307, 312 - 2.3 * 25), (307, 312 - 2.3 * 50))
    else:
        s.keys("Shift+" + RIGHT, 5)
    s.expect(frac="1/2")
    s.numbers(percent=50)
    s.keys("Shift+" + LEFT, 5)
    s.expect(frac="1/4")
    s.keys("Shift+" + LEFT)
    s.expect(frac="1/5")


def third(s):
    s.keys(UP, 5)
    s.expect(base="last")
    s.numbers(percent=150)
    s.keys("Enter")
    s.expect(base="this")
    s.numbers(percent=67)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 3, 1))
