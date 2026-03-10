# Flight Monitor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Monitor JHB/KUL ↔ KIX flight prices via Kiwi Tequila API, push alerts to Telegram when prices drop below thresholds.

**Architecture:** Single Python process running APScheduler (2x daily scans) + Telegram bot polling. Kiwi Tequila API for flight data, SQLite for price history, python-telegram-bot for notifications and commands.

**Tech Stack:** Python 3.10+, requests, python-telegram-bot v22, APScheduler, SQLite3 (stdlib)

---

### Task 1: Project Setup & Config

**Files:**
- Create: `~/flight-monitor/requirements.txt`
- Create: `~/flight-monitor/config.py`
- Create: `~/flight-monitor/.env`
- Create: `~/flight-monitor/.gitignore`

**Step 1: Create requirements.txt**

```
requests>=2.31
python-telegram-bot>=22.0
APScheduler>=3.10
python-dotenv>=1.0
```

**Step 2: Create .gitignore**

```
.env
prices.db
__pycache__/
*.pyc
```

**Step 3: Create .env**

```
KIWI_API_KEY=__PLACEHOLDER__
TELEGRAM_BOT_TOKEN=8045804388:AAHVqSiDGozFA76fVXuS01nNBiaMBDOc7Uw
TELEGRAM_CHAT_ID=8761909198
```

**Step 4: Create config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

KIWI_API_KEY = os.getenv("KIWI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

KIWI_BASE_URL = "https://api.tequila.kiwi.com"

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
```

**Step 5: Install dependencies**

```bash
cd ~/flight-monitor && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

**Step 6: Init git repo and commit**

```bash
cd ~/flight-monitor && git init && git add -A && git commit -m "chore: project setup with config and dependencies"
```

---

### Task 2: Database Layer

**Files:**
- Create: `~/flight-monitor/db.py`

**Step 1: Write db.py**

```python
import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY,
            route TEXT NOT NULL,
            fly_date TEXT NOT NULL,
            price REAL NOT NULL,
            airline TEXT,
            stops INTEGER DEFAULT 0,
            deep_link TEXT,
            queried_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            route TEXT NOT NULL,
            fly_date TEXT NOT NULL,
            price REAL NOT NULL,
            level TEXT NOT NULL,
            sent_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_prices_route_date ON prices(route, fly_date);
        CREATE INDEX IF NOT EXISTS idx_alerts_dedup ON alerts(route, fly_date, price);
    """)
    conn.close()


def save_price(route, fly_date, price, airline, stops, deep_link):
    conn = get_conn()
    conn.execute(
        "INSERT INTO prices (route, fly_date, price, airline, stops, deep_link, queried_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (route, fly_date, price, airline, stops, deep_link, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_previous_price(route, fly_date):
    conn = get_conn()
    row = conn.execute(
        "SELECT price FROM prices WHERE route = ? AND fly_date = ? ORDER BY queried_at DESC LIMIT 1",
        (route, fly_date),
    ).fetchone()
    conn.close()
    return row["price"] if row else None


def get_cheapest_per_route():
    conn = get_conn()
    rows = conn.execute("""
        SELECT route, fly_date, price, airline, stops, deep_link
        FROM prices
        WHERE queried_at > datetime('now', '-24 hours')
        GROUP BY route
        HAVING price = MIN(price)
        ORDER BY route
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def was_alert_sent(route, fly_date, price, hours=12):
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    row = conn.execute(
        "SELECT 1 FROM alerts WHERE route = ? AND fly_date = ? AND price = ? AND sent_at > ?",
        (route, fly_date, price, cutoff),
    ).fetchone()
    conn.close()
    return row is not None


def save_alert(route, fly_date, price, level):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (route, fly_date, price, level, sent_at) VALUES (?, ?, ?, ?, ?)",
        (route, fly_date, price, level, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_price_history(route, days=30):
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT fly_date, MIN(price) as min_price, queried_at
           FROM prices WHERE route = ? AND queried_at > ?
           GROUP BY fly_date ORDER BY fly_date""",
        (route, cutoff),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

**Step 2: Test manually**

```bash
cd ~/flight-monitor && source venv/bin/activate && python3 -c "
from db import init_db, save_price, get_previous_price, get_cheapest_per_route
init_db()
save_price('KUL-KIX', '2026-05-01', 199.0, 'AirAsia X', 0, 'https://example.com')
print('prev:', get_previous_price('KUL-KIX', '2026-05-01'))
print('cheapest:', get_cheapest_per_route())
print('DB OK')
"
```

Expected: prints prev price 199.0 and cheapest list with one entry.

**Step 3: Commit**

```bash
git add db.py && git commit -m "feat: add SQLite database layer"
```

---

### Task 3: Kiwi Tequila API Client

**Files:**
- Create: `~/flight-monitor/kiwi_client.py`

**Step 1: Write kiwi_client.py**

```python
import requests
from datetime import datetime, timedelta
from config import KIWI_API_KEY, KIWI_BASE_URL, CURRENCY


HEADERS = {"apikey": KIWI_API_KEY}


def search_flights(fly_from, fly_to, date_from, date_to, max_stopovers=2):
    """Search flights for a date range. Returns list of flight dicts."""
    params = {
        "fly_from": fly_from,
        "fly_to": fly_to,
        "date_from": date_from.strftime("%d/%m/%Y"),
        "date_to": date_to.strftime("%d/%m/%Y"),
        "curr": CURRENCY,
        "max_stopovers": max_stopovers,
        "sort": "price",
        "limit": 5,
        "one_for_city": 0,
        "flight_type": "oneway",
    }
    resp = requests.get(
        f"{KIWI_BASE_URL}/v2/search",
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])

    results = []
    for flight in data:
        airlines = ", ".join(set(r.get("airline", "?") for r in flight.get("route", [])))
        results.append({
            "price": flight["price"],
            "fly_date": datetime.utcfromtimestamp(flight["dTime"]).strftime("%Y-%m-%d"),
            "airline": airlines,
            "stops": len(flight.get("route", [])) - 1,
            "deep_link": flight.get("deep_link", ""),
        })
    return results


