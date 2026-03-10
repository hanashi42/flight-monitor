import re
import logging
import requests
from xml.etree import ElementTree

log = logging.getLogger(__name__)

# AirAsia and budget airline promo sources
PROMO_FEEDS = [
    {
        "name": "SingPromos",
        "url": "https://singpromos.com/feed/",
    },
    {
        "name": "TheSmartLocal MY",
        "url": "https://thesmartlocal.com/malaysia/feed/",
    },
    {
        "name": "SoyaCincau",
        "url": "https://soyacincau.com/feed/",
    },
    {
        "name": "EverydayOnSales",
        "url": "https://www.everydayonsales.com/feed/",
    },
]

# Keywords that indicate a relevant promo (case-insensitive)
PROMO_KEYWORDS_HIGH = ["big sale", "free seats", "big member", "super sale", "flash sale"]
PROMO_KEYWORDS_LOW = ["airasia", "air asia", "scoot", "vietjet", "cebu pacific", "jetstar"]
ROUTE_KEYWORDS = ["japan", "osaka", "kansai", "kix", "tokyo", "nrt", "hnd"]


def fetch_rss(url, timeout=15):
    """Fetch and parse RSS feed. Returns list of items with title, link, description, pubDate."""
    headers = {"User-Agent": "Mozilla/5.0 (FlightMonitor/1.0)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    root = ElementTree.fromstring(resp.content)
    items = []

    # RSS 2.0
    for item in root.iter("item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        desc = item.findtext("description", "")
        pub = item.findtext("pubDate", "")
        items.append({"title": title, "link": link, "description": desc, "pubDate": pub})

    # Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns)
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href", "") if link_el is not None else ""
        desc = entry.findtext("atom:summary", "", ns) or entry.findtext("atom:content", "", ns)
        pub = entry.findtext("atom:published", "", ns) or entry.findtext("atom:updated", "", ns)
        items.append({"title": title, "link": link, "description": desc, "pubDate": pub})

    return items


def score_promo(title, description):
    """Score how relevant a promo item is. Higher = more relevant."""
    text = f"{title} {description}".lower()
    score = 0

    for kw in PROMO_KEYWORDS_HIGH:
        if kw in text:
            score += 10

    for kw in PROMO_KEYWORDS_LOW:
        if kw in text:
            score += 3

    for kw in ROUTE_KEYWORDS:
        if kw in text:
            score += 5

    return score


def check_promos():
    """Check all promo feeds. Returns list of relevant promos sorted by score."""
    promos = []

    for feed in PROMO_FEEDS:
        try:
            items = fetch_rss(feed["url"])
            for item in items[:10]:  # Only check latest 10
                score = score_promo(item["title"], item["description"])
                if score >= 5:  # At least somewhat relevant
                    promos.append({
                        "source": feed["name"],
                        "title": item["title"],
                        "link": item["link"],
                        "score": score,
                    })
        except Exception as e:
            log.warning(f"Failed to fetch {feed['name']}: {e}")

    promos.sort(key=lambda p: p["score"], reverse=True)
    return promos


def format_promo_alert(promo):
    """Format a promo for Telegram."""
    if promo["score"] >= 10:
        emoji = "🔥"
        label = "促销警报"
    else:
        emoji = "📢"
        label = "促销信息"

    return (
        f"{emoji} <b>{label}！</b>\n"
        f"📰 {promo['source']}\n"
        f"📌 {promo['title']}\n"
        f"🔗 <a href=\"{promo['link']}\">查看详情</a>"
    )
