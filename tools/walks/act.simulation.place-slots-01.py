"""位值格。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, run


def first(s):
    for digit in "1255":
        s.keys(digit)
    s.expect(a="0.125", b="0.5", larger="b")
    s.keys("6")
    s.keys("Tab")
    s.keys("4")
    s.button("比一比")


def second(s):
    s.button("末尾添 0")
    s.expect(value="0.30")
    s.numbers(level=0.3)
    s.button("小数点后面添 0")
    s.expect(value="0.03")
    s.numbers(level=0.03)


def third(s):
    s.button("倒进去")
    s.expect(aligned=False)
    for total in (0.75, 1.55, 1):
        if total != 0.75:
            s.button("换一道")
        if total != 1:
            s.keys(RIGHT)
        s.button("倒进去")
        s.numbers(sum=total)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 3, 1))
