"""从孩子看见的钉头、墨印、粉笔和拓杆位置检验杠杆。不读取活动的模型。"""
import json
import math
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import walklib

VECTORS = json.loads((TOOLS / "tests/fixtures/expected/lever-dock.json").read_text(encoding="utf-8"))
LIVE = '[data-lever="live"]'
RINGS = {(s["rings"], s["hole"]): s for s in VECTORS["ring_moves"]}
PIVOTS = {(s["pivot"], s["left_weight"]): s for s in VECTORS["pivot_moves"]}

# 直接量实际绘制的圆钉。boundingBox 包含整棵 SVG 的旋转、缩放与窄屏布局。
def center(element):
    box = element.bounding_box(timeout=2000)
    if not box or min(box["width"], box["height"]) <= 0:
        raise walklib.WalkError("画面上应能看见这枚钉子")
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def pins(w, drawing):
    root = w.doc.locator(drawing)
    return [center(root.locator(f'[data-part="{part}"]')) for part in ("left-hook", "pivot", "right-hook")]


def check_beam(w, drawing, left_arm, right_arm, low_end):
    left, pivot, right = pins(w, drawing)
    span = right[0] - left[0]
    fraction = (pivot[0] - left[0]) / span if span > 0 else -1
    w.check(f"支点分开的两段实际距离为 {left_arm} 对 {right_arm}",
            abs(fraction - left_arm / (left_arm + right_arm)) < 0.025, (left, pivot, right))
    gap = left[1] - right[1]
    w.check(f"这根杆实际画成 {low_end}", {"level": abs(gap) <= 1, "left": gap > 1, "right": gap < -1}[low_end],
            (left[1], right[1]))


def visible_shapes(root, selector):
    return sum(shape.is_visible() for shape in root.locator(selector).all())


def beam_imprints(w, drawing, side, hook, pivot, holes, weight):
    # 在屏幕上沿倾斜的木杆轴投影。光有正确总数，还不能证明印落在对应的两孔之间。
    groups = drawing.locator(f'[data-beam-segment="{side}"]').evaluate_all("""segments => segments.map(
        segment => Array.from(segment.querySelectorAll('[data-beam-stamp]'), stamp => {
            const box = stamp.getBoundingClientRect();
            const style = getComputedStyle(stamp);
            if (!box.width || !box.height || style.visibility === 'hidden' || style.opacity === '0') return null;
            return [box.x + box.width / 2, box.y + box.height / 2];
        }).filter(Boolean))""")
    dx, dy = hook[0] - pivot[0], hook[1] - pivot[1]
    length = math.hypot(dx, dy)
    pitch = length / holes
    slots = []
    for stamps in groups:
        indices = set()
        for x, y in stamps:
            x, y = x - pivot[0], y - pivot[1]
            along = (x * dx + y * dy) / length
            offset = abs(x * dy - y * dx) / length
            indices.add(math.floor(along / pitch) if offset < pitch / 2 else -1)
        # 同一孔距所有墨印必须都贴在同一段杆上，段数从木尖向钩子递增。
        slots.append((next(iter(indices)) if len(indices) == 1 else -1, len(stamps)))
    w.check(f"{side} 杆从木尖到钩子每段都有 {weight} 枚方印",
            sorted(slots) == [(i, weight) for i in range(holes)], sorted(slots))


def position(w, spec):
    drawing = w.doc.locator(LIVE)
    if "hole" in spec:
        left, right = spec["hole"], 1
        left_hook, pivot, right_hook = pins(w, LIVE)
        beam_imprints(w, drawing, "left", left_hook, pivot, left, spec["rings"])
        beam_imprints(w, drawing, "right", right_hook, pivot, right, 6)
        w.check("左钩上的铁环个数", visible_shapes(drawing, '[data-part="ring"]') == spec["rings"])
    else:
        left, right = spec["pivot"], 6 - spec["pivot"]
    check_beam(w, LIVE, left, right, spec["low_end"])
    for side in ("left", "right"):
        n = visible_shapes(w.doc.locator("#stage"), f'[data-stamp="{side}"]')
        w.check(f'{side} 棚中能数到 {spec[side + "_stamps"]} 枚印', n == spec[side + "_stamps"], n)


def chalk_gap(w, detail=False):
    def box(part):
        tag = f'#stage [data-detail="{part}"]' if detail else f'#stage [data-part="{part}"]'
        return w.doc.locator(tag).bounding_box(timeout=2000)
    crate, chalk = box("crate"), box("footprint")
    w.check("粉笔印在箱底下方的同一处", min(chalk["x"] + chalk["width"], crate["x"] + crate["width"])
            > max(chalk["x"], crate["x"]), (crate, chalk))
    return chalk["y"] - crate["y"] - crate["height"]


def arrow(w, key, steps=1):
    stage = w.doc.locator("#stage")
    stage.focus()
    for _ in range(steps):
        stage.press(key)
    w.wait(350)


def drag_holes(w, kind, signed_steps, count):
    grip = w.doc.locator(f'[data-grip="{kind}"]')
    grip.scroll_into_view_if_needed()
    x, y = center(grip)
    left, _, right = pins(w, LIVE)
    distance = (right[0] - left[0]) * signed_steps / count
    points = [(x + distance * i / 12, y) for i in range(13)]
    (w.touch_drag if w.touch else w.mouse_drag)(points)
    w.wait(350)


def hidden_formula(w):
    text = w.doc.locator("body").inner_text()
    w.check("还没有翻纸，页面没有乘法或力矩等式", re.search(r"[×✕]|牛[·⋅]格", text) is None, text[-200:])


def masked_shot(w, name, mask):
    # 遮词只用于拍证据，不改动实物，也不触发游戏操作。
    style = w.doc.add_style_tag(content=mask + " {visibility:hidden !important}")
    try:
        w.shot(name)
    finally:
        style.evaluate("(el) => el.remove()")


