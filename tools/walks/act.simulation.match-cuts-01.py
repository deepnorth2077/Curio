"""对刀口。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, UP, run


def first(s):
    s.keys("Enter")
    s.keys("Space")
    s.expect(overlaid=True, gaps_compared=True)


def second(s):
    s.keys(RIGHT, 3)
    s.keys(UP, 2)
    s.expect(parts_a=12, parts_b=12, aligned=True)
    s.button("换第二对")
    s.keys(RIGHT, 4)
    s.keys(UP, 2)
    s.expect(parts_a=15, parts_b=15, aligned=True)


def third(s):
    for target in (3/8, 2/5, 4/7, 5/6):
        s.keys("Enter")
        s.numbers(target=target)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(3, 1, 2))
