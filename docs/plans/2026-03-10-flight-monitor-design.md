# Flight Monitor Design

## Overview

Flight price monitoring tool for JHB/KUL ↔ KIX routes with Telegram push notifications.

## Routes

| # | From | To   | Note |
|---|------|------|------|
| 1 | JHB  | KIX  | 含转机 |
| 2 | KUL  | KIX  | 直飞+转机 |
| 3 | KIX  | JHB  | 回程 |
| 4 | KIX  | KUL  | 回程 |

## Data Source

**Kiwi Tequila API** (free, unlimited search, commission-based model)
- Register at https://tequila.kiwi.com/
- 150+ airlines, auto-combines connecting flights
- Returns deep links for booking

## Query Strategy

1. **Monthly scan** (2x/day, morning 8:00 + evening 20:00):
   - For each route, query next 6 months by month
   - Get cheapest price per month
2. **Daily drill-down**: When a month's lowest < MYR 250, query individual dates in that month
3. **Return pairing**: When outbound is cheap, auto-check return flights 7-11 days later

## Price Thresholds & Alerts

| Single-leg Price | Level | Label |
|-----------------|-------|-------|
| < MYR 250       | LOW   | 低价 |
| < MYR 200       | VERY_LOW | 超低价 |
| < MYR 150       | BUY_NOW | 立刻买 |

## Notifications (Telegram Bot)

### Real-time Alert (on each query, when new low found)

```
🟠 超低价！KUL → KIX
📅 2026-04-15 (Tue)
✈️ AirAsia X (1次转机)
💰 MYR 189 (↓ MYR 36)
🔗 https://kiwi.com/...

回程参考：KIX → KUL
📅 2026-04-22~26 最低 MYR 210
```

- Dedup: same route+date+price within 12h not re-sent
- Price drop from previous query shown as ↓/↑

### Daily Summary (8:00 AM)

Table of cheapest price per route across all monitored months.

### Telegram Commands

- `/check` — query all routes now, return current cheapest
- `/routes` — list monitored routes and thresholds
- `/history` — 30-day price trend for a route

## Data Storage (SQLite)

```sql
CREATE TABLE prices (
    id INTEGER PRIMARY KEY,
    route TEXT NOT NULL,        -- 'JHB-KIX', 'KUL-KIX', etc.
    fly_date TEXT NOT NULL,     -- 'YYYY-MM-DD'
    price REAL NOT NULL,        -- MYR
    airline TEXT,
    stops INTEGER DEFAULT 0,
    deep_link TEXT,
    queried_at TEXT NOT NULL    -- ISO timestamp
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    route TEXT NOT NULL,
    fly_date TEXT NOT NULL,
    price REAL NOT NULL,
    level TEXT NOT NULL,        -- 'LOW', 'VERY_LOW', 'BUY_NOW'
    sent_at TEXT NOT NULL
);

CREATE INDEX idx_prices_route_date ON prices(route, fly_date);
CREATE INDEX idx_alerts_dedup ON alerts(route, fly_date, price);
```

## Project Structure

```
~/flight-monitor/
├── config.py          # API keys, routes, thresholds, Telegram config
├── monitor.py         # Main: scan → store → alert pipeline
├── kiwi_client.py     # Kiwi Tequila API wrapper
├── telegram_bot.py    # Telegram send + command handler (polling)
├── db.py              # SQLite operations
├── prices.db          # Auto-created
└── requirements.txt   # requests, python-telegram-bot, apscheduler
```

## Scheduling

- `APScheduler` in-process:
  - `scan_job`: runs at 08:00 and 20:00 daily
  - `summary_job`: runs at 08:00 daily
- Telegram bot polling runs in background thread

Single process: `python monitor.py` starts scheduler + telegram polling.

## Deployment

### Local
```bash
python monitor.py  # runs forever: scheduler + telegram bot
```

### Cloud (PythonAnywhere / Railway / Render)
- PythonAnywhere: "Always-on task" (free tier has scheduled tasks, paid has always-on)
- Railway/Render: free tier container, run `python monitor.py`

## Setup Steps

### 1. Kiwi Tequila API Key
1. Go to https://tequila.kiwi.com/
2. Create account → get API key
3. Put in `config.py`

### 2. Telegram Bot
1. Open Telegram, search `@BotFather`
2. Send `/newbot`, follow prompts, pick a name
3. Copy the bot token
4. Send any message to your new bot
5. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Find `chat.id` from the response
7. Put token + chat_id in `config.py`

## Dependencies

- `requests` — HTTP calls to Kiwi API
- `python-telegram-bot` — Telegram bot framework
- `APScheduler` — in-process cron scheduling
- Python 3.10+, no other system deps
