# Discord 内容自动推送

零成本、无需服务器：GitHub Actions 定时运行 → Discord Webhook 推送到频道。

| 功能 | 频道建议 | 频率 | 数据来源 | 需要的 Secret |
|---|---|---|---|---|
| 突发新闻（中文快讯 + X 新闻账号机翻） | ⚡突发新闻 | 约每 1 分钟 | 华尔街见闻美股快讯；Walter Bloomberg、Watcher Guru（Telegram 镜像）、Unusual Whales（官网），只推美股相关 | `WEBHOOK_NEWS` |
| 川普 Truth Social（机翻） | 🦅川普专区 | 约每 1 分钟 | trumpstruth.org 存档 | `WEBHOOK_TRUMP` |
| 国会议员股票交易 + Quiver Quant 动态 | 🏛️白宫内幕 | 每 30 分钟 / 约每 1 分钟 | Capitol Trades、Quiver Quantitative（Telegram 镜像） | `WEBHOOK_WHITEHOUSE` |
| 恐惧贪婪指数 + Reddit 24H 热度榜 | 📈市场指标＆异动榜 | 交易日盘前 / 收盘后 | CNN、ApeWisdom | `WEBHOOK_MARKET` |
| 财报速递（EPS/营收 vs 预期 + 盘前盘后反应） | 📅每周预告＆财报速递 | 约每 3 分钟 | Earnings Whispers、Yahoo Finance | `WEBHOOK_CALENDAR`（与每周预告共用） |
| 盘前 / 盘后异动榜 | 📈市场指标＆异动榜 | 交易日盘前、收盘后 | Yahoo Finance | `WEBHOOK_MARKET`（与市场指标共用） |
| 下周财报 + 下周财经日历（图片） | 📅每周预告＆财报速递 | 每周日傍晚（美东） | Earnings Whispers、华尔街见闻 | `WEBHOOK_CALENDAR` |

## 部署步骤

### 1. Discord：为每个频道创建 Webhook
频道右侧 ⚙️ 编辑频道 → 整合（Integrations）→ Webhooks → 新 Webhook → 改名（如"仙人快讯"）、可换头像 → **复制 Webhook URL**。

> Webhook URL 相当于发帖密码，不要发到聊天或公开地方。

### 2. GitHub：建仓库并上传本项目
- 推荐 **Public（公开）仓库**：GitHub Actions 对公开仓库免费不限时长。Webhook 存在 Secrets 里是加密的，公开仓库也看不到。
- 如果用 Private（私有）仓库，每月只有 2000 分钟免费额度，不够每分钟循环检查；需要把 `feeds.yml` 里的 `LOOP_MINUTES` 默认值改成 `0`、`*/10` 改成 `*/30`（每 30 分钟检查一次）。

### 3. GitHub：填写 Secrets
仓库 → Settings → Secrets and variables → Actions → New repository secret，逐个添加上表中的名字，值粘贴对应频道的 Webhook URL。

### 4. 测试运行
仓库 → Actions → 选择一个工作流 → Run workflow：
- `dry_run` 填 `1`：只在日志里打印，不发到 Discord
- `dry_run` 填 `0`：真实发送

第一次运行新闻 / 川普时，每个来源只补发最新 3 条，之后只推送新内容。

## 常用调整（都在 `config.py`）
- `WSCN_MIN_SCORE`：`2` 只推红色重要快讯，`1` 推全部（量很大）
- `NEWS_KEYWORDS`：只推含关键词的新闻，如 `["美联储", "英伟达"]`
- `NEWS_RSS`：增删中文 RSS 新闻源
- `TELEGRAM_CHANNELS`：增删 X 新闻账号的 Telegram 镜像频道
- `TRUMP_INCLUDE_REPOSTS`：是否推送川普转帖
- `REDDIT_TOP_N`：热度榜显示前几名
- `CAL_TZ` / `CAL_DATA_COUNTRIES` / `CAL_*_IMPORTANCE`：财经日历的时区和筛选条件
- `WEEKLY_MENTION_EVERYONE`：每周预告是否 @everyone

## 注意
- GitHub 定时任务高峰期可能延迟 5–20 分钟，不是秒级推送。
- 免费数据源都是非官方接口，个别来源偶尔失效时，其他来源不受影响；日志里会显示哪一个失败。
- 仓库 60 天无任何提交时 GitHub 会暂停定时任务；本项目每次推送都会提交 `state.json`，正常情况下不会触发。
- 机器翻译仅供参考；市场数据不构成投资建议。

## 本地运行（可选）
```bash
pip install -r requirements.txt
DRY_RUN=1 python -m jobs.news      # 只打印
WEBHOOK_NEWS=你的链接 python -m jobs.news
```
