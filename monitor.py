import logging
from datetime import time
from config import ROUTES, THRESHOLDS, SCAN_MONTHS_AHEAD, ALERT_DEDUP_HOURS
from db import init_db, save_price, get_previous_price, was_alert_sent, save_alert, get_cheapest_per_route
from flights_client import scan_route_months
from promo_monitor import check_promos, format_promo_alert
from telegram_bot import get_app, send_message, format_alert, format_summary, setup_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Shared app instance, set in main()
_app = None


def classify_price(price):
    for t in THRESHOLDS:  # sorted low to high
        if price < t["max_price"]:
            return t
    return None


async def run_scan(context=None):
    """Scan all routes. Called by JobQueue or /check command."""
    global _app
    app = _app

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


async def check_promo_feeds(context=None):
    """Check airline promo RSS feeds for sales."""
    global _app
    try:
        promos = check_promos()
        for promo in promos[:3]:  # Max 3 promos per check
            if was_alert_sent("promo", promo["title"][:50], promo["score"], ALERT_DEDUP_HOURS):
                continue
            msg = format_promo_alert(promo)
            await send_message(_app, msg)
            save_alert("promo", promo["title"][:50], promo["score"], "PROMO")
            log.info(f"Promo alert sent: {promo['title'][:60]}")
    except Exception as e:
        log.error(f"Failed to check promos: {e}")


async def send_daily_summary(context=None):
    """Send daily cheapest price summary."""
    global _app
    cheapest = get_cheapest_per_route()
    msg = format_summary(cheapest)
    try:
        await send_message(_app, msg)
        log.info("Daily summary sent")
    except Exception as e:
        log.error(f"Failed to send summary: {e}")


async def post_init(application):
    """Called after app.initialize(). Set up jobs and run initial scan."""
    global _app
    _app = application

    # Schedule recurring jobs via built-in JobQueue
    jq = application.job_queue
    jq.run_repeating(run_scan, interval=3600 * 2, first=10, name="scan")
    jq.run_daily(send_daily_summary, time=time(hour=8, minute=5), name="summary")
    jq.run_repeating(check_promo_feeds, interval=3600 * 4, first=60, name="promo_check")
    log.info("Jobs scheduled: scan every 2h, summary at 08:05, promo every 4h")

    # Run initial scan on startup
    log.info("Running initial scan...")
    await run_scan()


def main():
    init_db()
    log.info("Flight Monitor starting...")

    app = get_app()
    setup_handlers(app)
    app.post_init = post_init

    # run_polling() is synchronous — it manages the event loop,
    # starts polling, and blocks until Ctrl+C
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
