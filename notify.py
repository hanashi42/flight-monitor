import logging
import requests
from config import NTFY_TOPIC

log = logging.getLogger(__name__)

NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"


def send_alert(title, message, priority="default", tags=None, click_url=None):
    """Send notification via ntfy.sh using JSON body for UTF-8 support."""
    payload = {
        "topic": NTFY_TOPIC,
        "title": title,
        "message": message,
        "priority": _priority_to_int(priority),
    }
    if tags:
        payload["tags"] = tags
    if click_url:
        payload["click"] = click_url

    try:
        resp = requests.post("https://ntfy.sh", json=payload, timeout=10)
        resp.raise_for_status()
        log.info(f"ntfy sent: {title}")
    except Exception as e:
        log.error(f"ntfy failed: {e}")


def _priority_to_int(p):
    return {"low": 2, "default": 3, "high": 4, "urgent": 5}.get(p, 3)


def format_price_alert(flight, route_label, level_info, prev_price=None):
    """Format flight alert for ntfy."""
    diff = ""
    if prev_price is not None and prev_price > 0:
        change = flight["price"] - prev_price
        arrow = "\u2193" if change < 0 else "\u2191"
        diff = f" ({arrow} MYR {abs(change):.0f})"

    stops_text = "\u76f4\u98de" if flight["stops"] == 0 else f"{flight['stops']}\u6b21\u8f6c\u673a"
    title = f"{level_info['emoji']} {level_info['label']}\uff01{route_label}"
    body = (
        f"\U0001f4c5 {flight['fly_date']}\n"
        f"\u2708\ufe0f {flight['airline']} ({stops_text})\n"
        f"\U0001f4b0 MYR {flight['price']:.0f}{diff}\n"
        f"\U0001f517 Google Flights: {flight['deep_link']}\n"
        f"\U0001f6eb AirAsia: {flight.get('airasia_link', '')}"
    )

    priority = (
        "urgent" if level_info["level"] == "BUY_NOW"
        else "high" if level_info["level"] == "VERY_LOW"
        else "default"
    )
    tags = ["airplane", level_info["level"].lower()]

    # Click action opens AirAsia MOVE search directly
    click_url = flight.get("airasia_link", flight["deep_link"])

    return title, body, priority, tags, click_url


def format_summary(cheapest_list):
    """Format daily summary for ntfy."""
    if not cheapest_list:
        return "\u6bcf\u65e5\u4ef7\u683c\u6c47\u603b", "\u6682\u65e0\u6570\u636e", "low", ["chart_with_upwards_trend"], None

    lines = []
    for item in cheapest_list:
        stops_text = "\u76f4\u98de" if item["stops"] == 0 else f"{item['stops']}\u8f6c"
        lines.append(
            f"{item['route']}: MYR {item['price']:.0f} "
            f"({item['fly_date']}, {item['airline']}, {stops_text})"
        )
    return "\U0001f4ca \u6bcf\u65e5\u4ef7\u683c\u6c47\u603b", "\n".join(lines), "low", ["chart_with_upwards_trend"], None


def format_promo_alert(promo):
    """Format promo alert for ntfy."""
    emoji = "\U0001f525" if promo["score"] >= 10 else "\U0001f4e2"
    title = f"{emoji} \u4fc3\u9500\u8b66\u62a5\uff01"
    body = f"\U0001f4f0 {promo['source']}\n\U0001f4cc {promo['title']}\n\U0001f517 {promo['link']}"
    priority = "high" if promo["score"] >= 10 else "default"
    return title, body, priority, ["loudspeaker"], promo["link"]
