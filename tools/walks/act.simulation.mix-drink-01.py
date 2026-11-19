"""调饮料台。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, UP, run


def first(s):
    s.keys(RIGHT, 3)
    s.keys(UP, 4)
    s.expect(powder=3, water=4, value="3/4", same_as_a=False)
    s.keys(RIGHT)
    s.keys(UP, 2)
    s.expect(powder=4, water=6, same_as_a=True)


def second(s):
    for jugs in (2, 3, 6):
        s.button(f"{jugs} 只小壶")
        s.expect(jugs=jugs, each=f"{12//jugs}:{18//jugs}")


def third(s):
    s.button("各加 2")
    s.expect(powder=4, water=5, same=False)
    s.button("各乘 2")
    s.expect(powder=4, water=6, same=True)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(1, 2, 3))
