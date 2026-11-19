"""量杯。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, run


def first(s):
    s.keys("Enter", 2)
    s.keys("Space")
    s.expect(level="5/6", flag=True)


def second(s):
    for marks in (3, 4, 5, 6, 8, 10, 12):
        s.keys(RIGHT)
        s.expect(marks=marks, on_line=(marks % 6 == 0))


def third(s):
    s.held_until("result", "5/12")
    s.button("换加法")
    s.keys("Enter", 2)
    s.expect(result="7/6")


if __name__ == "__main__":
    run((first, second, third), correct_positions=(3, 1, 2))
