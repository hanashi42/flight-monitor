import os
from dotenv import load_dotenv

load_dotenv()

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "hanashi-flights")

# Origins
ORIGINS = ["KUL", "JHB"]

# ── Priority destinations ────────────────────────────────────────
# Japan + Taiwan first, rest optional (uncomment to add later)
DESTINATIONS = {
    # Japan — threshold MYR 250
    "japan": {
        "threshold": [
            {"max_price": 150, "level": "BUY_NOW", "emoji": "\U0001f534", "label": "立刻买"},
            {"max_price": 200, "level": "VERY_LOW", "emoji": "\U0001f7e0", "label": "超低价"},
            {"max_price": 250, "level": "LOW", "emoji": "\U0001f7e1", "label": "低价"},
        ],
        "airports": [
            {"code": "KIX", "name": "大阪"},
            {"code": "NRT", "name": "东京成田"},
            {"code": "HND", "name": "东京羽田"},
            {"code": "CTS", "name": "札幌"},
            {"code": "FUK", "name": "福冈"},
            {"code": "OKA", "name": "冲绳"},
        ],
    },
    # Taiwan — threshold MYR 200
    "taiwan": {
        "threshold": [
            {"max_price": 100, "level": "BUY_NOW", "emoji": "\U0001f534", "label": "立刻买"},
            {"max_price": 150, "level": "VERY_LOW", "emoji": "\U0001f7e0", "label": "超低价"},
            {"max_price": 200, "level": "LOW", "emoji": "\U0001f7e1", "label": "低价"},
        ],
        "airports": [
            {"code": "TPE", "name": "台北桃园"},
            {"code": "KHH", "name": "高雄"},
        ],
    },
    # ── Uncomment below to add more tiers later ──
    # "sea": {
    #     "threshold": [
    #         {"max_price": 50, "level": "BUY_NOW", "emoji": "\U0001f534", "label": "立刻买"},
    #         {"max_price": 75, "level": "VERY_LOW", "emoji": "\U0001f7e0", "label": "超低价"},
    #         {"max_price": 100, "level": "LOW", "emoji": "\U0001f7e1", "label": "低价"},
    #     ],
    #     "airports": [
    #         {"code": "BKK", "name": "曼谷"},
    #         {"code": "SGN", "name": "胡志明"},
    #         {"code": "MNL", "name": "马尼拉"},
    #         {"code": "DPS", "name": "巴厘岛"},
    #         {"code": "SIN", "name": "新加坡"},
    #     ],
    # },
    # "oceania": {
    #     "threshold": [
    #         {"max_price": 250, "level": "BUY_NOW", "emoji": "\U0001f534", "label": "立刻买"},
    #         {"max_price": 350, "level": "VERY_LOW", "emoji": "\U0001f7e0", "label": "超低价"},
    #         {"max_price": 400, "level": "LOW", "emoji": "\U0001f7e1", "label": "低价"},
    #     ],
    #     "airports": [
    #         {"code": "SYD", "name": "悉尼"},
    #         {"code": "MEL", "name": "墨尔本"},
    #         {"code": "PER", "name": "珀斯"},
    #     ],
    # },
}

# ── Scan settings ────────────────────────────────────────────────
SCAN_MONTHS_AHEAD = 4          # Look 4 months ahead
CURRENCY = "MYR"
ALERT_DEDUP_HOURS = 12
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.db")
