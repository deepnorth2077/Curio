"""卷扬台：比较相同和不同货单；验算每秒做功和星卡上的最后一单。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib


def play(w):
    w.open(hosted=True)
    w.btn("还得看看")
    w.btn("去卷扬台")
    w.btn("同时开动")
    w.doc.get_by_role("button", name="给乙机换货").wait_for(timeout=9000)
    w.check("同做十二焦耳，三秒四瓦、六秒两瓦", w.sent("state")[-1]["payload"] ==
            dict(station=1, workA=12, timeA=3, powerA=4, workB=12, timeB=6, powerB=2))
    w.shot("1-hoists")
    w.btn("给乙机换货")
    w.doc.get_by_label("乙机货单").select_option("30")
    w.btn("同时开动")
    w.doc.get_by_role("button", name="收好工票").wait_for(timeout=9000)
    state = w.sent("state")[-1]["payload"]
    w.check("晚到的乙机也能每秒做更多功", state["powerB"] == 5 and state["timeB"] == 6)
    w.shot("2-stopwatches")
    w.btn("再配一单")
    w.doc.get_by_label("乙机货单").select_option("18")
    w.btn("同时开动")
    w.doc.get_by_role("button", name="收好工票").wait_for(timeout=9000)
    w.check("十八焦耳六秒得到三瓦", w.sent("state")[-1]["payload"]["powerB"] == 3)
    w.btn("收好工票")
    text = w.doc.locator("#dyn").text_content()
    w.check("留下实际做过的最后一单", "18 J，用 6 s，每秒 3 J" in text, text)
    w.check("一次预测、两站观察和一次完成", [m["payload"]["verb"] for m in w.sent("event")] ==
            ["predicted", "observed", "observed"] and len(w.sent("complete")) == 1)
    w.shot("card")


if __name__ == "__main__":
    walklib.main(play)
