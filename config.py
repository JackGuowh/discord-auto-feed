"""所有可调整的设置都在这里。改完提交到 GitHub 即生效。"""

# ===== ⚡ 突发新闻 =====
# 华尔街见闻 7x24 快讯频道：global-channel(要闻) / us-stock-channel(美股) /
# forex-channel(外汇) / commodity-channel(商品) / a-stock-channel(A股)
WSCN_CHANNELS = ["us-stock-channel"]   # 只要美股相关
# 快讯重要度：1 = 该频道全部快讯；2 = 只推红色重要快讯
WSCN_MIN_SCORE = 1
# 只推含这些关键词的快讯（留空 = 不过滤）。例如 ["美联储", "特朗普", "英伟达"]
NEWS_KEYWORDS = []
# 额外的中文 RSS 新闻源（名称, 链接）。不需要可以清空列表
NEWS_RSS = []   # 例如 [("FT中文网", "https://www.ftchinese.com/rss/news")]
# X(推特)新闻账号 —— 通过它们的 Telegram 公开镜像频道免费抓取 (频道名, 显示名称)
# 在浏览器打开 https://t.me/s/频道名 能看到消息列表的才能用
TELEGRAM_CHANNELS = [
    ("WalterBloomberg", "Walter Bloomberg"),   # 美股/宏观快讯
    ("WatcherGuru", "Watcher Guru"),           # JUST IN 类突发新闻
]
# 只推美股相关：包含股票代码（如 $TSLA）或下列任一关键词的才推送
TELEGRAM_KEYWORDS = [
    "🇺🇸", "U.S.", "US ", "USA", "AMERICA", "FED", "FOMC", "POWELL", "TREASURY", "YIELD",
    "S&P", "SPX", "NASDAQ", "DOW", "WALL STREET", "STOCK", "SHARES", "EARNINGS", "REVENUE",
    "EPS", "GUIDANCE", "IPO", "SEC ", "TRUMP", "WHITE HOUSE", "TARIFF", "CPI", "PCE", "JOBS",
    "PAYROLL", "UNEMPLOYMENT", "GDP", "INFLATION", "RATE CUT", "RATE HIKE", "BUYBACK",
]
# 包含这些词的不推（过滤加密货币等非美股内容）
TELEGRAM_EXCLUDE = ["BITCOIN", "$BTC", "$ETH", "ETHEREUM", "CRYPTO", "$SOL", "$XRP", "$DOGE",
                    "MEMECOIN", "STABLECOIN", "BINANCE", "COINBASE WALLET"]
# 首次运行时每个来源只补发最新几条，避免刷屏
FIRST_RUN_BACKFILL = 3

# ===== 🦅 川普 / 🏛️ 白宫 =====
TRUMP_FEED = "https://www.trumpstruth.org/feed"
TRUMP_INCLUDE_REPOSTS = False   # 是否推送转帖
WHITEHOUSE_FEED = "https://www.whitehouse.gov/news/feed/"

# ===== 📈 市场指标 =====
# 盘前推一次恐惧贪婪指数；收盘后推恐惧贪婪指数 + Reddit 24H 热度榜
REDDIT_TOP_N = 20                    # 热度榜显示前几名

# ===== 📅 每周预告（周日推送两条：下周财报 + 下周财经日历）=====
WEEKLY_MENTION_EVERYONE = False      # 推送时是否 @everyone
# 财经日历时区（成员主要在国内就用北京时间；想用美东时间改成 America/New_York）
CAL_TZ = "Asia/Shanghai"
CAL_TZ_LABEL = "北京时间"
# 数据来源：华尔街见闻财经日历。重要度 1=低 2=中 3=高 4=极高
CAL_COUNTRIES = ["US"]               # 只列这些国家（只要美股相关 = 只留美国）
CAL_DATA_MIN_IMPORTANCE = 2          # 经济数据：重要度 ≥ 2 列出
CAL_EVENT_MIN_IMPORTANCE = 3         # 事件（发布会、讲话等）：重要度 ≥ 3 列出
CAL_HIGHLIGHT_IMPORTANCE = 3         # 重要度 ≥ 3 的高亮显示
CAL_EARNINGS_PER_DAY = 8             # 日历图里每天列出的热门财报数量
# 财报来源：Earnings Whispers「Most Anticipated Earnings Releases」
EARNINGS_MAX_TICKERS = 60            # 财报帖里最多列出多少个代码
