"""松开车闸：观察理想轨与粗糙轨的等时印迹。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import walklib


def play(w):
    w.open(hosted=True)
    w.check("首条消息是 ready", w.sent()[0]["type"] == "ready")
    w.btn("自己慢慢停")
    w.btn("上轨道试试")
    w.shot("1-glide", first=True)

    def run():
        before = len(w.sent("state"))
        w.btn("松开车闸")
        w.page.wait_for_function("before => {const states=window.__got.filter(m=>m.type==='state'); "
                                 "return states.length>before && states.at(-1).payload.seconds===4;}", arg=before)
        return w.sent("state")[-1]["payload"]

    rest = run()
    w.check("无水平力，静止的小车仍静止", (rest["velocity"], rest["position"], rest["netForce"]) == (0, 0, 0), rest)
    w.check("共五个印章叠在原点", "×5" in w.doc.locator("#dyn").text_content())
    launch = w.doc.locator("#launch")
    if w.touch:
        launch.scroll_into_view_if_needed()
        b = launch.bounding_box()
        w.touch_drag([(b["x"] + 6, b["y"] + b["height"]/2),
                      (b["x"] + b["width"] - 3, b["y"] + b["height"]/2)])
    else:
        launch.press("End")
    coast = run()
    w.check("2 米每秒无阻力滑了 4 秒", (coast["velocity"], coast["position"], coast["netForce"]) == (2, 8, 0), coast)

    def gaps():
        return w.ev("""Array.from(document.querySelectorAll('#dyn .stamp'), c=>+c.getAttribute('cx'))
            .map((x,i,a)=>i ? x-a[i-1] : 0).slice(1)""")

    clear_gaps = gaps()
    w.check("连续四秒印迹等距", len(clear_gaps) == 4 and len(set(clear_gaps)) == 1, clear_gaps)
    w.btn("去第 2 站")
    w.btn("间距慢慢变小")
    w.btn("上轨道试试")
    w.shot("2-pad", first=True)
    w.doc.locator("#mat").press("End")
    w.check("铺上垫子时阻力向左", "向左 1 牛" in w.readout(), w.readout())
    rough = run()
    rough_gaps = gaps()
    w.check("同初速铺垫后四秒停车", (rough["launch"], rough["velocity"], rough["position"], rough["netForce"]) == (2,0,4,0), rough)
    w.check("每秒走过的距离逐步变小", len(rough_gaps) == 4 and all(a>b>0 for a,b in zip(rough_gaps, rough_gaps[1:])), rough_gaps)
    w.doc.locator("#mat").press("Home")
    w.check("收起垫子，阻力归零", "合力 0 牛" in w.readout(), w.readout())
    w.btn("收好星卡")
    events = w.sent("event")
    w.check("预测与真实观察各两次", [e["payload"]["verb"] for e in events] == ["predicted","observed"]*2, events)
    complete = w.sent("complete")
    w.check("星卡保存同初速的两条车印", len(complete)==1 and complete[0]["payload"]["records"]["rough"]["launch"] == 2, complete)
    w.check("星卡写下两段实测路程", all(word in w.doc.locator("#receipt").inner_text() for word in ["8 米","4 米"]))
    w.check("手机没有横向滚动", w.ev("document.documentElement.scrollWidth <= innerWidth"))
    w.shot("3-card")


if __name__ == "__main__":
    walklib.main(play, timeout=75)
