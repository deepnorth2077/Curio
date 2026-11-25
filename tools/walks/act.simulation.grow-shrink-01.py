"""伸缩柱。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, run


def first(s):
    s.button("涨 50%")
    s.button("降 50%")
    s.numbers(value=75)
    s.button("重来")
    s.button("降 50%")
    s.button("涨 50%")
    s.numbers(value=75)


def second(s):
    s.keys(RIGHT, 3)
    s.numbers(start=150, value=100)
    s.button("换成 50 元")
    s.keys(RIGHT)
    s.numbers(start=50, value=100)


def third(s):
    s.held_until("year", 50, timeout=24)
    s.numbers(compound=11739, simple=600)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 1, 3))
