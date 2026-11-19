"""拉伸相框。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
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


def third(s):
    s.keys("]")
    s.numbers(map_cm=4, real_km=8)
    s.keys("[")
    s.numbers(real_km=4)
    s.keys(RIGHT)
    s.numbers(map_cm=3, real_km=3)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 1, 3))
