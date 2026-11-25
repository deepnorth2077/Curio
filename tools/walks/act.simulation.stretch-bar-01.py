"""伸缩条。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import LEFT, RIGHT, UP, run


def first(s):
    s.keys(RIGHT)
    s.keys(LEFT)
    s.numbers(m=1, length=6)
    s.keys(LEFT, 5)
    s.numbers(m=0.5, length=3)


def second(s):
    if s.w.touch:
        # 格子纸左上角 (270, 66)，每一小格的边长 26。
        s.drag((270 + 2*26, 66 + 2*26), (270 + 5*26, 66 + 5*26))
    else:
        s.keys(RIGHT, 3)
        s.keys(UP, 3)
    s.numbers(w=0.5, h=0.5, cells=25, product=0.25)
    s.keys(LEFT, 2)
    s.keys("ArrowDown")
    s.numbers(w=0.3, h=0.4, cells=12, product=0.12)


def third(s):
    s.keys("Space", 10)
    s.numbers(cuts=10, left_mm=0.98)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(1, 2, 3))
