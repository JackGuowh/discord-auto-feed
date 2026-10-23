"""所有可调整的设置都在这里。改完提交到 GitHub 即生效。"""

# ===== ⚡ 突发新闻 =====
# 华尔街见闻 7x24 快讯频道：global-channel(要闻) / us-stock-channel(美股) /
# forex-channel(外汇) / commodity-channel(商品) / a-stock-channel(A股)
# (频道, 最低重要度)：1 = 该频道全部快讯；2 = 只推红色重要快讯
WSCN_CHANNELS = [("global-channel", 2), ("us-stock-channel", 1)]
WSCN_MIN_SCORE = 1
# 突发新闻是否只推美股相关（False = 和参考服务器一样，全球要闻、政治、科技都推）
NEWS_US_ONLY = False
# 只推含这些关键词的快讯（留空 = 不过滤）。例如 ["美联储", "特朗普", "英伟达"]
NEWS_KEYWORDS = []
# 额外的中文 RSS 新闻源（名称, 链接）。不需要可以清空列表
NEWS_RSS = []   # 例如 [("FT中文网", "https://www.ftchinese.com/rss/news")]
# X(推特)新闻账号 —— 通过它们的 Telegram 公开镜像频道免费抓取 (频道名, 显示名称[, 推送到哪个频道])
# 在浏览器打开 https://t.me/s/频道名 能看到消息列表的才能用
TELEGRAM_CHANNELS = [
    # 第 4 项 True = 这个来源只推美股相关（Walter Bloomberg 量太大，只留美股/宏观）
    ("WalterBloomberg", "Walter Bloomberg", None, True),
    ("WatcherGuru", "Watcher Guru"),           # JUST IN 类突发新闻
    ("disclosetv", "Disclose.tv"),             # 全球/美国政治突发
    ("insiderpaper", "Insider Paper"),         # 全球突发、财经
    ("QuiverQuant", "Quiver Quantitative", "WEBHOOK_WHITEHOUSE", True),  # 国会交易/政策数据 → 白宫内幕
]
# 只推美股相关：包含股票代码（如 $TSLA）或下列任一关键词的才推送
UNUSUAL_WHALES = True   # Unusual Whales 新闻（官网抓取，没有 Telegram 频道）
# 只推美股相关的关键词（Telegram 和 Unusual Whales 共用）
TELEGRAM_KEYWORDS = [
    "🇺🇸", "U.S.", "US", "USA", "AMERICA", "FED", "FOMC", "POWELL", "TREASURY", "YIELD",
    "S&P", "SPX", "NASDAQ", "DOW", "WALL STREET", "STOCK", "SHARES", "EARNINGS", "REVENUE",
    "EPS", "GUIDANCE", "IPO", "SEC ", "TRUMP", "WHITE HOUSE", "TARIFF", "CPI", "PCE", "JOBS",
    "PAYROLL", "UNEMPLOYMENT", "GDP", "INFLATION", "RATE CUT", "RATE HIKE", "BUYBACK",
    "MARKETS", "CONGRESS",
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
WHITEHOUSE_PRESS = False        # 是否推送白宫官网新闻稿（非美股内容，默认关闭）

# ===== 🏛️ 白宫内幕：国会议员股票交易 =====
CONGRESS_CHECK_MINUTES = 30     # 每 30 分钟检查一次 Capitol Trades（申报一天更新几次）
CONGRESS_SKIP_SMALL = False     # True = 跳过 $1K–15K 的小额交易

# ===== 📈 市场指标 =====
# 盘前推一次恐惧贪婪指数；收盘后推恐惧贪婪指数 + Reddit 24H 热度榜
REDDIT_TOP_N = 20                    # 热度榜显示前几名

# ===== 🧪 稀有 & 特种气体行业新闻 =====
GAS_CHECK_MINUTES = 20          # 每 20 分钟检查一次（这些网站更新不频繁）
# (显示名称, 抓取方式, 地址)
GAS_SOURCES = [
    ("gasworld", "gasworld", "https://www.gasworld.com/"),
    ("GAWDA Media", "rss", "https://gawdamedia.com/feed/"),
    ("GAWDA", "rss", "https://www.gawda.org/feed/"),
    ("CGA 压缩气体协会", "cga", "https://www.cganet.com/resources/news/"),
    ("SEMI", "semi", "https://www.semi.org/en/news-media-press/semi-press-releases"),
    # Google 新闻关键词：补充其他媒体上的稀有/特种气体新闻（不需要可以删掉这一行）
    ("Google 新闻", "google",
     '"helium" OR "neon gas" OR "xenon" OR "krypton" OR "specialty gases" OR "electronic gases" '
     'OR "industrial gases" OR "tungsten hexafluoride" OR "sulfur hexafluoride" OR "nitrogen trifluoride"'),
]
GAS_GOOGLE_STRICT = True        # Google 新闻只推标题里明确提到下面这些气体的
# 标题/摘要里出现这些词会标红并注明「🔥 涉及」
GAS_HIGHLIGHT = ["Helium", "Neon", "Krypton", "Xenon", "Argon", "WF6", "SF6", "NF3",
                 "Tungsten hexafluoride", "Sulfur hexafluoride", "Nitrogen trifluoride",
                 "HFC-227ea", "Electronic gases", "Specialty gases", "Rare gases", "Noble gases",
                 "Hydrogen fluoride", "Germane", "Silane", "Diborane", "Phosphine", "Arsine"]

# ===== 📊 财报速递 =====
EARNINGS_TOP_N = 40             # 只推当天关注度最高的前 40 家公司
EARNINGS_MIN_MARKET_CAP = 2e9    # 只推美国上市、市值 ≥ 20 亿美元的公司（排除场外 ADR 和小银行）
EARNINGS_CHECK_MINUTES = 3      # 每 3 分钟检查一次是否有新财报发布

# ===== 🚀 异动榜 =====
MOVERS_TOP_N = 10               # 涨幅榜、跌幅榜各显示前 10
MOVERS_MIN_MARKET_CAP = 2e9     # 只看市值 ≥ 20 亿美元的公司

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
