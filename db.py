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
