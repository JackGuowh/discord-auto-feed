"""在一次 GitHub Actions 运行里循环检查新闻和川普动态，实现约 1 分钟一次的刷新。

GitHub 定时任务最短只能 5 分钟一次，而且经常延迟。所以每次运行会在内部
循环 LOOP_MINUTES 分钟、每 INTERVAL 秒检查一次，下一次定时任务会排队接上。
"""
import os
import time
import traceback

from jobs import news, telegram, trump

LOOP_MINUTES = float(os.getenv("LOOP_MINUTES", "14"))
INTERVAL = int(os.getenv("INTERVAL", "60"))


def main():
    deadline = time.time() + LOOP_MINUTES * 60
    rounds = 0
    while True:
        start = time.time()
        rounds += 1
        for job in (news.main, telegram.main, trump.main):
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
