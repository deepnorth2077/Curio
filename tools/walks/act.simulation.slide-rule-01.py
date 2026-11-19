"""滑尺。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import LEFT, RIGHT, run


def first(s):
    s.keys(LEFT)
    s.numbers(value=15)
    s.keys(LEFT)
    s.numbers(value=150)
    s.keys(RIGHT, 3)
    s.numbers(value=0.15)


def second(s):
    for unit, value in (("dm", 13.5), ("cm", 135), ("mm", 1350)):
        s.keys(RIGHT)
        s.expect(unit=unit)
        s.numbers(number=value)


def third(s):
    for power in range(1, 8):
        s.button("乘 10")
        s.numbers(sheets=10**power, height_mm=10**(power - 1))


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 3, 1))
