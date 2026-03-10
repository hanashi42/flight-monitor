import os
from dotenv import load_dotenv

load_dotenv()

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "hanashi-flights")

# Origins
ORIGINS = ["KUL", "JHB"]

# Destinations grouped by distance tier, with alert thresholds
DESTINATIONS = {
    # Southeast Asia — threshold MYR 100
    "sea": {
        "threshold": [
            {"max_price": 50, "level": "BUY_NOW", "emoji": "🔴", "label": "立刻买"},
            {"max_price": 75, "level": "VERY_LOW", "emoji": "🟠", "label": "超低价"},
            {"max_price": 100, "level": "LOW", "emoji": "🟡", "label": "低价"},
        ],
        "airports": [
            {"code": "BKK", "name": "曼谷"},
            {"code": "SGN", "name": "胡志明"},
            {"code": "HAN", "name": "河内"},
            {"code": "DPS", "name": "巴厘岛"},
            {"code": "CGK", "name": "雅加达"},
            {"code": "MNL", "name": "马尼拉"},
            {"code": "HKT", "name": "普吉岛"},
            {"code": "REP", "name": "暹粒"},
            {"code": "SIN", "name": "新加坡"},
        ],
    },
    # East Asia — threshold MYR 250
    "east_asia": {
        "threshold": [
            {"max_price": 150, "level": "BUY_NOW", "emoji": "🔴", "label": "立刻买"},
            {"max_price": 200, "level": "VERY_LOW", "emoji": "🟠", "label": "超低价"},
            {"max_price": 250, "level": "LOW", "emoji": "🟡", "label": "低价"},
        ],
        "airports": [
            {"code": "KIX", "name": "大阪"},
            {"code": "NRT", "name": "东京"},
            {"code": "ICN", "name": "首尔"},
            {"code": "TPE", "name": "台北"},
            {"code": "HKG", "name": "香港"},
            {"code": "PVG", "name": "上海"},
            {"code": "CTS", "name": "札幌"},
            {"code": "FUK", "name": "福冈"},
            {"code": "OKA", "name": "冲绳"},
        ],
    },
    # Australia — threshold MYR 400
    "oceania": {
        "threshold": [
            {"max_price": 250, "level": "BUY_NOW", "emoji": "🔴", "label": "立刻买"},
            {"max_price": 350, "level": "VERY_LOW", "emoji": "🟠", "label": "超低价"},
            {"max_price": 400, "level": "LOW", "emoji": "🟡", "label": "低价"},
        ],
        "airports": [
            {"code": "SYD", "name": "悉尼"},
            {"code": "MEL", "name": "墨尔本"},
            {"code": "PER", "name": "珀斯"},
        ],
    },
}

SCAN_MONTHS_AHEAD = 6
CURRENCY = "MYR"
ALERT_DEDUP_HOURS = 12
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.db")
