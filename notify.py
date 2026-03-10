import logging
import requests
from config import NTFY_TOPIC

log = logging.getLogger(__name__)

NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"


def send_alert(title, message, priority="default", tags=None):
    """Send notification via ntfy.sh using JSON body for UTF-8 support."""
    payload = {
        "topic": NTFY_TOPIC,
        "title": title,
        "message": message,
        "priority": _priority_to_int(priority),
    }
    if tags:
        payload["tags"] = tags

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
        arrow = "↓" if change < 0 else "↑"
        diff = f" ({arrow} MYR {abs(change):.0f})"

    stops_text = "直飞" if flight["stops"] == 0 else f"{flight['stops']}次转机"
    title = f"{level_info['emoji']} {level_info['label']}！{route_label}"
    body = (
        f"📅 {flight['fly_date']}\n"
        f"✈️ {flight['airline']} ({stops_text})\n"
        f"💰 MYR {flight['price']:.0f}{diff}\n"
        f"🔗 {flight['deep_link']}"
    )

    priority = "urgent" if level_info["level"] == "BUY_NOW" else "high" if level_info["level"] == "VERY_LOW" else "default"
    tags = ["airplane", level_info["level"].lower()]
    return title, body, priority, tags


def format_summary(cheapest_list):
    """Format daily summary for ntfy."""
    if not cheapest_list:
        return "每日价格汇总", "暂无数据", "low", ["chart_with_upwards_trend"]

    lines = []
    for item in cheapest_list:
        stops_text = "直飞" if item["stops"] == 0 else f"{item['stops']}转"
        lines.append(
            f"{item['route']}: MYR {item['price']:.0f} "
            f"({item['fly_date']}, {item['airline']}, {stops_text})"
        )
    return "📊 每日价格汇总", "\n".join(lines), "low", ["chart_with_upwards_trend"]


def format_promo_alert(promo):
    """Format promo alert for ntfy."""
    emoji = "🔥" if promo["score"] >= 10 else "📢"
    title = f"{emoji} 促销警报！"
    body = f"📰 {promo['source']}\n📌 {promo['title']}\n🔗 {promo['link']}"
    priority = "high" if promo["score"] >= 10 else "default"
    return title, body, priority, ["loudspeaker"]
