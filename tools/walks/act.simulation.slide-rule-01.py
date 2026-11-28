"""滑尺。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
import re

from constellation import LEFT, RIGHT, run


def first(s):
    s.w.check(
        "开场未触发正误或星卡音",
        [s.w.ev('Sfx.count("right")'), s.w.ev('Sfx.count("nudge")'), s.w.ev('Sfx.count("lit")')] == [0, 0, 0],
    )
    if not s.w.touch:
        s.w.page.set_viewport_size({"width": 820, "height": 1180})
        s.w.wait(150)
        s.w.page.set_viewport_size({"width": 390, "height": 844})
        s.w.wait(220)
        try:
            r = s.w.ev("document.querySelector('#dyn .gfill')?.getAttribute('r')")
            s.w.check("缩窄视口后圆钮半径立即重算", r is not None and 20 < float(r) < 27, r)
        finally:
            s.w.page.set_viewport_size(s.w.vp)
            s.w.wait(150)
        seq0 = s.w.ev("Sfx.seq()")
        s.drag((520, 126), (510, 126))
        s.w.check("滑条同档内微移不响", s.w.ev("Sfx.seq()") == seq0, s.w.ev("Sfx.seq()") - seq0)
        t0 = s.w.ev('Sfx.count("tick")')
        s.keys(LEFT)
        s.w.check("滑条跨一格只响一次拨动音", s.w.ev('Sfx.count("tick")') == t0 + 1, s.w.ev('Sfx.count("tick")') - t0)
    else:
        s.keys(LEFT)
    s.numbers(value=15)
    s.keys(LEFT)
    s.numbers(value=150)
    s.keys(RIGHT, 3)
    s.numbers(value=0.15)


def second(s):
    s.w.check_rewards(1, 0)
    snap0 = s.w.ev('Sfx.count("snap")')
    disc0 = s.w.ev('Sfx.count("discover")')
    for unit, value in (("dm", 13.5), ("cm", 135), ("mm", 1350)):
        s.keys(RIGHT)
        s.expect(unit=unit)
        s.numbers(number=value)
    s.w.check(
        "切换四个单位响拼合音和发现音",
        s.w.ev('Sfx.count("snap")') == snap0 + 2 and s.w.ev('Sfx.count("discover")') == disc0 + 1,
    )


def third(s):
    s.w.check_rewards(2, 0)
    hop0 = s.w.ev('Sfx.count("hop")')
    disc0 = s.w.ev('Sfx.count("discover")')
    for power in range(1, 8):
        s.button("乘 10")
        s.numbers(sheets=10**power, height_mm=10**(power - 1))
    s.w.check(
        "叠纸 7 次前 6 次上跃、第 7 次响发现音",
        s.w.ev('Sfx.count("hop")') == hop0 + 6 and s.w.ev('Sfx.count("discover")') == disc0 + 1,
    )


def card(s):
    s.w.check_rewards(3, 1)
    s.button(re.compile(r"第\s*2\s*站"))
    s.keys(RIGHT, 3)
    s.button("看看发现")
    s.button("回星卡")
    s.w.check_rewards(3, 1)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 3, 1), on_card=card)
