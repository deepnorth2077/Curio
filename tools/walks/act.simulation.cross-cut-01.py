"""横切再竖切。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
from constellation import RIGHT, UP, LEFT, DOWN, run


def choose(s, cols, rows, taken_cols, taken_rows):
    state = s.state()
    for target, old, forward, back in ((cols, state["b"], RIGHT, LEFT), (rows, state["d"], UP, DOWN)):
        s.keys(forward if target >= old else back, abs(target - old))
    for number in range(1, taken_cols + 1):
        s.keys(str(number))
    for number in range(1, taken_rows + 1):
        s.keys(f"Shift+Digit{number}")
    s.numbers(pieces=cols * rows, taken=taken_cols * taken_rows)


def first(s):
    choose(s, 2, 3, 1, 1)
    s.button("换一块")
    choose(s, 3, 4, 2, 3)


def second(s):
    s.keys("Space", 6)
    s.numbers(units=6)
    s.button("再拼一次")
    s.keys("Space", 8)
    s.numbers(units=8)


def third(s):
    choose(s, 3, 4, 2, 3)
    choose(s, 4, 3, 3, 2)
    choose(s, 5, 6, 3, 5)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 3, 1))
