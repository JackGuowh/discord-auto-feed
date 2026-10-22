"""定时任务调度：不依赖 GitHub 自带的 cron（新仓库经常不触发）。
新闻循环每分钟顺便检查一次，到点就用 gh 命令触发对应的工作流，每个任务每天只触发一次。"""
import os
import subprocess

from common import load_state, now_et, save_state

# (任务名, 工作流文件, 参数, 星期几[0=周一], 开始时间, 结束时间)  —— 均为美东时间
TASKS = [
    ("movers_pre", "movers.yml", {"mode": "pre"}, range(0, 5), "09:00", "09:29"),
    ("market_fg", "market.yml", {"mode": "fg"}, range(0, 5), "09:35", "11:00"),
    ("market_close", "market.yml", {"mode": "close"}, range(0, 5), "16:25", "19:00"),
    ("movers_post", "movers.yml", {"mode": "post"}, range(0, 5), "16:45", "19:00"),
    ("weekly", "weekly.yml", {}, [6], "18:00", "23:59"),
]


def main():
    if not os.getenv("GH_TOKEN") or os.getenv("DRY_RUN") == "1":
        return
    now = now_et()
    hm = now.strftime("%H:%M")
    state = load_state()
    fired = state.setdefault("scheduler", [])
    try:
        for name, wf, inputs, days, start, end in TASKS:
            key = f"{name}:{now.date()}"
            if now.weekday() not in days or not (start <= hm <= end) or key in fired:
                continue
            cmd = ["gh", "workflow", "run", wf, "--ref", "main"]
            for k, v in inputs.items():
                cmd += ["-f", f"{k}={v}"]
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(f"[scheduler] 触发 {name}: {r.returncode} {r.stderr.strip()[:200]}")
            if r.returncode == 0:
                fired.append(key)
        state["scheduler"] = fired[-100:]
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
