"""常见美股公司中文名（财经日历显示用）。没有收录的公司显示英文简称。"""
ZH = {
    "AAPL": "苹果", "MSFT": "微软", "NVDA": "英伟达", "AMZN": "亚马逊", "GOOGL": "谷歌", "GOOG": "谷歌",
    "META": "Meta", "TSLA": "特斯拉", "AVGO": "博通", "BRK.B": "伯克希尔", "LLY": "礼来", "JPM": "摩根大通",
    "V": "Visa", "MA": "万事达", "UNH": "联合健康", "XOM": "埃克森美孚", "CVX": "雪佛龙", "WMT": "沃尔玛",
    "COST": "好市多", "HD": "家得宝", "PG": "宝洁", "JNJ": "强生", "ABBV": "艾伯维", "MRK": "默沙东",
    "PFE": "辉瑞", "KO": "可口可乐", "PEP": "百事", "MCD": "麦当劳", "SBUX": "星巴克", "NKE": "耐克",
    "DIS": "迪士尼", "NFLX": "奈飞", "ORCL": "甲骨文", "CRM": "Salesforce", "ADBE": "Adobe", "AMD": "AMD",
    "INTC": "英特尔", "QCOM": "高通", "TXN": "德州仪器", "MU": "美光", "AMAT": "应用材料", "LRCX": "泛林",
    "KLAC": "科磊", "ASML": "阿斯麦", "TSM": "台积电", "ARM": "Arm", "SMCI": "超微电脑", "DELL": "戴尔",
    "HPQ": "惠普", "IBM": "IBM", "CSCO": "思科", "ANET": "Arista", "NOW": "ServiceNow", "PLTR": "Palantir",
    "SNOW": "Snowflake", "SHOP": "Shopify", "UBER": "优步", "ABNB": "爱彼迎", "PYPL": "PayPal",
    "SQ": "Block", "XYZ": "Block", "COIN": "Coinbase", "HOOD": "Robinhood", "SOFI": "SoFi", "MSTR": "Strategy",
    "BA": "波音", "LMT": "洛克希德马丁", "RTX": "雷神", "NOC": "诺斯罗普", "GD": "通用动力", "GE": "通用电气",
    "GEV": "GE Vernova", "CAT": "卡特彼勒", "DE": "迪尔", "HON": "霍尼韦尔", "MMM": "3M", "UPS": "UPS",
    "FDX": "联邦快递", "UNP": "联合太平洋", "T": "AT&T", "VZ": "Verizon", "TMUS": "T-Mobile",
    "CMCSA": "康卡斯特", "BAC": "美国银行", "WFC": "富国银行", "C": "花旗", "GS": "高盛", "MS": "摩根士丹利",
    "BLK": "贝莱德", "SCHW": "嘉信理财", "AXP": "美国运通", "BX": "黑石", "KKR": "KKR", "SPGI": "标普全球",
    "MCO": "穆迪", "CME": "芝商所", "ICE": "洲际交易所", "TMO": "赛默飞", "DHR": "丹纳赫", "ABT": "雅培",
    "ISRG": "直觉外科", "AMGN": "安进", "GILD": "吉利德", "BMY": "百时美施贵宝", "VRTX": "福泰制药",
    "REGN": "再生元", "CVS": "CVS", "CI": "信诺", "ELV": "Elevance", "HUM": "Humana", "NVO": "诺和诺德",
    "LIN": "林德", "APD": "空气化工", "SHW": "宣伟", "NEM": "纽蒙特", "FCX": "自由港", "DOW": "陶氏",
    "F": "福特", "GM": "通用汽车", "RIVN": "Rivian", "LCID": "Lucid", "NIO": "蔚来", "LI": "理想汽车",
    "XPEV": "小鹏汽车", "BABA": "阿里巴巴", "PDD": "拼多多", "JD": "京东", "BIDU": "百度", "TCEHY": "腾讯",
    "SPOT": "Spotify", "RBLX": "Roblox", "RDDT": "Reddit", "SNAP": "Snap", "PINS": "Pinterest",
    "DASH": "DoorDash", "CMG": "Chipotle", "YUM": "百胜", "LULU": "lululemon", "TGT": "塔吉特",
    "LOW": "劳氏", "BKNG": "Booking", "MAR": "万豪", "HLT": "希尔顿", "DAL": "达美航空", "UAL": "美联航",
    "AAL": "美国航空", "LUV": "西南航空", "CCL": "嘉年华", "MRNA": "Moderna", "CRWD": "CrowdStrike",
    "PANW": "Palo Alto", "FTNT": "飞塔", "ZS": "Zscaler", "NET": "Cloudflare", "DDOG": "Datadog",
    "MDB": "MongoDB", "TEAM": "Atlassian", "WDAY": "Workday", "INTU": "财捷", "ADP": "ADP", "CDNS": "楷登电子",
    "SNPS": "新思科技", "MRVL": "迈威尔", "ON": "安森美", "NXPI": "恩智浦", "ADI": "亚德诺", "MCHP": "微芯",
    "STX": "希捷", "WDC": "西部数据", "SNDK": "闪迪", "APH": "安费诺", "GLW": "康宁", "CLS": "天弘科技",
    "VRT": "Vertiv", "ETN": "伊顿", "CEG": "Constellation", "VST": "Vistra", "NEE": "新纪元能源",
    "ENPH": "Enphase", "FSLR": "First Solar", "OXY": "西方石油", "COP": "康菲", "SLB": "斯伦贝谢",
    "SKHY": "SK海力士", "QXO": "QXO", "CVNA": "Carvana", "IP": "国际纸业", "UBS": "瑞银", "STM": "意法半导体",
    "TWLO": "Twilio", "CAKE": "芝乐坊", "VMC": "火神材料", "CNC": "Centene", "AMKR": "安靠", "PNR": "滨特尔",
    "CARR": "开利", "APP": "AppLovin", "FI": "Fiserv", "LITE": "Lumentum", "COHR": "Coherent", "CART": "Instacart",
    "OKLO": "Oklo", "TEM": "Tempus AI", "CHKP": "Check Point", "EL": "雅诗兰黛", "CAH": "卡地纳健康", "U": "Unity",
    "GFS": "格芯", "RIOT": "Riot", "DUOL": "多邻国", "AFRM": "Affirm", "TTD": "The Trade Desk",
    "PLUG": "Plug Power", "IONQ": "IonQ", "RKLB": "Rocket Lab", "HIMS": "Hims & Hers", "CELH": "Celsius", "BSX": "波士顿科学", "SPCX": "SpaceX", "CRWV": "CoreWeave", "ROKU": "Roku",
}


def zh_name(ticker, company=""):
    if ticker in ZH:
        return ZH[ticker]
    import re
    n = re.sub(r"^The\s+", "", (company or ticker).strip())
    suffix = (r"[,.]?\s*(Inc|Incorporated|Corp|Corporation|Company|Companies|Co|Holdings|Holding|Group|Ltd|Limited|plc|"
              r"N\.V|S\.A|SE|LP|Technologies|Technology|Enterprises|International|Brands|Incorporated|Platforms)\.?$")
    for _ in range(3):
        n = re.sub(suffix, "", n, flags=re.I).strip()
    return n or ticker