def scan_month(fly_from, fly_to, year, month):
    """Scan a whole month, return cheapest flights found."""
    from calendar import monthrange
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, monthrange(year, month)[1])
    return search_flights(fly_from, fly_to, first_day, last_day)


def scan_route_months(fly_from, fly_to, months_ahead=6):
    """Scan multiple months ahead for a route. Returns all results."""
    all_results = []
    now = datetime.now()
    for i in range(months_ahead):
        month = now.month + i
        year = now.year
        while month > 12:
            month -= 12
            year += 1
        try:
            results = scan_month(fly_from, fly_to, year, month)
            all_results.extend(results)
        except Exception as e:
            print(f"Error scanning {fly_from}-{fly_to} {year}-{month:02d}: {e}")
    return all_results
```

**Step 2: Test manually (requires API key)**

```bash
cd ~/flight-monitor && source venv/bin/activate && python3 -c "
from kiwi_client import scan_month
from datetime import datetime
results = scan_month('KUL', 'KIX', 2026, 6)
for r in results[:3]:
    print(f'{r[\"fly_date\"]} {r[\"airline\"]} MYR {r[\"price\"]} ({r[\"stops\"]} stops)')
"
```

**Step 3: Commit**

```bash
git add kiwi_client.py && git commit -m "feat: add Kiwi Tequila API client"
```

---

### Task 4: Telegram Bot (send + commands)

**Files:**
- Create: `~/flight-monitor/telegram_bot.py`

**Step 1: Write telegram_bot.py**

```python
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ROUTES, THRESHOLDS
from db import get_cheapest_per_route, get_price_history


def get_app():
    return Application.builder().token(TELEGRAM_BOT_TOKEN).build()


async def send_message(app, text, parse_mode="HTML"):
    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode=parse_mode,
        disable_web_page_preview=True,
    )


def format_alert(flight, route_label, level_info, prev_price=None):
    diff = ""
    if prev_price is not None:
        change = flight["price"] - prev_price
        arrow = "↓" if change < 0 else "↑"
        diff = f" ({arrow} MYR {abs(change):.0f})"

    stops_text = "直飞" if flight["stops"] == 0 else f"{flight['stops']}次转机"
    return (
        f"{level_info['emoji']} <b>{level_info['label']}！{route_label}</b>\n"
        f"📅 {flight['fly_date']}\n"
        f"✈️ {flight['airline']} ({stops_text})\n"
        f"💰 MYR {flight['price']:.0f}{diff}\n"
        f"🔗 <a href=\"{flight['deep_link']}\">订票链接</a>"
    )


def format_summary(cheapest_list):
    if not cheapest_list:
        return "📊 <b>每日价格汇总</b>\n\n暂无数据"
    lines = ["📊 <b>每日价格汇总</b>\n"]
    for item in cheapest_list:
        stops_text = "直飞" if item["stops"] == 0 else f"{item['stops']}转"
        lines.append(
            f"<b>{item['route']}</b>: MYR {item['price']:.0f} "
            f"({item['fly_date']}, {item['airline']}, {stops_text})"
        )
    return "\n".join(lines)


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ 正在查询最新价格...")
    # Import here to avoid circular dependency
    from monitor import run_scan
    await run_scan(manual=True)
    cheapest = get_cheapest_per_route()
    await update.message.reply_text(format_summary(cheapest), parse_mode="HTML")


