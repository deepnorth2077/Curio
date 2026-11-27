"""位值格。输入来自孩子用的键盘操作或屏上按钮，期望值由任务中的数学关系算得。"""
import re

from constellation import DOWN, LEFT, RIGHT, UP, run


def first(s):
    s.w.check(
        "开场未触发正误或星卡音",
        [s.w.ev('Sfx.count("right")'), s.w.ev('Sfx.count("nudge")'), s.w.ev('Sfx.count("lit")')] == [0, 0, 0],
    )
    snap0 = s.w.ev('Sfx.count("snap")')
    disc0 = s.w.ev('Sfx.count("discover")')
    for digit in "1255":
        s.keys(digit)
    s.expect(a="0.125", b="0.5", larger="b")
    s.w.check(
        "摆完目标小数响拼合音和发现音",
        s.w.ev('Sfx.count("snap")') - snap0 >= 3 and s.w.ev('Sfx.count("discover")') == disc0 + 1,
    )
    s.keys("6")
    s.keys("Tab")
    s.keys("4")
    s.button("比一比")


def second(s):
    s.w.check_rewards(1, 0)
    s.button("末尾添 0")
    s.expect(value="0.30")
    s.numbers(level=0.3)
    s.button("小数点后面添 0")
    s.expect(value="0.03")
    s.numbers(level=0.03)


def row(s, name):
    # 两行各自的十进位刻度。用数字间距把手指移动量换成一格。
    return s.stage.locator(f'.pour-row[data-row="{name}"]').evaluate("""g => {
        const svg = g.ownerSVGElement, grip = g.querySelector('.gfill');
        const point = svg.createSVGPoint();
        point.x = grip.cx.baseVal.value;
        point.y = grip.cy.baseVal.value;
        const matrix = svg.getScreenCTM().inverse().multiply(g.getScreenCTM());
        const center = point.matrixTransform(matrix);
        const digits = g.querySelectorAll('.digit-face');
        const step = digits[1].x.baseVal[0].value - digits[0].x.baseVal[0].value;
        return {x: center.x, y: center.y, step};
    }""")


def first_pour(s):
    s.expect(aligned=False, sum=None)
    rule = re.compile(r"对齐|对准|面对面|(?:下排|下面一行).{0,8}(?:右挪|向右|往右)")
    initial = s.w.doc.locator("body").inner_text()
    s.w.check("首次操作前没有透露对齐方法", not rule.search(initial), initial)
    nudge0 = s.w.ev('Sfx.count("nudge")')
    s.button("倒进去")
    s.w.check("未对齐倒水有提醒音", s.w.ev('Sfx.count("nudge")') == nudge0 + 1, s.w.ev('Sfx.count("nudge")') - nudge0)
    clue = s.w.said()
    s.expect(aligned=False, sum=None)
    s.w.check("错倒后才提示观察两个 5 所在的位",
              all(token in clue for token in ("0.5", "0.25", "5")) and "？" in clue
              and not rule.search(clue), clue)
    s.w.shot("3-clue")
    top = row(s, "top")
    bottom = row(s, "bottom")
    if s.w.touch:
        s.drag((top["x"], top["y"]), (top["x"] - top["step"], top["y"]))
    else:
        s.keys(UP)
        seq0 = s.w.ev("Sfx.seq()")
        s.drag((top["x"], top["y"]), (top["x"] - 10, top["y"]))
        s.w.check("同格内微移数条不响", s.w.ev("Sfx.seq()") == seq0, s.w.ev("Sfx.seq()") - seq0)
        t0 = s.w.ev('Sfx.count("tick")')
        s.keys(LEFT)
        s.w.check("跨一格对齐只响一次拨动音", s.w.ev('Sfx.count("tick")') == t0 + 1, s.w.ev('Sfx.count("tick")') - t0)
    s.expect(aligned=True, sum=None)
    s.w.check("只挪上排也能摆好", abs(row(s, "top")["x"] - top["x"] + top["step"]) < 1
              and abs(row(s, "bottom")["x"] - bottom["x"]) < 1)
    d_pour = s.w.ev('Sfx.count("discover")')
    s.button("倒进去")
    s.w.check("对齐倒成响一次发现音", s.w.ev('Sfx.count("discover")') == d_pour + 1, s.w.ev('Sfx.count("discover")') - d_pour)
    s.numbers(sum=0.75)
    s.w.check("倒成功后才说出规律", "对齐" in s.w.said(), s.w.said())


def next_pours(s):
    s.button("换一道")
    s.keys(DOWN)
    s.keys(RIGHT)
    s.button("倒进去")
    s.numbers(sum=1.55)
    s.button("换一道")
    s.button("倒进去")
    s.numbers(sum=1)


def third(s):
    s.w.check_rewards(2, 0)
    first_pour(s)
    next_pours(s)


def replay(s):
    s.w.check_rewards(3, 1)
    s.button(re.compile(r"第\s*3\s*站"))
    s.expect(aligned=False, sum=None)
    # 自己先发现方法的孩子可以直接动下排，不必故意错倒。
    s.keys(RIGHT)
    s.button("倒进去")
    s.numbers(sum=0.75)
    next_pours(s)
    s.button("看看发现")
    s.button("回星卡")
    s.w.check_rewards(3, 1)


if __name__ == "__main__":
    run((first, second, third), correct_positions=(2, 3, 1), on_card=replay)
