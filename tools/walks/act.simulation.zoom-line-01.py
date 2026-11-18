"""数线放大镜走查，验收值见 docs/constellations/zero-to-one/stars/04-tenths.md。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib  # noqa: E402


def play(w):
    keyboard = w.page.keyboard

    def state():
        messages = w.sent("state")
        return messages[-1]["payload"] if messages else {}

    def check_state(label, expected):
        actual = state()
        w.check(label, actual == expected, actual)

    def check_parts(label, *parts):
        content = f"{w.readout()} {w.said()}".replace(" ", "")
        w.check(label, all(part.replace(" ", "") in content for part in parts), content)

    def fraction(den):
        # 核对上下排的分子、分母，不把读数中的小数当成分数。
        fractions = w.doc.locator("#readout .frac").evaluate_all(
            "els => els.map(el => Array.from(el.children, span => span.textContent))"
        )
        return ["1", str(den)] in fractions

    def action_exists(label):
        return w.doc.locator("#actions button", has_text=label).count() > 0

    def press(key, count=1):
        stage.focus()
        for _ in range(count):
            keyboard.press(key)
        w.wait(110)

    def point(selector, scroll=False):
        if scroll:
            stage.scroll_into_view_if_needed()
        rect = w.doc.locator(selector).first.bounding_box(timeout=2000)
        return rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2

    def tap(selector):
        x, y = point(selector, scroll=True)
        if w.touch:
            w.page.touchscreen.tap(x, y)
        else:
            w.page.mouse.click(x, y)
        w.wait(120)

    def drag(source, target, vertical=False, photo=None):
        x1, y1 = point(source, scroll=True)
        x2, y2 = point(target)
        if vertical:
            x2 = x1
        points = [(x1 + (x2 - x1) * i / 8, y1 + (y2 - y1) * i / 8) for i in range(9)]
        before = w.ev("scrollY")
        (w.touch_drag if w.touch else w.mouse_drag)(
            points, before_release=(lambda: w.shot(photo)) if photo else None
        )
        w.wait(160)
        w.check("拖动时模块页面不滚", w.ev("scrollY") == before, [before, w.ev("scrollY")])

    def hold(duration, by_key=False):
        w.step("按住放大")
        if by_key:
            stage.focus()
            keyboard.down("Space")
            try:
                w.wait(duration)
            finally:
                keyboard.up("Space")
        else:
            button = w.doc.locator("#actions button.hold")
            button.scroll_into_view_if_needed()
            x, y = point("#actions button.hold")
            if w.touch:
                cdp = w.ctx.new_cdp_session(w.page)
                try:
                    cdp.send("Input.dispatchTouchEvent", {
                        "type": "touchStart", "touchPoints": [{"x": x, "y": y}],
                    })
                    w.wait(duration)
                    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                finally:
                    cdp.detach()
            else:
                mouse = w.page.mouse
                mouse.move(x, y)
                mouse.down()
                try:
                    w.wait(duration)
                finally:
                    mouse.up()
        w.wait(160)

    def options():
        return w.doc.locator("#actions .choice").all_text_contents()

    def intro(station, correct, pick):
        w.shot(f"{station}a-intro")
        w.btn("然后呢")
        choices = options()
        w.check(f"第 {station} 站提问时没有圆钮", w.grips() == 0, w.grips())
        w.check(f"第 {station} 站有三个选项", len(choices) == 3, choices)
        w.shot(f"{station}b-ask")
        w.step(f"预测第 {station} 站，选第 {pick + 1} 项")
        w.wait(430)
        w.doc.locator("#actions .choice").nth(pick).click(timeout=2500)
        w.wait(150)
        prediction = w.sent("event")[-1]["payload"]
        w.check(
            f"第 {station} 站的正确答案位于第 {correct + 1} 个",
            prediction["verb"] == "predicted" and prediction["result"]["correct"] == (pick == correct),
            prediction,
        )
        w.btn("动手试")
        w.wait(1800)
        w.check(f"第 {station} 站首次动手有提醒环", w.cue(), w.cue())
        w.shot(f"{station}c-act-first", first=True)

    def height_ticks():
        return w.doc.locator("#height-tenths path").count()

    # 桌面验证沙箱消息；CDP 触摸注入在独立页面上走完整个流程。
    if w.touch:
        w.step("打开触摸走查页面")
        url = walklib.HOST + "module/index.html"
        w.page.route(url, lambda route: route.fulfill(path=str(w.path), content_type="text/html; charset=utf-8"))
        w.page.goto(url)
        w.wait(400)
    else:
        w.open(hosted=True)
    messages = w.sent()
    w.check("先发 ready", bool(messages) and messages[0]["type"] == "ready", messages)
    stage = w.doc.locator("#stage")
    w.check("开场没有十分刻度", height_ticks() == 0, height_ticks())

    # 第 1 站：真相表 1.3 米，另量门和桌子。
    intro(1, 1, {"phone": 0, "tablet": 2, "desk": 1}[w.name])
    w.check("横杆还在 2 米以上，没有小格", height_ticks() == 0, height_ticks())
    if w.name == "desk":
        press("ArrowDown")
        press("ArrowUp")
        check_state("上键移横杆，每次 0.1 米", {"station": 1, "height": 2.2})
        press("ArrowDown", 9)
    else:
        drag("#height-grip circle", "#height-target", vertical=True)
    check_state("压到头顶 1.3 米", {"station": 1, "height": 1.3})
    w.check("横杆进入 1–2 米后显示十等分", height_ticks() == 9, height_ticks())
    w.check("碰过横杆后撤掉提醒", not w.cue(), w.cue())
    check_parts("身高读数写作 1.3 米，说明 3 个十分之一米", "1.3 米", "3 个")
    w.check("身高读数有十分之一", fraction(10), w.readout())
    w.shot("1d-height")
    w.check("只量过身高，不能提前结束", not action_exists("看读数"), w.buttons())
    w.btn("量下一样")
    drag("#height-grip circle", "#height-target", vertical=True)
    check_state("门高 1.9 米", {"station": 1, "height": 1.9})
    w.btn("量下一样")
    drag("#height-grip circle", "#height-target", vertical=True)
    check_state("桌高 0.7 米", {"station": 1, "height": 0.7})
    w.btn("看读数")
    check_parts("1.3 米是 1 米 3 分米", "1 米 3 分米")
    w.shot("1e-reveal")
    w.btn("去第 2 站")

    # 第 2 站：每层一格分别是 0.1、0.01、0.001。手动放大后钉下 0.374。
    intro(2, 2, {"phone": 0, "tablet": 1, "desk": 2}[w.name])
    minimap = w.doc.locator("#minimap").element_handle()
    w.check("放大前小地图就存在", minimap is not None, minimap)

    def overview_width():
        return w.doc.locator("#minimap .zoom-window").evaluate("el => el.getBBox().width")

    def zoom_to(depth, den, decimal, by_key=False):
        old_width = overview_width()
        hold(1250, by_key=by_key)
        w.check(f"放大到第 {depth} 层", state().get("depth") == depth, state())
        w.check(f"一格是 1 的 1/{den}，写作 {decimal}", fraction(den) and decimal in w.readout(), w.readout())
        w.check("小地图一直是同一张", minimap.evaluate("el => el === document.querySelector('#minimap')"))
        width = overview_width()
        if depth > 1:
            w.check("小地图上的框缩小", 0 < width < old_width, [width, old_width])
        w.shot(f"2d-depth-{depth}")

    hold(80)
    w.check("点一下立即松开不会完成放大", state().get("depth") == 0, state())
    zoom_to(1, 10, "0.1", by_key=w.name == "desk")
    if w.name == "desk":
        press("ArrowRight", 4)
        press("ArrowLeft")
    else:
        tap("[data-cell='3']")
    zoom_to(2, 100, "0.01")
    tap("[data-cell='7']")
    zoom_to(3, 1000, "0.001")
    w.check("放大三次还需要钉下一个点", not action_exists("看钉下的点"), w.buttons())
    if w.name == "desk":
        press("ArrowRight", 4)
        press("Enter")
    else:
        tap("[data-tick='4']")
    check_state("3、7、4 钉下 0.374", {"station": 2, "depth": 3, "path": [3, 7, 4], "pin": 0.374})
    check_parts("钉点读数跟随孩子选的位置", "0.374", "3 个", "7 个", "4 个")
    w.check("钉点读数拆成十分之一、百分之一、千分之一三个单位",
            all(fraction(den) for den in (10, 100, 1000)), w.readout())
    w.shot("2e-pin")
    w.btn("看钉下的点")
    w.btn("去第 3 站")

    # 第 3 站：130 厘米、103 厘米和独立摆出的 1.01 米。
    intro(3, 0, {"phone": 1, "tablet": 2, "desk": 0}[w.name])

    def stick(number, target=None, photo=None):
        target = number if target is None else target
        drag(f"[data-stick='{number}'] circle", f"[data-slot='{target}']", photo=photo)

    def place(m, dm, cm, value):
        check_state(f"位值格 {m}、{dm}、{cm} 摆出 {value} 米",
                    {"station": 3, "m": m, "dm": dm, "cm": cm, "value": value})

    stick(0, 2)
    place(0, 0, 0, "0")
    stick(0, photo="3d-dragging")
    place(1, 0, 0, "1")
    w.check("摆到 1 米还不能留下 1.3 米", not action_exists("留下这一排"), w.buttons())
    if w.name == "desk":
        press("ArrowRight")
        press("Enter", 4)
        press("Backspace")
    else:
        for _ in range(3):
            stick(1)
    place(1, 3, 0, "1.3")
    check_parts("摆出的读数为 1.3 米", "1.3 米")
    w.check("尺子写 130 厘米", w.doc.locator("#stage text", has_text="130 厘米").count() == 1)
    w.shot("3d-130cm")
    w.btn("留下这一排")
    place(0, 0, 0, "0")
    stick(0)
    for _ in range(3):
        stick(2)
    place(1, 0, 3, "1.03")
    check_parts("摆出的读数为 1.03 米", "1.03 米")
    w.check("尺子写 103 厘米", w.doc.locator("#stage text", has_text="103 厘米").count() == 1)
    w.btn("并排看看")
    rows = w.ev("""['first-row', 'second-row'].map(id => {
      const el = document.getElementById(id);
      if (!el) return null;
      const {x, y, width} = el.getBBox();
      return {x, y, width, cm: el.dataset.cm};
    })""")
    w.check("130 厘米和 103 厘米从同一零点起，前者更长且分两排",
            all(rows) and [row["cm"] for row in rows] == ["130", "103"]
            and abs(rows[0]["x"] - rows[1]["x"]) < 1
            and rows[0]["y"] != rows[1]["y"] and rows[0]["width"] > rows[1]["width"], rows)
    w.shot("3e-comparison")
    w.btn("摆我的长度")
    w.check("还没摆自己的数，不能完成", not action_exists("留下我的长度"), w.buttons())
    stick(0)
    stick(2)
    place(1, 0, 1, "1.01")
    w.btn("留下我的长度")
    w.check("揭晓时无圆钮", w.grips() == 0, w.grips())
    w.wait(2600)
    lenses = w.doc.locator("[data-lens]").count()
    w.check("头发丝在六层放大圈里", lenses == 6 and w.doc.locator("#hair").is_visible(), lenses)
    check_parts("放大六次，一格 1 微米，头发占 70 格", "1 微米", "70 格")
    w.shot("3f-hair")
    w.btn("看我的星卡")

    def card_text():
        return w.ev("document.querySelector('#stage').textContent.replace(/\\s+/g, ' ')")

    text = card_text()
    w.check("星卡保留实际钉下的点和自摆长度", "0.374" in text and "1.01" in text, text[:600])
    w.check("星卡写量了三样、钉下的点和三次放大",
            "量了 3 样东西" in text and "0.374" in text and "放大 3 次" in w.readout() and fraction(1000),
            [text, w.readout()])
    w.shot("4-card")

    def events():
        return [(e["payload"]["verb"], e["payload"]["result"]) for e in w.sent("event")]

    before = events()
    mistake = {
        "phone": ["tail-as-small-unit", "ten-plus-ten", "ignore-place"],
        "tablet": ["glue-digits", "still-tenths", "ignore-place"],
        "desk": [None, None, None],
    }[w.name]
    w.check("三次预测，记录对应的误区", [(r["station"], r["misconception"]) for v, r in before
            if v == "predicted"] == list(enumerate(mistake, 1)), before)
    w.check("三次观察且没有其他事件", [v for v, _ in before] == ["predicted", "observed"] * 3
            and [r for v, r in before if v == "observed"] == [{"station": i} for i in (1, 2, 3)], before)
    w.check("只完成一次", len(w.sent("complete")) == 1 and w.sent("complete")[0]["payload"] == {},
            w.sent("complete"))

    # 重玩用另一个路径和末尾的零，检查星卡来自这次钉点。
    w.btn("第 2 站")
    w.check("选站重玩跳过猜测", options() == [], options())
    hold(1250)
    tap("[data-cell='0']")
    hold(1250)
    tap("[data-cell='1']")
    hold(1250)
    tap("[data-tick='3']")
    check_state("0、1、3 钉下 0.013", {"station": 2, "depth": 3, "path": [0, 1, 3], "pin": 0.013})
    check_parts("十分位上的 0 仍然显示", "0.013")
    tap("[data-tick='0']")
    check_state("0、1、0 改钉到 0.010", {"station": 2, "depth": 3, "path": [0, 1, 0], "pin": 0.01})
    check_parts("千分位上的 0 仍然显示", "0.010")
    w.btn("看钉下的点")
    w.btn("回星卡")
    text = card_text()
    w.check("重玩星卡改为 0.010，其余保留", "0.010" in text and "1.01" in text and "0.374" not in text)
    w.check("重玩不重复记事件", events() == before and len(w.sent("complete")) == 1,
            [events(), w.sent("complete")])
    w.shot("5-card-replay")
    w.btn("从头玩")
    w.check("从头玩回到开场且页面无横向溢出",
            action_exists("然后呢") and w.ev("document.documentElement.scrollWidth <= innerWidth"),
            w.buttons())


if __name__ == "__main__":
    walklib.main(play)
