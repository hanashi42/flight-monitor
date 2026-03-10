import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
DB_PATH = os.path.join(os.path.dirname(__file__), "prices.db")
