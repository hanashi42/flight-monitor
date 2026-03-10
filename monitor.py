import logging
import sys
from config import ORIGINS, DESTINATIONS, SCAN_MONTHS_AHEAD, ALERT_DEDUP_HOURS
from db import init_db, save_price, get_previous_price, was_alert_sent, save_alert, get_cheapest_per_route
from flights_client import scan_route_months
from promo_monitor import check_promos
from notify import send_alert, format_price_alert, format_summary, format_promo_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def build_routes():
    """Build route list from origins × destinations, both directions."""
    routes = []
    for origin in ORIGINS:
        for tier_name, tier in DESTINATIONS.items():
            for dest in tier["airports"]:
                routes.append({
                    "from": origin,
                    "to": dest["code"],
                    "label": f"{origin} → {dest['name']}",
                    "thresholds": tier["threshold"],
                })
    return routes


def classify_price(price, thresholds):
    for t in thresholds:
        if price < t["max_price"]:
            return t
    return None


def run_scan():
    """Scan all routes, save prices, send alerts for low prices."""
    routes = build_routes()
    log.info(f"Scanning {len(routes)} routes...")

    for route in routes:
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

            level = classify_price(flight["price"], route["thresholds"])
            if level is None:
                continue

            if was_alert_sent(route_key, flight["fly_date"], flight["price"], ALERT_DEDUP_HOURS):
                continue

            title, body, priority, tags = format_price_alert(flight, route["label"], level, prev_price)
            send_alert(title, body, priority, tags)
            save_alert(route_key, flight["fly_date"], flight["price"], level["level"])


def run_summary():
    """Send daily cheapest price summary."""
    cheapest = get_cheapest_per_route()
    title, body, priority, tags = format_summary(cheapest)
    send_alert(title, body, priority, tags)


def run_promos():
    """Check promo feeds and alert on relevant ones."""
    promos = check_promos()
    for promo in promos[:3]:
        if was_alert_sent("promo", promo["title"][:50], promo["score"], ALERT_DEDUP_HOURS):
            continue
        title, body, priority, tags = format_promo_alert(promo)
        send_alert(title, body, priority, tags)
        save_alert("promo", promo["title"][:50], promo["score"], "PROMO")


def main():
    init_db()

    command = sys.argv[1] if len(sys.argv) > 1 else "scan"

    if command == "scan":
        log.info("Running flight scan...")
        run_scan()
        run_promos()
        log.info("Scan complete.")
    elif command == "summary":
        log.info("Sending daily summary...")
        run_summary()
    elif command == "promos":
        log.info("Checking promos...")
        run_promos()
    else:
        print(f"Usage: python monitor.py [scan|summary|promos]")
        sys.exit(1)


if __name__ == "__main__":
    main()
