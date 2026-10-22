"""所有可调整的设置都在这里。改完提交到 GitHub 即生效。"""

# ===== ⚡ 突发新闻 =====
# 华尔街见闻 7x24 快讯频道：global-channel(要闻) / us-stock-channel(美股) /
# forex-channel(外汇) / commodity-channel(商品) / a-stock-channel(A股)
WSCN_CHANNELS = ["global-channel"]
# 快讯重要度：1 = 全部快讯（量很大，每天数百条）；2 = 只推红色重要快讯（推荐）
WSCN_MIN_SCORE = 2
# 只推含这些关键词的快讯（留空 = 不过滤）。例如 ["美联储", "特朗普", "英伟达"]
NEWS_KEYWORDS = []
# 额外的中文 RSS 新闻源（名称, 链接）。不需要可以清空列表
NEWS_RSS = [
    ("FT中文网", "https://www.ftchinese.com/rss/news"),
]
# 首次运行时每个来源只补发最新几条，避免刷屏
FIRST_RUN_BACKFILL = 3

# ===== 🦅 川普 / 🏛️ 白宫 =====
TRUMP_FEED = "https://www.trumpstruth.org/feed"
TRUMP_INCLUDE_REPOSTS = False   # 是否推送转帖
WHITEHOUSE_FEED = "https://www.whitehouse.gov/news/feed/"

# ===== 📈 市场指标（收盘后推送）=====
# (Yahoo 代码, 显示名称)
MARKET_SYMBOLS = [
    ("^GSPC", "标普500"),
    ("^IXIC", "纳斯达克"),
    ("^DJI", "道琼斯"),
    ("^RUT", "罗素2000"),
    ("^VIX", "VIX 恐慌指数"),
    ("^TNX", "10年期美债收益率"),
    ("DX-Y.NYB", "美元指数"),
    ("GC=F", "黄金"),
    ("CL=F", "WTI 原油"),
    ("BTC-USD", "比特币"),
]
# 重点个股（可自行增删）
WATCHLIST = ["NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "META", "GOOGL"]

# ===== 📅 每周预告 =====
CAL_COUNTRIES = ["USD"]              # 经济数据国家，例如加上 "CNY"
CAL_IMPACTS = ["High", "Medium"]     # High=高影响, Medium=中等
EARNINGS_MIN_MARKET_CAP = 50e9       # 只列市值 ≥ 500 亿美元的公司财报
EARNINGS_MAX_PER_DAY = 12
