"""在一次 GitHub Actions 运行里循环检查新闻和川普动态，实现约 1 分钟一次的刷新。

GitHub 定时任务最短只能 5 分钟一次，而且经常延迟。所以每次运行会在内部
循环 LOOP_MINUTES 分钟、每 INTERVAL 秒检查一次，下一次定时任务会排队接上。
"""
import os
import time
import traceback

import scheduler
from jobs import congress, earnings, gas, news, shows, telegram, trump, uw

RESET_PREFIXES = ("wscn:", "rss:", "truth", "tg:", "unusualwhales", "congress", "earnings_",
                  "gas", "shows_")


def maybe_reset():
    """reset.txt 里的编号变了，就清掉各频道的去重记录，让每个来源重新补发最新 3 条（用于测试）。"""
    from common import ROOT, load_state, save_state
    f = ROOT / "reset.txt"
    if not f.exists():
        return
    rid = f.read_text(encoding="utf-8").strip()
    state = load_state()
    if not rid or state.get("reset_id") == rid:
        return
    for k in list(state):
        if k.startswith(RESET_PREFIXES):
            del state[k]
    state["reset_id"] = rid
    save_state(state)
    print(f"[run_feeds] 已按 reset.txt（{rid}）重置去重记录")


LOOP_MINUTES = float(os.getenv("LOOP_MINUTES", "14"))
INTERVAL = int(os.getenv("INTERVAL", "60"))


def main():
    maybe_reset()
    deadline = time.time() + LOOP_MINUTES * 60
    rounds = 0
    while True:
        start = time.time()
        rounds += 1
        for job in (news.main, telegram.main, uw.main, trump.main, congress.main, earnings.main, gas.main, shows.main,
                    scheduler.main):
            try:
                job()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        if time.time() + INTERVAL > deadline:
            break
        time.sleep(max(0, INTERVAL - (time.time() - start)))
    print(f"[run_feeds] 完成 {rounds} 轮检查")


if __name__ == "__main__":
    main()
