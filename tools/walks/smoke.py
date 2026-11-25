# Curio · 冒烟走查：给还没有专属走查的旧模块用。用法：python tools/walks/smoke.py <index.html> <截图目录> [--only tablet|phone|desk]
# 像平台一样放进沙箱 iframe 打开，查四件事：ready 是第一条消息、console 没有错误、没有横向溢出、第一屏截图。
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import walklib  # noqa: E402


def play(w):
    w.open(hosted=True, wait=1200)
    msgs = w.sent()
    first = msgs[0]["type"] if msgs else None
    w.check("ready 是第一条消息", first == "ready", [m["type"] for m in msgs])
    w.check("页面没有横向溢出", w.ev("document.documentElement.scrollWidth <= innerWidth"), w.ev("document.documentElement.scrollWidth"))
    w.shot("1-first", first=True)


if __name__ == "__main__":
    walklib.main(play, timeout=60)
