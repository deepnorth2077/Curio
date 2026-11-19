"""从孩子能操作的控件走过三站。每颗星的手算用例写在自己的走查里。"""
import re
import sys
from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import walklib


class Station:
    def __init__(self, walker):
        self.w = walker
        self.stage = walker.doc.locator("#stage")
        self.buttons = walker.doc.locator("#actions button, #workbench button")

    def button(self, text):
        # 用可见名称定位。浅、深两种触摸屏都实际点击 DOM 中的控件。
        button = self.buttons.filter(has_text=text).first
        self.w.step(f"点「{text}」")
        self.w.wait(440)
        if self.w.touch:
            button.tap(timeout=3500)
        else:
            button.click(timeout=3500)
        self.w.wait(100)

    def drag(self, start, end):
        """真实触摸坐标以模块绘图单位给出，支持按比例缩放的屏幕。"""
        self.stage.scroll_into_view_if_needed()
        start, end = self.w.pt(*start), self.w.pt(*end)
        # getScreenCTM() 使用 iframe 视口；harness 的 iframe 正好铺满页面。
        x, y = start
        dx, dy = end[0] - x, end[1] - y
        points = [(x + dx * i / 8, y + dy * i / 8) for i in range(9)]
        if self.w.touch:
            self.w.touch_drag(points)
        else:
            self.w.mouse_drag(points)
        self.w.wait(120)

    def keys(self, key, count=1):
        self.w.step(f"在实物上按 {key} × {count}")
        self.stage.focus()
        for _ in range(count):
            self.w.page.keyboard.press(key)
        self.w.wait(80)

    def held_until(self, field, target, timeout=14):
        self.w.step(f"按住空格，直到 {field} = {target}")
        self.stage.focus()
        keyboard = self.w.page.keyboard
        keyboard.down("Space")
        try:
            start = monotonic()
            while self.state().get(field) != target and monotonic() - start < timeout:
                self.w.wait(80)
        finally:
            keyboard.up("Space")
        self.expect(**{field: target})

    def state(self):
        states = self.w.sent("state")
        return states[-1]["payload"] if states else {}

    def expect(self, **fields):
        got = self.state()
        self.w.check(f"实物读数 {fields}", all(got.get(k) == v for k, v in fields.items()), got)

    def numbers(self, **fields):
        """有些读数按约定保留显示精度（例如 1.0 和 0.98）。"""
        got = self.state()
        for key, value in fields.items():
            try:
                equal = abs(float(got[key]) - value) < 1e-8
            except (ValueError, TypeError, KeyError):
                equal = False
            self.w.check(f"{key} = {value}", equal, got)


def run(stations, correct_positions):
    def play(w):
        if w.touch:
            # 触摸坐标以独立活动的视口为准。由本地路由提供同一文件，
            # 兼容禁止 file:// 的浏览器；模块仍然完全离线。
            url = walklib.HOST + "standalone/index.html"
            w.page.route(url, lambda route: route.fulfill(path=str(w.path)))
            w.page.goto(url)
            w.wait(400)
        else:
            w.open(hosted=True)
        s = Station(w)
        w.check("ready 先于活动消息", [m["type"] for m in w.sent()][:1] == ["ready"], w.sent())
        for number, exercise in enumerate(stations, 1):
            choices = w.doc.locator("#actions .choice")
            if choices.count() == 0:
                s.button(re.compile("然后呢|猜一猜|先猜"))
            w.check("有三个猜测选项", choices.count() == 3, w.buttons())
            w.check("提问画面没有操作圆钮", w.grips() == 0, w.grips())
            w.wait(440)
            pick = {"tablet": 0, "phone": 1, "desk": 2}[w.name]
            choices.nth(pick).click(timeout=3000)
            s.button(re.compile("动手"))
            w.check("画面适合屏宽", w.ev("document.documentElement.scrollWidth <= innerWidth"))
            prediction = w.sent("event")[-1]["payload"]
            correct = pick + 1 == correct_positions[number - 1]
            w.check("猜测记录对应的答案和误区", prediction["verb"] == "predicted"
                    and prediction["result"]["correct"] == correct
                    and bool(prediction["result"].get("misconception")) != correct, prediction)
            reveal = s.buttons.filter(has_text=re.compile("看.*发现|看结果"))
            w.check("操作之前还不能揭晓", not reveal.count() or reveal.first.is_disabled())
            w.shot(f"{number}-start", first=True)
            exercise(s)
            w.shot(f"{number}-done")
            s.button(re.compile("看.*发现|看结果"))
            s.button(re.compile(r"去第\s*\d+\s*站|看我的星卡"))
        events = [m["payload"] for m in w.sent("event")]
        expected = [(verb, n) for n in (1, 2, 3) for verb in ("predicted", "observed")]
        w.check("每站的预测与观察各记一次",
                [(e["verb"], e["result"]["station"]) for e in events] == expected, events)
        w.check("收卡时活动完成一次", len(w.sent("complete")) == 1, w.sent("complete"))
        w.shot("card")
        s.button(re.compile(r"第\s*1\s*站"))
        w.check("重玩直接回到第一站的实物", not w.doc.locator("#actions .choice").count()
                and s.state().get("station") == 1, s.state())
        w.check("重进第一站没有新预测与重复完成", len(w.sent("event")) == len(events)
                and len(w.sent("complete")) == 1)
    walklib.main(play)


LEFT, RIGHT, UP, DOWN = "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"
