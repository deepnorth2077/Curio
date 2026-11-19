"""再切刀。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, run


def first(s):
    s.keys(RIGHT, 3)
    s.expect(base="1/2", k=4, name="4/8")
    s.button("换成三分之二")
    s.keys(RIGHT, 2)
    s.expect(base="2/3", k=3, name="6/9")


def second(s):
    s.button("每 2 份并一份")
    s.expect(ok=True, to="3/4")
    s.button("换成十八分之十二")
    s.button("每 6 份并一份")
    s.expect(ok=True, to="2/3")


def third(s):
    for denominator in range(3, 13):
        s.keys(RIGHT)
        s.expect(den=denominator, aligned=(denominator % 3 == 0))


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 1, 3))
