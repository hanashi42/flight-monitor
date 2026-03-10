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
