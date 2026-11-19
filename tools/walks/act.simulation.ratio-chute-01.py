"""分配槽。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, run


def first(s):
    s.keys("Space", 2)
    s.expect(total=10, a=4, b=6)
    s.button("装 20 块")
    s.keys("Space", 4)
    s.expect(total=20, a=8, b=12)


def second(s):
    for i in range(4):
        if i:
            s.keys(RIGHT)
        s.keys("Enter")


def third(s):
    for steps, rounds, result in ((0, 6, [6, 6]), (1, 4, [4, 8]), (4, 2, [2, 4, 6])):
        s.keys(RIGHT, steps)
        s.keys("Space", rounds)
        s.expect(shares=result)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(1, 2, 3))
