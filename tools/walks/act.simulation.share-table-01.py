"""分饼台。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, run


def first(s):
    s.keys("Enter")
    s.keys("Space", 3)
    s.expect(pies=3, people=4, each="3/4")
    s.button("分 2 张饼")
    s.keys("Enter")
    s.keys("Space", 2)
    s.expect(pies=2, people=3, each="2/3")


def second(s):
    s.keys("Space", 5)
    s.expect(improper="5/4")
    s.button("换 7 张饼")
    s.keys("Space", 7)
    s.expect(improper="7/2")


def third(s):
    s.keys(RIGHT, 4)
    s.expect(num=4, den=4)
    s.keys(RIGHT, 7)
    s.expect(num=11, den=4)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 1, 3))
