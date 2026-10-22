"""📅 每周预告：下周重要经济数据 + 大公司财报日程（周日晚推送）。"""
from collections import defaultdict
from datetime import datetime, timedelta

import config as C
from common import ET, embed, get, now_et, post

WEBHOOK = "WEBHOOK_CALENDAR"
WD = "一二三四五六日"

EVENT_ZH = {  # 常见数据的中文名（没有收录的保持英文）
    "Non-Farm Employment Change": "非农就业人数", "Unemployment Rate": "失业率",
    "CPI m/m": "CPI 月率", "Core CPI m/m": "核心 CPI 月率", "CPI y/y": "CPI 年率",
    "PPI m/m": "PPI 月率", "Core PPI m/m": "核心 PPI 月率",
    "Core PCE Price Index m/m": "核心 PCE 物价指数月率",
    "Federal Funds Rate": "联邦基金利率决议", "FOMC Statement": "FOMC 声明",
    "FOMC Press Conference": "FOMC 新闻发布会", "FOMC Meeting Minutes": "FOMC 会议纪要",
    "Advance GDP q/q": "GDP 初值（季率）", "Prelim GDP q/q": "GDP 修正值（季率）",
    "Final GDP q/q": "GDP 终值（季率）", "Retail Sales m/m": "零售销售月率",
    "Core Retail Sales m/m": "核心零售销售月率",
    "Unemployment Claims": "初请失业金人数", "ISM Manufacturing PMI": "ISM 制造业 PMI",
    "ISM Services PMI": "ISM 服务业 PMI", "JOLTS Job Openings": "JOLTS 职位空缺",
    "ADP Non-Farm Employment Change": "ADP 就业人数",
    "Prelim UoM Consumer Sentiment": "密歇根消费者信心初值",
    "CB Consumer Confidence": "谘商会消费者信心", "Fed Chair Powell Speaks": "美联储主席讲话",
    "Average Hourly Earnings m/m": "平均时薪月率", "Durable Goods Orders m/m": "耐用品订单月率",
    "Building Permits": "营建许可", "Existing Home Sales": "成屋销售",
    "New Home Sales": "新屋销售", "Crude Oil Inventories": "EIA 原油库存",
}
IMPACT = {"High": "🔴", "Medium": "🟠", "Low": "⚪"}


def econ_events():
    try:
        rows = get("https://nfs.faireconomy.media/ff_calendar_thisweek.json").json()
    except Exception as e:  # noqa: BLE001
        print(f"[weekly] 经济日历失败: {e}")
        return {}
    by_day = defaultdict(list)
    for r in rows:
        if r.get("country") not in C.CAL_COUNTRIES or r.get("impact") not in C.CAL_IMPACTS:
            continue
        dt = datetime.fromisoformat(r["date"]).astimezone(ET)
        name = EVENT_ZH.get(r["title"], r["title"])
        extra = []
        if r.get("forecast"):
            extra.append(f"预期 {r['forecast']}")
        if r.get("previous"):
            extra.append(f"前值 {r['previous']}")
        t = dt.strftime("%H:%M") if (dt.hour, dt.minute) != (0, 0) else "全天"
        by_day[dt.date()].append(
            f"{IMPACT.get(r['impact'], '')} {t} {name}" + (f"（{'，'.join(extra)}）" if extra else ""))
    return by_day


def parse_cap(s):
    try:
        return float(s.replace("$", "").replace(",", ""))
    except Exception:  # noqa: BLE001
        return 0.0


def earnings(days):
    out = {}
    for d in days:
        try:
            rows = get("https://api.nasdaq.com/api/calendar/earnings",
                       params={"date": d.isoformat()},
                       headers={"Origin": "https://www.nasdaq.com",
                                "Referer": "https://www.nasdaq.com/"}).json()
            rows = (rows.get("data") or {}).get("rows") or []
        except Exception as e:  # noqa: BLE001
            print(f"[weekly] 财报 {d} 失败: {e}")
            continue
        rows = [r for r in rows if parse_cap(r.get("marketCap", "0")) >= C.EARNINGS_MIN_MARKET_CAP]
        rows.sort(key=lambda r: -parse_cap(r.get("marketCap", "0")))
        when = {"time-pre-market": "盘前", "time-after-hours": "盘后"}
        out[d] = [f"**{r['symbol']}** {when.get(r.get('time'), '')}".strip()
                  for r in rows[: C.EARNINGS_MAX_PER_DAY]]
    return out


def main():
    today = now_et().date()
    # 周日运行 → 下周一到周五；其他日子手动运行 → 本周剩余交易日
    if today.weekday() == 6:
        days = [today + timedelta(days=i) for i in range(1, 6)]
        label = "下周预告"
    else:
        days = [today + timedelta(days=i) for i in range(0, 5 - today.weekday())]
        label = "本周剩余日程"
        if not days:  # 周六
            print("[weekly] 周六没有剩余交易日，跳过")
            return

    ev = econ_events()
    er = earnings(days)
    fields = []
    for d in days:
        parts = []
        if ev.get(d):
            parts.append("\n".join(ev[d]))
        if er.get(d):
            parts.append("📊 财报：" + "、".join(er[d]))
        fields.append((f"{d.month}/{d.day} 周{WD[d.weekday()]}",
                       "\n".join(parts) or "暂无重要事件"))

    post(WEBHOOK, embeds=[embed(
        title=f"📅 {label} · {days[0].month}/{days[0].day} – {days[-1].month}/{days[-1].day}",
        description="时间均为美东时间 · 🔴 高影响　🟠 中等影响",
        fields=fields, color=0xFDD835,
        footer="数据：Forex Factory / Nasdaq · 日程可能变动",
    )])


if __name__ == "__main__":
    main()
