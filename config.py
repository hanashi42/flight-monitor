import os
from dotenv import load_dotenv

load_dotenv()

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "hanashi-flights")

ROUTES = [
    {"from": "JHB", "to": "KIX", "label": "JHB → KIX"},
    {"from": "KUL", "to": "KIX", "label": "KUL → KIX"},
    {"from": "KIX", "to": "JHB", "label": "KIX → JHB"},
    {"from": "KIX", "to": "KUL", "label": "KIX → KUL"},
]

THRESHOLDS = [
    {"max_price": 150, "level": "BUY_NOW", "emoji": "🔴", "label": "立刻买"},
    {"max_price": 200, "level": "VERY_LOW", "emoji": "🟠", "label": "超低价"},
    {"max_price": 250, "level": "LOW", "emoji": "🟡", "label": "低价"},
]

SCAN_MONTHS_AHEAD = 6
CURRENCY = "MYR"
ALERT_DEDUP_HOURS = 12
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.db")