async def cmd_routes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📋 <b>监控路线</b>\n"]
    for r in ROUTES:
        lines.append(f"• {r['label']}")
    lines.append("\n<b>价格阈值</b>")
    for t in THRESHOLDS:
        lines.append(f"{t['emoji']} MYR {t['max_price']} — {t['label']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("用法: /history JHB KIX")
        return
    route = f"{args[0].upper()}-{args[1].upper()}"
    history = get_price_history(route)
    if not history:
        await update.message.reply_text(f"暂无 {route} 的历史数据")
        return
    lines = [f"📈 <b>{route} 近30天最低价</b>\n"]
    for h in history[-15:]:  # Show last 15 dates
        lines.append(f"{h['fly_date']}: MYR {h['min_price']:.0f}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def setup_handlers(app):
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("routes", cmd_routes))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("start", cmd_routes))
```

**Step 2: Test send message**

```bash
cd ~/flight-monitor && source venv/bin/activate && python3 -c "
import asyncio
from telegram_bot import get_app, send_message
async def test():
    app = get_app()
    await app.initialize()
    await send_message(app, '🛫 Flight Monitor 已上线！')
    await app.shutdown()
asyncio.run(test())
"
```

Expected: Telegram receives the message.

**Step 3: Commit**

```bash
git add telegram_bot.py && git commit -m "feat: add Telegram bot with send and command handlers"
```

---

### Task 5: Main Monitor Pipeline

**Files:**
- Create: `~/flight-monitor/monitor.py`

**Step 1: Write monitor.py**

```python
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import ROUTES, THRESHOLDS, SCAN_MONTHS_AHEAD, ALERT_DEDUP_HOURS
from db import init_db, save_price, get_previous_price, was_alert_sent, save_alert, get_cheapest_per_route
from kiwi_client import scan_route_months
from telegram_bot import get_app, send_message, format_alert, format_summary, setup_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def classify_price(price):
    for t in THRESHOLDS:  # sorted low to high
        if price < t["max_price"]:
            return t
    return None


async def run_scan(manual=False):
    app = get_app()
    await app.initialize()

    for route in ROUTES:
        route_key = f"{route['from']}-{route['to']}"
        log.info(f"Scanning {route_key}...")

        try:
            results = scan_route_months(route["from"], route["to"], SCAN_MONTHS_AHEAD)
        except Exception as e:
            log.error(f"Failed to scan {route_key}: {e}")
            continue

        for flight in results:
            prev_price = get_previous_price(route_key, flight["fly_date"])
            save_price(
                route_key, flight["fly_date"], flight["price"],
                flight["airline"], flight["stops"], flight["deep_link"],
            )

            level = classify_price(flight["price"])
            if level is None:
                continue

            if was_alert_sent(route_key, flight["fly_date"], flight["price"], ALERT_DEDUP_HOURS):
                continue

            msg = format_alert(flight, route["label"], level, prev_price)
            try:
                await send_message(app, msg)
                save_alert(route_key, flight["fly_date"], flight["price"], level["level"])
                log.info(f"Alert sent: {route_key} {flight['fly_date']} MYR {flight['price']}")
            except Exception as e:
                log.error(f"Failed to send alert: {e}")

    await app.shutdown()


async def send_daily_summary():
    app = get_app()
    await app.initialize()
    cheapest = get_cheapest_per_route()
    msg = format_summary(cheapest)
    try:
        await send_message(app, msg)
        log.info("Daily summary sent")
    except Exception as e:
        log.error(f"Failed to send summary: {e}")
    await app.shutdown()


async def main():
    init_db()
    log.info("Flight Monitor starting...")

    # Run initial scan
    await run_scan()

    # Set up scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_scan, "cron", hour="8,20", minute=0, id="scan")
    scheduler.add_job(send_daily_summary, "cron", hour=8, minute=5, id="summary")
    scheduler.start()
    log.info("Scheduler started: scan at 08:00/20:00, summary at 08:05")

    # Set up Telegram bot polling
    app = get_app()
    setup_handlers(app)
    log.info("Telegram bot polling started")

    # run_polling() blocks, handles graceful shutdown
    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Test full pipeline (requires Kiwi API key)**

```bash
cd ~/flight-monitor && source venv/bin/activate && python3 monitor.py
```

Expected: Scans all routes, sends alerts for any prices below MYR 250, starts scheduler and Telegram polling.

**Step 3: Commit**

```bash
git add monitor.py && git commit -m "feat: add main monitor pipeline with scheduler and Telegram polling"
```

---

### Task 6: Integration Test & Polish

**Step 1: Verify Telegram commands work**

- Send `/routes` to bot → should list all 4 routes and thresholds
- Send `/check` to bot → should trigger manual scan and return summary
- Send `/history KUL KIX` → should return price history

**Step 2: Verify alerts are deduped**

Run `python monitor.py` twice within 12 hours — same price alerts should not be re-sent.

**Step 3: Final commit**

```bash
git add -A && git commit -m "chore: flight monitor v1.0 ready"
```