def play_one(w, route):
    w.open(hosted=True)
    hidden_formula(w)
    w.btn("不能，箱子重")
    w.btn("松开木杆")
    position(w, RINGS[(1, 1)])
    hidden_formula(w)
    w.shot("01-ring", first=True)
    if route == "A":
        drag_holes(w, "ring", -4, 2)
        position(w, RINGS[(1, 5)])
        hidden_formula(w)
        arrow(w, "ArrowLeft")
    else:
        # 一气拖到杆尾，掠过六格时没有停、没有松手，不能替孩子认领「看见停平」。
        drag_holes(w, "ring", -6, 2)
        position(w, RINGS[(1, 7)])
        for label in ("加一枚环", "拓下这根杆"):
            btn = w.doc.get_by_role("button", name=label, exact=True)
            w.check("只看过抬箱，还不能" + label, not btn.count() or btn.is_disabled())
        arrow(w, "ArrowRight")
    position(w, RINGS[(1, 6)])
    hidden_formula(w)
    level_gap = chalk_gap(w)
    w.check("停平时箱底遮着粉笔印", level_gap <= 1, level_gap)
    if route == "A":
        w.shot("02-level")
        before = pins(w, LIVE)
        w.btn("翻看算式")
        w.check("翻开才读得到两组相等的数", re.search(r"1\s*(?:牛|N)?\s*×\s*6", w.doc.locator("body").inner_text())
                and re.search(r"6\s*(?:牛|N)?\s*×\s*1", w.doc.locator("body").inner_text()))
        w.check("翻纸不挪杆", pins(w, LIVE) == before)
        w.btn("合上算式")
        hidden_formula(w)
    arrow(w, "ArrowLeft")
    position(w, RINGS[(1, 7)])
    up_gap = chalk_gap(w)
    w.check("箱底高过粉笔印，能看清两者之间的缝", up_gap > 1 and up_gap > level_gap + 1, (level_gap, up_gap))
    seats = w.doc.locator('[data-lever="seesaw"]')
    lseat, rseat = [center(seats.locator(f'[data-part="{s}-hook"]')) for s in ("left", "right")]
    w.check("旁边的跷跷板也画成远端低、近端高", lseat[1] > rseat[1] + 1, (lseat, rseat))
    closeup = chalk_gap(w, detail=True)
    w.check("纸框中真实露出至少六像素的亮缝", closeup >= 6, closeup)
    if route == "A":
        masked_shot(w, "03-wow-without-words", "#say, #readout, #hint, #stage text")
    arrow(w, "ArrowRight")
    position(w, RINGS[(1, 6)])
    w.check("退一孔又遮回去", abs(chalk_gap(w) - level_gap) <= 1)
    arrow(w, "ArrowLeft")
    w.check("再进杆尾，缝重新出现", abs(chalk_gap(w) - up_gap) <= 1)
    if route == "B":
        w.btn("加一枚环")
        arrow(w, "ArrowRight", 4)
        position(w, RINGS[(2, 3)])
        arrow(w, "ArrowRight")
        position(w, RINGS[(2, 2)])
        arrow(w, "ArrowLeft")
    w.btn("拓下这根杆")
    position(w, PIVOTS[(3, 6)])
    proofs = w.doc.locator("[data-proof]")
    collect = w.doc.get_by_role("button", name="收进星卡", exact=True)
    w.check("刚看到中档不自动盖印", proofs.count() == 0, proofs.count())
    w.check("两个台架端点尚未比较不能收卡", not collect.count() or collect.is_disabled())
    w.btn("取下 1 牛")
    w.btn("加上 1 牛")
    position(w, PIVOTS[(3, 6)])
    w.check("亲手调回中档才有一印", proofs.count() == 1, proofs.count())
    w.check("只找到中档仍不能收卡", not collect.count() or collect.is_disabled())
    if route == "A":
        w.shot("04-sealed", first=True)
    drag_holes(w, "pivot", 1, 6)
    position(w, PIVOTS[(4, 6)])
    for _ in range(3):
        w.btn("取下 1 牛")
    position(w, PIVOTS[(4, 3)])
    w.check("两次平衡分别留下两印", proofs.count() == 2, proofs.count())
    arrow(w, "ArrowLeft")
    position(w, PIVOTS[(3, 3)])
    if route == "A":
        arrow(w, "ArrowRight")
    else:
        for _ in range(3):
            w.btn("加上 1 牛")
    w.btn("收进星卡")
    chosen = VECTORS["prints"][route]
    first, second = '[data-lever="print-1"]', '[data-lever="print-2"]'
    check_beam(w, first, chosen["ring_hole"], 1, chosen["first_low_end"])
    check_beam(w, second, chosen["pivot"], 6 - chosen["pivot"], "level")
    count_rings = visible_shapes(w.doc.locator(first), '[data-part="ring"]')
    count_weights = visible_shapes(w.doc.locator(second), '[data-part="weight"]')
    w.check("上幅还挂着我选的铁环", count_rings == chosen["rings"], count_rings)
    w.check("下幅还留着我选的配重", count_weights == chosen["weights"], count_weights)
    masked_shot(w, f"05-print-{route}-without-words", "#say, #readout, #hint, #stage text")
    w.shot(f"06-print-{route}")
    events = [m["payload"] for m in w.sent("event")]
    observed = [e["result"]["station"] for e in events if e["verb"] == "observed"]
    w.check("两站各记一次观察", observed == [1, 2], observed)
    w.check("只领一张星卡", len(w.sent("complete")) == 1)


def play(w):
    play_one(w, "A")
    play_one(w, "B")


if __name__ == "__main__":
    walklib.main(play)
