"""数线放大镜走查，验收值见 docs/constellations/zero-to-one/stars/04-tenths.md。"""
import sys
from pathlib import Path
from time import monotonic

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

    def hold(duration, by_key=False, inspect=None):
        w.step("按住放大")

        def wait_while_held():
            start = monotonic()
            if inspect:
                inspect()
            remaining = duration - (monotonic() - start) * 1000
            if remaining > 0:
                w.wait(remaining)

        if by_key:
            stage.focus()
            keyboard.down("Space")
            try:
                wait_while_held()
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
                    try:
                        wait_while_held()
                    finally:
                        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                finally:
                    cdp.detach()
            else:
                mouse = w.page.mouse
                mouse.move(x, y)
                mouse.down()
                try:
                    wait_while_held()
                finally:
                    mouse.up()
        w.wait(160)

    def options():
        return w.doc.locator("#actions .choice").all_text_contents()

    def check_prediction_ruler():
        prediction = w.doc.locator("#zoom-prediction-ruler")
        w.check("猜测图上有完整的 0 到 1 米尺", prediction.is_visible(), prediction.count())
        labels = prediction.locator("text").all_text_contents()
        w.check("猜测图标出整把尺以及被框住的一小段", {"0 米", "1 米", "这一小段"}.issubset(labels), labels)
        segments = prediction.locator("[data-ruler-segment]")
        edges = segments.evaluate_all("els => els.map(el => {const b = el.getBBox(); return [b.x, b.width]})")
        w.check("整段尺有十个连续等宽的大格",
                len(edges) == 10 and edges[0][1] > 0
                and all(abs(width - edges[0][1]) < .2 for _, width in edges)
                and all(abs(x + width - next_x) < .2 for (x, width), (next_x, _) in zip(edges, edges[1:])),
                edges)
        w.check("猜测图只指出一大格，没先画出答案",
                prediction.locator(".pick").count() == 1 and not w.doc.locator("#zoom-new-ticks").count())

    def intro(station, correct, pick):
        w.shot(f"{station}a-intro")
        w.btn("然后呢")
        choices = options()
        w.check(f"第 {station} 站提问时没有圆钮", w.grips() == 0, w.grips())
        w.check(f"第 {station} 站有三个选项", len(choices) == 3, choices)
        if station == 2:
            check_prediction_ruler()
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

    # 桌面验证沙箱消息；触摸走查直接打开活动，避开缩放后的 iframe 坐标差。
    w.open(hosted=not w.touch)
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

    def zoom_geometry():
        return w.ev("""(() => {
            const box = el => {
                if (!el) return null;
                const { x, width, height } = el.getBoundingClientRect();
                return [x, width, height];
            };
            return {
                map: box(document.querySelector('#minimap .zoom-window')),
                band: box(document.querySelector('#zoom-band')),
                source: box(document.querySelector('#zoom-source-guides rect')),
                old: [...document.querySelectorAll('#zoom-old-ticks path')].map(box),
                ticks: [...document.querySelectorAll('#zoom-new-ticks path')].map(box),
            };
        })()""")

    def endpoints(prefix, left, right):
        texts = [w.doc.locator(f"#zoom-{prefix}-{end}").all_text_contents() for end in ("start", "end")]
        row = "选中段" if prefix == "selected" else "放大窗"
        w.check(f"{row}两端看得出是 {left} 米到 {right} 米", texts == [[f"{left} 米"], [f"{right} 米"]], texts)

    def inspect_zoom():
        w.wait(260)
        moving.append(zoom_geometry())
        w.wait(270)
        moving.append(zoom_geometry())
        if w.name != "desk":
            w.shot("2d-depth-2-mid-hold")

    def zoom_to(depth, den, decimal, by_key=False, inspect=None):
        old_width = overview_width()
        hold(1250, by_key=by_key, inspect=inspect)
        w.check(f"放大到第 {depth} 层", state().get("depth") == depth, state())
        w.check(f"一格是 1 的 1/{den}，写作 {decimal}", fraction(den) and decimal in w.readout(), w.readout())
        unit = w.doc.locator("#zoom-unit").all_text_contents()
        expected = ["分米", "厘米", "毫米"][depth - 1]
        w.check(f"放大窗标明每格 1 {expected}", unit == [f"每小格 1 {expected}"], unit)
        w.check("小地图一直是同一张", minimap.evaluate("el => el === document.querySelector('#minimap')"))
        width = overview_width()
        if depth > 1:
            w.check("整把尺的框缩到原来的十分之一", abs(width * 10 - old_width) < .01, [width, old_width])
        w.shot(f"2d-depth-{depth}")

    # 核对初始画面。短按松手后，回弹的每一帧都会替换放大窗的 SVG 标签。
    map_label = w.doc.locator("#minimap text", has_text="整把米尺")
    lens_label = w.doc.locator("#zoom-lens text", has_text="放大窗")
    guides = w.doc.locator("#zoom-guides [data-end]")
    w.check("整把米尺在上、放大窗在下，两条线对应起来",
            map_label.is_visible() and lens_label.is_visible() and guides.count() == 2
            and map_label.evaluate("el => el.getBBox().y") < lens_label.evaluate("el => el.getBBox().y"))
    endpoints("range", "0", "1")
    hold(80)
    w.check("点一下立即松开不会完成放大", state().get("depth") == 0, state())
    zoom_to(1, 10, "0.1", by_key=w.name == "desk")
    if w.name == "desk":
        press("ArrowRight", 4)
        press("ArrowLeft")
    else:
        tap("[data-cell='3']")
    endpoints("selected", "0.3", "0.4")
    w.shot("2c-selected-03-to-04")
    initial = zoom_geometry()
    hold(330)
    w.wait(650)
    w.check("松手取消后，刻度回到刚刚选的格，没跳下一层", state().get("depth") == 1
            and zoom_geometry() == initial, zoom_geometry())
    moving = []
    zoom_to(2, 100, "0.01", inspect=inspect_zoom)
    settled = zoom_geometry()
    if w.name == "desk":
        w.check("减少动效时，按住中途尺与窗保持原状，完成时直接到位",
                moving[0] == moving[1] == initial and settled["map"] != initial["map"],
                [initial, *moving, settled])
    else:
        first, second = moving
        w.check("选中段在两帧间逐渐向左展开",
                all(frame["band"] for frame in (initial, first, second)) and first["ticks"] and second["ticks"]
                and initial["band"][0] > first["band"][0] > second["band"][0]
                and initial["band"][1] < first["band"][1] < second["band"][1], [initial, *moving])
        boundaries = [frame["old"][4][0] - frame["old"][3][0]
                      for frame in (initial, first, second) if len(frame["old"]) == 11]
        w.check("原尺选中段的两条刻线向两旁分开，新的九条刻线逐步显出",
                len(boundaries) == 3 and boundaries[0] < boundaries[1] < boundaries[2]
                and len(first["ticks"]) == len(second["ticks"]) == 9
                and 0 < first["ticks"][0][2] < second["ticks"][0][2], [boundaries, first, second])
        w.check("整段尺的视窗在两帧间缩到选中段",
                initial["map"][0] < first["map"][0] < second["map"][0] <= settled["map"][0]
                and initial["map"][1] > first["map"][1] > second["map"][1] >= settled["map"][1],
                [initial, *moving, settled])
        w.check("两帧中，额外的小框始终标在原尺的 0.3 到 0.4 米",
                first["source"] and first["source"] == second["source"]
                and all(abs(first["source"][i] - settled["map"][i]) < .2 for i in (0, 1)),
                [first["source"], second["source"], settled["map"]])
    endpoints("range", "0.3", "0.4")
    tap("[data-cell='7']")
    endpoints("selected", "0.37", "0.38")
    w.shot("2c-selected-037-to-038")
    zoom_to(3, 1000, "0.001")
    endpoints("range", "0.37", "0.38")
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

    def hair_ruler(which):
        return w.ev(f"""(() => {{
            const ruler = document.querySelector('[data-hair-ruler="{which}"]');
            if (!ruler) return null;
            const extent = el => {{
                if (!el) return null;
                const {{ x, y, width }} = el.getBBox();
                return [x, y, x + width];
            }};
            return {{
                depth: Number(ruler.dataset.depth),
                span: Number(ruler.dataset.spanMicrons),
                line: extent(ruler.querySelector('[data-hair-baseline]')),
                marks: [...ruler.querySelectorAll('[data-hair-tick]')].map(el => extent(el)[0]),
                selected: extent(ruler.querySelector('.hair-selection')),
                pick: Number(ruler.dataset.hairSelected),
                diameter: extent(document.querySelector('#hair [data-hair-diameter]')),
                landmark: extent(document.querySelector('[data-hair-landmark] [data-hair-diameter]')),
            }};
        }})()""")

    def inspect_hair_scale(depth, pick=None):
        ruler = hair_ruler("current")
        intervals = 1 if depth == 6 else 10
        span = 10 ** (6 - depth)
        w.check(f"头发尺第 {depth} 步的实际范围是 {span} 微米",
                ruler is not None and ruler["depth"] == depth and ruler["span"] == span, ruler)
        if ruler:
            check_ruler_marks(ruler, intervals, f"第 {depth} 步的尺画出 {intervals} 个等宽间隔")
        if depth:
            parent = hair_ruler("parent")
            clip = parent and parent["selected"]
            line = parent and parent["line"]
            w.check("选框标着上一把尺中的一格",
                    clip and line and line[2] > line[0] and (pick is None or parent["pick"] == pick)
                    and parent["span"] == span * 10
                    and abs((clip[2] - clip[0]) / (line[2] - line[0]) - .1) < .002,
                    parent)

    def check_ruler_marks(ruler, intervals, label):
        line, marks = ruler["line"], ruler["marks"]
        width = line[2] - line[0] if line else 0
        w.check(label, width > 0 and len(marks) == intervals + 1
                and all(abs(x - (line[0] + i * width / intervals)) < .2 for i, x in enumerate(marks)), ruler)

    w.wait(1400)
    check_parts("从 1 米尺出发，先让孩子把格子放大", "1 米")
    inspect_hair_scale(0)
    w.check("一开始就能跳到星卡，头发结论尚未出现",
            action_exists("看我的星卡") and "70 格" not in f"{w.readout()} {w.said()}"
            and not w.doc.locator("#hair [data-hair-diameter]").count(), w.buttons())
    w.shot("3f-hair-start")

    if action_exists("放大一格"):
        if w.touch:
            tap('[data-hair-ruler="current"] [data-hair-piece="7"]')
        else:
            press("ArrowRight")
            press("Enter")
        inspect_hair_scale(1, pick=7 if w.touch else 5)
        for depth in range(2, 7):
            w.btn("放大一格")
            inspect_hair_scale(depth)
            if depth == 3:
                millimeter = hair_ruler("current")
                line, hair = millimeter["line"], millimeter["landmark"]
                w.check("一毫米尺上的头发直径约占尺宽的 7%",
                        line and hair and abs((hair[2] - hair[0]) / (line[2] - line[0]) - .07) < .001,
                        [line, hair])
                w.shot("3f-hair-one-mm")
            if depth == 4:
                w.btn("退一格")
                inspect_hair_scale(3)
                w.btn("放大一格")
                inspect_hair_scale(4)

        check_parts("放大六次，一格 1 微米，头发占约 70 格", "1 微米", "70 格")
        measuring = hair_ruler("measure")
        w.check("头发对照尺的总宽为 70 微米", measuring and measuring["span"] == 70, measuring)
        if measuring:
            check_ruler_marks(measuring, 70, "头发对照尺画出 71 条线，恰好围成 70 小格")
            diameter = measuring["diameter"]
            w.check("头发丝的直径两端对齐上尺的 0 和 70",
                    diameter and measuring["line"] and diameter[1] < measuring["line"][1]
                    and all(abs(diameter[i] - measuring["line"][i]) < .2 for i in (0, 2)), measuring)
        w.shot("3f-hair")
        w.btn("退一格")
        inspect_hair_scale(5)
        w.check("退回时撤掉 70 格对照，仍能再放大", hair_ruler("measure") is None and action_exists("放大一格"))
        w.btn("放大一格")
        w.btn("再量一次")
        inspect_hair_scale(0)
        w.check("重看回到 1 米尺，跳过不会自动完成活动", hair_ruler("measure") is None and not w.sent("complete"))
    else:
        w.check("头发尺等孩子自己放大", False, w.buttons())

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
            and [r for v, r in before if v == "observed"] == [{"station": i, "item": "station-complete"} for i in (1, 2, 3)], before)
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
