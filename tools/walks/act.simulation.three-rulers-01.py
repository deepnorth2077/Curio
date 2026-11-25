"""三把尺子。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import LEFT, RIGHT, run


def first(s):
    for index, key, steps, name in ((10, RIGHT, 10, "1/4"), (8, LEFT, 2, "1/5"), (5, LEFT, 3, "1/8")):
        s.keys(key, steps)
        s.expect(frac=name)
        s.numbers(k=index, dec=index/40)
        percent = s.state()["pct"]
        s.w.check("百分数和分数落在同一点", float(str(percent).rstrip("%")) == index * 2.5, percent)


def second(s):
    s.held_until("done", True)
    s.numbers(digits=2)
    s.keys(RIGHT, 2)
    s.held_until("digits", 10)
    s.expect(done=False)


def third(s):
    s.keys("Enter", 11)
    s.numbers(placed=11, pins=5)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 3, 1))
